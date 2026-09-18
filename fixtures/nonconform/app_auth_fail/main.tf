resource "google_cloud_run_service_iam_member" "public_access" {
  service  = "insecure-service"
  location = "us-central1"
  role     = "roles/run.invoker"
  member   = "allUsers"
}
