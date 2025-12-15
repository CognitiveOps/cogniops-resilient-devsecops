package app.policy

# Baseline OPA guardrails for SS1 (rego v1 syntax). These validate deploy inputs.

deny contains "service name is required" if {
  not input.service
}

deny contains sprintf("service %v must use secure-* naming", [input.service]) if {
  not startswith(input.service, "secure-")
}

deny contains "region is required" if {
  not input.region
}

deny contains "environment must be provided" if {
  not input.env
}

deny contains sprintf("environment %v is not allowed (prod only)", [input.env]) if {
  input.env != "prod"
}

deny contains sprintf("region %v not in allowed_regions", [input.region]) if {
  count(input.allowed_regions) > 0
  not input.region == input.allowed_regions[_]
}

deny contains "image tag is missing" if {
  not input.image_tag
}

deny contains "mutable tag 'latest' is forbidden" if {
  input.image_tag == "latest"
}

deny contains "memory limit must be set" if {
  not input.limits.memory
}

deny contains sprintf("memory limit must be an Mi suffix, got %v", [input.limits.memory]) if {
  input.limits.memory
  not re_match("^[0-9]+Mi$", input.limits.memory)
}

deny contains sprintf("memory limit too low: %v (min 512Mi)", [input.limits.memory]) if {
  re_match("^[0-9]+Mi$", input.limits.memory)
  to_number(replace(input.limits.memory, "Mi", "")) < 512
}

deny contains "cpu limit must be set" if {
  not input.limits.cpu
}

deny contains sprintf("cpu must be numeric, got %v", [input.limits.cpu]) if {
  input.limits.cpu
  not is_number(input.limits.cpu)
}

deny contains sprintf("cpu limit too high for baseline: %v (max 2)", [input.limits.cpu]) if {
  is_number(input.limits.cpu)
  input.limits.cpu > 2
}

deny contains "allow_unauthenticated does not match allowed_public policy" if {
  input.allowed_public != null
  input.allow_unauthenticated != input.allowed_public
}

deny contains sprintf("ingress mode %v not in allowed list", [input.ingress]) if {
  count(input.allowed_ingress) > 0
  not input.ingress == input.allowed_ingress[_]
}

deny contains sprintf("service account %v not in allowed list", [input.service_account]) if {
  count(input.allowed_service_accounts) > 0
  not input.service_account == input.allowed_service_accounts[_]
}

deny contains sprintf("image repo %v not allowed (must start with %v)", [input.image_repo, input.allowed_registry_prefix]) if {
  input.allowed_registry_prefix
  input.image_repo
  not startswith(input.image_repo, input.allowed_registry_prefix)
}
