resource "google_cloudfunctions2_function" "job_strategy" {
  name        = "generate_job_strategy"
  location    = var.region
  description = "Generate job search strategy"

  build_config {
    runtime     = "python311"
    entry_point = "generate_job_strategy"
    source {
      storage_source {
        bucket = var.source_bucket
        object = "function-source.zip"
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
    source {
      storage_source {
        bucket = var.source_bucket
        object = "function-source.zip"
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
    source {
      storage_source {
        bucket = var.source_bucket
        object = "function-source.zip"
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
    source {
      storage_source {
        bucket = var.source_bucket
        object = "function-source.zip"
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
    source {
      storage_source {
        bucket = var.source_bucket
        object = "function-source.zip"
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