#!/usr/bin/env python3
"""
ActionTrace schema + ACR contract for S5/SS2.

ActionTraces are CloudEvents envelopes whose `.data` includes the minimum
fields needed to support explainability, provenance, and auditability.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


ACTIONTRACE_SCHEMA_VERSION = "1.0"


REQUIRED_CE_FIELDS = ["specversion", "id", "source", "type", "time", "datacontenttype", "data"]

REQUIRED_DATA_FIELDS = [
    "schema_version",
    "scenario_id",
    "stage",
    "mode",
    "run_id",
    "case_id",
    "actor",
    "action",
    "recommendation",
    "decision",
    "rationale",
    "risk",
    "evidence",
    "timestamps",
    "provenance",
    "otel",
]

REQUIRED_RISK_FIELDS = ["score", "level"]
REQUIRED_TIMESTAMPS_FIELDS = ["t_recommend_epoch"]
REQUIRED_PROVENANCE_FIELDS = ["commit_sha"]


def _is_nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict, set)):
        return len(v) > 0
    return True


def validate_action_trace(trace: Dict[str, Any]) -> Tuple[bool, List[str]]:
    missing: List[str] = []

    for f in REQUIRED_CE_FIELDS:
        if f not in trace or not _is_nonempty(trace.get(f)):
            missing.append(f)

    data = trace.get("data") if isinstance(trace.get("data"), dict) else {}

    for f in REQUIRED_DATA_FIELDS:
        if f not in data or not _is_nonempty(data.get(f)):
            missing.append(f"data.{f}")

    risk = data.get("risk") if isinstance(data.get("risk"), dict) else {}
    for f in REQUIRED_RISK_FIELDS:
        if f not in risk or not _is_nonempty(risk.get(f)):
            missing.append(f"data.risk.{f}")

    timestamps = data.get("timestamps") if isinstance(data.get("timestamps"), dict) else {}
    for f in REQUIRED_TIMESTAMPS_FIELDS:
        if f not in timestamps or not _is_nonempty(timestamps.get(f)):
            missing.append(f"data.timestamps.{f}")

    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    for f in REQUIRED_PROVENANCE_FIELDS:
        if f not in provenance or not _is_nonempty(provenance.get(f)):
            missing.append(f"data.provenance.{f}")

    return (len(missing) == 0), missing


def compute_acr(traces: Iterable[Dict[str, Any]]) -> float:
    traces_list = list(traces)
    if not traces_list:
        return 0.0
    ok = 0
    for t in traces_list:
        valid, _missing = validate_action_trace(t)
        ok += 1 if valid else 0
    return ok / len(traces_list)

