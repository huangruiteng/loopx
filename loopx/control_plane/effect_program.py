from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Generic, TypeVar

from .effect_runtime import EffectRuntimeRejected, effect_runtime_result


# Identity remains stable while the plan and receipt versions advance with the
# typed terminal-closeout step shared by quota and Turn adapters.
SETTLEMENT_IDENTITY_SCHEMA_VERSION = "quota_settlement_identity_v0"
SCOPED_SETTLEMENT_IDENTITY_SCHEMA_VERSION = "quota_settlement_identity_v1"
SETTLEMENT_PLAN_SCHEMA_VERSION = "quota_settlement_plan_v1"
SETTLEMENT_RECEIPT_SCHEMA_VERSION = "quota_settlement_receipt_v1"


@dataclass(frozen=True)
class EffectRequest:
    kind: str
    source: str
    goal_id: str | None = None
    agent_id: str | None = None
    capabilities: tuple[str, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectInterpretation:
    route: str
    obligation: str
    interaction_mode: str
    capability_action: str | None = None
    cadence_class: str | None = None


@dataclass(frozen=True)
class EffectObservation:
    decision: str
    should_run: bool
    effective_action: str
    recommended_action: str
    protocol_summary: str | None = None


@dataclass(frozen=True)
class EffectNext:
    cli_actions: tuple[str, ...] = ()
    execution_mode: str | None = None
    scheduler_action: str | None = None
    cadence_class: str | None = None
    ack_cli_args: tuple[str, ...] = ()
    failure_cli_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectTurn:
    request: EffectRequest
    interpretation: EffectInterpretation
    observation: EffectObservation
    next_effect: EffectNext


@dataclass(frozen=True)
class EffectStep:
    step_id: str | None = None
    kind: str | None = None
    command: str | None = None
    purpose: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectProgram:
    steps: tuple[EffectStep, ...] = ()
    execution_mode: str | None = None


_TURN_TRANSACTION_CONTRACT_PATH = Path(__file__).with_name(
    "turn_transaction_contract.json"
)
_TURN_TRANSACTION_CONTRACT = json.loads(
    _TURN_TRANSACTION_CONTRACT_PATH.read_text(encoding="utf-8")
)
TURN_TRANSACTION_PHASES = tuple(_TURN_TRANSACTION_CONTRACT["phases"])


class SettlementStepKind(StrEnum):
    VALIDATION = "validation"
    DURABLE_WRITEBACK = "durable_writeback"
    QUOTA_SPEND = "quota_spend"
    TERMINAL_CLOSEOUT = "terminal_closeout"


class SettlementBindingKind(StrEnum):
    TODO = "todo"
    AUTONOMOUS_REPLAN = "autonomous_replan"
    UNBOUND = "unbound"


class SettlementFailureKind(StrEnum):
    INVALID_IDENTITY = "invalid_identity"
    RECEIPT_MISSING = "receipt_missing"
    IDENTITY_MISMATCH = "identity_mismatch"
    WRITEBACK_MISSING = "writeback_missing"
    WRITEBACK_REJECTED = "writeback_rejected"
    QUOTA_SPEND_REJECTED = "quota_spend_rejected"
    TERMINAL_CLOSEOUT_REJECTED = "terminal_closeout_rejected"
    CANCELLED = "cancelled"
    PERMISSION_DENIED = "permission_denied"
    BUDGET_REJECTED = "budget_rejected"
    EFFECT_OUTCOME_UNKNOWN = "effect_outcome_unknown"


@lru_cache(maxsize=4096)
def _settlement_identity_full(
    goal_id: str,
    agent_id: str,
    todo_id: str | None,
    turn_instance_id: str,
    replan_obligation_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        result = effect_runtime_result(
            "settlement.identity_full",
            {
                "goal_id": goal_id,
                "agent_id": agent_id,
                "todo_id": todo_id,
                "turn_instance_id": turn_instance_id,
                "replan_obligation_id": replan_obligation_id,
            },
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping):
        raise RuntimeError("TypeScript settlement identity shape mismatch")
    identity = result.get("identity")
    payload = result.get("payload")
    if not isinstance(identity, Mapping) or not isinstance(payload, Mapping):
        raise RuntimeError("TypeScript settlement identity shape mismatch")
    return dict(identity), dict(payload)


@dataclass(frozen=True, slots=True)
class SettlementIdentity:
    goal_id: str
    agent_id: str
    todo_id: str | None
    turn_instance_id: str
    replan_obligation_id: str | None = None
    _runtime_identity: Mapping[str, Any] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _runtime_payload: Mapping[str, Any] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        identity, payload = _settlement_identity_full(
            self.goal_id,
            self.agent_id,
            self.todo_id,
            self.turn_instance_id,
            self.replan_obligation_id,
        )
        object.__setattr__(self, "todo_id", identity.get("todo_id"))
        object.__setattr__(
            self, "replan_obligation_id", identity.get("replan_obligation_id")
        )
        object.__setattr__(self, "_runtime_identity", identity)
        object.__setattr__(self, "_runtime_payload", payload)

    @property
    def binding_kind(self) -> SettlementBindingKind:
        return SettlementBindingKind(str(self._runtime_identity["binding_kind"]))

    @property
    def binding_id(self) -> str:
        return str(self._runtime_identity["binding_id"])

    @property
    def effect_id(self) -> str:
        return str(self._runtime_identity["effect_id"])

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in self._runtime_payload.items()}


@dataclass(frozen=True, slots=True)
class SettlementReceipt:
    step_kind: SettlementStepKind
    status: str
    effect_id: str
    source_ref: str | None = None

    def as_dict(self) -> dict[str, str]:
        receipt = {
            "schema_version": SETTLEMENT_RECEIPT_SCHEMA_VERSION,
            "step_kind": self.step_kind.value,
            "status": self.status,
            "effect_id": self.effect_id,
        }
        if self.source_ref:
            receipt["source_ref"] = self.source_ref
        return receipt


@dataclass(frozen=True, slots=True)
class SettlementFailure:
    kind: SettlementFailureKind
    step_kind: SettlementStepKind
    reason: str
    details: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind.value,
            "step_kind": self.step_kind.value,
            "reason": self.reason,
        }
        if self.details:
            result["details"] = dict(self.details)
        return result


