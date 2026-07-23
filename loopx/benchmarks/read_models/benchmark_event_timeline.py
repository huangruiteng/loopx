from __future__ import annotations

from typing import Any

from ...control_plane.runtime.public_safety import (
    public_safe_compact_list,
    public_safe_compact_text,
)


MAX_BENCHMARK_EVENT_LABELS = 5
MAX_BENCHMARK_EVENTS = 12


def compact_benchmark_case_event_timeline(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    events: list[dict[str, Any]] = []
    for raw_event in value.get("events", []):
        if not isinstance(raw_event, dict):
            continue
        event: dict[str, Any] = {}
        for field in ("phase", "event", "status"):
            text = public_safe_compact_text(raw_event.get(field), limit=120)
            if text:
                event[field] = text
        if not {"phase", "event", "status"} <= set(event):
            continue
        for field in (
            "execution_style",
            "agent_operation_trace_status",
            "host_local_acp_bridge_progress_status",
            "host_local_acp_bridge_progress_signal_source",
            "last_decision",
            "recovery_stage",
            "recovery_exception_type",
            "runner_failure_class",
            "official_score_status",
            "score_failure_attribution",
        ):
            text = public_safe_compact_text(raw_event.get(field), limit=140)
            if text:
                event[field] = text
        for field in (
            "required",
            "initialized_before_agent",
            "consumed_by_solver",
            "official_score_passed",
            "selected_todo_completed_observed",
            "quota_spend_missing_after_repeated_complete",
        ):
            if isinstance(raw_event.get(field), bool):
                event[field] = raw_event[field]
        for field in (
            "index",
            "checkpoint_count",
            "state_read_count",
            "state_write_count",
            "solver_operation_count",
            "solver_probe_ready_count",
            "trajectory_event_count",
            "trajectory_round_count",
            "trajectory_tool_call_count",
            "acp_protocol_tool_call_count",
            "agent_bridge_request_count",
            "agent_bridge_task_facing_operation_count",
            "action_decision_count",
            "initial_prompt_count",
            "followup_prompt_count",
            "stop_decision_count",
            "max_rounds_budget",
            "host_local_idle_no_task_output_progress_streak",
            "host_local_idle_no_task_output_progress_streak_threshold",
            "final_round",
            "recovery_delta_events",
            "recovery_delta_tool_calls",
            "benchflow_agent_timeout_effective_sec",
            "local_codex_exec_timeout_sec",
            "todo_closeout_count",
            "refresh_state_count",
            "quota_spend_slot_count",
            "selected_todo_complete_count",
            "selected_todo_duplicate_complete_count",
            "agent_todo_complete_unique_todo_count",
            "non_selected_todo_complete_count",
            "todo_complete_without_todo_id_count",
        ):
            raw = raw_event.get(field)
            if isinstance(raw, int) and not isinstance(raw, bool):
                event[field] = max(0, raw)
        for field in ("best_round_reward", "official_score_value"):
            raw = raw_event.get(field)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                event[field] = raw
        labels = public_safe_compact_list(
            raw_event.get("failure_attribution_labels"),
            limit=MAX_BENCHMARK_EVENT_LABELS,
        )
        if labels:
            event["failure_attribution_labels"] = labels
        events.append(event)

    if not events:
        return {}

    return {
        "schema_version": "skillsbench_case_event_timeline_v0",
        "source": "compact_public_signals",
        "raw_material_recorded": False,
        "event_count": len(events),
        "events": events[:MAX_BENCHMARK_EVENTS],
    }
