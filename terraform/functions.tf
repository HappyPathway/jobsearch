data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../functions"
  output_path = "${path.root}/function-source.zip"
}

resource "google_storage_bucket_object" "function_archive" {
  name   = "function-source-${data.archive_file.function_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function_zip.output_path
}

resource "google_artifact_registry_repository" "function_repo" {
  location      = var.region
  repository_id = "cloud-functions"
  description   = "Docker repository for Cloud Functions"
  format        = "DOCKER"
}

resource "google_cloudfunctions2_function" "job_strategy" {
  name        = "generate_job_strategy"
  location    = var.region
  description = "Generate job search strategy"

  build_config {
    runtime     = "python311"
    entry_point = "generate_job_strategy"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}

resource "google_cloudfunctions2_function" "medium_article" {
  name        = "generate_medium_article"
  location    = var.region
  description = "Generate Medium articles"

  build_config {
    runtime     = "python311"
    entry_point = "generate_medium_article"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}

resource "google_cloudfunctions2_function" "profile_update" {
  name        = "update_profile_data"
  location    = var.region
  description = "Update profile data"

  build_config {
    runtime     = "python311"
    entry_point = "update_profile_data"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}

resource "google_cloudfunctions2_function" "github_pages" {
  name        = "deploy_github_pages"
  location    = var.region
  description = "Deploy GitHub Pages"

  build_config {
    runtime     = "python311"
    entry_point = "deploy_github_pages"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}

resource "google_cloudfunctions2_function" "strategy_cleanup" {
  name        = "cleanup_strategy_files"
  location    = var.region
  description = "Clean up old strategy files"

  build_config {
    runtime     = "python311"
    entry_point = "cleanup_strategy_files"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}

resource "google_cloudfunctions2_function" "file_retrieval" {
  name        = "retrieve_file"
  location    = var.region
  description = "Retrieve files from GCS"

  build_config {
    runtime     = "python311"
    entry_point = "retrieve_file"
    docker_repository = google_artifact_registry_repository.function_repo.id
    service_account_email = google_service_account.function_account.email
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_account.email
  }
}