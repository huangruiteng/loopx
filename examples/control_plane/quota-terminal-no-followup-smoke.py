#!/usr/bin/env python3
"""Smoke-test explicit terminal no-follow-up shutdown across quota and scheduler."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.goals.goal_frontier import (  # noqa: E402
    goal_frontier_is_terminal_no_followup,
)
from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.status import compact_todo_group  # noqa: E402


GOAL_ID = "terminal-no-followup-fixture"
AGENT_ID = "codex-main-control"


def completed_todos(*, role: str) -> dict:
    summary = compact_todo_group(
        [
            {
                "index": 1,
                "todo_id": f"todo_completed_{role}",
                "text": "Complete the bounded fixture work.",
                "role": role,
                "status": "done",
                "done": True,
                "priority": "P1",
                "task_class": "advancement_task" if role == "agent" else "user_action",
                "no_followup": True,
                "claimed_by": AGENT_ID if role == "agent" else None,
            }
        ],
        source_section="Agent Todo" if role == "agent" else "User Todo",
        role=role,
    )
    assert summary is not None
    return summary


def status_payload() -> dict:
    project_asset = {
        "next_action": "No further action is required.",
        "user_todos": completed_todos(role="user"),
        "agent_todos": completed_todos(role="agent"),
    }
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": [AGENT_ID],
    }
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 10,
        "spent_slots": 0,
        "state": "eligible",
        "reason": "eligible fixture",
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "terminal_no_followup",
                    "waiting_on": "codex",
                    "severity": "active",
                    "source": "active_state",
                    "recommended_action": "No further action is required.",
                    "quota": quota,
                    "project_asset": project_asset,
                    "coordination": coordination,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "paused",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": quota,
                    "coordination": coordination,
                    "latest_runs": [],
                }
            ]
        },
    }


def assert_terminal_guard_stops_recurring_automation() -> None:
    guard = build_quota_should_run(
        status_payload(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert guard["status"] == "terminal_no_followup", guard
    assert guard["state"] == "terminal_no_followup", guard
    assert guard["quota"]["state"] == "terminal_no_followup", guard
    assert guard["should_run"] is False, guard
    assert guard["normal_delivery_allowed"] is False, guard
    assert guard["effective_action"] == "terminal_no_followup", guard
    assert guard["decision"] == "skip", guard
    assert guard["execution_obligation"]["must_attempt_work"] is False, guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is False, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is True, guard

    liveness = guard["automation_liveness"]
    assert liveness["automation_action"] == "stop_terminal_no_followup", guard
    assert liveness["keep_active"] is False, guard
    assert liveness["pause_allowed"] is True, guard

    scheduler = guard["scheduler_hint"]
    assert scheduler["action"] == "stop_until_explicit_resume", guard
    assert scheduler["codex_app"]["apply"] == "pause_or_delete_current_heartbeat_if_possible", guard
    assert scheduler["unchanged_poll"]["codex_cli_tui"] == "exit", guard


def assert_terminal_marker_alone_cannot_hide_remaining_work() -> None:
    projection = {
        "normalized_progress": {
            "user_open_count": 0,
            "agent_open_count": 1,
            "agent_advancement_open_count": 1,
            "agent_monitor_open_count": 0,
            "agent_monitor_due_count": 0,
        },
        "remaining_advancement_frontier": {
            "current_agent_claimed_advancement_count": 1,
            "unclaimed_advancement_count": 0,
            "other_agent_claimed_advancement_count": 0,
        },
        "monitor_only_lanes": {"present": False, "quiet_until_material_transition": False},
        "deferred_successors": {"ready_count": 0, "blocked_count": 0, "current_agent_ready_count": 0},
        "acceptance_gaps": [],
        "autonomy_blockers": [],
        "replan_required": False,
    }
    assert goal_frontier_is_terminal_no_followup(
        status="terminal_no_followup",
        projection=projection,
    ) is False
    assert goal_frontier_is_terminal_no_followup(
        status="terminal_no_followup",
        projection={
            "normalized_progress": {},
            "remaining_advancement_frontier": {},
            "monitor_only_lanes": {},
            "deferred_successors": {},
        },
    ) is False


def main() -> int:
    assert_terminal_guard_stops_recurring_automation()
    assert_terminal_marker_alone_cannot_hide_remaining_work()
    print("quota-terminal-no-followup-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
