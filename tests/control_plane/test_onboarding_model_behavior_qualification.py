from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from loopx.control_plane.testing.onboarding_model_behavior_qualification import (
    ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_PAIR_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
    OnboardingModelBehaviorPairValidationError,
    build_onboarding_model_behavior_actor_request,
    build_onboarding_postcondition_observation,
    onboarding_entry_semantic_contract,
    onboarding_postcondition_semantic_contract,
    run_onboarding_closed_loop_pair,
)


COMMANDS = {
    "goal_start_connect_if_needed": "cd $PROJECT && loopx bootstrap --project .",
    "goal_start_refresh_state": "loopx refresh-state --goal-id fixture-goal",
    "goal_start_host_loop_activation": (
        "loopx heartbeat-prompt --thin --goal-id fixture-goal"
    ),
    "goal_start_quota_should_run": (
        "loopx quota should-run --goal-id fixture-goal"
    ),
}
ACTIVATION = {
    "schema_version": "loopx_host_loop_activation_v1",
    "agent_id": "codex-fixture",
    "activation_required_after_todo_write": True,
}
TRANSACTION = {
    "schema_version": "loopx_goal_start_transaction_v0",
    "writes_now": False,
    "spends_quota_now": False,
    "ordered_steps": [
        {"id": "inspect_connection", "kind": "read_only"},
        {"id": "connect_if_needed", "kind": "conditional_mutation"},
        {"id": "write_ordered_todos", "kind": "operator_or_agent_actions"},
        {"id": "activate_host_loop", "kind": "host_loop"},
        {"id": "quota_guard", "kind": "guard"},
    ],
}


def _entry_packet(*, compact: bool) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_version": "loopx_start_goal_guided_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "guided_transaction": TRANSACTION,
        "safety_contract": {
            "writes_registry": False,
            "writes_state_file": False,
            "spends_quota": False,
        },
    }
    if compact:
        packet.update(
            commands=dict(COMMANDS),
            host_loop_activation=dict(ACTIVATION),
        )
    else:
        packet["command_pack"] = {
            "commands": dict(COMMANDS),
            "host_loop_activation": dict(ACTIVATION),
            "message": "Detailed diagnostic material stays in the cold path.",
        }
    return packet


def _decision_for_request(request: Mapping[str, Any]) -> dict[str, Any]:
    phase = str(request["phase"])
    if phase == "entry":
        contract = onboarding_entry_semantic_contract(request["packet"])
    else:
        contract = onboarding_postcondition_semantic_contract(request["packet"])
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "phase": phase,
        "next_action": contract["route"],
        "semantic_contract": contract,
        "reason_codes": ["source_aligned"],
    }


def _actor(request: Mapping[str, Any]) -> dict[str, Any]:
    assert request["sandbox"]["tools_enabled"] is False
    assert request["sandbox"]["filesystem_writes_allowed"] is False
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
        "actor_ref": "fixture-model-v1",
        "decision": _decision_for_request(request),
        "tool_calls": [],
    }


def _healthy_observation() -> dict[str, Any]:
    return build_onboarding_postcondition_observation(
        check_warning_codes=[],
        executable_todo_count=1,
        selected_action_kind="onboarding_connection_validation",
        normal_delivery_allowed=True,
        user_action_required=False,
        next_action_actionable=True,
    )


def test_closed_loop_pair_checks_entry_and_2134_postcondition_without_raw_retention() -> None:
    transitions: list[str] = []

    result = run_onboarding_closed_loop_pair(
        _entry_packet(compact=False),
        _entry_packet(compact=True),
        qualification_id="onboarding-2134-healthy-001",
        actor=_actor,
        transition_runner=lambda arm: transitions.append(arm) or _healthy_observation(),
        arm_order=("guided_default", "full_detail"),
    )

    assert result["schema_version"] == ONBOARDING_MODEL_BEHAVIOR_PAIR_SCHEMA_VERSION
    assert result["closed_loop_complete"] is True
    assert result["qualification_passed"] is True
    assert result["automatic_release_promotion_allowed"] is False
    assert result["entry"]["equivalent"] is True
    assert result["postcondition"]["equivalent"] is True
    assert transitions == ["guided_default", "full_detail"]
    encoded = json.dumps(result, sort_keys=True)
    assert "Detailed diagnostic material" not in encoded
    assert "onboarding_connection_validation" not in encoded
    assert "$PROJECT" not in encoded


def test_pair_rejects_missing_candidate_commands_before_provider_or_transition() -> None:
    calls = 0
    candidate = _entry_packet(compact=True)
    del candidate["commands"]["goal_start_host_loop_activation"]

    def actor(_: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    with pytest.raises(
        OnboardingModelBehaviorPairValidationError,
        match="not semantically equivalent",
    ):
        run_onboarding_closed_loop_pair(
            _entry_packet(compact=False),
            candidate,
            qualification_id="onboarding-command-gap-001",
            actor=actor,
            transition_runner=lambda _: _healthy_observation(),
        )
    assert calls == 0


def test_entry_source_misalignment_stops_before_allowlisted_transition() -> None:
    transitions = 0

    def wrong_actor(request: Mapping[str, Any]) -> Mapping[str, Any]:
        result = _actor(request)
        result["decision"] = dict(result["decision"])
        result["decision"]["next_action"] = "stop"
        return result

    def transition(_: str) -> Mapping[str, Any]:
        nonlocal transitions
        transitions += 1
        return _healthy_observation()

    result = run_onboarding_closed_loop_pair(
        _entry_packet(compact=False),
        _entry_packet(compact=True),
        qualification_id="onboarding-stop-before-transition-001",
        actor=wrong_actor,
        transition_runner=transition,
    )

    assert result["closed_loop_complete"] is False
    assert result["qualification_passed"] is False
    assert result["failure_code"] == "entry_source_alignment_failed"
    assert transitions == 0


def test_postcondition_builder_calibrates_known_2134_projection_gap() -> None:
    observation = build_onboarding_postcondition_observation(
        check_warning_codes=["state_projection_gap"],
        executable_todo_count=0,
        selected_action_kind=None,
        normal_delivery_allowed=False,
        user_action_required=False,
        next_action_actionable=True,
    )

    contract = onboarding_postcondition_semantic_contract(observation)

    assert contract == {
        "route": "repair_projection",
        "state_projection_gap": True,
        "executable_todo_present": False,
        "selected_action_kind": None,
        "normal_delivery_allowed": False,
        "user_action_required": False,
    }


def test_actor_request_rejects_local_paths_and_tool_boundary_changes() -> None:
    packet = _entry_packet(compact=True)
    packet["project"] = "/Users/example/private-project"
    with pytest.raises(ValueError, match="local absolute path"):
        build_onboarding_model_behavior_actor_request(
            packet,
            qualification_id="onboarding-private-path-001",
            arm="guided_default",
            phase="entry",
        )

    request = build_onboarding_model_behavior_actor_request(
        _entry_packet(compact=True),
        qualification_id="onboarding-boundary-001",
        arm="guided_default",
        phase="entry",
    )
    request["sandbox"] = {**request["sandbox"], "tools_enabled": True}
    from loopx.control_plane.testing.onboarding_model_behavior_qualification import (
        normalize_onboarding_model_behavior_actor_request,
    )

    with pytest.raises(ValueError, match="canonical no-write contract"):
        normalize_onboarding_model_behavior_actor_request(request)
