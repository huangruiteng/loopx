from __future__ import annotations

from typing import Any

from ...control_plane.runtime.public_safety import (
    public_safe_compact_list,
    public_safe_compact_text,
)


MAX_BENCHMARK_LIFECYCLE_LIST_ITEMS = 5


def compact_product_mode_lifecycle_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "countable_treatment",
        "checkpoint_required",
        "closeout_required",
        "closeout_satisfied",
        "agent_operation_trace_required",
        "agent_operation_trace_satisfied",
        "agent_operation_trace_missing",
        "orchestrated_driver_lifecycle_satisfied",
        "orchestrated_driver_counts_as_product_mode",
        "quota_spend_missing_after_repeated_complete",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "state_read_count",
        "state_write_count",
        "checkpoint_count",
        "checkpoint_round",
        "agent_bridge_state_read_count",
        "agent_bridge_state_write_count",
        "agent_bridge_todo_closeout_count",
        "agent_bridge_refresh_state_count",
        "agent_bridge_quota_spend_slot_count",
        "driver_lifecycle_state_read_count",
        "driver_lifecycle_state_write_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    missing_reason = public_safe_compact_text(value.get("missing_reason"), limit=140)
    if missing_reason:
        compact["missing_reason"] = missing_reason
    trace_status = public_safe_compact_text(
        value.get("agent_operation_trace_status"),
        limit=120,
    )
    if trace_status:
        compact["agent_operation_trace_status"] = trace_status
    execution_style = public_safe_compact_text(value.get("execution_style"), limit=120)
    if execution_style:
        compact["execution_style"] = execution_style
    _normalize_product_mode_lifecycle_contract(compact)
    return compact


def compact_native_goal_worker_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "countable_baseline",
        "fresh_goal_thread_per_independent_attempt",
        "official_reward_feedback_forwarded_to_worker",
        "verifier_output_forwarded_to_worker",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "benchflow_max_rounds_budget",
        "initial_goal_turn_budget",
        "same_thread_followup_budget",
        "independent_attempt_budget",
        "trace_count",
        "ok_count",
        "goal_get_count",
        "turn_start_count",
        "assistant_message_present_count",
        "assistant_context_only_count",
        "context_only_recovery_attempted_count",
        "context_only_recovery_succeeded_count",
        "context_only_followup_start_attempted_count",
        "context_only_followup_start_succeeded_count",
        "normal_followup_attempted_count",
        "normal_followup_succeeded_count",
        "normal_followup_start_attempted_count",
        "normal_followup_start_succeeded_count",
        "finish_guard_followup_attempted_count",
        "finish_guard_followup_succeeded_count",
        "finish_guard_followup_start_attempted_count",
        "finish_guard_followup_start_succeeded_count",
        "incomplete_turn_status_count",
        "incomplete_after_completion_event_count",
        "transport_reconnect_attempted_count",
        "transport_reconnect_succeeded_count",
        "goal_reactivation_attempted_count",
        "goal_reactivation_succeeded_count",
        "post_context_assistant_chars_total",
        "first_action_observed_count",
        "effective_action_observed_count",
        "failure_trace_count",
        "bridge_task_facing_operation_count",
        "bridge_task_facing_success_count",
    ):
        field_value = value.get(field)
        if isinstance(field_value, int) and not isinstance(field_value, bool):
            compact[field] = field_value
    for field in (
        "session_policy",
        "max_rounds_budget_applies_to",
        "countability_source",
        "trace_status",
        "reasoning_effort",
        "failure_category",
        "first_blocker",
        "failure_label",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    incomplete_statuses = public_safe_compact_list(
        value.get("incomplete_turn_statuses"),
        limit=MAX_BENCHMARK_LIFECYCLE_LIST_ITEMS,
    )
    if incomplete_statuses:
        compact["incomplete_turn_statuses"] = incomplete_statuses
    return compact


def compact_app_server_goal_round_semantics(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "route",
        "session_policy",
        "max_rounds_budget_applies_to",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "benchflow_max_rounds_budget",
        "initial_goal_turn_budget",
        "same_thread_followup_budget",
        "independent_attempt_budget",
    ):
        number = _nonnegative_int(value.get(field))
        if number is not None:
            compact[field] = number
    for field in (
        "fresh_goal_thread_per_independent_attempt",
        "official_reward_feedback_forwarded_to_worker",
        "verifier_output_forwarded_to_worker",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _normalize_product_mode_lifecycle_contract(contract: dict[str, Any]) -> None:
    """Repair old compact records whose bridge closeout evidence was copied late."""

    def positive_int(field: str) -> int:
        value = contract.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    agent_trace_required = contract.get("agent_operation_trace_required") is True
    agent_trace_satisfied = contract.get("agent_operation_trace_satisfied") is True
    agent_trace_missing = contract.get("agent_operation_trace_missing") is True
    agent_trace_ok = bool(
        not agent_trace_missing
        and (agent_trace_satisfied or not agent_trace_required)
    )
    agent_bridge_closeout_satisfied = bool(
        positive_int("agent_bridge_todo_closeout_count") > 0
        and positive_int("agent_bridge_refresh_state_count") > 0
        and positive_int("agent_bridge_quota_spend_slot_count") > 0
    )
    lifecycle_io_satisfied = bool(
        positive_int("state_read_count") > 0
        and positive_int("state_write_count") > 0
    )
    lifecycle_closeout_satisfied = bool(
        contract.get("closeout_satisfied") is True
        or agent_bridge_closeout_satisfied
    )
    if (
        contract.get("required") is True
        and agent_trace_ok
        and lifecycle_io_satisfied
        and lifecycle_closeout_satisfied
    ):
        contract["satisfied"] = True
        contract["countable_treatment"] = True
        contract["closeout_satisfied"] = True
        if contract.get("missing_reason") in {
            "missing_case_local_loopx_closeout",
            "remote_command_file_bridge_agent_operation_trace_missing",
        }:
            contract.pop("missing_reason", None)
