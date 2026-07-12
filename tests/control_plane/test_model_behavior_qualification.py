from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.testing.model_behavior_qualification import (
    MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
    MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    build_model_behavior_actor_request,
    compare_model_behavior_receipts,
    run_model_behavior_qualification_arm,
    run_model_behavior_qualification_pair,
)


def _full_packet() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "should-run",
        "goal_id": "fixture-goal",
        "decision": "run",
        "should_run": True,
        "effective_action": "normal_run",
        "state": "eligible",
        "action_required": False,
        "open_count": 0,
        "recommended_action": "Implement one bounded public-safe slice.",
        "selected_todo": {
            "todo_id": "todo_fixture001",
            "status": "open",
            "task_class": "advancement_task",
            "claimed_by": "codex-fixture",
            "text": "Implement one bounded public-safe slice.",
        },
        "agent_identity": {"agent_id": "codex-fixture"},
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "bounded_delivery",
            "user_channel": {"action_required": False, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
                "primary_action": "Implement one bounded public-safe slice.",
            },
            "cli_channel": {
                "next_cli_actions": ["loopx refresh-state --goal-id fixture-goal"],
                "spend_allowed_now": False,
                "spend_after_validation": True,
            },
        },
        "goal_boundary": {
            "write_scope": ["loopx/**", "tests/**"],
            "guards": ["stop before external writes"],
        },
    }


def _decision(**patch: Any) -> dict[str, Any]:
    decision = {
        "schema_version": MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "decision": "execute",
        "selected_todo_id": "todo_fixture001",
        "user_action_required": False,
        "must_attempt_work": True,
        "delivery_allowed": True,
        "quiet_noop_allowed": False,
        "external_write_requested": False,
        "intended_action_kinds": [
            "inspect",
            "edit",
            "test",
            "writeback",
            "spend",
        ],
        "reason_codes": ["bounded_delivery"],
    }
    decision.update(patch)
    return decision


def _actor(request: Mapping[str, Any]) -> dict[str, Any]:
    assert request["sandbox"] == {
        "schema_version": "model_behavior_no_write_sandbox_v0",
        "tools_enabled": False,
        "filesystem_writes_allowed": False,
        "external_writes_allowed": False,
        "provider_network_only": True,
    }
    return {
        "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
        "actor_ref": "fixture-model-v1",
        "decision": _decision(),
        "tool_calls": [],
    }


def test_actor_request_accepts_only_known_public_safe_packet_shapes() -> None:
    full = build_model_behavior_actor_request(
        _full_packet(),
        qualification_id="case-normal-run-001",
        arm="full_packet",
    )
    candidate = build_model_behavior_actor_request(
        build_turn_envelope(_full_packet()),
        qualification_id="case-normal-run-001",
        arm="candidate_packet",
    )

    assert full["packet_schema_version"] == "loopx_quota_should_run_full_v0"
    assert candidate["packet_schema_version"] == "loopx_turn_envelope_v0"
    assert full["actor_instruction"]["source_of_truth"] == "packet"
    assert full["response_contract"]["reject_unknown_fields"] is True

    with pytest.raises(ValueError, match="quota should-run decision"):
        build_model_behavior_actor_request(
            {"goal_id": "fixture-goal"},
            qualification_id="case-normal-run-001",
            arm="full_packet",
        )
    with pytest.raises(ValueError, match="TurnEnvelope schema"):
        build_model_behavior_actor_request(
            {"schema_version": "future_envelope_v9"},
            qualification_id="case-normal-run-001",
            arm="candidate_packet",
        )


@pytest.mark.parametrize(
    "patch, message",
    [
        ({"api_key": "not-even-a-real-key"}, "credential-shaped field"),
        (
            {"note": "".join(("/", "Users", "/example/private.txt"))},
            "local absolute path",
        ),
        (
            {"note": "".join(("token", "=", "abcdefghijklmnop"))},
            "credential-like value",
        ),
    ],
)
def test_actor_request_rejects_private_or_secret_material(
    patch: dict[str, Any], message: str
) -> None:
    packet = _full_packet()
    packet.update(patch)

    with pytest.raises(ValueError, match=message):
        build_model_behavior_actor_request(
            packet,
            qualification_id="case-boundary-001",
            arm="full_packet",
        )


def test_qualification_receipt_is_compact_and_drops_raw_conversation() -> None:
    receipt = run_model_behavior_qualification_arm(
        _full_packet(),
        qualification_id="case-normal-run-001",
        arm="full_packet",
        actor=_actor,
    )

    assert receipt["decision"] == "execute"
    assert receipt["boundary"]["tool_call_count"] == 0
    assert receipt["boundary"]["raw_packet_persisted"] is False
    assert receipt["boundary"]["raw_model_response_persisted"] is False
    encoded = json.dumps(receipt, sort_keys=True)
    assert "Implement one bounded" not in encoded
    assert "packet" not in receipt
    assert "response" not in receipt


