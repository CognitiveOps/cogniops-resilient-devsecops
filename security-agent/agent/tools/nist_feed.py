"""NIST feed ingestion — NVD API v2 + SP 800-53 CPRT.

Deterministic tool: fetches structured data from NIST public APIs,
parses responses, and returns typed FeedEntry objects.

Rate limits:
  - NVD API v2: 5 req/30s (no key), 50 req/30s (with API key)
  - CPRT: no documented limit, use conservative pacing

Fail-safe: API errors → empty list + warning log (never raises).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from models.schemas import ControlDetail, FeedEntry, FeedSource

logger = logging.getLogger("security-agent.nist_feed")

# ── API Endpoints ────────────────────────────────────────────────────

NIST_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NIST_CPRT_BASE = (
    "https://csrc.nist.gov/extensions/nudp/services/json/nudp"
    "/framework/version/sp_800_53_5_1_1"
)
NIST_CPRT_ELEMENTS = f"{NIST_CPRT_BASE}/element"

# Optional API key for higher NVD rate limit
NIST_API_KEY = os.getenv("NIST_API_KEY", "")

# HTTP timeout (seconds)
_TIMEOUT = 30.0

# Controls we track (from control-mappings.yaml)
TRACKED_CONTROLS = frozenset({"CM-3", "CP-10", "SI-3", "IR-6"})


# ── NVD API v2 ───────────────────────────────────────────────────────


async def fetch_nvd_updates(
    since: datetime,
    tracked_keywords: frozenset[str] | None = None,
) -> list[FeedEntry]:
    """Fetch CVEs from NVD API v2 modified since *since*.

    Filters results to those relevant to our tracked controls
    (matching by keyword in description or references).
    Returns empty list on any API error.
    """
    if tracked_keywords is None:
        tracked_keywords = TRACKED_CONTROLS

    params: dict[str, Any] = {
        "lastModStartDate": since.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "lastModEndDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000"),
        "resultsPerPage": 100,
    }
    headers: dict[str, str] = {}
    if NIST_API_KEY:
        headers["apiKey"] = NIST_API_KEY

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(NIST_NVD_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("NVD API fetch failed: %s", exc)
        return []

    entries: list[FeedEntry] = []
    for vuln in data.get("vulnerabilities", []):
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "")
        descriptions = cve.get("descriptions", [])
        desc_en = next(
            (d.get("value", "") for d in descriptions if d.get("lang") == "en"),
            "",
        )

        # Check relevance: does any tracked keyword appear?
        text_blob = f"{cve_id} {desc_en}".upper()
        relevant = any(kw.upper() in text_blob for kw in tracked_keywords)
        if not relevant:
            continue

        published = cve.get("published")
        pub_dt = (
            datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published
            else None
        )

        entries.append(
            FeedEntry(
                source=FeedSource.NIST_NVD,
                ref_id=cve_id,
                current_revision="",
                latest_revision=cve.get("lastModified", ""),
                change_summary=desc_en[:500],
                published_at=pub_dt,
            )
        )

    logger.info(
        "NVD API returned %d CVEs, %d relevant",
        len(data.get("vulnerabilities", [])),
        len(entries),
    )
    return entries


# ── SP 800-53 CPRT ───────────────────────────────────────────────────


async def fetch_sp800_53_controls(
    tracked: frozenset[str] | None = None,
) -> list[FeedEntry]:
    """Fetch current SP 800-53 control definitions from NIST CPRT.

    Filters to only the controls referenced in our control-mappings.yaml.
    Returns empty list on any API error.
    """
    if tracked is None:
        tracked = TRACKED_CONTROLS

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(NIST_CPRT_ELEMENTS)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("CPRT API fetch failed: %s", exc)
        return []

    elements = data if isinstance(data, list) else data.get("elements", [])

    entries: list[FeedEntry] = []
    for el in elements:
        el_id = el.get("element_identifier", "")
        if el_id not in tracked:
            continue

        entries.append(
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id=f"SP 800-53 {el_id}",
                current_revision="",  # filled by diff engine
                latest_revision=el.get("revision", el.get("version", "")),
                change_summary=el.get("element_name", ""),
                published_at=None,
            )
        )

    logger.info(
        "CPRT API returned %d elements, %d tracked", len(elements), len(entries)
    )
    return entries


# ── Control Detail Fetch ─────────────────────────────────────────────


async def fetch_control_detail(control_id: str) -> ControlDetail | None:
    """Fetch full text of a specific SP 800-53 control from CPRT.

    Returns None on API error (fail-safe).
    """
    url = f"{NIST_CPRT_ELEMENTS}/{control_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            el = resp.json()
    except Exception as exc:
        logger.warning("CPRT detail fetch failed for %s: %s", control_id, exc)
        return None

    return ControlDetail(
        control_id=el.get("element_identifier", control_id),
        title=el.get("element_name", ""),
        full_text=el.get("element_text", el.get("description", "")),
        guidance=el.get("supplemental_guidance", ""),
        related_controls=el.get("related_controls", []),
        enhancements=[
            e.get("text", e.get("element_text", ""))
            for e in el.get("control_enhancements", [])
            if isinstance(e, dict)
        ],
    )


# ── Combined Ingestion ───────────────────────────────────────────────


async def ingest_feeds(since: datetime) -> list[FeedEntry]:
    """Run all feed fetches concurrently. Returns combined deduped entries."""
    nvd_task = fetch_nvd_updates(since)
    cprt_task = fetch_sp800_53_controls()

    nvd_entries, cprt_entries = await asyncio.gather(
        nvd_task, cprt_task, return_exceptions=True
    )

    all_entries: list[FeedEntry] = []
    if isinstance(nvd_entries, list):
        all_entries.extend(nvd_entries)
    else:
        logger.warning("NVD ingestion raised: %s", nvd_entries)

    if isinstance(cprt_entries, list):
        all_entries.extend(cprt_entries)
    else:
        logger.warning("CPRT ingestion raised: %s", cprt_entries)

    # Deduplicate by ref_id (keep latest)
    seen: dict[str, FeedEntry] = {}
    for entry in all_entries:
        existing = seen.get(entry.ref_id)
        if existing is None or (
            entry.published_at
            and existing.published_at
            and entry.published_at > existing.published_at
        ):
            seen[entry.ref_id] = entry
    return list(seen.values())
