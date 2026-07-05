#!/usr/bin/env python3
"""Canary the interaction/protocol state machine across major quota modes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.agents.agent_scope import AgentScopeFrontierAction  # noqa: E402
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint  # noqa: E402
from loopx.control_plane.work_items.execution_obligation import (  # noqa: E402
    build_execution_obligation,
)
from loopx.control_plane.work_items.interaction_contract import (  # noqa: E402
    build_interaction_contract,
    build_protocol_action_packet,
    user_channel_action_required,
)
from loopx.control_plane.work_items.work_lane import build_work_lane_contract  # noqa: E402


GOAL_ID = "interaction-state-machine-goal"
AGENT_ID = "codex-product-capability"


def advancement_item(todo_id: str = "todo_active") -> dict[str, Any]:
    return {
        "todo_id": todo_id,
        "status": "open",
        "task_class": "advancement_task",
        "text": "[P1] Advance the canary-controlled interaction contract.",
        "claimed_by": AGENT_ID,
    }


def monitor_item(todo_id: str = "todo_monitor") -> dict[str, Any]:
    return {
        "todo_id": todo_id,
        "status": "open",
        "task_class": "continuous_monitor",
        "text": "[P1-monitor] Monitor the state-machine canary transition.",
        "claimed_by": AGENT_ID,
    }


def due_monitor_item(todo_id: str = "todo_due_monitor") -> dict[str, Any]:
    return {
        **monitor_item(todo_id),
        "priority": "P0",
        "cadence": "15m",
        "next_due_at": "2026-07-05T15:00:00Z",
    }


def advancement_lane() -> dict[str, Any]:
    item = advancement_item()
    return build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 1, "monitor": 0},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=item,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=3,
    )


def due_monitor_lane() -> dict[str, Any]:
    monitor = due_monitor_item()
    item = advancement_item("todo_active_after_due_monitor")
    return build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 2, "advancement": 1, "monitor": 1},
        monitor_due_count=1,
        due_monitor_items=[monitor],
        first_advancement=item,
        due_monitor_preempts_advancement=True,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=3,
    )


def monitor_schedule_gap_lane() -> dict[str, Any]:
    monitor = monitor_item("todo_monitor_gap")
    return build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 0, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=None,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=3,
        monitor_schedule_gap_count=1,
        monitor_schedule_gap_items=[monitor],
    )


def monitor_quiet_lane() -> dict[str, Any]:
    return build_work_lane_contract(
        progress_scope="agent_lane",
        external_poll_signal=False,
        todo_counts={"open": 1, "advancement": 0, "monitor": 1},
        monitor_due_count=0,
        due_monitor_items=[],
        first_advancement=None,
        due_monitor_preempts_advancement=False,
        outcome_followthrough=None,
        next_action_requires_advancement=False,
        monitor_due_item_limit=3,
    )


def base_payload(
    *,
    should_run: bool,
    effective_action: str,
    work_lane: dict[str, Any] | None,
    heartbeat_mode: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "goal_id": GOAL_ID,
        "should_run": should_run,
        "decision": "run" if should_run else "skip",
        "state": "eligible",
        "effective_action": effective_action,
        "normal_delivery_allowed": should_run and effective_action == "normal_run",
        "recovery_delivery_allowed": False,
        "self_repair_allowed": False,
        "requires_user_action": False,
        "agent_identity": {"agent_id": AGENT_ID},
        "heartbeat_recommendation": {
            "recommended_mode": heartbeat_mode,
            "notify": "DONT_NOTIFY",
            "spend_policy": "spend once after validated writeback",
        },
        "agent_lane_next_action": {
            "todo_id": "todo_active",
            "text": "[P1] Advance the canary-controlled interaction contract.",
        },
        "agent_todo_summary": {
            "first_executable_items": [advancement_item()] if should_run else [],
            "first_open_items": [advancement_item()] if should_run else [],
        },
        "automation_liveness": {
            "automation_action": "execute_bounded_work" if should_run else "keep_active_quiet",
            "pause_allowed": False,
        },
    }
    if work_lane:
        payload["work_lane_contract"] = work_lane
    payload["execution_obligation"] = build_execution_obligation(
        should_run=should_run,
        effective_action=effective_action,
        heartbeat_recommendation=payload["heartbeat_recommendation"],
        work_lane_contract=work_lane,
    )
    return payload


def finalize(payload: dict[str, Any]) -> dict[str, Any]:
    payload["interaction_contract"] = build_interaction_contract(payload)
    payload["scheduler_hint"] = build_scheduler_hint(
        payload,
        user_action_required=user_channel_action_required(payload),
        agent_scope_frontier_actions=[action.value for action in AgentScopeFrontierAction],
    )
    payload["protocol_action_packet"] = build_protocol_action_packet(payload)
    return payload


def _successor_replan_payload() -> dict[str, Any]:
    payload = base_payload(
        should_run=True,
        effective_action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
        work_lane=None,
        heartbeat_mode=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
    )
    payload["normal_delivery_allowed"] = False
    payload["agent_scope_frontier"] = {
        "deferred_resume_candidates": [{"todo_id": "todo_deferred_successor"}],
    }
    payload["execution_obligation"] = build_execution_obligation(
        should_run=True,
        effective_action=payload["effective_action"],
        heartbeat_recommendation=payload["heartbeat_recommendation"],
        work_lane_contract=None,
    )
    return finalize(payload)


def _due_monitor_payload() -> dict[str, Any]:
    lane = due_monitor_lane()
    payload = base_payload(
        should_run=True,
        effective_action="normal_run",
        work_lane=lane,
        heartbeat_mode="steering_audit_then_one_step",
    )
    payload.pop("agent_lane_next_action", None)
    payload["agent_todo_summary"] = {
        "first_executable_items": [advancement_item("todo_active_after_due_monitor")],
        "current_agent_claimed_monitor_items": lane["monitor_due_items"],
        "monitor_due_items": lane["monitor_due_items"],
    }
    payload["execution_obligation"] = build_execution_obligation(
        should_run=True,
        effective_action=payload["effective_action"],
        heartbeat_recommendation=payload["heartbeat_recommendation"],
        work_lane_contract=lane,
    )
    return finalize(payload)


def _monitor_schedule_gap_payload() -> dict[str, Any]:
    lane = monitor_schedule_gap_lane()
    payload = base_payload(
        should_run=True,
        effective_action="normal_run",
        work_lane=lane,
        heartbeat_mode="steering_audit_then_one_step",
    )
    payload.pop("agent_lane_next_action", None)
    payload["agent_todo_summary"] = {
        "current_agent_claimed_monitor_items": lane["monitor_schedule_gap_items"],
        "monitor_schedule_gap_items": lane["monitor_schedule_gap_items"],
    }
    payload["execution_obligation"] = build_execution_obligation(
        should_run=True,
        effective_action=payload["effective_action"],
        heartbeat_recommendation=payload["heartbeat_recommendation"],
        work_lane_contract=lane,
    )
    return finalize(payload)


def _assert_cross_layer_case(
    name: str,
    payload: dict[str, Any],
    *,
    lane: str = "none",
    obligation: str | None = None,
    interaction: str,
    scheduler: str = "run_now",
    interval: int = 3,
    must_attempt: bool = True,
    quiet: bool = False,
    spend: bool = True,
    summary_fragments: tuple[str, ...] = (),
    cli_fragments: tuple[str, ...] = (),
) -> None:
    contract = payload["interaction_contract"]
    scheduler_hint = payload["scheduler_hint"]
    work_lane = payload.get("work_lane_contract")
    actual_lane = work_lane.get("lane") if isinstance(work_lane, dict) else "none"
    actual_obligation = (
        work_lane.get("obligation") if isinstance(work_lane, dict) else None
    )
    assert actual_lane == lane, (name, payload)
    assert actual_obligation == obligation, (name, payload)
    assert contract["mode"] == interaction, (name, contract)
    assert contract["agent_channel"]["must_attempt"] is must_attempt, (name, contract)
    assert contract["agent_channel"]["quiet_noop_allowed"] is quiet, (name, contract)
    assert contract["cli_channel"]["spend_after_validation"] is spend, (name, contract)
    assert scheduler_hint["action"] == scheduler, (name, scheduler_hint)
    assert scheduler_hint["codex_app"]["recommended_interval_minutes"] == interval, (
        name,
        scheduler_hint,
    )
    summary = payload["protocol_action_packet"]["summary"]
    for fragment in summary_fragments:
        assert fragment in summary, (name, summary)
    cli_actions = " ".join(contract["cli_channel"]["next_cli_actions"])
    for fragment in cli_fragments:
        assert fragment in cli_actions, (name, cli_actions)


def assert_cross_layer_state_machine_matrix() -> None:
    _assert_cross_layer_case(
        "advancement",
        finalize(
            base_payload(
                should_run=True,
                effective_action="normal_run",
                work_lane=advancement_lane(),
                heartbeat_mode="steering_audit_then_one_step",
            )
        ),
        lane="advancement_task",
        obligation="advance_one_bounded_segment",
        interaction="bounded_delivery",
        summary_fragments=("lane=advancement_task", "scheduler=run_now"),
    )
    _assert_cross_layer_case(
        "due monitor preemption",
        _due_monitor_payload(),
        lane="continuous_monitor",
        obligation="attempt_due_monitor",
        interaction="bounded_delivery",
        summary_fragments=("lane=continuous_monitor", "todo_due_monitor"),
    )
    _assert_cross_layer_case(
        "monitor schedule gap repair",
        _monitor_schedule_gap_payload(),
        lane="advancement_task",
        obligation="repair_monitor_schedule_metadata",
        interaction="bounded_delivery",
        summary_fragments=(
            "lane=advancement_task",
            "repair the selected continuous_monitor todo",
        ),
    )
    _assert_cross_layer_case(
        "monitor quiet wait",
        finalize(
            base_payload(
                should_run=False,
                effective_action="monitor_quiet_skip",
                work_lane=monitor_quiet_lane(),
                heartbeat_mode="monitor_quiet_until_material_transition",
            )
        ),
        lane="continuous_monitor",
        obligation="quiet_until_material_monitor_transition",
        interaction="monitor_quiet_skip",
        scheduler="backoff_until_material_transition",
        interval=15,
        must_attempt=False,
        quiet=True,
        spend=False,
        summary_fragments=(
            "lane=continuous_monitor",
            "scheduler=backoff_until_material_transition",
        ),
    )
    _assert_cross_layer_case(
        "agent scope wait",
        finalize(
            base_payload(
                should_run=False,
                effective_action=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
                work_lane=None,
                heartbeat_mode=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            )
        ),
        interaction=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
        scheduler="backoff_until_reassigned",
        interval=10,
        must_attempt=False,
        quiet=True,
        spend=False,
        summary_fragments=("scheduler=backoff_until_reassigned",),
    )
    _assert_cross_layer_case(
        "successor replan",
        _successor_replan_payload(),
        interaction=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
        summary_fragments=("scheduler=run_now",),
        cli_fragments=("todo_deferred_successor",),
    )


def assert_bounded_delivery_bundle() -> None:
    payload = finalize(
        base_payload(
            should_run=True,
            effective_action="normal_run",
            work_lane=advancement_lane(),
            heartbeat_mode="steering_audit_then_one_step",
        )
    )
    contract = payload["interaction_contract"]
    assert contract["mode"] == "bounded_delivery", payload
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is False, contract
    assert contract["cli_channel"]["spend_after_validation"] is True, contract
    assert payload["scheduler_hint"]["action"] == "run_now", payload
    summary = payload["protocol_action_packet"]["summary"]
    assert "actor=agent" in summary, summary
    assert "lane=advancement_task" in summary, summary
    assert "scheduler=run_now" in summary, summary


def assert_user_notice_can_coexist_with_bounded_delivery() -> None:
    payload = base_payload(
        should_run=True,
        effective_action="normal_run",
        work_lane=advancement_lane(),
        heartbeat_mode="steering_audit_then_one_step",
    )
    payload["requires_user_action"] = True
    payload["user_todo_summary"] = {
        "first_open_items": [
            {
                "todo_id": "todo_user_gate",
                "status": "open",
                "task_class": "user_gate",
                "text": "[P0-user] Decide whether the canary may publish.",
            }
        ]
    }
    payload = finalize(payload)
    contract = payload["interaction_contract"]
    assert contract["mode"] == "bounded_delivery_with_user_notice", payload
    assert contract["user_channel"]["action_required"] is True, contract
    assert contract["user_channel"]["notify"] == "NOTIFY", contract
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["delivery_allowed"] is True, contract


def assert_monitor_quiet_skip_is_no_spend() -> None:
    payload = finalize(
        base_payload(
            should_run=False,
            effective_action="monitor_quiet_skip",
            work_lane=monitor_quiet_lane(),
            heartbeat_mode="monitor_quiet_until_material_transition",
        )
    )
    contract = payload["interaction_contract"]
    assert contract["mode"] == "monitor_quiet_skip", payload
    assert contract["agent_channel"]["must_attempt"] is False, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is True, contract
    assert contract["cli_channel"]["spend_after_validation"] is False, contract
    assert contract["cli_channel"]["spend_policy"] == "no spend for unchanged monitor poll", contract
    assert "monitor-poll" in contract["cli_channel"]["next_cli_actions"][0], contract


def assert_autonomous_replan_preempts_monitor_quiet() -> None:
    payload = finalize(
        base_payload(
            should_run=True,
            effective_action="autonomous_replan_required",
            work_lane=monitor_quiet_lane(),
            heartbeat_mode="autonomous_replan_required",
        )
    )
    contract = payload["interaction_contract"]
    assert contract["mode"] == "autonomous_replan", payload
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["cli_channel"]["spend_after_validation"] is True, contract
    assert payload["scheduler_hint"]["action"] == "run_now", payload


def assert_agent_scope_wait_is_quiet_noop() -> None:
    payload = finalize(
        base_payload(
            should_run=False,
            effective_action=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            work_lane=None,
            heartbeat_mode=AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
        )
    )
    contract = payload["interaction_contract"]
    assert contract["mode"] == AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value, payload
    assert contract["agent_channel"]["quiet_noop_allowed"] is True, contract
    assert contract["cli_channel"]["spend_after_validation"] is False, contract
    assert "no quota spend" in contract["cli_channel"]["next_cli_actions"][0], contract


def assert_successor_replan_is_validated_spend_path() -> None:
    payload = _successor_replan_payload()
    contract = payload["interaction_contract"]
    assert contract["mode"] == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value, payload
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["cli_channel"]["spend_after_validation"] is True, contract
    assert contract["cli_channel"]["spend_policy"].startswith("spend once"), contract
    actions = contract["cli_channel"]["next_cli_actions"]
    assert any("todo_deferred_successor" in action for action in actions), actions
    assert any("spend-slot" in action for action in actions), actions


def main() -> int:
    assert_cross_layer_state_machine_matrix()
    assert_bounded_delivery_bundle()
    assert_user_notice_can_coexist_with_bounded_delivery()
    assert_monitor_quiet_skip_is_no_spend()
    assert_autonomous_replan_preempts_monitor_quiet()
    assert_agent_scope_wait_is_quiet_noop()
    assert_successor_replan_is_validated_spend_path()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
