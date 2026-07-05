from __future__ import annotations

from typing import Any

from ..todos.contract import TODO_TASK_CLASS_MONITOR, normalize_todo_id
from ..todos.projection import todo_item_task_class

EXTERNAL_MONITOR_POLICIES = {
    "material_transition_only",
    "read_only_observation_then_no_spend_if_unchanged",
}
EXTERNAL_MONITOR_REASON_CODES = {
    "external_monitor_context",
    "external_evidence_poll_signal",
}
DUE_MONITOR_OBLIGATION = "attempt_due_monitor"


def work_lane_reason_codes(work_lane_contract: dict[str, Any]) -> set[str]:
    reason_codes = work_lane_contract.get("reason_codes")
    if not isinstance(reason_codes, list):
        return set()
    return {str(value) for value in reason_codes if str(value or "").strip()}


def allows_no_spend_external_monitor_poll(decision: dict[str, Any]) -> bool:
    """Return true when should-run represents observation, not delivery completion."""

    work_lane_contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    reason_codes = work_lane_reason_codes(work_lane_contract)
    monitor_policy = str(work_lane_contract.get("monitor_policy") or "")
    if decision.get("requires_user_action") is True:
        return False
    if decision.get("should_run") is not True:
        return False
    if work_lane_contract.get("must_attempt_work") is not True:
        return False
    if monitor_policy not in EXTERNAL_MONITOR_POLICIES:
        return False
    if reason_codes.intersection(EXTERNAL_MONITOR_REASON_CODES):
        return True
    return bool(decision.get("external_evidence_observation"))


def quota_decision_due_monitor_item(decision: dict[str, Any]) -> dict[str, Any]:
    item = (
        decision.get("agent_lane_next_action")
        if isinstance(decision.get("agent_lane_next_action"), dict)
        else {}
    )
    if todo_item_task_class(item) != TODO_TASK_CLASS_MONITOR:
        item = {}
    if item:
        return item
    contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    selected_todo_id = normalize_todo_id(contract.get("selected_todo_id"))
    due_items = (
        contract.get("monitor_due_items")
        if isinstance(contract.get("monitor_due_items"), list)
        else []
    )
    for due_item in due_items:
        if not isinstance(due_item, dict):
            continue
        if selected_todo_id and normalize_todo_id(due_item.get("todo_id")) != selected_todo_id:
            continue
        if todo_item_task_class(due_item) == TODO_TASK_CLASS_MONITOR:
            return due_item
    return item


def allows_due_monitor_poll(
    decision: dict[str, Any],
    *,
    todo_id: str | None = None,
    target_key: str | None = None,
) -> bool:
    contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    if contract.get("obligation") != DUE_MONITOR_OBLIGATION:
        return False
    if contract.get("must_attempt_work") is not True:
        return False
    item = quota_decision_due_monitor_item(decision)
    if not item:
        return False
    if todo_id and normalize_todo_id(item.get("todo_id")) != normalize_todo_id(todo_id):
        return False
    if target_key:
        item_target_key = str(item.get("target_key") or "").strip()
        if item_target_key != str(target_key).strip():
            return False
    return True
