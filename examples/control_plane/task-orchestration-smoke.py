#!/usr/bin/env python3
"""Smoke deterministic task-scoped coordination among equal peers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402


GOAL_ID = "task-orchestration-fixture"
PEERS = ["codex-alpha", "codex-beta", "codex-gamma"]


def payload(*, reverse_agents: bool = False) -> dict:
    registered_agents = list(reversed(PEERS)) if reverse_agents else PEERS
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": registered_agents,
    }
    todos = [
        {
            "index": index,
            "status": "open",
            "todo_id": f"todo_peer_{index}",
            "task_class": "advancement_task",
            "priority": "P0",
            "text": f"Advance peer lane {index}.",
            "claimed_by": agent_id,
        }
        for index, agent_id in enumerate(PEERS, start=1)
    ]
    goal = {
        "id": GOAL_ID,
        "status": "active",
        "registry_member": True,
        "adapter_kind": "read_only_project_map_v0",
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
        },
        "coordination": coordination,
        "spawn_policy": {
            "mode": "multi_subagent",
            "allowed": True,
            "max_children": 2,
        },
    }
    attention = {
        "goal_id": GOAL_ID,
        "status": "state_refreshed",
        "waiting_on": "codex",
        "severity": "action",
        "source": "fixture",
        "recommended_action": "coordinate the bounded peer task bundle",
        "coordination": coordination,
        "quota": {**goal["quota"], "state": "eligible", "reason": "eligible fixture"},
        "agent_todos": {
            "schema_version": "todo_summary_v0",
            "source_section": "Agent Todo",
            "total": len(todos),
            "open": len(todos),
            "done": 0,
            "items": todos,
        },
    }
    return {
        "ok": True,
        "attention_queue": {"items": [attention]},
        "run_history": {"goals": [goal]},
    }


def main() -> int:
    decisions = {
        agent_id: build_quota_should_run(
            payload(),
            goal_id=GOAL_ID,
            agent_id=agent_id,
        )
        for agent_id in PEERS
    }
    coordinators = [
        agent_id
        for agent_id, decision in decisions.items()
        if "task_orchestration_contract" in decision
    ]
    assert len(coordinators) == 1, decisions
    coordinator = coordinators[0]
    decision = decisions[coordinator]
    contract = decision["task_orchestration_contract"]
    assert decision["effective_action"] == "coordinate_task_bundle", decision
    assert decision["interaction_contract"]["mode"] == "task_orchestration", decision
    assert contract["coordinator_agent_id"] == coordinator, contract
    assert contract["writeback_owner"] == "task_coordinator", contract
    assert "controller_agent_id" not in contract, contract
    assert "eligible_child_lanes" not in contract, contract
    assert all(
        lane["agent_id"] != coordinator for lane in contract["eligible_peer_lanes"]
    ), contract
    assert len(contract["eligible_peer_lanes"]) == 2, contract
    markdown = render_quota_should_run_markdown(decision)
    assert "task_orchestration: mode=task_scoped_peer" in markdown, markdown

    reversed_decision = build_quota_should_run(
        payload(reverse_agents=True),
        goal_id=GOAL_ID,
        agent_id=coordinator,
    )
    assert reversed_decision["task_orchestration_contract"][
        "coordinator_agent_id"
    ] == coordinator, reversed_decision
    print("task-orchestration-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
