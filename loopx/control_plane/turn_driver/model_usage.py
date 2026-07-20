"""Provider usage normalization and compact LoopX Turn usage receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION = "loopx_turn_model_usage_v0"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def normalize_provider_usage(value: Any) -> dict[str, int] | None:
    """Normalize one provider event and reject internally inconsistent totals."""
    if not isinstance(value, Mapping):
        return None
    aliases = {
        "input_tokens": ("input_tokens", "inputTokens"),
        "cache_tokens": (
            "cached_input_tokens",
            "cachedInputTokens",
            "cache_tokens",
        ),
        "output_tokens": ("output_tokens", "outputTokens"),
        "reasoning_output_tokens": (
            "reasoning_output_tokens",
            "reasoningOutputTokens",
        ),
        "total_tokens": ("total_tokens", "totalTokens"),
    }
    usage: dict[str, int] = {}
    for target, candidates in aliases.items():
        for candidate in candidates:
            parsed = _non_negative_int(value.get(candidate))
            if parsed is not None:
                usage[target] = parsed
                break
    if "input_tokens" not in usage or "output_tokens" not in usage:
        return None
    expected_total = usage["input_tokens"] + usage["output_tokens"]
    if usage.get("total_tokens", expected_total) != expected_total:
        return None
    usage["total_tokens"] = expected_total
    return usage


def event_usage(event: Mapping[str, Any]) -> dict[str, int] | None:
    for candidate in (event.get("usage"), event.get("tokenUsage")):
        usage = normalize_provider_usage(candidate)
        if usage is not None:
            return usage
    payload = _mapping(event.get("payload"))
    info = _mapping(payload.get("info"))
    for candidate in (
        info.get("last_token_usage"),
        info.get("lastTokenUsage"),
        info.get("total_token_usage"),
        info.get("totalTokenUsage"),
    ):
        usage = normalize_provider_usage(candidate)
        if usage is not None:
            return usage
    return None


def direct_model_usage(executor: Mapping[str, int]) -> dict[str, Any]:
    compact = dict(executor)
    return {
        "schema_version": LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION,
        "mode": "direct",
        "advisor_applied": False,
        "executor": compact,
        "total": dict(compact),
    }


def advisor_model_usage(
    *,
    advisor: Mapping[str, int],
    executor: Mapping[str, int],
    advice: Mapping[str, Any],
) -> dict[str, Any]:
    keys = set(advisor) | set(executor)
    total = {
        key: int(advisor.get(key, 0)) + int(executor.get(key, 0))
        for key in sorted(keys)
    }
    digest = hashlib.sha256(
        json.dumps(
            dict(advice),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION,
        "mode": "advisor",
        "advisor_applied": True,
        "advisor": dict(advisor),
        "executor": dict(executor),
        "total": total,
        "advice_digest": f"sha256:{digest}",
    }
