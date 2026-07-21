"""Provider usage normalization and compact LoopX Turn usage receipts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any


LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION = "loopx_turn_model_usage_v0"
MODEL_USAGE_KEYS = {
    "input_tokens",
    "cache_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}


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


def normalize_model_usage_receipt(
    value: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one compact Turn usage receipt and return bounded errors."""
    errors: list[str] = []
    if value is None:
        return None, errors
    if not isinstance(value, Mapping):
        return None, ["model_usage must be an object"]
    allowed = {
        "schema_version",
        "mode",
        "advisor_applied",
        "advisor",
        "executor",
        "total",
        "advice_digest",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append("unsupported model_usage fields: " + ", ".join(unknown))
    if value.get("schema_version") != LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION:
        errors.append("unsupported model_usage schema_version")
    mode = str(value.get("mode") or "")
    if mode not in {"direct", "advisor"}:
        errors.append("model_usage mode must be direct or advisor")
    advisor_applied = value.get("advisor_applied")
    if not isinstance(advisor_applied, bool) or advisor_applied != (mode == "advisor"):
        errors.append("model_usage advisor_applied must match mode")

    phases = ["executor"] if mode == "direct" else ["advisor", "executor"]
    normalized_phases: dict[str, dict[str, int]] = {}
    for phase in phases:
        raw = value.get(phase)
        if not isinstance(raw, Mapping):
            errors.append(f"model_usage {phase} must be an object")
            continue
        phase_unknown = sorted(set(raw) - MODEL_USAGE_KEYS)
        if phase_unknown:
            errors.append(
                f"unsupported model_usage {phase} fields: " + ", ".join(phase_unknown)
            )
        compact: dict[str, int] = {}
        for key, item in raw.items():
            if key not in MODEL_USAGE_KEYS:
                continue
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                errors.append(f"model_usage {phase}.{key} must be a non-negative integer")
                continue
            compact[key] = item
        if not {"input_tokens", "output_tokens", "total_tokens"}.issubset(compact):
            errors.append(
                f"model_usage {phase} requires input_tokens, output_tokens, and total_tokens"
            )
        elif compact["total_tokens"] != compact["input_tokens"] + compact["output_tokens"]:
            errors.append(
                f"model_usage {phase}.total_tokens must equal input_tokens plus output_tokens"
            )
        normalized_phases[phase] = compact

    raw_total = value.get("total")
    if not isinstance(raw_total, Mapping):
        errors.append("model_usage total must be an object")
        normalized_total: dict[str, int] = {}
    else:
        normalized_total = {}
        total_unknown = sorted(set(raw_total) - MODEL_USAGE_KEYS)
        if total_unknown:
            errors.append("unsupported model_usage total fields: " + ", ".join(total_unknown))
        for key, item in raw_total.items():
            if key not in MODEL_USAGE_KEYS:
                continue
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                errors.append(f"model_usage total.{key} must be a non-negative integer")
                continue
            normalized_total[key] = item
    for key in MODEL_USAGE_KEYS:
        expected = sum(phase.get(key, 0) for phase in normalized_phases.values())
        if expected or key in normalized_total:
            if normalized_total.get(key) != expected:
                errors.append(f"model_usage total.{key} must equal phase usage sum")

    normalized: dict[str, Any] = {
        "schema_version": LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION,
        "mode": mode,
        "advisor_applied": advisor_applied,
        **normalized_phases,
        "total": normalized_total,
    }
    advice_digest = str(value.get("advice_digest") or "")
    if advice_digest:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", advice_digest):
            errors.append("model_usage advice_digest must be a sha256 digest")
        else:
            normalized["advice_digest"] = advice_digest
    return normalized, errors
