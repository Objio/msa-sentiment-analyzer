"""
MSA Ingestion Service

FastAPI application for ingesting text data from multiple sources.
Validates, normalizes, and publishes data to the processing pipeline.
"""

import os
import logging
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
import structlog

# Add parent directory to path for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    RawDataMessage,
    SourceMetadata,
    HealthResponse,
)
from shared.pubsub import PubSubPublisher
from shared.bigquery import BigQueryClient
from shared.auth import rate_limit_dependency

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Configuration from environment
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "msa-project")
RAW_DATA_TOPIC = os.getenv("RAW_DATA_TOPIC", "raw-data-topic")
GCS_RAW_BUCKET = os.getenv("GCS_RAW_BUCKET", "msa-raw-data")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "msa_production")
ENV = os.getenv("ENV", "development")

# Global clients
publisher: Optional[PubSubPublisher] = None
bq_client: Optional[BigQueryClient] = None
storage_client: Optional[storage.Client] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown."""
    global publisher, bq_client, storage_client
    
    # Startup
    logger.info("Starting Ingestion Service", env=ENV)
    
    try:
        publisher = PubSubPublisher(PROJECT_ID, RAW_DATA_TOPIC)
        bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET)
        storage_client = storage.Client(project=PROJECT_ID)
        logger.info("Clients initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize clients", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ingestion Service")
    if publisher:
        await publisher.close()
    if bq_client:
        bq_client.close()


# Create FastAPI app
app = FastAPI(
    title="MSA Ingestion Service",
    description="Entry point for sentiment analysis data",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
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
        service="ingestion",
        timestamp=datetime.now(),
        version="1.0.0",
        details={
            "project_id": PROJECT_ID,
            "topic": RAW_DATA_TOPIC,
            "env": ENV
        }
    )


@app.post("/v1/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_text(
    request: AnalyzeRequest,
    tenant_id: str = Depends(rate_limit_dependency),
    x_api_key: str = Header(..., alias="X-API-Key"),
    user_agent: Optional[str] = Header(None),
):
    """
    Analyze a single text for sentiment.
    
    This endpoint queues the text for asynchronous processing.
    """
    text_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    logger.info(
        "Received analyze request",
        tenant_id=tenant_id,
        text_id=text_id,
        text_length=len(request.text)
    )
    
    try:
        # Create Pub/Sub message
        raw_message = RawDataMessage(
            message_id=message_id,
            timestamp=datetime.now(),
            tenant_id=tenant_id,
            source="api",
            source_metadata=SourceMetadata(
                api_key=x_api_key[:8] + "...",  # Partial for logging
                user_agent=user_agent
            ),
            text_id=text_id,
            text=request.text,
            language=request.language,
            metadata=request.metadata
        )
        
        # Publish to Pub/Sub
        await publisher.publish(raw_message)
        
        # Store in BigQuery for audit trail
        audit_row = {
            "text_id": text_id,
            "message_id": message_id,
            "tenant_id": tenant_id,
            "text": request.text,
            "language": request.language,
            "source": "api",
            "source_api_key": x_api_key[:8] + "...",
            "metadata": request.metadata,
            "ingested_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
        
        await bq_client.insert_row("raw_texts", audit_row, row_id=text_id)
        
        logger.info("Text queued for analysis", text_id=text_id)
        
        return AnalyzeResponse(
            text_id=text_id,
            status="queued"
        )
        
    except Exception as e:
        logger.error("Error processing analyze request", error=str(e), text_id=text_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue text for analysis: {str(e)}"
        )


@app.post("/v1/analyze/batch", response_model=BatchAnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    tenant_id: str = Depends(rate_limit_dependency),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """
    Analyze a batch of texts for sentiment.
    
    This endpoint queues multiple texts for asynchronous processing.
    """
    batch_id = str(uuid.uuid4())
    total_texts = len(request.texts)
    
    logger.info(
        "Received batch analyze request",
        tenant_id=tenant_id,
        batch_id=batch_id,
        total_texts=total_texts
    )
    
    try:
        messages = []
        audit_rows = []
        
        for text_data in request.texts:
            text_id = text_data.get("text_id", str(uuid.uuid4()))
            message_id = str(uuid.uuid4())
            
            # Create Pub/Sub message
            raw_message = RawDataMessage(
                message_id=message_id,
                timestamp=datetime.now(),
                tenant_id=tenant_id,
                source="batch",
                source_metadata=SourceMetadata(
                    api_key=x_api_key[:8] + "...",
                    batch_id=batch_id
                ),
                text_id=text_id,
                text=text_data.get("text", ""),
                language=text_data.get("language", "en"),
                metadata=text_data.get("metadata")
            )
            messages.append(raw_message)
            
            # Prepare audit row
            audit_rows.append({
                "text_id": text_id,
                "message_id": message_id,
                "tenant_id": tenant_id,
                "text": text_data.get("text", ""),
                "language": text_data.get("language", "en"),
                "source": "batch",
                "batch_id": batch_id,
                "metadata": text_data.get("metadata"),
                "ingested_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat()
            })
        
        # Publish batch to Pub/Sub
        await publisher.publish_batch(messages)
        
        # Store in BigQuery
        await bq_client.insert_rows("raw_texts", audit_rows)
        
        logger.info("Batch queued for analysis", batch_id=batch_id, total_texts=total_texts)
        
        return BatchAnalyzeResponse(
            batch_id=batch_id,
            total_texts=total_texts,
            status="processing"
        )
        
    except Exception as e:
        logger.error("Error processing batch request", error=str(e), batch_id=batch_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue batch for analysis: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