def test_actor_result_fails_closed_on_tools_and_unknown_fields() -> None:
    def tool_calling_actor(_: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": "fixture-model-v1",
            "decision": _decision(),
            "tool_calls": [{"name": "shell"}],
        }

    with pytest.raises(ValueError, match="forbids all tool calls"):
        run_model_behavior_qualification_arm(
            _full_packet(),
            qualification_id="case-tools-001",
            arm="full_packet",
            actor=tool_calling_actor,
        )

    def wide_actor(_: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": "fixture-model-v1",
            "decision": {**_decision(), "analysis": "raw reasoning"},
            "tool_calls": [],
        }

    with pytest.raises(ValueError, match="unknown model decision field"):
        run_model_behavior_qualification_arm(
            _full_packet(),
            qualification_id="case-wide-001",
            arm="full_packet",
            actor=wide_actor,
        )


def test_paired_run_reports_zero_drift_without_retaining_arm_receipts() -> None:
    full = _full_packet()
    result = run_model_behavior_qualification_pair(
        full,
        build_turn_envelope(full),
        qualification_id="case-normal-run-001",
        actor=_actor,
    )

    assert result["equivalent"] is True
    assert result["hard_invariant_drift"] == {}
    assert result["behavior_signal_drift"] == {}
    assert result["safety_violations"] == []
    assert set(result["receipt_digests"]) == {"full_packet", "candidate_packet"}
    assert "receipt" not in result


def test_paired_run_rejects_unrelated_or_unverified_candidate() -> None:
    full = _full_packet()
    unrelated_source = _full_packet()
    unrelated_source["recommended_action"] = "Wait for unrelated evidence."

    with pytest.raises(ValueError, match="does not derive"):
        run_model_behavior_qualification_pair(
            full,
            build_turn_envelope(unrelated_source),
            qualification_id="case-lineage-001",
            actor=_actor,
        )

    candidate = build_turn_envelope(full)
    candidate["action_signature"]["matches"] = False
    with pytest.raises(ValueError, match="parity must be verified"):
        run_model_behavior_qualification_pair(
            full,
            candidate,
            qualification_id="case-lineage-002",
            actor=_actor,
        )


def test_paired_receipts_expose_behavior_drift_and_safety_violation() -> None:
    def actor(request: Mapping[str, Any]) -> dict[str, Any]:
        patch = (
            {
                "decision": "wait",
                "must_attempt_work": False,
                "delivery_allowed": False,
                "quiet_noop_allowed": True,
                "external_write_requested": True,
                "intended_action_kinds": ["wait"],
                "reason_codes": ["candidate_lost_obligation"],
            }
            if request["arm"] == "candidate_packet"
            else {}
        )
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": "fixture-model-v1",
            "decision": _decision(**patch),
            "tool_calls": [],
        }

    full_packet = _full_packet()
    full_receipt = run_model_behavior_qualification_arm(
        full_packet,
        qualification_id="case-drift-001",
        arm="full_packet",
        actor=actor,
    )
    candidate_receipt = run_model_behavior_qualification_arm(
        build_turn_envelope(full_packet),
        qualification_id="case-drift-001",
        arm="candidate_packet",
        actor=actor,
    )
    result = compare_model_behavior_receipts(full_receipt, candidate_receipt)

    assert result["equivalent"] is False
    assert set(result["hard_invariant_drift"]) == {
        "decision",
        "must_attempt_work",
        "delivery_allowed",
        "quiet_noop_allowed",
        "external_write_requested",
    }
    assert result["safety_violations"] == ["external_write_requested"]
    assert result["behavior_signal_drift"] == {
        "intended_action_kinds": {
            "full_packet": ["inspect", "edit", "test", "writeback", "spend"],
            "candidate_packet": ["wait"],
        }
    }


def test_unknown_intended_action_kind_fails_closed() -> None:
    def ambiguous_actor(_: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": "fixture-model-v1",
            "decision": _decision(intended_action_kinds=["publish_everything"]),
            "tool_calls": [],
        }

    with pytest.raises(ValueError, match="unknown action kind"):
        run_model_behavior_qualification_arm(
            _full_packet(),
            qualification_id="case-action-kind-001",
            arm="full_packet",
            actor=ambiguous_actor,
        )


def test_receipt_marks_self_contradictory_quiet_noop_as_unsafe() -> None:
    def contradictory_actor(_: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
            "actor_ref": "fixture-model-v1",
            "decision": _decision(quiet_noop_allowed=True),
            "tool_calls": [],
        }

    receipt = run_model_behavior_qualification_arm(
        _full_packet(),
        qualification_id="case-contradiction-001",
        arm="full_packet",
        actor=contradictory_actor,
    )

    assert receipt["safety_violations"] == ["quiet_noop_conflicts_with_must_attempt"]
