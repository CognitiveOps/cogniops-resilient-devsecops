#!/usr/bin/env python3
"""
Approval timestamp helpers for AL measurement.

AL is measured using the GitHub Environments "pause-until-approved" semantics:
  AL = t_approved - t_recommend

Implementation note:
- The workflow job that uses `environment: <name>` is paused *before it starts*.
- Therefore, the approval timestamp is captured as the first step after resume.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _utc_now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _utc_iso_from_epoch(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_timestamp(path: str, *, key: str, epoch: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ts = float(epoch) if epoch is not None else _utc_now_epoch()
    payload: Dict[str, Any] = {
        key: {"epoch": ts, "iso": _utc_iso_from_epoch(ts)},
    }
    if extra:
        payload[key].update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
    return payload


def read_timestamp(path: str, *, key: str) -> Optional[Tuple[float, str]]:
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
        node = data.get(key) if isinstance(data, dict) else None
        if not isinstance(node, dict):
            return None
        epoch = float(node.get("epoch"))
        iso = str(node.get("iso") or "")
        return epoch, iso
    except Exception:
        return None


def compute_approval_latency_sec(t_recommend_epoch: float, t_approved_epoch: float) -> float:
    return max(0.0, float(t_approved_epoch) - float(t_recommend_epoch))

