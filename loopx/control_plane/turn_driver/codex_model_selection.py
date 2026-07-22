"""Experimental Codex model-pair resolution for LoopX Turn Advisor auto mode."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any


LOOPX_TURN_MODEL_SELECTION_SCHEMA_VERSION = "loopx_turn_model_selection_v0"
_MODEL_SELECTION_FIELDS = (
    "schema_version",
    "requested_mode",
    "profile_id",
    "advisor_model",
    "executor_model",
    "selection_reason",
)
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}$")
_SELECTION_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

_EXPERIMENTAL_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "profile_id": "experimental-codex-sol-luna-v1",
        "advisor_model": "gpt-5.6-sol",
        "executor_model": "gpt-5.6-luna",
        "priority": 100,
    },
)


def normalize_codex_model_selection(value: Any) -> dict[str, str]:
    """Validate and compact a public-safe auto-selection receipt."""
    if not isinstance(value, Mapping) or set(value) != set(_MODEL_SELECTION_FIELDS):
        raise ValueError("invalid model_selection fields")
    normalized = {key: str(value.get(key) or "") for key in _MODEL_SELECTION_FIELDS}
    if normalized["schema_version"] != LOOPX_TURN_MODEL_SELECTION_SCHEMA_VERSION:
        raise ValueError("unsupported model_selection schema_version")
    if normalized["requested_mode"] != "auto":
        raise ValueError("model_selection requested_mode must be auto")
    if not _SELECTION_LABEL_RE.fullmatch(normalized["profile_id"]):
        raise ValueError("invalid model_selection profile_id")
    if not _SELECTION_LABEL_RE.fullmatch(normalized["selection_reason"]):
        raise ValueError("invalid model_selection selection_reason")
    if not _MODEL_ID_RE.fullmatch(normalized["advisor_model"]):
        raise ValueError("invalid model_selection advisor_model")
    if not _MODEL_ID_RE.fullmatch(normalized["executor_model"]):
        raise ValueError("invalid model_selection executor_model")
    if normalized["advisor_model"] == normalized["executor_model"]:
        raise ValueError("model_selection models must be distinct")
    return normalized


def _available_model_slugs(value: Any) -> frozenset[str]:
    if not isinstance(value, Mapping):
        return frozenset()
    models = value.get("models")
    if not isinstance(models, list):
        return frozenset()
    return frozenset(
        slug
        for item in models
        if isinstance(item, Mapping)
        and isinstance((slug := item.get("slug")), str)
        and slug
    )


def resolve_auto_codex_model_selection(
    codex_bin: str | Path,
) -> dict[str, str]:
    """Select the highest-priority experimental pair present in Codex's catalog."""
    try:
        completed = subprocess.run(
            [str(codex_bin), "debug", "models"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("codex_advisor_auto_catalog_unavailable") from exc
    if completed.returncode != 0:
        raise ValueError("codex_advisor_auto_catalog_unavailable")
    try:
        available = _available_model_slugs(json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise ValueError("codex_advisor_auto_catalog_unavailable") from exc
    candidates = [
        profile
        for profile in _EXPERIMENTAL_PROFILES
        if profile["advisor_model"] in available
        and profile["executor_model"] in available
    ]
    if not candidates:
        raise ValueError("codex_advisor_auto_no_qualified_model_pair")
    selected = max(candidates, key=lambda item: (int(item["priority"]), item["profile_id"]))
    return normalize_codex_model_selection(
        {
            "schema_version": LOOPX_TURN_MODEL_SELECTION_SCHEMA_VERSION,
            "requested_mode": "auto",
            "profile_id": str(selected["profile_id"]),
            "advisor_model": str(selected["advisor_model"]),
            "executor_model": str(selected["executor_model"]),
            "selection_reason": "highest_priority_available_experimental_pair",
        }
    )
