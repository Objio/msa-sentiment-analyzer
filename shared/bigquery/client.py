"""
BigQuery client utilities for MSA system.

Provides async client for inserting and querying data
with stream inserts, deduplication, and query optimization.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Async BigQuery client for MSA."""
    
    def __init__(self, project_id: str, dataset_id: str):
        """
        Initialize BigQuery client.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        self.dataset_ref = self.client.dataset(dataset_id)
        
        logger.info(f"BigQuery client initialized for {project_id}.{dataset_id}")
    
    def _table_ref(self, table_id: str) -> bigquery.TableReference:
        """Get table reference."""
        return self.dataset_ref.table(table_id)
    
    async def insert_rows(
        self,
        table_id: str,
        rows: List[Dict[str, Any]],
        row_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Insert rows into a table using streaming insert.
        
        Args:
            table_id: Table name
            rows: List of row dictionaries
            row_ids: Optional list of row IDs for deduplication
            
        Returns:
            True if successful, False otherwise
        """
        table_ref = self._table_ref(table_id)
        
        try:
            errors = self.client.insert_rows_json(
                table_ref,
                rows,
                row_ids=row_ids
            )
            
            if errors:
                logger.error(f"Errors inserting rows into {table_id}: {errors}")
                return False
            
            logger.info(f"Inserted {len(rows)} rows into {table_id}")
            return True
            
        except GoogleAPIError as e:
            logger.error(f"Error inserting into {table_id}: {e}")
            return False
    
    async def insert_row(
        self,
        table_id: str,
        row: Dict[str, Any],
        row_id: Optional[str] = None
    ) -> bool:
        """
        Insert a single row.
        
        Args:
            table_id: Table name
            row: Row dictionary
            row_id: Optional row ID for deduplication
            
        Returns:
            True if successful
        """
        row_ids = [row_id] if row_id else None
        return await self.insert_rows(table_id, [row], row_ids)
    
    async def query(
        self,
        query_string: str,
        params: Optional[List[bigquery.ScalarQueryParameter]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and return results.
        
        Args:
            query_string: SQL query
            params: Optional query parameters for parameterized queries
            
        Returns:
            List of result dictionaries
        """
        try:
            job_config = bigquery.QueryJobConfig()
            if params:
                job_config.query_parameters = params
            
            query_job = self.client.query(query_string, job_config=job_config)
            results = query_job.result()
            
            # Convert to list of dicts
            rows = [dict(row) for row in results]
            
            logger.info(f"Query returned {len(rows)} rows")
            return rows
            
        except GoogleAPIError as e:
            logger.error(f"Query error: {e}")
            return []
    
    async def query_sentiments(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sentiment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query sentiments table with filters.
        
        Args:
            tenant_id: Tenant ID to filter by
            start_date: Optional start date
            end_date: Optional end date
            sentiment: Optional sentiment filter
            limit: Max results
            offset: Offset for pagination
            
        Returns:
            List of sentiment records
        """
        # Build query
        query = f"""
        SELECT
            text_id,
            overall_sentiment,
            sentiment_score,
            confidence,
            processed_at,
            metadata
        FROM `{self.project_id}.{self.dataset_id}.sentiments`
        WHERE tenant_id = @tenant_id
        """
        
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id)
        ]
        
        if start_date:
            query += " AND processed_at >= @start_date"
            params.append(
                bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", start_date)
            )
        
        if end_date:
            query += " AND processed_at <= @end_date"
            params.append(
                bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", end_date)
            )
        
        if sentiment:
            query += " AND overall_sentiment = @sentiment"
            params.append(
                bigquery.ScalarQueryParameter("sentiment", "STRING", sentiment)
            )
        
        query += f"""
        ORDER BY processed_at DESC
        LIMIT @limit
        OFFSET @offset
        """
        
        params.extend([
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset)
        ])
        
        return await self.query(query, params)
    
    async def query_aggregated_metrics(
        self,
        tenant_id: str,
        aggregation_level: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Query aggregated metrics.
        
        Args:
            tenant_id: Tenant ID
            aggregation_level: "hourly", "daily", "weekly", "monthly"
            start_date: Start date
            end_date: End date
            
        Returns:
            List of aggregated metrics
        """
        query = f"""
        SELECT
            period_start,
            period_end,
            total_texts,
            total_positive,
            total_negative,
            total_neutral,
            total_mixed,
            avg_sentiment_score,
            avg_emotion_joy,
            avg_emotion_anger,
            avg_emotion_sadness,
            toxicity_rate,
            sentiment_trend,
            trend_score
        FROM `{self.project_id}.{self.dataset_id}.aggregated_metrics`
        WHERE tenant_id = @tenant_id
          AND aggregation_level = @aggregation_level
          AND period_start >= @start_date
          AND period_start <= @end_date
        ORDER BY period_start ASC
        """
        
        params = [
            bigquery.ScalarQueryParameter("tenant_id", "STRING", tenant_id),
            bigquery.ScalarQueryParameter("aggregation_level", "STRING", aggregation_level),
            bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", start_date),
            bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", end_date)
        ]
        
        return await self.query(query, params)
    
    def close(self):
        """Close the client."""
        self.client.close()
        logger.info("BigQuery client closed")
