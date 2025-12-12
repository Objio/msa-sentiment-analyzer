terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  
  backend "gcs" {
    # bucket  = "msa-terraform-state"  # Set via backend-config in CI/CD
    # prefix  = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
  ])
  
  service            = each.value
  disable_on_destroy = false
}

# Pub/Sub Topics and Subscriptions
module "pubsub" {
  source = "../../modules/pubsub"
  
  project_id = var.project_id
  region     = var.region
  
  topics = {
    raw_data = {
      name                       = "raw-data-topic"
      message_retention_duration = "604800s" # 7 days
    }
    analyzed_data = {
      name                       = "analyzed-data-topic"
      message_retention_duration = "604800s" # 7 days
    }
  }
  
  subscriptions = {
    raw_data_sentiment = {
      name               = "raw-data-sentiment-sub"
      topic              = "raw-data-topic"
      ack_deadline_seconds = 600  # 10 minutes
      retry_policy = {
        minimum_backoff = "10s"
        maximum_backoff = "600s"
      }
    }
    analyzed_data_aggregation = {
      name               = "analyzed-data-aggregation-sub"
      topic              = "analyzed-data-topic"
      ack_deadline_seconds = 300  # 5 minutes
      retry_policy = {
        minimum_backoff = "10s"
        maximum_backoff = "600s"
      }
    }
  }
  
  depends_on = [google_project_service.required_apis]
}

# BigQuery Dataset and Tables
module "bigquery" {
  source = "../../modules/bigquery"
  
  project_id = var.project_id
  region     = var.region
  
  dataset_id = "msa_${var.environment}"
  dataset_description = "Massive Sentiment Analyzer data warehouse - ${var.environment}"
  
  tables = {
    raw_texts = {
      table_id    = "raw_texts"
      description = "Audit trail of all ingested texts"
      schema_file = "schemas/raw_texts.json"
      partitioning = {
        type  = "DAY"
        field = "ingested_at"
      }
      clustering = ["tenant_id", "source"]
    }
    sentiments = {
      table_id    = "sentiments"
      description = "Sentiment analysis results"
      schema_file = "schemas/sentiments.json"
      partitioning = {
        type  = "DAY"
        field = "processed_at"
      }
      clustering = ["tenant_id", "overall_sentiment"]
    }
    aggregated_metrics = {
      table_id    = "aggregated_metrics"
      description = "Pre-computed aggregations for fast querying"
      schema_file = "schemas/aggregated_metrics.json"
      partitioning = {
        type  = "DAY"
        field = "period_start"
      }
      clustering = ["tenant_id", "aggregation_level"]
    }
    api_usage = {
      table_id    = "api_usage"
      description = "API usage tracking for billing and quotas"
      schema_file = "schemas/api_usage.json"
      partitioning = {
        type  = "DAY"
        field = "request_timestamp"
      }
      clustering = ["tenant_id", "api_key"]
    }
  }
  
  depends_on = [google_project_service.required_apis]
}

# Cloud Storage Buckets
module "storage" {
  source = "../../modules/storage"
  
  project_id = var.project_id
  region     = var.region
  
  buckets = {
    raw_data = {
      name          = "msa-${var.environment}-raw-data"
      storage_class = "STANDARD"
      lifecycle_rules = [
        {
          action    = { type = "Delete" }
          condition = { age = 90 }  # Delete after 90 days
        }
      ]
    }
    processed_data = {
      name          = "msa-${var.environment}-processed-data"
      storage_class = "STANDARD"
      lifecycle_rules = [
        {
          action    = { type = "SetStorageClass", storage_class = "NEARLINE" }
          condition = { age = 30 }  # Move to Nearline after 30 days
        },
        {
          action    = { type = "Delete" }
          condition = { age = 365 }  # Delete after 1 year
        }
      ]
    }
  }
  
  depends_on = [google_project_service.required_apis]
}

# Service Accounts and IAM
module "iam" {
  source = "../../modules/iam"
  
  project_id = var.project_id
  
  service_accounts = {
    ingestion = {
      account_id   = "msa-ingestion-sa"
      display_name = "MSA Ingestion Service"
      roles = [
        "roles/pubsub.publisher",
        "roles/storage.objectCreator",
        "roles/bigquery.dataEditor",
        "roles/secretmanager.secretAccessor",
      ]
    }
    sentiment_analysis = {
      account_id   = "msa-sentiment-sa"
      display_name = "MSA Sentiment Analysis Service"
      roles = [
        "roles/pubsub.subscriber",
        "roles/pubsub.publisher",
        "roles/bigquery.dataEditor",
        "roles/storage.objectViewer",
        "roles/secretmanager.secretAccessor",
      ]
    }
    aggregation = {
      account_id   = "msa-aggregation-sa"
      display_name = "MSA Aggregation Service"
      roles = [
        "roles/pubsub.subscriber",
        "roles/bigquery.dataEditor",
        "roles/secretmanager.secretAccessor",
      ]
    }
    api = {
      account_id   = "msa-api-sa"
      display_name = "MSA API Service"
      roles = [
        "roles/bigquery.dataViewer",
        "roles/bigquery.jobUser",
        "roles/storage.objectViewer",
        "roles/secretmanager.secretAccessor",
      ]
    }
    monitoring = {
      account_id   = "msa-monitoring-sa"
      display_name = "MSA Monitoring Service"
      roles = [
        "roles/monitoring.metricWriter",
        "roles/logging.logWriter",
        "roles/bigquery.dataViewer",
      ]
    }
  }
  
