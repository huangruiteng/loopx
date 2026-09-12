from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..scheduler.execution_context import SchedulerExecutionContextResolution
from ..work_items.interaction_contract import (
    build_interaction_contract,
    build_protocol_action_packet,
)
from .heartbeat_receipt import (
    heartbeat_receipt_settlement_replan_obligation_id,
    heartbeat_receipt_settlement_todo_id,
    prior_closeout_required_heartbeat_receipts,
)
from .settlement import read_heartbeat_settlement

UNSETTLED_HOST_TURN_RECOVERY_SCHEMA_VERSION = "unsettled_host_turn_recovery_v0"


def _todo_item_by_id(
    payload: Mapping[str, Any], todo_id: str
) -> Mapping[str, Any] | None:
    summary = payload.get("agent_todo_summary")
    if not isinstance(summary, Mapping):
        return None
    for value in summary.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, Mapping) and item.get("todo_id") == todo_id:
                return item
    return None


def _typed_lifecycle_closeout(
    payload: Mapping[str, Any],
    *,
    todo_id: str | None,
) -> str | None:
    if not todo_id:
        return None
    item = _todo_item_by_id(payload, todo_id)
    if item is None:
        return None
    status = str(item.get("status") or "")
    if (
        status == "open"
        and item.get("resume_when")
        and isinstance(item.get("successor_todo_ids"), list)
        and bool(item.get("successor_todo_ids"))
    ):
        return "typed_external_wait"
    if status in {"done", "blocked", "deferred"}:
        return f"todo_{status}"
    return None


