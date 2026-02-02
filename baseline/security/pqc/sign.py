#!/usr/bin/env python3
"""
Create a PQC signature over a canonical OTA manifest.

This CLI is intended for pipeline-side signing in S4/SS2 demos.
It generates an ephemeral keypair per invocation.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any, Dict, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from baseline.security.pqc.backends import PQCBackendError, get_backend


def canonical_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, help="Path to OTA manifest JSON.")
    ap.add_argument("--backend", default="oqs", help="Backend: oqs.")
    ap.add_argument("--algorithm", default="Dilithium2", help="PQC algorithm (oqs only).")
    ap.add_argument("--out-sig", required=True, help="Path to write signature.")
    ap.add_argument("--out-pub", required=True, help="Path to write public key.")
    ap.add_argument("--out", default="", help="Optional JSON output file.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    try:
        backend = get_backend(args.backend, args.algorithm)
        manifest = load_manifest(args.manifest)
        payload = canonical_bytes(manifest)

        priv_main, pub_main = backend.generate_keypair()

        sig = backend.sign(payload, priv_main)

        write_bytes(args.out_sig, sig)
        write_bytes(args.out_pub, pub_main)
    except PQCBackendError as exc:
        sys.stderr.write(f"[sign] backend error: {exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"[sign] error: {exc}\n")
        return 2

    result = {
        "backend": backend.name,
        "algorithm": backend.algorithm,
        "manifest": os.path.abspath(args.manifest),
        "signature": os.path.abspath(args.out_sig),
        "public_key": os.path.abspath(args.out_pub),
        "signature_b64": base64.b64encode(sig).decode("ascii"),
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    else:
        print(json.dumps(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
