# ─────────────────────────────────────────────────────────────────────
# Step 6b – Security Compliance Agent Infrastructure (additive only)
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
# ─────────────────────────────────────────────────────────────────────


###########################
# Service Account: compliance-agent-sa
###########################
resource "google_service_account" "compliance_agent" {
  account_id   = "compliance-agent-sa"
  display_name = "Security Compliance Agent – Step 6b (Cloud Run)"
}

# IAM: roles/logging.logWriter
resource "google_project_iam_member" "compliance_agent_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.compliance_agent.email}"

  depends_on = [google_project_service.services]
}

# IAM: roles/storage.objectViewer on config bucket (read control-mappings, OPA policies)
resource "google_storage_bucket_iam_member" "compliance_agent_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.compliance_agent.email}"
}

# IAM: roles/storage.objectCreator on config bucket (write proposals + feed snapshots)
resource "google_storage_bucket_iam_member" "compliance_agent_config_writer" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.compliance_agent.email}"
}

# IAM: roles/secretmanager.secretAccessor (GitHub token, optional NIST API key)
resource "google_project_iam_member" "compliance_agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.compliance_agent.email}"

  depends_on = [google_project_service.secretmanager]
}

# IAM: roles/artifactregistry.reader (pull container images)
resource "google_project_iam_member" "compliance_agent_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.compliance_agent.email}"

  depends_on = [google_project_service.services]
}

# Allow gha-infra SA to act as compliance-agent-sa (Terraform deployments)
resource "google_service_account_iam_member" "infra_can_actas_compliance_agent" {
  service_account_id = google_service_account.compliance_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"

  depends_on = [google_project_service.services]
}

# Allow gha-app SA to act as compliance-agent-sa (CI/CD deployments)
resource "google_service_account_iam_member" "app_can_actas_compliance_agent" {
  service_account_id = google_service_account.compliance_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_app.email}"

  depends_on = [google_project_service.services]
}


###########################
# Secret Manager: NIST API Key (optional, higher rate limit)
###########################
resource "google_secret_manager_secret" "nist_api_key" {
  secret_id = "compliance-agent-nist-api-key"
  replication {
    auto {}
  }
  depends_on = [
    google_project_service.secretmanager,
    google_project_iam_member.compliance_agent_secret_accessor,
    google_service_account_iam_member.infra_can_actas_compliance_agent,
  ]
}


###########################
# Cloud Run v2: security-compliance-agent
###########################
resource "google_cloud_run_v2_service" "compliance_agent" {
  name     = "security-compliance-agent"
  location = var.region

  template {
    service_account = google_service_account.compliance_agent.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1  # batch job, single instance sufficient
    }

    containers {
      image = var.compliance_agent_image

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
        name  = "CONFIG_BUCKET"
        value = google_storage_bucket.cogniops_config.name
      }
      env {
        name  = "PROPOSALS_BUCKET"
        value = google_storage_bucket.cogniops_config.name
      }
      env {
        name  = "COGNIOPS_MODEL"
        value = "gemini-2.0-flash"
      }
      env {
        name  = "LOOKBACK_DAYS"
        value = "7"
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
        name = "NIST_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.nist_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  ingress    = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  depends_on = [
    google_project_service.services,
    google_secret_manager_secret.nist_api_key,
    google_service_account_iam_member.infra_can_actas_compliance_agent,
    google_service_account_iam_member.app_can_actas_compliance_agent,
    google_project_iam_member.compliance_agent_log_writer,
    google_project_iam_member.compliance_agent_secret_accessor,
    google_project_iam_member.compliance_agent_ar_reader,
    google_storage_bucket_iam_member.compliance_agent_config_reader,
    google_storage_bucket_iam_member.compliance_agent_config_writer,
  ]
}


###########################
# Cloud Scheduler: compliance check (weekly)
###########################
resource "google_project_service" "cloudscheduler" {
  project            = var.project_id
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_scheduler_job" "compliance_check" {
  name        = "compliance-agent-weekly"
  description = "Trigger Security Compliance Agent weekly check"
  schedule    = "0 6 * * 1"  # Every Monday at 06:00 UTC
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.compliance_agent.uri}/run"

    oidc_token {
      service_account_email = google_service_account.compliance_agent.email
    }
  }

  depends_on = [
    google_project_service.cloudscheduler,
    google_cloud_run_v2_service.compliance_agent,
  ]
}

# compliance-agent-sa needs roles/run.invoker on its own service (Cloud Scheduler invocation)
resource "google_cloud_run_v2_service_iam_member" "compliance_agent_self_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.compliance_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.compliance_agent.email}"
}


###########################
# Outputs
###########################
output "compliance_agent_sa_email" {
  description = "Email of the compliance-agent service account."
  value       = google_service_account.compliance_agent.email
}

output "compliance_agent_url" {
  description = "URL of the security-compliance-agent Cloud Run service."
  value       = google_cloud_run_v2_service.compliance_agent.uri
}

output "compliance_scheduler_name" {
  description = "Name of the Cloud Scheduler job for compliance checks."
  value       = google_cloud_scheduler_job.compliance_check.name
}
