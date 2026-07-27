"""evaluation.configs — load experiment_matrix.json and thresholds.json."""

from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def load_experiment_matrix() -> dict:
    """Load the experiment matrix configuration."""
    with open(_DIR / "experiment_matrix.json") as f:
        return json.load(f)


def load_thresholds() -> dict:
    """Load the statistical thresholds configuration."""
    with open(_DIR / "thresholds.json") as f:
        return json.load(f)
