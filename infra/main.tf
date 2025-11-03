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
    google-beta = { source = "hashicorp/google-beta", version = "~> 5.37" }
    archive     = { source = "hashicorp/archive",     version = "~> 2.4" }
    time        = { source = "hashicorp/time",        version = "~> 0.9" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
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
# BigQuery (dataset + table)
#############################
resource "google_bigquery_dataset" "metrics" {
  dataset_id                 = "agent_metrics"
  location                   = var.bigquery_location
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "s1_runs" {
  dataset_id = google_bigquery_dataset.metrics.dataset_id
  table_id   = "s1_pipeline_runs"

  time_partitioning {
     type = "DAY" 
     field = "ended_at" 
    }

  clustering = ["status", "service"]

  schema = jsonencode([
    { name = "run_id",       type = "STRING",    mode = "REQUIRED" },
    { name = "commit_sha",   type = "STRING",    mode = "REQUIRED" },
    { name = "scenario_id",  type = "STRING",    mode = "NULLABLE" },
    { name = "branch",       type = "STRING",    mode = "NULLABLE" },
    { name = "env",          type = "STRING",    mode = "REQUIRED" },
    { name = "service",      type = "STRING",    mode = "REQUIRED" },
    { name = "started_at",   type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "ended_at",     type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "duration_sec", type = "FLOAT",     mode = "REQUIRED" },
    { name = "status",       type = "STRING",    mode = "REQUIRED" },
    { name = "tests_total",  type = "INTEGER",   mode = "NULLABLE" },
    { name = "tests_failed", type = "INTEGER",   mode = "NULLABLE" },
    { name = "inserted_at",  type = "TIMESTAMP", mode = "NULLABLE" } 
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

# Runtime SA -> writers
resource "google_project_iam_member" "run_exec_writers" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter"])
  project  = var.project_id
  role     = each.key
  member   = "serviceAccount:${google_service_account.run_exec.email}"
}

# App CI can view logs (optional but handy for diagnostics in CI)
resource "google_project_iam_member" "app_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_service_account" "cf_ingest" {
  account_id   = "cf-ingest"
  display_name = "Cloud Functions (Gen2) - Metrics Ingest"
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

  # Bind only this repository; add ref filter if needed
  attribute_condition = "attribute.repository == \"${var.github_repo}\""
}

# Allow GitHub principal to impersonate the SAs (WIF)
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

# Infra SA (Terraform runner) — has broad admin permissions for bootstrapping.
# You can later reduce privileges if you split infra responsibilities.
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

# App CI — minimal roles to build/push images and deploy to Cloud Run.
resource "google_project_iam_member" "app_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/run.developer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gha_app.email}"
}

# Cloud Run runtime SA — needs to pull container images from Artifact Registry.
resource "google_project_iam_member" "run_exec_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.run_exec.email}"
}

# Token minting (for impersonation / ID token generation)
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

# Cloud Functions (Gen2) service agent must be able to deploy Cloud Run services.
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
# --- ACT-AS bindings (roles/iam.serviceAccountUser) ---

# Allow Infra SA (Terraform runner) to "act as" the Cloud Run runtime SA.
resource "google_service_account_iam_member" "infra_can_actas_run_exec" {
  service_account_id = google_service_account.run_exec.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

# Allow App CI to "act as" the Cloud Run runtime SA (for deploy actions).
resource "google_service_account_iam_member" "app_can_actas_run_exec" {
  service_account_id = google_service_account.run_exec.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}

# Allow Infra SA (Terraform runner) to act as the Cloud Function SA (cf-ingest).
resource "google_service_account_iam_member" "infra_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}

# Optional — if Terraform is executed via a bootstrap SA, allow it too.
resource "google_service_account_iam_member" "bootstrap_can_actas_cf_ingest" {
  count              = var.bootstrap_sa_email != "" ? 1 : 0
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.bootstrap_sa_email}"
}

# Allow Cloud Functions internal agent to impersonate cf-ingest.
resource "google_service_account_iam_member" "gcf_admin_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

# Allow Serverless runtime (Cloud Run’s serverless-robot-prod) to impersonate cf-ingest.
resource "google_service_account_iam_member" "serverless_can_actas_cf_ingest" {
  service_account_id = google_service_account.cf_ingest.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.current.number}@serverless-robot-prod.iam.gserviceaccount.com"
}

# Allow Infra SA to act as the default Compute Engine SA (for CF update transition)
resource "google_service_account_iam_member" "infra_can_actas_default_compute" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.gha_infra.email}"
}


