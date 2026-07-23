"""Public-safe identity helpers shared by LoopX turn entrypoints."""

from __future__ import annotations

import re


TURN_INSTANCE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def normalize_turn_instance_id(value: str | None) -> str | None:
    normalized = str(value).strip() if value is not None else None
    if normalized is not None and not TURN_INSTANCE_ID_RE.fullmatch(normalized):
        raise ValueError(
            "turn_instance_id must be 1-128 public-safe letters, numbers, or ._:-"
        )
    return normalized
