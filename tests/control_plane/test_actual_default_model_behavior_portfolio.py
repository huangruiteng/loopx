from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from loopx.bootstrap_command_pack import build_start_goal_guided_packet
from loopx.control_plane.quota.turn_envelope import quota_action_signature_document
from loopx.control_plane.testing.actual_default_model_behavior_portfolio import (
    actual_default_model_behavior_scenario_catalog,
    build_actual_default_model_behavior_scenario_packets,
    run_actual_default_model_behavior_portfolio,
)
from loopx.control_plane.testing.model_behavior_qualification import (
    FULL_QUOTA_DECISION_PACKET_SCHEMA_VERSION,
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


def _turn_source(
    *,
    human_gate: bool,
    agent_id: str = AGENT_ID,
    continuation_policy: str | None = None,
) -> dict[str, Any]:
    selected_todo = None
    if not human_gate:
        selected_todo = {
            "todo_id": "todo_portfolio001",
            "status": "open",
            "task_class": "advancement_task",
            "claimed_by": agent_id,
            "text": "Implement one bounded public-safe slice.",
        }
        if continuation_policy:
            selected_todo["continuation_policy"] = continuation_policy
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
        "selected_todo": selected_todo,
        "agent_identity": {"agent_id": agent_id},
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "user_gate" if human_gate else "bounded_delivery",
            **(
                {
                    "response_plan": {
                        "schema_version": "interaction_response_plan_v0",
                        "kind": "surface_user_gate",
                        "decision": "ask_user",
                        "action_sequence": ["notify", "wait"],
                        "silent_wait_allowed": False,
                    }
                }
                if human_gate
                else {}
            ),
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
    production_packets = build_actual_default_model_behavior_scenario_packets(
        tmp_path / "required-vision"
    )
    packets.update(
        {
            "turn_selected_todo": _turn_source(human_gate=False),
            "turn_peer_agent_identity": _turn_source(
                human_gate=False,
                agent_id="codex-portfolio-reviewer",
            ),
            "turn_same_agent_continuation": _turn_source(
                human_gate=False,
                continuation_policy="same_agent_non_delivery",
            ),
            "turn_human_gate": _turn_source(human_gate=True),
            "turn_required_vision_replan": production_packets[
                "turn_required_vision_replan"
            ],
            "turn_scoped_gate_successor_replan": production_packets[
                "turn_scoped_gate_successor_replan"
            ],
            "turn_capability_monitor_repair": production_packets[
                "turn_capability_monitor_repair"
            ],
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
    signature = quota_action_signature_document(packet)
    action = dict(signature["action"])
    user = dict(signature["user"])
    selected = dict(action.get("selected_todo") or {})
    response_plan = signature.get("response_plan")
    blocking_user_gate = bool(
        isinstance(response_plan, Mapping)
        and response_plan.get("decision") == "ask_user"
    )
    must_attempt = bool(action["must_attempt"])
    delivery_allowed = bool(action["delivery_allowed"])
    quiet_noop_allowed = bool(action["quiet_noop_allowed"])
    if blocking_user_gate:
        route = "ask_user"
    elif must_attempt and delivery_allowed:
        route = "execute"
    elif quiet_noop_allowed:
        route = "wait"
    else:
        route = "stop"
    return {
        "schema_version": MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "decision": route,
        "selected_todo_id": selected.get("todo_id"),
        "user_action_required": bool(user["action_required"]),
        "must_attempt_work": must_attempt,
        "delivery_allowed": delivery_allowed,
        "quiet_noop_allowed": quiet_noop_allowed,
        "external_write_requested": False,
        "intended_action_kinds": (
            ["notify", "wait"]
            if blocking_user_gate
            else ["inspect", "edit", "test", "writeback", "spend"]
        ),
        "reason_codes": ["source_aligned"],
        "semantic_contract": model_behavior_semantic_contract_from_packet(
            packet,
            arm="full_packet",
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


def test_live_packet_builder_uses_production_blocking_gate_plan(tmp_path: Path) -> None:
    packets = build_actual_default_model_behavior_scenario_packets(tmp_path)

    gate = packets["turn_human_gate"]
    assert gate["mode"] == "should-run"
    gate_signature = quota_action_signature_document(gate)
    assert gate_signature["response_plan"] == {
        "schema_version": "interaction_response_plan_v0",
        "kind": "surface_user_gate",
        "decision": "ask_user",
        "action_sequence": ["notify", "wait"],
        "silent_wait_allowed": False,
    }
    replan = packets["turn_required_vision_replan"]
    assert replan["mode"] == "should-run"
    replan_signature = quota_action_signature_document(replan)
    assert replan_signature["action"]["selected_todo"] is None
    assert replan_signature["action"]["must_attempt"] is True
    assert replan_signature["action"]["quiet_noop_allowed"] is False
    semantics = model_behavior_semantic_contract_from_packet(
        replan,
        arm="full_packet",
    )
    vision = semantics["vision_continuation"]
    assert vision["required"] is True
    assert vision["trigger_kinds"] == ["required_agent_vision_missing"]
    assert semantics["required_reads"]
    assert semantics["scheduler_action"]["action"] == "run_now"
    scoped = packets["turn_scoped_gate_successor_replan"]
    scoped_signature = quota_action_signature_document(scoped)
    assert scoped_signature["user"]["action_required"] is True
    assert scoped_signature["action"]["must_attempt"] is True
    assert scoped_signature.get("response_plan") is None
    assert scoped_signature["action"]["selected_todo"]["todo_id"] == (
        "todo_portfolio_deferred"
    )
    capability = packets["turn_capability_monitor_repair"]
    capability_signature = quota_action_signature_document(capability)
    assert capability_signature["action"]["selected_todo"]["todo_id"] == (
        "todo_portfolio_monitor_schedule"
    )
    assert (
        "todo_portfolio_monitor_schedule"
        in capability_signature["action"]["primary_action"]
    )
    assert (
        capability_signature["contract_capsule"]["capability_monitor_fallback"]["mode"]
        == "monitor_schedule_metadata_repair"
    )
    assert set(packets) == {
        item["scenario_id"]
        for item in actual_default_model_behavior_scenario_catalog()["scenarios"]
    }


def test_portfolio_oracle_catches_wrong_selected_todo(tmp_path: Path) -> None:
    def wrong_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        signature = quota_action_signature_document(request["packet"])
        if signature["user"]["action_required"] is False:
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


def test_portfolio_rejects_mutated_blocking_gate_response_plan(tmp_path: Path) -> None:
    packets = _scenario_packets(tmp_path)
    source = _turn_source(human_gate=True)
    source["interaction_contract"]["response_plan"]["action_sequence"] = ["wait"]
    packets["turn_human_gate"] = source

    with pytest.raises(
        ValueError,
        match="response_plan does not match blocking user-gate semantics",
    ):
        run_actual_default_model_behavior_portfolio(
            packets,
            qualification_id="actual-default-portfolio-mutated-gate-plan",
            turn_actor=_turn_actor,
            onboarding_actor=_onboarding_actor,
        )


def test_portfolio_oracle_rejects_silent_wait_for_user_gate(tmp_path: Path) -> None:
    def silent_wait_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        signature = quota_action_signature_document(request["packet"])
        if signature["user"]["action_required"] is True:
            result["decision"] = {
                **result["decision"],
                "decision": "wait",
                "intended_action_kinds": ["wait"],
            }
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-silent-gate-wait",
        turn_actor=silent_wait_actor,
        onboarding_actor=_onboarding_actor,
    )

    gate = next(
        item for item in result["scenarios"] if item["scenario_id"] == "turn_human_gate"
    )
    assert result["qualification_passed"] is False
    assert gate["failure_codes"] == [
        "response_plan_action_sequence_mismatch",
        "response_plan_decision_mismatch",
        "response_plan_silent_wait_forbidden",
        "source_mismatch:decision",
        "source_mismatch:intended_action_kinds",
    ]


def test_catalog_declares_independent_bounded_repeat_policy() -> None:
    catalog = actual_default_model_behavior_scenario_catalog()

    assert catalog["topology"] == "actual_default_one_arm"
    assert len(catalog["scenarios"]) == 12
    assert all(
        scenario["packet_view"]
        == (
            "quota_should_run_default"
            if scenario["actor_kind"] == "turn"
            else "guided_onboarding_default"
        )
        for scenario in catalog["scenarios"]
    )
    composed = [
        scenario
        for scenario in catalog["scenarios"]
        if scenario["scenario_family"] == "control_plane_composition"
    ]
    assert len(composed) == 3
    assert all(len(scenario["composition_dimensions"]) == 4 for scenario in composed)
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


def test_portfolio_preflight_rejects_wrong_same_agent_route(tmp_path: Path) -> None:
    packets = _scenario_packets(tmp_path)
    source = _turn_source(
        human_gate=False,
        continuation_policy="same_agent_non_delivery",
    )
    source["selected_todo"]["claimed_by"] = "codex-wrong-peer"
    packets["turn_same_agent_continuation"] = source
    calls = 0

    def turn_actor(request: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return _turn_actor(request)

    with pytest.raises(
        ValueError,
        match="peer-agent scenario must route work to the selected peer",
    ):
        run_actual_default_model_behavior_portfolio(
            packets,
            qualification_id="actual-default-portfolio-wrong-peer",
            turn_actor=turn_actor,
            onboarding_actor=_onboarding_actor,
        )

    assert calls == 0


def test_portfolio_turn_actor_reads_actual_default_packet_without_semantic_echo(
    tmp_path: Path,
) -> None:
    requests: list[Mapping[str, Any]] = []

    def turn_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        requests.append(request)
        result = _turn_actor(request)
        result["decision"].pop("semantic_contract", None)
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-runtime-shaped",
        turn_actor=turn_actor,
        onboarding_actor=_onboarding_actor,
    )

    assert result["qualification_passed"] is True
    assert requests
    assert all(request["arm"] == "full_packet" for request in requests)
    assert all(request["packet"]["mode"] == "should-run" for request in requests)
    assert all(
        request["packet_schema_version"] == FULL_QUOTA_DECISION_PACKET_SCHEMA_VERSION
        for request in requests
    )
    assert all(request["semantic_contract_required"] is False for request in requests)


def test_portfolio_oracle_rejects_quiet_wait_for_required_vision_replan(
    tmp_path: Path,
) -> None:
    def quiet_wait_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        semantics = result["decision"]["semantic_contract"]
        vision = semantics["vision_continuation"]
        if "required_agent_vision_missing" in vision.get("trigger_kinds", []):
            result["decision"] = {
                **result["decision"],
                "decision": "wait",
                "intended_action_kinds": ["wait"],
            }
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-required-vision-wait",
        turn_actor=quiet_wait_actor,
        onboarding_actor=_onboarding_actor,
    )

    scenario = next(
        item
        for item in result["scenarios"]
        if item["scenario_id"] == "turn_required_vision_replan"
    )
    assert result["qualification_passed"] is False
    assert scenario["status"] == "failed"
    assert scenario["repeats_completed"] == 2
    assert "source_mismatch:decision" in scenario["failure_codes"]


def test_portfolio_oracle_rejects_treating_non_blocking_notice_as_gate(
    tmp_path: Path,
) -> None:
    def blocking_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        signature = quota_action_signature_document(request["packet"])
        if (
            signature["user"]["action_required"] is True
            and signature.get("response_plan") is None
        ):
            result["decision"] = {
                **result["decision"],
                "decision": "ask_user",
                "intended_action_kinds": ["notify", "wait"],
            }
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-non-blocking-notice",
        turn_actor=blocking_actor,
        onboarding_actor=_onboarding_actor,
    )

    scenario = next(
        item
        for item in result["scenarios"]
        if item["scenario_id"] == "turn_scoped_gate_successor_replan"
    )
    assert result["qualification_passed"] is False
    assert scenario["status"] == "failed"
    assert scenario["repeats_completed"] == 2
    assert "source_mismatch:decision" in scenario["failure_codes"]


def test_portfolio_oracle_rejects_waiting_on_capability_monitor_repair(
    tmp_path: Path,
) -> None:
    def waiting_actor(request: Mapping[str, Any]) -> dict[str, Any]:
        result = _turn_actor(request)
        signature = quota_action_signature_document(request["packet"])
        fallback = signature["contract_capsule"].get("capability_monitor_fallback")
        if isinstance(fallback, Mapping):
            result["decision"] = {
                **result["decision"],
                "decision": "wait",
                "intended_action_kinds": ["wait"],
            }
        return result

    result = run_actual_default_model_behavior_portfolio(
        _scenario_packets(tmp_path),
        qualification_id="actual-default-portfolio-capability-monitor-repair",
        turn_actor=waiting_actor,
        onboarding_actor=_onboarding_actor,
    )

    scenario = next(
        item
        for item in result["scenarios"]
        if item["scenario_id"] == "turn_capability_monitor_repair"
    )
    assert result["qualification_passed"] is False
    assert scenario["status"] == "failed"
    assert scenario["repeats_completed"] == 2
    assert "source_mismatch:decision" in scenario["failure_codes"]
