#!/usr/bin/env python3
"""
S5 Explainability & Human-in-the-Loop (HITL) runner.

This script is designed to be used across GitHub Actions jobs:
  - stage=explain  : generate ActionTraces + explanation reports; record t_recommend
  - stage=approved : record t_approved right after the environment gate resumes
  - stage=final    : compute AL + ACR; emit final stage metrics; write summary artifacts

It also supports SS2 reuse by accepting `--cases-file` instead of synthetic cases.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from baseline.explainability.approval import (
    compute_approval_latency_sec,
    read_timestamp,
    write_timestamp,
)
from baseline.explainability.cloudevents import new_cloudevent
from baseline.explainability.emit import emit_cloudevent, emit_stage_event
from baseline.explainability.report import (
    render_explanation_json,
    render_explanation_markdown,
)
from baseline.explainability.schema import ACTIONTRACE_SCHEMA_VERSION, compute_acr, validate_action_trace


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def _append_jsonl(path: str, obj: Any) -> None:
    _ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def _load_json(path: str) -> Any:
    return json.loads(open(path, "r", encoding="utf-8").read())


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def synthetic_cases() -> List[Dict[str, Any]]:
    return [
        {
            "case_id": "C0_policy_violation_detected",
            "action": "block_deploy",
            "recommendation": "block",
            "decision": "block",
            "risk": {"score": 0.81, "level": "high"},
            "rationale": "Policy checks indicate a violation (e.g., missing required security scan), so deployment is blocked.",
            "inputs": {"policy": "security_scan_required", "scan_status": "missing"},
            "outputs": {"mitigation": "block_deploy", "next": "request_manual_review"},
            "evidence": [{"type": "workflow_log", "ref": "actions://job/s5_explain"}],
            "policy_refs": ["OPA decision logs pattern (industry)", "Change control: block on policy violation"],
        },
        {
            "case_id": "C1_tampered_artifact_detected",
            "action": "quarantine_artifact",
            "recommendation": "quarantine",
            "decision": "require_approval",
            "risk": {"score": 0.95, "level": "critical"},
            "rationale": "Artifact integrity/tampering signal requires quarantine and investigation before any rollout.",
            "inputs": {"artifact": "edge_cv_app", "digest_mismatch": True},
            "outputs": {"mitigation": "quarantine", "notify": "security_team"},
            "evidence": [{"type": "attestation", "ref": "pqc://verification-failed"}],
            "policy_refs": ["Incident response: isolate on integrity failure"],
        },
        {
            "case_id": "C2_rollback_recommendation",
            "action": "rollback_release",
            "recommendation": "rollback",
            "decision": "approve_then_rollback",
            "risk": {"score": 0.7, "level": "medium"},
            "rationale": "Rollback is reversible and mitigates elevated error rates while investigation continues.",
            "inputs": {"service": "baseline-app", "error_rate": 0.08},
            "outputs": {"mitigation": "rollback", "target": "last_known_good"},
            "evidence": [{"type": "metric", "ref": "prom://error_rate"}],
            "policy_refs": ["Resilience playbook: rollback on elevated error rate"],
        },
    ]


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["explain", "approved", "final"])
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--run-id", required=True)
    ap.add_argument("--commit-sha", required=True)
    ap.add_argument("--scenario-id", default="s5")
    ap.add_argument("--mode", default="baseline")

    ap.add_argument("--cases-file", default="", help="Path to JSON list of cases (for SS2 reuse).")
    ap.add_argument("--service-name", default="cogniops")
    ap.add_argument("--deployment-environment", default="github-actions")

    ap.add_argument("--ingest-url", default=os.getenv("METRICS_INGEST_URL", ""))
    ap.add_argument("--auth-token", default=os.getenv("ID_TOKEN", ""))

    return ap.parse_args()


def _cases_from_args(args: argparse.Namespace) -> List[Dict[str, Any]]:
    if args.cases_file:
        return _load_json(args.cases_file)
    return synthetic_cases()


def stage_explain(args: argparse.Namespace) -> int:
    t0 = time.time()
    outdir = args.outdir
    _ensure_dir(outdir)
    cases_dir = os.path.join(outdir, "cases")
    _ensure_dir(cases_dir)

    action_traces_path = os.path.join(outdir, "action_traces.jsonl")
    if os.path.exists(action_traces_path):
        os.remove(action_traces_path)

    cases = _cases_from_args(args)

    # Record a single "recommendation time" for the run (before the environment gate).
    recommend_path = os.path.join(outdir, "recommendation.json")
    recommend = write_timestamp(
        recommend_path,
        key="t_recommend",
        extra={"run_id": args.run_id, "scenario_id": args.scenario_id, "mode": args.mode},
    )
    t_recommend_epoch = float(recommend["t_recommend"]["epoch"])

    for case in cases:
        trace_data: Dict[str, Any] = {
            "schema_version": ACTIONTRACE_SCHEMA_VERSION,
            "scenario_id": args.scenario_id,
            "stage": "s5_explain",
            "mode": args.mode,
            "run_id": args.run_id,
            "case_id": case.get("case_id", ""),
            "actor": "baseline-agent",
            "action": case.get("action", ""),
            "recommendation": case.get("recommendation", ""),
            "decision": case.get("decision", ""),
            "rationale": case.get("rationale", ""),
            "risk": case.get("risk") or {},
            "evidence": case.get("evidence") or [],
            "inputs": case.get("inputs") or {},
            "outputs": case.get("outputs") or {},
            "policy_refs": case.get("policy_refs") or [],
            "timestamps": {
                "t_recommend_epoch": t_recommend_epoch,
            },
            "provenance": {
                "commit_sha": args.commit_sha,
            },
            "otel": {
                "service.name": args.service_name,
                "deployment.environment.name": args.deployment_environment,
            },
        }

        trace = new_cloudevent(
            source=f"cogniops://{args.scenario_id}",
            type="cogniops.actiontrace.v1",
            subject=trace_data["case_id"],
            data=trace_data,
        )
        _append_jsonl(action_traces_path, trace)

        # Emit the full ActionTrace (as CloudEvent) for downstream ACR computation in BigQuery.
        emit_cloudevent(
            ingest_url=args.ingest_url,
            auth_token=args.auth_token,
            cloudevent=trace,
        )

        exp_json = render_explanation_json(trace)
        exp_md = render_explanation_markdown(trace)
        _write_json(os.path.join(cases_dir, f"{trace_data['case_id']}.explanation.json"), exp_json)
        with open(os.path.join(cases_dir, f"{trace_data['case_id']}.explanation.md"), "w", encoding="utf-8") as f:
            f.write(exp_md)

    t1 = time.time()
    emit_stage_event(
        ingest_url=args.ingest_url,
        auth_token=args.auth_token,
        run_id=args.run_id,
        scenario_id=args.scenario_id,
        stage="s5_explain",
        mode=args.mode,
        status="success",
        commit_sha=args.commit_sha,
        t_start_epoch=t0,
        t_end_epoch=t1,
        labels={"cases": len(cases)},
        metrics={"t_recommend_epoch": t_recommend_epoch},
    )

    return 0


def stage_approved(args: argparse.Namespace) -> int:
    t0 = time.time()
    outdir = args.outdir
    _ensure_dir(outdir)

    approved_path = os.path.join(outdir, "approved.json")
    approved = write_timestamp(
        approved_path,
        key="t_approved",
        extra={"run_id": args.run_id, "scenario_id": args.scenario_id, "mode": args.mode},
    )
    t_approved_epoch = float(approved["t_approved"]["epoch"])
    t1 = time.time()

    emit_stage_event(
        ingest_url=args.ingest_url,
        auth_token=args.auth_token,
        run_id=args.run_id,
        scenario_id=args.scenario_id,
        stage="s5_approve",
        mode=args.mode,
        status="success",
        commit_sha=args.commit_sha,
        t_start_epoch=t0,
        t_end_epoch=t1,
        metrics={"t_approved_epoch": t_approved_epoch},
    )

    return 0


def stage_final(args: argparse.Namespace) -> int:
    t0 = time.time()
    outdir = args.outdir

    recommend_path = os.path.join(outdir, "recommendation.json")
    approved_path = os.path.join(outdir, "approved.json")

    rec = read_timestamp(recommend_path, key="t_recommend")
    appr = read_timestamp(approved_path, key="t_approved")
    if not rec or not appr:
        raise SystemExit(f"Missing timestamps: rec={bool(rec)} appr={bool(appr)}; expected {recommend_path} and {approved_path}")

    t_recommend_epoch, _ = rec
    t_approved_epoch, _ = appr
    al_sec = compute_approval_latency_sec(t_recommend_epoch, t_approved_epoch)

    traces_path = os.path.join(outdir, "action_traces.jsonl")
    traces = _load_jsonl(traces_path)
    acr = compute_acr(traces)

    per_trace: List[Dict[str, Any]] = []
    for tr in traces:
        ok, missing = validate_action_trace(tr)
        per_trace.append(
            {
                "case_id": (tr.get("data") or {}).get("case_id"),
                "valid": ok,
                "missing": missing,
            }
        )

    results = {
        "summary": {
            "run_id": args.run_id,
            "scenario_id": args.scenario_id,
            "mode": args.mode,
            "commit_sha": args.commit_sha,
            "cases": len(traces),
            "al_sec": round(float(al_sec), 6),
            "acr": round(float(acr), 4),
            "t_recommend_epoch": t_recommend_epoch,
            "t_approved_epoch": t_approved_epoch,
        },
        "traces": per_trace,
    }
    results_path = os.path.join(outdir, "results.json")
    _write_json(results_path, results)

    report_md = os.path.join(outdir, "report.md")
    lines = [
        "# S5 Explainability (AL/ACR) — Summary",
        "",
        f"- Run ID: `{args.run_id}`",
        f"- Commit: `{args.commit_sha}`",
        f"- AL: `{results['summary']['al_sec']}` sec",
        f"- ACR: `{results['summary']['acr']}`",
        "",
        "## Trace validation (ACR contract)",
        "",
        "| Case | Complete | Missing fields |",
        "|---|:---:|---|",
    ]
    for tr in per_trace:
        missing = ", ".join(tr["missing"]) if tr["missing"] else ""
        lines.append(f"| `{tr['case_id']}` | {'yes' if tr['valid'] else 'no'} | {missing} |")
    lines.append("")
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    t1 = time.time()
    emit_stage_event(
        ingest_url=args.ingest_url,
        auth_token=args.auth_token,
        run_id=args.run_id,
        scenario_id=args.scenario_id,
        stage="s5_final",
        mode=args.mode,
        status="success",
        commit_sha=args.commit_sha,
        t_start_epoch=t0,
        t_end_epoch=t1,
        labels={"cases": len(traces)},
        metrics={"al_sec": round(float(al_sec), 6), "acr": round(float(acr), 4)},
    )

    return 0


def main() -> int:
    args = _parse_args()
    if args.stage == "explain":
        return stage_explain(args)
    if args.stage == "approved":
        return stage_approved(args)
    if args.stage == "final":
        return stage_final(args)
    raise SystemExit(f"Unsupported stage: {args.stage}")


if __name__ == "__main__":
    raise SystemExit(main())
