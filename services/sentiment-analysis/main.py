"""
MSA Sentiment Analysis Service

Background worker that processes texts from Pub/Sub using Gemini AI,
stores results in BigQuery, and publishes to analyzed-data topic.
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
import structlog

# Add parent directory to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import RawDataMessage, AnalyzedDataMessage
from shared.pubsub import PubSubSubscriber, PubSubPublisher
from shared.bigquery import BigQueryClient
from gemini_client import GeminiClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "msa-project")
RAW_DATA_SUBSCRIPTION = os.getenv("RAW_DATA_SUBSCRIPTION", "raw-data-sentiment-sub")
ANALYZED_DATA_TOPIC = os.getenv("ANALYZED_DATA_TOPIC", "analyzed-data-topic")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "msa_production")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))

# Global clients
subscriber: PubSubSubscriber = None
publisher: PubSubPublisher = None
bq_client: BigQueryClient = None
gemini_client: GeminiClient = None


async def process_message(message: RawDataMessage):
    """
    Process a single message from Pub/Sub.
    
    Args:
        message: Raw data message to process
    """
    start_time = datetime.now()
    
    logger.info(
        "Processing message",
        text_id=message.text_id,
        tenant_id=message.tenant_id
    )
    
    try:
        # Analyze sentiment using Gemini
        sentiment_result = await gemini_client.analyze_sentiment(message.text)
        
        if not sentiment_result:
            logger.error("Failed to get sentiment result", text_id=message.text_id)
            return
        
        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Create analyzed message
        analyzed_message = AnalyzedDataMessage(
            message_id=f"{message.message_id}-analyzed",
            timestamp=datetime.now(),
            tenant_id=message.tenant_id,
            text_id=message.text_id,
            original_message_id=message.message_id,
            sentiment_result=sentiment_result,
            processing_metadata={
                "model": "gemini-2.0-flash-exp",
                "processing_time_ms": processing_time_ms,
                "retry_count": 0,
                "processed_at": datetime.now().isoformat()
            },
            original_metadata=message.metadata
        )
        
        # Store in BigQuery
        sentiment_row = {
            "sentiment_id": f"{message.text_id}-sentiment",
            "text_id": message.text_id,
            "tenant_id": message.tenant_id,
            "message_id": message.message_id,
            "overall_sentiment": sentiment_result.overall_sentiment.value,
            "sentiment_score": sentiment_result.sentiment_score,
            "confidence": sentiment_result.confidence,
            "emotion_joy": sentiment_result.emotions.joy if sentiment_result.emotions else 0.0,
            "emotion_anger": sentiment_result.emotions.anger if sentiment_result.emotions else 0.0,
            "emotion_sadness": sentiment_result.emotions.sadness if sentiment_result.emotions else 0.0,
            "emotion_fear": sentiment_result.emotions.fear if sentiment_result.emotions else 0.0,
            "emotion_surprise": sentiment_result.emotions.surprise if sentiment_result.emotions else 0.0,
            "key_phrases": sentiment_result.key_phrases,
            "entities": sentiment_result.entities,
            "is_toxic": sentiment_result.toxicity.is_toxic if sentiment_result.toxicity else False,
            "toxicity_score": sentiment_result.toxicity.toxicity_score if sentiment_result.toxicity else 0.0,
            "toxicity_details": sentiment_result.toxicity.categories if sentiment_result.toxicity else {},
            "model": "gemini-2.0-flash-exp",
            "processing_time_ms": processing_time_ms,
            "retry_count": 0,
            "processed_at": datetime.now().isoformat(),
            "metadata": message.metadata,
            "created_at": datetime.now().isoformat()
        }
        
        await bq_client.insert_row("sentiments", sentiment_row, row_id=message.text_id)
        
        # Publish to analyzed-data topic
        await publisher.publish(analyzed_message)
        
        logger.info(
            "Message processed successfully",
            text_id=message.text_id,
            sentiment=sentiment_result.overall_sentiment.value,
            processing_time_ms=processing_time_ms
        )
        
    except Exception as e:
        logger.error(
            "Error processing message",
            text_id=message.text_id,
            error=str(e)
        )
        raise


async def main():
    """Main worker loop."""
    global subscriber, publisher, bq_client, gemini_client
    
    logger.info("Starting Sentiment Analysis Service")
    
    try:
        # Initialize clients
        subscriber = PubSubSubscriber(PROJECT_ID, RAW_DATA_SUBSCRIPTION, max_messages=BATCH_SIZE)
        publisher = PubSubPublisher(PROJECT_ID, ANALYZED_DATA_TOPIC)
        bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET)
        gemini_client = GeminiClient()
        
        logger.info("Clients initialized, starting message consumption")
        
        # Start consuming messages
        await subscriber.start_consuming(
            callback=process_message,
            model_class=RawDataMessage,
            poll_interval_seconds=POLL_INTERVAL
        )
        
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        raise
    finally:
        # Cleanup
        if publisher:
            await publisher.close()
        if bq_client:
            bq_client.close()
        if subscriber:
            subscriber.close()
        
        logger.info("Sentiment Analysis Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
