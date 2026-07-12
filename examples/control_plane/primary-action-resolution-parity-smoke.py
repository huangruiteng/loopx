#!/usr/bin/env python3
"""Pin quota primary-action resolution across the four main decision paths."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
)
from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "primary-action-resolution-parity"
AGENT_ID = "codex-side-bypass"
PRIMARY_AGENT_ID = "codex-main-control"


def status_payload(
    *,
    agent_items: list[dict[str, Any]],
    user_items: list[dict[str, Any]] | None = None,
    quota_state: str = "eligible",
) -> dict[str, Any]:
    durable_action = "Keep the durable goal route unchanged."
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="operator_gate" if quota_state == "operator_gate" else "active",
        recommended_action=durable_action,
        next_action=durable_action,
        active_state_next_action=durable_action,
        agent_todo_items=agent_items,
        user_todo_items=user_items or [],
        quota_state=quota_state,
        project_asset_source="project_asset",
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [PRIMARY_AGENT_ID, AGENT_ID],
        },
        latest_runs=[],
        registry_status="active",
    )


def signature(payload: dict[str, Any]) -> dict[str, Any]:
    contract = payload["interaction_contract"]
    agent_channel = contract["agent_channel"]
    trace = agent_channel.get("resolution_trace") or {}
    assert "authoritative_next_action" not in payload, payload
    return {
        "decision": payload["decision"],
        "effective_action": payload["effective_action"],
        "mode": contract["mode"],
        "primary_action": agent_channel["primary_action"],
        "resolution_summary": trace.get("summary"),
    }


def main() -> int:
    run = build_quota_should_run(
        status_payload(
            agent_items=[
                quota_todo_item(
                    todo_id="todo_run",
                    title="Run the bounded implementation slice.",
                    priority="P1",
                    claimed_by=AGENT_ID,
                )
            ]
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    gate = build_quota_should_run(
        status_payload(
            agent_items=[],
            user_items=[
                quota_todo_item(
                    todo_id="todo_gate",
                    title="Approve the external publication boundary.",
                    role="user",
                    task_class="user_gate",
                    blocks_agent=AGENT_ID,
                )
            ],
            quota_state="operator_gate",
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    monitor = build_quota_should_run(
        status_payload(
            agent_items=[
                quota_todo_item(
                    todo_id="todo_monitor",
                    title="Poll the due monitor.",
                    priority="P0",
                    task_class="continuous_monitor",
                    claimed_by=AGENT_ID,
                    cadence="15m",
                    next_due_at="2026-01-01T00:00:00+00:00",
                )
            ]
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    replan = build_quota_should_run(
        status_payload(
            agent_items=[
                quota_todo_item(
                    todo_id="todo_future_monitor",
                    title="Watch the future monitor window.",
                    priority="P1",
                    task_class="continuous_monitor",
                    claimed_by=AGENT_ID,
                    cadence="15m",
                    next_due_at="2099-01-01T00:00:00+00:00",
                )
            ]
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )

    actual = {
        "run": signature(run),
        "gate": signature(gate),
        "monitor": signature(monitor),
        "replan": signature(replan),
    }
    expected = {
        "run": {
            "decision": "run",
            "effective_action": "normal_run",
            "mode": "bounded_delivery",
            "primary_action": "todo_run: [P1] Run the bounded implementation slice.",
            "resolution_summary": "source=agent_lane drift=true",
        },
        "gate": {
            "decision": "skip",
            "effective_action": "operator_gate_notify",
            "mode": "user_gate",
            "primary_action": "wait for user/owner action after surfacing the blocker or gate",
            "resolution_summary": "source=mode:user_gate drift=true",
        },
        "monitor": {
            "decision": "autonomous_replan_required",
            "effective_action": "autonomous_replan_required",
            "mode": "autonomous_replan",
            "primary_action": (
                "run one bounded autonomous replan slice around todo_monitor: "
                "[P0] Poll the due monitor."
            ),
            "resolution_summary": "source=mode:autonomous_replan drift=true",
        },
        "replan": {
            "decision": "autonomous_replan_required",
            "effective_action": "autonomous_replan_required",
            "mode": "autonomous_replan",
            "primary_action": (
                "run one bounded autonomous replan slice around wait quietly for "
                "material monitor evidence"
            ),
            "resolution_summary": "source=mode:autonomous_replan drift=true",
        },
    }
    assert actual == expected, actual
    print("primary-action-resolution-parity-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
