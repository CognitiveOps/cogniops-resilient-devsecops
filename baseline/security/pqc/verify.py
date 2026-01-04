#!/usr/bin/env python3
"""
Verify a PQC signature over a canonical OTA manifest.

This CLI is intended for pipeline/edge reuse (S4, SS2) and supports a pluggable
backend (toy or liboqs).
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from baseline.security.pqc.backends import PQCBackendError, get_backend


def canonical_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def verify_manifest(
    backend_name: str,
    algorithm: str,
    manifest: Dict[str, Any],
    signature: bytes,
    public_key: bytes,
    replay_cutoff_sec: float,
) -> Tuple[bool, str, str, str]:
    if replay_cutoff_sec > 0:
        ts = manifest.get("ts")
        if ts is not None and float(ts) < time.time() - replay_cutoff_sec:
            backend = get_backend(backend_name, algorithm)
            return False, "replay-window", backend.name, backend.algorithm

    payload = canonical_bytes(manifest)
    backend = get_backend(backend_name, algorithm)
    verified = backend.verify(payload, public_key, signature)
    return verified, "ok" if verified else "signature-mismatch", backend.name, backend.algorithm


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to OTA manifest JSON.")
    ap.add_argument("--sig", required=True, help="Path to PQC signature file.")
    ap.add_argument("--pub", required=True, help="Path to public key file.")
    ap.add_argument("--backend", default="auto", help="Backend: auto | oqs | toy.")
    ap.add_argument("--algorithm", default="Dilithium2", help="PQC algorithm (oqs only).")
    ap.add_argument(
        "--replay-cutoff-sec",
        type=float,
        default=0.0,
        help="Replay window in seconds (0 = disabled).",
    )
    ap.add_argument("--out", default="", help="Optional JSON output file.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    try:
        manifest = load_manifest(args.manifest)
        signature = load_bytes(args.sig)
        public_key = load_bytes(args.pub)
        verified, reason, backend_name, backend_alg = verify_manifest(
            args.backend,
            args.algorithm,
            manifest,
            signature,
            public_key,
            args.replay_cutoff_sec,
        )
    except PQCBackendError as exc:
        sys.stderr.write(f"[verify] backend error: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"[verify] error: {exc}\n")
        return 2

    result = {
        "verified": verified,
        "reason": reason,
        "backend": backend_name,
        "algorithm": backend_alg,
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result))

    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
