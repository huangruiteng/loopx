#!/usr/bin/env python3
"""Smoke-test per-agent monitor-only work-mode precedence."""

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


GOAL_ID = "agent-monitor-only-smoke"
CURRENT_AGENT = "codex-current"
PEER_AGENT = "codex-peer"


def decision_for(items: list[dict], *, agent_id: str = CURRENT_AGENT) -> dict:
    agent_todos = quota_todo_summary(
        items,
        role="agent",
        claim_scope_agent_id=agent_id,
    )
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Continue bounded work.",
        agent_todos=agent_todos,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [CURRENT_AGENT, PEER_AGENT],
            "agent_work_modes": {CURRENT_AGENT: "monitor_only"},
        },
    )
    return build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=agent_id,
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )


def assert_monitor_only_wait(decision: dict, *, action: str) -> None:
    assert decision["decision"] == "skip", decision
    assert decision["effective_action"] == action, decision
    assert decision["should_run"] is False, decision
    assert decision["agent_work_mode"] == "monitor_only", decision
    for field in (
        "normal_delivery_allowed",
        "recovery_delivery_allowed",
        "self_repair_allowed",
        "capability_repair_allowed",
        "workspace_repair_allowed",
        "actionable_by_codex",
        "requires_user_action",
    ):
        assert decision[field] is False, (field, decision)
    for field in (
        "autonomous_replan_decision",
        "autonomous_replan_obligation",
        "autonomous_replan_scope",
        "required_reads",
        "scoped_user_gate_fallback",
        "vision_continuation_audit",
        "vision_wait_state",
    ):
        assert field not in decision, (field, decision)
    assert "vision_continuation_audit" not in decision.get(
        "goal_frontier_projection", {}
    ), decision
    interaction = decision["interaction_contract"]
    assert interaction["user_channel"]["notify"] == "DONT_NOTIFY", interaction
    assert interaction["agent_channel"]["must_attempt"] is False, interaction
    assert interaction["agent_channel"]["delivery_allowed"] is False, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is True, interaction
    assert interaction["cli_channel"]["spend_after_validation"] is False, interaction


def main() -> None:
    advancement = quota_todo_item(
        todo_id="todo_advancement",
        title="Open a new implementation topic.",
        claimed_by=CURRENT_AGENT,
    )
    stopped = decision_for([advancement])
    assert_monitor_only_wait(stopped, action="agent_monitor_only")
    assert stopped["interaction_contract"]["mode"] == "agent_monitor_only", stopped
    assert (
        stopped["automation_liveness"]["automation_action"]
        == "keep_active_monitor_only"
    ), stopped
    assert stopped["scheduler_hint"]["action"] == "backoff_agent_monitor_only", stopped
    assert stopped["scheduler_hint"]["cadence_class"] == "agent_monitor_only", stopped

    future_monitor = quota_todo_item(
        todo_id="todo_future_monitor",
        index=2,
        title="Observe an external merge result.",
        task_class="continuous_monitor",
        claimed_by=CURRENT_AGENT,
        cadence="daily",
        next_due_at="2999-01-01T00:00:00Z",
    )
    quiet = decision_for([advancement, future_monitor])
    assert_monitor_only_wait(quiet, action="monitor_quiet_skip")
    assert quiet["work_lane_contract"]["lane"] == "continuous_monitor", quiet

    due_monitor = {
        **future_monitor,
        "todo_id": "todo_due_monitor",
        "next_due_at": "2020-01-01T00:00:00Z",
    }
    due = decision_for([advancement, due_monitor])
    assert due["decision"] == "run", due
    assert due["effective_action"] == "monitor_due", due
    assert due["should_run"] is True, due
    assert due["work_lane_contract"]["lane"] == "continuous_monitor", due
    assert due["work_lane_contract"]["selected_todo_id"] == "todo_due_monitor", due
    assert due["interaction_contract"]["mode"] == "monitor_due", due
    assert due["interaction_contract"]["user_channel"]["notify"] == "DONT_NOTIFY", due
    assert due["interaction_contract"]["agent_channel"]["must_attempt"] is True, due
    assert (
        due["interaction_contract"]["cli_channel"]["spend_after_validation"] is True
    ), due
    assert "autonomous_replan_obligation" not in due, due
    assert due["selected_todo"]["todo_id"] == "todo_due_monitor", due
    assert "todo_advancement" not in due["protocol_action_packet"]["summary"], due

    peer = decision_for(
        [
            quota_todo_item(
                todo_id="todo_peer_advancement",
                title="Peer-owned bounded advancement.",
                claimed_by=PEER_AGENT,
            )
        ],
        agent_id=PEER_AGENT,
    )
    assert peer["effective_action"] == "normal_run", peer
    assert peer["should_run"] is True, peer
    assert peer.get("agent_work_mode") != "monitor_only", peer
    print("agent-monitor-only-work-mode-smoke: ok")


if __name__ == "__main__":
    main()
