#!/usr/bin/env python3
"""Smoke-test user gates scoped to a specific agent via blocks_agent."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "agent-scoped-user-gate-fixture"


def todo_item(
    *,
    todo_id: str,
    text: str,
    role: str = "agent",
    task_class: str = "advancement_task",
    claimed_by: str | None = None,
    action_kind: str | None = None,
    blocks_agent: str | None = None,
) -> dict:
    item = {
        "todo_id": todo_id,
        "index": 1,
        "status": "open",
        "done": False,
        "role": role,
        "task_class": task_class,
        "text": text,
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if action_kind:
        item["action_kind"] = action_kind
    if blocks_agent:
        item["blocks_agent"] = blocks_agent
    return item


def todo_summary(item: dict, *, source_section: str) -> dict:
    return {
        "schema_version": "todo_summary_v0",
        "source_section": source_section,
        "total_count": 1,
        "open_count": 1,
        "done_count": 0,
        "first_open_items": [item],
        "first_executable_items": [item]
        if item.get("task_class") == "advancement_task"
        else [],
        "items": [item],
    }


def status_payload(*, blocks_agent: str | None = "codex-product-capability") -> dict:
    user_gate = todo_item(
        todo_id="todo_lark_kanban_gate",
        text="Choose the Lark Kanban target Base before product-capability setup.",
        role="user",
        task_class="user_gate",
        action_kind="lark_kanban_target_decision",
        blocks_agent=blocks_agent,
    )
    agent_todo = todo_item(
        todo_id="todo_benchmark_driver",
        text="[P1] Debug benchmark lifecycle counters and validate the driver.",
        claimed_by="codex-main-control",
    )
    return {
        "ok": True,
        "goal_count": 1,
        "run_count": 0,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "controller",
                    "severity": "blocked",
                    "source": "active_state",
                    "recommended_action": (
                        "Ask for the Lark Kanban target while benchmark work may "
                        "continue on independent agent todos."
                    ),
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 1440,
                        "spent_slots": 0,
                        "state": "operator_gate",
                        "reason": "open user gate",
                    },
                    "user_todos": todo_summary(user_gate, source_section="User Todo"),
                    "agent_todos": todo_summary(agent_todo, source_section="Agent Todo"),
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "adapter_kind": "fixture_adapter_v0",
                    "adapter_status": "connected",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": [
                            "codex-main-control",
                            "codex-product-capability",
                        ],
                    },
                    "latest_runs": [],
                }
            ]
        },
    }


def scoped_no_candidate_status_payload() -> dict:
    primary_agent_todo = todo_item(
        todo_id="todo_primary_benchmark",
        text="[P0] Repair the primary-owned benchmark lifecycle driver.",
        claimed_by="codex-main-control",
    )
    product_monitor = todo_item(
        todo_id="todo_product_monitor",
        text="[P2] Monitor product-capability rollout evidence.",
        task_class="continuous_monitor",
        claimed_by="codex-product-capability",
    )
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": 2,
        "open_count": 2,
        "done_count": 0,
        "first_open_items": [primary_agent_todo, product_monitor],
        "first_executable_items": [primary_agent_todo],
        "executable_backlog_items": [primary_agent_todo],
        "items": [primary_agent_todo, product_monitor],
    }
    return {
        "ok": True,
        "goal_count": 1,
        "run_count": 0,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "",
                    "severity": "active",
                    "source": "active_state",
                    "recommended_action": (
                        "Repair the primary-owned benchmark lifecycle driver."
                    ),
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 1440,
                        "spent_slots": 0,
                        "state": "eligible",
                        "reason": "eligible",
                    },
                    "user_todos": {
                        "schema_version": "todo_summary_v0",
                        "source_section": "User Todo",
                        "total_count": 0,
                        "open_count": 0,
                        "done_count": 0,
                        "first_open_items": [],
                        "items": [],
                    },
                    "agent_todos": agent_todos,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "adapter_kind": "fixture_adapter_v0",
                    "adapter_status": "connected",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": [
                            "codex-main-control",
                            "codex-product-capability",
                        ],
                    },
                    "latest_runs": [],
                }
            ]
        },
    }


def assert_other_agent_user_gate_does_not_block_current_agent() -> None:
    payload = build_quota_should_run(
        status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is True, payload
    assert payload["normal_delivery_allowed"] is True, payload
    assert payload["decision"] == "run", payload
    assert payload["effective_action"] == "normal_run", payload
    assert payload["requires_user_action"] is False, payload
    contract = payload["interaction_contract"]
    assert contract["user_channel"]["action_required"] is False, contract
    assert contract["agent_channel"]["delivery_allowed"] is True, contract
    summary = payload["user_todo_summary"]
    assert summary["open_count"] == 0, summary
    assert summary["other_agent_scoped_open_count"] == 1, summary
    assert summary["other_agent_scoped_items"][0]["blocks_agent"] == "codex-product-capability"
    override = payload["agent_scoped_user_gate_override"]
    assert override["from_state"] == "operator_gate", override
    assert override["to_state"] == "eligible", override
    assert payload["agent_lane_next_action"]["todo_id"] == "todo_benchmark_driver", payload


def assert_target_agent_still_blocks_on_its_user_gate() -> None:
    payload = build_quota_should_run(
        status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    assert payload["should_run"] is False, payload
    assert payload["normal_delivery_allowed"] is False, payload
    assert payload["requires_user_action"] is True, payload
    contract = payload["interaction_contract"]
    assert contract["mode"] == "user_gate", contract
    assert contract["user_channel"]["action_required"] is True, contract
    assert contract["agent_channel"]["delivery_allowed"] is False, contract
    summary = payload["user_todo_summary"]
    assert summary["open_count"] == 1, summary
    assert "agent_scoped_user_gate_override" not in payload, payload


def assert_unscoped_user_gate_remains_global() -> None:
    payload = build_quota_should_run(
        status_payload(blocks_agent=None),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    assert payload["should_run"] is False, payload
    assert payload["requires_user_action"] is True, payload
    assert payload["interaction_contract"]["mode"] == "user_gate", payload
    assert payload["user_todo_summary"]["open_count"] == 1, payload
    assert "agent_scoped_user_gate_override" not in payload, payload


def assert_agent_without_advancement_candidate_enters_scope_wait() -> None:
    payload = build_quota_should_run(
        scoped_no_candidate_status_payload(),
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    assert payload["decision"] == "agent_scope_wait", payload
    assert payload["should_run"] is False, payload
    assert payload["normal_delivery_allowed"] is False, payload
    assert payload.get("agent_lane_next_action") is None, payload
    frontier = payload["agent_scope_frontier"]
    assert frontier["action"] == "agent_scope_wait", frontier
    assert frontier["candidate_counts"]["current_agent_claimed_advancement_count"] == 0
    assert frontier["candidate_counts"]["other_agent_claimed_advancement_count"] == 1
    contract = payload["interaction_contract"]
    assert contract["user_channel"]["action_required"] is False, contract
    assert contract["agent_channel"]["must_attempt"] is False, contract
    assert contract["agent_channel"]["delivery_allowed"] is False, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is True, contract
    scheduler = payload["scheduler_hint"]
    assert scheduler["schema_version"] == "scheduler_hint_v0", scheduler
    assert scheduler["action"] == "backoff_until_reassigned", scheduler
    assert scheduler["codex_app"]["recommended_interval_minutes"] == 10, scheduler
    assert scheduler["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=10", scheduler
    assert scheduler["codex_app"]["example_progression_minutes"] == [10, 20, 30], scheduler
    assert scheduler["codex_cli_tui"]["unchanged_poll_limit"] == 3, scheduler
    assert scheduler["codex_cli_tui"]["final_quota_replan_check"]["enabled"] is True, scheduler
    assert scheduler["claude_code_loop"]["after_limit"] == "stop_loop", scheduler
    assert scheduler["claude_code_loop"]["unchanged_poll_limit"] == 3, scheduler
    reset = scheduler["reset_policy"]
    assert reset["schema_version"] == "scheduler_reset_policy_v0", reset
    assert reset["profile_action"] == "backoff_until_reassigned", reset
    assert isinstance(reset["reset_token"], str) and len(reset["reset_token"]) == 16, reset
    assert reset["host_state_key"] == "scheduler_hint.reset_policy.reset_token", reset
    assert reset["codex_app_initial_interval_minutes"] == 10, reset
    assert reset["codex_app_initial_rrule"] == "FREQ=MINUTELY;INTERVAL=10", reset
    assert reset["identity_keys"] == scheduler["unchanged_identity_keys"], reset
    assert reset["identity_snapshot"]["agent_identity.agent_id"] == payload["agent_identity"]["agent_id"], reset
    assert "reset_token_changed" in reset["reset_conditions"], reset
    assert "new_or_reassigned_todo" in reset["reset_conditions"], reset
    assert "active_work_projected" in reset["reset_conditions"], reset
    assert reset["no_spend_for_reset"] is True, reset
    assert "scheduler=backoff_until_reassigned" in payload["protocol_action_packet"]["summary"], payload


def main() -> int:
    assert_other_agent_user_gate_does_not_block_current_agent()
    assert_target_agent_still_blocks_on_its_user_gate()
    assert_unscoped_user_gate_remains_global()
    assert_agent_without_advancement_candidate_enters_scope_wait()
    print("quota-agent-scoped-user-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
