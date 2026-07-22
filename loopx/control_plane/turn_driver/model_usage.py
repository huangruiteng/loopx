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
ADVISOR_DECISIONS = {
    "skipped_simple",
    "applied_complexity",
    "fallback_failure",
}
ADVISOR_COMPLEXITY_SIGNALS = {
    "cross_file_reasoning",
    "ambiguous_root_cause",
    "invariant_risk",
    "validation_uncertainty",
    "external_contract",
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


def aggregate_provider_usage(*phases: Mapping[str, int]) -> dict[str, int]:
    keys = set().union(*(phase.keys() for phase in phases))
    return {
        key: sum(int(phase.get(key, 0)) for phase in phases)
        for key in sorted(keys)
    }


def advisor_decision_receipt(
    checkpoint: Mapping[str, Any],
    *,
    decision: str,
    failure_category: str | None = None,
) -> dict[str, Any]:
    digest = hashlib.sha256(
        json.dumps(
            dict(checkpoint),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    raw_signals = checkpoint.get("signals")
    signals = list(raw_signals) if isinstance(raw_signals, list) else []
    receipt = {
        "schema_version": "loopx_turn_advisor_decision_v0",
        "decision": decision,
        "signals": signals,
        "checkpoint_digest": f"sha256:{digest}",
    }
    if failure_category:
        receipt["failure_category"] = failure_category
    return receipt


def direct_model_usage(
    executor: Mapping[str, int],
    *,
    advisor_decision: Mapping[str, Any] | None = None,
    advisor_attempt: Mapping[str, int] | None = None,
    usage_complete: bool = True,
) -> dict[str, Any]:
    compact = dict(executor)
    total = (
        aggregate_provider_usage(compact, advisor_attempt)
        if advisor_attempt is not None
        else dict(compact)
    )
    receipt: dict[str, Any] = {
        "schema_version": LOOPX_TURN_MODEL_USAGE_SCHEMA_VERSION,
        "mode": "direct",
        "advisor_applied": False,
        "executor": compact,
        "total": total,
    }
    if advisor_decision is not None:
        receipt["advisor_decision"] = dict(advisor_decision)
    if advisor_attempt is not None:
        receipt["advisor_attempt"] = dict(advisor_attempt)
    if advisor_decision is not None or not usage_complete:
        receipt["usage_complete"] = usage_complete
    return receipt


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


def _normalize_usage_row(
    value: Any,
    *,
    phase: str,
    errors: list[str],
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        errors.append(f"model_usage {phase} must be an object")
        return {}
    unknown = sorted(set(value) - MODEL_USAGE_KEYS)
    if unknown:
        errors.append(f"unsupported model_usage {phase} fields: " + ", ".join(unknown))
    compact: dict[str, int] = {}
    for key, item in value.items():
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
    return compact


def _normalize_advisor_decision(
    value: Any,
    *,
    mode: str,
    usage_complete: Any,
    errors: list[str],
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        errors.append("model_usage advisor_decision must be an object")
        return None
    allowed = {
        "schema_version",
        "decision",
        "signals",
        "checkpoint_digest",
        "failure_category",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(
            "unsupported model_usage advisor_decision fields: " + ", ".join(unknown)
        )
    decision = str(value.get("decision") or "")
    signals = value.get("signals")
    digest = str(value.get("checkpoint_digest") or "")
    failure_category = str(value.get("failure_category") or "")
    if value.get("schema_version") != "loopx_turn_advisor_decision_v0":
        errors.append("unsupported model_usage advisor_decision schema_version")
    if decision not in ADVISOR_DECISIONS:
        errors.append("model_usage advisor_decision decision is invalid")
    if (
        not isinstance(signals, list)
        or any(signal not in ADVISOR_COMPLEXITY_SIGNALS for signal in signals)
        or len(signals) != len(set(signals))
    ):
        errors.append("model_usage advisor_decision signals are invalid")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        errors.append(
            "model_usage advisor_decision checkpoint_digest must be a sha256 digest"
        )
    if decision == "fallback_failure" and not failure_category:
        errors.append("model_usage fallback advisor_decision requires failure_category")
    if decision != "fallback_failure" and failure_category:
        errors.append("model_usage advisor_decision failure_category requires fallback")
    if decision == "applied_complexity" and mode != "advisor":
        errors.append("applied advisor_decision requires advisor mode")
    if decision != "applied_complexity" and mode != "direct":
        errors.append("skipped or fallback advisor_decision requires direct mode")
    if decision == "skipped_simple" and signals:
        errors.append("skipped advisor_decision cannot carry complexity signals")
    if decision in {"applied_complexity", "fallback_failure"} and not signals:
        errors.append("complex advisor_decision requires complexity signals")
    if decision != "fallback_failure" and usage_complete is not True:
        errors.append("applied or skipped advisor_decision requires complete usage")
    normalized = {
        "schema_version": "loopx_turn_advisor_decision_v0",
        "decision": decision,
        "signals": list(signals) if isinstance(signals, list) else [],
        "checkpoint_digest": digest,
    }
    if failure_category:
        normalized["failure_category"] = failure_category
    return normalized


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
        "advisor_decision",
        "advisor_attempt",
        "usage_complete",
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
    if "advisor_attempt" in value:
        phases.append("advisor_attempt")
    normalized_phases = {
        phase: _normalize_usage_row(value.get(phase), phase=phase, errors=errors)
        for phase in phases
    }
    normalized_total = _normalize_usage_row(
        value.get("total"), phase="total", errors=errors
    )
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

    usage_complete = value.get("usage_complete", True)
    if not isinstance(usage_complete, bool):
        errors.append("model_usage usage_complete must be a boolean")
    elif "usage_complete" in value:
        normalized["usage_complete"] = usage_complete

    raw_decision = value.get("advisor_decision")
    normalized_decision = _normalize_advisor_decision(
        raw_decision,
        mode=mode,
        usage_complete=usage_complete,
        errors=errors,
    )
    if normalized_decision is not None:
        normalized["advisor_decision"] = normalized_decision

    if "advisor_attempt" in value:
        decision = (
            str(raw_decision.get("decision") or "")
            if isinstance(raw_decision, Mapping)
            else ""
        )
        if mode != "direct" or decision != "fallback_failure":
            errors.append(
                "model_usage advisor_attempt requires a direct fallback decision"
            )
    if (
        isinstance(raw_decision, Mapping)
        and raw_decision.get("decision") == "fallback_failure"
        and usage_complete is True
        and "advisor_attempt" not in value
    ):
        errors.append(
            "complete fallback model_usage requires observed advisor_attempt usage"
        )
    return normalized, errors
