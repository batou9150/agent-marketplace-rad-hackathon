resource "google_cloud_run_service" "secured_service" {
  name     = "secured-agent-service"
  location = "europe-west1"

  template {
    spec {
      containers {
        image = "europe-west1-docker.pkg.dev/my-project/repo/agent:v1"
      }
    }
    metadata {
      annotations = {
        "run.googleapis.com/ingress" = "internal-and-cloud-load-balancing"
      }
    }
  }
}

resource "google_cloud_run_service_iam_member" "authorized_invoker" {
  service  = google_cloud_run_service.secured_service.name
  location = google_cloud_run_service.secured_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:authorized-gateway@my-project.iam.gserviceaccount.com"
}
