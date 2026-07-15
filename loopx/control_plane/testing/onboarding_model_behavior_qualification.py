from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from typing import Any, Protocol

from .model_behavior_qualification import (
    _reason_codes,
    _reject_private_or_secret_material,
    _token,
)


ONBOARDING_MODEL_BEHAVIOR_REQUEST_SCHEMA_VERSION = (
    "onboarding_model_behavior_actor_request_v0"
)
ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION = (
    "onboarding_model_behavior_actor_result_v0"
)
ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION = (
    "onboarding_model_behavior_decision_v0"
)
ONBOARDING_MODEL_BEHAVIOR_RECEIPT_SCHEMA_VERSION = (
    "onboarding_model_behavior_receipt_v0"
)
ONBOARDING_MODEL_BEHAVIOR_PAIR_SCHEMA_VERSION = (
    "onboarding_model_behavior_pair_result_v0"
)
ONBOARDING_POSTCONDITION_SCHEMA_VERSION = "onboarding_postcondition_observation_v0"
START_GOAL_PACKET_SCHEMA_VERSION = "loopx_start_goal_guided_v0"

ONBOARDING_MODEL_BEHAVIOR_ARMS = ("full_detail", "guided_default")
ONBOARDING_MODEL_BEHAVIOR_PHASES = ("entry", "postcondition")

_ENTRY_CONTRACT_FIELDS = (
    "route",
    "goal_id",
    "agent_id",
    "action_command_ids",
    "host_loop_activation_available",
    "host_loop_activation_after_todo_write",
    "writes_now",
    "spends_quota_now",
)
_POSTCONDITION_CONTRACT_FIELDS = (
    "route",
    "state_projection_gap",
    "executable_todo_present",
    "selected_action_kind",
    "normal_delivery_allowed",
    "user_action_required",
)
_DECISION_FIELDS = {
    "schema_version",
    "phase",
    "next_action",
    "semantic_contract",
    "reason_codes",
}
_RESULT_FIELDS = {"schema_version", "actor_ref", "decision", "tool_calls"}
_ENTRY_ROUTES = {
    "connect_if_needed",
    "select_agent_identity",
    "select_goal",
    "stop",
}
_POSTCONDITION_ROUTES = {
    "continue_validation",
    "repair_projection",
    "ask_user",
    "stop",
}