def _unsettled_host_turn_recovery(
    payload: Mapping[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
    agent_id: str | None,
    current_turn_instance_id: str | None,
) -> dict[str, Any] | None:
    if not agent_id or not current_turn_instance_id:
        return None
    for receipt in prior_closeout_required_heartbeat_receipts(
        runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        exclude_turn_instance_id=current_turn_instance_id,
    ):
        todo_id = heartbeat_receipt_settlement_todo_id(receipt)
        replan_obligation_id = heartbeat_receipt_settlement_replan_obligation_id(
            receipt
        )
        prior_turn_id = str(receipt.get("run_id") or "").strip()
        if not prior_turn_id or not (todo_id or replan_obligation_id):
            continue
        readback = read_heartbeat_settlement(
            runtime_root,
            goal_id=goal_id,
            agent_id=agent_id,
            todo_id=todo_id,
            turn_instance_id=prior_turn_id,
            replan_obligation_id=replan_obligation_id,
        )
        if readback is not None and readback.settlement.failure is None:
            return None
        lifecycle_closeout = _typed_lifecycle_closeout(payload, todo_id=todo_id)
        if lifecycle_closeout is not None:
            return None
        details_value = receipt.get("details")
        details = details_value if isinstance(details_value, Mapping) else {}
        effect_id = str(details.get("settlement_effect_id") or "").strip()
        missing_receipts: list[str] = []
        if readback is None or readback.writeback.failure is not None:
            missing_receipts.append("durable_writeback_receipt")
        if readback is None or readback.spend.failure is not None:
            missing_receipts.append("quota_spend_receipt")
        binding_kind = "todo" if todo_id else "autonomous_replan"
        binding_id = todo_id or replan_obligation_id
        return {
            "schema_version": UNSETTLED_HOST_TURN_RECOVERY_SCHEMA_VERSION,
            "state": "recovery_required",
            "reason_code": "required_closeout_receipt_missing",
            "prior_turn_instance_id": prior_turn_id,
            "prior_event_id": receipt.get("event_id"),
            "binding_kind": binding_kind,
            "binding_id": binding_id,
            "settlement_effect_id": effect_id,
            "missing_receipts": missing_receipts,
            "accepted_closeouts": [
                "validated_writeback_and_quota_spend",
                "typed_external_wait_with_runnable_successor",
                "typed_blocker_or_lifecycle_transition",
            ],
            "external_state_policy": "typed_host_observation_only",
            "quota_policy": "no_spend_for_recovery_transition",
        }
    return None


def apply_unsettled_host_turn_recovery_if_required(
    payload: dict[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
    agent_id: str | None,
    current_turn_instance_id: str | None,
    available_capabilities: list[str] | None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ),
) -> bool:
    """Preempt ordinary selection when the preceding host Turn lacks closeout."""

    recovery = _unsettled_host_turn_recovery(
        payload,
        runtime_root=runtime_root,
        goal_id=goal_id,
        agent_id=agent_id,
        current_turn_instance_id=current_turn_instance_id,
    )
    if recovery is None:
        return False
    binding_id = str(recovery.get("binding_id") or "prior binding")
    payload.pop("selected_todo", None)
    payload.pop("todo_id", None)
    payload.pop("action_portfolio", None)
    payload.update(
        {
            "decision": "unsettled_host_turn_recovery",
            "should_run": True,
            "state": "eligible",
            "effective_action": "unsettled_host_turn_recovery",
            "actionable_by_codex": True,
            "normal_delivery_allowed": False,
            "recovery_delivery_allowed": False,
            "self_repair_allowed": False,
            "reason": "a prior must-attempt heartbeat has no legal closeout receipt",
            "recommended_action": (
                f"Recover prior unsettled host Turn for {binding_id}; use a typed "
                "lifecycle observation, then rerun quota and continue independent work"
            ),
            "unsettled_host_turn_recovery": recovery,
            "heartbeat_recommendation": {
                "source": "unsettled_host_turn_recovery",
                "recommended_mode": "unsettled_host_turn_recovery",
                "notify": "DONT_NOTIFY",
                "spend_policy": "no spend for the recovery transition",
                "reason": "prior must-attempt host Turn is missing a legal closeout",
                "agent_must_attempt": True,
            },
            "execution_obligation": {
                "must_attempt_work": True,
                "kind": "unsettled_host_turn_recovery",
                "contract": "repair_prior_turn_closeout",
                "contract_obligation": "author_typed_closeout_then_continue_successor",
                "delivery_allowed": False,
                "notify_is_execution_gate": False,
                "reason": "prior must-attempt host Turn is missing a legal closeout",
            },
            "work_lane_contract": {
                "schema_version": "work_lane_contract_v1",
                "lane": "control_plane_recovery",
                "next_lane": "advancement_task",
                "obligation": "author_typed_closeout_then_continue_successor",
                "must_attempt_work": True,
                "reason_codes": ["unsettled_host_turn"],
                "monitor_policy": "typed_observation_only",
                "action": "repair the prior Turn closeout without spending quota",
            },
            "automation_liveness": {
                "schema_version": "automation_liveness_v0",
                "keep_active": True,
                "pause_allowed": False,
                "automation_action": "execute_bounded_recovery",
                "reason": "prior must-attempt host Turn remains unsettled",
                "spend_policy": "no spend for the recovery transition",
            },
        }
    )
    interaction_contract = build_interaction_contract(
        payload,
        available_capabilities=available_capabilities,
        scheduler_execution_context=scheduler_execution_context,
        turn_instance_id=current_turn_instance_id,
        runtime_root=str(runtime_root),
    )
    agent_channel = interaction_contract.get("agent_channel")
    if isinstance(agent_channel, dict):
        agent_channel["primary_action"] = payload["recommended_action"]
        agent_channel.pop("next_task_action", None)
        agent_channel["recovery_ref"] = "$.unsettled_host_turn_recovery"
    cli_channel = interaction_contract.get("cli_channel")
    if isinstance(cli_channel, dict):
        cli_channel["recovery_ref"] = "$.unsettled_host_turn_recovery"
    payload["interaction_contract"] = interaction_contract
    payload["protocol_action_packet"] = build_protocol_action_packet(payload)
    return True
