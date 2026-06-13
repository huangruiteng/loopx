#!/usr/bin/env python3
"""Smoke-test compact protocol action packets for quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown


GOAL_ID = "protocol-packet-fixture"
ADVANCEMENT_TODO = (
    "[P1] LLM-assisted protocol simplification research spike: compare a "
    "deterministic action packet with an optional Codex/LLM router before "
    "adding direct API wiring."
)
MONITOR_TODO = (
    "[P2] Meta canary/readiness observation lane: keep status health observable."
)
USER_TODO = "[P1] Decide whether to approve a no-submit setup check."


def status_payload(
    *,
    agent_todos: list[dict],
    user_todos: list[dict] | None = None,
    status: str = "protocol_packet_fixture",
    next_action: str = "Advance the P1 protocol simplification spike.",
) -> dict:
    agent_summary = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(agent_todos),
        "open_count": len(agent_todos),
        "done_count": 0,
        "first_open_items": agent_todos[:3],
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
            "agent_todos": agent_summary,
        },
    }
    if user_todos:
        user_summary = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "total_count": len(user_todos),
            "open_count": len(user_todos),
            "done_count": 0,
            "first_open_items": user_todos,
            "items": user_todos,
        }
        item["user_todos"] = user_summary
        item["project_asset"]["user_todos"] = user_summary
    payload = {
        "ok": True,
        "attention_queue": {
            "items": [item],
        },
        "run_history": {
            "goals": [
                {
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
            ]
        },
    }
    advancement_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "advancement_task"
        or "research spike" in str(item.get("text") or "")
    ]
    monitor_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "continuous_monitor"
        or "observation lane" in str(item.get("text") or "")
    ]
    if advancement_items:
        payload["attention_queue"]["autonomous_backlog_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(advancement_items),
            "task_class": "advancement_task",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "advancement_task",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in advancement_items
            ],
        }
    if monitor_items:
        payload["attention_queue"]["autonomous_monitor_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(monitor_items),
            "task_class": "continuous_monitor",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "continuous_monitor",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in monitor_items
            ],
        }
    return payload


def todo(index: int, text: str, *, priority: str, task_class: str | None = None) -> dict:
    item = {
        "index": index,
        "text": text,
        "role": "agent",
        "status": "open",
        "priority": priority,
    }
    if task_class:
        item["task_class"] = task_class
    return item


def user_todo(index: int, text: str) -> dict:
    return {
        "index": index,
        "text": text,
        "role": "user",
        "status": "open",
        "priority": "P1",
    }


def assert_advancement_packet_prefers_backlog_candidate() -> None:
    guard = build_quota_should_run(
        status_payload(
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
                todo(2, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert packet["schema_version"] == "protocol_action_packet_v0", packet
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "LLM-assisted protocol simplification" in packet["summary"], packet
    assert "compare a deterministic" not in packet["summary"], packet
    assert "llm=no_api" in packet["summary"], packet
    markdown = render_quota_should_run_markdown(guard)
    assert "protocol_action_packet: schema=protocol_action_packet_v0 actor=agent" in markdown, markdown


def assert_advancement_packet_keeps_user_todo_pending() -> None:
    guard = build_quota_should_run(
        status_payload(
            agent_todos=[
                todo(1, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
            ],
            user_todos=[user_todo(1, USER_TODO)],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "user_action_pending=true" in packet["summary"], packet
    assert f"user_action={USER_TODO}" in packet["summary"], packet
    assert "agent_action=[P1] LLM-assisted protocol simplification research spike" in packet["summary"], packet
    assert f"agent_action={USER_TODO}" not in packet["summary"], packet


def assert_monitor_only_packet_keeps_user_todo_pending() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_fixture",
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
            ],
            user_todos=[user_todo(1, USER_TODO)],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=false" in packet["summary"], packet
    assert "quiet_noop_allowed=true" in packet["summary"], packet
    assert "user_action_pending=true" in packet["summary"], packet
    assert USER_TODO in packet["summary"], packet
    assert guard.get("notify_user_on_open_todo") is None, guard


def assert_monitor_only_packet_allows_quiet_noop() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_fixture",
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=false" in packet["summary"], packet
    assert "quiet_noop_allowed=true" in packet["summary"], packet
    assert "lane=continuous_monitor" in packet["summary"], packet
    assert "material monitor transition" in packet["summary"], packet


def main() -> None:
    assert_advancement_packet_prefers_backlog_candidate()
    assert_advancement_packet_keeps_user_todo_pending()
    assert_monitor_only_packet_keeps_user_todo_pending()
    assert_monitor_only_packet_allows_quiet_noop()
    print("ok: protocol action packet smoke")


if __name__ == "__main__":
    main()
