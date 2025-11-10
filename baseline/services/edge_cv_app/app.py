import os

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import cv2
import numpy as np

app = FastAPI()

# Haar cascade shipped with OpenCV
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


@app.get("/status")
def status():
    """
    Health endpoint used by S2 (OTA) and S3 (resilience).

    - Normal mode (FAIL_MODE not set or "0"):
        returns HTTP 200, used for health checks.

    - Failure mode (FAIL_MODE="1"):
        returns HTTP 500 to simulate a broken deployment
        for S3 rollback / MTTD / MTTR measurements.
    """
    fail_mode = os.getenv("FAIL_MODE", "0")
    if fail_mode == "1":
        # Simulated failure for S3 scenario
        raise HTTPException(
            status_code=500,
            detail="Injected failure for S3 scenario (FAIL_MODE=1)",
        )

    return {"ok": True, "service": "edge_cv_app", "fail_mode": fail_mode}


@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    """
    Simple computer-vision inference endpoint:
    - Accepts an image file
    - Runs face detection using Haar cascades
    - Returns bounding boxes and count
    """
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
