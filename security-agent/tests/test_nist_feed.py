"""Tests for NIST feed ingestion — security-agent/agent/tools/nist_feed.py.

All external API calls are mocked.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agent.tools.nist_feed import (
    NIST_CPRT_ELEMENTS,
    NIST_NVD_URL,
    TRACKED_CONTROLS,
    fetch_control_detail,
    fetch_nvd_updates,
    fetch_sp800_53_controls,
    ingest_feeds,
)
from models.schemas import FeedSource


# ── Fixtures ─────────────────────────────────────────────────────────


def _mock_nvd_response(cves: list[dict]) -> httpx.Response:
    """Build a mock NVD API response."""
    return httpx.Response(
        status_code=200,
        json={"vulnerabilities": cves, "totalResults": len(cves)},
        request=httpx.Request("GET", NIST_NVD_URL),
    )


def _mock_cprt_response(elements: list[dict]) -> httpx.Response:
    """Build a mock CPRT API response."""
    return httpx.Response(
        status_code=200,
        json=elements,
        request=httpx.Request("GET", NIST_CPRT_ELEMENTS),
    )


def _make_cve(
    cve_id: str, description: str, published: str = "2026-03-14T00:00:00Z"
) -> dict:
    return {
        "cve": {
            "id": cve_id,
            "descriptions": [{"lang": "en", "value": description}],
            "published": published,
            "lastModified": "2026-03-14T12:00:00Z",
        }
    }


def _make_element(el_id: str, name: str, revision: str = "5.1.1") -> dict:
    return {
        "element_identifier": el_id,
        "element_name": name,
        "revision": revision,
        "element_text": f"Full text of {el_id}...",
        "supplemental_guidance": f"Guidance for {el_id}",
        "related_controls": [],
        "control_enhancements": [],
    }


# ── NVD API Tests ────────────────────────────────────────────────────


class TestFetchNVDUpdates:
    @pytest.mark.asyncio
    async def test_relevant_cve_returned(self):
        """CVE mentioning CM-3 should be included."""
        cves = [_make_cve("CVE-2026-99999", "Flaw in CM-3 configuration control")]
        mock_resp = _mock_nvd_response(cves)

        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_nvd_updates(
                since=datetime(2026, 3, 1, tzinfo=timezone.utc)
            )

        assert len(entries) == 1
        assert entries[0].source == FeedSource.NIST_NVD
        assert entries[0].ref_id == "CVE-2026-99999"

    @pytest.mark.asyncio
    async def test_irrelevant_cve_filtered(self):
        """CVE not mentioning any tracked control should be excluded."""
        cves = [_make_cve("CVE-2026-00001", "Unrelated buffer overflow in widget")]
        mock_resp = _mock_nvd_response(cves)

        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_nvd_updates(
                since=datetime(2026, 3, 1, tzinfo=timezone.utc)
            )

        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty(self):
        """NVD API failure should return empty list, not raise."""
        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_nvd_updates(
                since=datetime(2026, 3, 1, tzinfo=timezone.utc)
            )

        assert entries == []

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """Empty NVD response should return empty list."""
        mock_resp = _mock_nvd_response([])

        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_nvd_updates(
                since=datetime(2026, 3, 1, tzinfo=timezone.utc)
            )

        assert entries == []


# ── CPRT Tests ───────────────────────────────────────────────────────


class TestFetchSP80053Controls:
    @pytest.mark.asyncio
    async def test_tracked_controls_returned(self):
        """Only tracked controls should be returned."""
        elements = [
            _make_element("CM-3", "Configuration Change Control", "5.1.1"),
            _make_element("CP-10", "System Recovery", "5.1.1"),
            _make_element("AC-1", "Access Control Policy", "5.1.1"),  # not tracked
        ]
        mock_resp = _mock_cprt_response(elements)

        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_sp800_53_controls()

        assert len(entries) == 2
        ref_ids = {e.ref_id for e in entries}
        assert "SP 800-53 CM-3" in ref_ids
        assert "SP 800-53 CP-10" in ref_ids

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty(self):
        """CPRT failure should return empty list."""
        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            entries = await fetch_sp800_53_controls()

        assert entries == []


# ── Control Detail Tests ─────────────────────────────────────────────


class TestFetchControlDetail:
    @pytest.mark.asyncio
    async def test_detail_returned(self):
        el = _make_element("CM-3", "Configuration Change Control")
        mock_resp = httpx.Response(
            status_code=200,
            json=el,
            request=httpx.Request("GET", f"{NIST_CPRT_ELEMENTS}/CM-3"),
        )

        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            detail = await fetch_control_detail("CM-3")

        assert detail is not None
        assert detail.control_id == "CM-3"
        assert "Full text" in detail.full_text

    @pytest.mark.asyncio
    async def test_detail_failure_returns_none(self):
        with patch("agent.tools.nist_feed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "404",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(404),
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            detail = await fetch_control_detail("INVALID-99")

        assert detail is None


# ── Combined Ingestion Tests ─────────────────────────────────────────


class TestIngestFeeds:
    @pytest.mark.asyncio
    async def test_combined_deduplication(self):
        """Entries from both sources should be deduped by ref_id."""
        with (
            patch("agent.tools.nist_feed.fetch_nvd_updates") as mock_nvd,
            patch("agent.tools.nist_feed.fetch_sp800_53_controls") as mock_cprt,
        ):
            from models.schemas import FeedEntry, FeedSource

            mock_nvd.return_value = [
                FeedEntry(
                    source=FeedSource.NIST_NVD,
                    ref_id="CVE-2026-11111",
                    latest_revision="1.0",
                )
            ]
            mock_cprt.return_value = [
                FeedEntry(
                    source=FeedSource.NIST_SP800_53,
                    ref_id="SP 800-53 CM-3",
                    latest_revision="5.1.1",
                )
            ]

            entries = await ingest_feeds(datetime(2026, 3, 1, tzinfo=timezone.utc))

        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_partial_failure_returns_available(self):
        """If one source fails, the other source's entries are still returned."""
        with (
            patch("agent.tools.nist_feed.fetch_nvd_updates") as mock_nvd,
            patch("agent.tools.nist_feed.fetch_sp800_53_controls") as mock_cprt,
        ):
            from models.schemas import FeedEntry, FeedSource

            mock_nvd.side_effect = Exception("NVD down")
            mock_cprt.return_value = [
                FeedEntry(
                    source=FeedSource.NIST_SP800_53,
                    ref_id="SP 800-53 CM-3",
                    latest_revision="5.1.1",
                )
            ]

            entries = await ingest_feeds(datetime(2026, 3, 1, tzinfo=timezone.utc))

        assert len(entries) == 1
        assert entries[0].ref_id == "SP 800-53 CM-3"
