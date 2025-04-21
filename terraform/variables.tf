variable "project_id" {
  description = "The Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "The region to deploy resources to"
  type        = string
  default     = "us-central1"
}

variable "cloud_functions" {
  description = "Map of Cloud Functions to deploy"
  type        = set(string)
  default = [
    "generate_job_strategy",
    "generate_medium_article",
    "update_profile_data",
    "deploy_github_pages",
    "cleanup_strategy_files"
  ]
}

variable "source_bucket" {
  description = "GCS bucket containing Cloud Functions source code"
  type        = string
}