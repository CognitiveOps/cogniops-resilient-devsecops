#!/usr/bin/env python3
"""
S4 PQC Validation Runner

Implements deterministic sub-scenarios for S4:
  - P0: valid manifest + correct signature (expect PASS)
  - P1: tampered manifest (expect FAIL)
  - P2: incorrect public key (expect FAIL)
  - P3: replayed/old manifest (expect FAIL)

Outputs per-scenario metrics (TTV, verification outcome) and aggregates VSR/FDR.
Optionally posts each stage to the scenario-runs-ingest endpoint used across
the project (BigQuery sink).

Cryptographic backend: pluggable interface using liboqs (python-oqs), with
Dilithium as the default demo algorithm.
"""

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from baseline.security.pqc.backends import PQCBackendError, get_backend


def canonical_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def verify_payload(
    payload: bytes,
    backend_name: str,
    algorithm: str,
    pub: bytes,
    signature: bytes,
    replay_cutoff_ts: Optional[float] = None,
    manifest_ts: Optional[float] = None,
) -> Tuple[bool, str]:
    if replay_cutoff_ts is not None and manifest_ts is not None:
        if manifest_ts < replay_cutoff_ts:
            return False, "replay-window"

    backend = get_backend(backend_name, algorithm)
    verified = backend.verify(payload, pub, signature)
    if not verified:
        return False, "signature-mismatch"
    return True, "ok"


def write_artifacts(
    output_dir: str, manifest_path: str, signature: bytes, public_key: bytes
) -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(manifest_path)
    sig_path = os.path.join(output_dir, f"{base_name}.pqcsig")
    pub_path = os.path.join(output_dir, "pub.key")
    with open(sig_path, "wb") as f:
        f.write(signature)
    with open(pub_path, "wb") as f:
        f.write(public_key)
    return sig_path, pub_path


def send_ingest(
    ingest_url: str,
    token: str,
    payload: Dict[str, Any],
) -> None:
    if not ingest_url:
        return

    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        ingest_url, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() != 200:
                sys.stderr.write(
                    f"[ingest] HTTP {resp.getcode()} body={resp.read()!r}\n"
                )
    except urllib.error.HTTPError as e:
        sys.stderr.write(
            f"[ingest] HTTPError status={e.code} body={e.read()!r}\n"
        )
    except Exception as e:  # pragma: no cover - defensive logging
        sys.stderr.write(f"[ingest] error: {e}\n")


def mutate_manifest_single_byte(manifest: Dict[str, Any]) -> Dict[str, Any]:
    mutated = copy.deepcopy(manifest)
    digest = str(mutated.get("digest", ""))
    if digest:
        flip = "a" if digest[-1] != "a" else "b"
        mutated["digest"] = digest[:-1] + flip
    else:
        mutated["version"] = str(mutated.get("version", "")) + "-tamper"
    return mutated


def replay_manifest(manifest: Dict[str, Any], delta_seconds: float) -> Dict[str, Any]:
    replayed = copy.deepcopy(manifest)
    ts = float(replayed.get("ts", time.time()))
    replayed["ts"] = max(0, ts - delta_seconds)
    return replayed


def run_subscenario(
    scenario_id: str,
    manifest: Dict[str, Any],
    payload: bytes,
    backend_name: str,
    algorithm: str,
    pub: bytes,
    signature: bytes,
    expected_verified: bool,
    replay_cutoff_ts: Optional[float],
) -> Dict[str, Any]:
    start_epoch = time.time()
    t0 = time.perf_counter()
    verified, reason = verify_payload(
        payload, backend_name, algorithm, pub, signature, replay_cutoff_ts, manifest.get("ts")
    )
    ttv_ms = (time.perf_counter() - t0) * 1000.0
    end_epoch = time.time()

    status = "success" if verified == expected_verified else "failure"

    return {
        "id": scenario_id,
        "expected": expected_verified,
        "verified": verified,
        "reason": reason or "ok",
        "status": status,
        "metrics": {
            "ttv_ms": round(ttv_ms, 3),
            "ttv_sec": round(ttv_ms / 1000.0, 6),
        },
        "t_start": start_epoch,
        "t_end": end_epoch,
    }


