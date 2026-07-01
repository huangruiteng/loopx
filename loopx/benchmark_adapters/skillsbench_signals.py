from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _positive_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _compact_text(value: Any, *, limit: int = 160) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _compact_list(value: Any, *, limit: int = 16) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        text = _compact_text(item, limit=160)
        if not text:
            continue
        labels.append(text)
        if len(labels) >= limit:
            break
    return labels


def _timeline_events_by_name(timeline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    events = timeline.get("events") if isinstance(timeline.get("events"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = _compact_text(event.get("event"), limit=120)
        if name and name not in result:
            result[name] = event
    return result


def build_skillsbench_solution_quality_signals(
    benchmark_run: dict[str, Any],
) -> dict[str, Any]:
    """Summarize solution-level public signals without raw benchmark material."""

    if not isinstance(benchmark_run, dict):
        return {}
    official = (
        benchmark_run.get("official_task_score")
        if isinstance(benchmark_run.get("official_task_score"), dict)
        else {}
    )
    score_value = _number(official.get("value"))
    if score_value is None:
        score_value = _number(benchmark_run.get("official_score"))
    official_passed = official.get("passed")
    if not isinstance(official_passed, bool):
        official_passed = bool(score_value is not None and score_value >= 1)

    labels = _compact_list(benchmark_run.get("failure_attribution_labels"))
    counters = (
        benchmark_run.get("interaction_counters")
        if isinstance(benchmark_run.get("interaction_counters"), dict)
        else {}
    )
    timeline = (
        benchmark_run.get("case_event_timeline")
        if isinstance(benchmark_run.get("case_event_timeline"), dict)
        else {}
    )
    activity_event = _timeline_events_by_name(timeline).get("task_facing_activity", {})

    bridge_operation_count = _positive_int(
        activity_event.get("agent_bridge_task_facing_operation_count")
    ) or _positive_int(
        counters.get("remote_command_file_bridge_agent_task_facing_operation_count")
    )
    bridge_success_count = _positive_int(
        activity_event.get("agent_bridge_task_facing_success_count")
    ) or _positive_int(
        counters.get("remote_command_file_bridge_agent_task_facing_success_count")
    )
    tool_call_count = _positive_int(
        activity_event.get("acp_protocol_tool_call_count")
    ) or _positive_int(counters.get("private_trajectory_tool_call_count"))
    activity_status = (
        _compact_text(activity_event.get("status"), limit=120)
        or _compact_text(counters.get("host_local_acp_bridge_progress_status"), limit=120)
        or ""
    )
    task_activity_observed = bool(
        bridge_operation_count > 0
        or bridge_success_count > 0
        or tool_call_count > 0
        or benchmark_run.get("native_goal_worker_connected") is True
        or activity_status
        in {
            "task_activity_observed",
            "bridge_task_facing_success_observed",
            "agent_operation_trace_observed",
        }
    )

    if score_value is None:
        outcome_class = "missing_score"
    elif official_passed:
        outcome_class = "pass"
    elif score_value == 0:
        outcome_class = "official_zero"
    elif score_value < 1:
        outcome_class = "partial_nonpass"
    else:
        outcome_class = "nonpassing_unknown"

    solution_action_labels: list[str] = []
    if outcome_class == "official_zero":
        solution_action_labels.append(
            "official_zero_after_public_worker_activity"
            if task_activity_observed
            else "official_zero_without_public_worker_activity"
        )
    elif outcome_class == "partial_nonpass":
        solution_action_labels.append("partial_nonpass_official_score")
    elif outcome_class == "pass":
        solution_action_labels.append("official_pass")
    elif outcome_class == "missing_score":
        solution_action_labels.append("official_score_missing")

    runner_failure = (
        benchmark_run.get("runner_failure")
        if isinstance(benchmark_run.get("runner_failure"), dict)
        else {}
    )
    runner_failure_class = _compact_text(runner_failure.get("failure_class"), limit=140)
    if (
        "skillsbench_runner_interrupted_after_controller_reward_observation" in labels
        or runner_failure_class
        == "skillsbench_runner_interrupted_after_controller_reward_observation"
    ):
        solution_action_labels.append("runner_recovery_noise_recorded")
    if "partial_trajectory" in labels:
        solution_action_labels.append("partial_trajectory_public_label_present")

    rubric_miss_status = (
        "not_applicable_pass"
        if outcome_class == "pass"
        else (
            "score_missing"
            if outcome_class == "missing_score"
            else "not_available_from_compact_public_signals"
        )
    )
    if rubric_miss_status == "not_available_from_compact_public_signals":
        solution_action_labels.append("rubric_miss_labels_unavailable_compact_only")

    deduped_labels: list[str] = []
    for label in solution_action_labels:
        if label not in deduped_labels:
            deduped_labels.append(label)

    return {
        "schema_version": "skillsbench_solution_quality_signals_v0",
        "source": "compact_public_signals",
        "outcome_class": outcome_class,
        "solution_action_labels": deduped_labels,
        "rubric_miss_labels": [],
        "rubric_miss_label_status": rubric_miss_status,
        "worker_activity": {
            "task_facing_activity_observed": task_activity_observed,
            "worker_turn_or_bridge_observed": task_activity_observed,
            "tool_call_count": tool_call_count,
            "bridge_task_facing_operation_count": bridge_operation_count,
            "bridge_task_facing_success_count": bridge_success_count,
        },
        "public_limits": [
            "task_text_not_recorded",
            "trajectory_not_recorded",
            "verifier_output_not_recorded",
        ],
    }
