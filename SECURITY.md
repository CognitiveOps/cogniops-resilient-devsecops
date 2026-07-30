# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.0-alpha | ✅ Current release |
| earlier commits | ❌ No support |

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Instead, email `security@cognitiveops.example` with:

- A description of the issue
- Steps to reproduce (if applicable)
- Affected files/components
- Suggested remediation (optional)

We will respond within 5 business days.

## Security architecture

- The runtime agent runs with a bounded action surface: `NO_OP`, `BLOCK`,
  `ROLLBACK`, `QUARANTINE`, `ESCALATE`.
- OPA policies enforce mode and severity constraints before any action is
  executed.
- PQC validation uses ML-DSA (FIPS 204) via liboqs for S4/SS2 scenarios.
- No secrets are committed; use environment variables or GCP Secret Manager.
