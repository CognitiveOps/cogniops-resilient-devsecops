# --------------------------------------------------------------------------------
# Terraform Variables for GCP Infrastructure (CogniOps)
# These variables are populated from GitHub Actions environment variables.
# --------------------------------------------------------------------------------

# The Google Cloud Project ID where all resources will be created.
variable "project_id" {
  description = "GCP Project ID (e.g., cogent-wall-445012-h5)"
  type        = string
}

# The GCP region used for regional services like Cloud Run and Cloud Functions.
variable "region" {
  description = "Default GCP region for regional services (e.g., europe-west1)"
  type        = string
  default     = "europe-west1"
}

# Artifact Registry location (multi-region prefix, e.g. europe, us, asia)
variable "repo_location" {
  description = "Artifact Registry location prefix (e.g., europe)"
  type        = string
  default     = "europe"
}

# Multi-region or regional location for GCS buckets
variable "bucket_location" {
  description = "GCS bucket location (e.g., EU for multi-region or europe-west1 for regional)"
  type        = string
  default     = "EU"
}

# BigQuery dataset location (multi-region recommended)
variable "bigquery_location" {
  description = "BigQuery dataset location (e.g., EU or US)"
  type        = string
  default     = "EU"
}

# GitHub repository identifier, used in WIF trust (e.g. CognitiveOps/cogniops-resilient-devsecops)
variable "github_repo" {
  description = "GitHub repository identifier (org/repo) for Workload Identity Federation trust"
  type        = string
}

# Service Account used for initial Terraform bootstrap (with JSON key auth)
variable "bootstrap_sa_email" {
  description = "Email of the Service Account used by Terraform (bootstrap/apply)"
  type        = string
}

# Runtime agent container image
variable "runtime_agent_image" {
  description = "Full container image URI for the runtime-agent (set by CI/CD)"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

# Security compliance agent container image
variable "compliance_agent_image" {
  description = "Full container image URI for the security-compliance-agent (set by CI/CD)"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

# Scenario toggles
variable "cloud_run_public" {
  type        = bool
  default     = true
  description = "Public access to Cloud Run service (S1 baseline = true)."
}

# Whether the generic scenario-runs ingest CF (S2+) is public
variable "scenario_runs_public" {
  type        = bool
  default     = true
  description = "Whether to make the generic scenario-runs ingest Cloud Function public."
}
