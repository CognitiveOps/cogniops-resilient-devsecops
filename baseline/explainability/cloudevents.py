#!/usr/bin/env python3
"""
CloudEvents v1.0 helpers.

Spec: https://github.com/cloudevents/spec
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_cloudevent(
    *,
    source: str,
    type: str,
    data: Dict[str, Any],
    subject: Optional[str] = None,
    event_id: Optional[str] = None,
    time: Optional[str] = None,
    datacontenttype: str = "application/json",
    extensions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a CloudEvents v1.0 JSON envelope.
    """
    evt: Dict[str, Any] = {
        "specversion": "1.0",
        "id": event_id or str(uuid.uuid4()),
        "source": source,
        "type": type,
        "time": time or utc_now_iso(),
        "datacontenttype": datacontenttype,
        "data": data or {},
    }
    if subject:
        evt["subject"] = subject
    if extensions:
        for k, v in extensions.items():
            if k in evt:
                continue
            evt[k] = v
    return evt

