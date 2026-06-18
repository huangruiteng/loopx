#!/usr/bin/env python3
"""Regression for scoped user gates that still allow non-dependent fallback work."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from goal_harness.status import compact_todo_group, project_asset_todo_summary  # noqa: E402


GOAL_ID = "scoped-user-gate-fallback-fixture"
USER_GATE = (
    "[P1] Decide whether the next private authority gap-sync may read the "
    "registered private design source; until approved, automation "
    "should continue public-safe P1/P2 fallback work."
)
GATED_AGENT_TODO = (
    "[P1] Run the private authority gap-sync against the registered private "
    "design source."
)
FALLBACK_TODO = (
    "[P2] Fold dreaming and periodic replan into the public Goal Harness server "
    "roadmap without reading internal material."
)


def build_status_payload() -> dict:
    user_todos = compact_todo_group(
        [
            {
                "index": 1,
                "done": False,
                "text": USER_GATE,
                "status": "open",
                "task_class": "user_gate",
                "action_kind": "approve_private_authority_sync",
            }
        ],
        source_section="User Todo",
        role="user",
    )
    agent_todos = compact_todo_group(
        [
            {
                "index": 1,
                "done": False,
                "text": GATED_AGENT_TODO,
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "core_private_authority_gap_sync",
            },
            {
                "index": 2,
                "done": False,
                "text": FALLBACK_TODO,
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "server_scheduled_planning_queue",
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert user_todos is not None, user_todos
    assert agent_todos is not None, agent_todos
    user_asset_summary = project_asset_todo_summary(user_todos)
    agent_asset_summary = project_asset_todo_summary(agent_todos)
    assert user_asset_summary is not None, user_todos
    assert agent_asset_summary is not None, agent_todos

    attention_item = {
        "goal_id": GOAL_ID,
        "status": "eligible_with_scoped_user_gate_fallback",
        "waiting_on": "codex",
        "severity": "action",
        "source": "latest_run",
        "recommended_action": GATED_AGENT_TODO,
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
            "next_action": GATED_AGENT_TODO,
            "stop_condition": "stop on fixture boundary",
            "user_todos": user_asset_summary,
            "agent_todos": agent_asset_summary,
            "quota": {
                "compute": 1.0,
                "slot_minutes": 1,
                "allowed_slots": 1440,
                "spent_slots": 0,
                "state": "eligible",
                "reason": "eligible fixture",
            },
        },
        "user_todos": user_todos,
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
    assert guard["requires_user_action"] is True, guard
    assert guard["notify_user_on_gate"] is True, guard
    assert guard["safe_bypass_allowed"] is True, guard
    assert guard["safe_bypass_kind"] == "scoped_user_gate_fallback", guard
    assert guard["recommended_action"] == GATED_AGENT_TODO, guard

    fallback = guard["scoped_user_gate_fallback"]
    assert fallback["notify_user"] is True, fallback
    assert fallback["requires_user_action"] is True, fallback
    assert fallback["blocked_user_gate"]["text"] == USER_GATE, fallback
    assert fallback["blocked_agent_items"][0]["text"] == GATED_AGENT_TODO, fallback
    assert fallback["selected_executable"]["text"] == FALLBACK_TODO, fallback

    interaction = guard["interaction_contract"]
    assert interaction["mode"] == "scoped_user_gate_fallback", interaction
    assert interaction["user_channel"]["action_required"] is True, interaction
    assert interaction["user_channel"]["notify"] == "NOTIFY", interaction
    assert interaction["agent_channel"]["must_attempt"] is True, interaction
    assert interaction["agent_channel"]["delivery_allowed"] is True, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
    assert interaction["agent_channel"]["primary_action"].startswith(
        "[P2] Fold dreaming and periodic replan"
    ), interaction
    assert interaction["cli_channel"]["spend_after_validation"] is True, interaction
    assert interaction["cli_channel"]["spend_policy"] == (
        "spend once after validated writeback"
    ), interaction

    packet_summary = guard["protocol_action_packet"]["summary"]
    assert "actor=agent_with_user_gate" in packet_summary, packet_summary
    assert "user_action_required=true" in packet_summary, packet_summary
    assert "agent_action_required=true" in packet_summary, packet_summary
    assert "user_action_pending=true" in packet_summary, packet_summary
    assert "agent_action=[P2] Fold dreaming and periodic replan" in packet_summary, packet_summary

    markdown = render_quota_should_run_markdown(guard)
    assert "scoped_user_gate_fallback: notify_user=True" in markdown, markdown
    assert f"scoped_user_gate: {USER_GATE}" in markdown, markdown
    assert f"scoped_user_gate_blocked_item[1]: {GATED_AGENT_TODO}" in markdown, markdown
    assert f"scoped_user_gate_selected: {FALLBACK_TODO}" in markdown, markdown
    print("scoped-user-gate-fallback-contract-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
