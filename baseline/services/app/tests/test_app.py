from fastapi.testclient import TestClient
from baseline.services.app.app import app

def test_status_ok():
    c = TestClient(app)
    r = c.get("/status")
    assert r.status_code == 200
    assert r.json().get("ok") is True
