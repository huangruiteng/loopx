from __future__ import annotations

from typing import Any


def _compact_text(value: Any, *, limit: int = 160) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _numeric_score_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def official_score_bool_fallback_used(run: dict[str, Any]) -> bool:
    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    if not isinstance(official.get("passed"), bool):
        return False
    if _numeric_score_value(official.get("value")) is not None:
        return False
    if _numeric_score_value(run.get("official_score")) is not None:
        return False
    return True


def official_score_attempt_uncountable(
    run: dict[str, Any],
    accounting: dict[str, Any],
    has_official_bool_score: bool,
) -> bool:
    """Return true when a candidate official score came from a non-countable attempt."""

    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    if (
        _compact_text(official.get("kind"), limit=120)
        == "skillsbench_verifier_reward_missing"
        and _numeric_score_value(official.get("value")) is None
    ):
        return True

    explicit_attempt_countable = run.get("official_score_attempt_countable")
    if explicit_attempt_countable is None:
        explicit_attempt_countable = accounting.get("official_score_attempt_countable")
    if explicit_attempt_countable is False and not has_official_bool_score:
        return True

    lifecycle_phase = _compact_text(
        run.get("attempt_lifecycle_phase") or accounting.get("lifecycle_phase"),
        limit=120,
    )
    failure_scope = _compact_text(run.get("failure_scope"), limit=120)
    failure_class = _compact_text(
        run.get("score_failure_attribution")
        or run.get("failure_class")
        or accounting.get("failure_class")
        or accounting.get("failure_label"),
        limit=180,
    ).lower()
    if has_official_bool_score:
        return False

    if (
        failure_scope == "runner_or_setup"
        and lifecycle_phase in {"not_started", "runner_accepted_args"}
        and any(
            marker in failure_class
            for marker in ("runner", "setup", "preflight", "docker", "compose")
        )
    ):
        return True

    if failure_scope == "verifier_or_infra":
        return True

    return False
