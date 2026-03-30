# ─────────────────────────────────────────────────────────────────────
# Phase 0 – Runtime-Ready Infrastructure (additive only)
# This file MUST NOT modify any resource defined in main.tf.
#
# References from main.tf (read-only):
#   - google_bigquery_dataset.metrics        (dataset_id = agent_metrics)
#   - google_service_account.gha_infra
#   - google_service_account.gha_app
#   - google_artifact_registry_repository.docker
#   - google_project_service.services        (baseline API enables)
#   - data.google_project.current
# ─────────────────────────────────────────────────────────────────────


###########################
# Enable Additional APIs
###########################
resource "google_project_service" "pubsub" {
  project            = var.project_id
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "aiplatform" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}


###########################
# Service Account: runtime-agent-sa
###########################
resource "google_service_account" "runtime_agent" {
  account_id   = "runtime-agent-sa"
  display_name = "Runtime Agent – Phase 0 (Cloud Run)"
}

# IAM: roles/logging.logWriter
resource "google_project_iam_member" "runtime_agent_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.services]
}

# IAM: roles/monitoring.metricWriter
resource "google_project_iam_member" "runtime_agent_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.services]
}

# IAM: roles/bigquery.dataEditor scoped to agent_metrics dataset only
resource "google_bigquery_dataset_iam_member" "runtime_agent_bq_writer" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.services]
}

# IAM: roles/secretmanager.secretAccessor (for AgentOps API key in Secret Manager)
resource "google_project_iam_member" "runtime_agent_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.secretmanager]
}

# IAM: roles/artifactregistry.reader (pull container images)
resource "google_project_iam_member" "runtime_agent_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.services]
}

# IAM: roles/aiplatform.user (Vertex AI Gemini for ADK cognitive planning)
resource "google_project_iam_member" "runtime_agent_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime_agent.email}"

  depends_on = [google_project_service.aiplatform]
}

# Allow gha-infra SA to act as runtime-agent-sa (Terraform deployments)
resource "google_service_account_iam_member" "infra_can_actas_runtime_agent" {
  service_account_id = google_service_account.runtime_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"

  depends_on = [google_project_service.services]
}

# Allow gha-app SA to act as runtime-agent-sa (CI/CD deployments)
resource "google_service_account_iam_member" "app_can_actas_runtime_agent" {
  service_account_id = google_service_account.runtime_agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_app.email}"

  depends_on = [google_project_service.services]
}


###########################
# Pub/Sub: runtime-events-v1
###########################
resource "google_pubsub_topic" "runtime_events" {
  name = "runtime-events-v1"

  depends_on = [google_project_service.pubsub]
}


###########################
# Pub/Sub: runtime-events-v1-dlq (Dead Letter)
###########################
resource "google_pubsub_topic" "runtime_events_dlq" {
  name = "runtime-events-v1-dlq"

  depends_on = [google_project_service.pubsub]
}


###########################
# Pub/Sub Push Subscription
###########################
resource "google_pubsub_subscription" "runtime_agent_push" {
  name  = "runtime-agent-push"
  topic = google_pubsub_topic.runtime_events.id

  ack_deadline_seconds = 30

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.runtime_agent.uri}/events/runtime"

    oidc_token {
      service_account_email = google_service_account.runtime_agent.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.runtime_events_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [
    google_project_service.pubsub,
    google_cloud_run_v2_service.runtime_agent,
  ]
}

# Pub/Sub service agent needs roles/pubsub.subscriber on the subscription (DLQ forwarding)
resource "google_pubsub_subscription_iam_member" "pubsub_sa_can_ack" {
  subscription = google_pubsub_subscription.runtime_agent_push.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Pub/Sub service agent needs roles/pubsub.publisher on DLQ topic (dead-letter forwarding)
resource "google_pubsub_topic_iam_member" "pubsub_sa_dlq_publisher" {
  topic  = google_pubsub_topic.runtime_events_dlq.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# gha-app gets roles/pubsub.publisher on runtime-events-v1 (publish pipeline events)
resource "google_pubsub_topic_iam_member" "gha_app_runtime_publisher" {
  topic  = google_pubsub_topic.runtime_events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.gha_app.email}"
}

# cf-ingest gets roles/pubsub.publisher on runtime-events-v1 (bridge: stage-event → RuntimeEvent)
resource "google_pubsub_topic_iam_member" "cf_ingest_runtime_publisher" {
  topic  = google_pubsub_topic.runtime_events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.cf_ingest.email}"
}


