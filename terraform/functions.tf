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

resource "google_cloudfunctions_function" "functions" {
  for_each    = local.cloud_functions
  name        = each.value.name
  description = each.value.description
  runtime     = "python311"

  available_memory_mb   = each.value.memory
  source_archive_bucket = google_storage_bucket.function_source.name
  source_archive_object = google_storage_bucket_object.function_archive.name
  trigger_http          = true
  entry_point           = each.value.entry_point
  service_account_email = google_service_account.function_account.email
  build_service_account = "projects/${data.google_project.project.project_id}/serviceAccounts/${google_service_account.function_account.email}"
  depends_on = [
    google_project_iam_member.function_roles
  ]
}