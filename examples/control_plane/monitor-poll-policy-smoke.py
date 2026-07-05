#!/usr/bin/env python3
"""Smoke-test monitor-poll policy extraction from quota into scheduler."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.scheduler.monitor_poll_policy import (  # noqa: E402
    allows_due_monitor_poll,
    allows_no_spend_external_monitor_poll,
    quota_decision_due_monitor_item,
    work_lane_reason_codes,
)


def assert_external_monitor_observation_policy() -> None:
    base_decision = {
        "should_run": True,
        "work_lane_contract": {
            "must_attempt_work": True,
            "monitor_policy": "material_transition_only",
            "reason_codes": [
                "open_agent_todo",
                "external_monitor_context",
                "",
                None,
            ],
        },
    }
    assert work_lane_reason_codes(base_decision["work_lane_contract"]) == {
        "open_agent_todo",
        "external_monitor_context",
    }
    assert allows_no_spend_external_monitor_poll(base_decision) is True

    blocked_by_user_gate = dict(base_decision, requires_user_action=True)
    assert allows_no_spend_external_monitor_poll(blocked_by_user_gate) is False

    explicit_observation = {
        "should_run": True,
        "external_evidence_observation": {
            "target": "remote job handle",
        },
        "work_lane_contract": {
            "must_attempt_work": True,
            "monitor_policy": "read_only_observation_then_no_spend_if_unchanged",
            "reason_codes": ["open_agent_todo"],
        },
    }
    assert allows_no_spend_external_monitor_poll(explicit_observation) is True

    due_monitor_delivery = {
        "should_run": True,
        "work_lane_contract": {
            "must_attempt_work": True,
            "monitor_policy": "attempt_due_monitor_once_then_writeback_or_no_spend_if_unchanged",
            "reason_codes": ["monitor_due"],
        },
    }
    assert allows_no_spend_external_monitor_poll(due_monitor_delivery) is False


def assert_due_monitor_policy_from_next_action() -> None:
    decision = {
        "work_lane_contract": {
            "obligation": "attempt_due_monitor",
            "must_attempt_work": True,
            "monitor_due_items": [
                {
                    "todo_id": "todo_due_from_contract",
                    "task_class": "continuous_monitor",
                    "target_key": "contract-target",
                }
            ],
        },
        "agent_lane_next_action": {
            "todo_id": "todo_due_from_next",
            "task_class": "continuous_monitor",
            "target_key": "next-target",
        },
    }
    selected = quota_decision_due_monitor_item(decision)
    assert selected["todo_id"] == "todo_due_from_next", selected
    assert allows_due_monitor_poll(decision, todo_id="todo_due_from_next") is True
    assert allows_due_monitor_poll(decision, target_key="next-target") is True
    assert allows_due_monitor_poll(decision, todo_id="todo_due_from_contract") is False
    assert allows_due_monitor_poll(decision, target_key="contract-target") is False


def assert_due_monitor_policy_from_contract_selection() -> None:
    decision = {
        "work_lane_contract": {
            "obligation": "attempt_due_monitor",
            "must_attempt_work": True,
            "selected_todo_id": "todo_due_selected",
            "monitor_due_items": [
                {
                    "todo_id": "todo_advancement_decoy",
                    "task_class": "advancement_task",
                    "target_key": "wrong-kind",
                },
                {
                    "todo_id": "todo_due_selected",
                    "task_class": "continuous_monitor",
                    "target_key": "selected-target",
                },
                {
                    "todo_id": "todo_due_other",
                    "task_class": "continuous_monitor",
                    "target_key": "other-target",
                },
            ],
        },
        "agent_lane_next_action": {
            "todo_id": "todo_advancement_next",
            "task_class": "advancement_task",
            "target_key": "next-decoy",
        },
    }
    selected = quota_decision_due_monitor_item(decision)
    assert selected["todo_id"] == "todo_due_selected", selected
    assert allows_due_monitor_poll(decision, todo_id="todo_due_selected") is True
    assert allows_due_monitor_poll(decision, target_key="selected-target") is True
    assert allows_due_monitor_poll(decision, todo_id="todo_due_other") is False
    assert allows_due_monitor_poll(decision, target_key="other-target") is False

    not_attemptable = {
        **decision,
        "work_lane_contract": {
            **decision["work_lane_contract"],
            "must_attempt_work": False,
        },
    }
    assert allows_due_monitor_poll(not_attemptable, todo_id="todo_due_selected") is False


def main() -> int:
    assert_external_monitor_observation_policy()
    assert_due_monitor_policy_from_next_action()
    assert_due_monitor_policy_from_contract_selection()
    print("monitor-poll-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
