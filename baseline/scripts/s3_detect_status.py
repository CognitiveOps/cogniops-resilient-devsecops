"""
Lightweight detector for S3 status payloads.
Reads JSON from stdin and outputs "1" if a fault is considered detected, else "0".
Detection aligns with the table's C signals:
- unhealthy flag
- fps too low
- detection_rate ≈ 0 (e.g., black frames)
Thresholds are configured via env vars to allow per-fault tuning.
"""

import json
import os
import sys


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("1")  # invalid payload counts as failure
        return 0

    fps_min = float(os.getenv("FPS_MIN", "10"))
    detection_rate_min = float(os.getenv("DETECTION_RATE_MIN", "0.01"))

    # unhealthy flag → immediate detection (covers deterministic faults)
    if not data.get("healthy", True):
        print("1")
        return 0
    # fps below threshold → captures CPU starvation spikes (table row 3)
    if data.get("fps", 0) < fps_min:
        print("1")
        return 0
    # detection_rate ~0 → captures dead camera / black frames (table row 4)
    if data.get("detection_rate", 1.0) <= detection_rate_min:
        print("1")
        return 0

    print("0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