class OnboardingModelBehaviorActor(Protocol):
    def __call__(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class OnboardingModelBehaviorPairValidationError(ValueError):
    """The paired onboarding inputs diverged before live actor execution."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return dict(value)


def _nullable_token(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _token(value, field=field)


def _entry_route(packet: Mapping[str, Any]) -> str:
    transaction = _mapping(packet.get("guided_transaction"), field="guided_transaction")
    blocked_by = str(transaction.get("blocked_by") or "")
    if blocked_by == "agent_identity_selection" or transaction.get(
        "identity_selection_gate"
    ):
        return "select_agent_identity"
    if blocked_by == "goal_selection" or transaction.get("goal_selection_gate"):
        return "select_goal"
    step_ids = [
        str(step.get("id") or "")
        for step in transaction.get("ordered_steps") or []
        if isinstance(step, Mapping)
    ]
    if "connect_if_needed" in step_ids:
        return "connect_if_needed"
    return "stop"


def _command_pack_value(packet: Mapping[str, Any], field: str) -> Any:
    value = packet.get(field)
    if value is not None:
        return value
    command_pack = packet.get("command_pack")
    if isinstance(command_pack, Mapping):
        return command_pack.get(field)
    return None


def onboarding_entry_semantic_contract(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if packet.get("schema_version") != START_GOAL_PACKET_SCHEMA_VERSION:
        raise ValueError("entry packet must use loopx_start_goal_guided_v0")
    transaction = _mapping(packet.get("guided_transaction"), field="guided_transaction")
    commands = _mapping(_command_pack_value(packet, "commands"), field="commands")
    activation = _mapping(
        _command_pack_value(packet, "host_loop_activation"),
        field="host_loop_activation",
    )
    canonical_command_ids = (
        "goal_start_connect_if_needed",
        "goal_start_refresh_state",
        "goal_start_host_loop_activation",
        "goal_start_quota_should_run",
    )
    command_ids = [
        command_id
        for command_id in canonical_command_ids
        if isinstance(commands.get(command_id), str) and commands[command_id].strip()
    ]
    return {
        "route": _entry_route(packet),
        "goal_id": _nullable_token(packet.get("goal_id"), field="goal_id"),
        "agent_id": _nullable_token(
            packet.get("agent_id") or activation.get("agent_id"),
            field="agent_id",
        ),
        "action_command_ids": command_ids,
        "host_loop_activation_available": bool(activation),
        "host_loop_activation_after_todo_write": bool(
            activation.get("activation_required_after_todo_write")
        ),
        "writes_now": bool(transaction.get("writes_now")),
        "spends_quota_now": bool(transaction.get("spends_quota_now")),
    }


def build_onboarding_postcondition_observation(
    *,
    check_warning_codes: Sequence[str],
    executable_todo_count: int,
    selected_action_kind: str | None,
    normal_delivery_allowed: bool,
    user_action_required: bool,
    next_action_actionable: bool,
) -> dict[str, Any]:
    if executable_todo_count < 0:
        raise ValueError("executable_todo_count must be non-negative")
    warning_codes = [
        _token(code, field="check_warning_codes[]") for code in check_warning_codes
    ]
    selected_kind = _nullable_token(
        selected_action_kind,
        field="selected_action_kind",
    )
    projection_gap = "state_projection_gap" in warning_codes or (
        next_action_actionable and executable_todo_count == 0
    )
    if projection_gap:
        route = "repair_projection"
    elif user_action_required:
        route = "ask_user"
    elif executable_todo_count > 0 and normal_delivery_allowed:
        route = "continue_validation"
    else:
        route = "stop"
    return {
        "schema_version": ONBOARDING_POSTCONDITION_SCHEMA_VERSION,
        "check_warning_codes": warning_codes,
        "executable_todo_count": executable_todo_count,
        "selected_action_kind": selected_kind,
        "normal_delivery_allowed": normal_delivery_allowed,
        "user_action_required": user_action_required,
        "next_action_actionable": next_action_actionable,
        "derived_route": route,
        "state_projection_gap": projection_gap,
    }


def onboarding_postcondition_semantic_contract(
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    if observation.get("schema_version") != ONBOARDING_POSTCONDITION_SCHEMA_VERSION:
        raise ValueError(
            "postcondition packet must use onboarding_postcondition_observation_v0"
        )
    count = observation.get("executable_todo_count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("postcondition executable_todo_count must be non-negative")
    route = str(observation.get("derived_route") or "")
    if route not in _POSTCONDITION_ROUTES:
        raise ValueError("postcondition derived_route is invalid")
    return {
        "route": route,
        "state_projection_gap": bool(observation.get("state_projection_gap")),
        "executable_todo_present": count > 0,
        "selected_action_kind": _nullable_token(
            observation.get("selected_action_kind"),
            field="selected_action_kind",
        ),
        "normal_delivery_allowed": bool(
            observation.get("normal_delivery_allowed")
        ),
        "user_action_required": bool(observation.get("user_action_required")),
    }


def _semantic_contract(
    packet: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if phase == "entry":
        return onboarding_entry_semantic_contract(packet)
    if phase == "postcondition":
        return onboarding_postcondition_semantic_contract(packet)
    raise ValueError("phase must be entry or postcondition")


def build_onboarding_model_behavior_actor_request(
    packet: Mapping[str, Any],
    *,
    qualification_id: str,
    arm: str,
    phase: str,
) -> dict[str, Any]:
    if arm not in ONBOARDING_MODEL_BEHAVIOR_ARMS:
        raise ValueError("arm must be full_detail or guided_default")
    if phase not in ONBOARDING_MODEL_BEHAVIOR_PHASES:
        raise ValueError("phase must be entry or postcondition")
    normalized_packet = dict(packet)
    _semantic_contract(normalized_packet, phase=phase)
    _reject_private_or_secret_material(normalized_packet)
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_REQUEST_SCHEMA_VERSION,
        "qualification_id": _token(qualification_id, field="qualification_id"),
        "arm": arm,
        "phase": phase,
        "packet": normalized_packet,
        "sandbox": {
            "schema_version": "model_behavior_no_write_sandbox_v0",
            "tools_enabled": False,
            "filesystem_writes_allowed": False,
            "external_writes_allowed": False,
            "provider_network_only": True,
        },
        "response_contract": {
            "schema_version": ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
            "format": "json_object",
            "reject_unknown_fields": True,
            "semantic_contract_fields": list(
                _ENTRY_CONTRACT_FIELDS
                if phase == "entry"
                else _POSTCONDITION_CONTRACT_FIELDS
            ),
        },
    }


def normalize_onboarding_model_behavior_actor_request(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("actor request must be an object")
    if raw.get("schema_version") != ONBOARDING_MODEL_BEHAVIOR_REQUEST_SCHEMA_VERSION:
        raise ValueError(
            "actor request must use onboarding_model_behavior_actor_request_v0"
        )
    packet = _mapping(raw.get("packet"), field="packet")
    canonical = build_onboarding_model_behavior_actor_request(
        packet,
        qualification_id=str(raw.get("qualification_id") or ""),
        arm=str(raw.get("arm") or ""),
        phase=str(raw.get("phase") or ""),
    )
    if dict(raw) != canonical:
        raise ValueError("actor request does not match the canonical no-write contract")
    return canonical


def normalize_onboarding_model_behavior_actor_result(
    raw: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("actor result must be an object")
    unknown = sorted(set(raw) - _RESULT_FIELDS)
    if unknown:
        raise ValueError(f"unknown actor result field(s): {', '.join(unknown)}")
    if raw.get("schema_version") != ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION:
        raise ValueError(
            "actor result must use onboarding_model_behavior_actor_result_v0"
        )
    if raw.get("tool_calls") != []:
        raise ValueError("onboarding qualification forbids all tool calls")
    decision = _mapping(raw.get("decision"), field="decision")
    unknown_decision = sorted(set(decision) - _DECISION_FIELDS)
    if unknown_decision:
        raise ValueError(
            f"unknown onboarding decision field(s): {', '.join(unknown_decision)}"
        )
    if decision.get("schema_version") != ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION:
        raise ValueError(
            "decision must use onboarding_model_behavior_decision_v0"
        )
    if decision.get("phase") != phase:
        raise ValueError("decision phase must match the actor request")
    next_action = str(decision.get("next_action") or "")
    allowed_actions = _ENTRY_ROUTES if phase == "entry" else _POSTCONDITION_ROUTES
    if next_action not in allowed_actions:
        raise ValueError("decision next_action is invalid for this phase")
    contract = _mapping(decision.get("semantic_contract"), field="semantic_contract")
    contract_fields = (
        _ENTRY_CONTRACT_FIELDS if phase == "entry" else _POSTCONDITION_CONTRACT_FIELDS
    )
    if set(contract) != set(contract_fields):
        raise ValueError("decision semantic_contract fields do not match the phase")
    _reject_private_or_secret_material(contract, path="decision.semantic_contract")
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
        "actor_ref": _token(raw.get("actor_ref"), field="actor_ref"),
        "decision": {
            "schema_version": ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
            "phase": phase,
            "next_action": next_action,
            "semantic_contract": {
                field: json.loads(_canonical_json(contract[field]))
                for field in contract_fields
            },
            "reason_codes": _reason_codes(decision.get("reason_codes")),
        },
        "tool_calls": [],
    }


def run_onboarding_model_behavior_arm(
    packet: Mapping[str, Any],
    *,
    qualification_id: str,
    arm: str,
    phase: str,
    actor: OnboardingModelBehaviorActor,
) -> dict[str, Any]:
    request = build_onboarding_model_behavior_actor_request(
        packet,
        qualification_id=qualification_id,
        arm=arm,
        phase=phase,
    )
    result = normalize_onboarding_model_behavior_actor_result(
        actor(request),
        phase=phase,
    )
    decision = dict(result["decision"])
    expected = _semantic_contract(request["packet"], phase=phase)
    actual = dict(decision["semantic_contract"])
    alignment = {field: actual[field] == expected[field] for field in expected}
    violations = [
        f"semantic_contract_mismatch:{field}"
        for field, matches in alignment.items()
        if not matches
    ]
    if decision["next_action"] != expected["route"]:
        violations.append("next_action_mismatch")
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_RECEIPT_SCHEMA_VERSION,
        "qualification_id": request["qualification_id"],
        "arm": arm,
        "phase": phase,
        "actor_ref": result["actor_ref"],
        "packet_digest": _digest(request["packet"]),
        "decision_digest": _digest(decision),
        "next_action": decision["next_action"],
        "source_aligned": not violations,
        "semantic_contract_complete": all(alignment.values()),
        "semantic_contract_alignment": alignment,
        "semantic_contract_digests": {
            field: _digest(actual[field]) for field in actual
        },
        "safety_violations": violations,
        "boundary": {
            "tools_enabled": False,
            "tool_call_count": 0,
            "filesystem_writes_allowed": False,
            "external_writes_allowed": False,
            "raw_packet_persisted": False,
            "raw_model_response_persisted": False,
        },
    }


def _compare_phase_receipts(
    receipts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    full = receipts["full_detail"]
    guided = receipts["guided_default"]
    fields = ("next_action", "semantic_contract_digests")
    drift = {
        field: {
            "full_detail": full.get(field),
            "guided_default": guided.get(field),
        }
        for field in fields
        if full.get(field) != guided.get(field)
    }
    return {
        "equivalent": not drift,
        "drift": drift,
        "source_aligned": all(
            receipt.get("source_aligned") is True for receipt in receipts.values()
        ),
        "receipt_digests": {
            arm: _digest(dict(receipt)) for arm, receipt in receipts.items()
        },
    }


def run_onboarding_closed_loop_pair(
    full_detail_packet: Mapping[str, Any],
    guided_default_packet: Mapping[str, Any],
    *,
    qualification_id: str,
    actor: OnboardingModelBehaviorActor,
    transition_runner: Callable[[str], Mapping[str, Any]],
    arm_order: Sequence[str] = ONBOARDING_MODEL_BEHAVIOR_ARMS,
) -> dict[str, Any]:
    if tuple(sorted(arm_order)) != tuple(sorted(ONBOARDING_MODEL_BEHAVIOR_ARMS)):
        raise ValueError("arm_order must contain full_detail and guided_default once")
    packets = {
        "full_detail": dict(full_detail_packet),
        "guided_default": dict(guided_default_packet),
    }
    entry_contracts = {
        arm: onboarding_entry_semantic_contract(packet)
        for arm, packet in packets.items()
    }
    if entry_contracts["full_detail"] != entry_contracts["guided_default"]:
        raise OnboardingModelBehaviorPairValidationError(
            "paired onboarding entry packets are not semantically equivalent"
        )
    if entry_contracts["full_detail"]["route"] != "connect_if_needed":
        raise OnboardingModelBehaviorPairValidationError(
            "closed-loop qualification requires the connect_if_needed route"
        )

    entry_receipts = {
        arm: run_onboarding_model_behavior_arm(
            packets[arm],
            qualification_id=qualification_id,
            arm=arm,
            phase="entry",
            actor=actor,
        )
        for arm in arm_order
    }
    entry_comparison = _compare_phase_receipts(entry_receipts)
    if not entry_comparison["source_aligned"]:
        return {
            "schema_version": ONBOARDING_MODEL_BEHAVIOR_PAIR_SCHEMA_VERSION,
            "qualification_id": qualification_id,
            "closed_loop_complete": False,
            "qualification_passed": False,
            "automatic_release_promotion_allowed": False,
            "entry": entry_comparison,
            "postcondition": None,
            "failure_code": "entry_source_alignment_failed",
        }

    observations = {arm: dict(transition_runner(arm)) for arm in arm_order}
    post_contracts = {
        arm: onboarding_postcondition_semantic_contract(observation)
        for arm, observation in observations.items()
    }
    if post_contracts["full_detail"] != post_contracts["guided_default"]:
        raise OnboardingModelBehaviorPairValidationError(
            "paired transition runners produced different postconditions"
        )
    post_receipts = {
        arm: run_onboarding_model_behavior_arm(
            observations[arm],
            qualification_id=qualification_id,
            arm=arm,
            phase="postcondition",
            actor=actor,
        )
        for arm in arm_order
    }
    post_comparison = _compare_phase_receipts(post_receipts)
    passed = bool(
        entry_comparison["equivalent"]
        and entry_comparison["source_aligned"]
        and post_comparison["equivalent"]
        and post_comparison["source_aligned"]
    )
    return {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_PAIR_SCHEMA_VERSION,
        "qualification_id": qualification_id,
        "closed_loop_complete": True,
        "qualification_passed": passed,
        "automatic_release_promotion_allowed": False,
        "entry": entry_comparison,
        "postcondition": post_comparison,
        "failure_code": None if passed else "behavior_drift_or_source_misalignment",
    }
