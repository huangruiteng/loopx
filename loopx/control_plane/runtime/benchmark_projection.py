from __future__ import annotations

from typing import Any

from .public_safety import (
    compact_numeric_map,
    public_safe_compact_list,
    public_safe_compact_text,
)


BENCHMARK_RUN_TEXT_FIELDS = (
    "worker_mode",
    "trace_publicness",
    "first_blocker",
    "score_failure_attribution",
    "validation_scope",
    "worker_submit_eligible_mismatch_reason",
    "worker_bridge_writeback_loss_reason",
    "worker_bridge_materialization_status",
    "worker_bridge_materialization_blocker",
    "worker_bridge_failure_attribution",
    "repeat_blocked_by",
    "pre_worker_startup_blocker",
    "environment_setup_probe_status",
    "runner_return_status",
    "official_score_source",
    "official_score_status",
    "skillsbench_route_semantics",
    "native_goal_mode_confirmation_status",
    "loopx_treatment_evidence_tier",
    "loopx_treatment_claim_blocker",
    "loopx_cli_bridge_surface",
    "loopx_cli_bridge_contract",
    "loopx_cli_bridge_scope",
    "loopx_counter_scope",
)
BENCHMARK_RUN_BOOL_FIELDS = (
    "real_run",
    "submit_eligible",
    "case_semantics_changed_by_harness",
    "loopx_inside_case",
    "loopx_automation_loop",
    "product_mode",
    "official_score_comparable_to_native_codex",
    "official_score_comparable_to_loopx_treatment",
    "model_plus_harness_pair",
    "control_plane_score_applicable",
    "startup_surface_calibration",
    "hardened_install_surface",
    "hardened_install_baseline",
    "environment_setup_probe_run",
    "environment_setup_probe_cleared",
    "leaderboard_evidence",
    "loopx_cli_bridge_contract_available",
    "loopx_cli_bridge_trace_observed",
    "loopx_worker_cli_bridge_available",
    "loopx_worker_cli_bridge_trace_observed",
    "loopx_prompt_driven_trace_observed",
    "loopx_prompt_driven_lifecycle_observed",
    "loopx_controller_trace_present",
    "loopx_controller_trace_public_safe",
    "controller_turn_completed_observed",
    "assisted_collaboration_claim_allowed",
    "official_score_claim_allowed",
    "bridge_connectivity_claim_allowed",
    "case_success_claimed",
    "official_verifier_validation_present",
    "official_case_success",
    "active_user_simulator_injection_channel_available",
    "inner_codex_goal_mode",
    "native_goal_mode_requested",
    "native_goal_mode_invoked",
    "codex_acp_protocol_used",
    "blind_loop",
    "agent_declared_done",
    "official_feedback_blinded",
    "reward_feedback_forwarded",
    "native_goal_worker_route",
    "native_goal_worker_connected",
    "native_goal_worker_trace_dir_present",
    "native_goal_worker_public_trace_read",
    "native_goal_worker_raw_material_recorded",
    "remote_command_file_bridge_consumed_by_solver",
    "remote_command_file_bridge_solver_trace_dir_present",
    "remote_command_file_bridge_solver_public_trace_read",
    "remote_command_file_bridge_solver_raw_material_recorded",
    "strict_loopx_treatment_claim_allowed",
    "controller_trace_present",
)
BENCHMARK_RUN_INT_FIELDS = (
    "runner_loopx_cli_call_total",
    "worker_loopx_cli_call_total",
    "loopx_prompt_driven_case_cli_call_count",
    "loopx_prompt_driven_trace_file_count",
    "loopx_prompt_driven_compact_file_count",
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
    "worker_runtime_exception_before_checkpoint_count",
    "verifier_failure_attribution_count",
    "verifier_dependency_failure_count",
    "official_zero_observation_count",
    "planned_worker_loopx_cli_call_total",
    "required_worker_loopx_cli_call_total_min",
    "native_goal_worker_connect_count",
    "native_goal_worker_trace_count",
    "native_goal_worker_lifecycle_trace_count",
    "native_goal_worker_prompt_received_count",
    "native_goal_worker_ok_count",
    "native_goal_worker_goal_get_count",
    "native_goal_worker_turn_start_count",
    "native_goal_worker_turn_completed_observed_count",
    "native_goal_worker_assistant_message_present_count",
    "native_goal_worker_assistant_context_only_count",
    "native_goal_worker_context_only_recovery_attempted_count",
    "native_goal_worker_context_only_recovery_succeeded_count",
    "native_goal_worker_context_only_followup_start_attempted_count",
    "native_goal_worker_context_only_followup_start_succeeded_count",
    "native_goal_worker_normal_followup_attempted_count",
    "native_goal_worker_normal_followup_succeeded_count",
    "native_goal_worker_normal_followup_start_attempted_count",
    "native_goal_worker_normal_followup_start_succeeded_count",
    "native_goal_worker_finish_guard_followup_attempted_count",
    "native_goal_worker_finish_guard_followup_succeeded_count",
    "native_goal_worker_finish_guard_followup_start_attempted_count",
    "native_goal_worker_finish_guard_followup_start_succeeded_count",
    "native_goal_worker_incomplete_turn_status_count",
    "native_goal_worker_incomplete_after_completion_event_count",
    "native_goal_worker_transport_reconnect_attempted_count",
    "native_goal_worker_transport_reconnect_succeeded_count",
    "native_goal_worker_goal_reactivation_attempted_count",
    "native_goal_worker_goal_reactivation_succeeded_count",
    "native_goal_worker_post_context_assistant_chars_total",
    "native_goal_worker_first_action_observed_count",
    "native_goal_worker_effective_action_observed_count",
    "remote_command_file_bridge_solver_trace_count",
    "remote_command_file_bridge_solver_probe_ready_count",
    "remote_command_file_bridge_solver_operation_count",
    "controller_max_round_observed",
    "controller_max_rounds_budget",
    "controller_initial_prompt_count",
    "controller_followup_prompt_count",
    "controller_action_decisions",
    "controller_no_active_todo_confirmed_count",
    "max_rounds_budget",
    "round_reward_count",
)


