#!/bin/bash
# MSA Quick Deploy Script
# Deploys all infrastructure and services to GCP

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Massive Sentiment Analyzer - Quick Deploy ===${NC}"
echo ""

# Check required environment variables
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID environment variable not set${NC}"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}Error: GEMINI_API_KEY environment variable not set${NC}"
    exit 1
fi

REGION=${GCP_REGION:-us-central1}
ENV=${ENV:-production}

echo -e "${YELLOW}Configuration:${NC}"
echo "  Project ID: $GCP_PROJECT_ID"
echo "  Region: $REGION"
echo "  Environment: $ENV"
echo ""

# Step 1: Deploy Infrastructure
echo -e "${GREEN}Step 1: Deploying Infrastructure with Terraform${NC}"
cd infrastructure/environments/$ENV

# Check if terraform.tfvars exists
if [ ! -f terraform.tfvars ]; then
    echo "Creating terraform.tfvars from example..."
    cp terraform.tfvars.example terraform.tfvars
    sed -i "s/your-gcp-project-id/$GCP_PROJECT_ID/g" terraform.tfvars
    sed -i "s/us-central1/$REGION/g" terraform.tfvars
fi

terraform init
terraform plan -out=tfplan
echo -e "${YELLOW}Review the plan above. Press Enter to continue or Ctrl+C to cancel${NC}"
read

terraform apply tfplan
cd ../../..

echo -e "${GREEN}Infrastructure deployed!${NC}"
echo ""

# Step 2: Store Gemini API Key in Secret Manager
echo -e "${GREEN}Step 2: Storing Gemini API Key in Secret Manager${NC}"
echo -n "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --project=$GCP_PROJECT_ID \
    --data-file=- \
    --replication-policy="automatic" || echo "Secret already exists, skipping..."

# Grant access to sentiment analysis service account
gcloud secrets add-iam-policy-binding gemini-api-key \
    --project=$GCP_PROJECT_ID \
    --member="serviceAccount:msa-sentiment-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

echo -e "${GREEN}Secrets configured!${NC}"
echo ""

# Step 3: Enable Artifact Registry and create repository
echo -e "${GREEN}Step 3: Setting up Artifact Registry${NC}"
gcloud services enable artifactregistry.googleapis.com --project=$GCP_PROJECT_ID

gcloud artifacts repositories create msa-images \
    --project=$GCP_PROJECT_ID \
    --repository-format=docker \
    --location=$REGION \
    --description="MSA Docker images" || echo "Repository already exists, skipping..."

echo -e "${GREEN}Artifact Registry ready!${NC}"
echo ""

# Step 4: Build and Push Docker Images
echo -e "${GREEN}Step 4: Building and Pushing Docker Images${NC}"

SERVICES=("ingestion" "sentiment-analysis" "aggregation" "api" "monitoring")

for service in "${SERVICES[@]}"; do
    echo -e "${YELLOW}Building $service...${NC}"
    
    IMAGE_NAME="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-$service:latest"
    
    docker build -t $IMAGE_NAME -f services/$service/Dockerfile .
    docker push $IMAGE_NAME
    
    echo -e "${GREEN}✓ $service image pushed${NC}"
done

echo -e "${GREEN}All images built and pushed!${NC}"
echo ""

# Step 5: Deploy Services to Cloud Run
echo -e "${GREEN}Step 5: Deploying Services to Cloud Run${NC}"

# Deploy Ingestion Service
echo -e "${YELLOW}Deploying Ingestion Service...${NC}"
gcloud run deploy msa-ingestion \
    --project=$GCP_PROJECT_ID \
    --image="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-ingestion:latest" \
    --region=$REGION \
    --service-account=msa-ingestion-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,RAW_DATA_TOPIC=raw-data-topic,BIGQUERY_DATASET=msa_$ENV,ENV=$ENV" \
    --allow-unauthenticated \
    --max-instances=100 \
    --min-instances=0

