"""Diff engine — compares current control-mappings.yaml against NIST feed data.

100% deterministic: no LLM, no external API calls.
Produces an EnrichedDiffReport with full control text for relevant changes.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from models.schemas import (
    DiffReport,
    EnrichedEntry,
    FeedEntry,
    FeedSource,
)

logger = logging.getLogger("security-agent.diff_engine")

# Map of base control IDs to their decision types in our YAML
# e.g. {"CM-3": "BLOCK", "CP-10": "ROLLBACK", ...}
_REF_PATTERN = re.compile(
    r"(?:SP 800-53|NIST SP 800-53)\s+([A-Z]{2}-\d+)", re.IGNORECASE
)


def _extract_base_ref(ref_id: str) -> str | None:
    """Extract base control ID (e.g. 'CM-3') from a ref string."""
    m = _REF_PATTERN.search(ref_id)
    return m.group(1) if m else None


def _build_ref_index(
    yaml_mappings: dict[str, Any],
) -> dict[str, list[tuple[str, dict]]]:
    """Build an index: base_control_id → [(decision_type, ref_entry), ...]."""
    index: dict[str, list[tuple[str, dict]]] = {}
    for decision_type, refs in yaml_mappings.items():
        if not isinstance(refs, list):
            continue
        for ref_entry in refs:
            if not isinstance(ref_entry, dict) or "ref" not in ref_entry:
                continue
            base = _extract_base_ref(ref_entry["ref"])
            if base:
                index.setdefault(base, []).append((decision_type, ref_entry))
    return index


def compute_diff(
    feed_entries: list[FeedEntry],
    current_yaml: dict[str, Any],
) -> DiffReport:
    """Compare feed entries against current control-mappings.yaml.

    Classifies each entry as:
      - updated: ref exists in YAML but revision changed
      - new: ref does not exist in YAML but is relevant (SP 800-53 source)

    Args:
        feed_entries: Entries from NIST feed ingestion.
        current_yaml: Parsed control-mappings.yaml dict.

    Returns:
        DiffReport with new and updated entries (not yet enriched with full text).
    """
    mappings = current_yaml.get("mappings", {})
    ref_index = _build_ref_index(mappings)

    new_entries: list[EnrichedEntry] = []
    updated_entries: list[EnrichedEntry] = []
    affected_decisions: set[str] = set()

    for entry in feed_entries:
        base_ref = _extract_base_ref(entry.ref_id)

        if base_ref and base_ref in ref_index:
            # Known control — check if revision changed
            for decision_type, ref_entry in ref_index[base_ref]:
                current_rev = ref_entry.get("revision", "")
                if entry.latest_revision and entry.latest_revision != current_rev:
                    # Fill in current_revision for context
                    enriched_entry = entry.model_copy(
                        update={"current_revision": current_rev}
                    )
                    updated_entries.append(
                        EnrichedEntry(
                            feed_entry=enriched_entry,
                            change_highlights=(
                                f"{base_ref}: {current_rev!r} → {entry.latest_revision!r}"
                            ),
                        )
                    )
                    affected_decisions.add(decision_type)

        elif entry.source == FeedSource.NIST_SP800_53 and base_ref:
            # New relevant SP 800-53 control not yet in our YAML
            new_entries.append(
                EnrichedEntry(
                    feed_entry=entry,
                    change_highlights=f"New control: {entry.ref_id}",
                )
            )

        # NVD CVEs without a matching SP 800-53 ref are informational only
        # They don't produce diff entries but are logged
        elif entry.source == FeedSource.NIST_NVD:
            logger.debug("NVD CVE %s — informational only", entry.ref_id)

    logger.info(
        "Diff complete: %d updated, %d new, affecting %s",
        len(updated_entries),
        len(new_entries),
        sorted(affected_decisions) or "none",
    )

    return DiffReport(
        checked_at=datetime.now(timezone.utc),
        new_entries=new_entries,
        updated_entries=updated_entries,
        affected_decision_types=sorted(affected_decisions),
    )


async def enrich_diff(diff: DiffReport) -> DiffReport:
    """Enrich a DiffReport by fetching full control text for changed entries.

    Fetches from NIST CPRT only for SP 800-53 entries that have changes.
    NVD CVEs are NOT enriched (they're informational).
    """
    from agent.tools.nist_feed import fetch_control_detail

    all_entries = diff.updated_entries + diff.new_entries
    enriched_updated: list[EnrichedEntry] = []
    enriched_new: list[EnrichedEntry] = []

    for entry in all_entries:
        base_ref = _extract_base_ref(entry.feed_entry.ref_id)
        if base_ref and entry.feed_entry.source == FeedSource.NIST_SP800_53:
            detail = await fetch_control_detail(base_ref)
            if detail:
                entry = entry.model_copy(
                    update={
                        "new_full_text": detail.full_text,
                        "guidance": detail.guidance,
                        "related_controls": detail.related_controls,
                    }
                )

        if entry in diff.updated_entries or entry.feed_entry in [
            e.feed_entry for e in diff.updated_entries
        ]:
            enriched_updated.append(entry)
        else:
            enriched_new.append(entry)

    return DiffReport(
        checked_at=diff.checked_at,
        new_entries=enriched_new,
        updated_entries=enriched_updated,
        affected_decision_types=diff.affected_decision_types,
    )
