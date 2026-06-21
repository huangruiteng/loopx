#!/usr/bin/env python3
"""Regression for surfacing blocked high-priority work while using fallback."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.status import compact_todo_group, project_asset_todo_summary  # noqa: E402


GOAL_ID = "blocked-priority-fallback-fixture"
BLOCKED_CORE_TODO = "[P0] Repair the primary benchmark mode before selecting another case."
FALLBACK_TODO = (
    "[P1] Continue one safe benchmark attribution cleanup while the primary "
    "mode is blocked."
)


def build_status_payload() -> dict:
    agent_todos = compact_todo_group(
        [
            {
                "index": 1,
                "done": False,
                "text": BLOCKED_CORE_TODO,
                "status": "blocked",
                "task_class": "advancement_task",
                "action_kind": "repair_primary_mode",
            },
            {
                "index": 2,
                "done": False,
                "text": FALLBACK_TODO,
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "safe_fallback_cleanup",
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None, agent_todos
    asset_summary = project_asset_todo_summary(agent_todos)
    assert asset_summary is not None, agent_todos
    attention_item = {
        "goal_id": GOAL_ID,
        "status": "eligible_with_blocked_priority_fallback",
        "waiting_on": "codex",
        "severity": "action",
        "source": "latest_run",
        "recommended_action": (
            "Use the first executable fallback only after surfacing the blocked core todo."
        ),
        "quota": {
            "compute": 1.0,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "owner": "codex",
            "next_action": (
                "Use the first executable fallback only after surfacing the blocked core todo."
            ),
            "stop_condition": "stop on fixture boundary",
            "agent_todos": asset_summary,
            "quota": {
                "compute": 1.0,
                "slot_minutes": 1,
                "allowed_slots": 1440,
                "spent_slots": 0,
                "state": "eligible",
                "reason": "eligible fixture",
            },
        },
        "agent_todos": agent_todos,
    }
    return {
        "ok": True,
        "attention_queue": {"items": [attention_item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }


def main() -> int:
    guard = build_quota_should_run(build_status_payload(), goal_id=GOAL_ID)
    assert guard["should_run"] is True, guard
    assert guard["recommended_action"] == FALLBACK_TODO, guard
    assert guard["heartbeat_recommendation"]["notify"] == "NOTIFY", guard

    fallback = guard["blocked_priority_fallback"]
    assert fallback["notify_user"] is True, fallback
    assert fallback["requires_user_action"] is False, fallback
    assert fallback["blocked_items"][0]["text"] == BLOCKED_CORE_TODO, fallback
    assert fallback["selected_executable"]["text"] == FALLBACK_TODO, fallback

    interaction = guard["interaction_contract"]
    assert interaction["mode"] == "bounded_delivery", interaction
    assert interaction["user_channel"]["action_required"] is False, interaction
    assert interaction["user_channel"]["notify"] == "NOTIFY", interaction
    assert interaction["agent_channel"]["must_attempt"] is True, interaction
    assert interaction["agent_channel"]["delivery_allowed"] is True, interaction
    primary_action = interaction["agent_channel"]["primary_action"]
    assert primary_action.startswith("[P1] Continue one safe benchmark attribution cleanup"), interaction
    assert "Repair the primary benchmark mode" not in primary_action, interaction

    packet_summary = guard["protocol_action_packet"]["summary"]
    assert "user_action_required=false" in packet_summary, packet_summary
    assert "agent_action_required=true" in packet_summary, packet_summary
    assert "lane=advancement_task" in packet_summary, packet_summary
    assert "agent_action=[P1] Continue one safe benchmark attribution cleanup" in packet_summary, packet_summary

    markdown = render_quota_should_run_markdown(guard)
    assert "blocked_priority_fallback: notify_user=True" in markdown, markdown
    assert f"blocked_priority_item[1]: {BLOCKED_CORE_TODO}" in markdown, markdown
    assert f"blocked_priority_selected: {FALLBACK_TODO}" in markdown, markdown
    print("blocked-priority-fallback-contract-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
