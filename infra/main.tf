/*
    Required variables (must be defined in variables.tf or via CLI/TFVARS):
        - var.project_id   : GCP project ID to provision resources into
        - var.region       : GCP region (used for regional services like Cloud Run / Functions)
        - var.repo_location: Location for Artifact Registry and storage buckets (e.g. "eu", "us")
        - var.github_repo  : GitHub repository identifier used for Workload Identity (e.g. "org/repo")
*/

data "google_project" "current" {}
terraform {
    required_version = ">= 1.6"
    required_providers {
        google      = { source = "hashicorp/google",      version = "~> 5.37" }
        google-beta = { source = "hashicorp/google-beta", version = "~> 5.37" }
        archive     = { source = "hashicorp/archive",     version = "~> 2.4" }
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
# Enable required Google Cloud APIs for this project
# This ensures the services we create below (Artifact Registry, Cloud Run, etc.) are usable
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
  project = var.project_id
  service = each.key
  disable_on_destroy = true
}

# --------------------------------------------------------------------------------
# Artifact Registry repository for container images (Docker format)
# repository_id "apps" — used by CI to push built container images
# --------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "docker" {
    location      = var.repo_location
    repository_id = "apps"
    format        = "DOCKER"
    description   = "Container registry for apps"
}

# --------------------------------------------------------------------------------
# BigQuery Dataset and Table
# - dataset: partitioned by day (EU location here)
# - table: partition by ended_at and cluster on status/service for query performance
# --------------------------------------------------------------------------------
resource "google_bigquery_dataset" "metrics" {
    dataset_id                 = "agent_metrics"
    location                   = var.repo_location
    delete_contents_on_destroy = false  # preserve data on destroy unless explicitly removed
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
        {name="run_id",      type="STRING",  mode="REQUIRED"},
        {name="commit_sha",  type="STRING",  mode="REQUIRED"},
        {name="started_at",  type="TIMESTAMP", mode="REQUIRED"},
        {name="ended_at",    type="TIMESTAMP", mode="REQUIRED"},
        {name="duration_sec",type="FLOAT",   mode="REQUIRED"},
        {name="status",      type="STRING",  mode="REQUIRED"},
        {name="tests_total", type="INTEGER", mode="NULLABLE"},
        {name="tests_failed",type="INTEGER", mode="NULLABLE"},
        {name="service",     type="STRING",  mode="REQUIRED"},
        {name="env",         type="STRING",  mode="REQUIRED"},
    ])
}

# --------------------------------------------------------------------------------
# Service Accounts
# - gha_infra: used by GitHub Actions to run Terraform and provisioning tasks
# - gha_app  : used by GitHub Actions for app CI (build/push)
# - run_exec : runtime identity for Cloud Run (service runs as this SA)
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

# Allow the runtime SA to write logs and metrics
resource "google_project_iam_member" "run_exec_writers" {
    for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter"])
    project  = var.project_id
    role     = each.key
    member   = "serviceAccount:${google_service_account.run_exec.email}"
}

# --------------------------------------------------------------------------------
# Workload Identity Federation (WIF) for GitHub Actions (OIDC)
# - creates a Workload Identity Pool and OIDC provider for GitHub Actions tokens
# - attribute_mapping maps assertions from GitHub to Google attributes, used to form principals
# --------------------------------------------------------------------------------
resource "google_iam_workload_identity_pool" "pool" {
    workload_identity_pool_id = "gha-pool"
    display_name              = "GitHub Pool"
}

resource "google_iam_workload_identity_pool_provider" "provider" {
    workload_identity_pool_id          = google_iam_workload_identity_pool.pool.workload_identity_pool_id
    workload_identity_pool_provider_id = "github-provider"
    display_name                       = "GitHub OIDC"

    # GitHub Actions OIDC issuer
    oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

    # Map values from the OIDC token to attributes consumed by iam principals and policies
    attribute_mapping = {
        "google.subject"       = "assertion.sub"
        "attribute.repository" = "assertion.repository" # used to restrict repo => principal
        "attribute.ref"        = "assertion.ref"
    }
}

