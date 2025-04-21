terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Service account for Cloud Functions
resource "google_service_account" "function_account" {
  account_id   = "job-search-functions"
  display_name = "Service Account for Job Search Functions"
}

# Grant Secret Manager access
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.function_account.email}"
}

# Grant Storage access
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.function_account.email}"
}

# Cloud Function IAM policy
resource "google_cloudfunctions_function_iam_member" "invoker" {
  for_each = var.cloud_functions

  project        = var.project_id
  region         = var.region
  cloud_function = each.key

  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.function_account.email}"
}