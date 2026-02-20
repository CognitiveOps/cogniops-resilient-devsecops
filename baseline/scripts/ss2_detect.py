#!/usr/bin/env python3
"""
SS2 Adaptive Threat Mitigation — Detection stage (MTTD).

This script intentionally measures only detection latency (MTTD) for SS2.
Recovery timing (MTTR) remains a component benchmark of S3.

Usage: provide a t_inject timestamp (epoch seconds) and poll /status until a
failure condition is detected (non-200, slow response, or unhealthy metrics).
Optionally emits a stage event to the unified ingest endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from baseline.explainability.emit import emit_stage_event


def _get_status(service_url: str, timeout_sec: float) -> Tuple[int, float, str]:
    """
    Return: (http_code, latency_sec, body_text)
    Uses urllib to avoid external deps.
    """
    import urllib.error
    import urllib.request

    url = service_url.rstrip("/") + "/status"
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = int(resp.getcode())
    except urllib.error.HTTPError as e:
        code = int(e.code)
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
    except Exception as e:
        code = 0
        body = str(e)
    latency = max(0.0, time.perf_counter() - t0)
    return code, latency, body


def _is_detected(
    *,
    http_code: int,
    latency_sec: float,
    body_text: str,
    latency_budget_sec: float,
    fps_min: float,
    detection_rate_min: float,
) -> Tuple[bool, str, Dict[str, Any]]:
    if http_code != 200:
        return True, f"http_{http_code}", {}

    if latency_budget_sec > 0 and latency_sec > latency_budget_sec:
        return True, "latency_budget_exceeded", {}

    try:
        payload = json.loads(body_text)
    except Exception:
        return True, "invalid_json", {}

    # Align with baseline/scripts/s3_detect_status.py thresholds.
    if not payload.get("healthy", True):
        return True, "unhealthy_flag", payload
    if float(payload.get("fps", 0.0) or 0.0) < fps_min:
        return True, "fps_below_threshold", payload
    if float(payload.get("detection_rate", 1.0) or 1.0) <= detection_rate_min:
        return True, "detection_rate_below_threshold", payload

    return False, "ok", payload


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service-url", default="http://127.0.0.1:8080")
    ap.add_argument("--t-inject-epoch", type=float, required=True)
    ap.add_argument("--deadline-sec", type=float, default=300.0)
    ap.add_argument("--poll-interval-sec", type=float, default=2.0)
    ap.add_argument("--timeout-sec", type=float, default=5.0)

    ap.add_argument("--latency-budget-sec", type=float, default=float(os.getenv("LATENCY_BUDGET_SEC", "2.0")))
    ap.add_argument("--fps-min", type=float, default=float(os.getenv("FPS_MIN", "10.0")))
    ap.add_argument(
        "--detection-rate-min",
        type=float,
        default=float(os.getenv("DETECTION_RATE_MIN", "0.01")),
    )

    ap.add_argument("--run-id", default=os.getenv("RUN_ID", ""))
    ap.add_argument("--commit-sha", default=os.getenv("GITHUB_SHA", ""))
    ap.add_argument("--scenario-id", default=os.getenv("SCENARIO_ID", "ss2"))
    ap.add_argument("--mode", default=os.getenv("MODE", "baseline"))

    ap.add_argument("--fault-mode", default=os.getenv("FAIL_MODE", ""))
    ap.add_argument("--ingest-url", default=os.getenv("METRICS_INGEST_URL", ""))
    ap.add_argument("--auth-token", default=os.getenv("ID_TOKEN", ""))
    ap.add_argument("--stage", default="ss2_detect", help="Stage name to emit (default: ss2_detect).")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    t_inject = float(args.t_inject_epoch)
    deadline = t_inject + float(args.deadline_sec)

    last: Dict[str, Any] = {}
    detected = False
    detect_reason = "timeout"
    t_detect = time.time()

    while time.time() < deadline:
        http_code, latency_sec, body_text = _get_status(args.service_url, float(args.timeout_sec))
        is_detected, reason, payload = _is_detected(
            http_code=http_code,
            latency_sec=latency_sec,
            body_text=body_text,
            latency_budget_sec=float(args.latency_budget_sec),
            fps_min=float(args.fps_min),
            detection_rate_min=float(args.detection_rate_min),
        )

        last = {
            "http_code": http_code,
            "latency_sec": round(float(latency_sec), 6),
            "body": payload if payload else None,
            "body_raw": body_text[:2000],
            "reason": reason,
        }

        if is_detected:
            detected = True
            detect_reason = reason
            t_detect = time.time()
            break

        time.sleep(float(args.poll_interval_sec))

    mttd_sec = max(0.0, float(t_detect) - float(t_inject))
    result: Dict[str, Any] = {
        "detected": detected,
        "t_inject_epoch": t_inject,
        "t_detect_epoch": float(t_detect),
        "mttd_sec": round(mttd_sec, 6),
        "detect_reason": detect_reason,
        "observation": last,
        "thresholds": {
            "latency_budget_sec": float(args.latency_budget_sec),
            "fps_min": float(args.fps_min),
            "detection_rate_min": float(args.detection_rate_min),
        },
        "context": {
            "service_url": args.service_url,
            "fault_mode": args.fault_mode,
        },
    }

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:
        print(json.dumps(result, ensure_ascii=False))

    if args.ingest_url and args.run_id and args.commit_sha:
        emit_stage_event(
            ingest_url=args.ingest_url,
            auth_token=args.auth_token,
            run_id=args.run_id,
            scenario_id=args.scenario_id,
            stage=str(args.stage),
            mode=args.mode,
            status="success" if detected else "failure",
            commit_sha=args.commit_sha,
            t_start_epoch=t_inject,
            t_end_epoch=float(t_detect),
            labels={
                "service": "edge_cv_app",
                "env": "gh-runner",
                "edge_device": "gh-runner",
                "fault_type": args.fault_mode,
                "fault_mode": args.fault_mode,
            },
            metrics={
                "mttd_sample_sec": round(mttd_sec, 6),
                "detect_reason": detect_reason,
                "http_code": last.get("http_code"),
                "latency_sec": last.get("latency_sec"),
            },
        )

    return 0 if detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
