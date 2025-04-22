locals {
  cloud_functions = {
    generate_job_strategy = {
      name        = "generate_job_strategy"
      description = "Generate job search strategy"
      entry_point = "generate_job_strategy"
      memory     = "256"
    }
    generate_medium_article = {
      name        = "generate_medium_article"
      description = "Generate Medium articles"
      entry_point = "generate_medium_article"
      memory     = "256"
    }
    update_profile_data = {
      name        = "update_profile_data"
      description = "Update profile data"
      entry_point = "update_profile_data"
      memory     = "256"
    }
    deploy_github_pages = {
      name        = "deploy_github_pages"
      description = "Deploy GitHub Pages"
      entry_point = "deploy_github_pages"
      memory     = "256"
    }
    cleanup_strategy_files = {
      name        = "cleanup_strategy_files"
      description = "Clean up old strategy files"
      entry_point = "cleanup_strategy_files"
      memory     = "256"
    }
    retrieve_file = {
      name        = "retrieve_file"
      description = "Retrieve files from GCS"
      entry_point = "retrieve_file"
      memory     = "256"
    }
    generate_documents = {
      name        = "generate_documents"
      description = "Generate tailored resumes and cover letters"
      entry_point = "generate_job_documents"
      memory     = "512"
    }
  }
}