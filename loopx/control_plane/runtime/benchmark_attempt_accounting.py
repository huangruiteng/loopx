from __future__ import annotations

from typing import Any

from .public_safety import public_safe_compact_text


def compact_benchmark_attempt_accounting(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "lifecycle_phase",
        "failure_label",
        "failure_class",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "launcher_attempt_countable",
        "case_attempt_countable",
        "solver_attempt_countable",
        "verifier_attempt_countable",
        "official_score_attempt_countable",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    attempts = value.get("attempts")
    if isinstance(attempts, dict):
        compact_attempts: dict[str, Any] = {}
        for phase in (
            "launcher",
            "case",
            "solver",
            "verifier",
            "official_score",
        ):
            phase_value = attempts.get(phase)
            if not isinstance(phase_value, dict):
                continue
            compact_phase: dict[str, bool] = {}
            for field in ("attempted", "countable"):
                if isinstance(phase_value.get(field), bool):
                    compact_phase[field] = phase_value[field]
            if compact_phase:
                compact_attempts[phase] = compact_phase
        if compact_attempts:
            compact["attempts"] = compact_attempts
    return compact
