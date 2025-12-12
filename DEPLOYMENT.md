# MSA Deployment Guide

## Prerequisites

### 1. Google Cloud Platform Setup

- **GCP Account**: Active account with billing enabled
- **Project**: Create or select a GCP project
- **Permissions**: Owner or Editor role on the project
- **Quotas**: Default quotas are sufficient for MVP

### 2. Local Development Tools

```bash
# Install Google Cloud SDK
# Windows (PowerShell)
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe

# Authenticate
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Install Terraform
# Download from https://www.terraform.io/downloads
# Or use Chocolatey
choco install terraform

# Verify installations
gcloud --version
terraform --version
python --version  # Should be 3.11+
```

### 3. API Keys & Secrets

- **Gemini API Key**: Obtain from [Google AI Studio](https://makersuite.google.com/app/apikey)
- Store in Secret Manager (automated during deployment)

## Deployment Steps

### Step 1: Clone and Configure

```bash
# Navigate to project directory
cd "C:\Users\objio\Desktop\Analizador de sentimiento"

# Create .env file from example
cp .env.example .env

# Edit .env with your values
# At minimum, set:
# - GCP_PROJECT_ID
# - GEMINI_API_KEY
```

### Step 2: Initialize Terraform

```bash
# Navigate to production environment
cd infrastructure/environments/production

# Copy tfvars example
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your GCP project ID
# Example:
# project_id  = "msa-production-12345"
# region      = "us-central1"
# environment = "production"

# Initialize Terraform
terraform init

# Review the plan
terraform plan
```

**Expected Output**: Terraform will show ~30-40 resources to be created:
- 2 Pub/Sub topics + 2 subscriptions
- 1 BigQuery dataset + 4 tables
- 3-5 Cloud Storage buckets
- 5 Service accounts + IAM bindings
- 5 Cloud Run services

### Step 3: Deploy Infrastructure

```bash
# Apply Terraform configuration
terraform apply

# Type 'yes' when prompted
```

**Duration**: 5-10 minutes

**What's Created**:
- ✅ Pub/Sub topics: `raw-data-topic`, `analyzed-data-topic`
- ✅ BigQuery dataset: `msa_production`
- ✅ BigQuery tables: `raw_texts`, `sentiments`, `aggregated_metrics`, `api_usage`
- ✅ Cloud Storage buckets for raw and processed data
- ✅ Service accounts with least-privilege IAM roles
- ✅ Cloud Run services (skeleton, need Docker images)

### Step 4: Store Secrets

```bash
# Store Gemini API key in Secret Manager
gcloud secrets create gemini-api-key \
  --data-file=- <<< "YOUR_GEMINI_API_KEY"

# Grant access to service accounts
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:msa-sentiment-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 5: Build Docker Images

```bash
# Navigate to project root
cd "C:\Users\objio\Desktop\Analizador de sentimiento"

# Set environment variables
$PROJECT_ID = "YOUR_PROJECT_ID"
$REGION = "us-central1"

# Enable Artifact Registry API
gcloud services enable artifactregistry.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create msa-images \
  --repository-format=docker \
  --location=$REGION

# Build and push each service
# Note: These commands will fail until services are implemented in Phase 2

# Ingestion Service
cd services/ingestion
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-ingestion:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-ingestion:latest"

# Sentiment Analysis Service
cd ../sentiment-analysis
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-sentiment-analysis:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-sentiment-analysis:latest"

# Aggregation Service
cd ../aggregation
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-aggregation:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-aggregation:latest"

# API Service
cd ../api
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-api:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-api:latest"

# Monitoring Service
cd ../monitoring
docker build -t "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-monitoring:latest" .
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-monitoring:latest"
```

### Step 6: Deploy Services to Cloud Run

```bash
# Deploy Ingestion Service
gcloud run deploy msa-ingestion \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-ingestion:latest" \
  --region=$REGION \
  --service-account=msa-ingestion-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --allow-unauthenticated

# Deploy API Service
gcloud run deploy msa-api \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-api:latest" \
  --region=$REGION \
  --service-account=msa-api-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --allow-unauthenticated

# Deploy Sentiment Analysis (background service)
gcloud run deploy msa-sentiment-analysis \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-sentiment-analysis:latest" \
  --region=$REGION \
  --service-account=msa-sentiment-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated

# Deploy Aggregation Service
gcloud run deploy msa-aggregation \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-aggregation:latest" \
  --region=$REGION \
  --service-account=msa-aggregation-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated

# Deploy Monitoring Service
gcloud run deploy msa-monitoring \
  --image="$REGION-docker.pkg.dev/$PROJECT_ID/msa-images/msa-monitoring:latest" \
  --region=$REGION \
  --service-account=msa-monitoring-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated
```

### Step 7: Verify Deployment

```bash
# Get Cloud Run service URLs
gcloud run services list --region=$REGION

# Test Ingestion API health
$INGESTION_URL = (gcloud run services describe msa-ingestion --region=$REGION --format="value(status.url)")
curl "$INGESTION_URL/health"

# Expected: {"status": "healthy", "service": "ingestion"}

# Test API service health
$API_URL = (gcloud run services describe msa-api --region=$REGION --format="value(status.url)")
curl "$API_URL/health"

# Expected: {"status": "healthy", "service": "api"}
```

### Step 8: End-to-End Test

```bash
# Send a test analysis request
curl -X POST "$INGESTION_URL/v1/analyze" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: test-api-key" `
  -d '{
    "text": "This is an amazing product! I love it!",
    "language": "en",
    "metadata": {
      "source": "test",
      "product_id": "test-product-123"
    }
  }'

