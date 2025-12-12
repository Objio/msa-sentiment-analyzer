# API Service

Public REST API for querying sentiment data.

## Status
🚧 **Phase 1 Complete** - Architecture and skeleton defined  
⏳ **Phase 2 Pending** - Implementation

## Overview

FastAPI-based public API for querying sentiment analysis results and metrics.

## Responsibilities

- Provide REST API for data retrieval
- API key authentication
- Tenant-scoped authorization
- Query optimization
- Rate limiting
- OpenAPI documentation

## API Endpoints

- `GET /v1/sentiments` - Query sentiment results
- `GET /v1/metrics/aggregated` - Get aggregated metrics
- `GET /v1/tenants/{tenant_id}/usage` - Usage statistics
- `GET /v1/status/{text_id}` - Check analysis status
- `GET /health` - Health check
- `GET /docs` - API documentation

## Technology Stack

- **Framework**: FastAPI
- **Runtime**: Cloud Run
- **Language**: Python 3.11+

## Next Steps (Phase 2)

1. Implement FastAPI application
2. Create BigQuery query utilities
3. Add authentication and authorization
4. Implement rate limiting
5. Create Dockerfile
6. Add tests
7. Deploy to Cloud Run

See [MICROSERVICES.md](../../MICROSERVICES.md) for detailed specifications.
