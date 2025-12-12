"""
Shared Pydantic models for MSA system.

These models are used for data validation, serialization,
and API request/response handling across all services.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class SentimentType(str, Enum):
    """Sentiment classification types."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class EmotionScores(BaseModel):
    """Emotion breakdown scores."""
    joy: float = Field(ge=0.0, le=1.0, default=0.0)
    anger: float = Field(ge=0.0, le=1.0, default=0.0)
    sadness: float = Field(ge=0.0, le=1.0, default=0.0)
    fear: float = Field(ge=0.0, le=1.0, default=0.0)
    surprise: float = Field(ge=0.0, le=1.0, default=0.0)


class KeyPhrase(BaseModel):
    """A key phrase extracted from text with sentiment."""
    phrase: str
    sentiment: SentimentType
    score: float = Field(ge=0.0, le=1.0)


class Entity(BaseModel):
    """Named entity detected in text."""
    text: str
    type: str
    sentiment: Optional[SentimentType] = None


class ToxicityResult(BaseModel):
    """Toxicity detection result."""
    is_toxic: bool
    toxicity_score: float = Field(ge=0.0, le=1.0)
    categories: Dict[str, float] = Field(default_factory=dict)


class SentimentResult(BaseModel):
    """Complete sentiment analysis result."""
    overall_sentiment: SentimentType
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    emotions: Optional[EmotionScores] = None
    key_phrases: Optional[List[KeyPhrase]] = None
    entities: Optional[List[Entity]] = None
    toxicity: Optional[ToxicityResult] = None


class AnalyzeOptions(BaseModel):
    """Options for sentiment analysis."""
    include_emotions: bool = True
    include_entities: bool = True
    include_key_phrases: bool = True
    detect_toxicity: bool = True


class AnalyzeRequest(BaseModel):
    """Request to analyze a single text."""
    text: str = Field(min_length=1, max_length=10000)
    language: str = Field(default="en", pattern="^[a-z]{2}$")
    metadata: Optional[Dict[str, Any]] = None
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class AnalyzeResponse(BaseModel):
    """Response from text analysis request."""
    text_id: str
    status: str  # "queued", "processing", "completed", "failed"
    sentiment_result: Optional[SentimentResult] = None
    processing_time_ms: Optional[int] = None
    processed_at: Optional[datetime] = None
    error: Optional[str] = None


class BatchAnalyzeRequest(BaseModel):
    """Request to analyze multiple texts."""
    texts: List[Dict[str, Any]] = Field(min_length=1, max_length=1000)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class BatchAnalyzeResponse(BaseModel):
    """Response from batch analysis request."""
    batch_id: str
    total_texts: int
    status: str  # "processing", "completed", "failed"
    estimated_completion: Optional[datetime] = None
    webhook_url: Optional[str] = None


class SourceMetadata(BaseModel):
    """Metadata about the source of data."""
    api_key: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    batch_id: Optional[str] = None


class RawDataMessage(BaseModel):
    """Message published to raw-data-topic."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "message_id": "uuid-v4",
            "timestamp": "2025-12-11T21:30:00Z",
            "tenant_id": "tenant-123",
            "source": "api",
            "text_id": "text-unique-id",
            "text": "This product is amazing!",
            "language": "en",
            "metadata": {}
        }
    })
    
    message_id: str
    timestamp: datetime
    tenant_id: str
    source: str  # "api", "webhook", "batch", "file_upload"
    source_metadata: Optional[SourceMetadata] = None
    text_id: str
    text: str
    language: str = "en"
    metadata: Optional[Dict[str, Any]] = None


class AnalyzedDataMessage(BaseModel):
    """Message published to analyzed-data-topic."""
    message_id: str
    timestamp: datetime
    tenant_id: str
    text_id: str
    original_message_id: str
    sentiment_result: SentimentResult
    processing_metadata: Dict[str, Any]
    original_metadata: Optional[Dict[str, Any]] = None


class SentimentQuery(BaseModel):
    """Query parameters for sentiment search."""
    tenant_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    sentiment: Optional[SentimentType] = None
    platform: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class SentimentQueryResult(BaseModel):
    """Result from sentiment query."""
    text_id: str
    text: str
    overall_sentiment: SentimentType
    sentiment_score: float
    confidence: float
    processed_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class SentimentQueryResponse(BaseModel):
    """Response from sentiment query."""
    total: int
    limit: int
    offset: int
    results: List[SentimentQueryResult]


class AggregatedMetric(BaseModel):
    """Pre-computed aggregated metric."""
    date: str
    total_texts: int
    sentiment_breakdown: Dict[str, int]
    avg_sentiment_score: float
    emotions: EmotionScores
    toxicity_rate: float
    trend: str  # "improving", "declining", "stable"
    trend_score: float


class MetricsQuery(BaseModel):
    """Query parameters for aggregated metrics."""
    tenant_id: str
    aggregation_level: str  # "hourly", "daily", "weekly", "monthly"
    start_date: datetime
    end_date: datetime
    dimensions: Optional[Dict[str, str]] = None


class MetricsResponse(BaseModel):
    """Response from metrics query."""
    aggregation_level: str
    period_start: datetime
    period_end: datetime
    metrics: List[AggregatedMetric]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    timestamp: datetime
    version: str = "1.0.0"
    details: Optional[Dict[str, Any]] = None
