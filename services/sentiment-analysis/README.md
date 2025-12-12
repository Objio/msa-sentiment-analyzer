# Sentiment Analysis Service

Core sentiment analysis engine using Gemini 2.0 Flash.

## Status
🚧 **Phase 1 Complete** - Architecture and skeleton defined  
⏳ **Phase 2 Pending** - Implementation

## Overview

Background worker service that processes text from Pub/Sub, analyzes sentiment using Gemini API, and stores results.

## Responsibilities

- Subscribe to `raw-data-topic`
- Batch processing for efficiency
- Call Gemini API for sentiment analysis
- Parse and validate results
- Store in BigQuery `sentiments` table
- Publish to `analyzed-data-topic`
- Handle retries and rate limiting

## Technology Stack

- **Runtime**: Cloud Run
- **Language**: Python 3.11+
- **AI**: Gemini 2.0 Flash

## Next Steps (Phase 2)

1. Implement Pub/Sub subscriber
2. Create Gemini API client with prompt template
3. Implement batch processing logic
4. Add error handling and retries
5. Create Dockerfile
6. Add tests
7. Deploy to Cloud Run

See [MICROSERVICES.md](../../MICROSERVICES.md) for detailed specifications.
