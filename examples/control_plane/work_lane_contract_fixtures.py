"""Shared fixtures for work-lane quota contract smokes."""

from __future__ import annotations


GOAL_ID = "work-lane-fixture"
PAST_DUE_AT = "2000-01-01T00:00:00+00:00"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"


def status_payload(
    *,
    status: str,
    has_agent_todo: bool = True,
    agent_todo_items: list[dict] | None = None,
    user_todo_items: list[dict] | None = None,
    next_action: str = "Observe dependency state and then advance backlog if unchanged.",
    post_handoff_latest_run: dict | None = None,
    coordination: dict | None = None,
) -> dict:
    if agent_todo_items is None:
        agent_todo_items = [
            {
                "index": 1,
                "text": "[P1] Advance the self-repair planning slice with a validation-backed patch.",
                "role": "agent",
                "status": "open",
                "priority": "P1",
            }
        ]
    open_items = agent_todo_items if has_agent_todo else []
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(open_items),
        "open_count": len(open_items),
        "done_count": 0,
        "first_open_items": open_items,
    }
    item = {
        "goal_id": GOAL_ID,
        "status": status,
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": next_action,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "next_action": next_action,
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
    if user_todo_items:
        item["user_todos"] = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "total_count": len(user_todo_items),
            "open_count": len(user_todo_items),
            "done_count": 0,
            "first_open_items": user_todo_items,
            "items": user_todo_items,
        }
    goal_history_item = {
        "id": GOAL_ID,
        "registry_member": True,
        "status": status,
        "adapter_kind": "harness_self_improvement",
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
        },
    }
    if coordination:
        goal_history_item["coordination"] = coordination
    return {
        "ok": True,
        "attention_queue": {
            "items": [item]
        },
        "run_history": {
            "goals": [goal_history_item]
        },
    }