###########################
# BigQuery: runtime_decisions
###########################
resource "google_bigquery_table" "runtime_decisions" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "runtime_decisions"

  time_partitioning {
    type  = "DAY"
    field = "processed_at"
  }

  schema = jsonencode([
    { name = "event_id",          type = "STRING",    mode = "REQUIRED", description = "UUID from runtime event envelope" },
    { name = "event_type",        type = "STRING",    mode = "REQUIRED", description = "pipeline_failure, policy_violation, etc." },
    { name = "occurred_at",       type = "TIMESTAMP", mode = "REQUIRED", description = "When the event occurred (from envelope)" },
    { name = "source",            type = "STRING",    mode = "REQUIRED", description = "Publisher identity" },
    { name = "context",           type = "JSON",      mode = "NULLABLE", description = "Full context object from event envelope" },
    { name = "decision",          type = "STRING",    mode = "REQUIRED", description = "NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE" },
    { name = "decision_executed", type = "BOOLEAN",   mode = "REQUIRED", description = "Always false in Phase 0 (shadow mode)" },
    { name = "rationale",         type = "STRING",    mode = "NULLABLE", description = "Human-readable explanation of the decision" },
    { name = "policy_refs",       type = "JSON",      mode = "NULLABLE", description = "NIST/ISO/IMO control references" },
    { name = "mode",              type = "STRING",    mode = "REQUIRED", description = "shadow (Phase 0), advisory, enforce (future)" },
    { name = "agentops_trace_id", type = "STRING",    mode = "NULLABLE", description = "AgentOps trace ID (if enabled)" },
    { name = "processed_at",      type = "TIMESTAMP", mode = "REQUIRED", description = "When the runtime-agent processed the event" },
  ])
}


###########################
# GCS: cogniops-config (live-updatable config store)
###########################
resource "google_storage_bucket" "cogniops_config" {
  name          = "${var.project_id}-cogniops-config"
  location      = var.bucket_location
  force_destroy = false

  versioning { enabled = true }

  uniform_bucket_level_access = true
}

# runtime-agent-sa needs objectViewer to poll config from GCS
resource "google_storage_bucket_iam_member" "runtime_agent_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime_agent.email}"
}

# gha-app SA needs objectAdmin to upload/list bundles and config from CI
resource "google_storage_bucket_iam_member" "gha_app_config_writer" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gha_app.email}"
}


###########################
# Secret Manager: runtime-agent secrets
###########################
resource "google_secret_manager_secret" "runtime_github_token" {
  secret_id = "runtime-agent-github-token"
  replication {
    auto {}
  }
  depends_on = [
    google_project_service.secretmanager,
    google_project_iam_member.runtime_agent_secret_accessor,
    google_service_account_iam_member.infra_can_actas_runtime_agent,
  ]
}

resource "google_secret_manager_secret_version" "runtime_github_token_initial" {
  secret      = google_secret_manager_secret.runtime_github_token.id
  secret_data = "REPLACE_ME"  # Placeholder — update via GCP Console or gcloud

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "runtime_agentops_key" {
  secret_id = "runtime-agent-agentops-key"
  replication {
    auto {}
  }
  depends_on = [
    google_project_service.secretmanager,
    google_project_iam_member.runtime_agent_secret_accessor,
    google_service_account_iam_member.infra_can_actas_runtime_agent,
  ]
}

resource "google_secret_manager_secret_version" "runtime_agentops_key_initial" {
  secret      = google_secret_manager_secret.runtime_agentops_key.id
  secret_data = "REPLACE_ME"  # Placeholder — update via GCP Console or gcloud

  lifecycle {
    ignore_changes = [secret_data]
  }
}


###########################
# OPA Server (Cloud Run) — custom image with embedded Rego policies
###########################
resource "google_service_account" "opa" {
  account_id   = "opa-server-sa"
  display_name = "OPA Server (Cloud Run)"
}

# OPA SA needs objectViewer to poll bundles from GCS
resource "google_storage_bucket_iam_member" "opa_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.opa.email}"

  depends_on = [google_project_service.services]
}

