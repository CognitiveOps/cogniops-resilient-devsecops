package app.policy

# SS1 OPA guardrails (Rego v1)
# Input contract (from your workflow):
# input = {
#   service, region, env, image_tag,
#   limits: {cpu, memory},
#   allow_unauthenticated,   # ACTUAL deploy intent
#   allowed_public,          # POLICY allowance (usually false)
#   ingress, allowed_ingress,
#   service_account, allowed_service_accounts,
#   allowed_regions,
#   allowed_registry_prefix, image_repo
# }

deny contains "service name is required" if { not input.service }

deny contains sprintf("service %v must use secure-* naming", [input.service]) if {
  input.service
  not startswith(input.service, "secure-")
}

deny contains "region is required" if { not input.region }
deny contains "environment must be provided" if { not input.env }

deny contains sprintf("environment %v is not allowed (prod only)", [input.env]) if {
  input.env
  input.env != "prod"
}

# ---------- Allow-lists ----------
deny contains sprintf("region %v not in allowed_regions", [input.region]) if {
  input.region
  input.allowed_regions != null
  count(input.allowed_regions) > 0
  not region_allowed
}

region_allowed if {
  some r
  r := input.allowed_regions[_]
  input.region == r
}

deny contains sprintf("service account %v not in allowed list", [input.service_account]) if {
  input.service_account
  input.allowed_service_accounts != null
  count(input.allowed_service_accounts) > 0
  not sa_allowed
}

sa_allowed if {
  some sa
  sa := input.allowed_service_accounts[_]
  input.service_account == sa
}

deny contains sprintf("ingress mode %v not in allowed list", [input.ingress]) if {
  input.ingress
  input.allowed_ingress != null
  count(input.allowed_ingress) > 0
  not ingress_allowed
}

ingress_allowed if {
  some ing
  ing := input.allowed_ingress[_]
  input.ingress == ing
}

# ---------- Artifact immutability / provenance ----------
deny contains "image tag is missing" if { not input.image_tag }

deny contains "mutable tag 'latest' is forbidden" if {
  input.image_tag == "latest"
}

deny contains sprintf("image repo %v not allowed (must start with %v)", [input.image_repo, input.allowed_registry_prefix]) if {
  input.allowed_registry_prefix
  input.image_repo
  not startswith(input.image_repo, input.allowed_registry_prefix)
}

# ---------- Resource bounds ----------
deny contains "memory limit must be set" if { not input.limits.memory }

deny contains sprintf("memory limit must be an Mi suffix, got %v", [input.limits.memory]) if {
  input.limits.memory
  not regex.match("^[0-9]+Mi$", input.limits.memory)
}

deny contains sprintf("memory limit too low: %v (min 512Mi)", [input.limits.memory]) if {
  regex.match("^[0-9]+Mi$", input.limits.memory)
  to_number(replace(input.limits.memory, "Mi", "")) < 512
}

deny contains "cpu limit must be set" if { not input.limits.cpu }

deny contains sprintf("cpu must be numeric, got %v", [input.limits.cpu]) if {
  input.limits.cpu
  not is_number(input.limits.cpu)
}

deny contains sprintf("cpu limit too high for baseline: %v (max 2)", [input.limits.cpu]) if {
  is_number(input.limits.cpu)
  input.limits.cpu > 2
}

# ---------- Public access policy (the key fix) ----------
# If allowed_public is provided (true/false), then the ACTUAL intent must match.
deny contains sprintf(
  "public access mismatch: allow_unauthenticated=%v but policy allows public=%v",
  [input.allow_unauthenticated, input.allowed_public]
) if {
  input.allowed_public != null
  input.allow_unauthenticated != input.allowed_public
}
