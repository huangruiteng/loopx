from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loopx.bootstrap_command_pack import build_start_goal_guided_packet
from loopx.control_plane.quota.turn_envelope import (
    build_turn_envelope,
    turn_envelope_action_signature_document,
)
from loopx.control_plane.testing.actual_default_model_behavior_portfolio import (
    ACTUAL_DEFAULT_MODEL_BEHAVIOR_PORTFOLIO_SCHEMA_VERSION,
    actual_default_model_behavior_scenario_catalog,
    run_actual_default_model_behavior_portfolio,
)
from loopx.control_plane.testing.model_behavior_qualification import (
    MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
    MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    model_behavior_semantic_contract_from_packet,
)
from loopx.control_plane.testing.onboarding_model_behavior_qualification import (
    ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
    build_onboarding_postcondition_observation,
    onboarding_entry_semantic_contract,
    onboarding_postcondition_semantic_contract,
)


GOAL_ID = "portfolio-goal"
AGENT_ID = "codex-portfolio"


def _write_project(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("# Active Goal State\n", encoding="utf-8")
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_file.relative_to(project)),
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return project, registry_path


def _guided_packet(
    project: Path,
    *,
    goal_id: str | None,
    agent_id: str | None,
) -> dict[str, Any]:
    return build_start_goal_guided_packet(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text="Establish one public-safe quality contract.",
        available_capabilities=["network"],
        include_command_pack_detail=False,
    )


def _entry_packets(tmp_path: Path) -> dict[str, dict[str, Any]]:
    project, registry_path = _write_project(tmp_path)
    connect = _guided_packet(project, goal_id=GOAL_ID, agent_id=AGENT_ID)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"].append(
        "codex-portfolio-reviewer"
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    identity = _guided_packet(project, goal_id=GOAL_ID, agent_id=None)

    second_goal = "portfolio-second-goal"
    second_state = project / ".codex" / "goals" / second_goal / "ACTIVE_GOAL_STATE.md"
    second_state.parent.mkdir(parents=True)
    second_state.write_text("# Second Active Goal State\n", encoding="utf-8")
    registry["goals"].append(
        {
            "id": second_goal,
            "status": "active",
            "repo": str(project),
            "state_file": str(second_state.relative_to(project)),
            "coordination": {
                "agent_model": "peer_v1",
                "registered_agents": ["codex-portfolio-second"],
            },
        }
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    goal_selection = _guided_packet(project, goal_id=None, agent_id=None)
    return {
        "onboarding_connect_default": connect,
        "onboarding_agent_identity_gate": identity,
        "onboarding_goal_selection_gate": goal_selection,
    }


def _turn_source(*, human_gate: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "should-run",
        "goal_id": GOAL_ID,
        "decision": "skip" if human_gate else "run",
        "should_run": not human_gate,
        "effective_action": "operator_gate" if human_gate else "normal_run",
        "state": "operator_gate" if human_gate else "eligible",
        "action_required": human_gate,
        "open_count": 1 if human_gate else 0,
        "recommended_action": (
            "Approve the bounded public release."
            if human_gate
            else "Implement one bounded public-safe slice."
        ),
        "selected_todo": (
            None
            if human_gate
            else {
                "todo_id": "todo_portfolio001",
                "status": "open",
                "task_class": "advancement_task",
                "claimed_by": AGENT_ID,
                "text": "Implement one bounded public-safe slice.",
            }
        ),
        "agent_identity": {"agent_id": AGENT_ID},
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "user_gate" if human_gate else "bounded_delivery",
            "user_channel": {
                "action_required": human_gate,
                "notify": "NOTIFY" if human_gate else "DONT_NOTIFY",
                "actions": ["Approve the bounded public release."]
                if human_gate
                else [],
            },
            "agent_channel": {
                "must_attempt": not human_gate,
                "delivery_allowed": not human_gate,
                "quiet_noop_allowed": False,
                "primary_action": (
                    "Wait for release approval."
                    if human_gate
                    else "Implement one bounded public-safe slice."
                ),
            },
            "cli_channel": {
                "next_cli_actions": [],
                "spend_allowed_now": False,
                "spend_after_validation": not human_gate,
                "spend_policy": (
                    "no spend while user gate is open"
                    if human_gate
                    else "spend after validated writeback"
                ),
            },
        },
        "goal_boundary": {
            "write_scope": ["loopx/**", "tests/**"],
            "guards": ["stop before external writes"],
        },
    }


def _scenario_packets(tmp_path: Path) -> dict[str, dict[str, Any]]:
    packets = _entry_packets(tmp_path)
    packets.update(
        {
            "turn_selected_todo": build_turn_envelope(_turn_source(human_gate=False)),
            "turn_human_gate": build_turn_envelope(_turn_source(human_gate=True)),
            "onboarding_healthy_continue": build_onboarding_postcondition_observation(
                check_warning_codes=[],
                executable_todo_count=1,
                selected_action_kind="quality_qualification",
                normal_delivery_allowed=True,
                user_action_required=False,
                next_action_actionable=True,
            ),
            "onboarding_projection_repair": build_onboarding_postcondition_observation(
                check_warning_codes=["state_projection_gap"],
                executable_todo_count=0,
                selected_action_kind=None,
                normal_delivery_allowed=False,
                user_action_required=False,
                next_action_actionable=True,
            ),
        }
    )
    return packets


