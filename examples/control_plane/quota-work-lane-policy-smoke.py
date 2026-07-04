#!/usr/bin/env python3
"""Smoke-test the extracted quota work-lane policy helper."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.work_lane import build_work_lane_contract  # noqa: E402


def assert_contract(name: str, contract: dict | None, **expected: object) -> None:
    assert isinstance(contract, dict), (name, contract)
    for key, value in expected.items():
        assert contract.get(key) == value, (name, key, contract)


def main() -> int:
    advancement = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=True,
        todo_counts={"open": 2, "advancement": 1, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement={"todo_id": "todo_adv"},
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
    )
    assert_contract(
        "advancement-with-monitor-context",
        advancement,
        lane="advancement_task",
        obligation="advance_one_bounded_segment",
        must_attempt_work=True,
        monitor_policy="material_transition_only",
    )
    assert advancement["reason_codes"] == [
        "open_agent_todo",
        "external_monitor_context",
    ], advancement

    due_monitor = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 2, "advancement": 1, "monitor": 1},
        monitor_due_count=2,
        due_monitor_items=[
            {"todo_id": "todo_due", "next_due_at": "2000-01-01T00:00:00+00:00"},
            {"todo_id": "todo_due_2", "next_due_at": "2000-01-02T00:00:00+00:00"},
        ],
        first_advancement={"todo_id": "todo_adv"},
        due_monitor_preempts_advancement=True,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
    )
    assert_contract(
        "due-monitor-preempts",
        due_monitor,
        lane="continuous_monitor",
        monitor_kind="todo_monitor_due",
        obligation="attempt_due_monitor",
        must_attempt_work=True,
        monitor_due_count=2,
        selected_todo_id="todo_due",
    )
    assert len(due_monitor["monitor_due_items"]) == 1, due_monitor

    quiet_monitor = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 0, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=None,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
    )
    assert_contract(
        "quiet-monitor",
        quiet_monitor,
        lane="continuous_monitor",
        monitor_kind="todo_monitor",
        obligation="quiet_until_material_monitor_transition",
        must_attempt_work=False,
    )

    explicit_next_action = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 0, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=None,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=True,
        monitor_due_item_limit=1,
        monitor_schedule_gap_count=1,
        monitor_schedule_gap_items=[{"todo_id": "todo_monitor_without_schedule"}],
    )
    assert_contract(
        "explicit-next-action-over-monitor-schedule-gap",
        explicit_next_action,
        lane="advancement_task",
        next_lane="advancement_task",
        obligation="materialize_advancement_todo_or_blocker",
        must_attempt_work=True,
        monitor_policy="material_transition_only",
    )
    assert explicit_next_action["reason_codes"] == [
        "monitor_todo_only",
        "next_action_requires_advancement",
    ], explicit_next_action

    resume_blocked_by_monitor = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 2, "advancement": 0, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=None,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
        resume_blocked_by_monitor_count=1,
        resume_blocked_by_monitor_items=[
            {
                "todo_id": "todo_gated_refactor",
                "resume_when": "todo_done:todo_standing_gate",
            }
        ],
    )
    assert_contract(
        "resume-blocked-by-monitor",
        resume_blocked_by_monitor,
        lane="advancement_task",
        obligation="repair_resume_gate_or_close_standing_monitor",
        must_attempt_work=True,
        monitor_policy="material_transition_only",
        selected_todo_id="todo_gated_refactor",
    )
    assert resume_blocked_by_monitor["reason_codes"] == [
        "monitor_todo_only",
        "resume_blocked_by_open_monitor",
    ], resume_blocked_by_monitor

    dependency_advancement = build_work_lane_contract(
        progress_scope="dependency_observation",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 1, "monitor": 0},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement={"todo_id": "todo_adv"},
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
    )
    assert_contract(
        "dependency-advancement",
        dependency_advancement,
        lane="continuous_monitor",
        monitor_kind="dependency_observation",
        obligation="advance_unless_material_monitor_transition",
        must_attempt_work=True,
        next_lane="advancement_task",
    )

    outcome_followthrough = {
        "source": "post_handoff_latest_run",
        "required": True,
    }
    followthrough = build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 1, "monitor": 0},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement={"todo_id": "todo_adv"},
        due_monitor_preempts_advancement=False,
        outcome_followthrough=outcome_followthrough,
        next_action_requires_advancement=False,
        monitor_due_item_limit=1,
    )
    assert_contract(
        "outcome-followthrough",
        followthrough,
        lane="advancement_task",
        obligation="advance_primary_outcome_or_write_blocker",
        must_attempt_work=True,
    )
    assert followthrough["outcome_followthrough"] == outcome_followthrough, followthrough

    print("quota-work-lane-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
