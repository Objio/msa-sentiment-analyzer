# Massive Sentiment Analyzer (MSA)

A production-ready, cloud-native sentiment analysis system built on Google Cloud Platform, designed to process millions of texts per month with sub-30-second end-to-end latency.

## 🎯 Overview

MSA is an event-driven, serverless architecture that ingests text data from multiple sources, analyzes sentiment using Gemini 2.0 Flash, and provides powerful aggregation and querying capabilities.

### Key Features

- 📊 **Multi-tenant Architecture**: Isolated tenant data and quotas
- ⚡ **Real-time Processing**: Sub-30s latency for 95% of analyses
- 📈 **Scalable**: Handles 10K+ analyses/hour with auto-scaling
- 💰 **Cost-Efficient**: ~$0.005 per analysis
- 🔒 **Secure**: API key authentication, IAM isolation, encryption at rest/transit
- 🌐 **Production-Ready**: Monitoring, alerting, disaster recovery

## 🏗️ Architecture

```
Data Sources → Ingestion Service → Pub/Sub → Sentiment Analysis → Pub/Sub → Aggregation → BigQuery
                      ↓                                ↓                         ↓            ↓
                Cloud Storage                     Cloud Storage              BigQuery     API Service
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed architecture documentation.

## 📁 Repository Structure

```
msa/
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md           # System architecture
│   ├── ASSUMPTIONS.md            # Key assumptions
│   ├── DATA_MODEL.md             # Data schemas
│   └── DEPLOYMENT.md             # Deployment guide
├── services/                      # Microservices
│   ├── ingestion/                # Ingestion Service
│   ├── sentiment-analysis/       # Sentiment Analysis Service
│   ├── aggregation/              # Aggregation Service
│   ├── api/                      # API Service
│   └── monitoring/               # Monitoring Service
├── shared/                        # Shared libraries
│   ├── models/                   # Pydantic models
│   ├── pubsub/                   # Pub/Sub utilities
│   ├── bigquery/                 # BigQuery utilities
│   └── auth/                     # Authentication utilities
├── infrastructure/                # Terraform IaC
│   ├── modules/                  # Reusable Terraform modules
│   ├── environments/             # Environment-specific configs
│   └── scripts/                  # Deployment scripts
├── tests/                         # Tests
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   └── load/                     # Load tests
├── .github/                       # GitHub Actions CI/CD
│   └── workflows/
├── .gitignore
├── README.md
└── requirements.txt               # Root dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`)
- Terraform 1.5+
- Active GCP project with billing enabled

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd msa
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure GCP credentials**
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```

4. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run tests**
   ```bash
   pytest tests/
   ```

## 📦 Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deploy to Production

```bash
cd infrastructure/environments/production
terraform init
terraform plan
terraform apply
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | GCP project ID | - |
| `GCP_REGION` | Primary GCP region | `us-central1` |
| `GEMINI_API_KEY` | Gemini API key | - |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENV` | Environment (dev/staging/prod) | `dev` |

## 📊 Monitoring & Operations

### Health Checks

- **Ingestion Service**: `GET /health`
- **API Service**: `GET /health`
- **Sentiment Analysis**: Monitored via Pub/Sub queue depth

### Dashboards

Access Cloud Monitoring dashboards:
- [MSA Overview Dashboard](https://console.cloud.google.com/monitoring)
- [Cost Tracking Dashboard](https://console.cloud.google.com/billing)

### Alerts

- **High Queue Depth**: Pub/Sub queue > 10,000 messages
- **High Error Rate**: > 5% errors in any service
- **Budget Alert**: Monthly spend > $5,000

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Load tests
pytest tests/load/
```

## 📈 Performance

- **Throughput**: 10,000+ analyses/hour
- **Latency**: < 30s end-to-end (95th percentile)
- **Availability**: 99.9% uptime SLA
- **Cost**: ~$0.005 per analysis

## 🔒 Security

- **Authentication**: API key-based (OAuth 2.0 coming soon)
- **Authorization**: Tenant-scoped data isolation
- **Encryption**: At rest and in transit (TLS 1.3)
- **Compliance**: GDPR-ready, audit logging

## 📚 Documentation

- [Architecture](./ARCHITECTURE.md) - System design and components
- [Assumptions](./ASSUMPTIONS.md) - Key assumptions and constraints
- [Data Model](./DATA_MODEL.md) - Schemas and data structures
- [Deployment](./DEPLOYMENT.md) - Deployment procedures
- [API Reference](./docs/API.md) - REST API documentation

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes and add tests
3. Run tests: `pytest`
4. Commit: `git commit -m 'Add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open a Pull Request

## 📝 License

This project is proprietary and confidential.

## 👥 Team

- **Architecture**: @architect
- **Backend**: @backend-dev
- **DevOps**: @devops-engineer
- **Product**: @product-manager

## 🆘 Support

- **Issues**: Create a GitHub issue
- **Slack**: #msa-support
- **Email**: support@example.com

---

**Version**: 1.0.0  
**Last Updated**: 2025-12-11  
**Status**: MVP in Development
