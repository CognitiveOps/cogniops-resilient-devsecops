variable "project_id" {}
variable "region"        { default = "europe-west1" }
variable "repo_location" { default = "europe" }     # για Artifact Registry
variable "github_repo"   {}                         # "org/repo"
variable "bucket_location" { default = "EU" }       # GCS: "EU" (multi-region) ή π.χ. "europe-west1"
