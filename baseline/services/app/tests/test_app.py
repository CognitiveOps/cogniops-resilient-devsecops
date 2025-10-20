from fastapi.testclient import TestClient
from baseline.services.app.app import app


def test_status_ok():
    """Ensure the /status endpoint responds with HTTP 200 and a JSON payload containing {'ok': True}."""
    c = TestClient(app)
    r = c.get("/status")
    assert r.status_code == 200
    assert r.json().get("ok") is True
