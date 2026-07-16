from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from ..scheduler.execution_context import scheduler_execution_context_for_turn
from .transaction import build_loopx_turn_transaction_plan


LOOPX_TURN_PLAN_SCHEMA_VERSION = "loopx_turn_plan_v0"
LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION = "loopx_turn_session_binding_v0"
TURN_ENVELOPE_SCHEMA_VERSION = "loopx_turn_envelope_v0"
SUPPORTED_HOSTS = {"codex-cli", "claude-code", "generic-cli"}
SUPPORTED_EXECUTION_MODES = {"interactive-visible", "isolated-headless"}
REPLAN_ACTIONS = {
    "autonomous_replan",
    "autonomous_replan_required",
    "successor_replan_required",
}
REPAIR_ACTIONS = {
    "capability_repair",
    "projection_repair",
    "self_repair",
    "state_projection_repair",
    "workspace_repair",
}


class LoopXTurnRoute(str, Enum):
    READY_FOR_HOST = "ready_for_host"
    REPAIR_REQUIRED = "repair_required"
    REPLAN_REQUIRED = "replan_required"
    USER_ACTION_REQUIRED = "user_action_required"
    WAIT = "wait"
    BLOCKED = "blocked"
    CONTRACT_ERROR = "contract_error"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _typed_route(envelope: Mapping[str, Any]) -> LoopXTurnRoute:
    if envelope.get("schema_version") != TURN_ENVELOPE_SCHEMA_VERSION:
        return LoopXTurnRoute.CONTRACT_ERROR
    signature = _mapping(envelope.get("action_signature"))
    source_hash = str(signature.get("source_hash") or "")
    envelope_hash = str(signature.get("envelope_hash") or "")
    if (
        signature.get("matches") is not True
        or not source_hash
        or source_hash != envelope_hash
    ):
        return LoopXTurnRoute.CONTRACT_ERROR
    compaction = _mapping(envelope.get("compaction"))
    if compaction.get("within_budget") is not True:
        return LoopXTurnRoute.CONTRACT_ERROR

    action = _mapping(envelope.get("action"))
    user = _mapping(envelope.get("user"))
    should_run = envelope.get("should_run") is True
    effective_action = str(envelope.get("effective_action") or "")
    delivery_allowed = action.get("delivery_allowed") is True
    must_attempt = action.get("must_attempt") is True

    if should_run:
        if not delivery_allowed or not must_attempt:
            return LoopXTurnRoute.BLOCKED
        if effective_action in REPLAN_ACTIONS:
            return LoopXTurnRoute.REPLAN_REQUIRED
        if effective_action in REPAIR_ACTIONS or effective_action.endswith(
            ("_repair", "_repair_required")
        ):
            return LoopXTurnRoute.REPAIR_REQUIRED
        return LoopXTurnRoute.READY_FOR_HOST
    if user.get("action_required") is True:
        return LoopXTurnRoute.USER_ACTION_REQUIRED
    if action.get("quiet_noop_allowed") is True:
        return LoopXTurnRoute.WAIT
    return LoopXTurnRoute.BLOCKED


def _turn_lineage(envelope: Mapping[str, Any]) -> dict[str, str]:
    action = _mapping(envelope.get("action"))
    selected_todo = _mapping(action.get("selected_todo"))
    signature = _mapping(envelope.get("action_signature"))
    return {
        "goal_id": str(envelope.get("goal_id") or ""),
        "agent_id": str(envelope.get("agent_id") or ""),
        "todo_id": str(selected_todo.get("todo_id") or ""),
        "action_hash": str(signature.get("source_hash") or ""),
    }


