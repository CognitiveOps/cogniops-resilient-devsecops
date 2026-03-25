"""
Tests for OPA policy guard callback (Step 4).

- OPA allow → guard returns None (tool executes)
- OPA deny → guard returns block dict
- OPA unreachable → guard returns block dict (fail-closed)
- Observation tools → always pass through
- Unknown tools → always blocked
- PQC check for S4/SS2 scenarios
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.callbacks.guard_callback import (
    _EXECUTION_TOOLS,
    _OBSERVATION_TOOLS,
    _run_opa_check,
    _run_pqc_check,
    guard_callback,
)
from agent.callbacks.opa_client import OpaResult, build_opa_input


# ── OPA input construction ───────────────────────────────────────────


class TestBuildOpaInput:
    """Verify OPA input document construction."""

    def test_basic_input(self):
        result = build_opa_input(
            action="block_deployment",
            args={"rationale": "test", "target": "deploy-123"},
            session_state={"scenario": "S1", "severity": 0.9},
        )
        assert result["action"] == "block_deployment"
        assert result["scenario"] == "S1"
        assert result["severity"] == 0.9
        assert result["args"]["target"] == "deploy-123"

    def test_defaults_without_state(self):
        result = build_opa_input(action="no_action", args={})
        assert result["scenario"] == "unknown"
        assert result["severity"] == 0.5
        assert result["risk_score"] == 0.5

    def test_mode_from_env(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")
        result = build_opa_input(action="rollback_deployment", args={})
        assert result["mode"] == "enforce"


# ── OPA eval mock tests ─────────────────────────────────────────────


class TestOpaCheck:
    """Verify OPA check logic with mocked opa_eval."""

    @pytest.mark.asyncio
    async def test_opa_allow(self):
        """OPA returns no denials → check returns None (allow)."""
        with patch(
            "agent.callbacks.opa_client.opa_eval",
            new_callable=AsyncMock,
            return_value=OpaResult(allowed=True),
        ):
            result = await _run_opa_check(
                "block_deployment",
                {"rationale": "test"},
                {},
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_opa_deny(self):
        """OPA returns denials → check returns block dict."""
        with patch(
            "agent.callbacks.opa_client.opa_eval",
            new_callable=AsyncMock,
            return_value=OpaResult(allowed=False, denials=["region not allowed"]),
        ):
            result = await _run_opa_check(
                "block_deployment",
                {"rationale": "test"},
                {},
            )
        assert result is not None
        assert result["guard_blocked"] is True
        assert result["guard_reason"] == "opa_violation"
        assert "region not allowed" in result["rationale"]

    @pytest.mark.asyncio
    async def test_opa_unreachable(self):
        """OPA error → check returns block dict (fail-closed)."""
        with patch(
            "agent.callbacks.opa_client.opa_eval",
            new_callable=AsyncMock,
            return_value=OpaResult(allowed=False, error="connection refused"),
        ):
            result = await _run_opa_check(
                "rollback_deployment",
                {"rationale": "test"},
                {},
            )
        assert result is not None
        assert result["guard_blocked"] is True
        assert "connection refused" in result["rationale"]


# ── PQC check mock tests ────────────────────────────────────────────


class TestPqcCheck:
    """Verify PQC integrity check logic."""

    @pytest.mark.asyncio
    async def test_pqc_skip_non_s4_ss2(self):
        """PQC check skipped for non-S4/SS2 scenarios."""
        result = await _run_pqc_check({"scenario": "S1"})
        assert result is None

    @pytest.mark.asyncio
    async def test_pqc_skip_no_artifacts(self):
        """PQC check skipped when no artifact context."""
        result = await _run_pqc_check({"scenario": "S4"})
        assert result is None

    @pytest.mark.asyncio
    async def test_pqc_pass(self):
        """PQC verification passes → None."""
        with patch(
            "baseline.security.pqc.verify.verify_manifest",
            return_value=(True, "ok", "oqs", "Dilithium2"),
        ), patch(
            "baseline.security.pqc.verify.load_manifest",
            return_value={"image": "test:sha"},
        ), patch(
            "baseline.security.pqc.verify.load_bytes",
            return_value=b"fake",
        ):
            result = await _run_pqc_check(
                {
                    "scenario": "SS2",
                    "artifact_manifest": "/tmp/manifest.json",
                    "artifact_signature": "/tmp/sig",
                    "artifact_public_key": "/tmp/pub",
                }
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_pqc_fail(self):
        """PQC verification fails → block dict."""
        with patch(
            "baseline.security.pqc.verify.verify_manifest",
            return_value=(False, "signature-mismatch", "oqs", "Dilithium2"),
        ), patch(
            "baseline.security.pqc.verify.load_manifest",
            return_value={"image": "test:sha"},
        ), patch(
            "baseline.security.pqc.verify.load_bytes",
            return_value=b"fake",
        ):
            result = await _run_pqc_check(
                {
                    "scenario": "S4",
                    "artifact_manifest": "/tmp/manifest.json",
                    "artifact_signature": "/tmp/sig",
                    "artifact_public_key": "/tmp/pub",
                }
            )
        assert result is not None
        assert result["guard_reason"] == "pqc_failure"
        assert "signature-mismatch" in result["rationale"]

    @pytest.mark.asyncio
    async def test_pqc_error_fail_closed(self):
        """PQC backend error → block dict (fail-closed)."""
        with patch(
            "baseline.security.pqc.verify.load_manifest",
            side_effect=FileNotFoundError("no file"),
        ):
            result = await _run_pqc_check(
                {
                    "scenario": "S4",
                    "artifact_manifest": "/tmp/nonexistent.json",
                    "artifact_signature": "/tmp/sig",
                    "artifact_public_key": "/tmp/pub",
                }
            )
        assert result is not None
        assert result["guard_reason"] == "pqc_error"


# ── Full guard_callback tests ───────────────────────────────────────


class TestGuardCallback:
    """End-to-end guard callback with mocked OPA."""

    def _make_tool(self, name: str) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        return tool

    def _make_context(self, state: dict | None = None) -> MagicMock:
        ctx = MagicMock()
        ctx.state = state or {}
        return ctx

    def test_observation_tool_passes(self):
        """Observation tools (perceive_anomaly) are always allowed."""
        result = guard_callback(
            tool=self._make_tool("perceive_anomaly"),
            args={},
            tool_context=self._make_context(),
        )
        assert result is None

    def test_unknown_tool_blocked(self):
        """Unknown tools are blocked."""
        result = guard_callback(
            tool=self._make_tool("dangerous_tool"),
            args={},
            tool_context=self._make_context(),
        )
        assert result is not None
        assert result["guard_reason"] == "unknown_tool"

    def test_execution_tool_opa_allow(self):
        """Execution tool + OPA allow → None."""
        with patch(
            "agent.callbacks.guard_callback._async_guard",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = guard_callback(
                tool=self._make_tool("no_action"),
                args={"rationale": "test"},
                tool_context=self._make_context(),
            )
        assert result is None

    def test_execution_tool_opa_deny(self):
        """Execution tool + OPA deny → block dict."""
        block_result = {
            "action": "NO_OP",
            "rationale": "Guard blocked",
            "executed": False,
            "guard_blocked": True,
            "guard_reason": "opa_violation",
        }
        with patch(
            "agent.callbacks.guard_callback._async_guard",
            new_callable=AsyncMock,
            return_value=block_result,
        ):
            result = guard_callback(
                tool=self._make_tool("block_deployment"),
                args={"rationale": "policy violation"},
                tool_context=self._make_context(),
            )
        assert result is not None
        assert result["guard_blocked"] is True

    def test_all_observation_tools_pass(self):
        """All defined observation tools are let through."""
        for tool_name in _OBSERVATION_TOOLS:
            result = guard_callback(
                tool=self._make_tool(tool_name),
                args={},
                tool_context=self._make_context(),
            )
            assert result is None, f"{tool_name} should pass through"

    def test_all_execution_tools_known(self):
        """All execution tools are in the known set."""
        expected = {
            "no_action",
            "block_deployment",
            "rollback_deployment",
            "quarantine_artifact",
            "escalate_to_human",
        }
        assert _EXECUTION_TOOLS == expected
