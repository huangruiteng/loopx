from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from loopx.control_plane.testing.onboarding_model_behavior_qualification import (
    ONBOARDING_ACTUAL_BEHAVIOR_QUALIFICATION_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
    ONBOARDING_REQUIRED_CONNECT_COMMAND_IDS,
    OnboardingActualBehaviorValidationError,
    build_onboarding_model_behavior_actor_request,
    build_onboarding_postcondition_observation,
    normalize_onboarding_model_behavior_actor_request,
    onboarding_entry_semantic_contract,
    onboarding_postcondition_semantic_contract,
    run_onboarding_actual_behavior_qualification,
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


def _actual_entry_packet() -> dict[str, Any]:
    return {
        "schema_version": "loopx_start_goal_guided_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "guided_transaction": TRANSACTION,
        "safety_contract": {
            "writes_registry": False,
            "writes_state_file": False,
            "spends_quota": False,
        },
        "command_pack": {
            "commands": dict(COMMANDS),
            "host_loop_activation": dict(ACTIVATION),
            "message": "Current default command-pack detail.",
        },
    }


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


def _projection_gap_observation() -> dict[str, Any]:
    return build_onboarding_postcondition_observation(
        check_warning_codes=["state_projection_gap"],
        executable_todo_count=0,
        selected_action_kind=None,
        normal_delivery_allowed=False,
        user_action_required=False,
        next_action_actionable=True,
    )


def test_actual_default_closed_loop_checks_healthy_and_2134_repair_behavior() -> None:
    transitions = 0

    def transition() -> Mapping[str, Any]:
        nonlocal transitions
        transitions += 1
        return _healthy_observation()

    result = run_onboarding_actual_behavior_qualification(
        _actual_entry_packet(),
        qualification_id="onboarding-actual-2134-001",
        actor=_actor,
        transition_runner=transition,
        repair_observation=_projection_gap_observation(),
    )

    assert (
        result["schema_version"]
        == ONBOARDING_ACTUAL_BEHAVIOR_QUALIFICATION_SCHEMA_VERSION
    )
    assert result["closed_loop_complete"] is True
    assert result["qualification_passed"] is True
    assert result["automatic_release_promotion_allowed"] is False
    assert result["entry"]["next_action"] == "connect_if_needed"
    assert (
        result["healthy_postcondition"]["next_action"] == "continue_validation"
    )
    assert result["repair_calibration"]["next_action"] == "repair_projection"
    assert transitions == 1
    encoded = json.dumps(result, sort_keys=True)
    assert "arm" not in encoded
    assert "onboarding_connection_validation" not in encoded
    assert "$PROJECT" not in encoded


def test_independent_oracle_rejects_command_loss_before_model_or_transition() -> None:
    calls = 0
    transitions = 0
    packet = _actual_entry_packet()
    del packet["command_pack"]["commands"]["goal_start_host_loop_activation"]

    def actor(_: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    def transition() -> Mapping[str, Any]:
        nonlocal transitions
        transitions += 1
        return _healthy_observation()

    with pytest.raises(
        OnboardingActualBehaviorValidationError,
        match="connect_route_missing_required_commands",
    ):
        run_onboarding_actual_behavior_qualification(
            packet,
            qualification_id="onboarding-command-gap-001",
            actor=actor,
            transition_runner=transition,
            repair_observation=_projection_gap_observation(),
        )

    assert tuple(COMMANDS) == ONBOARDING_REQUIRED_CONNECT_COMMAND_IDS
    assert calls == 0
    assert transitions == 0


def test_independent_oracle_rejects_host_activation_loss_before_model() -> None:
    calls = 0
    packet = _actual_entry_packet()
    del packet["command_pack"]["host_loop_activation"]

    def actor(_: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    with pytest.raises(
        OnboardingActualBehaviorValidationError,
        match="connect_route_requires_host_loop_activation",
    ):
        run_onboarding_actual_behavior_qualification(
            packet,
            qualification_id="onboarding-activation-gap-001",
            actor=actor,
            transition_runner=_healthy_observation,
            repair_observation=_projection_gap_observation(),
        )

    assert calls == 0


def test_entry_source_misalignment_stops_before_allowlisted_transition() -> None:
    transitions = 0

    def wrong_actor(request: Mapping[str, Any]) -> Mapping[str, Any]:
        result = _actor(request)
        result["decision"] = dict(result["decision"])
        result["decision"]["next_action"] = "stop"
        return result

    def transition() -> Mapping[str, Any]:
        nonlocal transitions
        transitions += 1
        return _healthy_observation()

    result = run_onboarding_actual_behavior_qualification(
        _actual_entry_packet(),
        qualification_id="onboarding-stop-before-transition-001",
        actor=wrong_actor,
        transition_runner=transition,
        repair_observation=_projection_gap_observation(),
    )

    assert result["closed_loop_complete"] is False
    assert result["qualification_passed"] is False
    assert result["failure_code"] == "entry_source_alignment_failed"
    assert transitions == 0


def test_actual_projection_gap_fails_the_healthy_postcondition() -> None:
    result = run_onboarding_actual_behavior_qualification(
        _actual_entry_packet(),
        qualification_id="onboarding-actual-gap-001",
        actor=_actor,
        transition_runner=_projection_gap_observation,
        repair_observation=_projection_gap_observation(),
    )

    assert result["closed_loop_complete"] is True
    assert result["qualification_passed"] is False
    assert result["failure_code"] == "actual_postcondition_not_healthy"


def test_postcondition_builder_calibrates_known_2134_projection_gap() -> None:
    contract = onboarding_postcondition_semantic_contract(
        _projection_gap_observation()
    )

    assert contract == {
        "route": "repair_projection",
        "state_projection_gap": True,
        "executable_todo_present": False,
        "selected_action_kind": None,
        "normal_delivery_allowed": False,
        "user_action_required": False,
    }


def test_actor_request_rejects_local_paths_and_tool_boundary_changes() -> None:
    packet = _actual_entry_packet()
    packet["project"] = "/Users/example/private-project"
    with pytest.raises(ValueError, match="local absolute path"):
        build_onboarding_model_behavior_actor_request(
            packet,
            qualification_id="onboarding-private-path-001",
            phase="entry",
        )

    request = build_onboarding_model_behavior_actor_request(
        _actual_entry_packet(),
        qualification_id="onboarding-boundary-001",
        phase="entry",
    )
    request["sandbox"] = {**request["sandbox"], "tools_enabled": True}

    with pytest.raises(ValueError, match="canonical no-write contract"):
        normalize_onboarding_model_behavior_actor_request(request)
