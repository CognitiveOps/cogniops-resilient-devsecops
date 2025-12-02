import os
import random
import time
from threading import Thread
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .metrics import EdgeMetrics
from .fault_models import (
    NoFaultModel,
    NetworkLikeFault,
    CpuThrottleFault,
    BlackFramesFault,
    CorruptedModelFault,
    DiskFullFault,
    WrongArchFault,
    MarkovStepper,
)

app = FastAPI()

# Global state (simple for baseline)
METRICS = EdgeMetrics()
FAULT_MODEL = NoFaultModel()
RUNNING = True

# Haar cascade shipped with OpenCV
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _select_fault_model(mode: str, scenario: Optional[str]):
    """
    Select behavioral fault model based on MODE/SCENARIO or legacy FAIL_MODE.

    MODE:
      - real  -> no faults
      - twin  -> apply scenario (s3_net, s3_cpu, s3_cam, s3_model)
    FAIL_MODE (legacy Cloud Run env):
      - net_unstable, cpu_starvation, dead_camera, corrupt_weights, wrong_arch, generic_fail/1
    """
    if mode != "twin" or not scenario:
        return NoFaultModel()

    scenario = scenario.lower()
    if scenario in {"s3_net", "net_unstable"}:
        return NetworkLikeFault()
    if scenario in {"s3_cpu", "cpu_starvation"}:
        return CpuThrottleFault()
    if scenario in {"s3_cam", "dead_camera"}:
        return BlackFramesFault()
    if scenario in {"s3_model", "corrupt_weights"}:
        return CorruptedModelFault()
    if scenario in {"s3_disk", "disk_full"}:
        return DiskFullFault()
    if scenario in {"s3_wrong_arch", "wrong_arch"}:
        return WrongArchFault()

    # wrong_arch / generic_fail are handled at endpoint level
    return NoFaultModel()


def _simulate_frame_loop(mode: str) -> None:
    """
    Main loop for edge_cv_app.

    In MODE=real:
      - plug in real camera + model inference (baseline sim below).
    In MODE=twin:
      - simulate frames and base metrics, then apply fault models.
    """
    global METRICS, FAULT_MODEL, RUNNING

    markov = MarkovStepper()

    while RUNNING:
        start = time.time()

        METRICS.frame_idx += 1

        # --- Base metrics (healthy behavior) ---
        METRICS.fps = 25.0 + random.uniform(-2.0, 2.0)
        METRICS.detection_rate = random.uniform(0.7, 0.95)
        METRICS.queue_latency_ms = random.uniform(10.0, 40.0)
        METRICS.inference_ms = random.uniform(15.0, 30.0)
        METRICS.healthy = True
        METRICS.last_error = None
        METRICS.state = "healthy"

        # --- Apply Markov multistate reliability (healthy/degraded/failed/recovering) ---
        state = markov.step() if mode == "twin" else "healthy"
        METRICS.state = state
        if state == "degraded":
            METRICS.fps *= 0.8
            METRICS.queue_latency_ms *= 1.3
            METRICS.inference_ms *= 1.2
        elif state == "failed":
            METRICS.healthy = False
            METRICS.detection_rate = 0.0
            METRICS.fps = 0.0
            METRICS.queue_latency_ms *= 2.0
        elif state == "recovering":
            METRICS.fps *= 0.9
            METRICS.queue_latency_ms *= 1.1
            METRICS.inference_ms *= 1.05

        # --- Apply fault model only in twin mode ---
        FAULT_MODEL.apply(METRICS)

        # Update timestamp
        METRICS.touch()

        # Aim for ~25 FPS simulated loop
        elapsed = time.time() - start
        sleep_time = max(0.0, (1.0 / 25.0) - elapsed)
        time.sleep(sleep_time)


@app.get("/status")
def status():
    """
    Status endpoint used by S2 (real edge) and S3 (twin metrics).
    Legacy FAIL_MODEs can still force hard failures here.
    """
    fail_mode = os.getenv("FAIL_MODE", "0").lower()

    if fail_mode in {"generic_fail", "1"}:
        raise HTTPException(
            status_code=500,
            detail="Injected failure for S3 scenario (FAIL_MODE=generic_fail)",
        )

    if fail_mode == "disk_full":
        raise HTTPException(status_code=507, detail="Simulated disk full / read-only filesystem")

    if fail_mode == "corrupt_weights":
        raise HTTPException(status_code=500, detail="Simulated corrupted model weights")

    # net_unstable and cpu_starvation induce delay via fault model; keep fast response here
    return JSONResponse(METRICS.to_dict())


@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    """
    Simple computer-vision inference endpoint.
    Honors legacy FAIL_MODEs for compatibility with earlier S3 scripts.
    """
    fail_mode = os.getenv("FAIL_MODE", "0").lower()

    if fail_mode == "dead_camera":
        return JSONResponse(
            {"ok": False, "error": "dead_camera", "detections": [], "count": 0},
            status_code=503,
        )

    if fail_mode == "corrupt_weights":
        raise HTTPException(status_code=500, detail="Simulated corrupted model weights")

    if fail_mode == "cpu_starvation":
        time.sleep(random.uniform(1.5, 3.0))

    content = await file.read()
    img_array = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"ok": False, "error": "invalid_image"}, status_code=400)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(30, 30),
    )
    boxes = [
        {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        for (x, y, w, h) in faces
    ]
    return {"ok": True, "detections": boxes, "count": len(boxes)}


def main():
    global FAULT_MODEL, RUNNING

    # MODE default real; if FAIL_MODE set to non-0, treat as twin for fault injection
    mode_env = os.getenv("MODE", "real").lower()
    fail_mode = os.getenv("FAIL_MODE", "0").lower()
    mode = "twin" if fail_mode not in {"0", "", None} else mode_env

    scenario = os.getenv("SCENARIO") or fail_mode
    FAULT_MODEL = _select_fault_model(mode, scenario)

    # Start background loop
    t = Thread(target=_simulate_frame_loop, args=(mode,), daemon=True)
    t.start()

    try:
        port = int(os.getenv("PORT", "8080"))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    finally:
        RUNNING = False
        t.join(timeout=2.0)


if __name__ == "__main__":
    main()
