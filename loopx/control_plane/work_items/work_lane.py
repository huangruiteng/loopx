from __future__ import annotations

from typing import Any

from ..todos.projection import todo_priority_label, todo_priority_rank


WORK_LANE_CONTRACT_SCHEMA_VERSION = "work_lane_contract_v1"
WORK_LANE_CURRENT_AGENT_MONITOR_REPAIR_OBLIGATIONS = {
    "attempt_due_monitor",
    "repair_monitor_schedule_metadata",
    "repair_resume_gate_or_close_standing_monitor",
}
WORK_LANE_TODO_MONITOR_DUE_KIND = "todo_monitor_due"
WORK_LANE_TODO_ITEM_FIELDS = (
    "index",
    "text",
    "todo_id",
    "status",
    "priority",
    "task_class",
    "action_kind",
    "claimed_by",
    "target_key",
    "next_due_at",
    "expires_at",
    "resume_when",
    "resume_ready",
    "blocking_monitor_todo_id",
    "result_hash",
)
PRIVATE_BOUNDARY_MONITOR_RESULT_HASHES = {
    "private_boundary_no_authorized_read",
}
PRIVATE_BOUNDARY_MONITOR_ACTION_KIND_HINTS = (
    "private",
    "local_department_doc",
)


def due_monitor_can_preempt_advancement(item: dict[str, Any]) -> bool:
    """Return false for monitor work that requires private/local material."""

    result_hash = str(item.get("result_hash") or "").strip().lower()
    if result_hash in PRIVATE_BOUNDARY_MONITOR_RESULT_HASHES:
        return False
    action_kind = str(item.get("action_kind") or "").strip().lower()
    if any(hint in action_kind for hint in PRIVATE_BOUNDARY_MONITOR_ACTION_KIND_HINTS):
        return False
    priority = str(todo_priority_label(item) or "").strip().upper()
    if "LOCAL" in priority:
        return False
    return True


def due_monitor_preempts_advancement(
    due_monitor: dict[str, Any] | None,
    *,
    first_advancement: dict[str, Any] | None,
) -> bool:
    if not due_monitor:
        return False
    if not due_monitor_can_preempt_advancement(due_monitor):
        return False
    return first_advancement is None or (
        todo_priority_rank(due_monitor) < todo_priority_rank(first_advancement)
    )


def work_lane_contract_requires_current_agent_attempt(
    contract: dict[str, Any] | None,
) -> bool:
    """Return true when the work-lane contract is itself an actionable lane.

    This intentionally covers monitor-derived repair/attempt obligations, not
    every `advancement_task` contract. A generic advancement contract may still
    describe goal-level work claimed by another agent; monitor-derived contracts
    are built from current-agent/unclaimed monitor projections and must not be
    collapsed into agent-scope wait just because no ordinary advancement todo
    exists.
    """

    if not isinstance(contract, dict):
        return False
    if contract.get("must_attempt_work") is not True:
        return False
    obligation = str(contract.get("obligation") or "")
    return obligation in WORK_LANE_CURRENT_AGENT_MONITOR_REPAIR_OBLIGATIONS


def work_lane_contract_is_due_monitor_attempt(
    contract: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(contract, dict)
        and contract.get("monitor_kind") == WORK_LANE_TODO_MONITOR_DUE_KIND
        and contract.get("must_attempt_work") is True
    )


def _compact_work_lane_todo_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in WORK_LANE_TODO_ITEM_FIELDS
        if item.get(key) is not None
    }


def _compact_work_lane_todo_items(
    items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _compact_work_lane_todo_item(item)
        for item in items[:limit]
        if isinstance(item, dict)
    ]


