"""
security-agent – CogniOps Security Compliance Agent.

Batch/scheduled service that:
  1. Ingests NIST feeds (NVD API v2 + SP 800-53 CPRT)
  2. Diffs against current control-mappings.yaml
  3. Enriches with full control text
  4. Runs ADK LlmAgent for impact assessment
  5. Validates proposal (deterministic)
  6. Stores proposal in GCS + creates GitHub Issue

Endpoints:
  POST /run          – Trigger compliance check (Cloud Scheduler or manual)
  GET  /healthz      – Liveness probe
  GET  /agent/info   – ADK agent metadata

Trigger: Cloud Scheduler HTTP POST to /run (daily or weekly)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.compliance_agent import compliance_agent
from agent.tools.diff_engine import compute_diff, enrich_diff
from agent.tools.nist_feed import ingest_feeds
from agent.tools.proposal_builder import build_proposal
from agent.tools.validator import validate_proposal
from models.schemas import (
    ComplianceProposal,
    DiffReport,
    LastCheckRecord,
    YAMLPatch,
    YAMLPatchEntry,
)

# ── Logging ──────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("security-agent")

# ── Config ───────────────────────────────────────────────────────────

CONFIG_BUCKET = os.getenv("CONFIG_BUCKET", "")
PROPOSALS_BUCKET = os.getenv("PROPOSALS_BUCKET", CONFIG_BUCKET)
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "7"))

# ── FastAPI app ──────────────────────────────────────────────────────

app = FastAPI(
    title="CogniOps Security Compliance Agent",
    description="Automated NIST compliance monitoring (propose-only)",
    version="0.1.0",
)

# ── ADK Runner ───────────────────────────────────────────────────────

runner = InMemoryRunner(agent=compliance_agent, app_name="cogniops_compliance")
runner.auto_create_session = True


# ── GCS Helpers ──────────────────────────────────────────────────────


def _read_gcs_yaml(path: str) -> dict | None:
    """Read and parse YAML from GCS. Returns None on failure."""
    if not CONFIG_BUCKET:
        return None
    try:
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(CONFIG_BUCKET).blob(path)
        return yaml.safe_load(blob.download_as_text())
    except Exception as exc:
        logger.warning("GCS read failed (%s): %s", path, exc)
        return None


def _read_gcs_json(path: str) -> dict | None:
    """Read and parse JSON from GCS. Returns None on failure."""
    if not CONFIG_BUCKET:
        return None
    try:
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(CONFIG_BUCKET).blob(path)
        return json.loads(blob.download_as_text())
    except Exception as exc:
        logger.warning("GCS read failed (%s): %s", path, exc)
        return None


def _write_gcs_json(bucket_name: str, path: str, data: dict) -> bool:
    """Write JSON to GCS. Returns success boolean."""
    if not bucket_name:
        logger.warning("No bucket configured, skipping GCS write for %s", path)
        return False
    try:
        from google.cloud import storage

        client = storage.Client()
        blob = client.bucket(bucket_name).blob(path)
        blob.upload_from_string(
            json.dumps(data, indent=2, default=str),
            content_type="application/json",
        )
        logger.info("Wrote %s to gs://%s", path, bucket_name)
        return True
    except Exception as exc:
        logger.warning("GCS write failed (%s): %s", path, exc)
        return False


def _get_last_check() -> datetime:
    """Get the timestamp of the last successful check from GCS."""
    record = _read_gcs_json("compliance/last_check.json")
    if record:
        try:
            parsed = LastCheckRecord(**record)
            return parsed.timestamp
        except Exception:
            pass
    # Default: look back N days
    return datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)


def _save_last_check() -> None:
    """Save the current timestamp as last check."""
    record = LastCheckRecord(
        timestamp=datetime.now(timezone.utc),
        sources_checked=["NIST_NVD", "NIST_SP800_53"],
    )
    _write_gcs_json(
        CONFIG_BUCKET,
        "compliance/last_check.json",
        record.model_dump(mode="json"),
    )


def _load_current_yaml() -> dict:
    """Load current control-mappings.yaml from GCS or local fallback."""
    # Try GCS first
    data = _read_gcs_yaml("control-mappings/v1.yaml")
    if data and "mappings" in data:
        return data

    # Fallback: load from local file (for testing / initial bootstrap)
    from pathlib import Path

    local = Path(__file__).resolve().parent.parent / "config" / "control-mappings.yaml"
    if local.exists():
        return yaml.safe_load(local.read_text(encoding="utf-8"))

    # Hardcoded minimal fallback
    return {
        "mappings": {
            "BLOCK": [],
            "ROLLBACK": [],
            "QUARANTINE": [],
            "ESCALATE": [],
            "NO_OP": [],
        }
    }


# ── GitHub Issue Creation ────────────────────────────────────────────


def _create_github_issue(proposal: ComplianceProposal) -> str | None:
    """Create a GitHub Issue with the proposal summary. Returns issue URL or None."""
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "")
    if not token or not repo:
        logger.info("GitHub Issue creation skipped (no token/repo configured)")
        return None

    import httpx

    title = f"[Compliance] {proposal.proposal_id}: {len(proposal.diff_report.updated_entries)} updates, {len(proposal.diff_report.new_entries)} new"
    body_parts = [
        f"## Compliance Proposal: `{proposal.proposal_id}`",
        f"**Created**: {proposal.created_at.isoformat()}",
        f"**Confidence**: {proposal.confidence:.0%}",
        f"**Affected Decision Types**: {', '.join(proposal.diff_report.affected_decision_types) or 'none'}",
        "",
        "### Impact Assessment",
        proposal.impact_assessment,
        "",
        "### Proposed YAML Changes",
        "```yaml",
        yaml.dump(
            {
                dt: [e.model_dump(exclude_none=True) for e in entries]
                for dt, entries in proposal.proposed_yaml_patch.updates.items()
            },
            default_flow_style=False,
        ),
        "```",
    ]

    if proposal.proposed_rego_suggestions:
        body_parts.extend(
            [
                "",
                "### OPA Policy Suggestions",
                *[f"- {s}" for s in proposal.proposed_rego_suggestions],
            ]
        )

    body_parts.extend(
        [
            "",
            "---",
            "> This proposal was generated automatically by the CogniOps Security Compliance Agent.",
            "> **Human review is required** before any changes are applied.",
        ]
    )

    body = "\n".join(body_parts)

    try:
        resp = httpx.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": title,
                "body": body,
                "labels": ["compliance", "security-agent", "automated"],
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        issue_url = resp.json().get("html_url", "")
        logger.info("GitHub Issue created: %s", issue_url)
        return issue_url
    except Exception as exc:
        logger.warning("GitHub Issue creation failed: %s", exc)
        return None


# ── Health check ─────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "version": "0.1.0", "agent": "security-compliance"}


@app.get("/agent/info")
async def agent_info():
    """Return ADK agent metadata."""
    try:
        tool_names = [
            t.__name__ if callable(t) else str(t) for t in compliance_agent.tools
        ]
        return {
            "agent_name": compliance_agent.name,
            "model": str(compliance_agent.model),
            "tools": tool_names,
            "status": "loaded",
        }
    except Exception as exc:
        return {"status": "not_loaded", "detail": str(exc)}


# ── Main pipeline endpoint ───────────────────────────────────────────


@app.post("/run")
async def run_compliance_check():
    """Execute the full compliance check pipeline.

    Triggered by Cloud Scheduler (daily/weekly) or manual invocation.

    Pipeline:
      1. Load last check timestamp
      2. Ingest NIST feeds
      3. Load current control-mappings.yaml
      4. Compute diff
      5. Enrich with full control text
      6. Run ADK LlmAgent for impact assessment
      7. Build proposal
      8. Validate proposal
      9. Store in GCS + create GitHub Issue
    """
    t_start = time.monotonic()

    # ── 1. Last check ────────────────────────────────────────────────
    since = _get_last_check()
    logger.info("Starting compliance check (since=%s)", since.isoformat())

    # ── 2. Ingest feeds ──────────────────────────────────────────────
    try:
        feed_entries = await ingest_feeds(since)
    except Exception as exc:
        logger.error("Feed ingestion failed: %s", exc)
        return JSONResponse(
            status_code=200,
            content={"status": "error", "stage": "ingestion", "error": str(exc)},
        )

    if not feed_entries:
        _save_last_check()
        logger.info("No feed updates found — skipping")
        return JSONResponse(
            status_code=200,
            content={"status": "no_updates", "checked_since": since.isoformat()},
        )

    # ── 3. Load current YAML ─────────────────────────────────────────
    current_yaml = _load_current_yaml()

    # ── 4. Compute diff ──────────────────────────────────────────────
    diff = compute_diff(feed_entries, current_yaml)

    if not diff.has_changes:
        _save_last_check()
        logger.info("No relevant changes detected in feeds")
        return JSONResponse(
            status_code=200,
            content={
                "status": "no_changes",
                "feed_entries": len(feed_entries),
                "checked_since": since.isoformat(),
            },
        )

    # ── 5. Enrich with full text ─────────────────────────────────────
    try:
        diff = await enrich_diff(diff)
    except Exception as exc:
        logger.warning("Enrichment failed (proceeding with partial data): %s", exc)

    # ── 6. ADK LLM assessment ────────────────────────────────────────
    impact_assessment = "LLM assessment unavailable"
    confidence = 0.5
    rego_suggestions: list[str] = []
    llm_decision_assignments: dict[str, list[str]] = {}

    try:
        # Build context message for the LLM
        diff_context = json.dumps(diff.model_dump(mode="json"), indent=2, default=str)
        user_text = (
            f"Compliance check completed. DiffReport:\n\n{diff_context}\n\n"
            f"Affected decision types: {diff.affected_decision_types}\n"
            f"Updated entries: {len(diff.updated_entries)}, "
            f"New entries: {len(diff.new_entries)}"
        )

        user_msg = types.Content(
            role="user",
            parts=[types.Part(text=user_text)],
        )

        # Run ADK agent
        last_tool_result: dict | None = None
        async for adk_event in runner.run_async(
            user_id="compliance-agent",
            session_id=f"compliance-{int(time.time())}",
            new_message=user_msg,
        ):
            if hasattr(adk_event, "content") and adk_event.content:
                for part in adk_event.content.parts or []:
                    if hasattr(part, "function_response") and part.function_response:
                        resp = part.function_response.response
                        if isinstance(resp, dict) and "status" in resp:
                            last_tool_result = resp

        if last_tool_result:
            if last_tool_result.get("status") == "no_op":
                _save_last_check()
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "no_op",
                        "reason": last_tool_result.get(
                            "reason", "LLM determined no action needed"
                        ),
                    },
                )

            impact_assessment = last_tool_result.get(
                "impact_assessment", impact_assessment
            )
            confidence = last_tool_result.get("confidence", confidence)
            rego_suggestions = last_tool_result.get("rego_suggestions", [])
            llm_decision_assignments = last_tool_result.get(
                "decision_type_assignments", {}
            )

    except Exception as exc:
        logger.error("ADK runner failed — using fallback assessment: %s", exc)
        impact_assessment = (
            f"Automated assessment unavailable ({exc}). Manual review required."
        )
        confidence = 0.3

    # ── 7. Build proposal ────────────────────────────────────────────
    # If LLM provided decision type assignments, use them for the YAML patch
    yaml_patch_override = None
    if llm_decision_assignments:
        updates: dict[str, list[YAMLPatchEntry]] = {}
        for dt, ref_ids in llm_decision_assignments.items():
            for ref_id in ref_ids:
                # Find the matching entry from the diff
                matching = None
                for e in diff.updated_entries + diff.new_entries:
                    if ref_id in e.feed_entry.ref_id:
                        matching = e
                        break
                if matching:
                    updates.setdefault(dt, []).append(
                        YAMLPatchEntry(
                            ref=(
                                f"NIST {matching.feed_entry.ref_id}"
                                if "NIST" not in matching.feed_entry.ref_id
                                else matching.feed_entry.ref_id
                            ),
                            title=matching.feed_entry.change_summary
                            or matching.feed_entry.ref_id,
                            revision=matching.feed_entry.latest_revision or None,
                        )
                    )
        if updates:
            yaml_patch_override = YAMLPatch(updates=updates)

    proposal = build_proposal(
        diff=diff,
        impact_assessment=impact_assessment,
        confidence=confidence,
        proposed_rego_suggestions=rego_suggestions,
        yaml_patch_override=yaml_patch_override,
    )

    # ── 8. Validate ──────────────────────────────────────────────────
    validation = validate_proposal(proposal, current_yaml)

    if not validation.valid:
        logger.warning(
            "Proposal %s failed validation: %s — storing anyway for review",
            proposal.proposal_id,
            validation.errors,
        )

    # ── 9. Store + notify ────────────────────────────────────────────
    proposal_path = f"proposals/compliance/{proposal.created_at.strftime('%Y-%m-%d')}/{proposal.proposal_id}.json"
    gcs_ok = _write_gcs_json(
        PROPOSALS_BUCKET,
        proposal_path,
        proposal.model_dump(mode="json"),
    )

    issue_url = _create_github_issue(proposal) if validation.valid else None

    _save_last_check()

    elapsed = time.monotonic() - t_start
    logger.info(
        "Pipeline complete: proposal=%s valid=%s gcs=%s issue=%s elapsed=%.1fs",
        proposal.proposal_id,
        validation.valid,
        gcs_ok,
        issue_url or "skipped",
        elapsed,
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "proposal_created",
            "proposal_id": proposal.proposal_id,
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "gcs_stored": gcs_ok,
            "github_issue": issue_url,
            "updated_entries": len(diff.updated_entries),
            "new_entries": len(diff.new_entries),
            "confidence": proposal.confidence,
            "elapsed_seconds": round(elapsed, 1),
        },
    )
