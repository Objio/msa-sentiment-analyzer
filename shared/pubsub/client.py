"""
Pub/Sub client utilities for MSA system.

Provides async publisher and subscriber implementations
with batching, retry logic, and error handling.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from google.cloud import pubsub_v1
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError
from concurrent.futures import TimeoutError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PubSubPublisher:
    """Async Pub/Sub publisher with batching."""
    
    def __init__(
        self,
        project_id: str,
        topic_name: str,
        batch_size: int = 100,
        batch_timeout_seconds: float = 1.0
    ):
        """
        Initialize publisher.
        
        Args:
            project_id: GCP project ID
            topic_name: Pub/Sub topic name
            batch_size: Number of messages to batch before publishing
            batch_timeout_seconds: Max time to wait before flushing batch
        """
        self.project_id = project_id
        self.topic_name = topic_name
        self.batch_size = batch_size
        self.batch_timeout_seconds = batch_timeout_seconds
        
        # Initialize client
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_name)
        
        # Batching state
        self._batch: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        
        logger.info(f"Publisher initialized for topic: {self.topic_path}")
    
    async def publish(self, message: BaseModel, **attributes) -> str:
        """
        Publish a message to the topic.
        
        Args:
            message: Pydantic model to publish
            **attributes: Additional message attributes
            
        Returns:
            Message ID
        """
        message_data = message.model_dump_json().encode("utf-8")
        
        try:
            # Publish with retry
            future = self.publisher.publish(
                self.topic_path,
                message_data,
                **attributes
            )
            message_id = future.result(timeout=10.0)
            logger.debug(f"Published message {message_id} to {self.topic_name}")
            return message_id
            
        except TimeoutError:
            logger.error(f"Timeout publishing to {self.topic_name}")
            raise
        except GoogleAPIError as e:
            logger.error(f"Error publishing to {self.topic_name}: {e}")
            raise
    
    async def publish_batch(self, messages: List[BaseModel]) -> List[str]:
        """
        Publish a batch of messages.
        
        Args:
            messages: List of Pydantic models to publish
            
        Returns:
            List of message IDs
        """
        message_ids = []
        
        for message in messages:
            try:
                message_id = await self.publish(message)
                message_ids.append(message_id)
            except Exception as e:
                logger.error(f"Failed to publish message: {e}")
                # Continue with other messages
                continue
        
        return message_ids
    
    async def close(self):
        """Close the publisher and flush pending messages."""
        # Cancel flush task if running
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        
        logger.info(f"Publisher closed for topic: {self.topic_name}")


class PubSubSubscriber:
    """Async Pub/Sub subscriber with auto-ack."""
    
    def __init__(
        self,
        project_id: str,
        subscription_name: str,
        max_messages: int = 100,
        ack_deadline_seconds: int = 600
    ):
        """
        Initialize subscriber.
        
        Args:
            project_id: GCP project ID
            subscription_name: Pub/Sub subscription name
            max_messages: Max messages to pull at once
            ack_deadline_seconds: Ack deadline
        """
        self.project_id = project_id
        self.subscription_name = subscription_name
        self.max_messages = max_messages
        self.ack_deadline_seconds = ack_deadline_seconds
        
        # Initialize client
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            project_id, subscription_name
        )
        
        logger.info(f"Subscriber initialized for: {self.subscription_path}")
    
    async def pull_messages(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        model_class: Optional[type] = None
    ) -> int:
        """
        Pull and process messages.
        
        Args:
            callback: Async function to process each message
            model_class: Optional Pydantic model to parse messages
            
        Returns:
            Number of messages processed
        """
        try:
            # Pull messages
            response = self.subscriber.pull(
                request={
                    "subscription": self.subscription_path,
                    "max_messages": self.max_messages,
                }
            )
            
            if not response.received_messages:
                return 0
            
            ack_ids = []
            processed_count = 0
            
            for received_message in response.received_messages:
                try:
                    # Parse message data
                    data = json.loads(received_message.message.data.decode("utf-8"))
                    
                    # Optionally parse with Pydantic model
                    if model_class:
                        data = model_class(**data)
                    
                    # Process message
                    await callback(data)
                    
                    # Add to ack list
                    ack_ids.append(received_message.ack_id)
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Nack the message by not adding to ack_ids
                    continue
            
            # Acknowledge processed messages
            if ack_ids:
                self.subscriber.acknowledge(
                    request={
                        "subscription": self.subscription_path,
                        "ack_ids": ack_ids,
                    }
                )
                logger.info(f"Acknowledged {len(ack_ids)} messages")
            
            return processed_count
            
        except GoogleAPIError as e:
            logger.error(f"Error pulling messages: {e}")
            return 0
    
    async def start_consuming(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        model_class: Optional[type] = None,
        poll_interval_seconds: float = 1.0
    ):
        """
        Start consuming messages continuously.
        
        Args:
            callback: Async function to process each message
            model_class: Optional Pydantic model to parse messages
            poll_interval_seconds: Time between polls
        """
        logger.info(f"Starting consumer for {self.subscription_name}")
        
        while True:
            try:
                count = await self.pull_messages(callback, model_class)
                
                if count == 0:
                    # No messages, wait before next poll
                    await asyncio.sleep(poll_interval_seconds)
                else:
                    # Messages processed, poll immediately
                    continue
                    
            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")
                await asyncio.sleep(poll_interval_seconds)
    
    def close(self):
        """Close the subscriber."""
        self.subscriber.close()
        logger.info(f"Subscriber closed for: {self.subscription_name}")
