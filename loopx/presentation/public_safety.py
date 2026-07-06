from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


PUBLIC_SAFE_BOUNDARY_FIELDS = (
    "raw_logs_recorded",
    "raw_transcripts_recorded",
    "raw_connector_payloads_recorded",
    "credential_values_recorded",
    "absolute_paths_recorded",
    "private_source_bodies_recorded",
)

LOCAL_PATH_PATTERNS = (
    re.compile(r"/(?:Users|home|private|tmp|var)/[^\s`|,)]+"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\s`|,)]+"),
)


def public_safe_boundary() -> dict[str, bool]:
    return {field: False for field in PUBLIC_SAFE_BOUNDARY_FIELDS}


def redact_public_text(
    value: Any,
    *,
    limit: int,
    replacements: Mapping[str, str] | None = None,
    truncation_marker: str = "...",
) -> str:
    text = str(value or "").strip()
    for source, target in (replacements or {}).items():
        text = text.replace(source, target)
    for pattern in LOCAL_PATH_PATTERNS:
        text = pattern.sub("<local-path-redacted>", text)
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + truncation_marker
    return text