def compute_summary(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid_cases = [s for s in scenarios if s["expected"]]
    invalid_cases = [s for s in scenarios if not s["expected"]]

    vsr = (
        sum(1 for s in valid_cases if s["verified"]) / len(valid_cases)
        if valid_cases
        else 0.0
    )
    fdr = (
        sum(1 for s in invalid_cases if not s["verified"]) / len(invalid_cases)
        if invalid_cases
        else 0.0
    )

    ttv_all_ms = (
        sum(s["metrics"]["ttv_ms"] for s in scenarios) / len(scenarios)
        if scenarios
        else 0.0
    )
    ttv_valid_ms = (
        sum(s["metrics"]["ttv_ms"] for s in valid_cases) / len(valid_cases)
        if valid_cases
        else 0.0
    )

    return {
        "vsr": round(vsr, 4),
        "fdr": round(fdr, 4),
        "ttv_all_ms": round(ttv_all_ms, 3),
        "ttv_valid_ms": round(ttv_valid_ms, 3),
        "cases": len(scenarios),
        "status": "success" if all(s["status"] == "success" for s in scenarios) else "failure",
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to OTA manifest JSON.")
    ap.add_argument("--out", required=True, help="Path to write results JSON.")
    ap.add_argument(
        "--emit-artifacts-dir",
        default="",
        help="Optional output dir for signature/public key artifacts.",
    )
    ap.add_argument("--ingest-url", default="", help="Scenario ingest endpoint (optional).")
    ap.add_argument("--auth-token", default="", help="Bearer token for ingest (optional).")
    ap.add_argument("--run-id", required=True, help="Logical run identifier.")
    ap.add_argument("--commit-sha", required=True, help="Commit SHA for provenance.")
    ap.add_argument("--scenario-id", default="s4", help="Scenario identifier (default: s4).")
    ap.add_argument("--mode", default="baseline", help="Mode label (baseline/shadow/enforce).")
    ap.add_argument("--backend", default="oqs", help="Backend: oqs.")
    ap.add_argument(
        "--algorithm",
        default="Dilithium2",
        help="PQC algorithm (oqs backend).",
    )
    ap.add_argument(
        "--replay-cutoff-sec",
        type=float,
        default=900.0,
        help="Replay protection window (seconds). Manifest ts older than now-cutoff fails.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        base_manifest = json.load(f)

    base_payload = canonical_bytes(base_manifest)

    try:
        backend = get_backend(args.backend, args.algorithm)
    except PQCBackendError as exc:
        sys.stderr.write(f"[s4] backend error: {exc}\n")
        return 2

    priv_main, pub_main = backend.generate_keypair()
    sig_main = backend.sign(base_payload, priv_main)

    _, pub_alt = backend.generate_keypair()

    if args.emit_artifacts_dir:
        write_artifacts(args.emit_artifacts_dir, args.manifest, sig_main, pub_main)

    replay_cutoff_ts = time.time() - float(args.replay_cutoff_sec)

    scenarios: List[Dict[str, Any]] = []

    scenarios.append(
        run_subscenario(
            "s4_p0_valid",
            base_manifest,
            base_payload,
            backend.name,
            backend.algorithm,
            pub_main,
            sig_main,
            expected_verified=True,
            replay_cutoff_ts=replay_cutoff_ts,
        )
    )

    tampered_manifest = mutate_manifest_single_byte(base_manifest)
    tampered_payload = canonical_bytes(tampered_manifest)
    scenarios.append(
        run_subscenario(
            "s4_p1_tamper",
            tampered_manifest,
            tampered_payload,
            backend.name,
            backend.algorithm,
            pub_main,
            sig_main,
            expected_verified=False,
            replay_cutoff_ts=replay_cutoff_ts,
        )
    )

    scenarios.append(
        run_subscenario(
            "s4_p2_wrong_key",
            base_manifest,
            base_payload,
            backend.name,
            backend.algorithm,
            pub_alt,
            sig_main,
            expected_verified=False,
            replay_cutoff_ts=replay_cutoff_ts,
        )
    )

    replayed_manifest = replay_manifest(base_manifest, delta_seconds=args.replay_cutoff_sec * 2)
    replay_payload = canonical_bytes(replayed_manifest)
    replay_sig = backend.sign(replay_payload, priv_main)
    scenarios.append(
        run_subscenario(
            "s4_p3_replay",
            replayed_manifest,
            replay_payload,
            backend.name,
            backend.algorithm,
            pub_main,
            replay_sig,
            expected_verified=False,
            replay_cutoff_ts=replay_cutoff_ts,
        )
    )

    summary = compute_summary(scenarios)

    results = {
        "run_id": args.run_id,
        "commit_sha": args.commit_sha,
        "scenario_id": args.scenario_id,
        "mode": args.mode,
        "backend": backend.name,
        "algorithm": backend.algorithm,
        "replay_cutoff_ts": replay_cutoff_ts,
        "results": scenarios,
        "summary": summary,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Emit ingest events per stage + summary
    for s in scenarios:
        payload = {
            "run_id": args.run_id,
            "scenario_id": args.scenario_id,
            "stage": s["id"],
            "mode": args.mode,
            "status": s["status"],
            "commit_sha": args.commit_sha,
            "t_start": s["t_start"],
            "t_end": s["t_end"],
            "metrics": {
                "ttv_ms": s["metrics"]["ttv_ms"],
                "ttv_sec": s["metrics"]["ttv_sec"],
                "verified": s["verified"],
                "expected": s["expected"],
                "pqc_backend": backend.name,
                "pqc_algorithm": backend.algorithm,
            },
            "labels": {
                "reason": s["reason"],
                "backend": backend.name,
                "algorithm": backend.algorithm,
                "alg": backend.algorithm,
                "variant": os.environ.get("VARIANT", "baseline"),
            },
        }
        send_ingest(args.ingest_url, args.auth_token, payload)

    # Summary is kept in results.json; aggregate metrics are derived in BigQuery.

    return 0 if summary["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
