# Pub/Sub Module
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "topics" {
  description = "Map of Pub/Sub topics to create"
  type = map(object({
    name                       = string
    message_retention_duration = string
  }))
}

variable "subscriptions" {
  description = "Map of Pub/Sub subscriptions to create"
  type = map(object({
    name                 = string
    topic                = string
    ack_deadline_seconds = number
    retry_policy = object({
      minimum_backoff = string
      maximum_backoff = string
    })
  }))
}

# Create Pub/Sub topics
resource "google_pubsub_topic" "topics" {
  for_each = var.topics
  
  name    = each.value.name
  project = var.project_id
  
  message_retention_duration = each.value.message_retention_duration
  
  labels = {
    managed_by = "terraform"
  }
}

# Create Pub/Sub subscriptions
resource "google_pubsub_subscription" "subscriptions" {
  for_each = var.subscriptions
  
  name    = each.value.name
  topic   = google_pubsub_topic.topics[each.value.topic].id
  project = var.project_id
  
  ack_deadline_seconds = each.value.ack_deadline_seconds
  
  retry_policy {
    minimum_backoff = each.value.retry_policy.minimum_backoff
    maximum_backoff = each.value.retry_policy.maximum_backoff
  }
  
  labels = {
    managed_by = "terraform"
  }
}

# Outputs
output "topics" {
  description = "Created Pub/Sub topics"
  value       = google_pubsub_topic.topics
}

output "subscriptions" {
  description = "Created Pub/Sub subscriptions"
  value       = google_pubsub_subscription.subscriptions
}
