#!/usr/bin/env python3
"""Smoke-test ordered goal-frontier replan rules through quota routing."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.scheduler.execution_context import (  # noqa: E402
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
)
from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "goal-frontier-rule-smoke"
CURRENT_AGENT = "codex-current"
PEER_AGENT = "codex-peer"


def vision_run() -> dict:
    return {
        "classification": "goal_frontier_rule_smoke",
        "generated_at": "2026-07-18T00:00:00+00:00",
        "agent_id": CURRENT_AGENT,
        "progress_scope": "agent_lane",
        "agent_vision": {
            "schema_version": "goal_vision_replan_contract_v0",
            "agent_id": CURRENT_AGENT,
            "state": "active",
            "vision_patch": {
                "acceptance_summary": "Current agent must keep advancing its own stage.",
                "replan_trigger_summary": "No runnable work satisfies the current stage.",
                "advancement_policy": "repeat_until_closed",
            },
        },
    }


def advancement(todo_id: str, claimed_by: str, *, index: int) -> dict:
    return quota_todo_item(
        todo_id=todo_id,
        index=index,
        text=f"[P1] Advance {todo_id}.",
        claimed_by=claimed_by,
    )


def monitor() -> dict:
    return quota_todo_item(
        todo_id="todo_monitor",
        text="[P1] Monitor a material transition.",
        claimed_by=CURRENT_AGENT,
        task_class="continuous_monitor",
        action_kind="monitor",
        cadence="15m",
        next_due_at="2999-01-01T00:00:00+00:00",
        target_key="goal-frontier-rule-smoke",
    )


def quota(items: list[dict], *, include_vision: bool = True) -> dict:
    agent_todos = quota_todo_summary(
        items,
        role="agent",
        claim_scope_agent_id=CURRENT_AGENT,
    )
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Continue the current agent stage.",
        agent_todos=agent_todos,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [CURRENT_AGENT, PEER_AGENT],
        },
        latest_runs=[vision_run()] if include_vision else [],
    )
    return build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=CURRENT_AGENT,
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )


def main() -> None:
    peer_only = quota([advancement("todo_peer", PEER_AGENT, index=1)])
    assert peer_only["decision"] == "autonomous_replan_required", peer_only
    assert peer_only["goal_frontier_projection"]["replan_required"] is True
    assert peer_only["autonomous_replan_obligation"]["agent_id"] == CURRENT_AGENT

    own_frontier = quota(
        [
            advancement("todo_peer", PEER_AGENT, index=1),
            advancement("todo_current", CURRENT_AGENT, index=2),
        ]
    )
    assert own_frontier["decision"] == "run", own_frontier
    assert own_frontier["selected_todo"]["todo_id"] == "todo_current"
    assert own_frontier["goal_frontier_projection"]["replan_required"] is False

    monitor_only = quota([monitor()], include_vision=False)
    assert monitor_only["decision"] == "autonomous_replan_required", monitor_only
    trigger = monitor_only["autonomous_replan_obligation"]["triggers"][0]
    assert trigger["kind"] == "frontier_exhausted_monitor_lane", trigger
    print("goal-frontier-replan-rules-smoke ok")


if __name__ == "__main__":
    main()