# Deploy Sentiment Analysis Service
echo -e "${YELLOW}Deploying Sentiment Analysis Service...${NC}"
gcloud run deploy msa-sentiment-analysis \
    --project=$GCP_PROJECT_ID \
    --image="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-sentiment-analysis:latest" \
    --region=$REGION \
    --service-account=msa-sentiment-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,RAW_DATA_SUBSCRIPTION=raw-data-sentiment-sub,ANALYZED_DATA_TOPIC=analyzed-data-topic,BIGQUERY_DATASET=msa_$ENV" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --no-allow-unauthenticated \
    --max-instances=50 \
    --min-instances=1 \
    --memory=1Gi \
    --cpu=2

# Deploy Aggregation Service
echo -e "${YELLOW}Deploying Aggregation Service...${NC}"
gcloud run deploy msa-aggregation \
    --project=$GCP_PROJECT_ID \
    --image="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-aggregation:latest" \
    --region=$REGION \
    --service-account=msa-aggregation-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,ANALYZED_DATA_SUBSCRIPTION=analyzed-data-aggregation-sub,BIGQUERY_DATASET=msa_$ENV" \
    --no-allow-unauthenticated \
    --max-instances=20 \
    --min-instances=1

# Deploy API Service
echo -e "${YELLOW}Deploying API Service...${NC}"
gcloud run deploy msa-api \
    --project=$GCP_PROJECT_ID \
    --image="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-api:latest" \
    --region=$REGION \
    --service-account=msa-api-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,BIGQUERY_DATASET=msa_$ENV,ENV=$ENV" \
    --allow-unauthenticated \
    --max-instances=50 \
    --min-instances=1

# Deploy Monitoring Service
echo -e "${YELLOW}Deploying Monitoring Service...${NC}"
INGESTION_URL=$(gcloud run services describe msa-ingestion --region=$REGION --format="value(status.url)")
API_URL=$(gcloud run services describe msa-api --region=$REGION --format="value(status.url)")

gcloud run deploy msa-monitoring \
    --project=$GCP_PROJECT_ID \
    --image="$REGION-docker.pkg.dev/$GCP_PROJECT_ID/msa-images/msa-monitoring:latest" \
    --region=$REGION \
    --service-account=msa-monitoring-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,BIGQUERY_DATASET=msa_$ENV,INGESTION_URL=$INGESTION_URL,API_URL=$API_URL" \
    --no-allow-unauthenticated \
    --max-instances=5 \
    --min-instances=1

echo -e "${GREEN}All services deployed!${NC}"
echo ""

# Step 6: Verification
echo -e "${GREEN}Step 6: Verification${NC}"

INGESTION_URL=$(gcloud run services describe msa-ingestion --region=$REGION --format="value(status.url)")
API_URL=$(gcloud run services describe msa-api --region=$REGION --format="value(status.url)")

echo -e "${YELLOW}Service URLs:${NC}"
echo "  Ingestion: $INGESTION_URL"
echo "  API: $API_URL"
echo ""

echo -e "${YELLOW}Testing Ingestion Service...${NC}"
curl "$INGESTION_URL/health" && echo "" || echo -e "${RED}Health check failed${NC}"

echo -e "${YELLOW}Testing API Service...${NC}"
curl "$API_URL/health" && echo "" || echo -e "${RED}Health check failed${NC}"

echo ""
echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Test sentiment analysis:"
echo "   curl -X POST $INGESTION_URL/v1/analyze \\"
echo "     -H 'X-API-Key: test-api-key' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"text\": \"This is amazing!\", \"language\": \"en\"}'"
echo ""
echo "2. View API documentation:"
echo "   $API_URL/docs"
echo ""
echo "3. Query results (after ~30s):"
echo "   curl '$API_URL/v1/sentiments?tenant_id=default&limit=10' \\"
echo "     -H 'X-API-Key: test-api-key'"
echo ""
