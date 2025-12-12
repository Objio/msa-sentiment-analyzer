# IAM Module - Service Accounts and Permissions

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "service_accounts" {
  description = "Map of service accounts to create with roles"
  type = map(object({
    account_id   = string
    display_name = string
    roles        = list(string)
  }))
}

# Create service accounts
resource "google_service_account" "accounts" {
  for_each = var.service_accounts
  
  account_id   = each.value.account_id
  display_name = each.value.display_name
  project      = var.project_id
}

# Assign IAM roles to service accounts
resource "google_project_iam_member" "roles" {
  for_each = merge([
    for sa_key, sa in var.service_accounts : {
      for role in sa.roles :
      "${sa_key}-${role}" => {
        service_account = google_service_account.accounts[sa_key].email
        role            = role
      }
    }
  ]...)
  
  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${each.value.service_account}"
}

# Outputs
output "service_accounts" {
  description = "Created service accounts"
  value       = google_service_account.accounts
}
