"""
Unit tests for the POST /events/runtime endpoint.

Spec: full Pub/Sub push message → 200 + correct pipeline output
  - Valid message → 200, decision=NO_OP, mode=shadow, decision_executed=false
  - Invalid envelope → 400
  - Invalid base64 → 400
  - Invalid event schema → 400
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.conftest import SAMPLE_EVENT_DICT, SAMPLE_EVENT_NO_SCENARIO, make_pubsub_body


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
class TestEndpoint:
    """Integration tests for POST /events/runtime."""

    async def test_valid_event_returns_200(self):
        """Full Pub/Sub push → 200 with correct pipeline output."""
        body = make_pubsub_body(SAMPLE_EVENT_DICT)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("main.write_decision", return_value=True):
                resp = await client.post("/events/runtime", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == "b3f0a9c1-1234-4567-8901-abcdef123456"
        assert data["decision"] == "NO_OP"
        assert data["decision_executed"] is False
        assert data["mode"] == "shadow"
        assert "processed_at" in data
        assert "agentops_trace_id" in data

    async def test_valid_event_no_scenario_returns_200(self):
        """Event without scenario_id still processes successfully."""
        body = make_pubsub_body(SAMPLE_EVENT_NO_SCENARIO)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("main.write_decision", return_value=True):
                resp = await client.post("/events/runtime", json=body)

        assert resp.status_code == 200
        assert resp.json()["decision"] == "NO_OP"

    async def test_invalid_envelope_returns_400(self):
        """Missing 'message' key → 400 (non-retryable)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/events/runtime", json={"bad": "data"})

        assert resp.status_code == 400
        assert "invalid_pubsub_envelope" in resp.json()["detail"]["error"]

    async def test_invalid_base64_returns_400(self):
        """Bad base64 in message.data → 400."""
        body = {
            "message": {
                "data": "not-valid-base64!!!",
                "messageId": "msg-001",
            }
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/events/runtime", json=body)

        assert resp.status_code == 400

    async def test_invalid_event_schema_returns_400(self):
        """Valid base64 but invalid event (missing required fields) → 400."""
        import base64
        import json

        bad_event = {"event_id": "x"}  # missing event_type, occurred_at, source, context
        encoded = base64.b64encode(json.dumps(bad_event).encode()).decode()
        body = {"message": {"data": encoded}}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/events/runtime", json=body)

        assert resp.status_code == 400
        assert "invalid_event_schema" in resp.json()["detail"]["error"]

    async def test_healthz_returns_ok(self):
        """GET /healthz → 200 with shadow mode info."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/healthz")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["mode"] == "shadow"
        assert data["phase"] == 0
