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
        time        = { source = "hashicorp/time",    version = "~> 0.9" } 
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

# --------------------------------------------------------------------------------
# Enable required Google Cloud APIs
# --------------------------------------------------------------------------------
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

# --------------------------------------------------------------------------------
# Artifact Registry (Docker)
# --------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "docker" {
    location      = var.repo_location
    repository_id = "apps"
    format        = "DOCKER"
    description   = "Container registry for apps"
}

# --------------------------------------------------------------------------------
# BigQuery (dataset + table)
# --------------------------------------------------------------------------------
resource "google_bigquery_dataset" "metrics" {
    dataset_id                 = "agent_metrics"
    location                   = var.bigquery_location   # e.g. "EU"
    delete_contents_on_destroy = false
}

resource "google_bigquery_table" "s1_runs" {
    dataset_id = google_bigquery_dataset.metrics.dataset_id
    table_id   = "s1_pipeline_runs"

    time_partitioning {
        type  = "DAY"
        field = "ended_at"
    }

    clustering = ["status", "service"]

    schema = jsonencode([
        {name="run_id",      type="STRING",    mode="REQUIRED"},
        {name="commit_sha",  type="STRING",    mode="REQUIRED"},
        {name="started_at",  type="TIMESTAMP", mode="REQUIRED"},
        {name="ended_at",    type="TIMESTAMP", mode="REQUIRED"},
        {name="duration_sec",type="FLOAT",     mode="REQUIRED"},
        {name="status",      type="STRING",    mode="REQUIRED"},
        {name="tests_total", type="INTEGER",   mode="NULLABLE"},
        {name="tests_failed",type="INTEGER",   mode="NULLABLE"},
        {name="service",     type="STRING",    mode="REQUIRED"},
        {name="env",         type="STRING",    mode="REQUIRED"},
    ])
}

# --------------------------------------------------------------------------------
# Service Accounts
# --------------------------------------------------------------------------------
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

# --------------------------------------------------------------------------------
# Workload Identity Federation (OIDC) for GitHub Actions
# --------------------------------------------------------------------------------
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

# Bind repo → SAs
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

# --------------------------------------------------------------------------------
# IAM roles to SAs
# --------------------------------------------------------------------------------
resource "google_project_iam_member" "infra_roles" {
    for_each = toset([
        "roles/artifactregistry.admin",
        "roles/run.admin",
        "roles/cloudfunctions.admin",
        "roles/bigquery.admin",
        "roles/iam.serviceAccountAdmin",
        "roles/iam.workloadIdentityPoolAdmin",
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

# CF SA can deploy to Run
resource "google_project_iam_member" "cf_can_deploy_run" {
    project = var.project_id
    role    = "roles/run.developer"
    member  = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

# App CI SA can act as runtime SA
resource "google_service_account_iam_member" "app_can_actas_run_exec" {
    service_account_id = google_service_account.run_exec.name
    role               = "roles/iam.serviceAccountUser"
    member             = "serviceAccount:${google_service_account.gha_app.email}"
}

# --------------------------------------------------------------------------------
# Cloud Run (bootstrap)
# --------------------------------------------------------------------------------
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

    ingress    = "INGRESS_TRAFFIC_ALL"
    depends_on = [google_project_service.services]
}

# --------------------------------------------------------------------------------
# Cloud Functions Gen2 + source bucket
# --------------------------------------------------------------------------------
resource "google_storage_bucket" "src" {
    name     = "${var.project_id}-fn-src"
    location = var.bucket_location
    uniform_bucket_level_access = true
}

# Bootstrap SA needs upload/get on objects for TF bucket_object
resource "google_storage_bucket_iam_member" "src_uploader_admin" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.bootstrap_sa_email}"
}

# # (Optional but helpful) project-level admin for bootstrap SA while bootstrapping
# resource "google_project_iam_member" "bootstrap_storage_admin" {
#   project = var.project_id
#   role    = "roles/storage.admin"
#   member  = "serviceAccount:${var.bootstrap_sa_email}"
# }

resource "google_storage_bucket_iam_member" "src_uploader_view" {
    bucket = google_storage_bucket.src.name
    role   = "roles/storage.objectViewer"
    member = "serviceAccount:${var.bootstrap_sa_email}"
}

# Bucket IAM for builders/readers (CF & Cloud Build)
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

# Wait for IAM propagation (45–60s is safer than 20)
# resource "time_sleep" "wait_iam" {
#   depends_on = [
#     google_storage_bucket_iam_member.src_uploader_admin,
#     google_storage_bucket_iam_member.src_uploader_view,
#     google_storage_bucket_iam_member.src_cb_read,
#     google_storage_bucket_iam_member.src_cf_read,
#     # google_project_iam_member.bootstrap_storage_admin,
#   ]
#   create_duration = "90s"
# }

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
        # time_sleep.wait_iam,
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
        max_instance_count = 1
        available_memory   = "256M"
        ingress_settings   = "ALLOW_ALL"
    }

    depends_on = [
        google_project_service.services,
        google_project_iam_member.cf_can_deploy_run
    ]
}

# --------------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------------
output "workload_identity_provider_name" { value = google_iam_workload_identity_pool_provider.provider.name }
output "gha_infra_sa_email"             { value = google_service_account.gha_infra.email }
output "gha_app_sa_email"               { value = google_service_account.gha_app.email }
output "run_exec_sa_email"              { value = google_service_account.run_exec.email }
output "metrics_function_url" {
    value       = "https://${var.region}-${var.project_id}.cloudfunctions.net/${google_cloudfunctions2_function.ingest.name}"
    description = "HTTP trigger URL (ensure IAM invoker as needed)."
}
