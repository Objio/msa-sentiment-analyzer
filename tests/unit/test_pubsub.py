"""
Unit tests for Pub/Sub client.

Tests publisher and subscriber functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from shared.pubsub import PubSubPublisher, PubSubSubscriber
from shared.models import RawDataMessage
from datetime import datetime


@pytest.fixture
def mock_publisher():
    """Mock Pub/Sub publisher client."""
    with patch('shared.pubsub.client.pubsub_v1.PublisherClient') as mock:
        yield mock


@pytest.fixture
def mock_subscriber():
    """Mock Pub/Sub subscriber client."""
    with patch('shared.pubsub.client.pubsub_v1.SubscriberClient') as mock:
        yield mock


@pytest.mark.asyncio
async def test_publisher_initialization(mock_publisher):
    """Test publisher initializes correctly."""
    publisher = PubSubPublisher("test-project", "test-topic")
    
    assert publisher.project_id == "test-project"
    assert publisher.topic_name == "test-topic"
    assert publisher.batch_size == 100
    mock_publisher.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_publish_message(mock_publisher):
    """Test publishing a single message."""
    # Setup mock
    mock_client = mock_publisher.return_value
    mock_future = Mock()
    mock_future.result.return_value = "message-id-123"
    mock_client.publish.return_value = mock_future
    
    # Create publisher and message
    publisher = PubSubPublisher("test-project", "test-topic")
    message = RawDataMessage(
        message_id="test-123",
        timestamp=datetime.now(),
        tenant_id="tenant-1",
        source="api",
        text_id="text-456",
        text="Test message",
        language="en"
    )
    
    # Publish
    message_id = await publisher.publish(message)
    
    # Verify
    assert message_id == "message-id-123"
    mock_client.publish.assert_called_once()


@pytest.mark.asyncio
async def test_subscriber_initialization(mock_subscriber):
    """Test subscriber initializes correctly."""
    subscriber = PubSubSubscriber("test-project", "test-subscription")
    
    assert subscriber.project_id == "test-project"
    assert subscriber.subscription_name == "test-subscription"
    mock_subscriber.assert_called_once()


@pytest.mark.asyncio
async def test_subscriber_pull_messages(mock_subscriber):
    """Test pulling and processing messages."""
    # Setup mock
    mock_client = mock_subscriber.return_value
    mock_message = Mock()
    mock_message.message.data = b'{"message_id":"test","timestamp":"2025-12-11T00:00:00Z","tenant_id":"t1","source":"api","text_id":"txt1","text":"Test","language":"en"}'
    mock_message.ack_id = "ack-123"
    
    mock_response = Mock()
    mock_response.received_messages = [mock_message]
    mock_client.pull.return_value = mock_response
    
    # Create subscriber
    subscriber = PubSubSubscriber("test-project", "test-subscription")
    
    # Callback to track processing
    processed_messages = []
    
    async def callback(msg):
        processed_messages.append(msg)
    
    # Pull messages
    count = await subscriber.pull_messages(callback)
    
    # Verify
    assert count == 1
    assert len(processed_messages) == 1
    mock_client.acknowledge.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
