#!/usr/bin/env python3
"""
Emit S5/SS2 events to the unified ingest endpoint (BigQuery sink).

This uses the project-wide stage-event payload schema described in README:
  run_id, scenario_id, stage, mode, status, commit_sha, t_start, t_end,
  duration_sec, labels, metrics
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _iso_from_epoch(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def emit_stage_event(
    *,
    ingest_url: str,
    auth_token: str = "",
    run_id: str,
    scenario_id: str,
    stage: str,
    mode: str,
    status: str,
    commit_sha: str,
    t_start_epoch: float,
    t_end_epoch: float,
    labels: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    if not ingest_url:
        return

    duration = max(0.0, float(t_end_epoch) - float(t_start_epoch))
    merged_labels = dict(labels or {})
    if "variant" not in merged_labels:
        merged_labels["variant"] = os.environ.get("VARIANT", "baseline")
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "stage": stage,
        "mode": mode,
        "status": status,
        "commit_sha": commit_sha,
        "t_start": _iso_from_epoch(t_start_epoch),
        "t_end": _iso_from_epoch(t_end_epoch),
        "duration_sec": round(duration, 6),
        "labels": merged_labels,
        "metrics": metrics or {},
    }

    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = urllib.request.Request(ingest_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() != 200:
                sys.stderr.write(f"[ingest] HTTP {resp.getcode()} body={resp.read()!r}\n")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[ingest] HTTPError status={e.code} body={e.read()!r}\n")
    except Exception as e:  # pragma: no cover
        sys.stderr.write(f"[ingest] error: {e}\n")


def emit_cloudevent(
    *,
    ingest_url: str,
    auth_token: str = "",
    cloudevent: Dict[str, Any],
) -> None:
    """
    Emit a CloudEvents v1.0 envelope to the same ingest endpoint.

    The ingest function is responsible for normalizing it into the BigQuery 'runs' schema.
    """
    if not ingest_url:
        return
    if not isinstance(cloudevent, dict):
        raise TypeError("cloudevent must be a dict")

    body = json.dumps(cloudevent, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    req = urllib.request.Request(ingest_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() != 200:
                sys.stderr.write(f"[ingest] HTTP {resp.getcode()} body={resp.read()!r}\n")
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[ingest] HTTPError status={e.code} body={e.read()!r}\n")
    except Exception as e:  # pragma: no cover
        sys.stderr.write(f"[ingest] error: {e}\n")
