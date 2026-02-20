#!/usr/bin/env python3
"""
Explanation report rendering.

Produces:
- Machine-readable JSON explanation (derived from ActionTrace data)
- Human-readable Markdown summary
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_explanation_json(action_trace: Dict[str, Any]) -> Dict[str, Any]:
    data = action_trace.get("data") if isinstance(action_trace.get("data"), dict) else {}
    return {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "case_id": data.get("case_id"),
        "action": data.get("action"),
        "decision": data.get("decision"),
        "recommendation": data.get("recommendation"),
        "risk": data.get("risk", {}),
        "rationale": data.get("rationale", ""),
        "evidence": data.get("evidence", []),
        "inputs": data.get("inputs", {}),
        "outputs": data.get("outputs", {}),
        "policy_refs": data.get("policy_refs", []),
        "provenance": data.get("provenance", {}),
        "otel": data.get("otel", {}),
    }


def render_explanation_markdown(action_trace: Dict[str, Any]) -> str:
    exp = render_explanation_json(action_trace)
    risk = exp.get("risk") or {}
    risk_score = risk.get("score", "n/a")
    risk_level = risk.get("level", "n/a")

    inputs = exp.get("inputs") or {}
    outputs = exp.get("outputs") or {}
    evidence = exp.get("evidence") or []
    policy_refs = exp.get("policy_refs") or []

    lines = [
        f"# Explainability Report — {exp.get('case_id')}",
        "",
        f"- Action: `{exp.get('action')}`",
        f"- Decision: `{exp.get('decision')}`",
        f"- Recommendation: `{exp.get('recommendation')}`",
        f"- Risk: `{risk_level}` (score={risk_score})",
        "",
        "## Rationale",
        (exp.get("rationale") or "").strip(),
        "",
        "## Inputs",
        "```json",
        json.dumps(inputs, ensure_ascii=False, sort_keys=True, indent=2),
        "```",
        "",
        "## Outputs",
        "```json",
        json.dumps(outputs, ensure_ascii=False, sort_keys=True, indent=2),
        "```",
    ]
    if evidence:
        lines += [
            "",
            "## Evidence",
            "```json",
            json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2),
            "```",
        ]
    if policy_refs:
        lines += ["", "## Policy References"] + [f"- {p}" for p in policy_refs]
    lines.append("")
    return "\n".join(lines)

