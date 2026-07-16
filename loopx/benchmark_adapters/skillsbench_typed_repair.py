from __future__ import annotations

from typing import Any, Mapping

from loopx.control_plane.runtime.public_safety import compact_loopx_command_records
from loopx.control_plane.runtime.public_safety import public_safe_compact_text
from loopx.control_plane.turn_driver.transaction import (
    loopx_turn_execution_committed,
    loopx_turn_execution_has_durable_effects,
    loopx_turn_execution_recovery_required,
)


SKILLSBENCH_TYPED_REPAIR_POLICY_ID = "one_typed_repair_per_frontier_v0"
SKILLSBENCH_TYPED_REPAIR_SNAPSHOT_SCHEMA_VERSION = (
    "skillsbench_typed_repair_frontier_snapshot_v0"
)
SKILLSBENCH_TYPED_REPAIR_TERMINAL_RECEIPT_SCHEMA_VERSION = (
    "skillsbench_typed_repair_terminal_receipt_v0"
)
_TODO_REFERENCE_SUBCOMMANDS = {"todo add", "todo claim", "todo update"}
_NEW_TODO_IDENTITY_SUBCOMMANDS = {"todo add"}
_COMMAND_RECORD_LIMIT = 128
_TYPED_REPAIR_BOOL_FIELDS = (
    "product_mode_typed_repair_required",
    "product_mode_typed_repair_pending",
    "product_mode_typed_repair_todo_identity_observed",
    "product_mode_typed_repair_task_or_validation_delta",
    "product_mode_typed_repair_turn_validation_delta",
    "product_mode_typed_repair_delta_observed",
    "product_mode_typed_repair_terminal",
    "product_mode_typed_repair_terminal_receipt_consistent",
)
_TYPED_REPAIR_COUNT_FIELDS = (
    "product_mode_typed_repair_trigger_round",
    "product_mode_typed_repair_round_entered",
    "product_mode_typed_repair_round_entered_count",
    "product_mode_typed_repair_resolved_round",
    "product_mode_typed_repair_task_facing_success_delta",
    "product_mode_typed_repair_turn_execution_count_delta",
    "product_mode_typed_repair_turn_committed_count_delta",
    "product_mode_typed_repair_turn_recovery_required_count_delta",
    "product_mode_typed_repair_terminal_round",
    "product_mode_typed_repair_open_todo_count_public",
)
_TYPED_REPAIR_TEXT_FIELDS = (
    "product_mode_typed_repair_policy_id",
    "product_mode_typed_repair_trigger_kind",
    "product_mode_typed_repair_terminal_reason",
)


def _count(trace: Mapping[str, Any], field: str) -> int:
    value = trace.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        return 0
    return max(0, value)


def _command_records(trace: Mapping[str, Any]) -> list[dict[str, str]]:
    return compact_loopx_command_records(
        trace.get("remote_command_file_bridge_agent_successful_loopx_command_records"),
        limit=_COMMAND_RECORD_LIMIT,
    )


