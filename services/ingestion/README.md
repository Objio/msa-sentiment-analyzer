# Ingestion Service

Entry point for all text data into the MSA system.

## Status
🚧 **Phase 1 Complete** - Architecture and skeleton defined  
⏳ **Phase 2 Pending** - Implementation

## Overview

The Ingestion Service is a FastAPI-based REST API that accepts text data from multiple sources and publishes it to the MSA processing pipeline.

## Responsibilities

- Accept text data via REST API endpoints
- Validate and normalize input data
- Publish to Pub/Sub `raw-data-topic`
- Store raw data audit trail
- Rate limiting per tenant
- Error handling and feedback

## API Endpoints

- `POST /v1/analyze` - Single text analysis
- `POST /v1/analyze/batch` - Batch analysis
- `GET /health` - Health check

## Technology Stack

- **Framework**: FastAPI
- **Runtime**: Cloud Run
- **Language**: Python 3.11+

## Next Steps (Phase 2)

1. Implement FastAPI application with endpoints
2. Add Pub/Sub publisher client
3. Implement validation and rate limiting
4. Create Dockerfile
5. Add unit and integration tests
6. Deploy to Cloud Run

See [MICROSERVICES.md](../../MICROSERVICES.md) for detailed specifications.
