from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from ...bootstrap_command_pack import build_start_goal_guided_packet
from ..quota.turn_envelope import quota_action_signature_document
from ..work_items.interaction_contract import build_interaction_contract
from .control_plane_composition_scenarios import (
    build_control_plane_composition_scenario_sources,
)
from .model_behavior_qualification import (
    ModelBehaviorActor,
    _actor_failure_code,
    build_model_behavior_actor_request,
    model_behavior_semantic_contract_from_packet,
    run_model_behavior_qualification_arm,
)
from .onboarding_model_behavior_qualification import (
    OnboardingActualBehaviorValidationError,
    OnboardingModelBehaviorActor,
    _behavior_contract_violations,
    _semantic_contract,
    _validate_actual_default_projection,
    build_onboarding_postcondition_observation,
    build_onboarding_model_behavior_actor_request,
    run_onboarding_model_behavior_phase,
)


ACTUAL_DEFAULT_MODEL_BEHAVIOR_PORTFOLIO_SCHEMA_VERSION = (
    "actual_default_model_behavior_portfolio_v0"
)
ACTUAL_DEFAULT_MODEL_BEHAVIOR_CATALOG_SCHEMA_VERSION = (
    "actual_default_model_behavior_scenario_catalog_v0"
)
ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS = 2
ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID = "portfolio-goal"
ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_AGENT_ID = "codex-portfolio"


@dataclass(frozen=True)
class _ScenarioSpec:
    scenario_id: str
    actor_kind: str
    phase: str | None
    expected_route: str
    scenario_family: str = "core_contract"
    composition_dimensions: tuple[str, ...] = ()


_SCENARIOS = (
    _ScenarioSpec(
        "onboarding_connect_default",
        "onboarding",
        "entry",
        "connect_if_needed",
    ),
    _ScenarioSpec(
        "onboarding_agent_identity_gate",
        "onboarding",
        "entry",
        "select_agent_identity",
    ),
    _ScenarioSpec(
        "onboarding_goal_selection_gate",
        "onboarding",
        "entry",
        "select_goal",
    ),
    _ScenarioSpec(
        "turn_selected_todo",
        "turn",
        None,
        "execute",
    ),
    _ScenarioSpec(
        "turn_peer_agent_identity",
        "turn",
        None,
        "execute",
    ),
    _ScenarioSpec(
        "turn_same_agent_continuation",
        "turn",
        None,
        "execute",
    ),
    _ScenarioSpec(
        "turn_human_gate",
        "turn",
        None,
        "ask_user",
    ),
    _ScenarioSpec(
        "turn_required_vision_replan",
        "turn",
        None,
        "execute",
        "control_plane_composition",
        ("vision", "monitor", "peer_ownership", "autonomous_replan"),
    ),
    _ScenarioSpec(
        "turn_scoped_gate_successor_replan",
        "turn",
        None,
        "execute",
        "control_plane_composition",
        ("user_gate", "deferred_successor", "non_blocking_notice", "scheduler"),
    ),
    _ScenarioSpec(
        "turn_capability_monitor_repair",
        "turn",
        None,
        "execute",
        "control_plane_composition",
        ("capability_gate", "monitor_schedule", "fallback", "selected_action"),
    ),
    _ScenarioSpec(
        "onboarding_healthy_continue",
        "onboarding",
        "postcondition",
        "continue_validation",
    ),
    _ScenarioSpec(
        "onboarding_projection_repair",
        "onboarding",
        "postcondition",
        "repair_projection",
    ),
)
ACTUAL_DEFAULT_MODEL_BEHAVIOR_SCENARIO_COUNT = len(_SCENARIOS)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def actual_default_model_behavior_scenario_catalog() -> dict[str, Any]:
    return {
        "schema_version": ACTUAL_DEFAULT_MODEL_BEHAVIOR_CATALOG_SCHEMA_VERSION,
        "topology": "actual_default_one_arm",
        "scenarios": [
            {
                "scenario_id": spec.scenario_id,
                "actor_kind": spec.actor_kind,
                "phase": spec.phase,
                "expected_route": spec.expected_route,
                "scenario_family": spec.scenario_family,
                "composition_dimensions": list(spec.composition_dimensions),
                "packet_view": (
                    "quota_should_run_default"
                    if spec.actor_kind == "turn"
                    else "guided_onboarding_default"
                ),
                "repeat_policy": {
                    "attempts": ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS,
                    "pass_condition": "all_attempts_source_aligned",
                    "automatic_retry_on_actor_error": False,
                },
            }
            for spec in _SCENARIOS
        ],
    }


