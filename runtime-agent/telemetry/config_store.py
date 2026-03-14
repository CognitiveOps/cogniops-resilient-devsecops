"""Live-loading config store with GCS fetch + TTL cache.

Replaces hardcoded policy_refs with externalized YAML from GCS.
Falls back to built-in defaults if GCS is unavailable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import yaml

logger = logging.getLogger("runtime-agent.config")

CONFIG_BUCKET = os.getenv("CONFIG_BUCKET", "")
CONTROL_MAPPINGS_PATH = "control-mappings/v1.yaml"
REFRESH_INTERVAL_SEC = int(os.getenv("CONFIG_REFRESH_SEC", "300"))  # 5 min default


class ConfigStore:
    """TTL-cached config fetcher from GCS."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._last_fetch: float = 0.0

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._last_fetch) > REFRESH_INTERVAL_SEC

    def _fetch_from_gcs(self, path: str) -> dict | None:
        """Fetch YAML config from GCS. Returns None on failure."""
        if not CONFIG_BUCKET:
            return None
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(CONFIG_BUCKET)
            blob = bucket.blob(path)
            content = blob.download_as_text()
            return yaml.safe_load(content)
        except Exception as exc:
            logger.warning("GCS config fetch failed (%s): %s", path, exc)
            return None

    def get_control_mappings(self) -> dict[str, list[str]]:
        """Return decision->refs mapping, refreshing if stale.

        Falls back to built-in defaults (policy_refs._CONTROL_MAP) if GCS unavailable.
        """
        if self._is_stale():
            data = self._fetch_from_gcs(CONTROL_MAPPINGS_PATH)
            if data and "mappings" in data:
                # Flatten to simple ref strings for backward compat
                result: dict[str, list[str]] = {}
                for decision, entries in data["mappings"].items():
                    if isinstance(entries, list):
                        result[decision] = [
                            e["ref"] for e in entries if isinstance(e, dict) and "ref" in e
                        ]
                    else:
                        result[decision] = []
                self._cache = result
                self._last_fetch = time.monotonic()
                logger.info(
                    "Control mappings refreshed from GCS (version=%s)",
                    data.get("schema_version", "?"),
                )

        if self._cache:
            return self._cache

        # Fallback to built-in hardcoded defaults
        from models.schemas import DecisionType
        from telemetry.policy_refs import _CONTROL_MAP

        return {dt.value: list(_CONTROL_MAP.get(dt, [])) for dt in DecisionType}


# Singleton instance
config_store = ConfigStore()
