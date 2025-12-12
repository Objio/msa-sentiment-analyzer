"""
Unit tests for shared models.

Tests Pydantic models for validation and serialization.
"""

import pytest
from datetime import datetime
from shared.models import (
    SentimentType,
    SentimentResult,
    AnalyzeRequest,
    RawDataMessage,
    AnalyzedDataMessage,
    EmotionScores,
)


def test_sentiment_type_enum():
    """Test SentimentType enum values."""
    assert SentimentType.POSITIVE == "positive"
    assert SentimentType.NEGATIVE == "negative"
    assert SentimentType.NEUTRAL == "neutral"
    assert SentimentType.MIXED == "mixed"


def test_emotion_scores_validation():
    """Test EmotionScores validation."""
    # Valid emotions
    emotions = EmotionScores(joy=0.8, anger=0.1, sadness=0.05, fear=0.02, surprise=0.03)
    assert emotions.joy == 0.8
    assert emotions.anger == 0.1
    
    # Invalid emotion (out of range)
    with pytest.raises(ValueError):
        EmotionScores(joy=1.5, anger=0.1)
    
    with pytest.raises(ValueError):
        EmotionScores(joy=-0.1, anger=0.1)


def test_sentiment_result_creation():
    """Test SentimentResult model."""
    result = SentimentResult(
        overall_sentiment=SentimentType.POSITIVE,
        sentiment_score=0.85,
        confidence=0.92,
        emotions=EmotionScores(joy=0.9, anger=0.0, sadness=0.0, fear=0.0, surprise=0.1)
    )
    
    assert result.overall_sentiment == SentimentType.POSITIVE
    assert result.sentiment_score == 0.85
    assert result.confidence == 0.92
    assert result.emotions.joy == 0.9


def test_analyze_request_validation():
    """Test AnalyzeRequest validation."""
    # Valid request
    request = AnalyzeRequest(
        text="This is a test",
        language="en"
    )
    assert request.text == "This is a test"
    assert request.language == "en"
    
    # Empty text should fail
    with pytest.raises(ValueError):
        AnalyzeRequest(text="", language="en")
    
    # Invalid language code
    with pytest.raises(ValueError):
        AnalyzeRequest(text="Test", language="english")


def test_raw_data_message_serialization():
    """Test RawDataMessage serialization."""
    message = RawDataMessage(
        message_id="test-123",
        timestamp=datetime.now(),
        tenant_id="tenant-1",
        source="api",
        text_id="text-456",
        text="Sample text",
        language="en"
    )
    
    # Serialize to dict
    data = message.model_dump()
    assert data["message_id"] == "test-123"
    assert data["tenant_id"] == "tenant-1"
    assert data["text"] == "Sample text"
    
    # Serialize to JSON
    json_str = message.model_dump_json()
    assert "test-123" in json_str
    assert "Sample text" in json_str


def test_analyzed_data_message_creation():
    """Test AnalyzedDataMessage with nested objects."""
    sentiment_result = SentimentResult(
        overall_sentiment=SentimentType.POSITIVE,
        sentiment_score=0.75,
        confidence=0.88
    )
    
    message = AnalyzedDataMessage(
        message_id="analyzed-123",
        timestamp=datetime.now(),
        tenant_id="tenant-1",
        text_id="text-456",
        original_message_id="original-123",
        sentiment_result=sentiment_result,
        processing_metadata={"model": "gemini-2.0-flash", "time_ms": 1500}
    )
    
    assert message.sentiment_result.overall_sentiment == SentimentType.POSITIVE
    assert message.sentiment_result.sentiment_score == 0.75
    assert message.processing_metadata["model"] == "gemini-2.0-flash"


def test_model_json_schema():
    """Test that models can generate JSON schemas."""
    schema = AnalyzeRequest.model_json_schema()
    
    assert "properties" in schema
    assert "text" in schema["properties"]
    assert "language" in schema["properties"]
    assert schema["required"] == ["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
