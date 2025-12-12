"""
MSA API Service

Public REST API for querying sentiment data and aggregated metrics.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
import structlog

# Add parent directory to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import (
    SentimentQuery,
    SentimentQueryResponse,
    SentimentQueryResult,
    Met ricsQuery,
    MetricsResponse,
    AggregatedMetric,
    HealthResponse,
    EmotionScores,
)
from shared.bigquery import BigQueryClient
from shared.auth import rate_limit_dependency

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Configuration  
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "msa-project")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "msa_production")
ENV = os.getenv("ENV", "development")

# Global clients
bq_client: Optional[BigQueryClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager."""
    global bq_client
    
    logger.info("Starting API Service", env=ENV)
    bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET)
    logger.info("BigQuery client initialized")
    
    yield
    
    if bq_client:
        bq_client.close()
    logger.info("API Service stopped")


# Create FastAPI app
app = FastAPI(
    title="MSA API Service",
    description="Query API for sentiment analysis data",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="api",
        timestamp=datetime.now(),
        version="1.0.0"
    )


@app.get("/v1/sentiments", response_model=SentimentQueryResponse)
async def query_sentiments(
    tenant_id: str = Depends(rate_limit_dependency),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    sentiment: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Query sentiment results.
    
    Args:
        tenant_id: Tenant ID (from API key)
        start_date: Optional start date filter
        end_date: Optional end date filter
        sentiment: Optional sentiment filter
        limit: Max results (1-1000)
        offset: Pagination offset
    """
    logger.info(
        "Sentiment query",
        tenant_id=tenant_id,
        limit=limit,
        offset=offset
    )
    
    try:
        # Query BigQuery
        results = await bq_client.query_sentiments(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            sentiment=sentiment,
            limit=limit,
            offset=offset
        )
        
        # Get total count (simplified - in production, run separate COUNT query)
        total = len(results)
        
        # Convert to response model
        query_results = [
            SentimentQueryResult(
                text_id=row["text_id"],
                text=row.get("text", ""),
                overall_sentiment=row["overall_sentiment"],
                sentiment_score=row["sentiment_score"],
                confidence=row["confidence"],
                processed_at=row["processed_at"],
                metadata=row.get("metadata")
            )
            for row in results
        ]
        
        return SentimentQueryResponse(
            total=total,
            limit=limit,
            offset=offset,
            results=query_results
        )
        
    except Exception as e:
        logger.error(f"Error querying sentiments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query sentiments: {str(e)}"
        )


@app.get("/v1/metrics/aggregated", response_model=MetricsResponse)
async def query_metrics(
    tenant_id: str = Depends(rate_limit_dependency),
    aggregation_level: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$"),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
):
    """
    Query aggregated metrics.
    
    Args:
        tenant_id: Tenant ID (from API key)
        aggregation_level: Aggregation level (hourly, daily, weekly, monthly)
        start_date: Start date (required)
        end_date: End date (required)
    """
    logger.info(
        "Metrics query",
        tenant_id=tenant_id,
        level=aggregation_level,
        start=start_date,
        end=end_date
    )
    
    try:
        # Query BigQuery
        results = await bq_client.query_aggregated_metrics(
            tenant_id=tenant_id,
            aggregation_level=aggregation_level,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to response model
        metrics = [
            AggregatedMetric(
                date=row["period_start"].strftime("%Y-%m-%d"),
                total_texts=row["total_texts"],
                sentiment_breakdown={
                    "positive": row.get("total_positive", 0),
                    "negative": row.get("total_negative", 0),
                    "neutral": row.get("total_neutral", 0),
                    "mixed": row.get("total_mixed", 0),
                },
                avg_sentiment_score=row.get("avg_sentiment_score", 0.0),
                emotions=EmotionScores(
                    joy=row.get("avg_emotion_joy", 0.0),
                    anger=row.get("avg_emotion_anger", 0.0),
                    sadness=row.get("avg_emotion_sadness", 0.0),
                    fear=row.get("avg_emotion_fear", 0.0),
                    surprise=row.get("avg_emotion_surprise", 0.0),
                ),
                toxicity_rate=row.get("toxicity_rate", 0.0),
                trend=row.get("sentiment_trend", "stable"),
                trend_score=row.get("trend_score", 0.0),
            )
            for row in results
        ]
        
        return MetricsResponse(
            aggregation_level=aggregation_level,
            period_start=start_date,
            period_end=end_date,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Error querying metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query metrics: {str(e)}"
        )


@app.get("/v1/status/{text_id}")
async def check_status(
    text_id: str,
    tenant_id: str = Depends(rate_limit_dependency),
):
    """
    Check the analysis status of a specific text.
    
    Args:
        text_id: Text ID to check
        tenant_id: Tenant ID (from API key)
    """
    logger.info("Status check", text_id=text_id, tenant_id=tenant_id)
    
    try:
        # Query BigQuery for the text
        query = f"""
        SELECT
            text_id,
            overall_sentiment,
            sentiment_score,
            processed_at
        FROM `{PROJECT_ID}.{BIGQUERY_DATASET}.sentiments`
        WHERE text_id = @text_id
          AND tenant_id = @tenant_id
        LIMIT 1
        """
        
        from google.cloud import bigquery
        params = [
            bigquery.ScalarQueryParameter("text_id", "STRING", text_id),
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
        ]
        
        results = await bq_client.query(query, params)
        
        if not results:
            return {
                "text_id": text_id,
                "status": "not_found",
                "message": "Text analysis not found or still processing"
            }
        
        result = results[0]
        return {
            "text_id": text_id,
            "status": "completed",
            "sentiment": result["overall_sentiment"],
            "score": result["sentiment_score"],
            "processed_at": result["processed_at"],
        }
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check status: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
