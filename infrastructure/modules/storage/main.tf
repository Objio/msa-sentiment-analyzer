# Cloud Storage Module

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "buckets" {
  description = "Map of Cloud Storage buckets to create"
  type = map(object({
    name          = string
    storage_class = string
    lifecycle_rules = list(object({
      action = object({
        type          = string
        storage_class = optional(string)
      })
      condition = object({
        age = number
      })
    }))
  }))
}

# Create Cloud Storage buckets
resource "google_storage_bucket" "buckets" {
  for_each = var.buckets
  
  name          = each.value.name
  location      = var.region
  project       = var.project_id
  storage_class = each.value.storage_class
  
  uniform_bucket_level_access = true
  
  dynamic "lifecycle_rule" {
    for_each = each.value.lifecycle_rules
    content {
      action {
        type          = lifecycle_rule.value.action.type
        storage_class = lifecycle_rule.value.action.storage_class
      }
      condition {
        age = lifecycle_rule.value.condition.age
      }
    }
  }
  
  labels = {
    managed_by = "terraform"
  }
}

# Outputs
output "buckets" {
  description = "Created Cloud Storage buckets"
  value       = google_storage_bucket.buckets
}