########################
# Cloud Run (v2)
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
      ports { container_port = 8080 }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  # Allow traffic from everywhere (you still control auth via IAM)
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.services]
}

# Public access toggle: roles/run.invoker to allUsers
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.cloud_run_public ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

###############################
# Cloud Functions Gen2 (ingest)
###############################
resource "google_storage_bucket" "src" {
  name                        = "${var.project_id}-fn-src"
  location                    = var.bucket_location
  uniform_bucket_level_access = true
}

# Bootstrap SA & CI have object access (to upload function zip)
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

resource "google_storage_bucket_iam_member" "src_uploader_view" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.bootstrap_sa_email}"
}

# Builders/readers (CF & Cloud Build)
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

data "archive_file" "ingest_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/ingest"
  output_path = "${path.module}/.tf-build/ingest.zip"
}

resource "google_storage_bucket_object" "ingest_object" {
  name   = "ingest-${data.archive_file.ingest_zip.output_md5}.zip"
  bucket = google_storage_bucket.src.name
  source = data.archive_file.ingest_zip.output_path

  depends_on = [
    google_storage_bucket_iam_member.src_uploader_admin,
    google_storage_bucket_iam_member.src_uploader_view,
  ]
}
resource "google_cloudfunctions2_function" "ingest" {
  name     = "s1-metrics-ingest"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "ingest"
    source {
      storage_source {
        bucket = google_storage_bucket.src.name
        object = google_storage_bucket_object.ingest_object.name
      }
    }
  }

  service_config {
    service_account_email = google_service_account.cf_ingest.email
    max_instance_count    = 1
    available_memory      = "256M"
    ingress_settings      = "ALLOW_ALL" # Public ingress (auth still enforced via IAM)
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

# CF Gen2 IAM: Invoker (private by default)
resource "google_cloudfunctions2_function_iam_member" "ingest_invoker_app" {
  count              = var.cf_ingest_public ? 0 : 1
  project            = var.project_id
  location           = var.region
  cloud_function     = google_cloudfunctions2_function.ingest.name
  role               = "roles/cloudfunctions.invoker"
  member             = "serviceAccount:${google_service_account.gha_app.email}"
}

# Optional public toggle for ingest (rare; prefer private)
resource "google_cloudfunctions2_function_iam_member" "ingest_invoker_public" {
  count              = var.cf_ingest_public ? 1 : 0
  project            = var.project_id
  location           = var.region
  cloud_function     = google_cloudfunctions2_function.ingest.name
  role               = "roles/cloudfunctions.invoker"
  member             = "allUsers"
}

############
# Outputs
############
output "workload_identity_provider_name" { value = google_iam_workload_identity_pool_provider.provider.name }
output "gha_infra_sa_email"             { value = google_service_account.gha_infra.email }
output "gha_app_sa_email"               { value = google_service_account.gha_app.email }
output "run_exec_sa_email"              { value = google_service_account.run_exec.email }

# Cloud Run service URL (handy for health-checks)
output "cloud_run_service_url" {
  value       = "https://${google_cloud_run_v2_service.app.name}-${var.region}.a.run.app"
  description = "Public URL of the Cloud Run service (hostname pattern)."
}

# CF Gen2 correct HTTPS URI (from provider attribute)
output "metrics_function_url" {
  value       = google_cloudfunctions2_function.ingest.service_config[0].uri
  description = "HTTP trigger URL for the ingest function (use ID token if private)."
}