def _turn_executions(trace: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    executions = trace.get("loopx_turn_executions")
    if not isinstance(executions, list):
        return []
    return [item for item in executions if isinstance(item, Mapping)]


def _turn_outcome_counts(trace: Mapping[str, Any]) -> dict[str, int]:
    executions = _turn_executions(trace)
    return {
        "execution_count": len(executions),
        "committed_count": sum(
            loopx_turn_execution_committed(item) for item in executions
        ),
        "recovery_required_count": sum(
            loopx_turn_execution_recovery_required(item) for item in executions
        ),
    }


def skillsbench_turn_recovery_checkpoint(
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the public Turn receipt that should steer one typed repair."""

    executions = _turn_executions(trace)
    latest = executions[-1] if executions else {}
    recovery_required = bool(
        latest
        and loopx_turn_execution_recovery_required(latest)
        and not loopx_turn_execution_has_durable_effects(latest)
    )
    failed_transaction_with_durable_effects = bool(
        latest
        and loopx_turn_execution_recovery_required(latest)
        and loopx_turn_execution_has_durable_effects(latest)
    )
    validation = (
        latest.get("validation")
        if isinstance(latest.get("validation"), Mapping)
        else {}
    )
    counts = _turn_outcome_counts(trace)
    return {
        "schema_version": "skillsbench_turn_recovery_checkpoint_v0",
        "observed": bool(latest),
        "repair_required": recovery_required,
        "failed_transaction_with_durable_effects": (
            failed_transaction_with_durable_effects
        ),
        "recovery_kind": public_safe_compact_text(
            validation.get("recovery_kind"), limit=80
        ),
        **counts,
        "raw_material_recorded": False,
    }


def compact_skillsbench_typed_repair_counters(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    compact: dict[str, Any] = {
        field: value.get(field) is True for field in _TYPED_REPAIR_BOOL_FIELDS
    }
    for field in _TYPED_REPAIR_COUNT_FIELDS:
        compact[field] = _count(value, field)
    for field in _TYPED_REPAIR_TEXT_FIELDS:
        text = public_safe_compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    return compact


def skillsbench_typed_repair_round_trace_fields(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    compact = compact_skillsbench_typed_repair_counters(value)
    compact.pop("product_mode_typed_repair_pending", None)
    return compact


def skillsbench_typed_repair_failure_labels(
    value: Mapping[str, Any],
    *,
    official_passed: bool,
) -> tuple[str, ...]:
    if (
        official_passed
        or value.get("product_mode_typed_repair_terminal") is not True
    ):
        return ()
    return (
        "skillsbench_product_mode_typed_repair_terminal",
        "skillsbench_solver_exhausted_after_typed_repair",
    )


def skillsbench_projected_open_todo_count(
    trace: Mapping[str, Any],
) -> int | None:
    records = _command_records(trace)
    if len(records) >= _COMMAND_RECORD_LIMIT:
        return None

    todo_states: dict[str, str] = {}
    for record in records:
        todo_id = record.get("todo_id", "")
        if not todo_id:
            continue
        subcommand = record.get("subcommand")
        if subcommand == "todo add":
            todo_states[todo_id] = "open"
        elif subcommand == "todo claim":
            todo_states.setdefault(todo_id, "unknown")
        elif subcommand == "todo update":
            # Public command records intentionally omit mutable fields such as
            # --status, so an update cannot prove an open or closed transition.
            todo_states[todo_id] = "unknown"
        elif subcommand == "todo complete":
            todo_states[todo_id] = "closed"
    if todo_states:
        if "unknown" in todo_states.values():
            return None
        return sum(state == "open" for state in todo_states.values())
    explicit_count = trace.get("open_todo_count")
    if isinstance(explicit_count, int) and not isinstance(explicit_count, bool):
        return max(0, explicit_count)
    return None


def capture_skillsbench_typed_repair_frontier(
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    records = _command_records(trace)
    todo_ids: list[str] = []
    for record in records:
        todo_id = record.get("todo_id", "")
        if (
            record.get("subcommand") in _TODO_REFERENCE_SUBCOMMANDS
            and todo_id
            and todo_id not in todo_ids
        ):
            todo_ids.append(todo_id)
    turn_counts = _turn_outcome_counts(trace)
    return {
        "schema_version": SKILLSBENCH_TYPED_REPAIR_SNAPSHOT_SCHEMA_VERSION,
        "successful_command_record_count": len(records),
        "task_facing_success_count": _count(
            trace,
            "remote_command_file_bridge_agent_task_facing_success_count",
        ),
        "todo_identity_count": len(todo_ids),
        "todo_ids": todo_ids[:16],
        "turn_execution_count": turn_counts["execution_count"],
        "turn_committed_count": turn_counts["committed_count"],
        "turn_recovery_required_count": turn_counts["recovery_required_count"],
        "raw_material_recorded": False,
    }


def skillsbench_typed_repair_frontier_signature(
    snapshot: Mapping[str, Any],
    *,
    selected_todo_id: str = "",
) -> str:
    todo_ids = snapshot.get("todo_ids")
    if not isinstance(todo_ids, list):
        todo_ids = []
    safe_todo_ids = [str(todo_id)[:100] for todo_id in todo_ids[-4:] if todo_id]
    return "|".join(
        (
            selected_todo_id[:100] or "no_selected_todo",
            str(_count(snapshot, "successful_command_record_count")),
            str(_count(snapshot, "task_facing_success_count")),
            str(_count(snapshot, "turn_execution_count")),
            str(_count(snapshot, "turn_committed_count")),
            str(_count(snapshot, "turn_recovery_required_count")),
            ",".join(safe_todo_ids) or "no_todo_identity",
        )
    )[:420]


def begin_skillsbench_typed_repair(
    trace: dict[str, Any],
    *,
    trigger_round: int,
    scheduled_round: int,
    trigger_kind: str = "declared_done_below_passing_reward",
) -> bool:
    snapshot = capture_skillsbench_typed_repair_frontier(trace)
    signature = skillsbench_typed_repair_frontier_signature(
        snapshot,
        selected_todo_id=str(trace.get("selected_p0_todo_id") or ""),
    )
    attempted = trace.get("product_mode_typed_repair_attempted_frontiers")
    if not isinstance(attempted, list):
        attempted = []
    attempted = [str(item)[:420] for item in attempted if str(item)][:8]
    if signature in attempted:
        return False

    attempted.append(signature)
    trace["product_mode_typed_repair_required"] = True
    trace["product_mode_typed_repair_pending"] = True
    trace["product_mode_typed_repair_policy_id"] = (
        SKILLSBENCH_TYPED_REPAIR_POLICY_ID
    )
    trace["product_mode_typed_repair_trigger_kind"] = (
        public_safe_compact_text(trigger_kind, limit=120)
        or "declared_done_below_passing_reward"
    )
    trace["product_mode_typed_repair_trigger_round"] = trigger_round
    trace["product_mode_typed_repair_round_entered"] = scheduled_round
    trace["product_mode_typed_repair_round_entered_count"] = _count(
        trace,
        "product_mode_typed_repair_round_entered_count",
    ) + 1
    trace["product_mode_typed_repair_entry_snapshot"] = snapshot
    trace["product_mode_typed_repair_frontier_signature"] = signature
    trace["product_mode_typed_repair_attempted_frontiers"] = attempted
    trace["product_mode_typed_repair_todo_identity_observed"] = False
    trace["product_mode_typed_repair_task_or_validation_delta"] = False
    trace["product_mode_typed_repair_delta_observed"] = False
    trace["product_mode_typed_repair_terminal_receipt_consistent"] = False
    trace["product_mode_typed_repair_open_todo_count_public"] = 0
    trace["product_mode_declared_done_policy"] = (
        "one_typed_repair_then_delta_gated_continue_or_terminal"
    )
    return True


def resolve_skillsbench_typed_repair(
    trace: dict[str, Any],
    *,
    agent_round: int,
) -> dict[str, Any]:
    snapshot = trace.get("product_mode_typed_repair_entry_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    current_records = _command_records(trace)
    baseline_command_count = _count(snapshot, "successful_command_record_count")
    new_records = (
        current_records[baseline_command_count:]
        if baseline_command_count <= len(current_records)
        else []
    )
    todo_ids: list[str] = []
    for record in new_records:
        todo_id = record.get("todo_id", "")
        if (
            record.get("subcommand") in _NEW_TODO_IDENTITY_SUBCOMMANDS
            and todo_id
            and todo_id not in todo_ids
        ):
            todo_ids.append(todo_id)

    task_success_delta = max(
        0,
        _count(trace, "remote_command_file_bridge_agent_task_facing_success_count")
        - _count(snapshot, "task_facing_success_count"),
    )
    todo_identity_observed = bool(todo_ids)
    baseline_turn_count = _count(snapshot, "turn_execution_count")
    current_turns = _turn_executions(trace)
    new_turns = (
        current_turns[baseline_turn_count:]
        if baseline_turn_count <= len(current_turns)
        else []
    )
    turn_execution_count_delta = len(new_turns)
    turn_committed_count_delta = sum(
        loopx_turn_execution_committed(item) for item in new_turns
    )
    turn_recovery_required_count_delta = sum(
        loopx_turn_execution_recovery_required(item) for item in new_turns
    )
    turn_validation_delta = turn_committed_count_delta > 0
    trigger_kind = public_safe_compact_text(
        trace.get("product_mode_typed_repair_trigger_kind"), limit=120
    )
    if trigger_kind == "turn_transaction_recovery":
        task_or_validation_delta = turn_validation_delta
    else:
        task_or_validation_delta = task_success_delta > 0 or turn_validation_delta
    delta_observed = todo_identity_observed or task_or_validation_delta
    outcome = {
        "schema_version": "skillsbench_typed_repair_delta_v0",
        "agent_round": agent_round,
        "todo_identity_observed": todo_identity_observed,
        "todo_ids": todo_ids[:16],
        "task_or_validation_delta": task_or_validation_delta,
        "task_facing_success_delta": task_success_delta,
        "turn_execution_count_delta": turn_execution_count_delta,
        "turn_committed_count_delta": turn_committed_count_delta,
        "turn_recovery_required_count_delta": (
            turn_recovery_required_count_delta
        ),
        "turn_validation_delta": turn_validation_delta,
        "delta_observed": delta_observed,
        "raw_material_recorded": False,
    }
    trace["product_mode_typed_repair_pending"] = False
    trace["product_mode_typed_repair_resolved_round"] = agent_round
    trace["product_mode_typed_repair_todo_identity_observed"] = (
        todo_identity_observed
    )
    trace["product_mode_typed_repair_todo_ids"] = todo_ids[:16]
    trace["product_mode_typed_repair_task_or_validation_delta"] = (
        task_or_validation_delta
    )
    trace["product_mode_typed_repair_task_facing_success_delta"] = (
        task_success_delta
    )
    trace["product_mode_typed_repair_turn_execution_count_delta"] = (
        turn_execution_count_delta
    )
    trace["product_mode_typed_repair_turn_committed_count_delta"] = (
        turn_committed_count_delta
    )
    trace["product_mode_typed_repair_turn_recovery_required_count_delta"] = (
        turn_recovery_required_count_delta
    )
    trace["product_mode_typed_repair_turn_validation_delta"] = turn_validation_delta
    trace["product_mode_typed_repair_delta_observed"] = delta_observed
    trace["product_mode_typed_repair_delta"] = outcome
    return outcome


def advance_skillsbench_typed_repair_controller(
    trace: dict[str, Any],
    *,
    agent_round: int,
    scheduled_round: int,
    max_rounds: int,
    task_instruction_sent: bool,
) -> dict[str, str]:
    """Advance the typed-repair state machine from public controller evidence."""

    if trace.get("product_mode_typed_repair_pending") is True:
        trigger_kind = public_safe_compact_text(
            trace.get("product_mode_typed_repair_trigger_kind"), limit=120
        )
        outcome = resolve_skillsbench_typed_repair(trace, agent_round=agent_round)
        if outcome.get("delta_observed") is not True:
            reason = (
                "turn_repair_round_without_todo_or_committed_validation_delta"
                if trigger_kind == "turn_transaction_recovery"
                else "repair_round_without_todo_task_or_validation_delta"
            )
            record_skillsbench_typed_repair_terminal(
                trace,
                agent_round=agent_round,
                reason=reason,
            )
            return {
                "action": "stop",
                "last_decision": "stop_after_product_mode_typed_repair_without_delta",
            }
        if agent_round >= max_rounds:
            record_skillsbench_typed_repair_terminal(
                trace,
                agent_round=agent_round,
                reason="repair_delta_observed_at_budget_boundary",
            )
            return {
                "action": "stop",
                "last_decision": "stop_after_product_mode_typed_repair_budget",
            }
        return {
            "action": "continue",
            "last_decision": "continue_after_product_mode_typed_repair_delta",
        }

    if not task_instruction_sent:
        return {}
    checkpoint = skillsbench_turn_recovery_checkpoint(trace)
    trace["product_mode_turn_recovery_checkpoint"] = checkpoint
    if checkpoint.get("failed_transaction_with_durable_effects") is True:
        record_skillsbench_typed_repair_terminal(
            trace,
            agent_round=agent_round,
            reason="failed_turn_transaction_has_durable_effects",
        )
        return {
            "action": "stop",
            "last_decision": "stop_after_failed_turn_transaction_with_durable_effects",
        }
    if checkpoint.get("repair_required") is not True:
        return {}
    if not begin_skillsbench_typed_repair(
        trace,
        trigger_round=agent_round,
        scheduled_round=scheduled_round,
        trigger_kind="turn_transaction_recovery",
    ):
        record_skillsbench_typed_repair_terminal(
            trace,
            agent_round=agent_round,
            reason="unchanged_turn_recovery_frontier_already_repaired",
        )
        return {
            "action": "stop",
            "last_decision": "stop_after_repeated_turn_recovery_frontier",
        }
    return {
        "action": "send_repair_prompt",
        "last_decision": (
            "send_product_mode_typed_repair_after_turn_validation_failure"
        ),
        "trigger_kind": "turn_transaction_recovery",
    }


def build_skillsbench_typed_repair_prompt(
    *,
    scheduled_round: int,
    max_rounds: int,
    case_state_path: str,
    loop_alignment_contract: str,
    persistent_constraint_clause: str = "",
    trigger_kind: str = "declared_done_below_passing_reward",
) -> str:
    turn_recovery_clause = (
        " The previous public Turn receipt requires recovery. This round counts "
        "as validation progress only if a later Turn receipt commits, or if a "
        "new scoped todo identity records a genuinely changed frontier."
        if trigger_kind == "turn_transaction_recovery"
        else ""
    )
    return (
        f"Scheduled typed repair/replan round {scheduled_round} of {max_rounds}. "
        "This checkpoint is selected only from the public LoopX frontier. "
        f"Re-read `{case_state_path}` and run the case-local `quota should-run` "
        "contract. If concrete work remains, create one scoped successor agent "
        "todo with a stable identity, claim it, and perform one task-facing repair "
        "or local validation before updating the todo with public-safe evidence. "
        "The fixed loop may continue only when this round adds a todo identity or "
        "a successful task-facing/validation operation; otherwise the controller "
        "will close the unchanged frontier with a typed terminal receipt. "
        f"{turn_recovery_clause} "
        f"{loop_alignment_contract}"
        f"{persistent_constraint_clause}"
    )


def record_skillsbench_typed_repair_terminal(
    trace: dict[str, Any],
    *,
    agent_round: int,
    reason: str,
) -> dict[str, Any]:
    receipt = {
        "schema_version": SKILLSBENCH_TYPED_REPAIR_TERMINAL_RECEIPT_SCHEMA_VERSION,
        "policy_id": SKILLSBENCH_TYPED_REPAIR_POLICY_ID,
        "status": "terminal",
        "reason": reason[:120],
        "agent_round": agent_round,
        "repair_round_entered": _count(
            trace,
            "product_mode_typed_repair_round_entered",
        ),
        "repair_todo_identity_observed": trace.get(
            "product_mode_typed_repair_todo_identity_observed"
        )
        is True,
        "repair_task_or_validation_delta": trace.get(
            "product_mode_typed_repair_task_or_validation_delta"
        )
        is True,
        "terminal_receipt_consistent": True,
        "raw_material_recorded": False,
    }
    trace["product_mode_typed_repair_pending"] = False
    trace["product_mode_typed_repair_terminal"] = True
    trace["product_mode_typed_repair_terminal_round"] = agent_round
    trace["product_mode_typed_repair_terminal_reason"] = reason[:120]
    trace["product_mode_typed_repair_terminal_receipt"] = receipt
    trace["product_mode_typed_repair_terminal_receipt_consistent"] = True
    return receipt
