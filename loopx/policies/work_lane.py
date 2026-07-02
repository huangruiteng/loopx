from __future__ import annotations

from typing import Any


WORK_LANE_CONTRACT_SCHEMA_VERSION = "work_lane_contract_v1"


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

    def due_monitor_contract(*, reason_codes: list[str]) -> dict[str, Any]:
        selected = first_due_monitor or {}
        return {
            "schema_version": WORK_LANE_CONTRACT_SCHEMA_VERSION,
            "lane": "continuous_monitor",
            "monitor_kind": "todo_monitor_due",
            "next_lane": "advancement_task" if has_advancement_todos else "continuous_monitor",
            "obligation": "attempt_due_monitor",
            "must_attempt_work": True,
            "reason_codes": reason_codes,
            "monitor_policy": "attempt_due_monitor_once_then_writeback_or_no_spend_if_unchanged",
            "monitor_due_count": max(0, int(monitor_due_count)),
            "monitor_due_items": due_monitor_items[:monitor_due_item_limit],
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
                "resume_blocked_by_monitor_items": blocked_by_monitor_items[:monitor_due_item_limit],
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
