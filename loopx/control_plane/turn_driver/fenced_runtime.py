"""Lease-fenced, append-only runtime for one bounded LoopX Turn."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..effect_program import SettlementStepKind, interpret_turn_result_packet, settlement_result_payload
from ..work_items.task_lease import TaskLeaseError
from .executor import (
    LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
    STOP_HOST_RESULT_KINDS,
    CompletionWriteback,
    FaultInjector,
    HostRunner,
    Scheduler,
    Spend,
    TaskValidator,
    Writeback,
    _compact_callback,
    _completion_writeback_outcome,
    _ensure_turn_settlement_plan,
    _execution_payload,
    _host_failure,
    _receipt,
    _run_host,
    _run_host_runner,
    _run_task_validator,
    _task_validation_receipt,
    build_loopx_turn_host_request,
    normalize_host_argv,
    validate_loopx_turn_host_result,
)
from .journal import TurnJournalError, append_turn_event, load_turn_events
from .lease import TurnFence, TurnLeaseController
from .settlement import execute_turn_driver_settlement
from .transaction import TRANSACTION_PHASES, LoopXTurnResultKind, TurnEffectEnvelope


def _state_from_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    state: dict[str, Any] | None = None
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            continue
        candidate = payload.get("state")
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("schema_version") != LOOPX_TURN_JOURNAL_SCHEMA_VERSION:
            raise TurnJournalError("Turn state snapshot has an unsupported schema")
        state = dict(candidate)
    return state


def load_turn_state(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any] | None:
    events = load_turn_events(runtime_root, goal_id, turn_key)
    state = _state_from_events(events)
    if state is None:
        return None
    if state.get("goal_id") != goal_id or state.get("turn_key") != turn_key:
        raise TurnJournalError("Turn state snapshot has mismatched lineage")
    return state


def load_loopx_turn_plan_from_fenced_journal(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    state = load_turn_state(
        runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
    )
    if state is None:
        raise ValueError("LoopX Turn resume journal does not exist")
    plan = state.get("plan")
    if not isinstance(plan, dict):
        raise TypeError("LoopX Turn resume journal does not contain a plan")
    transaction = plan.get("transaction")
    if not isinstance(transaction, dict) or transaction.get("turn_key") != turn_key:
        raise ValueError("LoopX Turn resume journal has mismatched turn lineage")
    envelope = plan.get("turn_envelope")
    if not isinstance(envelope, dict) or envelope.get("goal_id") != goal_id:
        raise ValueError("LoopX Turn resume journal belongs to another goal")
    return dict(plan)


def _append_state(
    *,
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    event_type: str,
    phase_key: str,
    phase: str,
    fence: TurnFence,
    state: dict[str, Any],
) -> None:
    state["fencing_token"] = fence.token
    append_turn_event(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        event_type=event_type,
        phase_key=phase_key,
        fencing=fence,
        payload={"phase": phase, "state": dict(state)},
    )


def _unique_phase_key(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
    prefix: str,
) -> str:
    event_count = len(load_turn_events(runtime_root, goal_id, turn_key))
    return f"{turn_key}:{prefix}:event:{event_count:06d}"


def _record_intent(
    *,
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    envelope: TurnEffectEnvelope,
    fence: TurnFence,
) -> None:
    phase_key = f"{envelope.phase_key}:intent"
    expected_payload = {
        "phase": envelope.phase,
        "phase_key": envelope.phase_key,
    }
    for event in load_turn_events(runtime_root, goal_id, turn_key):
        if event.get("phase_key") != phase_key:
            continue
        if event.get("event_type") != "phase_intent" or event.get(
            "payload"
        ) != expected_payload:
            raise TurnJournalError("turn journal phase intent conflict")
        return
    append_turn_event(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        event_type="phase_intent",
        phase_key=phase_key,
        fencing=fence,
        payload=expected_payload,
    )


def _call_compatible(
    callback: Callable[..., dict[str, Any]],
    current_args: tuple[Any, ...],
    legacy_args: tuple[Any, ...],
) -> dict[str, Any]:
    try:
        callback_signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return callback(*current_args)
    try:
        callback_signature.bind(*current_args)
    except TypeError:
        callback_signature.bind(*legacy_args)
        return callback(*legacy_args)
    return callback(*current_args)


def _fault(fault_injector: FaultInjector | None, phase: str) -> None:
    if fault_injector is not None:
        fault_injector(phase)


def _public_payload(
    plan: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    execute: bool,
    replayed: bool,
    effects: Mapping[str, bool],
    fence: TurnFence | None,
) -> dict[str, Any]:
    payload = _execution_payload(
        plan,
        state,
        execute=execute,
        replayed=replayed,
        effects=effects,
    )
    fencing_token = fence.token if fence is not None else state.get("fencing_token")
    if fencing_token:
        payload["fencing_token"] = fencing_token
    if state.get("reason_code"):
        payload["reason_code"] = state["reason_code"]
    return payload


def _failed_closed_payload(
    plan: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    *,
    reason: str,
    reason_code: str,
    effects: Mapping[str, bool],
    fence: TurnFence | None,
) -> dict[str, Any]:
    failed_state = dict(state or {})
    transaction = plan.get("transaction")
    turn_key = str(transaction.get("turn_key") if isinstance(transaction, Mapping) else "")
    completed = list(failed_state.get("completed_phases") or [])
    failed_phase = (
        TRANSACTION_PHASES[len(completed)]
        if len(completed) < len(TRANSACTION_PHASES)
        else None
    )
    result = {"turn_key": turn_key, "result_kind": LoopXTurnResultKind.FAILED_CLOSED.value}
    failed_state.update(
        schema_version=LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
        turn_key=turn_key,
        status="failed_closed",
        result_kind=LoopXTurnResultKind.FAILED_CLOSED.value,
        completed_phases=completed,
        reason=reason,
        reason_code=reason_code,
        receipt=_receipt(
            plan,
            result,
            completed_phases=completed,
            failure_kind=LoopXTurnResultKind.FAILED_CLOSED,
            failed_phase=failed_phase,
        ),
    )
    return _public_payload(
        plan,
        failed_state,
        execute=True,
        replayed=False,
        effects=effects,
        fence=fence,
    )


def _record_failure(
    plan: Mapping[str, Any],
    state: dict[str, Any],
    *,
    kind: LoopXTurnResultKind,
    failed_phase: str,
    reason: str,
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    fence: TurnFence,
) -> None:
    completed = list(state.get("completed_phases") or [])
    failure = _host_failure(
        plan,
        kind=kind,
        completed_phases=completed,
        failed_phase=failed_phase,
        reason=reason,
    )
    state.update(
        status="failed",
        result_kind=kind.value,
        reason=reason,
        receipt=failure["receipt"],
    )
    _append_state(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        event_type="phase_failed",
        phase_key=_unique_phase_key(
            runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            prefix=f"{failed_phase}:failed",
        ),
        phase=failed_phase,
        fence=fence,
        state=state,
    )


def _prepare_retry(
    state: dict[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    fence: TurnFence,
) -> None:
    receipt = state.get("receipt") if isinstance(state.get("receipt"), dict) else {}
    if receipt.get("failed_phase") == "validation":
        if state.get("validation_stage") != "task_postcondition":
            state.pop("host_result", None)
        state.pop("result_kind", None)
        state["completed_phases"] = (
            list(TRANSACTION_PHASES[:2])
            if isinstance(state.get("host_result"), dict)
            else []
        )
        state.pop("task_validation", None)
        state.pop("validation_stage", None)
    state.pop("reason", None)
    state.pop("reason_code", None)
    state.pop("receipt", None)
    state["status"] = "in_progress"
    _append_state(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        event_type="turn_retry",
        phase_key=_unique_phase_key(
            runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            prefix="retry",
        ),
        phase="retry",
        fence=fence,
        state=state,
    )


def _guarded_effect(
    *,
    controller: TurnLeaseController,
    latest: Callable[[], TurnFence],
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    phase: str,
    invoke: Callable[[TurnEffectEnvelope], dict[str, Any]],
) -> dict[str, Any]:
    fence = latest()
    envelope = TurnEffectEnvelope(
        turn_key=turn_key,
        phase=phase,
        phase_key=f"{turn_key}:{phase}",
        fencing_token=fence.token,
    )
    controller.require_current(fence)
    _record_intent(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        envelope=envelope,
        fence=fence,
    )
    fence = latest()
    controller.require_current(fence)
    with controller.effect_guard(fence):
        payload = invoke(envelope)
    controller.require_current(latest())
    return payload


def _execute_fenced(
    plan: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    host_projection: Mapping[str, Any],
    argv: Sequence[str] | None,
    host_runner: HostRunner | None,
    project: Path,
    runtime_root: Path,
    goal_id: str,
    timeout_seconds: float,
    retry_failed: bool,
    task_validator: TaskValidator | None,
    writeback: Writeback,
    completion_writeback: CompletionWriteback | None,
    spend: Spend,
    scheduler: Scheduler,
    controller: TurnLeaseController,
    fence: TurnFence,
    latest: Callable[[], TurnFence],
    fault_injector: FaultInjector | None,
    effects: dict[str, bool],
) -> dict[str, Any]:
    turn_key = str(request["turn_key"])
    state = load_turn_state(runtime_root, goal_id=goal_id, turn_key=turn_key)
    if state is not None and (
        state.get("status") in {"committed", "stopped"}
        or state.get("status") == "failed" and not retry_failed
    ):
        return _public_payload(
            plan,
            state,
            execute=True,
            replayed=True,
            effects=effects,
            fence=fence,
        )
    if state is None:
        state = {
            "schema_version": LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
            "turn_key": turn_key,
            "goal_id": goal_id,
            "status": "in_progress",
            "host": dict(host_projection),
            "completed_phases": [],
            "plan": dict(plan),
        }
    if state.get("fencing_token") != fence.token:
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="turn_owned",
            phase_key=f"{turn_key}:ownership:{fence.generation}",
            phase="ownership",
            fence=fence,
            state=state,
        )
    if state.get("status") == "failed" and retry_failed:
        _prepare_retry(
            state,
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            fence=latest(),
        )

    completed = list(state.get("completed_phases") or [])
    result = state.get("host_result") if isinstance(state.get("host_result"), dict) else None
    if "typed_result" not in completed:
        observation = (
            _run_host_runner(request, runner=host_runner)
            if host_runner is not None
            else _run_host(
                request,
                argv=argv or [],
                project=project,
                timeout_seconds=timeout_seconds,
            )
        )
        effects["host_invoked"] = True
        if not observation.get("ok"):
            _record_failure(
                plan,
                state,
                kind=LoopXTurnResultKind.HOST_FAILURE,
                failed_phase="host_execute",
                reason=str(observation.get("reason") or "host execution failed"),
                runtime_root=runtime_root,
                goal_id=goal_id,
                turn_key=turn_key,
                fence=latest(),
            )
            return _public_payload(
                plan,
                state,
                execute=True,
                replayed=False,
                effects=effects,
                fence=latest(),
            )
        candidate = dict(observation["value"])
        validation = validate_loopx_turn_host_result(
            plan,
            candidate,
            completion_writeback_configured=completion_writeback is not None,
        )
        if not validation.get("ok"):
            state["completed_phases"] = list(TRANSACTION_PHASES[:2])
            state["validation_stage"] = "host_result_contract"
            _record_failure(
                plan,
                state,
                kind=LoopXTurnResultKind.VALIDATION_FAILED,
                failed_phase="validation",
                reason="; ".join(
                    validation.get("errors") or ["host result validation failed"]
                ),
                runtime_root=runtime_root,
                goal_id=goal_id,
                turn_key=turn_key,
                fence=latest(),
            )
            return _public_payload(
                plan,
                state,
                execute=True,
                replayed=False,
                effects=effects,
                fence=latest(),
            )
        result = dict(validation["result"])
        completed = list(TRANSACTION_PHASES[:2])
        state.update(
            host_result=result,
            result_kind=result.get("result_kind"),
            completed_phases=completed,
            status="in_progress",
        )
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="phase_completed",
            phase_key=f"{turn_key}:typed_result:completed",
            phase="typed_result",
            fence=latest(),
            state=state,
        )
        _fault(fault_injector, "after_host")
    assert result is not None

    turn = interpret_turn_result_packet(result)
    kind = LoopXTurnResultKind(turn.observation.decision)
    completed = list(state.get("completed_phases") or completed)
    if kind in STOP_HOST_RESULT_KINDS:
        completed = list(TRANSACTION_PHASES[:3])
        state.update(
            status="stopped",
            completed_phases=completed,
            task_validation=_task_validation_receipt(
                status="not_required",
                validator_kind="stop_result",
                summary="task validation is not required for a typed stop result",
            ),
            receipt=_receipt(plan, result, completed_phases=completed),
            scheduler={"disposition": "not_applicable"},
        )
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="phase_completed",
            phase_key=f"{turn_key}:validation:completed",
            phase="validation",
            fence=latest(),
            state=state,
        )
        _fault(fault_injector, "after_validation")
        return _public_payload(
            plan,
            state,
            execute=True,
            replayed=False,
            effects=effects,
            fence=latest(),
        )

    stored_validation = (
        state.get("task_validation")
        if isinstance(state.get("task_validation"), dict)
        else None
    )
    task_validation = (
        stored_validation
        if "validation" in completed
        and stored_validation is not None
        and stored_validation.get("ok") is True
        else _run_task_validator(plan, result, validator=task_validator)
    )
    state["task_validation"] = task_validation
    if not task_validation.get("ok"):
        state["completed_phases"] = list(TRANSACTION_PHASES[:2])
        state["validation_stage"] = "task_postcondition"
        _record_failure(
            plan,
            state,
            kind=LoopXTurnResultKind.VALIDATION_FAILED,
            failed_phase="validation",
            reason=str(
                task_validation.get("summary")
                or "independent task validation failed"
            ),
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            fence=latest(),
        )
        return _public_payload(
            plan,
            state,
            execute=True,
            replayed=False,
            effects=effects,
            fence=latest(),
        )
    if "validation" not in completed:
        completed = list(TRANSACTION_PHASES[:3])
        state.update(
            result_kind=result.get("result_kind"),
            completed_phases=completed,
            validation_stage="task_postcondition",
        )
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="phase_completed",
            phase_key=f"{turn_key}:validation:completed",
            phase="validation",
            fence=latest(),
            state=state,
        )
        _fault(fault_injector, "after_validation")

    transaction_plan = (
        plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    )
    _ensure_turn_settlement_plan(plan, transaction_plan)

    def writeback_effect() -> Mapping[str, Any]:
        def invoke(envelope: TurnEffectEnvelope) -> dict[str, Any]:
            callback = (
                completion_writeback
                if result.get("result_kind")
                == LoopXTurnResultKind.VALIDATED_COMPLETION.value
                else writeback
            )
            if callback is None:
                raise ValueError(
                    "validated_completion requires a todo lifecycle adapter"
                )
            callback_payload = _call_compatible(
                callback,
                (envelope, result),
                (result,),
            )
            if callback is completion_writeback:
                completion_outcome = _completion_writeback_outcome(
                    callback_payload,
                    plan=plan,
                )
                if completion_outcome is None:
                    return {
                        "ok": False,
                        "appended": False,
                        "reason": "todo lifecycle adapter returned an invalid completion outcome",
                    }
                return {**callback_payload, "completion": completion_outcome}
            return callback_payload

        return _guarded_effect(
            controller=controller,
            latest=latest,
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            phase="durable_writeback",
            invoke=invoke,
        )

    def spend_effect() -> Mapping[str, Any]:
        return _guarded_effect(
            controller=controller,
            latest=latest,
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            phase="quota_spend",
            invoke=lambda envelope: _call_compatible(
                spend,
                (envelope,),
                (),
            ),
        )

    def checkpoint(
        step_kind: SettlementStepKind,
        payload: Mapping[str, Any],
        phases: tuple[str, ...],
    ) -> None:
        if step_kind is SettlementStepKind.DURABLE_WRITEBACK:
            effects["state_written"] = True
            state["writeback"] = {
                **_compact_callback(payload),
                **(
                    {"completion": payload["completion"]}
                    if isinstance(payload.get("completion"), dict)
                    else {}
                ),
            }
        else:
            effects["quota_spent"] = True
            state["quota_spend"] = _compact_callback(payload)
        state["completed_phases"] = list(phases)
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="phase_completed",
            phase_key=f"{turn_key}:{step_kind.value}:completed",
            phase=step_kind.value,
            fence=latest(),
            state=state,
        )
        fault_phase = (
            "after_writeback"
            if step_kind is SettlementStepKind.DURABLE_WRITEBACK
            else "after_spend"
        )
        _fault(fault_injector, fault_phase)

    completed = list(state.get("completed_phases") or completed)
    settlement_result = execute_turn_driver_settlement(
        transaction_plan,
        transaction_phases=TRANSACTION_PHASES,
        completed_phases=completed,
        writeback_payload=(
            state.get("writeback")
            if isinstance(state.get("writeback"), Mapping)
            else None
        ),
        quota_spend_payload=(
            state.get("quota_spend")
            if isinstance(state.get("quota_spend"), Mapping)
            else None
        ),
        writeback=writeback_effect,
        spend=spend_effect,
        checkpoint=checkpoint,
    )
    state["settlement_result"] = settlement_result_payload(settlement_result)
    if settlement_result.failure is not None:
        failure_step = settlement_result.failure.step_kind
        result_kind = (
            LoopXTurnResultKind.VALIDATION_FAILED
            if failure_step is SettlementStepKind.VALIDATION
            else LoopXTurnResultKind.WRITEBACK_FAILED
            if failure_step is SettlementStepKind.DURABLE_WRITEBACK
            else LoopXTurnResultKind.QUOTA_SPEND_FAILED
        )
        _record_failure(
            plan,
            state,
            kind=result_kind,
            failed_phase=failure_step.value,
            reason=settlement_result.failure.reason,
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            fence=latest(),
        )
        return _public_payload(
            plan,
            state,
            execute=True,
            replayed=False,
            effects=effects,
            fence=latest(),
        )
    settlement_state = settlement_result.value
    if settlement_state is None or settlement_state.quota_spend is None:
        raise ValueError("typed Turn settlement completed without a quota spend receipt")
    completed = list(settlement_state.completed_phases)
    state["completed_phases"] = completed
    if not state.get("settlement_recorded"):
        state["settlement_recorded"] = True
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="settlement_completed",
            phase_key=f"{turn_key}:settlement:completed",
            phase="quota_spend",
            fence=latest(),
            state=state,
        )

    scheduler_payload = (
        state.get("scheduler")
        if "scheduler_apply" in completed and isinstance(state.get("scheduler"), dict)
        else None
    )
    if scheduler_payload is None:
        scheduler_payload = _guarded_effect(
            controller=controller,
            latest=latest,
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            phase="scheduler_apply",
            invoke=lambda envelope: _call_compatible(
                scheduler,
                (envelope, dict(settlement_state.quota_spend)),
                (dict(settlement_state.quota_spend),),
            ),
        )
        state["scheduler"] = scheduler_payload
        if scheduler_payload.get("completed") is not True:
            state.update(
                status="scheduler_action_required",
                receipt=_receipt(plan, result, completed_phases=completed),
            )
            _append_state(
                runtime_root=runtime_root,
                goal_id=goal_id,
                turn_key=turn_key,
                event_type="phase_pending",
                phase_key=_unique_phase_key(
                    runtime_root,
                    goal_id=goal_id,
                    turn_key=turn_key,
                    prefix="scheduler_apply:pending",
                ),
                phase="scheduler_apply",
                fence=latest(),
                state=state,
            )
            return _public_payload(
                plan,
                state,
                execute=True,
                replayed=False,
                effects=effects,
                fence=latest(),
            )
        completed = list(TRANSACTION_PHASES[:6])
        state["completed_phases"] = completed
        effects["scheduler_acknowledged"] = bool(
            scheduler_payload.get("acknowledged")
        )
        _append_state(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type="phase_completed",
            phase_key=f"{turn_key}:scheduler_apply:completed",
            phase="scheduler_apply",
            fence=latest(),
            state=state,
        )
        _fault(fault_injector, "after_scheduler_apply")

    completed = list(TRANSACTION_PHASES)
    state.update(
        status="committed",
        completed_phases=completed,
        receipt=_receipt(plan, result, completed_phases=completed),
    )
    _append_state(
        runtime_root=runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
        event_type="phase_completed",
        phase_key=f"{turn_key}:scheduler_ack:completed",
        phase="scheduler_ack",
        fence=latest(),
        state=state,
    )
    return _public_payload(
        plan,
        state,
        execute=True,
        replayed=False,
        effects=effects,
        fence=latest(),
    )


def run_fenced_loopx_turn_once(
    plan: Mapping[str, Any],
    *,
    host_argv: Sequence[str] | None = None,
    host_runner: HostRunner | None = None,
    project: Path,
    runtime_root: Path,
    goal_id: str,
    timeout_seconds: float,
    execute: bool,
    retry_failed: bool = False,
    task_validator: TaskValidator | None = None,
    writeback: Writeback | None = None,
    completion_writeback: CompletionWriteback | None = None,
    spend: Spend | None = None,
    scheduler: Scheduler | None = None,
    lease_controller: TurnLeaseController | None = None,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    if host_runner is not None and host_argv is not None:
        raise ValueError("run-once accepts either host_argv or host_runner, not both")
    if host_runner is None:
        argv = normalize_host_argv(host_argv or [])
        host_projection = {"executable": Path(argv[0]).name, "argv_count": len(argv)}
    else:
        argv = None
        planned_host = plan.get("host") if isinstance(plan.get("host"), dict) else {}
        host_projection = {
            "executable": "built-in",
            "kind": str(planned_host.get("kind") or "codex-cli"),
        }
    request = build_loopx_turn_host_request(plan)
    effects = {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    if not execute:
        preview = {
            "schema_version": LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
            "status": "preview",
            "host": host_projection,
            "result_kind": None,
            "receipt": None,
            "scheduler": {"disposition": "not_evaluated"},
        }
        return _public_payload(
            plan,
            preview,
            execute=False,
            replayed=False,
            effects=effects,
            fence=None,
        )
    if writeback is None or spend is None or scheduler is None:
        raise ValueError(
            "executing run-once requires writeback, spend, and scheduler callbacks"
        )
    turn_key = str(request["turn_key"])
    try:
        prior = load_turn_state(runtime_root, goal_id=goal_id, turn_key=turn_key)
    except TurnJournalError as exc:
        return _failed_closed_payload(
            plan,
            None,
            reason=str(exc),
            reason_code="journal_invariant_failed",
            effects=effects,
            fence=None,
        )
    if prior is not None and (
        prior.get("status") in {"committed", "stopped"}
        or prior.get("status") == "failed" and not retry_failed
    ):
        return _public_payload(
            plan,
            prior,
            execute=True,
            replayed=True,
            effects=effects,
            fence=None,
        )
    if lease_controller is None:
        raise ValueError("executing run-once requires a Turn lease controller")
    fence: TurnFence | None = None
    final_fence: TurnFence | None = None
    try:
        fence = lease_controller.acquire()
        with lease_controller.heartbeat(fence) as latest:
            payload = _execute_fenced(
                plan,
                request=request,
                host_projection=host_projection,
                argv=argv,
                host_runner=host_runner,
                project=project,
                runtime_root=runtime_root,
                goal_id=goal_id,
                timeout_seconds=timeout_seconds,
                retry_failed=retry_failed,
                task_validator=task_validator,
                writeback=writeback,
                completion_writeback=completion_writeback,
                spend=spend,
                scheduler=scheduler,
                controller=lease_controller,
                fence=fence,
                latest=latest,
                fault_injector=fault_injector,
                effects=effects,
            )
        final_fence = latest()
    except TaskLeaseError as exc:
        return _failed_closed_payload(
            plan,
            prior,
            reason=str(exc),
            reason_code=exc.code,
            effects=effects,
            fence=fence,
        )
    except TurnJournalError as exc:
        return _failed_closed_payload(
            plan,
            prior,
            reason=str(exc),
            reason_code="journal_invariant_failed",
            effects=effects,
            fence=fence,
        )
    if payload.get("status") in {"committed", "stopped"} and final_fence is not None:
        try:
            lease_controller.release(final_fence)
        except TaskLeaseError as exc:
            payload["lease_release"] = {
                "released": False,
                "reason_code": exc.code,
            }
        else:
            payload["lease_release"] = {"released": True}
    return payload
