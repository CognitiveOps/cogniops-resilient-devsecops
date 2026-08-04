from fastapi.testclient import TestClient
from baseline.services.edge_cv_app.app import app
import io
from PIL import Image


def test_status_ok():
    c = TestClient(app)
    r = c.get("/status")
    assert r.status_code == 200
    assert r.json()["healthy"] is True


def test_infer_rejects_invalid():
    c = TestClient(app)
    r = c.post("/infer", files={"file": ("x.jpg", b"not_an_image", "image/jpeg")})
    assert r.status_code == 400


def test_infer_accepts_image():
    c = TestClient(app)
    # create small blank image
    img = Image.new("RGB", (64, 64), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    r = c.post("/infer", files={"file": ("img.jpg", buf.read(), "image/jpeg")})
    assert r.status_code == 200
    js = r.json()
    assert js["ok"] is True
    assert "count" in js
