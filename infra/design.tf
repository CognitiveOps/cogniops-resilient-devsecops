# ─────────────────────────────────────────────────────────────────────
# Step 6 – Design-Time Agent Infrastructure (additive only)
#
# References from main.tf (read-only):
#   - google_bigquery_dataset.metrics
#   - google_service_account.gha_infra
#   - google_service_account.gha_app
#   - data.google_project.current
#
# References from runtime.tf (read-only):
#   - google_storage_bucket.cogniops_config
#   - google_project_service.secretmanager
#   - google_secret_manager_secret.runtime_github_token
# ─────────────────────────────────────────────────────────────────────


###########################
# Service Account: design-agent-sa
###########################
resource "google_service_account" "design_agent" {
  account_id   = "design-agent-sa"
  display_name = "Design-Time Agent – Step 6 (Cloud Run)"
}

# IAM: roles/logging.logWriter
resource "google_project_iam_member" "design_agent_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.design_agent.email}"
}

# IAM: roles/bigquery.dataViewer (read-only!) scoped to agent_metrics dataset
resource "google_bigquery_dataset_iam_member" "design_agent_bq_reader" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.design_agent.email}"
}

# IAM: roles/bigquery.jobUser (needed to run queries)
resource "google_project_iam_member" "design_agent_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.design_agent.email}"
}

# IAM: roles/storage.objectViewer on config bucket (read control-mappings, thresholds)
resource "google_storage_bucket_iam_member" "design_agent_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.design_agent.email}"
}

# IAM: roles/storage.objectCreator on config bucket (write proposals)
resource "google_storage_bucket_iam_member" "design_agent_config_writer" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.design_agent.email}"
}

# IAM: roles/secretmanager.secretAccessor (GitHub token for issue creation)
resource "google_project_iam_member" "design_agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.design_agent.email}"

  depends_on = [google_project_service.secretmanager]
}

# IAM: roles/artifactregistry.reader (pull container images)
resource "google_project_iam_member" "design_agent_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.design_agent.email}"
}

# Allow gha-infra SA to act as design-agent-sa (Terraform deployments)
resource "google_service_account_iam_member" "infra_can_actas_design_agent" {
  service_account_id = google_service_account.design_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

# Allow gha-app SA to act as design-agent-sa (CI/CD deployments)
resource "google_service_account_iam_member" "app_can_actas_design_agent" {
  service_account_id = google_service_account.design_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}


###########################
# Cloud Run v2: design-agent
###########################
resource "google_cloud_run_v2_service" "design_agent" {
  name     = "design-agent"
  location = var.region

  template {
    service_account = google_service_account.design_agent.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1  # batch analysis, single instance sufficient
    }

    containers {
      image = var.design_agent_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # ── Environment Variables ──
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = "agent_metrics"
      }
      env {
        name  = "CONFIG_BUCKET"
        value = google_storage_bucket.cogniops_config.name
      }
      env {
        name  = "PROPOSALS_PREFIX"
        value = "proposals/design"
      }
      env {
        name  = "COGNIOPS_MODEL"
        value = "gemini-2.0-flash"
      }
      env {
        name  = "CONTEXT_WINDOW_DAYS"
        value = "30"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "GITHUB_REPO"
        value = var.github_repo
      }
      env {
        name  = "COMMIT_SHA"
        value = "managed-by-ci"
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime_github_token.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  ingress = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.services,
    google_project_iam_member.design_agent_secret_accessor,
  ]

  # CI/CD deploys the real image; Terraform must not revert to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}


###########################
# Cloud Scheduler: design analysis (weekly)
###########################
resource "google_cloud_scheduler_job" "design_analysis" {
  name        = "design-agent-weekly"
  description = "Trigger Design-Time Agent weekly analysis"
  schedule    = "0 7 * * 1"  # Every Monday at 07:00 UTC (after compliance at 06:00)
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.design_agent.uri}/run"

    oidc_token {
      service_account_email = google_service_account.design_agent.email
    }
  }

  depends_on = [
    google_project_service.cloudscheduler,
    google_cloud_run_v2_service.design_agent,
  ]
}

# design-agent-sa needs roles/run.invoker on its own service (Cloud Scheduler invocation)
resource "google_cloud_run_v2_service_iam_member" "design_agent_self_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.design_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.design_agent.email}"
}

# gha-app SA needs roles/run.invoker on design-agent (CI smoke tests)
resource "google_cloud_run_v2_service_iam_member" "gha_app_design_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.design_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gha_app.email}"
}


###########################
# Outputs
###########################
output "design_agent_sa_email" {
  description = "Email of the design-agent service account."
  value       = google_service_account.design_agent.email
}

output "design_agent_url" {
  description = "URL of the design-agent Cloud Run service."
  value       = google_cloud_run_v2_service.design_agent.uri
}

output "design_scheduler_name" {
  description = "Name of the Cloud Scheduler job for design analysis."
  value       = google_cloud_scheduler_job.design_analysis.name
}
