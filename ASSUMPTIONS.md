# Massive Sentiment Analyzer (MSA) - Key Assumptions

## Business Assumptions

### 1. Scale & Volume
- **Initial Volume**: 1-10 million text analyses per month
- **Growth Trajectory**: 3x year-over-year growth expected
- **Peak Load**: 10x average during peak events (news events, product launches)
- **Text Size**: Average 500 characters, maximum 10,000 characters per text
- **Batch Upload Size**: Up to 100,000 texts per batch job

### 2. Use Cases
- **Primary**: Social media sentiment monitoring (Twitter, Reddit, Facebook)
- **Secondary**: Customer review analysis (app stores, e-commerce)
- **Tertiary**: News and article sentiment tracking
- **Not Supported (MVP)**: Video/audio transcription and analysis

### 3. Clients & Tenants
- **Multi-tenant**: System supports multiple isolated clients/tenants
- **Client Types**: Marketing agencies, brand management firms, enterprise customers
- **SLA Requirements**: 99.9% uptime for API, best-effort for processing latency
- **Support Model**: Email support, response within 24 hours

## Technical Assumptions

### 4. Google Cloud Platform
- **Primary Region**: `us-central1` (Iowa) for all resources
- **GCP Services Available**: Cloud Run, Pub/Sub, BigQuery, Cloud Storage, Secret Manager
- **Quotas**: Default quotas sufficient for MVP; will request increases as needed
- **Billing**: Pay-as-you-go with budget alerts set at $5,000/month initially

### 5. Gemini API
- **Model**: Gemini 2.0 Flash for sentiment analysis
- **API Quotas**: 
  - Rate limit: 1,000 requests per minute (RPM)
  - Daily limit: 50,000 requests per day (can be increased)
- **Response Time**: Average 1-2 seconds per analysis
- **Quality**: Gemini provides sufficient accuracy for MVP (human validation not required)
- **Cost**: ~$0.20 per 1,000 analyses (Flash pricing)
- **Fallback**: No fallback AI model in MVP; failures are retried

### 6. Data Retention
- **Raw Data**: 90 days in Cloud Storage (lifecycle policy)
- **Sentiment Results**: 2 years in BigQuery
- **Aggregated Metrics**: Indefinite retention (historical trends)
- **Logs**: 30 days in Cloud Logging
- **Backups**: 7-day snapshots for BigQuery tables

### 7. Processing Guarantees
- **At-Least-Once Delivery**: Pub/Sub provides at-least-once delivery semantics
- **Idempotency**: All processing steps are idempotent (duplicate messages handled)
- **Ordering**: No strict ordering guarantees; timestamps used for sequencing
- **Data Loss**: Acceptable data loss < 0.01% (1 in 10,000 messages)
- **Latency SLA**: 95% of messages processed within 30 seconds end-to-end

## Security & Compliance Assumptions

### 8. Authentication & Authorization
- **API Access**: API key-based authentication for programmatic access
- **User Access**: OAuth 2.0 via Google Identity Platform (future)
- **Service-to-Service**: Service accounts with least-privilege IAM roles
- **API Key Management**: Clients responsible for rotating their own API keys

### 9. Data Privacy
- **PII Handling**: System does not intentionally store PII; clients responsible for anonymization
- **Geographic Restrictions**: No data residency requirements (all data in us-central1)
- **GDPR Compliance**: Right to deletion supported via API (future enhancement)
- **Data Sharing**: No cross-tenant data sharing; strict isolation enforced

### 10. Compliance Requirements
- **SOC 2**: Not required for MVP
- **HIPAA**: Not required (no health data expected)
- **Industry-Specific**: No specific compliance (FINRA, PCI-DSS) required
- **Export Controls**: No restrictions on international data processing

## Infrastructure & Operations Assumptions

### 11. Deployment & CI/CD
- **Infrastructure as Code**: Terraform used for all infrastructure
- **Version Control**: Git (GitHub) for code and Terraform
- **CI/CD**: GitHub Actions for automated testing and deployment
- **Branching Strategy**: Main branch protected, feature branches + PR reviews
- **Deployment Frequency**: Daily to staging, weekly to production (after stabilization)

### 12. Monitoring & Alerting
- **Monitoring Tool**: Google Cloud Monitoring + Cloud Logging
- **On-Call**: Best-effort monitoring; no 24/7 on-call initially
- **Alerting Channels**: Email and Slack for critical alerts
- **Dashboard**: Public status page not required for MVP
- **SLOs**: No formal SLOs for MVP; informal targets (99.9% uptime, < 30s latency)

