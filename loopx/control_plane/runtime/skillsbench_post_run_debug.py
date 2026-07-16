from __future__ import annotations

from typing import Any

from .benchmark_event_timeline import (
    compact_benchmark_case_event_timeline,
)
from .benchmark_projection import (
    build_benchmark_solution_quality_signals,
)
from .public_safety import (
    public_safe_compact_list,
    public_safe_compact_text,
)
from ..turn_driver.transaction import (
    loopx_turn_execution_committed,
    loopx_turn_execution_has_durable_effects,
)

MAX_SKILLSBENCH_DEBUG_LIST_ITEMS = 5


def _benchmark_case_timeline_events_by_name(
    timeline: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    events = timeline.get("events") if isinstance(timeline.get("events"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = public_safe_compact_text(event.get("event"), limit=120)
        if name and name not in result:
            result[name] = event
    return result


def _benchmark_positive_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _skillsbench_turn_transaction_outcome(run: dict[str, Any]) -> dict[str, Any]:
    executions = run.get("loopx_turn_executions")
    if not isinstance(executions, list):
        execution = run.get("loopx_turn_execution")
        executions = [execution] if isinstance(execution, dict) else []
    executions = [item for item in executions if isinstance(item, dict)]
    if not executions:
        return {}

    committed_count = 0
    validation_failed_count = 0
    repair_required_count = 0
    replan_required_count = 0
    state_written_count = 0
    quota_spent_count = 0
    failed_transaction_with_durable_effect_count = 0
    for execution in executions:
        validation = (
            execution.get("validation")
            if isinstance(execution.get("validation"), dict)
            else {}
        )
        receipt = (
            execution.get("receipt")
            if isinstance(execution.get("receipt"), dict)
            else {}
        )
        effects = (
            execution.get("effects")
            if isinstance(execution.get("effects"), dict)
            else {}
        )
        state_written = effects.get("state_written") is True
        quota_spent = effects.get("quota_spent") is True
        committed = loopx_turn_execution_committed(execution)
        validation_failed = bool(
            validation.get("status") == "failed"
            or receipt.get("failed_phase") == "validation"
            or execution.get("status") == "validation_failed"
        )
        recovery_kind = public_safe_compact_text(
            validation.get("recovery_kind"),
            limit=80,
        )
        committed_count += int(committed)
        validation_failed_count += int(validation_failed)
        repair_required_count += int(recovery_kind == "repair_required")
        replan_required_count += int(recovery_kind == "replan_required")
        state_written_count += int(state_written)
        quota_spent_count += int(quota_spent)
        failed_transaction_with_durable_effect_count += int(
            validation_failed and loopx_turn_execution_has_durable_effects(execution)
        )

    execution_count = len(executions)
    if failed_transaction_with_durable_effect_count:
        status = "inconsistent_failed_transaction_has_durable_effects"
        causal_consistency = "violated"
        first_blocker = "failed_turn_transaction_has_durable_effects"
    elif committed_count == execution_count:
        status = "committed"
        causal_consistency = "committed_effects_observed"
        first_blocker = "none"
    elif validation_failed_count:
        status = "validation_failed"
        causal_consistency = "validation_failure_effects_not_committed"
        first_blocker = "loopx_turn_validation_failed"
    else:
        status = "uncommitted"
        causal_consistency = "uncommitted_result_requires_recovery"
        first_blocker = "loopx_turn_uncommitted"

    if repair_required_count:
        recovery_status = "repair_required"
    elif replan_required_count:
        recovery_status = "replan_required"
    elif committed_count == execution_count:
        recovery_status = "not_required"
    else:
        recovery_status = "missing"

    return {
        "schema_version": "skillsbench_loopx_turn_transaction_outcome_v0",
        "observed": True,
        "status": status,
        "causal_consistency": causal_consistency,
        "recovery_status": recovery_status,
        "progress_blocked": committed_count != execution_count,
        "first_blocker": first_blocker,
        "execution_count": execution_count,
        "committed_count": committed_count,
        "uncommitted_count": execution_count - committed_count,
        "validation_failed_count": validation_failed_count,
        "repair_required_count": repair_required_count,
        "replan_required_count": replan_required_count,
        "state_written_count": state_written_count,
        "quota_spent_count": quota_spent_count,
        "failed_transaction_with_durable_effect_count": (
            failed_transaction_with_durable_effect_count
        ),
    }


def build_skillsbench_post_run_debug_gate(
    run: dict[str, Any],
) -> dict[str, Any]:
    """Build the public-safe SkillsBench post-run debug gate packet."""

    if not isinstance(run, dict):
        return {}
    benchmark_id = public_safe_compact_text(run.get("benchmark_id"), limit=120) or ""
    timeline = compact_benchmark_case_event_timeline(run.get("case_event_timeline"))
    if not benchmark_id.startswith("skillsbench"):
        return {}

    counters = (
        run.get("interaction_counters")
        if isinstance(run.get("interaction_counters"), dict)
        else {}
    )
    lifecycle = (
        run.get("product_mode_lifecycle_contract")
        if isinstance(run.get("product_mode_lifecycle_contract"), dict)
        else {}
    )
    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    runner_failure = (
        run.get("runner_failure") if isinstance(run.get("runner_failure"), dict) else {}
    )
    verifier_artifact_recovery = (
        run.get("verifier_reward_artifact_recovery")
        if isinstance(run.get("verifier_reward_artifact_recovery"), dict)
        else {}
    )
    events = _benchmark_case_timeline_events_by_name(timeline)
    missing_fields: list[str] = []
    if not timeline:
        missing_fields.append("case_event_timeline")

    product_mode_required = bool(
        run.get("product_mode") is True
        or counters.get("product_mode") is True
        or lifecycle.get("required") is True
    )
    required_events = [
        "controller_decision_loop",
        "official_score_closeout",
    ]
    if product_mode_required:
        required_events.extend(
            [
                "case_goal_state_init",
                "orchestrated_loopx_lifecycle",
                "remote_command_bridge_consumption",
                "task_facing_activity",
                "agent_bridge_closeout",
            ]
        )
    for event_name in required_events:
        if timeline and event_name not in events:
            missing_fields.append(f"case_event_timeline.events.{event_name}")

    official_event = events.get("official_score_closeout", {})
    closeout_event = events.get("agent_bridge_closeout", {})
    controller_event = events.get("controller_decision_loop", {})
    driver_event = events.get("orchestrated_loopx_lifecycle", {})
    recovery_event = events.get("timeout_or_failure_closeout", {})
    activity_event = events.get("task_facing_activity", {})

    official_status = (
        public_safe_compact_text(
            official_event.get("status") or run.get("official_score_status"),
            limit=120,
        )
        or "unknown"
    )
    official_passed = official.get("passed")
    if not isinstance(official_passed, bool):
        official_passed = official_event.get("official_score_passed")
    official_score_value = official.get("value")
    if not isinstance(official_score_value, (int, float)) or isinstance(
        official_score_value,
        bool,
    ):
        official_score_value = run.get("official_score")
    closeout_status = public_safe_compact_text(
        closeout_event.get("status"),
        limit=120,
    ) or ("not_required" if not product_mode_required else "unknown")
    activity_status = (
        public_safe_compact_text(activity_event.get("status"), limit=120) or "unknown"
    )
    recovery_status = (
        public_safe_compact_text(recovery_event.get("status"), limit=120)
        or "not_observed"
    )
    agent_operation_trace_missing = bool(
        activity_status == "missing_agent_operation_trace"
        or lifecycle.get("agent_operation_trace_missing") is True
    )
    runner_recovery_blocked = recovery_status in {
        "user_loop_recovery_triggered",
        "runner_failure_recorded",
    }
    verifier_artifact_success = bool(
        verifier_artifact_recovery.get("passed") is True
        and (
            verifier_artifact_recovery.get("status")
            == "official_score_recovered_from_verifier_reward_artifact"
        )
    )
    lifecycle_required = lifecycle.get("required") is True or product_mode_required
    lifecycle_state_read_count = _benchmark_positive_int(
        lifecycle.get("state_read_count")
    ) or _benchmark_positive_int(driver_event.get("state_read_count"))
    lifecycle_state_write_count = _benchmark_positive_int(
        lifecycle.get("state_write_count")
    ) or _benchmark_positive_int(driver_event.get("state_write_count"))
    lifecycle_satisfied = lifecycle.get("satisfied")
    closeout_satisfied = bool(
        closeout_status in {"satisfied", "not_required"}
        or lifecycle.get("closeout_satisfied") is True
    )
    timeline_lifecycle_satisfied = bool(
        closeout_satisfied
        and (
            not lifecycle_required
            or (lifecycle_state_read_count > 0 and lifecycle_state_write_count > 0)
        )
    )
    effective_lifecycle_satisfied = bool(
        lifecycle_satisfied is True or timeline_lifecycle_satisfied
    )
    turn_transaction = _skillsbench_turn_transaction_outcome(run)
    turn_transaction_blocks_progress = bool(
        turn_transaction.get("progress_blocked") is True
    )
    qualified_lifecycle_satisfied = bool(
        effective_lifecycle_satisfied and not turn_transaction_blocks_progress
    )
    qualified_closeout_status = (
        "turn_transaction_repair_required"
        if turn_transaction_blocks_progress
        else closeout_status
    )
    case_closeout_complete = bool(
        (not missing_fields and official_passed is True and verifier_artifact_success)
        or (
            not missing_fields
            and (not lifecycle_required or effective_lifecycle_satisfied)
            and official_status not in {"unknown", ""}
            and not agent_operation_trace_missing
            and not (official_status == "missing" and runner_recovery_blocked)
        )
    )

    first_blocker = "none"
    attribution_layer = "solution_level_unknown"
    if missing_fields:
        attribution_layer = "incomplete_public_debug_packet"
        first_blocker = missing_fields[0]
    elif turn_transaction_blocks_progress:
        attribution_layer = "loopx_turn_transaction"
        first_blocker = (
            public_safe_compact_text(
                turn_transaction.get("first_blocker"),
                limit=140,
            )
            or "loopx_turn_transaction_repair_required"
        )
    elif (
        lifecycle_required
        and not verifier_artifact_success
        and (not effective_lifecycle_satisfied or agent_operation_trace_missing)
    ):
        attribution_layer = "loopx_lifecycle"
        first_blocker = (
            public_safe_compact_text(
                lifecycle.get("missing_reason"),
                limit=140,
            )
            or ""
        )
        if agent_operation_trace_missing and not first_blocker:
            first_blocker = "remote_command_file_bridge_agent_operation_trace_missing"
        if not first_blocker:
            first_blocker = (
                public_safe_compact_text(lifecycle.get("missing_reason"), limit=140)
                or "loopx_lifecycle_incomplete"
            )
    elif closeout_status in {"missing", "partial"} and not case_closeout_complete:
        attribution_layer = "loopx_lifecycle"
        first_blocker = "loopx_closeout_incomplete"
    elif runner_recovery_blocked:
        attribution_layer = "timeout_or_runner"
        first_blocker = (
            public_safe_compact_text(
                recovery_event.get("recovery_exception_type")
                or recovery_event.get("runner_failure_class"),
                limit=140,
            )
            or "runner_or_timeout_closeout"
        )
    elif official_status == "missing":
        attribution_layer = "verifier_or_scorer"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_missing"
        )
    elif official_passed is True:
        attribution_layer = "clean_pass"
    elif isinstance(official_score_value, (int, float)) and official_score_value == 0:
        attribution_layer = "solution_level_unknown"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_zero_case_failure"
        )
    elif official_passed is False:
        attribution_layer = "solution_level_unknown"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_nonpassing"
        )

    packet_complete = not missing_fields
    if not packet_complete:
        next_case_gate = "blocked_missing_debug_packet"
        next_action = "write_public_safe_case_debug_packet_before_next_case"
    elif not case_closeout_complete:
        next_case_gate = "blocked_incomplete_case_closeout"
        next_action = "record_or_repair_case_closeout_before_next_case"
    elif turn_transaction_blocks_progress:
        next_case_gate = "blocked_turn_transaction_repair"
        next_action = "repair_loopx_turn_transaction_before_next_matched_case"
    elif attribution_layer == "clean_pass":
        next_case_gate = "open"
        next_action = "upsert_ledger_and_continue_or_compare_pair"
    else:
        next_case_gate = "open_with_attribution"
        next_action = "use_debug_packet_attribution_before_rotating_or_rerunning"

    labels = public_safe_compact_list(
        run.get("failure_attribution_labels"),
        limit=MAX_SKILLSBENCH_DEBUG_LIST_ITEMS,
    )
    solution_quality = build_benchmark_solution_quality_signals(run)
    gate: dict[str, Any] = {
        "schema_version": "skillsbench_post_run_debug_gate_v0",
        "source": "compact_public_signals",
        "packet_complete": packet_complete,
        "case_closeout_complete": case_closeout_complete,
        "next_case_gate": next_case_gate,
        "normal_progress_allowed": bool(
            packet_complete
            and case_closeout_complete
            and not turn_transaction_blocks_progress
        ),
        "first_blocker": first_blocker,
        "next_action": next_action,
        "attribution_layer": attribution_layer,
        "raw_material_recorded": False,
        "missing_field_count": len(missing_fields),
        "missing_fields": missing_fields[:MAX_SKILLSBENCH_DEBUG_LIST_ITEMS],
        "verifier_artifact_recovery_authoritative": verifier_artifact_success,
        "scorer_verifier": {
            "official_score_status": official_status,
            "official_score_passed": (
                official_passed if isinstance(official_passed, bool) else None
            ),
            "official_score_value": (
                official_score_value
                if isinstance(official_score_value, (int, float))
                and not isinstance(official_score_value, bool)
                else None
            ),
            "score_failure_attribution": (
                public_safe_compact_text(
                    run.get("score_failure_attribution"),
                    limit=140,
                )
                or "none"
            ),
        },
        "loopx_lifecycle": {
            "required": lifecycle_required,
            "satisfied": qualified_lifecycle_satisfied,
            "direct_lifecycle_satisfied": effective_lifecycle_satisfied,
            "closeout_status": qualified_closeout_status,
            "direct_closeout_status": closeout_status,
            "state_read_count": lifecycle_state_read_count,
            "state_write_count": lifecycle_state_write_count,
            "todo_closeout_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_todo_closeout_count")
            )
            or _benchmark_positive_int(closeout_event.get("todo_closeout_count")),
            "refresh_state_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_refresh_state_count")
            )
            or _benchmark_positive_int(closeout_event.get("refresh_state_count")),
            "quota_spend_slot_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_quota_spend_slot_count")
            )
            or _benchmark_positive_int(closeout_event.get("quota_spend_slot_count")),
        },
        "todo_flow": {
            "case_todo_seeded_or_init_observed": (
                events.get("case_goal_state_init", {}).get("status")
                in {"passed", "satisfied", "not_required"}
            ),
            "task_facing_activity_status": activity_status,
            "host_local_acp_bridge_progress_status": (
                public_safe_compact_text(
                    activity_event.get("host_local_acp_bridge_progress_status"),
                    limit=140,
                )
                or public_safe_compact_text(
                    counters.get("host_local_acp_bridge_progress_status"),
                    limit=140,
                )
                or "unknown"
            ),
            "host_local_acp_bridge_progress_signal_source": (
                public_safe_compact_text(
                    activity_event.get("host_local_acp_bridge_progress_signal_source"),
                    limit=140,
                )
                or public_safe_compact_text(
                    counters.get("host_local_acp_bridge_progress_signal_source"),
                    limit=140,
                )
                or "unknown"
            ),
            "acp_protocol_tool_call_count": _benchmark_positive_int(
                activity_event.get("acp_protocol_tool_call_count")
            )
            or _benchmark_positive_int(
                counters.get("private_trajectory_tool_call_count")
            ),
            "agent_bridge_task_facing_operation_count": _benchmark_positive_int(
                activity_event.get("agent_bridge_task_facing_operation_count")
            )
            or _benchmark_positive_int(
                counters.get(
                    "remote_command_file_bridge_agent_task_facing_operation_count"
                )
            ),
            "open_todo_count_public": _benchmark_positive_int(
                counters.get("open_todo_count")
            ),
            "host_local_idle_no_task_output_progress_streak": _benchmark_positive_int(
                counters.get(
                    "product_mode_host_local_idle_no_task_output_progress_streak"
                )
            ),
            "host_local_idle_no_task_output_progress_streak_threshold": _benchmark_positive_int(
                counters.get(
                    "product_mode_host_local_idle_no_task_output_progress_streak_threshold"
                )
            ),
            "host_local_idle_no_task_output_progress_stop": counters.get(
                "product_mode_host_local_idle_no_task_output_progress_stop"
            )
            is True,
            "no_open_todo_below_passing_reward_streak": _benchmark_positive_int(
                counters.get("product_mode_no_open_todo_below_passing_reward_streak")
            ),
            "no_open_todo_below_passing_reward_streak_threshold": _benchmark_positive_int(
                counters.get(
                    "product_mode_no_open_todo_below_passing_reward_streak_threshold"
                )
            ),
            "no_open_todo_below_passing_reward_stop": counters.get(
                "product_mode_no_open_todo_below_passing_reward_stop"
            )
            is True,
            "typed_repair_round_entered": _benchmark_positive_int(
                counters.get("product_mode_typed_repair_round_entered")
            ),
            "typed_repair_todo_identity_observed": counters.get(
                "product_mode_typed_repair_todo_identity_observed"
            )
            is True,
            "typed_repair_task_or_validation_delta": counters.get(
                "product_mode_typed_repair_task_or_validation_delta"
            )
            is True,
            "typed_repair_terminal": counters.get(
                "product_mode_typed_repair_terminal"
            )
            is True,
            "typed_repair_terminal_receipt_consistent": counters.get(
                "product_mode_typed_repair_terminal_receipt_consistent"
            )
            is True,
        },
        "controller": {
            "status": (
                public_safe_compact_text(controller_event.get("status"), limit=120)
                or "unknown"
            ),
            "action_decision_count": _benchmark_positive_int(
                controller_event.get("action_decision_count")
            ),
            "initial_prompt_count": _benchmark_positive_int(
                controller_event.get("initial_prompt_count")
            ),
            "followup_prompt_count": _benchmark_positive_int(
                controller_event.get("followup_prompt_count")
            ),
            "stop_decision_count": _benchmark_positive_int(
                controller_event.get("stop_decision_count")
            ),
            "max_rounds_budget": _benchmark_positive_int(
                controller_event.get("max_rounds_budget")
            ),
            "last_decision": (
                public_safe_compact_text(
                    controller_event.get("last_decision"),
                    limit=140,
                )
                or "unknown"
            ),
        },
        "timeout_fairness": {
            "runner_recovery_status": recovery_status,
            "recovery_exception_type": (
                public_safe_compact_text(
                    recovery_event.get("recovery_exception_type"),
                    limit=140,
                )
                or "none"
            ),
            "benchflow_agent_timeout_effective_sec": _benchmark_positive_int(
                recovery_event.get("benchflow_agent_timeout_effective_sec")
            ),
        },
        "boundary": {
            "task_text_read": False,
            "logs_read": False,
            "trajectory_read": False,
            "verifier_output_tail_public": False,
        },
    }
    if solution_quality:
        gate["solution_quality"] = solution_quality
    if turn_transaction:
        gate["loopx_turn_transaction"] = turn_transaction
    if labels:
        gate["failure_attribution_labels"] = labels
    if runner_failure:
        gate["runner_failure_class"] = (
            public_safe_compact_text(runner_failure.get("failure_class"), limit=140)
            or "unknown"
        )
    return gate