def build_work_lane_contract(
    *,
    progress_scope: str,
    external_poll_signal: bool,
    todo_counts: dict[str, int],
    monitor_due_count: int,
    due_monitor_items: list[dict[str, Any]],
    first_advancement: dict[str, Any] | None,
    due_monitor_preempts_advancement: bool,
    outcome_followthrough: dict[str, Any] | None,
    next_action_requires_advancement: bool,
    monitor_due_item_limit: int,
    monitor_schedule_gap_count: int = 0,
    monitor_schedule_gap_items: list[dict[str, Any]] | None = None,
    resume_blocked_by_monitor_count: int = 0,
    resume_blocked_by_monitor_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return the work-lane execution contract from precomputed quota facts.

    The helper is pure and deliberately receives quota-local observations
    instead of importing quota internals. This keeps the lane routing policy
    testable while the surrounding quota builder still owns extraction from
    status/project-asset payloads.
    """

    open_count = int(todo_counts.get("open") or 0)
    advancement_count = int(todo_counts.get("advancement") or 0)
    monitor_count = int(todo_counts.get("monitor") or 0)
    has_agent_todos = open_count > 0
    has_advancement_todos = advancement_count > 0
    has_monitor_todos = monitor_count > 0
    monitor_only_todos = has_agent_todos and has_monitor_todos and not has_advancement_todos
    first_due_monitor = due_monitor_items[0] if due_monitor_items else None
    blocked_by_monitor_items = resume_blocked_by_monitor_items or []
    schedule_gap_items = monitor_schedule_gap_items or []
    first_schedule_gap = schedule_gap_items[0] if schedule_gap_items else None

    def due_monitor_contract(*, reason_codes: list[str]) -> dict[str, Any]:
        selected = first_due_monitor or {}
        return {
            "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
            "lane": "continuous_monitor",
            "monitor_kind": WORK_LANE_TODO_MONITOR_DUE_KIND,
            "next_lane": "advancement_task" if has_advancement_todos else "continuous_monitor",
            "obligation": "attempt_due_monitor",
            "must_attempt_work": True,
            "reason_codes": reason_codes,
            "monitor_policy": "attempt_due_monitor_once_then_writeback_or_no_spend_if_unchanged",
            "monitor_due_count": max(0, int(monitor_due_count)),
            "monitor_due_items": _compact_work_lane_todo_items(
                due_monitor_items,
                limit=monitor_due_item_limit,
            ),
            "selected_todo_id": selected.get("todo_id"),
            "selected_next_due_at": selected.get("next_due_at"),
            "action": (
                "attempt the selected due continuous_monitor todo; write back only a "
                "material transition, blocker, or compact reschedule/no-change note"
            ),
        }

    if progress_scope != "dependency_observation":
        if has_advancement_todos and due_monitor_preempts_advancement:
            return due_monitor_contract(
                reason_codes=["monitor_due", "due_monitor_priority_preempts_advancement"]
            )
        if has_advancement_todos:
            reason_codes = ["open_agent_todo"]
            if first_due_monitor:
                reason_codes.append("due_monitor_context")
            if external_poll_signal:
                reason_codes.append("external_monitor_context")
            if outcome_followthrough:
                reason_codes.append("outcome_followthrough_required")
            obligation = (
                "advance_primary_outcome_or_write_blocker"
                if outcome_followthrough
                else "advance_one_bounded_segment"
            )
            action = (
                "advance the first executable agent todo to product-path evidence, "
                "benchmark/case evidence, or a precise blocker; do not spend for "
                "another contract-only preparation layer"
                if outcome_followthrough
                else (
                    "advance the first executable agent todo or write a concrete blocker; "
                    "treat monitor todos as auxiliary observation context"
                )
            )
            contract: dict[str, Any] = {
                "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                "lane": "advancement_task",
                "next_lane": "advancement_task",
                "obligation": obligation,
                "must_attempt_work": True,
                "reason_codes": reason_codes,
                "monitor_policy": "material_transition_only",
                "action": action,
            }
            if outcome_followthrough:
                contract["outcome_followthrough"] = outcome_followthrough
            return contract
        if external_poll_signal:
            return {
                "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                "lane": "continuous_monitor",
                "monitor_kind": "external_evidence",
                "next_lane": "continuous_monitor",
                "obligation": "observe_external_evidence_or_blocker",
                "must_attempt_work": True,
                "reason_codes": ["external_evidence_poll_signal"],
                "monitor_policy": "read_only_observation_then_no_spend_if_unchanged",
                "action": (
                    "verify the observable external result handle; if it is absent, "
                    "write a compact blocker instead of rerunning launched work"
                ),
            }
        if resume_blocked_by_monitor_count > 0 and not first_due_monitor:
            selected = blocked_by_monitor_items[0] if blocked_by_monitor_items else {}
            reason_codes = ["resume_blocked_by_open_monitor"]
            if monitor_only_todos:
                reason_codes.insert(0, "monitor_todo_only")
            return {
                "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                "lane": "advancement_task",
                "next_lane": "advancement_task",
                "obligation": "repair_resume_gate_or_close_standing_monitor",
                "must_attempt_work": True,
                "reason_codes": reason_codes,
                "monitor_policy": "material_transition_only",
                "resume_blocked_by_monitor_count": max(0, int(resume_blocked_by_monitor_count)),
                "resume_blocked_by_monitor_items": _compact_work_lane_todo_items(
                    blocked_by_monitor_items,
                    limit=monitor_due_item_limit,
                ),
                "selected_todo_id": selected.get("todo_id"),
                "selected_resume_when": selected.get("resume_when"),
                "action": (
                    "repair the standing monitor dependency: close/supersede the monitor "
                    "after validated evidence, or replan the gated advancement todo with a "
                    "non-blocking monitor contract"
                ),
            }
        if monitor_only_todos:
            if first_due_monitor:
                return due_monitor_contract(
                    reason_codes=["monitor_todo_only", "monitor_due"]
                )
            if next_action_requires_advancement:
                return {
                    "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                    "lane": "advancement_task",
                    "next_lane": "advancement_task",
                    "obligation": "materialize_advancement_todo_or_blocker",
                    "must_attempt_work": True,
                    "reason_codes": ["monitor_todo_only", "next_action_requires_advancement"],
                    "monitor_policy": "material_transition_only",
                    "action": (
                        "materialize the planning/self-repair advancement todo or write a concrete blocker"
                    ),
                }
            if first_schedule_gap:
                return {
                    "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                    "lane": "advancement_task",
                    "monitor_kind": "todo_monitor_schedule_gap",
                    "next_lane": "continuous_monitor",
                    "obligation": "repair_monitor_schedule_metadata",
                    "must_attempt_work": True,
                    "reason_codes": [
                        "monitor_todo_only",
                        "monitor_schedule_metadata_gap",
                    ],
                    "monitor_policy": "repair_schedule_metadata_before_quiet_wait",
                    "monitor_schedule_gap_count": max(0, int(monitor_schedule_gap_count)),
                    "monitor_schedule_gap_items": _compact_work_lane_todo_items(
                        schedule_gap_items,
                        limit=monitor_due_item_limit,
                    ),
                    "selected_todo_id": first_schedule_gap.get("todo_id"),
                    "action": (
                        "repair the selected continuous_monitor todo by adding cadence/"
                        "next_due_at, superseding it, or recording an explicit no-schedule "
                        "policy; do not silently collapse it into monitor_quiet_skip"
                    ),
                }
            return {
                "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
                "lane": "continuous_monitor",
                "monitor_kind": "todo_monitor",
                "next_lane": "continuous_monitor",
                "obligation": "quiet_until_material_monitor_transition",
                "must_attempt_work": False,
                "reason_codes": ["monitor_todo_only"],
                "monitor_policy": "write_once_per_material_transition_else_no_spend",
                "material_transition": (
                    "a monitor todo may write back only material state transitions, regressions, or concrete blockers"
                ),
                "action": "wait quietly for material monitor evidence",
            }
        return None

    reason_codes = ["dependency_observation"]
    if has_advancement_todos:
        reason_codes.append("open_agent_todo")
        if due_monitor_preempts_advancement:
            reason_codes.append("due_monitor_priority_preempts_advancement")
    elif monitor_only_todos:
        reason_codes.append("monitor_todo_only")
        if first_due_monitor:
            reason_codes.append("monitor_due")
    else:
        reason_codes.append("no_open_agent_todo")
    if due_monitor_preempts_advancement:
        return due_monitor_contract(reason_codes=reason_codes)
    return {
        "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
        "lane": "continuous_monitor",
        "monitor_kind": "dependency_observation",
        "next_lane": "advancement_task" if has_advancement_todos else "continuous_monitor",
        "obligation": (
            "advance_unless_material_monitor_transition"
            if has_advancement_todos
            else "attempt_due_monitor"
            if first_due_monitor
            else "quiet_until_material_monitor_transition"
        ),
        "must_attempt_work": has_advancement_todos or bool(first_due_monitor),
        "reason_codes": reason_codes,
        "monitor_policy": "write_once_per_material_transition_else_no_spend",
        "material_transition": (
            "a dependency-state transition may be written back once when it changes the selected goal decision"
        ),
        "action": (
            "advance the first executable agent todo or write a concrete blocker"
            if has_advancement_todos
            else "wait quietly for new external evidence"
        ),
    }
