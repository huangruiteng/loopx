"""Turn-driver adapter for the shared typed settlement algebra."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..effect_program import (
    SettlementFailureKind,
    SettlementReceipt,
    SettlementResult,
    SettlementStepKind,
)


TurnEffect = Callable[[], Mapping[str, Any]]
TurnSettlementCheckpoint = Callable[
    [SettlementStepKind, Mapping[str, Any], tuple[str, ...]],
    None,
]


@dataclass(frozen=True, slots=True)
class TurnSettlementState:
    completed_phases: tuple[str, ...]
    writeback: Mapping[str, Any] | None = None
    quota_spend: Mapping[str, Any] | None = None


def _effect_id(transaction_plan: Mapping[str, Any]) -> str:
    settlement_plan = transaction_plan.get("settlement_plan")
    if not isinstance(settlement_plan, Mapping):
        raise ValueError("Turn transaction has no typed settlement plan")
    identity = settlement_plan.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("Turn settlement plan has no identity")
    effect_id = str(identity.get("effect_id") or "").strip()
    if not effect_id:
        raise ValueError("Turn settlement plan has no effect id")
    return effect_id


def _settlement_effect_id(
    transaction_plan: Mapping[str, Any],
) -> SettlementResult[str]:
    """Resolve the typed effect id, failing closed instead of raising.

    Legacy or journaled Turn plans created before the typed settlement binding
    may have no ``settlement_plan``. The turn driver must surface that as a
    typed validation failure rather than crash with ``ValueError``.
    """

    settlement_plan = transaction_plan.get("settlement_plan")
    if not isinstance(settlement_plan, Mapping):
        return SettlementResult.failed(
            kind=SettlementFailureKind.RECEIPT_MISSING,
            step_kind=SettlementStepKind.VALIDATION,
            reason="Turn transaction has no typed settlement plan",
        )
    identity = settlement_plan.get("identity")
    if not isinstance(identity, Mapping):
        return SettlementResult.failed(
            kind=SettlementFailureKind.INVALID_IDENTITY,
            step_kind=SettlementStepKind.VALIDATION,
            reason="Turn settlement plan has no identity",
        )
    effect_id = str(identity.get("effect_id") or "").strip()
    if not effect_id:
        return SettlementResult.failed(
            kind=SettlementFailureKind.INVALID_IDENTITY,
            step_kind=SettlementStepKind.VALIDATION,
            reason="Turn settlement plan has no effect id",
        )
    return SettlementResult.pure(effect_id)


def _receipt(
    *,
    effect_id: str,
    step_kind: SettlementStepKind,
) -> SettlementReceipt:
    return SettlementReceipt(
        step_kind=step_kind,
        status="committed",
        effect_id=effect_id,
        source_ref=f"turn_journal:{effect_id}#{step_kind.value}",
    )


def _committed_payload(value: Mapping[str, Any] | None) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("ok") is True
        and (
            value.get("appended") is True
            or value.get("idempotent") is True
        )
    )


def _seed_result(
    transaction_plan: Mapping[str, Any],
    *,
    transaction_phases: tuple[str, ...],
    completed_phases: Sequence[str],
    writeback_payload: Mapping[str, Any] | None,
    quota_spend_payload: Mapping[str, Any] | None,
) -> SettlementResult[TurnSettlementState]:
    effect_id = _effect_id(transaction_plan)
    phases = tuple(str(phase) for phase in completed_phases)
    if phases != transaction_phases[: len(phases)]:
        return SettlementResult.failed(
            kind=SettlementFailureKind.RECEIPT_MISSING,
            step_kind=SettlementStepKind.VALIDATION,
            reason="Turn journal phases are not an ordered transaction prefix",
        )
    if "validation" not in phases:
        return SettlementResult.failed(
            kind=SettlementFailureKind.RECEIPT_MISSING,
            step_kind=SettlementStepKind.VALIDATION,
            reason="Turn settlement requires a committed validation receipt",
        )

    receipts = [
        _receipt(
            effect_id=effect_id,
            step_kind=SettlementStepKind.VALIDATION,
        )
    ]
    if "durable_writeback" in phases:
        if not _committed_payload(writeback_payload):
            return SettlementResult.failed(
                kind=SettlementFailureKind.RECEIPT_MISSING,
                step_kind=SettlementStepKind.DURABLE_WRITEBACK,
                reason="Turn journal is missing its committed writeback payload",
                receipts=tuple(receipts),
            )
        receipts.append(
            _receipt(
                effect_id=effect_id,
                step_kind=SettlementStepKind.DURABLE_WRITEBACK,
            )
        )
    if "quota_spend" in phases:
        if not _committed_payload(quota_spend_payload):
            return SettlementResult.failed(
                kind=SettlementFailureKind.RECEIPT_MISSING,
                step_kind=SettlementStepKind.QUOTA_SPEND,
                reason="Turn journal is missing its committed quota spend payload",
                receipts=tuple(receipts),
            )
        receipts.append(
            _receipt(
                effect_id=effect_id,
                step_kind=SettlementStepKind.QUOTA_SPEND,
            )
        )
    return SettlementResult.pure(
        TurnSettlementState(
            completed_phases=phases,
            writeback=writeback_payload,
            quota_spend=quota_spend_payload,
        ),
        receipts=tuple(receipts),
    )


def _callback_failure_kind(
    step_kind: SettlementStepKind,
    reason: str,
) -> SettlementFailureKind:
    if step_kind is SettlementStepKind.DURABLE_WRITEBACK:
        return SettlementFailureKind.WRITEBACK_REJECTED
    if "budget" in reason.casefold():
        return SettlementFailureKind.BUDGET_REJECTED
    return SettlementFailureKind.QUOTA_SPEND_REJECTED


def _commit_effect(
    state: TurnSettlementState,
    *,
    effect_id: str,
    step_kind: SettlementStepKind,
    transaction_phases: tuple[str, ...],
    effect: TurnEffect,
    checkpoint: TurnSettlementCheckpoint,
) -> SettlementResult[TurnSettlementState]:
    payload = dict(effect())
    if not _committed_payload(payload):
        reason = str(
            payload.get("error")
            or payload.get("reason")
            or f"{step_kind.value} callback rejected the settlement"
        )
        return SettlementResult.failed(
            kind=_callback_failure_kind(step_kind, reason),
            step_kind=step_kind,
            reason=reason,
        )
    phase_index = transaction_phases.index(step_kind.value)
    completed_phases = transaction_phases[: phase_index + 1]
    next_state = TurnSettlementState(
        completed_phases=completed_phases,
        writeback=(
            payload
            if step_kind is SettlementStepKind.DURABLE_WRITEBACK
            else state.writeback
        ),
        quota_spend=(
            payload if step_kind is SettlementStepKind.QUOTA_SPEND else state.quota_spend
        ),
    )
    checkpoint(step_kind, payload, completed_phases)
    return SettlementResult.pure(
        next_state,
        receipts=(_receipt(effect_id=effect_id, step_kind=step_kind),),
    )


def execute_turn_driver_settlement(
    transaction_plan: Mapping[str, Any],
    *,
    transaction_phases: tuple[str, ...],
    completed_phases: Sequence[str],
    writeback_payload: Mapping[str, Any] | None,
    quota_spend_payload: Mapping[str, Any] | None,
    writeback: TurnEffect,
    spend: TurnEffect,
    checkpoint: TurnSettlementCheckpoint,
) -> SettlementResult[TurnSettlementState]:
    """Bind validation -> writeback -> spend for the isolated Turn adapter."""

    effect_result = _settlement_effect_id(transaction_plan)
    if effect_result.failure is not None:
        return effect_result
    effect_id = effect_result.value
    assert effect_id is not None
    result = _seed_result(
        transaction_plan,
        transaction_phases=transaction_phases,
        completed_phases=completed_phases,
        writeback_payload=writeback_payload,
        quota_spend_payload=quota_spend_payload,
    )
    if "durable_writeback" not in completed_phases:
        result = result.bind(
            lambda state: _commit_effect(
                state,
                effect_id=effect_id,
                step_kind=SettlementStepKind.DURABLE_WRITEBACK,
                transaction_phases=transaction_phases,
                effect=writeback,
                checkpoint=checkpoint,
            )
        )
    if "quota_spend" not in completed_phases:
        result = result.bind(
            lambda state: _commit_effect(
                state,
                effect_id=effect_id,
                step_kind=SettlementStepKind.QUOTA_SPEND,
                transaction_phases=transaction_phases,
                effect=spend,
                checkpoint=checkpoint,
            )
        )
    return result
