#!/usr/bin/env python3
"""Smoke-test primary controller routing for multi-subagent goals."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402


GOAL_ID = "controller-child-lanes"
PRIMARY_AGENT = "codex-main-control"
CHILD_AGENT_A = "codex-a-share-alpha"
CHILD_AGENT_B = "codex-us-qdii-alpha"


def goal() -> dict:
    return {
        "id": GOAL_ID,
        "status": "active",
        "registry_member": True,
        "lifecycle_phase": "refreshed",
        "adapter_kind": "read_only_project_map_v0",
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
        },
        "coordination": {
            "registered_agents": [
                PRIMARY_AGENT,
                CHILD_AGENT_A,
                CHILD_AGENT_B,
            ],
            "primary_agent": PRIMARY_AGENT,
        },
        "spawn_policy": {
            "mode": "multi_subagent",
            "allowed": True,
            "max_children": 2,
        },
    }


def attention_item() -> dict:
    return {
        "goal_id": GOAL_ID,
        "status": "state_refreshed",
        "waiting_on": "codex",
        "severity": "action",
        "source": "fixture",
        "recommended_action": "orchestrate child alpha lanes",
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "1 compute quota; eligible for the next automatic agent turn",
        },
        "agent_todos": {
            "schema_version": "todo_summary_v0",
            "source_section": "Agent Todo",
            "total": 4,
            "open": 4,
            "done": 0,
            "items": [
                {
                    "index": 1,
                    "done": False,
                    "status": "open",
                    "todo_id": "todo_controller_worker",
                    "task_class": "advancement_task",
                    "priority": "P0",
                    "text": "Controller should not do this worker lane directly.",
                    "claimed_by": PRIMARY_AGENT,
                },
                {
                    "index": 2,
                    "done": False,
                    "status": "open",
                    "todo_id": "todo_a_share",
                    "task_class": "advancement_task",
                    "priority": "P0",
                    "text": "Explore A-share PIT industry cache route.",
                    "claimed_by": CHILD_AGENT_A,
                },
                {
                    "index": 3,
                    "done": False,
                    "status": "open",
                    "todo_id": "todo_qdii",
                    "task_class": "advancement_task",
                    "priority": "P0",
                    "text": "Explore QDII dip-ladder route.",
                    "claimed_by": CHILD_AGENT_B,
                },
                {
                    "index": 4,
                    "done": False,
                    "status": "open",
                    "todo_id": "todo_review",
                    "task_class": "continuous_monitor",
                    "priority": "P1",
                    "text": "Review accepted child-lane evidence and write back final state.",
                    "claimed_by": PRIMARY_AGENT,
                },
            ],
        },
    }


def build_payload() -> dict:
    return {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "attention_queue": {"items": [attention_item()]},
        "run_history": {"goals": [goal()]},
    }


def build_peer_payload(*, reverse_agents: bool = False) -> dict:
    payload = build_payload()
    registered_agents = [PRIMARY_AGENT, CHILD_AGENT_A, CHILD_AGENT_B]
    if reverse_agents:
        registered_agents.reverse()
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": registered_agents,
    }
    payload["run_history"]["goals"][0]["coordination"] = coordination
    payload["attention_queue"]["items"][0]["coordination"] = coordination
    return payload


def main() -> int:
    decision = build_quota_should_run(
        build_payload(),
        goal_id=GOAL_ID,
        agent_id=PRIMARY_AGENT,
    )
    markdown = render_quota_should_run_markdown(decision)
    contract = decision["subagent_orchestration_contract"]

    assert decision["effective_action"] == "orchestrate_child_lanes", decision
    assert "spawn or resume eligible child lanes" in decision["recommended_action"], decision
    assert decision["work_lane_contract"]["obligation"] == "orchestrate_child_lanes", decision
    assert decision["execution_obligation"]["contract_obligation"] == "orchestrate_child_lanes", decision
    assert "agent_lane_next_action" not in decision, decision
    assert decision["goal_route_hint"]["route_decision"] == "orchestrate_child_lanes", decision
    assert "current_agent_next_action" not in decision["goal_route_hint"], decision
    assert contract["mode"] == "multi_subagent", contract
    assert contract["controller_agent_id"] == PRIMARY_AGENT, contract
    assert contract["spawn_required"] is True, contract
    assert contract["writeback_owner"] == "controller", contract
    assert [lane["agent_id"] for lane in contract["eligible_child_lanes"]] == [
        CHILD_AGENT_A,
        CHILD_AGENT_B,
    ], contract
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_a_share",
        "todo_qdii",
    ], contract
    assert decision["interaction_contract"]["agent_channel"]["primary_action"].startswith(
        "spawn/resume child lanes"
    ), decision
    assert "subagent_orchestration: mode=multi_subagent spawn_required=True child_lanes=2" in markdown, markdown

    peer_decisions = {
        agent_id: build_quota_should_run(
            build_peer_payload(),
            goal_id=GOAL_ID,
            agent_id=agent_id,
        )
        for agent_id in (PRIMARY_AGENT, CHILD_AGENT_A, CHILD_AGENT_B)
    }
    coordinators = [
        agent_id
        for agent_id, peer_decision in peer_decisions.items()
        if "task_orchestration_contract" in peer_decision
    ]
    assert len(coordinators) == 1, peer_decisions
    coordinator = coordinators[0]
    peer_decision = peer_decisions[coordinator]
    peer_contract = peer_decision["task_orchestration_contract"]
    assert peer_decision["effective_action"] == "coordinate_task_bundle", peer_decision
    assert peer_decision["interaction_contract"]["mode"] == "task_orchestration", peer_decision
    assert peer_decision["goal_route_hint"]["route_decision"] == (
        "coordinate_task_bundle"
    ), peer_decision
    assert peer_contract["coordinator_agent_id"] == coordinator, peer_contract
    assert peer_contract["writeback_owner"] == "task_coordinator", peer_contract
    assert "controller_agent_id" not in peer_contract, peer_contract
    assert "eligible_child_lanes" not in peer_contract, peer_contract
    assert all(
        lane["agent_id"] != coordinator
        for lane in peer_contract["eligible_peer_lanes"]
    ), peer_contract
    peer_markdown = render_quota_should_run_markdown(peer_decision)
    assert "task_orchestration: mode=task_scoped_peer" in peer_markdown, peer_markdown

    reversed_decision = build_quota_should_run(
        build_peer_payload(reverse_agents=True),
        goal_id=GOAL_ID,
        agent_id=coordinator,
    )
    assert reversed_decision["task_orchestration_contract"][
        "coordinator_agent_id"
    ] == coordinator, reversed_decision
    print("primary-controller-subagent-orchestration-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
