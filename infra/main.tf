/*
    Required variables:
        - var.project_id            : GCP project ID
        - var.region                : GCP region (e.g. "europe-west1")
        - var.repo_location         : Artifact Registry location (e.g. "europe")
        - var.bucket_location       : GCS bucket location (e.g. "EU" or "europe-west1")
        - var.bigquery_location     : BigQuery location (e.g. "EU")
        - var.github_repo           : "org/repo" used in WIF binding
        - var.bootstrap_sa_email    : SA that runs Terraform (bootstrap/apply)
*/

data "google_project" "current" {}

terraform {
  required_version = ">= 1.6"
  required_providers {
    google      = { source = "hashicorp/google",      version = "~> 5.37" }
    archive     = { source = "hashicorp/archive",     version = "~> 2.4" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}


#############################
# Enable Required GCP APIs
#############################
resource "google_project_service" "services" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "eventarc.googleapis.com",
    "bigquery.googleapis.com",
    "iamcredentials.googleapis.com",
    "iam.googleapis.com",
    "sts.googleapis.com",
    "logging.googleapis.com",
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = true
}

#############################
# Artifact Registry (Docker)
#############################
resource "google_artifact_registry_repository" "docker" {
  location      = var.repo_location
  repository_id = "apps"
  format        = "DOCKER"
  description   = "Container registry for apps"
}

#############################
# BigQuery (dataset + tables)
#############################
resource "google_bigquery_dataset" "metrics" {
  dataset_id                 = "agent_metrics"
  location                   = var.bigquery_location
  delete_contents_on_destroy = false
}

# S1-only table (CI/CD baseline)
resource "google_bigquery_table" "s1_runs" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "s1_pipeline_runs"

  time_partitioning {
    type  = "DAY"
    field = "ended_ts"
  }

  clustering = ["status", "service"]

  schema = jsonencode([
    { name = "run_id",        type = "STRING",    mode = "REQUIRED", description = "GitHub Actions run ID (unique per pipeline run)" },
    { name = "workflow",      type = "STRING",    mode = "NULLABLE", description = "Workflow file name (e.g. s1_ci.yml)" },
    { name = "scenario_id",   type = "STRING",    mode = "NULLABLE", description = "Scenario identifier (e.g. S1)" },
    { name = "branch",        type = "STRING",    mode = "NULLABLE", description = "Git branch where the run executed" },
    { name = "env",           type = "STRING",    mode = "NULLABLE", description = "Logical environment (e.g. prod, cloud-run)" },
    { name = "service",       type = "STRING",    mode = "NULLABLE", description = "Service name (e.g. baseline-app)" },
    { name = "status",        type = "STRING",    mode = "NULLABLE", description = "Final pipeline outcome: success / failure / cancelled" },
    { name = "failure_stage", type = "STRING",    mode = "NULLABLE", description = "Stage where failure occurred (test / deploy / health); null if success" },
    { name = "commit_sha",    type = "STRING",    mode = "REQUIRED", description = "Git commit SHA for this run" },
    { name = "image",         type = "STRING",    mode = "NULLABLE", description = "Container image reference with digest" },
    { name = "tests_total",   type = "INTEGER",   mode = "NULLABLE", description = "Total number of tests in this run" },
    { name = "tests_failed",  type = "INTEGER",   mode = "NULLABLE", description = "Number of failing tests" },
    { name = "commit_ts",     type = "TIMESTAMP", mode = "NULLABLE", description = "Pipeline start time (UTC)" },
    { name = "test_ts",       type = "TIMESTAMP", mode = "NULLABLE", description = "Test stage timestamp (UTC)" },
    { name = "push_ts",       type = "TIMESTAMP", mode = "NULLABLE", description = "Image pushed time (UTC)" },
    { name = "deploy_ts",     type = "TIMESTAMP", mode = "NULLABLE", description = "Deploy finished time (UTC)" },
    { name = "ended_ts",      type = "TIMESTAMP", mode = "NULLABLE", description = "Pipeline end time (UTC)" },
    { name = "ttd_sec",       type = "FLOAT",     mode = "NULLABLE", description = "Time-to-deploy in seconds (commit_ts → ended_ts)" },
    { name = "ingested_at",   type = "TIMESTAMP", mode = "NULLABLE", description = "Row ingestion timestamp (set by ingest function)" },
  ])
}

