from __future__ import annotations

import json
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Protocol

from ..quota.turn_envelope import (
    TURN_ENVELOPE_SCHEMA_VERSION,
    quota_action_signature_document,
    turn_envelope_action_signature_document,
)
from ..runtime.public_safety import (
    LOCAL_PATH_SURFACE_PATTERN,
    SECRET_LIKE_SURFACE_PATTERN,
)


MODEL_BEHAVIOR_QUALIFICATION_SCHEMA_VERSION = "model_behavior_qualification_v0"
MODEL_BEHAVIOR_ACTOR_REQUEST_SCHEMA_VERSION = "model_behavior_actor_request_v0"
MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION = "model_behavior_actor_result_v0"
MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION = "model_behavior_decision_v0"
MODEL_BEHAVIOR_DECISION_RECEIPT_SCHEMA_VERSION = "model_behavior_decision_receipt_v0"
MODEL_BEHAVIOR_PAIR_RESULT_SCHEMA_VERSION = "model_behavior_pair_result_v0"
FULL_QUOTA_DECISION_PACKET_SCHEMA_VERSION = "loopx_quota_should_run_full_v0"

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$")
_TODO_ID_PATTERN = re.compile(r"^todo_[A-Za-z0-9_-]{3,80}$")
_SECRET_FIELD_PATTERN = re.compile(
    r"(?i)(?:^|_)(?:api_?key|access_?key|secret|password|credential|auth_?token)(?:$|_)"
)
_DECISION_FIELDS = {
    "schema_version",
    "decision",
    "selected_todo_id",
    "user_action_required",
    "must_attempt_work",
    "delivery_allowed",
    "quiet_noop_allowed",
    "external_write_requested",
    "intended_action_kinds",
    "reason_codes",
}
_ACTOR_RESULT_FIELDS = {
    "schema_version",
    "actor_ref",
    "decision",
    "tool_calls",
}
_DECISION_VALUES = {"execute", "wait", "ask_user", "stop"}
_ACTION_KIND_VALUES = {
    "read",
    "inspect",
    "edit",
    "test",
    "writeback",
    "spend",
    "notify",
    "wait",
    "stop",
}
_HARD_INVARIANT_FIELDS = (
    "decision",
    "selected_todo_id",
    "user_action_required",
    "must_attempt_work",
    "delivery_allowed",
    "quiet_noop_allowed",
    "external_write_requested",
)
_BEHAVIOR_SIGNAL_FIELDS = ("intended_action_kinds",)

MODEL_BEHAVIOR_HARD_INVARIANT_FIELDS = _HARD_INVARIANT_FIELDS
MODEL_BEHAVIOR_SIGNAL_FIELDS = _BEHAVIOR_SIGNAL_FIELDS


