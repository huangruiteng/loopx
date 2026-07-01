#!/usr/bin/env python3
"""Characterize quota/status control-plane decisions before refactors.

This smoke is intentionally fixture-only. It pins current high-risk routing
behavior so later quota.py/status.py decomposition can move code behind stable
contracts before changing semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402


GOAL_ID = "control-plane-risk-characterization"
AGENT_ID = "codex-product-capability"
PRIMARY_AGENT_ID = "codex-main-control"


def todo_item(
    *,
    todo_id: str,
    title: str,
    priority: str = "P0",
    task_class: str = "advancement_task",
    role: str = "agent",
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    index: int = 1,
    next_due_at: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "todo_id": todo_id,
        "index": index,
        "text": f"[{priority}] {title}",
        "title": title,
        "priority": priority,
        "role": role,
        "status": "open",
        "done": False,
        "task_class": task_class,
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if blocks_agent:
        item["blocks_agent"] = blocks_agent
    if next_due_at:
        item["next_due_at"] = next_due_at
    return item


def todo_summary(items: list[dict[str, Any]], *, role: str) -> dict[str, Any]:
    open_items = [item for item in items if item.get("status") == "open"]
    executable_items = [
        item for item in open_items if item.get("task_class") == "advancement_task"
    ]
    monitor_items = [
        item for item in open_items if item.get("task_class") == "continuous_monitor"
    ]
    due_monitor_items = [item for item in monitor_items if item.get("next_due_at")]
    return {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo" if role == "agent" else "User Todo",
        "total_count": len(items),
        "open_count": len(open_items),
        "done_count": len(items) - len(open_items),
        "items": items,
        "first_open_items": open_items[:3],
        "first_executable_items": executable_items[:3],
        "executable_backlog_items": executable_items,
        "monitor_open_items": monitor_items,
        "monitor_due_items": due_monitor_items,
        "monitor_due_count": len(due_monitor_items),
    }


def status_payload(
    agent_items: list[dict[str, Any]],
    *,
    user_items: list[dict[str, Any]] | None = None,
    quota_state: str = "eligible",
    safe_bypass: bool = False,
) -> dict[str, Any]:
    agent_todos = todo_summary(agent_items, role="agent")
    user_todos = todo_summary(user_items or [], role="user")
    quota = {
        "state": quota_state,
        "reason": "fixture quota",
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 10,
        "spent_slots": 0,
    }
    if safe_bypass:
        quota.update(
            {
                "safe_bypass_allowed": True,
                "safe_bypass_kind": "scoped_user_gate_fallback",
                "safe_bypass_policy": "fixture safe bypass",
            }
        )
    item = {
        "goal_id": GOAL_ID,
        "status": "operator_gate"
        if quota_state == "operator_gate"
        else "active_state_agent_todo",
        "waiting_on": "controller" if quota_state == "operator_gate" else "codex",
        "severity": "active",
        "source": "active_state",
        "recommended_action": "Goal-level route should remain human-facing.",
        "active_state_next_action": "Goal-level route should remain human-facing.",
        "quota": quota,
        "agent_todos": agent_todos,
        "user_todos": user_todos,
        "project_asset": {
            "agent_todos": agent_todos,
            "user_todos": user_todos,
            "next_action": "Goal-level route should remain human-facing.",
        },
        "project_asset_source": "project_asset",
    }
    return {
        "ok": True,
        "goal_count": 1,
        "attention_queue": {"items": [item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "status": "active",
                    "registry_member": True,
                    "coordination": {
                        "primary_agent": PRIMARY_AGENT_ID,
                        "registered_agents": [PRIMARY_AGENT_ID, AGENT_ID],
                    },
                    "latest_runs": [],
                }
            ]
        },
    }


def assert_agent_lane_delivery() -> None:
    payload = status_payload(
        [
            todo_item(
                todo_id="todo_characterize",
                title="Characterize the control-plane route.",
                claimed_by=AGENT_ID,
            )
        ]
    )
    quota = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=AGENT_ID)
    assert quota["decision"] == "run", quota
    assert quota["effective_action"] == "normal_run", quota
    assert quota["interaction_contract"]["agent_channel"]["must_attempt"] is True, quota
    lane = quota["agent_lane_next_action"]
    assert lane["schema_version"] == "agent_lane_next_action_v0", lane
    assert lane["todo_id"] == "todo_characterize", lane
    assert lane["selected_by"] == "current_agent_claimed_todo", lane
    assert lane["preserves_goal_next_action"] is True, lane
    selected = quota["selected_todo"]
    assert selected["schema_version"] == "selected_todo_v0", selected
    assert selected["source"] == "agent_lane_next_action", selected
    assert selected["todo_source"] == "agent_todo_summary.first_executable_items", selected
    assert selected["todo_id"] == lane["todo_id"], selected
    assert selected["selected_by"] == lane["selected_by"], selected
    assert selected["agent_id"] == AGENT_ID, selected

    packet = build_review_packet(payload, goal_id=GOAL_ID)
    assert packet["ok"] is True, packet
    assert packet["project_asset_source"] == "project_asset", packet
    assert packet["agent_todo_items"] == [
        "[P0] Characterize the control-plane route. claimed_by=codex-product-capability"
    ], packet


def assert_scoped_operator_gate_safe_bypass() -> None:
    payload = status_payload(
        [
            todo_item(
                todo_id="todo_refactor_slice",
                title="Continue the refactor slice.",
                claimed_by=AGENT_ID,
            )
        ],
        user_items=[
            todo_item(
                todo_id="todo_primary_gate",
                title="Primary agent reviews an unrelated benchmark gate.",
                role="user",
                task_class="user_gate",
                blocks_agent=PRIMARY_AGENT_ID,
            )
        ],
        quota_state="operator_gate",
        safe_bypass=True,
    )
    quota = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=AGENT_ID)
    assert quota["should_run"] is True, quota
    assert quota["effective_action"] == "normal_run", quota
    assert quota["safe_bypass_allowed"] is True, quota
    assert quota["interaction_contract"]["user_channel"]["action_required"] is False, quota
    assert quota["agent_lane_next_action"]["todo_id"] == "todo_refactor_slice", quota


def assert_due_monitor_context_does_not_steal_advancement() -> None:
    payload = status_payload(
        [
            todo_item(
                todo_id="todo_advancement",
                title="Run the implementation slice.",
                claimed_by=AGENT_ID,
                index=1,
            ),
            todo_item(
                todo_id="todo_monitor",
                title="Poll a lower-priority scheduled monitor.",
                priority="P1",
                task_class="continuous_monitor",
                claimed_by=AGENT_ID,
                index=2,
                next_due_at="2026-01-01T00:00:00+00:00",
            ),
        ]
    )
    quota = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=AGENT_ID)
    contract = quota["work_lane_contract"]
    assert contract["lane"] == "advancement_task", contract
    assert "due_monitor_context" in contract["reason_codes"], contract
    assert quota["agent_lane_next_action"]["todo_id"] == "todo_advancement", quota


def assert_higher_priority_due_monitor_preempts_advancement() -> None:
    payload = status_payload(
        [
            todo_item(
                todo_id="todo_due_monitor",
                title="Poll the due monitor first.",
                priority="P0",
                task_class="continuous_monitor",
                claimed_by=AGENT_ID,
                index=1,
                next_due_at="2026-01-01T00:00:00+00:00",
            ),
            todo_item(
                todo_id="todo_later_advancement",
                title="Run the later implementation slice.",
                priority="P1",
                claimed_by=AGENT_ID,
                index=2,
            ),
        ]
    )
    quota = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=AGENT_ID)
    contract = quota["work_lane_contract"]
    assert contract["lane"] == "continuous_monitor", contract
    assert contract["monitor_kind"] == "todo_monitor_due", contract
    assert contract["selected_todo_id"] == "todo_due_monitor", contract
    assert "due_monitor_priority_preempts_advancement" in contract["reason_codes"], contract
    assert quota.get("agent_lane_next_action") is None, quota
    assert quota["recommended_action"] == "[P0] Poll the due monitor first.", quota


def main() -> None:
    assert_agent_lane_delivery()
    assert_scoped_operator_gate_safe_bypass()
    assert_due_monitor_context_does_not_steal_advancement()
    assert_higher_priority_due_monitor_preempts_advancement()
    print("control-plane-risk-characterization-smoke ok")


if __name__ == "__main__":
    main()