### 13. Disaster Recovery
- **Backup Frequency**: Daily BigQuery snapshots
- **RTO (Recovery Time Objective)**: < 1 hour
- **RPO (Recovery Point Objective)**: < 5 minutes
- **Multi-Region**: Not required for MVP; single region (us-central1)
- **Failover**: Manual failover process documented

## Cost & Budget Assumptions

### 14. Budget Constraints
- **Initial Budget**: $5,000/month for all GCP services
- **Target Cost per Analysis**: < $0.005 (half a cent)
- **Cost Monitoring**: Daily budget alerts, weekly cost review
- **Optimization Priority**: High; cost efficiency is critical for MVP

### 15. Pricing Model (To Customers)
- **Pay-per-Analysis**: $0.01 per text analyzed (2x markup on cost)
- **Volume Discounts**: > 1M analyses: $0.008, > 10M: $0.006
- **Subscription Tiers**: Not offered in MVP
- **Free Tier**: 1,000 analyses/month for trial users

## Development & Team Assumptions

### 16. Team Composition
- **Backend Developer**: 1 (Python, GCP, Terraform)
- **Frontend Developer**: 0.5 (API documentation, basic dashboard - Phase 2)
- **DevOps/SRE**: 0.5 (part of backend developer responsibilities)
- **Product Manager**: 0.25 (part-time, strategic direction)

### 17. Development Timeline
- **Phase 1 (Architecture & Skeleton)**: 1 week
- **Phase 2 (Implementation)**: 3-4 weeks
- **Phase 3 (Testing & Optimization)**: 2 weeks
- **Phase 4 (Production Deployment)**: 1 week
- **Total MVP**: ~8 weeks

### 18. Technology Expertise
- **Python**: Advanced proficiency required
- **GCP**: Intermediate proficiency; learning on the job acceptable
- **Terraform**: Basic proficiency required
- **FastAPI**: Intermediate proficiency
- **AI/ML**: Basic understanding; Gemini API usage is straightforward

## Critical Dependencies

### 19. External Dependencies
- **Gemini API Availability**: Critical; no fallback in MVP
- **GCP Service Availability**: Critical; relying on GCP SLAs
- **GitHub Availability**: Medium; can deploy manually if needed
- **Third-Party APIs**: None for MVP

### 20. Internal Dependencies
- **API Keys for Testing**: Need test Gemini API key and GCP project
- **Sample Data**: Need representative dataset for testing (100K+ texts)
- **Documentation**: Architecture and API docs completed before implementation

## Out of Scope (MVP)

The following are explicitly **NOT** included in the MVP but may be considered for future releases:

- ❌ Multi-language sentiment analysis (English only for MVP)
- ❌ Custom ML model training
- ❌ Real-time streaming dashboard (batch queries only)
- ❌ Multi-region deployment
- ❌ Advanced analytics (topic modeling, entity relationship graphs)
- ❌ Integration with BI tools (Looker, Tableau)
- ❌ Self-service tenant onboarding UI
- ❌ Detailed usage analytics and cost breakdown per tenant
- ❌ Automated anomaly detection and alerting
- ❌ A/B testing infrastructure
- ❌ GraphQL API (REST only)
- ❌ White-label solutions

## Risk Mitigation

### Key Risks & Mitigation Strategies

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Gemini API quota limits** | High | High | Implement request batching, caching, and graceful degradation |
| **Cost overruns** | Medium | High | Daily budget alerts, auto-scaling limits, cost monitoring dashboard |
| **Processing latency SLA misses** | Medium | Medium | Optimize batching, add caching layer, monitor queue depth |
| **Data loss due to bugs** | Low | High | Extensive testing, write-ahead logging, BigQuery snapshots |
| **Security breach** | Low | Critical | Least-privilege IAM, regular security audits, Secret Manager |
| **Scalability bottleneck** | Medium | Medium | Load testing, auto-scaling configuration, horizontal scaling design |

## Validation Criteria

These assumptions will be validated through:

1. **Load Testing**: Confirm system handles 10K analyses/hour
2. **Cost Analysis**: Verify cost per analysis < $0.005
3. **Latency Testing**: Confirm 95% of analyses complete < 30s
4. **Failure Testing**: Verify system handles Gemini API failures gracefully
5. **Security Audit**: Verify IAMroles follow least-privilege principle

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2025-12-11 | Initial version | MVP planning |

---

**Note**: These assumptions should be reviewed and updated quarterly or when significant changes occur in business requirements, technology landscape, or scale.