def _runtime_receipt(receipt: SettlementReceipt) -> dict[str, Any]:
    return {
        "step_kind": receipt.step_kind.value,
        "status": receipt.status,
        "effect_id": receipt.effect_id,
        **({"source_ref": receipt.source_ref} if receipt.source_ref else {}),
    }


def _runtime_failure(failure: SettlementFailure | None) -> dict[str, Any] | None:
    if failure is None:
        return None
    return {
        "kind": failure.kind.value,
        "step_kind": failure.step_kind.value,
        "reason": failure.reason,
        **({"details": dict(failure.details)} if failure.details else {}),
    }


def _runtime_result(result: SettlementResult[Any]) -> dict[str, Any]:
    return {
        "value": None,
        "receipts": [_runtime_receipt(receipt) for receipt in result.receipts],
        "failure": _runtime_failure(result.failure),
    }


def _runtime_result_metadata(
    payload: Any,
) -> tuple[tuple[SettlementReceipt, ...], SettlementFailure | None]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("TypeScript settlement result shape mismatch")
    receipts_value = payload.get("receipts")
    receipts = (
        tuple(
            SettlementReceipt(
                step_kind=SettlementStepKind(str(receipt["step_kind"])),
                status=str(receipt["status"]),
                effect_id=str(receipt["effect_id"]),
                source_ref=str(receipt.get("source_ref") or "") or None,
            )
            for receipt in receipts_value
            if isinstance(receipt, Mapping)
        )
        if isinstance(receipts_value, list)
        else ()
    )
    failure_value = payload.get("failure")
    failure = None
    if isinstance(failure_value, Mapping):
        details = failure_value.get("details")
        failure = SettlementFailure(
            kind=SettlementFailureKind(str(failure_value["kind"])),
            step_kind=SettlementStepKind(str(failure_value["step_kind"])),
            reason=str(failure_value["reason"]),
            details=dict(details) if isinstance(details, Mapping) else None,
        )
    return receipts, failure


