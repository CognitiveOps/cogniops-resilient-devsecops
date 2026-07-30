"""
Unit tests for the Execution module.

Spec: decision → executed=False (Phase 0 shadow mode)
  - decision_executed = False
  - log_message is non-empty
"""

from __future__ import annotations

from execution.executor import execute


class TestExecute:
    """Tests for execute()."""

    def test_decision_not_executed(self, sample_decision, sample_verdict):
        """Phase 0: decision_executed is always False."""
        result = execute(sample_decision, sample_verdict)

        assert result.decision_executed is False

    def test_log_message_is_populated(self, sample_decision, sample_verdict):
        """Execution must produce a non-empty log message."""
        result = execute(sample_decision, sample_verdict)

        assert result.log_message != ""
        assert "NO_OP" in result.log_message
        assert "shadow mode" in result.log_message

    def test_log_contains_decision_details(self, sample_decision, sample_verdict):
        """Log message should include decision value and approval status."""
        result = execute(sample_decision, sample_verdict)

        assert "decision=NO_OP" in result.log_message
        assert "approved=True" in result.log_message