# Expected response (202 Accepted):
# {
#   "text_id": "uuid-here",
#   "status": "queued",
#   "estimated_completion": "2025-12-11T22:00:00Z"
# }

# Wait 30 seconds for processing
Start-Sleep -Seconds 30

# Query the results
curl "$API_URL/v1/sentiments?tenant_id=default&limit=10"

# Expected: Array of sentiment results including your test text
```

## Monitoring & Operations

### View Logs

```bash
# Ingestion service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=msa-ingestion" --limit=50

# Sentiment analysis logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=msa-sentiment-analysis" --limit=50
```

### Monitor Pub/Sub

```bash
# Check queue depth
gcloud pubsub subscriptions describe raw-data-sentiment-sub --format="value(messageCount)"

# If queue is growing, check for processing issues
```

### Query BigQuery

```bash
# Check ingested texts
bq query --use_legacy_sql=false '
SELECT COUNT(*) as total_texts
FROM `msa_production.raw_texts`
WHERE DATE(ingested_at) = CURRENT_DATE()
'

# Check sentiment results
bq query --use_legacy_sql=false '
SELECT overall_sentiment, COUNT(*) as count
FROM `msa_production.sentiments`
WHERE DATE(processed_at) = CURRENT_DATE()
GROUP BY overall_sentiment
'
```

### View Cloud Monitoring Dashboard

1. Navigate to [Cloud Monitoring](https://console.cloud.google.com/monitoring)
2. Create custom dashboard with:
   - Cloud Run request count
   - Cloud Run latency
   - Pub/Sub message count
   - BigQuery rows inserted
   - Cost metrics

## Troubleshooting

### Issue: Terraform apply fails with "API not enabled"

**Solution**: Enable required APIs manually:
```bash
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
```

### Issue: Cloud Run deployment fails with "Permission denied"

**Solution**: Ensure service account has required permissions:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:msa-ingestion-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.developer"
```

### Issue: Sentiment analysis not processing messages

**Checklist**:
1. ✅ Check Gemini API key is stored in Secret Manager
2. ✅ Verify service account has `secretmanager.secretAccessor` role
3. ✅ Check Cloud Run logs for errors
4. ✅ Verify Pub/Sub subscription exists and has messages
5. ✅ Confirm Gemini API quota is not exceeded

### Issue: High latency (> 60s)

**Possible causes**:
- Pub/Sub queue backup (increase Cloud Run instances)
- Gemini API rate limiting (implement better batching)
- BigQuery write throttling (use streaming inserts)

**Solution**: Scale up Cloud Run:
```bash
gcloud run services update msa-sentiment-analysis \
  --region=$REGION \
  --max-instances=100 \
  --min-instances=5
```

### Issue: Costs exceeding budget

**Check costs**:
```bash
# View current month spending
gcloud billing projects describe YOUR_PROJECT_ID
```

**Optimization**:
1. Reduce Cloud Run min instances to 0 for non-critical services
2. Implement BigQuery table expiration
3. Use Cloud Storage lifecycle policies
4. Batch Gemini API calls more aggressively

## Rollback

### Rollback Cloud Run Deployment

```bash
# List revisions
gcloud run revisions list --service=msa-ingestion --region=$REGION

# Rollback to previous revision
gcloud run services update-traffic msa-ingestion \
  --region=$REGION \
  --to-revisions=msa-ingestion-00002=100
```

### Destroy Infrastructure

```bash
cd infrastructure/environments/production
terraform destroy
```

> [!CAUTION]
> This will delete ALL data, including BigQuery tables and Cloud Storage buckets. Create backups first!

## Backup & Recovery

### Backup BigQuery Tables

```bash
# Export to Cloud Storage
bq extract --destination_format=AVRO \
  msa_production.sentiments \
  gs://msa-production-backups/sentiments/$(date +%Y%m%d)/*.avro
```

### Restore BigQuery Table

```bash
# Import from Cloud Storage
bq load --source_format=AVRO \
  msa_production.sentiments_restored \
  gs://msa-production-backups/sentiments/20251211/*.avro
```

## Production Checklist

Before going live:

- [ ] Set up budget alerts in GCP Billing
- [ ] Configure Cloud Monitoring alerts
- [ ] Set up uptime checks for Ingestion and API services
- [ ] Implement API key rotation policy
- [ ] Configure Cloud Armor for DDoS protection
- [ ] Set up automated backups for BigQuery
- [ ] Document incident response procedures
- [ ] Load test with realistic traffic patterns
- [ ] Review and tighten IAM permissions
- [ ] Enable VPC Service Controls (optional, for extra security)

---

**Last Updated**: 2025-12-11  
**Version**: 1.0 (Phase 1 - Architecture)
