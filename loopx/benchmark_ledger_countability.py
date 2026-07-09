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
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _compact_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _compact_text(item)
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


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


def _round_success_observed(run: dict[str, Any]) -> bool:
    trace = run.get("round_reward_trace") if isinstance(run, dict) else {}
    if isinstance(trace, dict):
        if trace.get("success_observed") is True:
            return True
        for field in ("first_success_round", "best_round_passed", "final_round_passed"):
            value = trace.get(field)
            if value is True:
                return True
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                return True
        records = trace.get("records")
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict):
                    continue
                if record.get("passed") is True:
                    return True
                reward = _numeric_score_value(record.get("reward"))
                if reward is not None and reward >= 1:
                    return True
    if run.get("round_success_observed") is True:
        return True
    if _numeric_score_value(run.get("first_success_round")) is not None:
        return True
    return False


def _fallback_candidate_present(run: dict[str, Any]) -> bool:
    if official_score_bool_fallback_used(run):
        return True
    if run.get("official_score_bool_fallback_used") is not True:
        return False
    return isinstance(run.get("official_passed"), bool) or isinstance(
        run.get("passed"), bool
    )


def _fallback_label_values(run: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in (
        "repair_class",
        "score_failure_attribution",
        "failure_class",
        "first_blocker",
        "runner_return_status",
    ):
        text = _compact_text(run.get(key), limit=180).lower()
        if text:
            labels.append(text)
    for key in ("failure_labels", "failure_attribution_labels", "setup_blockers"):
        values = run.get(key)
        if not isinstance(values, list):
            continue
        for value in values[:16]:
            text = _compact_text(value, limit=180).lower()
            if text:
                labels.append(text)
    return labels


def official_score_bool_fallback_allowed(run: dict[str, Any]) -> bool:
    """Return true when a bool-only score can stand in for an official score.

    Some runners emit ``official_task_score.passed`` while their final official
    result is still missing because the closeout/transport step failed. When a
    compact round trace already proves task-facing success, that bool is a
    failure signal from finalization, not a trustworthy official score.
    """

    if not _fallback_candidate_present(run):
        return False

    labels = _fallback_label_values(run)
    if "skillsbench_codex_acp_post_success_finalization" in labels:
        return False

    score_status = _compact_text(
        run.get("official_score_status") or run.get("score_status"),
        limit=80,
    )
    closeout_failure = any(
        marker in label
        for label in labels
        for marker in ("jsonrpc", "transport", "finalization")
    )
    if score_status == "missing" and closeout_failure and _round_success_observed(run):
        return False

    return True


def _official_task_score_bool_passed(run: dict[str, Any]) -> bool | None:
    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    passed = official.get("passed")
    return passed if isinstance(passed, bool) else None


def _official_score_passed_bool_fallback(
    run: dict[str, Any],
) -> tuple[float | None, bool | None]:
    official_passed = _official_task_score_bool_passed(run)
    if isinstance(official_passed, bool):
        return (1.0 if official_passed else 0.0), official_passed

    score_status = _compact_text(
        run.get("official_score_status") or run.get("score_status"),
        limit=80,
    )
    if score_status not in {"completed", "passed", "failed"}:
        return None, None
    if _compact_text(run.get("runner_return_status"), limit=120) == (
        "failed_before_official_result"
    ):
        return None, None
    for key in ("official_passed", "passed"):
        value = run.get(key)
        if isinstance(value, bool):
            return (1.0 if value else 0.0), value
    return None, None


def _score_countability_label_values(run: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in (
        "score_failure_attribution",
        "failure_class",
        "attempt_failure_label",
        "attempt_failure_class",
        "first_blocker",
        "runner_return_status",
    ):
        text = _compact_text(run.get(key), limit=180)
        if text:
            labels.append(text)
    for key in ("failure_labels", "failure_attribution_labels", "setup_blockers"):
        labels.extend(_compact_list(run.get(key), limit=16))
    accounting = (
        run.get("attempt_accounting")
        if isinstance(run.get("attempt_accounting"), dict)
        else {}
    )
    for key in ("failure_label", "failure_class"):
        text = _compact_text(accounting.get(key), limit=180)
        if text:
            labels.append(text)
    return labels


def _completed_task_attempt_pass(run: dict[str, Any], score: float) -> bool:
    score_status = _compact_text(
        run.get("official_score_status") or run.get("score_status"),
        limit=80,
    )
    if score_status not in {"completed", "passed"} or score < 1:
        return False
    if (
        run.get("official_passed") is not True
        and _official_task_score_bool_passed(run) is not True
    ):
        return False
    signals = (
        run.get("solution_quality_signals")
        if isinstance(run.get("solution_quality_signals"), dict)
        else {}
    )
    activity = (
        signals.get("worker_activity")
        if isinstance(signals.get("worker_activity"), dict)
        else {}
    )
    return activity.get("task_facing_activity_observed") is True


def benchmark_run_official_score_countability(run: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a compact/ledger run's official score is aggregate-countable."""

    bool_fallback_candidate = official_score_bool_fallback_used(run) or run.get(
        "official_score_bool_fallback_used"
    ) is True
    bool_fallback_allowed = official_score_bool_fallback_allowed(run)
    score = _numeric_score_value(run.get("official_score"))
    if score is None:
        official = (
            run.get("official_task_score")
            if isinstance(run.get("official_task_score"), dict)
            else {}
        )
        score = _numeric_score_value(official.get("value"))
    if score is None and bool_fallback_allowed:
        score, _passed = _official_score_passed_bool_fallback(run)
    if score is None:
        return {"countable": False, "reason": "score_missing", "score": None}
    if bool_fallback_candidate and not bool_fallback_allowed:
        return {
            "countable": False,
            "reason": "official_score_bool_fallback_not_allowed",
            "score": None,
        }

    accounting = (
        run.get("attempt_accounting")
        if isinstance(run.get("attempt_accounting"), dict)
        else {}
    )
    completed_task_pass = _completed_task_attempt_pass(run, score)
    if not completed_task_pass and official_score_attempt_uncountable(
        run, accounting, bool_fallback_allowed
    ):
        return {
            "countable": False,
            "reason": "official_score_attempt_not_countable",
            "score": score,
        }

    score_status = _compact_text(
        run.get("official_score_status") or run.get("score_status"),
        limit=80,
    )
    if score_status == "missing" and bool_fallback_allowed:
        score_status = "failed" if score < 1 else "passed"
    if score_status and score_status not in {"completed", "passed", "failed"}:
        return {
            "countable": False,
            "reason": "official_score_status_not_countable",
            "score": score,
        }
    if not completed_task_pass and any(
        "uncountable" in label.lower()
        for label in _score_countability_label_values(run)
    ):
        return {
            "countable": False,
            "reason": "uncountable_attribution",
            "score": score,
        }
    if completed_task_pass:
        return {
            "countable": True,
            "reason": "countable_completed_task_attempt_pass",
            "score": score,
        }
    return {"countable": True, "reason": "countable_official_score", "score": score}


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

    if has_official_bool_score:
        return False

    return False
