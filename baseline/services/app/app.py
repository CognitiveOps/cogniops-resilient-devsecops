"""Baseline FastAPI application providing a status endpoint."""
from fastapi import FastAPI
app = FastAPI()


@app.get("/status")
def status():
    """Return service status and basic health indicator."""
    return {"ok": True, "service": "baseline-app"}
