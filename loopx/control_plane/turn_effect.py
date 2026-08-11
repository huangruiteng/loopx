"""Stable idempotency identities for irreversible Turn callbacks."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


# Mirrors task_lease without importing its history-dependent module here.
TURN_EFFECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:@/-]{1,160}$")


def normalize_turn_effect_key(value: str | None) -> str | None:
    key = str(value or "").strip()
    if not key:
        return None
    if not TURN_EFFECT_KEY_PATTERN.fullmatch(key):
        raise ValueError("turn_effect_key must be a public-safe token")
    return key


def turn_effect_input_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def find_turn_effect_record(
    index_path: Path,
    turn_effect_key: str,
) -> dict[str, Any] | None:
    if not index_path.exists():
        return None
    found: dict[str, Any] | None = None
    for line_number, line in enumerate(
        index_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"run index line {line_number} is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"run index line {line_number} must be an object")
        if value.get("turn_effect_key") != turn_effect_key:
            continue
        if found is not None and found != value:
            raise ValueError("turn effect key conflict")
        found = value
    return found


def require_matching_turn_effect(
    existing: Mapping[str, Any],
    effect_input_hash: str,
) -> None:
    if existing.get("effect_input_hash") != effect_input_hash:
        raise ValueError("turn effect key conflict")
