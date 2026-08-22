"""Turn-driver adapter for the shared typed settlement receipt-chain driver."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..effect_program import (
    SettlementResult,
    SettlementStepKind,
)
from ..effect_runtime import effect_runtime_result
from ..settlement_driver import decode_settlement_result
from .driver import selected_turn_todo
from .transaction import (
    LoopXTurnResultKind,
    require_loopx_turn_completion_outcome,
)


TurnEffect = Callable[..., Mapping[str, Any]]
TurnEffectResolver = Callable[[str], Mapping[str, Any]]
ResultEffect = Callable[..., Mapping[str, Any]]
TurnSettlementPrepare = Callable[[SettlementStepKind, str], None]
TurnSettlementAbort = Callable[[SettlementStepKind, str], None]
TurnSettlementCheckpoint = Callable[
    [SettlementStepKind, Mapping[str, Any], tuple[str, ...]],
    None,
]

TerminalCloseoutCheckpoint = Callable[[Mapping[str, Any]], None]
CompletionIntent = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class TurnSettlementState:
    completed_phases: tuple[str, ...]
    writeback: Mapping[str, Any] | None = None
    quota_spend: Mapping[str, Any] | None = None


TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION = "loopx_turn_settlement_transaction_v0"
TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION = "loopx_turn_settlement_reduction_v0"


def _invoke_turn_effect(effect: TurnEffect, effect_ref: str) -> Mapping[str, Any]:
    """Invoke a provider with a stable ref while retaining zero-arg callbacks."""

    try:
        signature = inspect.signature(effect)
    except (TypeError, ValueError):
        return effect(effect_ref)
    try:
        signature.bind(effect_ref=effect_ref)
    except TypeError:
        pass
    else:
        return effect(effect_ref=effect_ref)
    try:
        signature.bind()
    except TypeError:
        signature.bind(effect_ref)
        return effect(effect_ref)
    return effect()


def invoke_result_effect(
    effect: ResultEffect,
    result: Mapping[str, Any],
    effect_ref: str,
) -> Mapping[str, Any]:
    """Invoke a result provider with optional stable-ref compatibility."""

    try:
        signature = inspect.signature(effect)
    except (TypeError, ValueError):
        return effect(result, effect_ref)
    try:
        signature.bind(result, effect_ref=effect_ref)
    except TypeError:
        pass
    else:
        return effect(result, effect_ref=effect_ref)
    try:
        signature.bind(result)
    except TypeError:
        signature.bind(result, effect_ref)
        return effect(result, effect_ref)
    return effect(result)


def turn_effect_resolvers(
    *,
    writeback: TurnEffectResolver | None,
    spend: TurnEffectResolver | None,
    terminal_closeout: TurnEffectResolver | None,
) -> dict[SettlementStepKind, TurnEffectResolver]:
    """Collect configured provider readbacks under their typed steps."""

    return {
        step: resolver
        for step, resolver in (
            (SettlementStepKind.DURABLE_WRITEBACK, writeback),
            (SettlementStepKind.QUOTA_SPEND, spend),
            (SettlementStepKind.TERMINAL_CLOSEOUT, terminal_closeout),
        )
        if resolver is not None
    }


@dataclass(frozen=True, slots=True)
class TurnSettlementJournalAdapter:
    """Mechanically persist prepared effects and committed provider payloads."""

    journal: dict[str, Any]
    effects: dict[str, bool]
    persist: Callable[[], None]
    compact_payload: Callable[[Mapping[str, Any]], Mapping[str, Any]]

    @property
    def effect_attempts(self) -> Mapping[str, Mapping[str, Any]]:
        attempts = self.journal.get("effect_attempts")
        return attempts if isinstance(attempts, Mapping) else {}

    def prepare(self, step_kind: SettlementStepKind, effect_ref: str) -> None:
        attempts = self.journal.setdefault("effect_attempts", {})
        if not isinstance(attempts, dict):
            raise RuntimeError("Turn journal effect_attempts shape mismatch")
        attempts[step_kind.value] = {
            "status": "prepared",
            "effect_ref": effect_ref,
        }
        self.persist()

    def abort(self, step_kind: SettlementStepKind, effect_ref: str) -> None:
        self._forget(step_kind, effect_ref)
        self.persist()

    def checkpoint(
        self,
        step_kind: SettlementStepKind,
        payload: Mapping[str, Any],
        phases: tuple[str, ...],
    ) -> None:
        if step_kind is SettlementStepKind.DURABLE_WRITEBACK:
            self.effects["state_written"] = True
            self.journal["writeback"] = self._completion_payload(payload)
        elif step_kind is SettlementStepKind.QUOTA_SPEND:
            self.effects["quota_spent"] = True
            self.journal["quota_spend"] = dict(self.compact_payload(payload))
        self.journal["completed_phases"] = list(phases)
        self._forget(step_kind, str(payload.get("effect_ref") or ""), strict=False)
        self.persist()

    def checkpoint_terminal(self, payload: Mapping[str, Any]) -> None:
        compact = self._completion_payload(payload)
        self.journal["terminal_closeout"] = compact
        writeback = self.journal.get("writeback")
        self.journal["writeback"] = {
            **(dict(writeback) if isinstance(writeback, Mapping) else {}),
            "completion": compact.get("completion"),
        }
        self._forget(
            SettlementStepKind.TERMINAL_CLOSEOUT,
            str(payload.get("effect_ref") or ""),
            strict=False,
        )
        self.persist()

    def _completion_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            **dict(self.compact_payload(payload)),
            **(
                {"completion": dict(payload["completion"])}
                if isinstance(payload.get("completion"), Mapping)
                else {}
            ),
        }

    def _forget(
        self,
        step_kind: SettlementStepKind,
        effect_ref: str,
        *,
        strict: bool = True,
    ) -> None:
        attempts = self.journal.get("effect_attempts")
        if not isinstance(attempts, dict):
            return
        attempt = attempts.get(step_kind.value)
        if (
            isinstance(attempt, Mapping)
            and effect_ref
            and (attempt.get("effect_ref") != effect_ref)
        ):
            if strict:
                raise RuntimeError("Turn journal prepared effect ref changed")
            return
        attempts.pop(step_kind.value, None)
        if not attempts:
            self.journal.pop("effect_attempts", None)


def completion_writeback_outcome(
    payload: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return the selected Todo's validated durable completion outcome."""

    completion = payload.get("completion")
    if not isinstance(completion, Mapping):
        return None
    envelope = plan.get("turn_envelope")
    selected = selected_turn_todo(envelope) if isinstance(envelope, Mapping) else {}
    try:
        return require_loopx_turn_completion_outcome(
            completion,
            expected_todo_id=str(selected.get("todo_id") or ""),
        )
    except ValueError:
        return None