T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class SettlementResult(Generic[T]):
    value: T | None
    receipts: tuple[SettlementReceipt, ...] = ()
    failure: SettlementFailure | None = None
    _runtime_payload: Mapping[str, Any] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @classmethod
    def pure(
        cls,
        value: T,
        *,
        receipts: tuple[SettlementReceipt, ...] = (),
    ) -> SettlementResult[T]:
        return cls(value=value, receipts=receipts)

    @classmethod
    def failed(
        cls,
        *,
        kind: SettlementFailureKind,
        step_kind: SettlementStepKind,
        reason: str,
        receipts: tuple[SettlementReceipt, ...] = (),
        details: Mapping[str, Any] | None = None,
    ) -> SettlementResult[T]:
        return cls(
            value=None,
            receipts=receipts,
            failure=SettlementFailure(
                kind=kind,
                step_kind=step_kind,
                reason=reason,
                details=details,
            ),
        )

    def bind(self, step: Callable[[T], SettlementResult[U]]) -> SettlementResult[U]:
        gate = effect_runtime_result(
            "settlement.bind_gate",
            {"result": _runtime_result(self)},
        )
        if not isinstance(gate, Mapping) or not isinstance(gate.get("execute"), bool):
            raise RuntimeError("TypeScript settlement bind gate shape mismatch")
        if gate["execute"] is False:
            return SettlementResult(
                value=None,
                receipts=self.receipts,
                failure=self.failure,
            )
        next_result = step(self.value)  # type: ignore[arg-type]
        reduced = effect_runtime_result(
            "settlement.bind_reduce",
            {
                "current": _runtime_result(self),
                "next": _runtime_result(next_result),
            },
        )
        receipts, failure = _runtime_result_metadata(reduced)
        return SettlementResult(
            value=next_result.value,
            receipts=receipts,
            failure=failure,
        )


@dataclass(frozen=True, slots=True)
class SettlementStep:
    kind: SettlementStepKind
    owner: str
    precondition: str
    idempotency_key_ref: str
    expected_receipt: str
    command_template: str | None = None
    conditional: bool = False

    def as_dict(self) -> dict[str, Any]:
        step: dict[str, Any] = {
            "kind": self.kind.value,
            "owner": self.owner,
            "precondition": self.precondition,
            "idempotency_key_ref": self.idempotency_key_ref,
            "expected_receipt": self.expected_receipt,
        }
        if self.command_template:
            step["command_template"] = self.command_template
        if self.conditional:
            step["conditional"] = True
        return step


