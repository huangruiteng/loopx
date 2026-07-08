#!/usr/bin/env python3
"""Smoke-test agent-scope wait consistency for legacy work-lane projection."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown
from loopx.status import compact_todo_group


GOAL_ID = "agent-scope-work-lane-consistency-fixture"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-product-capability"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"


def _status_payload() -> dict:
    next_action = (
        "Post-reporting lane should route to the planning/self-repair capability "
        "lane as the next eligible advancement turn."
    )
    agent_todos = compact_todo_group(
        [
            {
                "index": 1,
                "text": "[P1-monitor] Watch the published PR until merge.",
                "role": "agent",
                "status": "open",
                "priority": "P1-monitor",
                "task_class": "continuous_monitor",
                "action_kind": "monitor",
                "claimed_by": SIDE_AGENT,
                "todo_id": "todo_side_monitor",
                "cadence": "60m",
                "next_due_at": FUTURE_DUE_AT,
            },
            {
                "index": 2,
                "text": next_action,
                "role": "agent",
                "status": "open",
                "priority": "P0",
                "task_class": "advancement_task",
                "claimed_by": PRIMARY_AGENT,
                "todo_id": "todo_primary_frontier",
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None
    coordination = {
        "primary_agent": PRIMARY_AGENT,
        "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
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
                    "coordination": coordination,
                    "project_asset": {
                        "next_action": next_action,
                        "agent_todos": agent_todos,
                    },
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "coordination": coordination,
                }
            ]
        },
    }


def main() -> None:
    guard = build_quota_should_run(
        _status_payload(),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )

    assert guard["decision"] == "agent_scope_wait", guard
    assert guard["should_run"] is False, guard
    assert guard["effective_action"] == "agent_scope_wait", guard

    lane = guard["work_lane_contract"]
    assert lane["lane"] == "agent_scope_wait", lane
    assert lane["obligation"] == "wait_for_current_agent_or_unclaimed_advancement", lane
    assert lane["must_attempt_work"] is False, lane
    assert lane["blocked_by_agent_scope"] is True, lane
    assert lane["deferred_work_lane"]["obligation"] == (
        "materialize_advancement_todo_or_blocker"
    ), lane
    assert "agent_scope_wait" in lane["reason_codes"], lane

    obligation = guard["execution_obligation"]
    assert obligation["kind"] == "agent_scope_wait", obligation
    assert obligation["must_attempt_work"] is False, obligation

    contract = guard["interaction_contract"]
    assert contract["mode"] == "agent_scope_wait", contract
    assert contract["agent_channel"]["must_attempt"] is False, contract
    assert contract["agent_channel"]["delivery_allowed"] is False, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is True, contract

    markdown = render_quota_should_run_markdown(guard)
    assert "obligation=materialize_advancement_todo_or_blocker" not in markdown, markdown
    assert (
        "work_lane_contract: lane=agent_scope_wait next=advancement_task" in markdown
    ), markdown
    print("agent-scope-work-lane-consistency-smoke ok")


if __name__ == "__main__":
    main()
