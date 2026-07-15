from __future__ import annotations

from typing import Any, Mapping

from loopx.control_plane.runtime.public_safety import compact_loopx_command_records
from loopx.control_plane.runtime.public_safety import public_safe_compact_text


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
    "product_mode_typed_repair_terminal_round",
    "product_mode_typed_repair_open_todo_count_public",
)
_TYPED_REPAIR_TEXT_FIELDS = (
    "product_mode_typed_repair_policy_id",
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
    return {
        "schema_version": SKILLSBENCH_TYPED_REPAIR_SNAPSHOT_SCHEMA_VERSION,
        "successful_command_record_count": len(records),
        "task_facing_success_count": _count(
            trace,
            "remote_command_file_bridge_agent_task_facing_success_count",
        ),
        "todo_identity_count": len(todo_ids),
        "todo_ids": todo_ids[:16],
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
            ",".join(safe_todo_ids) or "no_todo_identity",
        )
    )[:420]


def begin_skillsbench_typed_repair(
    trace: dict[str, Any],
    *,
    trigger_round: int,
    scheduled_round: int,
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
    task_or_validation_delta = task_success_delta > 0
    delta_observed = todo_identity_observed or task_or_validation_delta
    outcome = {
        "schema_version": "skillsbench_typed_repair_delta_v0",
        "agent_round": agent_round,
        "todo_identity_observed": todo_identity_observed,
        "todo_ids": todo_ids[:16],
        "task_or_validation_delta": task_or_validation_delta,
        "task_facing_success_delta": task_success_delta,
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
    trace["product_mode_typed_repair_delta_observed"] = delta_observed
    trace["product_mode_typed_repair_delta"] = outcome
    return outcome


def build_skillsbench_typed_repair_prompt(
    *,
    scheduled_round: int,
    max_rounds: int,
    case_state_path: str,
    loop_alignment_contract: str,
    persistent_constraint_clause: str = "",
) -> str:
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
