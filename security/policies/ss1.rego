package app.policy

# Baseline OPA guardrails for SS1. These rules validate the Cloud Run
# deployment inputs coming from the pipeline: enforce prod-only env,
# immutable image tags, and explicit CPU/memory bounds.

deny[msg] {
  not input.service
  msg := "service name is required"
}

deny[msg] {
  not startswith(input.service, "secure-")
  msg := sprintf("service %v must use secure-* naming", [input.service])
}

deny[msg] {
  not input.region
  msg := "region is required"
}

deny[msg] {
  not input.env
  msg := "environment must be provided"
}

deny[msg] {
  input.env != "prod"
  msg := sprintf("environment %v is not allowed (prod only)", [input.env])
}

deny[msg] {
  input.allowed_regions
  not input.region == input.allowed_regions[_]
  msg := sprintf("region %v not in allowed_regions", [input.region])
}

deny[msg] {
  not input.image_tag
  msg := "image tag is missing"
}

deny[msg] {
  input.image_tag == "latest"
  msg := "mutable tag 'latest' is forbidden"
}

deny[msg] {
  not input.limits.memory
  msg := "memory limit must be set"
}

deny[msg] {
  not re_match("^[0-9]+Mi$", input.limits.memory)
  msg := sprintf("memory limit must be an Mi suffix, got %v", [input.limits.memory])
}

deny[msg] {
  to_number(replace(input.limits.memory, "Mi", "")) < 512
  msg := sprintf("memory limit too low: %v (min 512Mi)", [input.limits.memory])
}

deny[msg] {
  not input.limits.cpu
  msg := "cpu limit must be set"
}

deny[msg] {
  not is_number(input.limits.cpu)
  msg := sprintf("cpu must be numeric, got %v", [input.limits.cpu])
}

deny[msg] {
  input.limits.cpu > 2
  msg := sprintf("cpu limit too high for baseline: %v (max 2)", [input.limits.cpu])
}

deny[msg] {
  input.allowed_public
  input.allow_unauthenticated != input.allowed_public
  msg := "allow_unauthenticated does not match allowed_public policy"
}

deny[msg] {
  input.allowed_ingress
  not input.ingress == input.allowed_ingress[_]
  msg := sprintf("ingress mode %v not in allowed list", [input.ingress])
}

deny[msg] {
  input.service_account
  input.allowed_service_accounts
  not input.service_account == input.allowed_service_accounts[_]
  msg := sprintf("service account %v not in allowed list", [input.service_account])
}

deny[msg] {
  input.allowed_registry_prefix
  input.image_repo
  not startswith(input.image_repo, input.allowed_registry_prefix)
  msg := sprintf("image repo %v not allowed (must start with %v)", [input.image_repo, input.allowed_registry_prefix])
}
