# Cloud Run Module - Serverless Services

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "services" {
  description = "Map of Cloud Run services to create"
  type = map(object({
    name                = string
    image               = string
    service_account     = string
    max_instances       = number
    min_instances       = number
    cpu                 = string
    memory              = string
    timeout             = string
    concurrency         = number
    allow_public_access = bool
    env_vars            = map(string)
  }))
}

# Create Cloud Run services
resource "google_cloud_run_v2_service" "services" {
  for_each = var.services
  
  name     = each.value.name
  location = var.region
  project  = var.project_id
  
  template {
    service_account = each.value.service_account
    
    scaling {
      max_instance_count = each.value.max_instances
      min_instance_count = each.value.min_instances
    }
    
    containers {
      image = each.value.image
      
      resources {
        limits = {
          cpu    = each.value.cpu
          memory = each.value.memory
        }
      }
      
      dynamic "env" {
        for_each = each.value.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }
    }
    
    timeout = each.value.timeout
    max_instance_request_concurrency = each.value.concurrency
  }
  
  labels = {
    managed_by = "terraform"
  }
}

# Allow public access if specified
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  for_each = {
    for k, v in var.services : k => v if v.allow_public_access
  }
  
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.services[each.key].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "services" {
  description = "Created Cloud Run services"
  value = {
    for k, v in google_cloud_run_v2_service.services : k => {
      name  = v.name
      url   = v.uri
      id    = v.id
    }
  }
}