  depends_on = [google_project_service.required_apis]
}

# Cloud Run Services
module "cloud_run" {
  source = "../../modules/cloud_run"
  
  project_id = var.project_id
  region     = var.region
  
  services = {
    ingestion = {
      name                = "msa-ingestion"
      image               = "gcr.io/${var.project_id}/msa-ingestion:latest"
      service_account     = module.iam.service_accounts["ingestion"].email
      max_instances       = 100
      min_instances       = 0
      cpu                 = "1"
      memory              = "512Mi"
      timeout             = "300s"
      concurrency         = 80
      allow_public_access = true
      
      env_vars = {
        ENV                = var.environment
        RAW_DATA_TOPIC     = module.pubsub.topics["raw_data"].name
        GCS_RAW_BUCKET     = module.storage.buckets["raw_data"].name
        BIGQUERY_DATASET   = module.bigquery.dataset_id
      }
    }
    
    sentiment_analysis = {
      name                = "msa-sentiment-analysis"
      image               = "gcr.io/${var.project_id}/msa-sentiment-analysis:latest"
      service_account     = module.iam.service_accounts["sentiment_analysis"].email
      max_instances       = 50
      min_instances       = 0  # Pay-per-use: scales to zero when idle
      cpu                 = "2"
      memory              = "1Gi"
      timeout             = "600s"
      concurrency         = 10
      allow_public_access = false
      
      env_vars = {
        ENV                    = var.environment
        RAW_DATA_SUBSCRIPTION  = module.pubsub.subscriptions["raw_data_sentiment"].name
        ANALYZED_DATA_TOPIC    = module.pubsub.topics["analyzed_data"].name
        BIGQUERY_DATASET       = module.bigquery.dataset_id
      }
    }
    
    aggregation = {
      name                = "msa-aggregation"
      image               = "gcr.io/${var.project_id}/msa-aggregation:latest"
      service_account     = module.iam.service_accounts["aggregation"].email
      max_instances       = 20
      min_instances       = 0  # Pay-per-use: scales to zero when idle
      cpu                 = "1"
      memory              = "512Mi"
      timeout             = "300s"
      concurrency         = 20
      allow_public_access = false
      
      env_vars = {
        ENV                          = var.environment
        ANALYZED_DATA_SUBSCRIPTION   = module.pubsub.subscriptions["analyzed_data_aggregation"].name
        BIGQUERY_DATASET             = module.bigquery.dataset_id
      }
    }
    
    api = {
      name                = "msa-api"
      image               = "gcr.io/${var.project_id}/msa-api:latest"
      service_account     = module.iam.service_accounts["api"].email
      max_instances       = 50
      min_instances       = 0  # Pay-per-use: scales to zero when idle
      cpu                 = "1"
      memory              = "512Mi"
      timeout             = "60s"
      concurrency         = 100
      allow_public_access = true
      
      env_vars = {
        ENV              = var.environment
        BIGQUERY_DATASET = module.bigquery.dataset_id
        GCS_BUCKET       = module.storage.buckets["processed_data"].name
      }
    }
    
    monitoring = {
      name                = "msa-monitoring"
      image               = "us-docker.pkg.dev/cloudrun/container/hello"
      service_account     = module.iam.service_accounts["monitoring"].email
      max_instances       = 5
      min_instances       = 0  # Pay-per-use: scales to zero when idle
      cpu                 = "1"
      memory              = "256Mi"
      timeout             = "60s"
      concurrency         = 50
      allow_public_access = false
      
      env_vars = {
        ENV              = var.environment
        BIGQUERY_DATASET = module.bigquery.dataset_id
      }
    }
  }
  
  depends_on = [
    google_project_service.required_apis,
    module.iam
  ]
}

# Outputs
output "pubsub_topics" {
  description = "Pub/Sub topic names"
  value       = { for k, v in module.pubsub.topics : k => v.name }
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value       = module.bigquery.dataset_id
}

output "storage_buckets" {
  description = "Cloud Storage bucket names"
  value       = { for k, v in module.storage.buckets : k => v.name }
}

output "cloud_run_urls" {
  description = "Cloud Run service URLs"
  value       = { for k, v in module.cloud_run.services : k => v.url }
  sensitive   = false
}

output "service_accounts" {
  description = "Service account emails"
  value       = { for k, v in module.iam.service_accounts : k => v.email }
}