# Generic runs table for S2+ (flexible JSON)
resource "google_bigquery_table" "runs" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "runs"

  time_partitioning {
    type  = "DAY"
    field = "t_end"
  }

  schema = jsonencode([
    {
      name        = "run_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "GitHub Actions run ID or logical run identifier"
    },
    {
      name        = "scenario_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Scenario identifier (s2, s3, s4, s5, ss1, ss2, etc.)"
    },
    {
      name        = "stage"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Stage name within the scenario (e.g. s2_activate)"
    },
    {
      name        = "mode"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "baseline / shadow / enforce"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "success / failed / cancelled"
    },
    {
      name        = "commit_sha"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Git commit SHA for this run"
    },
    {
      name        = "t_start"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "Start timestamp of this stage (UTC)"
    },
    {
      name        = "t_end"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "End timestamp of this stage (UTC)"
    },
    {
      name        = "duration_sec"
      type        = "FLOAT"
      mode        = "NULLABLE"
      description = "Stage duration in seconds (t_end - t_start)"
    },
    {
      name        = "labels"
      type        = "JSON"
      mode        = "NULLABLE"
      description = "Free-form labels (service, edge_device, env, etc.)"
    },
    {
      name        = "metrics"
      type        = "JSON"
      mode        = "NULLABLE"
      description = "Scenario-specific metrics (e.g. tdl_sec, mttd_sec, etc.)"
    },
    {
      name        = "ingested_at"
      type        = "TIMESTAMP"
      mode        = "NULLABLE"
      description = "Row ingestion timestamp (set by ingest function)"
    }
  ])
}

#####################
# Service Accounts
#####################
resource "google_service_account" "gha_infra" {
  account_id   = "gha-infra"
  display_name = "GitHub Actions - Infra (Terraform)"
}

resource "google_service_account" "gha_app" {
  account_id   = "gha-app"
  display_name = "GitHub Actions - App CI"
}

resource "google_service_account" "run_exec" {
  account_id   = "run-exec"
  display_name = "Cloud Run runtime SA"
}

resource "google_service_account" "cf_ingest" {
  account_id   = "cf-ingest"
  display_name = "Cloud Functions (Gen2) - Metrics Ingest"
}

# Cloud Functions Gen2 deployments can default to the project Compute Engine default
# service account during build/update operations. Ensure the infra SA can "actAs"
# that service account to avoid 403 errors during `google_cloudfunctions2_function` updates.
resource "google_service_account_iam_member" "infra_can_actas_default_compute" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_project_iam_member" "run_exec_writers" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter"])
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.run_exec.email}"
}

##############################
# Workload Identity Federation
##############################
resource "google_iam_workload_identity_pool" "pool" {
  workload_identity_pool_id = "gha-pool"
  display_name              = "GitHub Pool"
}

resource "google_iam_workload_identity_pool_provider" "provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "attribute.repository == \"${var.github_repo}\""
}

resource "google_service_account_iam_member" "wif_infra" {
  service_account_id = google_service_account.gha_infra.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.pool.name}/attribute.repository/${var.github_repo}"
}

resource "google_service_account_iam_member" "wif_app" {
  service_account_id = google_service_account.gha_app.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.pool.name}/attribute.repository/${var.github_repo}"
}

########################
# IAM Roles to Service Accounts
########################
resource "google_project_iam_member" "infra_roles" {
  for_each = toset([
    "roles/artifactregistry.admin",
    "roles/run.admin",
    "roles/cloudfunctions.admin",
    "roles/bigquery.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/viewer",
    "roles/storage.admin",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_project_iam_member" "app_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/run.developer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_project_iam_member" "run_exec_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.run_exec.email}"
}

resource "google_service_account_iam_member" "app_can_mint_tokens" {
  service_account_id = google_service_account.gha_app.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_service_account_iam_member" "infra_can_mint_tokens" {
  service_account_id = google_service_account.gha_infra.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_project_iam_member" "cf_can_deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

resource "google_bigquery_dataset_iam_member" "cf_ingest_bq_writer" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.cf_ingest.email}"
}


resource "google_service_account_iam_member" "infra_can_actas_run_exec" {
  service_account_id = google_service_account.run_exec.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_service_account_iam_member" "app_can_actas_run_exec" {
  service_account_id = google_service_account.run_exec.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_service_account_iam_member" "infra_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_service_account_iam_member" "bootstrap_can_actas_cf_ingest" {
  count              = var.bootstrap_sa_email != "" ? 1 : 0
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.bootstrap_sa_email}"
}

resource "google_service_account_iam_member" "gcf_admin_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "serverless_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.current.number}@serverless-robot-prod.iam.gserviceaccount.com"
}