@dataclass(frozen=True, slots=True)
class SettlementPlan:
    identity: SettlementIdentity
    steps: tuple[SettlementStep, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = effect_runtime_result(
            "settlement.plan_payload",
            {
                "plan": {
                    "identity": self.identity.as_dict(),
                    "steps": [step.as_dict() for step in self.steps],
                }
            },
        )
        if not isinstance(payload, Mapping):
            raise RuntimeError("TypeScript settlement plan shape mismatch")
        return dict(payload)


def settlement_result_payload(result: SettlementResult[Any]) -> dict[str, Any]:
    if result._runtime_payload is not None:
        return dict(result._runtime_payload)
    payload = effect_runtime_result(
        "settlement.result_payload",
        {"result": _runtime_result(result)},
    )
    if not isinstance(payload, Mapping):
        raise RuntimeError("TypeScript settlement result payload shape mismatch")
    return dict(payload)


def _effect_turn_from_payload(payload: Any) -> EffectTurn:
    if not isinstance(payload, Mapping):
        raise RuntimeError("TypeScript Effect turn shape mismatch")
    request = payload.get("request")
    interpretation = payload.get("interpretation")
    observation = payload.get("observation")
    next_effect = payload.get("next_effect")
    if not all(
        isinstance(value, Mapping)
        for value in (request, interpretation, observation, next_effect)
    ):
        raise RuntimeError("TypeScript Effect turn shape mismatch")
    assert isinstance(request, Mapping)
    assert isinstance(interpretation, Mapping)
    assert isinstance(observation, Mapping)
    assert isinstance(next_effect, Mapping)
    context = request.get("context")
    normalized_context = dict(context) if isinstance(context, Mapping) else {}
    if isinstance(normalized_context.get("completed_phases"), list):
        normalized_context["completed_phases"] = tuple(
            str(phase) for phase in normalized_context["completed_phases"]
        )
    return EffectTurn(
        request=EffectRequest(
            kind=str(request.get("kind") or ""),
            source=str(request.get("source") or ""),
            goal_id=str(request.get("goal_id"))
            if request.get("goal_id") is not None
            else None,
            agent_id=str(request.get("agent_id"))
            if request.get("agent_id") is not None
            else None,
            capabilities=tuple(str(item) for item in request.get("capabilities", [])),
            context=normalized_context,
        ),
        interpretation=EffectInterpretation(
            route=str(interpretation.get("route") or ""),
            obligation=str(interpretation.get("obligation") or ""),
            interaction_mode=str(interpretation.get("interaction_mode") or ""),
            capability_action=(
                str(interpretation["capability_action"])
                if interpretation.get("capability_action") is not None
                else None
            ),
            cadence_class=(
                str(interpretation["cadence_class"])
                if interpretation.get("cadence_class") is not None
                else None
            ),
        ),
        observation=EffectObservation(
            decision=str(observation.get("decision") or ""),
            should_run=observation.get("should_run") is True,
            effective_action=str(observation.get("effective_action") or ""),
            recommended_action=str(observation.get("recommended_action") or ""),
            protocol_summary=(
                str(observation["protocol_summary"])
                if observation.get("protocol_summary") is not None
                else None
            ),
        ),
        next_effect=EffectNext(
            cli_actions=tuple(str(item) for item in next_effect.get("cli_actions", [])),
            execution_mode=(
                str(next_effect["execution_mode"])
                if next_effect.get("execution_mode") is not None
                else None
            ),
            scheduler_action=(
                str(next_effect["scheduler_action"])
                if next_effect.get("scheduler_action") is not None
                else None
            ),
            cadence_class=(
                str(next_effect["cadence_class"])
                if next_effect.get("cadence_class") is not None
                else None
            ),
            ack_cli_args=tuple(
                str(item) for item in next_effect.get("ack_cli_args", [])
            ),
            failure_cli_args=tuple(
                str(item) for item in next_effect.get("failure_cli_args", [])
            ),
        ),
    )


def effect_program_from_ordered_steps(
    ordered_steps: Sequence[Mapping[str, Any]],
    *,
    execution_mode: str | None = None,
) -> EffectProgram:
    """Map existing `guided_transaction.ordered_steps` onto an effect program."""

    payload = effect_runtime_result(
        "effect.program_from_ordered_steps",
        {
            "ordered_steps": [
                dict(step) if isinstance(step, Mapping) else step
                for step in ordered_steps
            ],
            "execution_mode": execution_mode,
        },
    )
    if not isinstance(payload, Mapping) or not isinstance(payload.get("steps"), list):
        raise RuntimeError("TypeScript Effect Program shape mismatch")
    steps = tuple(
        EffectStep(
            step_id=str(step["step_id"]) if step.get("step_id") is not None else None,
            kind=str(step["kind"]) if step.get("kind") is not None else None,
            command=str(step["command"]) if step.get("command") is not None else None,
            purpose=str(step["purpose"]) if step.get("purpose") is not None else None,
            raw=dict(step["raw"]) if isinstance(step.get("raw"), Mapping) else {},
        )
        for step in payload["steps"]
        if isinstance(step, Mapping)
    )
    mode = payload.get("execution_mode")
    return EffectProgram(
        steps=steps, execution_mode=str(mode) if mode is not None else None
    )


def interpret_quota_should_run_packet(
    packet: Mapping[str, Any],
    *,
    goal_id: str | None = None,
    agent_id: str | None = None,
    capabilities: Sequence[str] = (),
) -> EffectTurn:
    """Map an existing `quota should-run` packet onto canonical effect slots."""
    return _effect_turn_from_payload(
        effect_runtime_result(
            "effect.interpret_quota",
            {
                "packet": dict(packet),
                "identity": {
                    "goal_id": goal_id,
                    "agent_id": agent_id,
                    "capabilities": list(capabilities),
                },
            },
        )
    )


def interpret_turn_result_packet(
    packet: Mapping[str, Any],
    *,
    goal_id: str | None = None,
    agent_id: str | None = None,
    capabilities: Sequence[str] = (),
) -> EffectTurn:
    """Map an existing `loopx_turn_result_v0` packet onto canonical slots."""
    return _effect_turn_from_payload(
        effect_runtime_result(
            "effect.interpret_turn_result",
            {
                "packet": dict(packet),
                "identity": {
                    "goal_id": goal_id,
                    "agent_id": agent_id,
                    "capabilities": list(capabilities),
                },
            },
        )
    )