def _write_scenario_project(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    state_file = (
        project
        / ".codex"
        / "goals"
        / ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID
        / "ACTIVE_GOAL_STATE.md"
    )
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
                        "id": ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state_file.relative_to(project)),
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [
                                ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_AGENT_ID
                            ],
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


def _guided_scenario_packet(
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


def _entry_scenario_packets(root: Path) -> dict[str, dict[str, Any]]:
    project, registry_path = _write_scenario_project(root)
    connect = _guided_scenario_packet(
        project,
        goal_id=ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID,
        agent_id=ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_AGENT_ID,
    )

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"].append(
        "codex-portfolio-reviewer"
    )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    identity = _guided_scenario_packet(
        project,
        goal_id=ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID,
        agent_id=None,
    )

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
    goal_selection = _guided_scenario_packet(project, goal_id=None, agent_id=None)
    return {
        "onboarding_connect_default": connect,
        "onboarding_agent_identity_gate": identity,
        "onboarding_goal_selection_gate": goal_selection,
    }


def _turn_scenario_source(
    *,
    human_gate: bool,
    agent_id: str = ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_AGENT_ID,
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
    payload: dict[str, Any] = {
        "ok": True,
        "mode": "should-run",
        "goal_id": ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID,
        "decision": "skip" if human_gate else "run",
        "should_run": not human_gate,
        "effective_action": "operator_gate" if human_gate else "normal_run",
        "state": "operator_gate" if human_gate else "eligible",
        "requires_user_action": human_gate,
        "gate_prompt": ("Approve the bounded public release." if human_gate else None),
        "recommended_action": (
            "Approve the bounded public release."
            if human_gate
            else "Implement one bounded public-safe slice."
        ),
        "selected_todo": selected_todo,
        "agent_identity": {"agent_id": agent_id},
        "execution_obligation": {
            "must_attempt_work": not human_gate,
            "delivery_allowed": not human_gate,
        },
        "normal_delivery_allowed": not human_gate,
        "heartbeat_recommendation": {
            "notify": "NOTIFY" if human_gate else "DONT_NOTIFY"
        },
        "goal_boundary": {
            "write_scope": ["loopx/**", "tests/**"],
            "guards": ["stop before external writes"],
        },
    }
    payload["interaction_contract"] = build_interaction_contract(
        payload,
        available_capabilities=["network"],
    )
    payload["action_required"] = human_gate
    payload["open_count"] = 1 if human_gate else 0
    return payload


def build_actual_default_model_behavior_scenario_packets(
    root: Path,
) -> dict[str, dict[str, Any]]:
    """Build the default packets used by Codex App automation qualification."""

    packets = _entry_scenario_packets(root)
    packets.update(
        {
            "turn_selected_todo": _turn_scenario_source(human_gate=False),
            "turn_peer_agent_identity": _turn_scenario_source(
                human_gate=False,
                agent_id="codex-portfolio-reviewer",
            ),
            "turn_same_agent_continuation": _turn_scenario_source(
                human_gate=False,
                continuation_policy="same_agent_non_delivery",
            ),
            "turn_human_gate": _turn_scenario_source(human_gate=True),
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
    packets.update(
        build_control_plane_composition_scenario_sources(
            goal_id=ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_GOAL_ID,
            agent_id=ACTUAL_DEFAULT_MODEL_BEHAVIOR_FIXTURE_AGENT_ID,
        )
    )
    return packets


def _turn_expected_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("mode") != "should-run":
        raise ValueError("turn scenarios require the default quota should-run packet")
    signature = quota_action_signature_document(packet)
    action = dict(signature.get("action") or {})
    user = dict(signature.get("user") or {})
    selected_todo = dict(action.get("selected_todo") or {})
    user_action_required = bool(user.get("action_required"))
    must_attempt = bool(action.get("must_attempt"))
    delivery_allowed = bool(action.get("delivery_allowed"))
    quiet_noop_allowed = bool(action.get("quiet_noop_allowed"))
    response_plan = signature.get("response_plan")
    blocking_user_gate = bool(
        isinstance(response_plan, Mapping)
        and response_plan.get("decision") == "ask_user"
    )
    if blocking_user_gate:
        route = "ask_user"
    elif must_attempt and delivery_allowed:
        route = "execute"
    elif quiet_noop_allowed:
        route = "wait"
    else:
        route = "stop"
    contract = {
        "decision": route,
        "selected_todo_id": selected_todo.get("todo_id"),
        "user_action_required": user_action_required,
        "must_attempt_work": must_attempt,
        "delivery_allowed": delivery_allowed,
        "quiet_noop_allowed": quiet_noop_allowed,
        "external_write_requested": False,
    }
    if blocking_user_gate:
        contract["intended_action_kinds"] = ["notify", "wait"]
    return contract


def _scenario_contract(
    spec: _ScenarioSpec,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if spec.actor_kind == "turn":
        build_model_behavior_actor_request(
            packet,
            qualification_id=f"portfolio-preflight-{spec.scenario_id}",
            arm="full_packet",
            semantic_contract_required=False,
        )
        contract = _turn_expected_contract(packet)
    else:
        if spec.phase == "entry":
            _validate_actual_default_projection(packet)
        build_onboarding_model_behavior_actor_request(
            packet,
            qualification_id=f"portfolio-preflight-{spec.scenario_id}",
            phase=str(spec.phase),
        )
        contract = _semantic_contract(packet, phase=str(spec.phase))
        violations = _behavior_contract_violations(contract, phase=str(spec.phase))
        if violations:
            raise OnboardingActualBehaviorValidationError(
                "actual onboarding behavior violates stable invariants: "
                + ", ".join(violations)
            )
    if contract.get("decision", contract.get("route")) != spec.expected_route:
        raise ValueError(
            f"scenario {spec.scenario_id} does not produce {spec.expected_route}"
        )
    if (
        spec.scenario_id == "onboarding_agent_identity_gate"
        and contract.get("agent_id") is not None
    ):
        raise ValueError("identity-gate scenario must not preselect an agent")
    if (
        spec.scenario_id == "onboarding_goal_selection_gate"
        and contract.get("goal_id") is not None
    ):
        raise ValueError("goal-selection scenario must not preselect a goal")
    if spec.scenario_id == "turn_selected_todo" and not contract.get(
        "selected_todo_id"
    ):
        raise ValueError("selected-todo scenario requires selected work")
    if spec.scenario_id in {
        "turn_peer_agent_identity",
        "turn_same_agent_continuation",
    }:
        peer_route = model_behavior_semantic_contract_from_packet(
            packet,
            arm="full_packet",
        )["peer_route"]
        if not peer_route.get("agent_id"):
            raise ValueError("peer-agent scenario requires a selected agent identity")
        if peer_route.get("selected_todo_claimed_by") != peer_route.get("agent_id"):
            raise ValueError("peer-agent scenario must route work to the selected peer")
        if spec.scenario_id == "turn_same_agent_continuation":
            if peer_route.get("continuation_policy") != "same_agent_non_delivery":
                raise ValueError("same-agent scenario requires same_agent_non_delivery")
            if peer_route.get("same_agent_continuation") is not True:
                raise ValueError(
                    "same-agent scenario must preserve the completing peer"
                )
    if spec.scenario_id == "turn_human_gate":
        required = {
            "selected_todo_id": None,
            "user_action_required": True,
            "must_attempt_work": False,
            "delivery_allowed": False,
            "quiet_noop_allowed": False,
        }
        if any(contract.get(field) != value for field, value in required.items()):
            raise ValueError("human-gate scenario violates final gate precedence")
    if spec.scenario_id == "turn_required_vision_replan":
        semantics = model_behavior_semantic_contract_from_packet(
            packet,
            arm="full_packet",
        )
        vision = semantics["vision_continuation"]
        trigger_kinds = set(vision.get("trigger_kinds", []))
        required = {
            "selected_todo_id": None,
            "user_action_required": False,
            "must_attempt_work": True,
            "quiet_noop_allowed": False,
        }
        if any(contract.get(field) != value for field, value in required.items()):
            raise ValueError("required-vision scenario must execute before quiet wait")
        if vision.get("required") is not True or (
            "required_agent_vision_missing" not in trigger_kinds
        ):
            raise ValueError("required-vision scenario must preserve the profile gap")
        if not semantics["required_reads"]:
            raise ValueError("required-vision scenario must preserve required reads")
        if semantics["scheduler_action"].get("action") != "run_now":
            raise ValueError(
                "required-vision scenario must remain immediately runnable"
            )
    if spec.scenario_id == "turn_scoped_gate_successor_replan":
        signature = quota_action_signature_document(packet)
        action = dict(signature.get("action") or {})
        user = dict(signature.get("user") or {})
        selected = dict(action.get("selected_todo") or {})
        if not (
            user.get("action_required") is True
            and action.get("must_attempt") is True
            and action.get("delivery_allowed") is True
            and signature.get("response_plan") is None
            and selected.get("todo_id") == "todo_portfolio_deferred"
        ):
            raise ValueError(
                "scoped-gate scenario must notify without blocking successor replan"
            )
        semantics = model_behavior_semantic_contract_from_packet(
            packet,
            arm="full_packet",
        )
        if semantics["gate_or_stop"].get("interaction_mode") != (
            "scoped_user_gate_fallback"
        ):
            raise ValueError("scoped-gate scenario must preserve fallback mode")
        if semantics["scheduler_action"].get("action") != "run_now":
            raise ValueError("scoped-gate fallback must remain immediately runnable")
    if spec.scenario_id == "turn_capability_monitor_repair":
        signature = quota_action_signature_document(packet)
        capsule = dict(signature.get("contract_capsule") or {})
        lane = dict(capsule.get("work_lane_contract") or {})
        fallback = dict(capsule.get("capability_monitor_fallback") or {})
        action = dict(signature.get("action") or {})
        selected = dict(action.get("selected_todo") or {})
        if not (
            selected.get("todo_id") == "todo_portfolio_monitor_schedule"
            and lane.get("obligation") == "repair_monitor_schedule_metadata"
            and fallback.get("mode") == "monitor_schedule_metadata_repair"
            and action.get("must_attempt") is True
            and action.get("quiet_noop_allowed") is False
        ):
            raise ValueError(
                "capability fallback must select the monitor schedule repair"
            )
        if "todo_portfolio_monitor_schedule" not in str(action.get("primary_action")):
            raise ValueError("primary action must name the selected monitor repair")
    return contract


def _receipt_alignment(
    spec: _ScenarioSpec,
    receipt: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    if spec.actor_kind == "turn":
        fields = tuple(expected)
        mismatches = [
            f"source_mismatch:{field}"
            for field in fields
            if receipt.get(field) != expected[field]
        ]
        mismatches.extend(str(item) for item in receipt.get("safety_violations") or [])
    else:
        mismatches = []
        if receipt.get("next_action") != spec.expected_route:
            mismatches.append("next_action_mismatch")
        if receipt.get("source_aligned") is not True:
            mismatches.append("source_alignment_failed")
        mismatches.extend(str(item) for item in receipt.get("safety_violations") or [])
    return not mismatches, sorted(set(mismatches))


def _scenario_result(
    spec: _ScenarioSpec,
    packet: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    qualification_id: str,
    turn_actor: ModelBehaviorActor,
    onboarding_actor: OnboardingModelBehaviorActor,
) -> tuple[dict[str, Any], bool]:
    receipt_digests: list[str] = []
    observed_routes: list[str] = []
    failure_codes: list[str] = []
    actor_error = False
    for repeat_index in range(ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS):
        run_id = f"{qualification_id}:{spec.scenario_id}:r{repeat_index + 1}"
        try:
            if spec.actor_kind == "turn":
                receipt = run_model_behavior_qualification_arm(
                    packet,
                    qualification_id=run_id,
                    arm="full_packet",
                    actor=turn_actor,
                    semantic_contract_required=False,
                )
                observed_route = str(receipt.get("decision") or "")
            else:
                receipt = run_onboarding_model_behavior_phase(
                    packet,
                    qualification_id=run_id,
                    phase=str(spec.phase),
                    actor=onboarding_actor,
                )
                observed_route = str(receipt.get("next_action") or "")
        except (ValueError, RuntimeError) as exc:
            failure_codes.append(_actor_failure_code(exc))
            actor_error = True
            break
        aligned, mismatches = _receipt_alignment(spec, receipt, expected)
        receipt_digests.append(_digest(dict(receipt)))
        if observed_route not in observed_routes:
            observed_routes.append(observed_route)
        if not aligned:
            failure_codes.extend(mismatches)
    repeats_completed = len(receipt_digests)
    passed = bool(
        not failure_codes
        and repeats_completed == ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS
    )
    return (
        {
            "scenario_id": spec.scenario_id,
            "actor_kind": spec.actor_kind,
            "phase": spec.phase,
            "expected_route": spec.expected_route,
            "status": "passed" if passed else "failed",
            "repeats_required": ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS,
            "repeats_completed": repeats_completed,
            "observed_routes": observed_routes,
            "failure_codes": sorted(set(failure_codes)),
            "receipt_digests": receipt_digests,
        },
        actor_error,
    )


def run_actual_default_model_behavior_portfolio(
    scenario_packets: Mapping[str, Mapping[str, Any]],
    *,
    qualification_id: str,
    turn_actor: ModelBehaviorActor,
    onboarding_actor: OnboardingModelBehaviorActor,
) -> dict[str, Any]:
    """Run the fixed low-frequency one-arm portfolio with bounded receipts."""
    expected_ids = {spec.scenario_id for spec in _SCENARIOS}
    supplied_ids = set(scenario_packets)
    if supplied_ids != expected_ids:
        missing = sorted(expected_ids - supplied_ids)
        unknown = sorted(supplied_ids - expected_ids)
        raise ValueError(
            f"scenario packets must match the catalog; missing={missing}, unknown={unknown}"
        )

    catalog = actual_default_model_behavior_scenario_catalog()
    contracts = {
        spec.scenario_id: _scenario_contract(spec, scenario_packets[spec.scenario_id])
        for spec in _SCENARIOS
    }
    results: list[dict[str, Any]] = []
    actor_call_count = 0
    aborted = False
    for spec in _SCENARIOS:
        if aborted:
            results.append(
                {
                    "scenario_id": spec.scenario_id,
                    "actor_kind": spec.actor_kind,
                    "phase": spec.phase,
                    "expected_route": spec.expected_route,
                    "status": "not_run",
                    "repeats_required": ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS,
                    "repeats_completed": 0,
                    "observed_routes": [],
                    "failure_codes": ["portfolio_aborted_after_actor_error"],
                    "receipt_digests": [],
                }
            )
            continue
        result, actor_error = _scenario_result(
            spec,
            scenario_packets[spec.scenario_id],
            expected=contracts[spec.scenario_id],
            qualification_id=qualification_id,
            turn_actor=turn_actor,
            onboarding_actor=onboarding_actor,
        )
        actor_call_count += int(result["repeats_completed"])
        if actor_error:
            actor_call_count += 1
            aborted = True
        results.append(result)

    passed = all(result["status"] == "passed" for result in results)
    return {
        "schema_version": ACTUAL_DEFAULT_MODEL_BEHAVIOR_PORTFOLIO_SCHEMA_VERSION,
        "qualification_id": qualification_id,
        "topology": "actual_default_one_arm",
        "scenario_catalog_digest": _digest(catalog),
        "scenario_count": ACTUAL_DEFAULT_MODEL_BEHAVIOR_SCENARIO_COUNT,
        "actor_call_budget": (
            ACTUAL_DEFAULT_MODEL_BEHAVIOR_SCENARIO_COUNT
            * ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS
        ),
        "actor_call_count": actor_call_count,
        "qualification_passed": passed,
        "automatic_release_promotion_allowed": False,
        "scenarios": results,
        "boundary": {
            "tools_enabled": False,
            "raw_packets_persisted": False,
            "raw_model_responses_persisted": False,
            "automatic_retries": False,
        },
    }