def _session_plan(
    *,
    route: LoopXTurnRoute,
    lineage: Mapping[str, str],
    session_binding: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    host_route = route in {
        LoopXTurnRoute.READY_FOR_HOST,
        LoopXTurnRoute.REPAIR_REQUIRED,
        LoopXTurnRoute.REPLAN_REQUIRED,
    }
    if not host_route:
        return {
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "action": "none",
            "binding_status": "not_applicable",
        }, None
    if not all(lineage.values()):
        return {
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "action": "reject",
            "binding_status": "missing_turn_lineage",
        }, "host-bound routes require goal, agent, todo, and action-hash lineage"

    binding = dict(session_binding or {})
    if not binding:
        return {
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "action": "start_new",
        }, None
    if binding.get("schema_version") != LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION:
        return {
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "action": "reject",
            "binding_status": "unsupported_schema",
        }, "unsupported LoopX Turn session binding schema"

    identity_fields = ("goal_id", "agent_id", "todo_id")
    actual = {field: str(binding.get(field) or "") for field in identity_fields}
    expected = {field: lineage[field] for field in identity_fields}
    if actual != expected:
        return {
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "action": "reject",
            "binding_status": "identity_mismatch",
        }, "session binding does not match the current goal, agent, and todo"
    return {
        "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
        "action": "resume",
    }, None


def build_loopx_turn_plan(
    turn_envelope: Mapping[str, Any],
    *,
    host: str,
    execution_mode: str,
    scheduler_owner: str | None = None,
    session_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project a TurnEnvelope into a typed, side-effect-free host decision."""

    if host not in SUPPORTED_HOSTS:
        raise ValueError(f"unsupported LoopX Turn host: {host}")
    if execution_mode not in SUPPORTED_EXECUTION_MODES:
        raise ValueError(f"unsupported LoopX Turn execution mode: {execution_mode}")

    execution_context = scheduler_execution_context_for_turn(
        host=host,
        execution_mode=execution_mode,
        scheduler_owner=scheduler_owner,
    )
    envelope = dict(turn_envelope)
    route = (
        _typed_route(envelope)
        if execution_context.ok
        else LoopXTurnRoute.CONTRACT_ERROR
    )
    lineage = _turn_lineage(envelope)
    session, session_error = _session_plan(
        route=route,
        lineage=lineage,
        session_binding=session_binding,
    )
    if session_error:
        route = LoopXTurnRoute.CONTRACT_ERROR
    action = _mapping(envelope.get("action"))
    selected_todo = _mapping(action.get("selected_todo"))
    would_invoke_host = route in {
        LoopXTurnRoute.READY_FOR_HOST,
        LoopXTurnRoute.REPAIR_REQUIRED,
        LoopXTurnRoute.REPLAN_REQUIRED,
    }
    context_projection = execution_context.projection()
    return {
        "ok": route is not LoopXTurnRoute.CONTRACT_ERROR,
        "schema_version": LOOPX_TURN_PLAN_SCHEMA_VERSION,
        "mode": "plan",
        "host": {
            "kind": host,
            "execution_mode": execution_mode,
            "scheduler_owner": context_projection.get("scheduler_owner"),
            "explicit_isolation": execution_mode == "isolated-headless",
        },
        "scheduler_execution_context": context_projection,
        "session": session,
        "route": {
            "schema_version": "loopx_turn_route_v0",
            "kind": route.value,
            "effective_action": envelope.get("effective_action"),
            "would_invoke_host": would_invoke_host,
            "host_invocation_allowed": False,
            "selected_todo": selected_todo or None,
        },
        "turn_envelope": envelope,
        "transaction": build_loopx_turn_transaction_plan(
            planned=would_invoke_host,
            lineage=lineage,
            host=host,
            execution_mode=execution_mode,
            scheduler_owner=str(context_projection.get("scheduler_owner") or ""),
            session_action=str(session.get("action") or "none"),
        ),
        "effects": {
            "host_invoked": False,
            "state_written": False,
            "scheduler_acknowledged": False,
            "quota_spent": False,
        },
        "boundary": {
            "read_only": True,
            "requires_explicit_execute_surface": True,
            "preserves_turn_envelope": True,
            "opaque_session_handle_omitted": True,
        },
        **(
            {"error": session_error or "; ".join(execution_context.errors)}
            if session_error or not execution_context.ok
            else {}
        ),
    }
