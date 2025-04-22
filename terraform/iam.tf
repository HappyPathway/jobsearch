# Required permissions for Cloud Functions runtime and build
locals {
  function_roles = [
    "roles/cloudfunctions.developer",
    "roles/cloudbuild.builds.builder",
    "roles/artifactregistry.reader",
    "roles/run.invoker",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/iam.serviceAccountUser"
  ]
}

# Service account for Cloud Functions
resource "google_service_account" "function_account" {
  account_id   = "job-search-functions"
  display_name = "Service Account for Job Search Functions"
}

resource "google_project_iam_member" "function_roles" {
  for_each = toset(local.function_roles)
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.function_account.email}"
}

# Cloud Function IAM policy
resource "google_cloudfunctions_function_iam_member" "invoker" {
  for_each = local.cloud_functions

  project        = var.project_id
  region         = var.region
  cloud_function = each.value.name

  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.function_account.email}"
  depends_on = [
    google_cloudfunctions_function.functions
  ]
}