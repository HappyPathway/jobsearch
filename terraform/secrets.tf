resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "GEMINI_API_KEY"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "medium_api_token" {
  secret_id = "MEDIUM_API_TOKEN"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "slack_api_token" {
  secret_id = "SLACK_API_TOKEN"
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "slack_channel_id" {
  secret_id = "SLACK_CHANNEL_ID"
  
  replication {
    auto {}
  }
}

# Note: Secret versions are managed through the migrate_secrets.py script
# This configuration only creates the secret containers