from __future__ import annotations

from typing import Any, TypedDict, get_type_hints

from loopx.control_plane.quota.decision_summary import (
    QuotaDecisionPacket,
    compact_quota_decision,
)
from loopx.control_plane.todos.summary_item import (
    TodoSummaryItemDict,
    compact_todo_summary_item,
)
from loopx.control_plane.work_items.interaction_contract import (
    InteractionContractPacket,
    build_interaction_contract,
)


def _shape_ok(packet: dict[str, Any], contract: type[TypedDict]) -> bool:
    annotations = set(get_type_hints(contract))
    required = set(getattr(contract, "__required_keys__", frozenset()))
    return required <= set(packet) and set(packet) <= annotations


def test_todo_summary_item_contract_accepts_representative_packet() -> None:
    packet = compact_todo_summary_item(
        {
            "todo_id": "todo_abc",
            "text": "Review PR #1",
            "status": "open",
            "priority": "P1",
            "task_class": "advancement_task",
            "action_kind": "review_pull_request_exact_head",
            "claimed_by": "codex-side-bypass",
            "required_capabilities": ["network"],
            "target_key": "github-pr-review:owner/repo#1@abc",
        }
    )

    assert _shape_ok(packet, TodoSummaryItemDict)


def test_quota_decision_packet_accepts_representative_packet() -> None:
    packet = compact_quota_decision(
        {
            "goal_id": "loopx-meta",
            "decision": "run",
            "should_run": True,
            "effective_action": "normal_run",
            "normal_delivery_allowed": True,
            "recovery_delivery_allowed": False,
            "self_repair_allowed": False,
            "capability_repair_allowed": False,
            "workspace_repair_allowed": False,
            "state": "normal",
            "safe_bypass_allowed": False,
            "safe_bypass_kind": None,
            "blocked_action_scope": None,
            "quota": {
                "compute": 1.0,
                "window_hours": 24,
                "slot_minutes": 1,
                "spent_slots": 3,
                "allowed_slots": 10,
            },
            "reason": "runnable work",
        }
    )

    assert _shape_ok(packet, QuotaDecisionPacket)


def test_interaction_contract_packet_accepts_representative_packet() -> None:
    packet = build_interaction_contract(
        {
            "goal_id": "loopx-meta",
            "effective_action": "normal_run",
            "agent_identity": {"agent_id": "codex-quality-qualification"},
            "heartbeat_recommendation": {"recommended_mode": "bounded_delivery"},
        }
    )

    assert _shape_ok(packet, InteractionContractPacket)


def test_packet_contracts_reject_unknown_keys() -> None:
    assert not _shape_ok({"unknown": True}, TodoSummaryItemDict)
    assert not _shape_ok({"unknown": True}, QuotaDecisionPacket)
    assert not _shape_ok({"unknown": True}, InteractionContractPacket)
