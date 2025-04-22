output "function_archive_hash" {
  description = "Hash of the function source code archive"
  value       = data.archive_file.function_zip.output_md5
}

output "function_source_bucket" {
  description = "Bucket containing function source code"
  value       = google_storage_bucket.function_source.name
}
