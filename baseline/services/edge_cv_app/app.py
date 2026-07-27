"""Re-export the FastAPI app defined in main.py for module-style imports."""
from __future__ import annotations

from .main import app

__all__ = ["app"]