########################
# Cloud Run (v2) - baseline-app
########################
resource "google_cloud_run_v2_service" "app" {
  name     = "baseline-app"
  location = var.region

  template {
    service_account = google_service_account.run_exec.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service_iam_member" "baseline_public_invoker" {
  count    = var.cloud_run_public ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

########################
# Cloud Run (v2) - edge-cv-app
########################
resource "google_cloud_run_v2_service" "edge_cv_app" {
  name     = "edge-cv-app"
  location = var.region

  template {
    service_account = google_service_account.run_exec.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service_iam_member" "edge_cv_public_invoker" {
  count    = var.cloud_run_public ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.edge_cv_app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

###############################
# Cloud Functions Gen2 source bucket (used for ingest functions)
###############################
resource "google_storage_bucket" "src" {
  name                        = "${var.project_id}-fn-src"
  location                    = var.bucket_location
  uniform_bucket_level_access = true
}

###############################
# Scenario artifacts bucket (canonical storage for SS2/S3 edge)
###############################
resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-agent-artifacts"
  location                    = var.bucket_location
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "artifacts_app_rw" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_storage_bucket_iam_member" "artifacts_infra_rw" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_storage_bucket_iam_member" "src_uploader_admin" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.bootstrap_sa_email}"
}

resource "google_storage_bucket_iam_member" "tf_state_infra_access" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gha_infra.email}"
}

# resource "google_storage_bucket_iam_member" "src_uploader_view" {
#   bucket = google_storage_bucket.src.name
#   role   = "roles/storage.objectViewer"
#   member = "serviceAccount:${var.bootstrap_sa_email}"
# }

resource "google_storage_bucket_iam_member" "src_cb_read" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

resource "google_storage_bucket_iam_member" "src_cf_read" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}
###############################
# Cloud Functions Gen2 (generic runs ingest)
###############################

# Package the ingest_runs function code into a zip
data "archive_file" "runs_ingest_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/ingest_runs"
  output_path = "${path.module}/.tf-build/ingest-runs.zip"
}

# Upload the packaged zip to the source bucket
resource "google_storage_bucket_object" "runs_ingest_object" {
  name   = "ingest-runs-${data.archive_file.runs_ingest_zip.output_md5}.zip"
  bucket = google_storage_bucket.src.name
  source = data.archive_file.runs_ingest_zip.output_path

  depends_on = [
    google_storage_bucket_iam_member.src_uploader_admin
  ]
}

# Deploy the Cloud Function Gen2 for metrics ingestion (all scenarios)
resource "google_cloudfunctions2_function" "runs_ingest" {
  name     = "scenario-runs-ingest"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "ingest_runs"
    source {
      storage_source {
        bucket = google_storage_bucket.src.name
        object = google_storage_bucket_object.runs_ingest_object.name
      }
    }
  }

  service_config {
    service_account_email = google_service_account.cf_ingest.email
    max_instance_count    = 1
    available_memory      = "256M"
    ingress_settings      = "ALLOW_ALL" # allow external POSTs; IAM still controls access
    environment_variables = {
      BQ_DATASET  = google_bigquery_dataset.metrics.dataset_id
      BQ_TABLE    = google_bigquery_table.runs.table_id
      GCP_PROJECT = var.project_id
    }
  }

  depends_on = [
    google_service_account.cf_ingest,
    google_service_account_iam_member.infra_can_actas_cf_ingest,
    google_service_account_iam_member.gcf_admin_can_actas_cf_ingest,
    google_service_account_iam_member.serverless_can_actas_cf_ingest,
    google_project_iam_member.cf_can_deploy_run,
    google_bigquery_dataset_iam_member.cf_ingest_bq_writer,
  ]
}

# Private invoker (GitHub Actions SA only) – used if scenario_runs_public = false
resource "google_cloudfunctions2_function_iam_member" "runs_ingest_invoker_app" {
  count              = var.scenario_runs_public ? 0 : 1
  project            = var.project_id
  location           = var.region
  cloud_function     = google_cloudfunctions2_function.runs_ingest.name
  role               = "roles/cloudfunctions.invoker"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}

# Optional public invoker (default = true)
resource "google_cloudfunctions2_function_iam_member" "runs_ingest_invoker_public" {
  count              = var.scenario_runs_public ? 1 : 0
  project            = var.project_id
  location           = var.region
  cloud_function     = google_cloudfunctions2_function.runs_ingest.name
  role               = "roles/cloudfunctions.invoker"
  member             = "allUsers"
}


############
# Outputs
############
output "workload_identity_provider_name" {
  value = google_iam_workload_identity_pool_provider.provider.name
}

output "gha_infra_sa_email" {
  value = google_service_account.gha_infra.email
}

output "gha_app_sa_email" {
  value = google_service_account.gha_app.email
}

output "run_exec_sa_email" {
  value = google_service_account.run_exec.email
}

output "agent_artifacts_bucket_name" {
  description = "GCS bucket name for scenario artifacts (SS2/S3 edge)."
  value       = google_storage_bucket.artifacts.name
}

output "cloud_run_service_url" {
  value       = "https://${google_cloud_run_v2_service.app.name}-${var.region}.a.run.app"
  description = "Public URL of the Cloud Run service (hostname pattern)."
}

output "scenario_runs_function_url" {
  value       = google_cloudfunctions2_function.runs_ingest.service_config[0].uri
  description = "HTTP trigger URL for the generic scenario runs ingest function."
}