def benchmark_run_source(
    run: dict[str, Any],
    *,
    schema_version: str,
) -> dict[str, Any] | None:
    nested = run.get("benchmark_run")
    if isinstance(nested, dict) and nested.get("schema_version") == schema_version:
        return nested
    if run.get("schema_version") == schema_version:
        return run
    return None


def compact_benchmark_run_core(
    source: dict[str, Any],
    *,
    schema_version: str,
    max_list_items: int,
) -> dict[str, Any]:
    compact: dict[str, Any] = {"schema_version": schema_version}
    for field in ("source_runner", "benchmark_id", "job_name", "mode"):
        value = public_safe_compact_text(source.get(field), limit=120)
        if value:
            compact[field] = value

    trials = source.get("trials") if isinstance(source.get("trials"), list) else []
    first_trial = trials[0] if trials and isinstance(trials[0], dict) else {}
    case_ids_source = source.get("case_ids") if isinstance(source.get("case_ids"), list) else []
    case_id = (
        public_safe_compact_text(source.get("case_id"), limit=120)
        or public_safe_compact_text(source.get("task_id"), limit=120)
        or public_safe_compact_text(first_trial.get("task_id"), limit=120)
        or (
            public_safe_compact_text(case_ids_source[0], limit=120)
            if case_ids_source
            else None
        )
    )
    if case_id:
        compact["case_id"] = case_id
        case_ids = public_safe_compact_list(case_ids_source, limit=max_list_items)
        compact["case_ids"] = case_ids or [case_id]

    for field in BENCHMARK_RUN_TEXT_FIELDS:
        value = public_safe_compact_text(source.get(field), limit=140)
        if value:
            compact[field] = value
    for field in BENCHMARK_RUN_BOOL_FIELDS:
        if isinstance(source.get(field), bool):
            compact[field] = source[field]
    for field in BENCHMARK_RUN_INT_FIELDS:
        if isinstance(source.get(field), int) and not isinstance(source.get(field), bool):
            compact[field] = source[field]

    round_timeout = source.get("controller_round_timeout_sec")
    if isinstance(round_timeout, (int, float)) and not isinstance(round_timeout, bool):
        compact["controller_round_timeout_sec"] = round_timeout
    last_decision = public_safe_compact_text(
        source.get("controller_last_decision"),
        limit=120,
    )
    if last_decision:
        compact["controller_last_decision"] = last_decision
    event_counts = compact_numeric_map(source.get("loopx_prompt_driven_event_counts"))
    if event_counts:
        compact["loopx_prompt_driven_event_counts"] = event_counts
    return compact
