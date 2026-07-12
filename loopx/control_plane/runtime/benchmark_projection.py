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


def _solution_quality_number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _solution_quality_positive_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _solution_quality_compact_text(value: Any, *, limit: int = 160) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _solution_quality_compact_list(value: Any, *, limit: int = 16) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        text = _solution_quality_compact_text(item, limit=160)
        if not text:
            continue
        labels.append(text)
        if len(labels) >= limit:
            break
    return labels


def _solution_quality_timeline_events_by_name(
    timeline: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    events = timeline.get("events") if isinstance(timeline.get("events"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = _solution_quality_compact_text(event.get("event"), limit=120)
        if name and name not in result:
            result[name] = event
    return result


def build_benchmark_solution_quality_signals(
    benchmark_run: dict[str, Any],
) -> dict[str, Any]:
    """Summarize solution-level public signals from a compact benchmark run."""

    if not isinstance(benchmark_run, dict):
        return {}
    official = (
        benchmark_run.get("official_task_score")
        if isinstance(benchmark_run.get("official_task_score"), dict)
        else {}
    )
    score_value = _solution_quality_number(official.get("value"))
    if score_value is None:
        score_value = _solution_quality_number(benchmark_run.get("official_score"))
    official_passed = official.get("passed")
    if not isinstance(official_passed, bool):
        official_passed = bool(score_value is not None and score_value >= 1)

    labels = _solution_quality_compact_list(
        benchmark_run.get("failure_attribution_labels")
    )
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
    activity_event = _solution_quality_timeline_events_by_name(timeline).get(
        "task_facing_activity", {}
    )

    bridge_operation_count = _solution_quality_positive_int(
        activity_event.get("agent_bridge_task_facing_operation_count")
    ) or _solution_quality_positive_int(
        counters.get("remote_command_file_bridge_agent_task_facing_operation_count")
    )
    bridge_success_count = _solution_quality_positive_int(
        activity_event.get("agent_bridge_task_facing_success_count")
    ) or _solution_quality_positive_int(
        counters.get("remote_command_file_bridge_agent_task_facing_success_count")
    )
    tool_call_count = _solution_quality_positive_int(
        activity_event.get("acp_protocol_tool_call_count")
    ) or _solution_quality_positive_int(counters.get("private_trajectory_tool_call_count"))
    activity_status = (
        _solution_quality_compact_text(activity_event.get("status"), limit=120)
        or _solution_quality_compact_text(
            counters.get("host_local_acp_bridge_progress_status"), limit=120
        )
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
    runner_failure_class = _solution_quality_compact_text(
        runner_failure.get("failure_class"), limit=140
    )
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
        # Retain the shipped schema while the producer moves to its generic home.
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
