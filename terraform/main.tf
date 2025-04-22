terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
    }
  }
}

# Create GCS bucket for function source code
resource "google_storage_bucket" "function_source" {
  name     = "${var.project_id}-function-source"
  location = var.region
  uniform_bucket_level_access = true
}

data "google_project" "project" {}