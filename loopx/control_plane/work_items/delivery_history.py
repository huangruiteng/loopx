"""Compact transport for the typed delivery-history read model, never a writer."""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from ..effect_runtime import effect_runtime_result


def _text(value: Any) -> str:
    # Preserve Python's legacy scalar/Enum transport without classifying prose.
    return str((value.value if isinstance(value, Enum) else value) or "")


def _bounded_text(text: str) -> str:
    # A non-whitespace invalid suffix survives downstream trim/normalization.
    # A raw prefix could end with spaces and alias a valid enum or identifier.
    return text if len(text) <= 128 else text[:128] + "!"


def _identifier_fact(value: Any) -> str:
    text = _text(value)
    # Keep one excess character as invalidity evidence, not a truncated valid id.
    # Whitespace-only bindings stay present for the exactly-one-scope check.
    return _bounded_text(text.strip()) or (" " if text else "")


def _run_facts(run: Mapping[str, Any]) -> dict[str, Any]:
    observation = run.get("progress_observation")
    compact_observation = None
    if isinstance(observation, Mapping):
        compact_observation = {
            **{key: _bounded_text(_text(observation.get(key))) for key in ("schema_version", "result_class")},
            **{key: _identifier_fact(observation.get(key)) for key in ("work_item_id", "blocker_id")},
        }
        evidence = observation.get("evidence_ids")
        compact_observation["evidence_ids"] = (
            [_identifier_fact(value) for value in evidence] if isinstance(evidence, list) else None
        )
    return {
        **{key: _bounded_text(_text(run.get(key)).strip()) for key in (
            "delivery_outcome", "delivery_batch_scale", "delivery_turn_kind",
        )},
        **{key: _identifier_fact(run.get(key)) for key in ("todo_id", "replan_obligation_id")},
        "outcome_followthrough_required": run.get("outcome_followthrough_required") is True,
        "progress_observation": compact_observation,
    }


def project_delivery_history(
    runs: list[dict[str, Any]], *, outcome_floor_configured: bool = False,
) -> dict[str, Any]:
    """Project a caller-selected history batch with one managed-runtime request.

    Do not send raw trajectories, evidence bodies, recommendations or profiles.
    The profile adapter passes only whether the legacy outcome floor is enabled.
    """
    result = effect_runtime_result("work_item.delivery_history.project", {
        "schema_version": "delivery_history_request_v0",
        "runs": [_run_facts(run) for run in runs],
        "outcome_floor_configured": outcome_floor_configured,
    })
    if (not isinstance(result, dict) or result.get("schema_version") != "delivery_history_v0"
        or not isinstance(result.get("runs"), list) or len(result["runs"]) != len(runs)):
        raise RuntimeError("TypeScript delivery history shape mismatch")
    for run, signal in zip(runs, result["runs"], strict=True):
        hint = signal["outcome_followthrough"]
        if hint is not None:
            # Display-only annotation after the decision; narrative never enters TS.
            hint["latest_classification"] = _text(run.get("classification")).strip()
    return result
