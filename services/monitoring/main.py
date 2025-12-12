"""
MSA Monitoring Service

Simple health monitoring and metrics collection service.
Monitors service health and publishes metrics to Cloud Monitoring.
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
import structlog
from google.cloud import monitoring_v3
from google.cloud import logging as cloud_logging

# Add parent directory to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.bigquery import BigQueryClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "msa-project")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "msa_production")
MONITORING_INTERVAL = int(os.getenv("MONITORING_INTERVAL_SECONDS", "60"))

# Service URLs to monitor (will be set from environment)
SERVICES = {
    "ingestion": os.getenv("INGESTION_URL", ""),
    "api": os.getenv("API_URL", "")
}

# Global clients
bq_client: BigQueryClient = None
metrics_client: monitoring_v3.MetricServiceClient = None


async def check_service_health(service_name: str, url: str) -> Dict[str, Any]:
    """
    Check health of a service.
    
    Args:
        service_name: Name of the service
        url: Health check URL
        
    Returns:
        Health status dict
    """
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"{service_name} is healthy")
                    return {
                        "service": service_name,
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat(),
                        "details": data
                    }
                else:
                    logger.warning(f"{service_name} returned {response.status}")
                    return {
                        "service": service_name,
                        "status": "unhealthy",
                        "timestamp": datetime.now().isoformat(),
                        "error": f"HTTP {response.status}"
                    }
    except Exception as e:
        logger.error(f"Error checking {service_name}: {e}")
        return {
            "service": service_name,
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


async def collect_processing_metrics() -> Dict[str, Any]:
    """
    Collect processing metrics from BigQuery.
    
    Returns:
        Metrics dict
    """
    try:
        # Query recent processing stats
        query = f"""
        SELECT
            COUNT(*) as total_processed,
            AVG(processing_time_ms) as avg_processing_time,
            MAX(processed_at) as latest_processing
        FROM `{PROJECT_ID}.{BIGQUERY_DATASET}.sentiments`
        WHERE DATE(processed_at) = CURRENT_DATE()
        """
        
        results = await bq_client.query(query)
        
        if results:
            metrics = results[0]
            logger.info(
                "Processing metrics",
                total=metrics.get("total_processed", 0),
                avg_time=metrics.get("avg_processing_time", 0)
            )
            return {
                "total_processed_today": metrics.get("total_processed", 0),
                "avg_processing_time_ms": metrics.get("avg_processing_time", 0),
                "latest_processing": metrics.get("latest_processing")
            }
        
        return {}
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        return {}


async def publish_metrics_to_cloud_monitoring(metrics: Dict[str, Any]):
    """
    Publish metrics to Cloud Monitoring.
    
    Args:
        metrics: Metrics to publish
    """
    try:
        project_name = f"projects/{PROJECT_ID}"
        
        # Create time series for processing count
        if "total_processed_today" in metrics:
            series = monitoring_v3.TimeSeries()
            series.metric.type = "custom.googleapis.com/msa/texts_processed"
            series.resource.type = "global"
            
            point = monitoring_v3.Point()
            point.value.int64_value = metrics["total_processed_today"]
            point.interval.end_time.FromDatetime(datetime.now())
            series.points = [point]
            
            metrics_client.create_time_series(name=project_name, time_series=[series])
            logger.debug("Published metrics to Cloud Monitoring")
            
    except Exception as e:
        logger.error(f"Error publishing metrics: {e}")


async def monitoring_loop():
    """Main monitoring loop."""
    logger.info("Starting monitoring loop")
    
    while True:
        try:
            # Check service health
            health_checks = []
            for service_name, url in SERVICES.items():
                if url:  # Only check if URL is configured
                    health = await check_service_health(service_name, url)
                    health_checks.append(health)
            
            # Collect processing metrics
            processing_metrics = await collect_processing_metrics()
            
            # Publish to Cloud Monitoring
            await publish_metrics_to_cloud_monitoring(processing_metrics)
            
            # Log summary
            healthy_count = sum(1 for h in health_checks if h["status"] == "healthy")
            logger.info(
                "Monitoring cycle complete",
                healthy_services=f"{healthy_count}/{len(health_checks)}",
                metrics=processing_metrics
            )
            
            # Wait for next cycle
            await asyncio.sleep(MONITORING_INTERVAL)
            
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(60)  # Wait before retry


async def main():
    """Main entry point."""
    global bq_client, metrics_client
    
    logger.info("Starting Monitoring Service")
    
    try:
        # Initialize clients
        bq_client = BigQueryClient(PROJECT_ID, BIGQUERY_DATASET)
        metrics_client = monitoring_v3.MetricServiceClient()
        
        logger.info("Clients initialized, starting monitoring")
        
        # Start monitoring loop
        await monitoring_loop()
        
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        if bq_client:
            bq_client.close()
        
        logger.info("Monitoring Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