def terminal_closeout_requirement(
    *,
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    journal: Mapping[str, Any],
    completion_intent: CompletionIntent,
) -> tuple[bool, str | None]:
    """Classify final no-followup without mutating the Todo frontier."""

    if result.get("result_kind") != LoopXTurnResultKind.VALIDATED_COMPLETION.value:
        return False, None
    stored_terminal = journal.get("terminal_closeout")
    stored_writeback = journal.get("writeback")
    terminal_payload = stored_terminal if isinstance(stored_terminal, Mapping) else {}
    writeback_payload = (
        stored_writeback if isinstance(stored_writeback, Mapping) else {}
    )
    observed_completion = terminal_payload.get("completion") or writeback_payload.get(
        "completion"
    )
    try:
        if not isinstance(observed_completion, Mapping):
            observed_completion = completion_intent(result)
        envelope = plan.get("turn_envelope")
        selected = selected_turn_todo(envelope) if isinstance(envelope, Mapping) else {}
        outcome = require_loopx_turn_completion_outcome(
            observed_completion,
            expected_todo_id=str(selected.get("todo_id") or ""),
        )
    except (TypeError, ValueError) as exc:
        return False, str(exc)
    return outcome["continuation"] == "no_followup", None


def verified_terminal_closeout_effect(
    effect: ResultEffect,
    *,
    result: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> TurnEffect:
    """Wrap terminal closeout with its durable no-followup postcondition."""

    def verified(effect_ref: str) -> Mapping[str, Any]:
        callback_payload = invoke_result_effect(effect, result, effect_ref)
        outcome = completion_writeback_outcome(callback_payload, plan=plan)
        if outcome is None or outcome.get("continuation") != "no_followup":
            return {
                "ok": False,
                "appended": False,
                "reason": (
                    "terminal closeout adapter did not durably record the "
                    "selected Todo as no_followup"
                ),
            }
        return {**callback_payload, "completion": outcome}

    return verified


def _resolve_prepared_effect(
    resolvers: Mapping[SettlementStepKind, TurnEffectResolver],
    step_kind: SettlementStepKind,
    effect_ref: str,
) -> tuple[bool, Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """Return execute, committed payload, or a fail-closed observation."""

    resolver = resolvers.get(step_kind)
    if resolver is None:
        return (
            False,
            None,
            {
                "kind": "unknown",
                "reason": "provider readback is unavailable",
            },
        )
    try:
        resolution = dict(resolver(effect_ref))
    except Exception as exc:
        return (
            False,
            None,
            {
                "kind": "unknown",
                "reason": f"provider readback raised {type(exc).__name__}",
            },
        )
    kind = str(resolution.get("kind") or "unknown")
    if kind == "absent":
        return True, None, None
    if kind != "committed":
        observation = (
            resolution
            if kind == "unknown"
            else {
                "kind": "unknown",
                "reason": f"unsupported provider readback kind: {kind}",
            }
        )
        return False, None, observation
    raw_payload = resolution.get("payload")
    observed = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
    if observed.get("ok") is True and observed.get("appended") is True:
        return False, observed, None
    return False, None, resolution


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
    committed_effect_id: str | None = None,
    terminal_closeout_required: bool = False,
    terminal_closeout_payload: Mapping[str, Any] | None = None,
    terminal_closeout: TurnEffect | None = None,
    terminal_checkpoint: TerminalCloseoutCheckpoint | None = None,
    prepare: TurnSettlementPrepare | None = None,
    abort: TurnSettlementAbort | None = None,
    effect_attempts: Mapping[str, Mapping[str, Any]] | None = None,
    effect_resolvers: Mapping[SettlementStepKind, TurnEffectResolver] | None = None,
) -> SettlementResult[TurnSettlementState]:
    """Run external effect providers and reduce one complete Turn settlement.

    TypeScript first validates identity, replay, and the committed journal
    prefix, then authorizes the still-Python providers in order. Python invokes
    and checkpoints those opaque outcomes before a final TypeScript reduction
    owns failure classification, receipts, and the canonical result. A replay
    with no pending provider completes in the first reduction.
    """
    phases = tuple(str(phase) for phase in completed_phases)
    writeback_value = writeback_payload
    spend_value = quota_spend_payload
    terminal_value = terminal_closeout_payload
    failed_attempt: tuple[SettlementStepKind, Mapping[str, Any]] | None = None
    attempts = {
        (step.value if isinstance(step, SettlementStepKind) else str(step)): dict(
            attempt
        )
        for step, attempt in (effect_attempts or {}).items()
    }
    observations: dict[str, Mapping[str, Any]] = {}
    resolvers = dict(effect_resolvers or {})

    def committed(payload: Mapping[str, Any]) -> bool:
        # This transport guard only prevents a later provider from running
        # after an earlier provider rejected. TS remains authoritative for the
        # typed failure kind, receipt chain, and final settlement result.
        return payload.get("ok") is True and payload.get("appended") is True

    def reduce() -> Mapping[str, Any]:
        payload = effect_runtime_result(
            "turn.settlement.reduce",
            {
                "schema_version": TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION,
                "transaction_plan": dict(transaction_plan),
                "transaction_phases": list(transaction_phases),
                "completed_phases": list(phases),
                "committed_effect_id": committed_effect_id,
                "writeback_payload": (
                    dict(writeback_value)
                    if isinstance(writeback_value, Mapping)
                    else None
                ),
                "quota_spend_payload": (
                    dict(spend_value) if isinstance(spend_value, Mapping) else None
                ),
                "terminal_closeout_required": terminal_closeout_required,
                "terminal_closeout_payload": (
                    dict(terminal_value)
                    if isinstance(terminal_value, Mapping)
                    else None
                ),
                "failed_provider_attempt": (
                    {
                        "step_kind": failed_attempt[0].value,
                        "payload": dict(failed_attempt[1]),
                    }
                    if failed_attempt is not None
                    else None
                ),
                "effect_attempts": attempts,
                "provider_observations": observations,
            },
        )
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema_version") != TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION
        ):
            raise RuntimeError("TypeScript Turn settlement reduction shape mismatch")
        return payload

    reduction = reduce()
    decision = str(reduction.get("decision") or "")
    if decision == "execute":
        provider_effects = reduction.get("provider_effects")
        if not isinstance(provider_effects, list) or not provider_effects:
            raise RuntimeError("TypeScript Turn settlement provider plan is empty")
        providers = {
            SettlementStepKind.DURABLE_WRITEBACK: writeback,
            SettlementStepKind.QUOTA_SPEND: spend,
        }
        for raw_effect in provider_effects:
            if not isinstance(raw_effect, Mapping):
                raise RuntimeError("TypeScript Turn settlement provider shape mismatch")
            step_kind = SettlementStepKind(str(raw_effect.get("step_kind") or ""))
            action = str(raw_effect.get("action") or "")
            effect_ref = str(raw_effect.get("effect_ref") or "")
            if action not in {"prepare_and_execute", "resolve_prepared"}:
                raise RuntimeError("TypeScript Turn settlement action mismatch")
            if not effect_ref:
                raise RuntimeError("TypeScript Turn settlement effect ref is empty")
            raw_phases = raw_effect.get("completed_phases")
            if not isinstance(raw_phases, list):
                raise RuntimeError("TypeScript Turn settlement phases shape mismatch")
            authorized_phases = tuple(str(phase) for phase in raw_phases)
            should_execute = action == "prepare_and_execute"
            if action == "prepare_and_execute":
                if prepare is not None:
                    prepare(step_kind, effect_ref)
                attempts[step_kind.value] = {
                    "status": "prepared",
                    "effect_ref": effect_ref,
                }
            else:
                should_execute, observed, observation = _resolve_prepared_effect(
                    resolvers, step_kind, effect_ref
                )
                if observation is not None:
                    observations[step_kind.value] = observation
                    break

            if step_kind is SettlementStepKind.TERMINAL_CLOSEOUT:
                if terminal_closeout is None or terminal_checkpoint is None:
                    raise ValueError(
                        "terminal closeout requires an effect provider and checkpoint"
                    )
                if should_execute:
                    observed = dict(_invoke_turn_effect(terminal_closeout, effect_ref))
                assert observed is not None
                if committed(observed):
                    terminal_value = observed
                    terminal_checkpoint(observed)
                    attempts.pop(step_kind.value, None)
                else:
                    if abort is not None:
                        abort(step_kind, effect_ref)
                    attempts.pop(step_kind.value, None)
                    failed_attempt = (step_kind, observed)
                    break
                continue

            if should_execute:
                observed = dict(_invoke_turn_effect(providers[step_kind], effect_ref))
            assert observed is not None
            if not committed(observed):
                if abort is not None:
                    abort(step_kind, effect_ref)
                attempts.pop(step_kind.value, None)
                failed_attempt = (step_kind, observed)
                break
            phases = authorized_phases
            checkpoint(step_kind, observed, phases)
            attempts.pop(step_kind.value, None)
            if step_kind is SettlementStepKind.DURABLE_WRITEBACK:
                writeback_value = observed
            else:
                spend_value = observed
        reduction = reduce()
        decision = str(reduction.get("decision") or "")

    if decision not in {"complete", "failed"}:
        raise RuntimeError("TypeScript Turn settlement did not reach an outcome")

    def decode_state(value: Any) -> TurnSettlementState:
        if not isinstance(value, Mapping):
            raise RuntimeError("TypeScript Turn settlement state shape mismatch")
        completed = value.get("completed_phases")
        if not isinstance(completed, list):
            raise RuntimeError("TypeScript Turn settlement phases shape mismatch")
        raw_writeback = value.get("writeback")
        raw_spend = value.get("quota_spend")
        return TurnSettlementState(
            completed_phases=tuple(str(phase) for phase in completed),
            writeback=(
                dict(raw_writeback) if isinstance(raw_writeback, Mapping) else None
            ),
            quota_spend=(dict(raw_spend) if isinstance(raw_spend, Mapping) else None),
        )

    projection = reduction.get("settlement_result")
    return decode_settlement_result(
        reduction.get("result"),
        value_decoder=decode_state,
        projection_payload=(projection if isinstance(projection, Mapping) else None),
    )
