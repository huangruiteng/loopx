from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from ..quota.turn_envelope import (
    TURN_ENVELOPE_SCHEMA_VERSION,
    turn_envelope_action_signature_document,
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


@dataclass(frozen=True)
class _ScenarioSpec:
    scenario_id: str
    actor_kind: str
    phase: str | None
    expected_route: str


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
                "repeat_policy": {
                    "attempts": ACTUAL_DEFAULT_MODEL_BEHAVIOR_REPEAT_ATTEMPTS,
                    "pass_condition": "all_attempts_source_aligned",
                    "automatic_retry_on_actor_error": False,
                },
            }
            for spec in _SCENARIOS
        ],
    }


def _turn_expected_contract(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("schema_version") != TURN_ENVELOPE_SCHEMA_VERSION:
        raise ValueError("turn scenarios require the current TurnEnvelope schema")
    signature = turn_envelope_action_signature_document(packet)
    action = dict(signature.get("action") or {})
    user = dict(signature.get("user") or {})
    selected_todo = dict(action.get("selected_todo") or {})
    user_action_required = bool(user.get("action_required"))
    must_attempt = bool(action.get("must_attempt"))
    delivery_allowed = bool(action.get("delivery_allowed"))
    quiet_noop_allowed = bool(action.get("quiet_noop_allowed"))
    if user_action_required:
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
    if user_action_required:
        contract["intended_action_kinds"] = ["notify", "wait"]
    return contract


def _scenario_contract(
    spec: _ScenarioSpec,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if spec.actor_kind == "turn":
        action_signature = dict(packet.get("action_signature") or {})
        if action_signature.get("matches") is not True:
            raise ValueError("turn scenario action signature parity is not verified")
        signature_digest = _digest(turn_envelope_action_signature_document(packet))
        if not (
            action_signature.get("source_hash")
            == action_signature.get("envelope_hash")
            == signature_digest
        ):
            raise ValueError("turn scenario action signature does not match its packet")
        build_model_behavior_actor_request(
            packet,
            qualification_id=f"portfolio-preflight-{spec.scenario_id}",
            arm="candidate_packet",
            semantic_contract_required=True,
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
            arm="candidate_packet",
        )["peer_route"]
        if not peer_route.get("agent_id"):
            raise ValueError("peer-agent scenario requires a selected agent identity")
        if peer_route.get("selected_todo_claimed_by") != peer_route.get("agent_id"):
            raise ValueError("peer-agent scenario must route work to the selected peer")
        if spec.scenario_id == "turn_same_agent_continuation":
            if peer_route.get("continuation_policy") != "same_agent_non_delivery":
                raise ValueError(
                    "same-agent scenario requires same_agent_non_delivery"
                )
            if peer_route.get("same_agent_continuation") is not True:
                raise ValueError("same-agent scenario must preserve the completing peer")
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
        if receipt.get("semantic_contract_complete") is not True:
            mismatches.append("semantic_contract_incomplete")
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
                    arm="candidate_packet",
                    actor=turn_actor,
                    semantic_contract_required=True,
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
