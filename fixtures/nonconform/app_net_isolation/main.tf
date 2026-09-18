resource "google_cloud_run_service" "default" {
  name     = "vibe-app"
  location = "europe-west1"

  template {
    spec {
      containers {
        image = "gcr.io/my-project/vibe-app:latest"
      }
    }
    metadata {
      annotations = {
        "run.googleapis.com/ingress" = "all"
      }
    }
  }
}