# Allow gha-infra SA to act as opa-server-sa (Terraform deployments)
resource "google_service_account_iam_member" "infra_can_actas_opa" {
  service_account_id = google_service_account.opa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service" "opa" {
  name     = "opa-server"
  location = var.region

  template {
    service_account = google_service_account.opa.email

    containers {
      image   = var.opa_image
      command = ["./opa"]
      args = [
        "run", "--server", "--addr=:8181",
        "--set=decision_logs.console=true",
        "/policies/",
      ]
      ports { container_port = 8181 }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
    }

    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }
  }

  # IAM auth (runtime-agent-sa has run.invoker) provides access control.
  # ingress=all because Cloud Run-to-Cloud Run with ingress=internal
  # does not reliably work without a VPC connector.
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.services,
    google_service_account_iam_member.infra_can_actas_opa,
    google_storage_bucket_iam_member.opa_config_reader,
  ]

  # CI/CD deploys the real image; Terraform must not revert to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# runtime-agent-sa can invoke OPA service
resource "google_cloud_run_v2_service_iam_member" "runtime_agent_opa_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.opa.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime_agent.email}"
}


###########################
# Cloud Run v2: runtime-agent
###########################
resource "google_cloud_run_v2_service" "runtime_agent" {
  name     = "runtime-agent"
  location = var.region

  template {
    service_account = google_service_account.runtime_agent.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.runtime_agent_image

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
        name  = "BIGQUERY_TABLE"
        value = "runtime_decisions"
      }
      env {
        name  = "AGENTOPS_ENABLED"
        value = "false"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "COGNIOPS_MODE"
        value = "shadow"
      }
      env {
        name  = "COGNIOPS_MODEL"
        value = "gemini-2.5-flash"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "METRICS_INGEST_URL"
        value = ""  # Set after ingest function is deployed
      }
      env {
        name  = "COMMIT_SHA"
        value = "managed-by-ci"  # Overridden at deploy time
      }
      env {
        name  = "OPA_URL"
        value = google_cloud_run_v2_service.opa.uri
      }
      env {
        name  = "CONFIG_BUCKET"
        value = google_storage_bucket.cogniops_config.name
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
      env {
        name = "AGENTOPS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.runtime_agentops_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.services,
    google_project_service.pubsub,
    google_secret_manager_secret.runtime_github_token,
    google_secret_manager_secret.runtime_agentops_key,
    google_service_account_iam_member.infra_can_actas_runtime_agent,
    google_service_account_iam_member.app_can_actas_runtime_agent,
    google_project_iam_member.runtime_agent_log_writer,
    google_project_iam_member.runtime_agent_metric_writer,
    google_bigquery_dataset_iam_member.runtime_agent_bq_writer,
    google_project_iam_member.runtime_agent_secret_accessor,
    google_project_iam_member.runtime_agent_ar_reader,
  ]

  # CI/CD deploys the real image; Terraform must not revert to the placeholder.
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# runtime-agent-sa gets roles/run.invoker on runtime-agent (self-invoke for Pub/Sub push)
resource "google_cloud_run_v2_service_iam_member" "runtime_agent_self_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.runtime_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime_agent.email}"
}

# gha-app SA needs roles/run.invoker on runtime-agent (CI smoke tests)
resource "google_cloud_run_v2_service_iam_member" "gha_app_runtime_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.runtime_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gha_app.email}"
}


###########################
# Outputs
###########################
output "runtime_agent_sa_email" {
  description = "Email of the runtime-agent service account."
  value       = google_service_account.runtime_agent.email
}

output "runtime_agent_url" {
  description = "URL of the runtime-agent Cloud Run service."
  value       = google_cloud_run_v2_service.runtime_agent.uri
}

output "runtime_events_topic" {
  description = "Pub/Sub topic name for runtime events."
  value       = google_pubsub_topic.runtime_events.name
}

output "runtime_events_dlq_topic" {
  description = "Pub/Sub DLQ topic name for failed runtime events."
  value       = google_pubsub_topic.runtime_events_dlq.name
}

output "opa_server_url" {
  description = "URL of the OPA Cloud Run service."
  value       = google_cloud_run_v2_service.opa.uri
}

output "cogniops_config_bucket" {
  description = "GCS bucket name for OPA bundles and config YAML."
  value       = google_storage_bucket.cogniops_config.name
}
