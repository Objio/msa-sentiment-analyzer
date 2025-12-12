# MSA Quick Deploy Script (PowerShell)
# Deploys all infrastructure and services to GCP

$ErrorActionPreference = "Stop"

Write-Host "=== Massive Sentiment Analyzer - Quick Deploy ===" -ForegroundColor Green
Write-Host ""

# Check required environment variables
if (-not $env:GCP_PROJECT_ID) {
    Write-Host "Error: GCP_PROJECT_ID environment variable not set" -ForegroundColor Red
    exit 1
}

if (-not $env:GEMINI_API_KEY) {
    Write-Host "Error: GEMINI_API_KEY environment variable not set" -ForegroundColor Red
    exit 1
}

$REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
$ENV = if ($env:ENV) { $env:ENV } else { "production" }

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Project ID: $env:GCP_PROJECT_ID"
Write-Host "  Region: $REGION"
Write-Host "  Environment: $ENV"
Write-Host ""

# Step 1: Deploy Infrastructure
Write-Host "Step 1: Deploying Infrastructure with Terraform" -ForegroundColor Green
cd infrastructure/environments/$ENV

if (-not (Test-Path terraform.tfvars)) {
    Write-Host "Creating terraform.tfvars from example..."
    Copy-Item terraform.tfvars.example terraform.tfvars
    (Get-Content terraform.tfvars) -replace 'your-gcp-project-id', $env:GCP_PROJECT_ID -replace 'us-central1', $REGION | Set-Content terraform.tfvars
}

terraform init
terraform plan -out=tfplan
Write-Host "Review the plan above. Press Enter to continue or Ctrl+C to cancel" -ForegroundColor Yellow
Read-Host

terraform apply tfplan
cd ../../..

Write-Host "Infrastructure deployed!" -ForegroundColor Green
Write-Host ""

# Step 2: Store Gemini API Key
Write-Host "Step 2: Storing Gemini API Key in Secret Manager" -ForegroundColor Green
echo $env:GEMINI_API_KEY | gcloud secrets create gemini-api-key `
    --project=$env:GCP_PROJECT_ID `
    --data-file=- `
    --replication-policy="automatic" 2>$null

gcloud secrets add-iam-policy-binding gemini-api-key `
    --project=$env:GCP_PROJECT_ID `
    --member="serviceAccount:msa-sentiment-sa@$env:GCP_PROJECT_ID.iam.gserviceaccount.com" `
    --role="roles/secretmanager.secretAccessor"

Write-Host "Secrets configured!" -ForegroundColor Green
Write-Host ""

# Step 3: Artifact Registry
Write-Host "Step 3: Setting up Artifact Registry" -ForegroundColor Green
gcloud services enable artifactregistry.googleapis.com --project=$env:GCP_PROJECT_ID

gcloud artifacts repositories create msa-images `
    --project=$env:GCP_PROJECT_ID `
    --repository-format=docker `
    --location=$REGION `
    --description="MSA Docker images" 2>$null

Write-Host "Artifact Registry ready!" -ForegroundColor Green
Write-Host ""

# Step 4: Build and Push Docker Images
Write-Host "Step 4: Building and Pushing Docker Images" -ForegroundColor Green

$SERVICES = @("ingestion", "sentiment-analysis", "aggregation", "api", "monitoring")

foreach ($service in $SERVICES) {
    Write-Host "Building $service..." -ForegroundColor Yellow
    
    $IMAGE_NAME = "$REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/msa-images/msa-$service:latest"
    
    docker build -t $IMAGE_NAME -f services/$service/Dockerfile .
    docker push $IMAGE_NAME
    
    Write-Host "✓ $service image pushed" -ForegroundColor Green
}

Write-Host "All images built and pushed!" -ForegroundColor Green
Write-Host ""

# Step 5: Deploy Services
Write-Host "Step 5: Deploying Services to Cloud Run" -ForegroundColor Green

# Deploy each service
gcloud run deploy msa-ingestion `
    --project=$env:GCP_PROJECT_ID `
    --image="$REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/msa-images/msa-ingestion:latest" `
    --region=$REGION `
    --service-account=msa-ingestion-sa@$env:GCP_PROJECT_ID.iam.gserviceaccount.com `
    --set-env-vars="GCP_PROJECT_ID=$env:GCP_PROJECT_ID,RAW_DATA_TOPIC=raw-data-topic,BIGQUERY_DATASET=msa_$ENV,ENV=$ENV" `
    --allow-unauthenticated `
    --max-instances=100 `
    --min-instances=0

Write-Host "All services deployed!" -ForegroundColor Green
Write-Host ""

# Step 6: Verification
Write-Host "Step 6: Verification" -ForegroundColor Green

$INGESTION_URL = gcloud run services describe msa-ingestion --region=$REGION --format="value(status.url)"
$API_URL = gcloud run services describe msa-api --region=$REGION --format="value(status.url)"

Write-Host "Service URLs:" -ForegroundColor Yellow
Write-Host "  Ingestion: $INGESTION_URL"
Write-Host "  API: $API_URL"
Write-Host ""

Write-Host "=== Deployment Complete! ===" -ForegroundColor Green
