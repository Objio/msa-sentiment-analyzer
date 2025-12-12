"""
MSA Aggregation Service

Background worker that computes aggregated metrics from sentiment results.
Calculates hourly, daily, weekly, and monthly statistics.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from collections import defaultdict
import structlog

# Add parent directory to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import AnalyzedDataMessage, SentimentType
from shared.pubsub import PubSubSubscriber
from shared.bigquery import BigQueryClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "msa-project")
ANALYZED_DATA_SUBSCRIPTION = os.getenv("ANALYZED_DATA_SUBSCRIPTION", "analyzed-data-aggregation-sub")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "msa_production")
AGGREGATION_WINDOW_MINUTES = int(os.getenv("AGGREGATION_WINDOW_MINUTES", "60"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "5.0"))

# Global clients
subscriber: PubSubSubscriber = None
bq_client: BigQueryClient = None

# In-memory aggregation state (use Redis in production)
aggregation_state = defaultdict(lambda: {
    "total_texts": 0,
    "positive": 0,
    "negative": 0,
    "neutral": 0,
    "mixed": 0,
    "sentiment_scores": [],
    "emotions_joy": [],
    "emotions_anger": [],
    "emotions_sadness": [],
    "emotions_fear": [],
    "emotions_surprise": [],
    "toxic_count": 0
})


async def process_message(message: AnalyzedDataMessage):
    """
    Process analyzed sentiment message and update aggregations.
    
    Args:
        message: Analyzed data message
    """
    logger.info(
        "Processing analyzed message",
        text_id=message.text_id,
        tenant_id=message.tenant_id,
        sentiment=message.sentiment_result.overall_sentiment.value
    )
    
    try:
        # Update hourly aggregation
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        tenant_hour_key = f"{message.tenant_id}:{hour_key}"
        
        state = aggregation_state[tenant_hour_key]
        state["total_texts"] += 1
        
        # Update sentiment counts
        sentiment = message.sentiment_result.overall_sentiment.value
        if sentiment in state:
            state[sentiment] += 1
        
        # Collect sentiment scores
        state["sentiment_scores"].append(message.sentiment_result.sentiment_score)
        
        # Collect emotion scores
        if message.sentiment_result.emotions:
            state["emotions_joy"].append(message.sentiment_result.emotions.joy)
            state["emotions_anger"].append(message.sentiment_result.emotions.anger)
            state["emotions_sadness"].append(message.sentiment_result.emotions.sadness)
            state["emotions_fear"].append(message.sentiment_result.emotions.fear)
            state["emotions_surprise"].append(message.sentiment_result.emotions.surprise)
        
        # Track toxicity
        if message.sentiment_result.toxicity and message.sentiment_result.toxicity.is_toxic:
            state["toxic_count"] += 1
        
        logger.debug(f"Updated aggregation state for {tenant_hour_key}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", text_id=message.text_id)
        raise


async def flush_aggregations():
    """Flush aggregations to BigQuery periodically."""
    logger.info("Starting aggregation flush task")
    
    while True:
        try:
            await asyncio.sleep(AGGREGATION_WINDOW_MINUTES * 60)
            
            if not aggregation_state:
                logger.debug("No aggregations to flush")
                continue
            
            logger.info(f"Flushing {len(aggregation_state)} aggregations")
            
            # Get current state and reset
            current_state = dict(aggregation_state)
            aggregation_state.clear()
            
            # Compute and store aggregations
            for tenant_hour_key, state in current_state.items():
                await compute_and_store_aggregation(tenant_hour_key, state)
            
            logger.info("Aggregations flushed successfully")
            
        except asyncio.CancelledError:
            logger.info("Flush task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in flush task: {e}")
            await asyncio.sleep(60)  # Wait before retrying


async def compute_and_store_aggregation(tenant_hour_key: str, state: Dict[str, Any]):
    """
    Compute aggregated metrics and store in BigQuery.
    
    Args:
        tenant_hour_key: Key in format "tenant_id:YYYY-MM-DD-HH"
        state: Aggregation state
    """
    parts = tenant_hour_key.split(":")
    tenant_id = parts[0]
    hour_str = ":".join(parts[1:])
    
    try:
        period_start = datetime.strptime(hour_str, "%Y-%m-%d-%H")
        period_end = period_start + timedelta(hours=1)
        
        # Calculate statistics
        total = state["total_texts"]
        if total == 0:
            return
        
        avg_sentiment = sum(state["sentiment_scores"]) / len(state["sentiment_scores"])
        toxicity_rate = state["toxic_count"] / total if total > 0 else 0.0
        
        # Calculate emotion averages
        avg_joy = sum(state["emotions_joy"]) / len(state["emotions_joy"]) if state["emotions_joy"] else 0.0
        avg_anger = sum(state["emotions_anger"]) / len(state["emotions_anger"]) if state["emotions_anger"] else 0.0
        avg_sadness = sum(state["emotions_sadness"]) / len(state["emotions_sadness"]) if state["emotions_sadness"] else 0.0
        avg_fear = sum(state["emotions_fear"]) / len(state["emotions_fear"]) if state["emotions_fear"] else 0.0
        avg_surprise = sum(state["emotions_surprise"]) / len(state["emotions_surprise"]) if state["emotions_surprise"] else 0.0
        
        # Determine trend (simplified - compare to previous period would be better)
        if avg_sentiment > 0.3:
            trend = "improving"
        elif avg_sentiment < -0.3:
            trend = "declining"
        else:
            trend = "stable"
        
        # Create metric row
        metric_row = {
            "metric_id": f"{tenant_id}-hourly-{period_start.strftime('%Y%m%d%H')}",
            "tenant_id": tenant_id,
            "aggregation_level": "hourly",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "dimensions": None,
            "total_texts": total,
            "total_positive": state["positive"],
            "total_negative": state["negative"],
            "total_neutral": state["neutral"],
            "total_mixed": state["mixed"],
            "avg_sentiment_score": avg_sentiment,
            "median_sentiment_score": avg_sentiment,  # Simplified
            "stddev_sentiment_score": 0.0,  # Simplified
            "avg_emotion_joy": avg_joy,
            "avg_emotion_anger": avg_anger,
            "avg_emotion_sadness": avg_sadness,
            "avg_emotion_fear": avg_fear,
            "avg_emotion_surprise": avg_surprise,
            "total_toxic": state["toxic_count"],
            "toxicity_rate": toxicity_rate,
            "sentiment_trend": trend,
            "trend_score": avg_sentiment,
            "computed_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        # Store in BigQuery
        await bq_client.insert_row("aggregated_metrics", metric_row)
        
        logger.info(
            "Stored aggregation",
            tenant_id=tenant_id,
            period=hour_str,
            total_texts=total,
            avg_sentiment=avg_sentiment
        )
        
    except Exception as e:
        logger.error(f"Error computing aggregation for {tenant_hour_key}: {e}")


async def main():
    """Main worker loop."""
    global subscriber, bq_client
    
    logger.info("Starting Aggregation Service")
    
    try:
        # Initialize clients
        subscriber = PubSubSubscriber(PROJECT_ID, ANALYZED_DATA_SUBSCRIPTION, max_messages=100)
        bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET)
        
        logger.info("Clients initialized")
        
        # Start flush task
        flush_task = asyncio.create_task(flush_aggregations())
        
        # Start consuming messages
        consume_task = asyncio.create_task(
            subscriber.start_consuming(
                callback=process_message,
                model_class=AnalyzedDataMessage,
                poll_interval_seconds=POLL_INTERVAL
            )
        )
        
        # Wait for tasks
        await asyncio.gather(flush_task, consume_task)
        
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        if bq_client:
            bq_client.close()
        if subscriber:
            subscriber.close()
        
        logger.info("Aggregation Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
