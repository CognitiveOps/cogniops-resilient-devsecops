"""Pytest configuration for security-agent tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure security-agent/ is on sys.path for imports
_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))