# --------------------------------------------------------------------------------
# Bind the WIF principal (repository) to the GitHub Actions service accounts
# This allows workflows from var.github_repo to impersonate the GCP service accounts
# member uses principalSet to allow multiple principals (e.g., branches or refs can be filtered)
# --------------------------------------------------------------------------------
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
# IAM roles assigned to service accounts
# - gha_infra: broad admin roles required for provisioning infra (Artifact Registry, Run, CF, BigQuery, SA admin)
# - gha_app  : limited roles for CI to push images and deploy to Cloud Run
# --------------------------------------------------------------------------------
resource "google_project_iam_member" "infra_roles" {
    for_each = toset([
        "roles/artifactregistry.admin",   # manage repositories, cleanup
        "roles/run.admin",
        "roles/cloudfunctions.admin",
        "roles/bigquery.admin",
        "roles/iam.serviceAccountAdmin",
        # Optional: allow Terraform to manage the WIF pool/provider itself
        "roles/iam.workloadIdentityPoolAdmin"
        # The role "roles/iam.workloadIdentityPoolProviderAdmin" is not required unless you need Terraform to manage providers within the WIF pool.
    ])
    project = var.project_id
    role    = each.key
    member  = "serviceAccount:${google_service_account.gha_infra.email}"
}

resource "google_project_iam_member" "app_roles" {
    for_each = toset([
        "roles/artifactregistry.writer",  # push images
        "roles/run.developer",            # deploy Cloud Run services
    ])
    project = var.project_id
    role    = each.key
    member  = "serviceAccount:${google_service_account.gha_app.email}"
}

resource "google_project_iam_member" "cf_can_deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

# Allow the App CI SA to impersonate the Cloud Run runtime SA when deploying
resource "google_service_account_iam_member" "app_can_actas_run_exec" {
    service_account_id = google_service_account.run_exec.name
    role               = "roles/iam.serviceAccountUser"
    member             = "serviceAccount:${google_service_account.gha_app.email}"
}

# --------------------------------------------------------------------------------
# Cloud Run service (bootstrap)
# - A minimal service is created here; CI/CD can replace the image on deploy
# - Runs as google_service_account.run_exec
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
    depends_on = [google_project_service.services] # ensure APIs are enabled
}

# --------------------------------------------------------------------------------
# Cloud Functions (Gen2) related resources
# - Storage bucket to stage function source code
# - Zip archive data + upload object that includes a content hash to force redeploys on changes
# - Cloud Function 2 (Gen2) configured for HTTP; still IAM-protected unless you add an 'allUsers' invoker
# --------------------------------------------------------------------------------
resource "google_storage_bucket" "src" {
  name     = "${var.project_id}-fn-src"
  location = var.repo_location   # use the same location variable as BigQuery and Artifact Registry
  uniform_bucket_level_access = true
}

# Cloud Build SA: <PROJECT_NUMBER>@cloudbuild.gserviceaccount.com
resource "google_storage_bucket_iam_member" "src_cb_read" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

# Cloud Functions Service Agent: service-<PROJECT_NUMBER>@gcf-admin-robot.iam.gserviceaccount.com
resource "google_storage_bucket_iam_member" "src_cf_read" {
  bucket = google_storage_bucket.src.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

data "archive_file" "ingest_zip" {
    type        = "zip"
    source_dir  = "${path.module}/../functions/ingest"   # relative to infra/ directory
    output_path = "${path.module}/.tf-build/ingest.zip"   # local build artifact for upload
}

resource "google_storage_bucket_object" "ingest_object" {
    name   = "ingest-${data.archive_file.ingest_zip.output_md5}.zip"
    bucket = google_storage_bucket.src.name
    source = data.archive_file.ingest_zip.output_path
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

  # MUST wait for APIs + bucket IAM + Run IAM
  depends_on = [
    google_project_service.services,
    google_storage_bucket_iam_member.src_cb_read,
    google_storage_bucket_iam_member.src_cf_read,
    google_project_iam_member.cf_can_deploy_run
  ]
}

# --------------------------------------------------------------------------------
# Outputs (useful for automating GitHub workflow variables and deployments)
# - workload_identity_provider_name: full provider name for GH Workflows to reference
# - *_sa_email: service account emails used by CI and runtime
# - metrics_function_url: public callable URL pattern (useful for wiring GitHub secrets / env)
# --------------------------------------------------------------------------------
output "workload_identity_provider_name" { value = google_iam_workload_identity_pool_provider.provider.resource_name }
output "gha_infra_sa_email"             { value = google_service_account.gha_infra.email }
output "gha_app_sa_email"               { value = google_service_account.gha_app.email }
output "run_exec_sa_email"              { value = google_service_account.run_exec.email }
# NOTE: The URL format for Cloud Functions Gen2 may differ by region and IAM settings.
# For public access, you must grant the 'roles/cloudfunctions.invoker' role to 'allUsers' or the desired principal.
# See: https://cloud.google.com/functions/docs/securing/function-identity
output "metrics_function_url" {
  value = "https://${var.region}-${var.project_id}.cloudfunctions.net/${google_cloudfunctions2_function.ingest.name}"
  description = "Default HTTP trigger URL for Cloud Functions Gen2. The actual URL may differ by region and deployment; verify the deployed URL in the GCP Console. Ensure IAM permissions allow invocation."
}
