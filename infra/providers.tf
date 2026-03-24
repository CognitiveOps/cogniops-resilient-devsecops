# Additional providers (additive only — main.tf providers are immutable)

terraform {
  required_providers {
    time = { source = "hashicorp/time", version = "~> 0.11" }
  }
}
