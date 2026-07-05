from __future__ import annotations

from typing import Any

from ...status import compact_todo_group


DEFAULT_FIXTURE_QUOTA = {
    "compute": 1.0,
    "window_hours": 24,
    "slot_minutes": 1,
    "allowed_slots": 10,
    "spent_slots": 0,
    "state": "eligible",
    "reason": "eligible fixture",
}


def quota_todo_summary(
    items: list[dict[str, Any]],
    *,
    role: str = "agent",
    claim_scope_agent_id: str | None = None,
) -> dict[str, Any]:
    summary = compact_todo_group(
        items,
        source_section="Agent Todo" if role == "agent" else "User Todo",
        role=role,
    )
    if claim_scope_agent_id:
        summary["claim_scope"] = {"agent_id": claim_scope_agent_id}
    return summary


def quota_status_payload(
    *,
    goal_id: str,
    status: str,
    agent_todo_items: list[dict[str, Any]],
    recommended_action: str,
    next_action: str | None = None,
    coordination: dict[str, Any] | None = None,
    latest_runs: list[dict[str, Any]] | None = None,
    post_handoff_latest_run: dict[str, Any] | None = None,
    claim_scope_agent_id: str | None = None,
    registry_status: str | None = None,
    goal_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_todos = quota_todo_summary(
        agent_todo_items,
        role="agent",
        claim_scope_agent_id=claim_scope_agent_id,
    )
    quota = dict(DEFAULT_FIXTURE_QUOTA)
    action = next_action if next_action is not None else recommended_action
    item: dict[str, Any] = {
        "goal_id": goal_id,
        "status": status,
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": recommended_action,
        "quota": quota,
        "agent_todos": agent_todos,
        "project_asset": {
            "next_action": action,
            "stop_condition": "stop on private material",
            "agent_todos": agent_todos,
        },
    }
    if post_handoff_latest_run:
        item["handoff_readiness"] = {
            "post_handoff_run_seen": True,
            "handoff_status": "post_handoff_run_seen",
            "post_handoff_latest_run": post_handoff_latest_run,
        }
    if coordination:
        item["coordination"] = coordination

    goal: dict[str, Any] = {
        "id": goal_id,
        "registry_member": True,
        "status": registry_status or status,
        "adapter_kind": "harness_self_improvement",
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": quota.get("compute", 1.0),
            "window_hours": quota.get("window_hours", 24),
            "slot_minutes": quota.get("slot_minutes", 1),
            "allowed_slots": quota.get("allowed_slots", 10),
        },
    }
    if coordination:
        goal["coordination"] = coordination
    if latest_runs is not None:
        goal["latest_runs"] = latest_runs
    if goal_extra:
        goal.update(goal_extra)

    return {
        "ok": True,
        "attention_queue": {"items": [item]},
        "run_history": {"goals": [goal]},
    }