def _turn_decision(request: Mapping[str, Any]) -> dict[str, Any]:
    packet = request["packet"]
    signature = turn_envelope_action_signature_document(packet)
    action = dict(signature["action"])
    user = dict(signature["user"])
    selected = dict(action.get("selected_todo") or {})
    user_gate = bool(user["action_required"])
    return {
        "schema_version": MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "decision": "ask_user" if user_gate else "execute",
        "selected_todo_id": selected.get("todo_id"),
        "user_action_required": user_gate,
        "must_attempt_work": bool(action["must_attempt"]),
        "delivery_allowed": bool(action["delivery_allowed"]),
        "quiet_noop_allowed": bool(action["quiet_noop_allowed"]),
        "external_write_requested": False,
        "intended_action_kinds": (
            ["notify", "wait"]
            if user_gate
            else ["inspect", "edit", "test", "writeback", "spend"]
        ),
        "reason_codes": ["source_aligned"],
        "semantic_contract": model_behavior_semantic_contract_from_packet(
            packet,
            arm="candidate_packet",
        ),
    }


def _turn_actor(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
        "actor_ref": "fixture-turn-model-v1",
        "decision": _turn_decision(request),
        "tool_calls": [],
    }


def _onboarding_actor(request: Mapping[str, Any]) -> dict[str, Any]:
    phase = str(request["phase"])
    contract = (
        onboarding_entry_semantic_contract(request["packet"])
        if phase == "entry"
        else onboarding_postcondition_semantic_contract(request["packet"])
    )
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
        "actor_ref": "fixture-onboarding-model-v1",
        "decision": {
            "schema_version": ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
            "phase": phase,
            "next_action": contract["route"],
            "semantic_contract": contract,
            "reason_codes": ["source_aligned"],
        },
        "tool_calls": [],
    }


def test_portfolio_runs_actual_default_one_arm_scenarios_twice(tmp_path: Path) -> None:
    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-001",
        turn_actor=_turn_actor,
        onboarding_actor=_onboarding_actor,
    )

    assert (
        result["schema_version"]
        == ACTUAL_DEFAULT_MODEL_BEHAVIOR_PORTFOLIO_SCHEMA_VERSION
    )
    assert result["topology"] == "actual_default_one_arm"
    assert result["scenario_count"] == 7
    assert result["actor_call_budget"] == 14
    assert result["actor_call_count"] == 14
    assert result["qualification_passed"] is True
    assert result["automatic_release_promotion_allowed"] is False
    assert all(item["status"] == "passed" for item in result["scenarios"])
    assert all(item["repeats_completed"] == 2 for item in result["scenarios"])
    encoded = json.dumps(result, sort_keys=True)
    assert str(tmp_path) not in encoded
    assert "todo_portfolio001" not in encoded
    assert "Implement one bounded" not in encoded


def test_portfolio_oracle_catches_wrong_selected_todo(tmp_path: Path) -> None:
    def wrong_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        if request["packet"]["user"]["action_required"] is False:
            result["decision"] = {
                **result["decision"],
                "selected_todo_id": "todo_wrong001",
            }
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-wrong-todo",
        turn_actor=wrong_actor,
        onboarding_actor=_onboarding_actor,
    )

    selected = next(
        item
        for item in result["scenarios"]
        if item["scenario_id"] == "turn_selected_todo"
    )
    assert result["qualification_passed"] is False
    assert selected["status"] == "failed"
    assert selected["repeats_completed"] == 2
    assert selected["failure_codes"] == ["source_mismatch:selected_todo_id"]


def test_catalog_declares_independent_bounded_repeat_policy() -> None:
    catalog = actual_default_model_behavior_scenario_catalog()

    assert catalog["topology"] == "actual_default_one_arm"
    assert len(catalog["scenarios"]) == 7
    assert all(
        scenario["repeat_policy"]
        == {
            "attempts": 2,
            "pass_condition": "all_attempts_source_aligned",
            "automatic_retry_on_actor_error": False,
        }
        for scenario in catalog["scenarios"]
    )


def test_portfolio_preflights_every_scenario_before_actor_spend(tmp_path: Path) -> None:
    packets = _scenario_packets(tmp_path)
    packets["onboarding_projection_repair"] = {
        **packets["onboarding_projection_repair"],
        "derived_route": "continue_validation",
    }
    calls = 0

    def turn_actor(request: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return _turn_actor(request)

    def onboarding_actor(request: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return _onboarding_actor(request)

    with pytest.raises(
        ValueError,
        match="actual onboarding behavior violates stable invariants",
    ):
        run_actual_default_model_behavior_portfolio(
            packets,
            qualification_id="actual-default-portfolio-preflight",
            turn_actor=turn_actor,
            onboarding_actor=onboarding_actor,
        )

    assert calls == 0