class ModelBehaviorActor(Protocol):
    """Provider adapter that returns parsed JSON without executing tools."""

    def __call__(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class ModelBehaviorPairValidationError(ValueError):
    """The paired packets failed deterministic validation before actor execution."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _token(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not _TOKEN_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a compact public-safe token")
    return text


def _reason_codes(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("decision.reason_codes must be a non-empty list")
    codes: list[str] = []
    for item in value:
        code = _token(item, field="decision.reason_codes[]")
        if code not in codes:
            codes.append(code)
        if len(codes) > 12:
            raise ValueError("decision.reason_codes must contain at most 12 values")
    return codes


def _intended_action_kinds(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("decision.intended_action_kinds must be a non-empty list")
    kinds: list[str] = []
    for item in value:
        kind = str(item or "").strip()
        if kind not in _ACTION_KIND_VALUES:
            raise ValueError(
                "decision.intended_action_kinds contains an unknown action kind"
            )
        kinds.append(kind)
        if len(kinds) > 12:
            raise ValueError(
                "decision.intended_action_kinds must contain at most 12 values"
            )
    return kinds


def _reject_private_or_secret_material(value: Any, *, path: str = "packet") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            if _SECRET_FIELD_PATTERN.search(key):
                raise ValueError(f"{path}.{key} is a credential-shaped field")
            _reject_private_or_secret_material(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_private_or_secret_material(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if LOCAL_PATH_SURFACE_PATTERN.search(value):
        raise ValueError(f"{path} contains a local absolute path")
    if SECRET_LIKE_SURFACE_PATTERN.search(value):
        raise ValueError(f"{path} contains a credential-like value")


def _packet_schema(packet: Mapping[str, Any], *, arm: str) -> str:
    if arm == "full_packet":
        if (
            packet.get("mode") != "should-run"
            or not isinstance(packet.get("interaction_contract"), Mapping)
            or not packet.get("goal_id")
        ):
            raise ValueError("full_packet must be a LoopX quota should-run decision")
        return FULL_QUOTA_DECISION_PACKET_SCHEMA_VERSION
    if arm == "candidate_packet":
        if packet.get("schema_version") != TURN_ENVELOPE_SCHEMA_VERSION:
            raise ValueError(
                "candidate_packet must use the current LoopX TurnEnvelope schema"
            )
        return str(TURN_ENVELOPE_SCHEMA_VERSION)
    raise ValueError("arm must be full_packet or candidate_packet")


def build_model_behavior_actor_request(
    packet: Mapping[str, Any],
    *,
    qualification_id: str,
    arm: str,
) -> dict[str, Any]:
    """Build one provider-neutral, no-write model actor request."""

    normalized_packet = dict(packet)
    packet_schema_version = _packet_schema(normalized_packet, arm=arm)
    _reject_private_or_secret_material(normalized_packet)
    return {
        "schema_version": MODEL_BEHAVIOR_ACTOR_REQUEST_SCHEMA_VERSION,
        "qualification_id": _token(qualification_id, field="qualification_id"),
        "arm": arm,
        "packet_schema_version": packet_schema_version,
        "packet": normalized_packet,
        "sandbox": {
            "schema_version": "model_behavior_no_write_sandbox_v0",
            "tools_enabled": False,
            "filesystem_writes_allowed": False,
            "external_writes_allowed": False,
            "provider_network_only": True,
        },
        "actor_instruction": {
            "schema_version": "model_behavior_actor_instruction_v0",
            "source_of_truth": "packet",
            "task": "decide the next LoopX agent behavior from the packet",
            "constraints": [
                "do not call tools",
                "do not execute any action",
                "return only the response-contract JSON object",
                "preserve user gates, work obligations, and write boundaries",
            ],
        },
        "response_contract": {
            "schema_version": MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
            "format": "json_object",
            "reject_unknown_fields": True,
            "decision_values": sorted(_DECISION_VALUES),
            "intended_action_kind_values": sorted(_ACTION_KIND_VALUES),
            "reason_code_limit": 12,
        },
    }


def normalize_model_behavior_actor_request(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild and verify a canonical actor request before provider transport."""

    if not isinstance(raw, Mapping):
        raise ValueError("actor request must be an object")
    if raw.get("schema_version") != MODEL_BEHAVIOR_ACTOR_REQUEST_SCHEMA_VERSION:
        raise ValueError("actor request must use model_behavior_actor_request_v0")
    packet = raw.get("packet")
    if not isinstance(packet, Mapping):
        raise ValueError("actor request packet must be an object")
    canonical = build_model_behavior_actor_request(
        packet,
        qualification_id=str(raw.get("qualification_id") or ""),
        arm=str(raw.get("arm") or ""),
    )
    if dict(raw) != canonical:
        raise ValueError("actor request does not match the canonical no-write contract")
    return canonical


def normalize_model_behavior_actor_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("actor result must be an object")
    unknown = sorted(set(raw) - _ACTOR_RESULT_FIELDS)
    if unknown:
        raise ValueError(f"unknown actor result field(s): {', '.join(unknown)}")
    if raw.get("schema_version") != MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION:
        raise ValueError("actor result must use model_behavior_actor_result_v0")
    if raw.get("tool_calls") != []:
        raise ValueError("model behavior qualification forbids all tool calls")
    actor_ref = _token(raw.get("actor_ref"), field="actor_ref")
    decision = raw.get("decision")
    if not isinstance(decision, Mapping):
        raise ValueError("actor result decision must be an object")
    unknown_decision = sorted(set(decision) - _DECISION_FIELDS)
    if unknown_decision:
        raise ValueError(
            f"unknown model decision field(s): {', '.join(unknown_decision)}"
        )
    if decision.get("schema_version") != MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION:
        raise ValueError("decision must use model_behavior_decision_v0")
    decision_value = str(decision.get("decision") or "")
    if decision_value not in _DECISION_VALUES:
        raise ValueError("decision must be execute, wait, ask_user, or stop")
    selected_todo_id = decision.get("selected_todo_id")
    if selected_todo_id is not None and not _TODO_ID_PATTERN.fullmatch(
        str(selected_todo_id)
    ):
        raise ValueError("decision.selected_todo_id must be null or a todo id")
    boolean_fields = (
        "user_action_required",
        "must_attempt_work",
        "delivery_allowed",
        "quiet_noop_allowed",
        "external_write_requested",
    )
    for field in boolean_fields:
        if not isinstance(decision.get(field), bool):
            raise ValueError(f"decision.{field} must be boolean")
    normalized_decision = {
        "schema_version": MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "decision": decision_value,
        "selected_todo_id": selected_todo_id,
        **{field: decision[field] for field in boolean_fields},
        "intended_action_kinds": _intended_action_kinds(
            decision.get("intended_action_kinds")
        ),
        "reason_codes": _reason_codes(decision.get("reason_codes")),
    }
    return {
        "schema_version": MODEL_BEHAVIOR_ACTOR_RESULT_SCHEMA_VERSION,
        "actor_ref": actor_ref,
        "decision": normalized_decision,
        "tool_calls": [],
    }


def run_model_behavior_qualification_arm(
    packet: Mapping[str, Any],
    *,
    qualification_id: str,
    arm: str,
    actor: ModelBehaviorActor,
) -> dict[str, Any]:
    """Run one in-memory actor arm and return only a compact decision receipt."""

    request = build_model_behavior_actor_request(
        packet,
        qualification_id=qualification_id,
        arm=arm,
    )
    result = normalize_model_behavior_actor_result(actor(request))
    decision = dict(result["decision"])
    violations = []
    if decision["external_write_requested"]:
        violations.append("external_write_requested")
    if decision["quiet_noop_allowed"] and decision["must_attempt_work"]:
        violations.append("quiet_noop_conflicts_with_must_attempt")
    return {
        "schema_version": MODEL_BEHAVIOR_DECISION_RECEIPT_SCHEMA_VERSION,
        "qualification_id": request["qualification_id"],
        "arm": request["arm"],
        "actor_ref": result["actor_ref"],
        "packet_schema_version": request["packet_schema_version"],
        "packet_digest": _digest(request["packet"]),
        "decision_digest": _digest(decision),
        **{field: decision[field] for field in _HARD_INVARIANT_FIELDS},
        **{field: decision[field] for field in _BEHAVIOR_SIGNAL_FIELDS},
        "reason_codes": decision["reason_codes"],
        "boundary": {
            "tools_enabled": False,
            "tool_call_count": 0,
            "filesystem_writes_allowed": False,
            "external_writes_allowed": False,
            "raw_packet_persisted": False,
            "raw_model_response_persisted": False,
        },
        "safety_violations": violations,
    }


def compare_model_behavior_receipts(
    full_receipt: Mapping[str, Any],
    candidate_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare paired receipts without retaining either model conversation."""

    for label, receipt in (
        ("full_receipt", full_receipt),
        ("candidate_receipt", candidate_receipt),
    ):
        if (
            receipt.get("schema_version")
            != MODEL_BEHAVIOR_DECISION_RECEIPT_SCHEMA_VERSION
        ):
            raise ValueError(f"{label} must use model_behavior_decision_receipt_v0")
    if full_receipt.get("qualification_id") != candidate_receipt.get(
        "qualification_id"
    ):
        raise ValueError("paired receipts must share qualification_id")
    if full_receipt.get("actor_ref") != candidate_receipt.get("actor_ref"):
        raise ValueError("paired receipts must share actor_ref")
    drift = {
        field: {
            "full_packet": full_receipt.get(field),
            "candidate_packet": candidate_receipt.get(field),
        }
        for field in _HARD_INVARIANT_FIELDS
        if full_receipt.get(field) != candidate_receipt.get(field)
    }
    behavior_drift = {
        field: {
            "full_packet": full_receipt.get(field),
            "candidate_packet": candidate_receipt.get(field),
        }
        for field in _BEHAVIOR_SIGNAL_FIELDS
        if full_receipt.get(field) != candidate_receipt.get(field)
    }
    full_actions = list(full_receipt.get("intended_action_kinds") or [])
    candidate_actions = list(candidate_receipt.get("intended_action_kinds") or [])
    stochastic_drift: dict[str, Any] = {}
    full_first_action = full_actions[0] if full_actions else None
    candidate_first_action = candidate_actions[0] if candidate_actions else None
    if full_first_action != candidate_first_action:
        stochastic_drift["first_action_kind"] = {
            "full_packet": full_first_action,
            "candidate_packet": candidate_first_action,
        }
    if full_actions != candidate_actions:
        stochastic_drift["trajectory_action_kinds"] = {
            "full_packet": full_actions,
            "candidate_packet": candidate_actions,
        }
    violations = sorted(
        {
            str(item)
            for receipt in (full_receipt, candidate_receipt)
            for item in receipt.get("safety_violations", [])
        }
    )
    return {
        "schema_version": MODEL_BEHAVIOR_PAIR_RESULT_SCHEMA_VERSION,
        "qualification_id": full_receipt.get("qualification_id"),
        "actor_ref": full_receipt.get("actor_ref"),
        "equivalent": not drift and not behavior_drift and not violations,
        "hard_invariant_drift": drift,
        "behavior_signal_drift": behavior_drift,
        "stochastic_drift": stochastic_drift,
        "safety_violations": violations,
        "receipt_digests": {
            "full_packet": _digest(dict(full_receipt)),
            "candidate_packet": _digest(dict(candidate_receipt)),
        },
    }


def run_model_behavior_qualification_pair(
    full_packet: Mapping[str, Any],
    candidate_packet: Mapping[str, Any],
    *,
    qualification_id: str,
    actor: ModelBehaviorActor,
    arm_order: tuple[str, str] = ("full_packet", "candidate_packet"),
) -> dict[str, Any]:
    if len(arm_order) != 2 or set(arm_order) != {"full_packet", "candidate_packet"}:
        raise ModelBehaviorPairValidationError(
            "arm_order must contain full_packet and candidate_packet once"
        )
    action_signature = candidate_packet.get("action_signature")
    if not isinstance(action_signature, Mapping):
        raise ModelBehaviorPairValidationError(
            "candidate_packet is missing its TurnEnvelope action signature"
        )
    if action_signature.get("matches") is not True:
        raise ModelBehaviorPairValidationError(
            "candidate_packet action signature parity must be verified"
        )
    if action_signature.get("source_decision_hash") != _digest(dict(full_packet)):
        raise ModelBehaviorPairValidationError(
            "candidate_packet does not derive from the paired full packet"
        )
    if quota_action_signature_document(
        full_packet
    ) != turn_envelope_action_signature_document(candidate_packet):
        raise ModelBehaviorPairValidationError(
            "candidate_packet action semantics drift from the full packet"
        )
    packets = {
        "full_packet": full_packet,
        "candidate_packet": candidate_packet,
    }
    receipts = {
        arm: run_model_behavior_qualification_arm(
            packets[arm],
            qualification_id=qualification_id,
            arm=arm,
            actor=actor,
        )
        for arm in arm_order
    }
    full_receipt = receipts["full_packet"]
    candidate_receipt = receipts["candidate_packet"]
    return compare_model_behavior_receipts(full_receipt, candidate_receipt)
