from __future__ import annotations

from typing import Any

from loopx.control_plane.quota.heartbeat_recommendation import (
    build_heartbeat_recommendation,
)
from loopx.control_plane.work_items.delivery_outcome import DeliveryOutcome


GOAL_ID = "heartbeat-recommendation-rules"


def _todo_summary(*, role: str, open_count: int) -> dict[str, Any]:
    task_class = "user_gate" if role == "user" else "advancement_task"
    return {
        "schema_version": "todo_summary_v0",
        "source_section": f"{role.title()} Todo",
        "open_count": open_count,
        "first_open_items": [
            {
                "todo_id": f"todo_{role}_{index}",
                "status": "open",
                "task_class": task_class,
                "text": f"[P0] {role} work",
            }
            for index in range(open_count)
        ],
    }


def _recommend(
    item: dict[str, Any] | None = None,
    *,
    state: str = "eligible",
    should_run: bool = True,
    user_open: int = 0,
    agent_open: int = 0,
    lane: str = "advancement",
    must_attempt_work: bool = True,
    stall_self_repair: dict[str, Any] | None = None,
    replan_obligation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_heartbeat_recommendation(
        item or {},
        goal_id=GOAL_ID,
        state=state,
        should_run=should_run,
        user_todo_summary=_todo_summary(role="user", open_count=user_open),
        agent_todo_summary=_todo_summary(role="agent", open_count=agent_open),
        work_lane_contract={
            "schema_version": "work_lane_contract_v0",
            "lane": lane,
            "must_attempt_work": must_attempt_work,
        },
        stall_self_repair=stall_self_repair,
        replan_obligation=replan_obligation,
        select_replan_obligation=False,
    )


def _required_replan() -> dict[str, Any]:
    return {
        "schema_version": "autonomous_replan_obligation_v0",
        "required": True,
        "stall_threshold": 2,
        "trigger_count": 1,
        "triggers": [{"kind": "dead_monitor_repeat"}],
        "stop_condition": "stop at a real owner boundary",
    }


def test_scope_projection_repair_preempts_operator_gate() -> None:
    recommendation = _recommend(
        state="operator_gate",
        stall_self_repair={
            "allowed": True,
            "trigger": "user_gate_scope_projection_drift",
            "recommended_mode": "repair_user_gate_scope",
            "repair_focus": "restore the exact blocked lane",
        },
    )

    assert recommendation["recommended_mode"] == "repair_user_gate_scope"
    assert recommendation["notify"] == "DONT_NOTIFY"
    assert recommendation["repair_focus"] == "restore the exact blocked lane"


def test_operator_gate_preempts_unrelated_stall_repair_and_replan() -> None:
    recommendation = _recommend(
        state="operator_gate",
        stall_self_repair={
            "allowed": True,
            "trigger": "small_scale_streak",
            "recommended_mode": "expand_delivery",
        },
        replan_obligation=_required_replan(),
    )

    assert recommendation["recommended_mode"] == "ask_operator_gate"
    assert recommendation["notify"] == "NOTIFY"


def test_required_replan_preempts_waiting_user_todo() -> None:
    recommendation = _recommend(
        state="waiting",
        user_open=1,
        replan_obligation=_required_replan(),
    )

    assert recommendation["recommended_mode"] == "autonomous_replan_required"
    assert recommendation["notify"] == "NOTIFY"
    assert recommendation["replan_obligation"]["trigger_count"] == 1


def test_waiting_user_todo_preempts_quota_skip() -> None:
    recommendation = _recommend(
        {"waiting_on": "external_evidence"},
        state="waiting",
        should_run=False,
        user_open=1,
    )

    assert recommendation["recommended_mode"] == "blocker_push_notify"
    assert recommendation["notify"] == "NOTIFY"
    assert recommendation["repeat_notification_required"] is True


def test_outcome_floor_blocker_preempts_quota_skip() -> None:
    recommendation = _recommend(
        {
            "quota": {
                "handoff_outcome_floor_block": True,
                "reason": "primary outcome evidence is missing",
            }
        },
        state="focus_wait",
        should_run=False,
    )

    assert recommendation["recommended_mode"] == "report_handoff_outcome_blocker"
    assert recommendation["notify"] == "NOTIFY"
    assert recommendation["reason"] == "primary outcome evidence is missing"


def test_quota_skip_preempts_agent_command() -> None:
    recommendation = _recommend(
        {"agent_command": "loopx bounded-command"},
        state="throttled",
        should_run=False,
    )

    assert recommendation["recommended_mode"] == "quota_skip"
    assert "throttled" in recommendation["reason"]


def test_agent_command_preempts_monitor_lane() -> None:
    recommendation = _recommend(
        {"agent_command": "loopx bounded-command"},
        lane="continuous_monitor",
        must_attempt_work=False,
    )

    assert recommendation["recommended_mode"] == "run_agent_command"
    assert recommendation["command"] == "loopx bounded-command"


def test_quiet_monitor_keeps_user_todo_non_blocking() -> None:
    recommendation = _recommend(
        lane="continuous_monitor",
        must_attempt_work=False,
        user_open=1,
    )

    assert (
        recommendation["recommended_mode"]
        == "monitor_quiet_until_material_transition"
    )
    assert recommendation["notify"] == "DONT_NOTIFY"
    assert "open user todo" in recommendation["spend_policy"]


def test_true_monitor_only_lane_keeps_monitor_only_reason() -> None:
    recommendation = _recommend(
        lane="continuous_monitor",
        must_attempt_work=False,
        agent_open=1,
    )

    assert "all visible open agent todos are monitor-class" in recommendation["reason"]


def test_due_monitor_lane_preempts_first_read_only_map() -> None:
    recommendation = _recommend(
        {
            "status": "connected_without_run",
            "adapter_kind": "docs_read_only_map_v0",
        },
        lane="continuous_monitor",
        must_attempt_work=True,
    )

    assert recommendation["recommended_mode"] == "follow_work_lane_contract"
    assert "machine contract" in recommendation["reason"]


def test_first_read_only_map_preempts_mapped_noop() -> None:
    recommendation = _recommend(
        {
            "status": "connected_without_run",
            "adapter_kind": "docs_read_only_map_v0",
            "lifecycle_flags": ["mapped"],
        }
    )

    assert recommendation["recommended_mode"] == "run_first_read_only_map"
    assert recommendation["command"] == f"loopx read-only-map --goal-id {GOAL_ID}"


def test_post_handoff_primary_outcome_preserves_observation_contract() -> None:
    recommendation = _recommend(
        {
            "status": "post_handoff_run_seen",
            "adapter_kind": "harness_self_improvement",
            "control_plane": {"self_repair": {"enabled": True}},
            "handoff_readiness": {
                "post_handoff_run_seen": True,
                "handoff_status": "post_handoff_run_seen",
                "post_handoff_latest_run": {
                    "classification": "implementation_merged",
                    "delivery_outcome": DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value,
                },
            },
        }
    )

    assert recommendation["recommended_mode"] == "post_handoff_observe_if_unchanged"
    assert recommendation["stop_if_unchanged"] is True
    assert recommendation["latest_run"]["progress_scope"] == "primary_goal"


def test_default_mode_keeps_compatibility_without_an_operation_limit() -> None:
    recommendation = _recommend(
        {"status": "active-read-only"},
        agent_open=1,
    )

    assert recommendation["recommended_mode"] == "steering_audit_then_one_step"
    assert "scope-bounded work" in recommendation["spend_policy"]
    assert "not an operation limit" in recommendation["spend_policy"]
