from __future__ import annotations

from typing import Any

from ...control_plane.runtime.public_safety import (
    compact_numeric_map,
    public_safe_compact_text,
)


def compact_benchmark_round_reward_trace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "source",
        "round_index_origin",
        "loop_score_policy",
        "official_score_policy",
    ):
        text = public_safe_compact_text(value.get(field), limit=100)
        if text:
            compact[field] = text
    for field in (
        "success_observed",
        "official_feedback_returned_to_agent",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "agent_declared_done",
        "agent_declared_no_remaining_goals",
        "product_mode_no_open_todo_below_passing_reward_stop",
        "product_mode_typed_repair_required",
        "product_mode_typed_repair_todo_identity_observed",
        "product_mode_typed_repair_task_or_validation_delta",
        "product_mode_typed_repair_delta_observed",
        "product_mode_typed_repair_terminal",
        "product_mode_typed_repair_terminal_receipt_consistent",
        "official_score_recovered_from_controller_trace",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "first_success_round",
        "declared_done_round",
        "max_rounds_budget",
        "final_round",
        "best_reward_round",
        "official_score_recovered_round",
        "product_mode_no_open_todo_below_passing_reward_streak",
        "product_mode_no_open_todo_below_passing_reward_streak_threshold",
        "product_mode_no_open_todo_below_passing_reward_round",
        "product_mode_no_open_todo_below_passing_reward_stop_round",
        "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
        "product_mode_typed_repair_trigger_round",
        "product_mode_typed_repair_round_entered",
        "product_mode_typed_repair_round_entered_count",
        "product_mode_typed_repair_resolved_round",
        "product_mode_typed_repair_task_facing_success_delta",
        "product_mode_typed_repair_terminal_round",
        "product_mode_typed_repair_open_todo_count_public",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            compact[field] = raw
    for field in (
        "final_round_reward",
        "best_round_reward",
        "declared_done_score",
        "product_mode_no_open_todo_below_passing_reward_score",
    ):
        raw = value.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            compact[field] = float(raw)
    score_status = public_safe_compact_text(
        value.get("product_mode_no_open_todo_below_passing_reward_score_status"),
        limit=100,
    )
    if score_status:
        compact["product_mode_no_open_todo_below_passing_reward_score_status"] = (
            score_status
        )
    for field in (
        "product_mode_typed_repair_policy_id",
        "product_mode_typed_repair_terminal_reason",
    ):
        text = public_safe_compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    for field in ("final_round_passed", "best_round_passed", "best_round_is_final"):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    records: list[dict[str, Any]] = []
    raw_records = value.get("records")
    if isinstance(raw_records, list):
        seen_rounds: set[int] = set()
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            agent_round = item.get("agent_round")
            if (
                not isinstance(agent_round, int)
                or isinstance(agent_round, bool)
                or agent_round <= 0
                or agent_round in seen_rounds
            ):
                continue
            seen_rounds.add(agent_round)
            record: dict[str, Any] = {"agent_round": agent_round}
            for field in ("reward_present", "passed"):
                if isinstance(item.get(field), bool):
                    record[field] = item[field]
            reward = item.get("reward")
            if isinstance(reward, (int, float)) and not isinstance(reward, bool):
                record["reward"] = float(reward)
            tool_calls = item.get("tool_calls")
            if (
                isinstance(tool_calls, int)
                and not isinstance(tool_calls, bool)
                and tool_calls >= 0
            ):
                record["tool_calls"] = tool_calls
            records.append(record)
    if records:
        compact["records"] = sorted(records, key=lambda record: record["agent_round"])
    return compact


def compact_benchmark_overhead_attribution_counters(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "source",
        "trace_publicness",
        "attribution_granularity",
        "worker_step_counter_status",
        "attribution_caveat",
        "timeout_tier",
    ):
        text = public_safe_compact_text(value.get(field), limit=160)
        if text:
            compact[field] = text

    for field in (
        "raw_logs_read",
        "raw_trace_recorded",
        "raw_task_prompt_recorded",
        "credential_values_recorded",
        "loopx_worker_cli_bridge_required",
        "observed_true_long_task_bar_met",
        "expected_hours_scale_bar_met",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    for field in (
        "wall_time_seconds",
        "wall_time_limit_seconds",
        "input_tokens",
        "cache_tokens",
        "output_tokens",
        "cost_usd",
        "trial_count",
        "errored_trial_count",
        "worker_bridge_event_count",
        "loopx_prompt_driven_case_cli_call_count",
        "worker_counter_trace_trial_count",
        "worker_benchmark_run_file_count",
        "worker_benchmark_run_schema_ok_count",
        "worker_self_validation_official_score_mismatch_count",
        "worker_validation_scope_ambiguous_official_score_failure_count",
        "worker_bridge_connected_official_score_failure_count",
        "worker_startup_blocker_count",
        "worker_setup_diagnostic_file_count",
        "worker_setup_diagnostic_schema_ok_count",
        "worker_submit_eligible_mismatch_count",
        "worker_bridge_writeback_loss_count",
        "environment_setup_failure_before_worker_count",
        "pre_worker_agent_setup_failure_count",
        "codex_runtime_goal_tool_trial_count",
        "loopx_cli_call_total",
        "loopx_required_cli_call_total",
        "loopx_optional_context_cli_call_total",
        "loopx_state_read_count",
        "loopx_state_write_count",
        "append_benchmark_run_success_count",
        "append_benchmark_run_schema_rejected_count",
        "codex_runtime_goal_tool_call_total",
    ):
        raw = value.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            compact[field] = raw

    mismatch_reason = public_safe_compact_text(
        value.get("worker_submit_eligible_mismatch_reason"),
        limit=160,
    )
    if mismatch_reason:
        compact["worker_submit_eligible_mismatch_reason"] = mismatch_reason

    for field in ("loopx_cli_calls", "codex_runtime_goal_tool_calls"):
        calls = compact_numeric_map(value.get(field))
        if calls:
            compact[field] = calls

    return compact
