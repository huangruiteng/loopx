from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from hashlib import sha256
from typing import Any

from ..quota.turn_envelope import turn_envelope_action_signature_document
from ..scheduler.execution_context import (
    scheduler_execution_context_for_turn,
)
from .transaction import build_loopx_turn_transaction_plan


LOOPX_TURN_PLAN_SCHEMA_VERSION = "loopx_turn_plan_v0"
LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION = "loopx_turn_session_binding_v0"
LOOPX_CHILD_HOST_OPERATION_SCHEMA_VERSION = "loopx_child_host_operation_v0"
TURN_ENVELOPE_SCHEMA_VERSION = "loopx_turn_envelope_v0"
SUPPORTED_HOSTS = {"codex-cli", "claude-code", "generic-cli"}
SUPPORTED_EXECUTION_MODES = {"interactive-visible", "isolated-headless"}
HOST_CHILD_CONTEXT_OPERATIONS = {
    "codex-cli": {
        "fresh": ("spawn_agent", False),
        "resume": ("resume_agent", True),
    },
    "claude-code": {
        "fresh": ("Task", False),
    },
}
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


def selected_turn_todo(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the todo that owns one Turn across adaptive bundle execution."""

    action = _mapping(envelope.get("action"))
    action_selected_todo = _mapping(action.get("selected_todo"))
    orchestration = _mapping(envelope.get("task_orchestration_contract"))
    primary_todo_id = str(orchestration.get("primary_todo_id") or "").strip()
    if (
        orchestration.get("schema_version") == "task_orchestration_contract_v2"
        and orchestration.get("mode") == "adaptive"
        and primary_todo_id
    ):
        primary_todo = _mapping(orchestration.get("primary_todo"))
        if str(primary_todo.get("todo_id") or "") == primary_todo_id:
            return {
                **primary_todo,
                "source": "task_orchestration_contract.primary_todo",
            }
        if str(action_selected_todo.get("todo_id") or "") == primary_todo_id:
            return action_selected_todo
        return {
            "todo_id": primary_todo_id,
            "source": "task_orchestration_contract.primary_todo_id",
        }
    return action_selected_todo


def selected_turn_todo_write_scopes(
    selected_todo: Mapping[str, Any],
) -> list[str]:
    """Return the selected Todo's normalized lease scope projection."""

    raw_write_scopes = selected_todo.get("required_write_scopes")
    if raw_write_scopes is None:
        if (
            selected_todo.get("source")
            == "task_orchestration_contract.primary_todo_id"
        ):
            raise ValueError(
                "adaptive primary todo must project required_write_scopes"
            )
        return []
    if not isinstance(raw_write_scopes, list) or not all(
        isinstance(scope, str) for scope in raw_write_scopes
    ):
        raise ValueError("selected todo required_write_scopes must be a string array")
    return list(raw_write_scopes)


def _turn_lineage(
    envelope: Mapping[str, Any],
    *,
    selected_todo: Mapping[str, Any],
) -> dict[str, str]:
    signature_document = turn_envelope_action_signature_document(envelope)
    action = _mapping(signature_document.get("action"))
    signature_document["action"] = {
        **action,
        "selected_todo": dict(selected_todo),
    }
    action_hash = "sha256:" + sha256(
        json.dumps(
            signature_document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "goal_id": str(envelope.get("goal_id") or ""),
        "agent_id": str(envelope.get("agent_id") or ""),
        "todo_id": str(selected_todo.get("todo_id") or ""),
        "action_hash": action_hash,
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


def _child_host_operations(
    envelope: Mapping[str, Any],
    *,
    host: str,
) -> list[dict[str, Any]]:
    orchestration = _mapping(envelope.get("task_orchestration_contract"))
    if (
        orchestration.get("schema_version") != "task_orchestration_contract_v2"
        or orchestration.get("mode") != "adaptive"
    ):
        return []
    lanes = orchestration.get("eligible_child_lanes")
    if not isinstance(lanes, list):
        return []
    brief_defaults = _mapping(orchestration.get("child_brief_defaults"))
    if brief_defaults.get("schema_version") != "subagent_control_plane_handoff_v0":
        return []
    operations = HOST_CHILD_CONTEXT_OPERATIONS.get(host, {})
    child_operations: list[dict[str, Any]] = []
    for lane in lanes:
        if not isinstance(lane, Mapping):
            continue
        brief = {**brief_defaults, **_mapping(lane.get("child_brief"))}
        brief["evidence_boundary"] = {
            "task_domain": brief.get("task_domain"),
            "task_repository": brief.get("task_repository"),
            "required_write_scopes": list(brief.get("required_write_scopes") or []),
        }
        context_policy = _mapping(brief.get("context_policy"))
        recommended = str(context_policy.get("default") or "fresh")
        allowed_contexts = context_policy.get("allowed")
        if not isinstance(allowed_contexts, list):
            allowed_contexts = [recommended]
        available_contexts = [
            {
                "context": context,
                "native_operation": operations[context][0],
                "requires_session": operations[context][1],
            }
            for context in allowed_contexts
            if context in operations
        ]
        if not available_contexts:
            continue
        if recommended not in {item["context"] for item in available_contexts}:
            recommended = str(available_contexts[0]["context"])
        child_operations.append(
            {
                "schema_version": LOOPX_CHILD_HOST_OPERATION_SCHEMA_VERSION,
                "todo_id": str(lane.get("todo_id") or "") or None,
                "host": host,
                "selection_owner": "task_coordinator",
                "recommended_context": recommended,
                "available_contexts": available_contexts,
                "brief": brief,
                "result_channel": "public_safe_typed_evidence",
                "writeback_owner": str(
                    orchestration.get("writeback_owner") or "task_coordinator"
                ),
            }
        )
    return child_operations


def build_loopx_turn_plan(
    turn_envelope: Mapping[str, Any],
    *,
    host: str,
    execution_mode: str,
    scheduler_owner: str | None = None,
    session_binding: Mapping[str, Any] | None = None,
    turn_instance_id: str | None = None,
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
    selected_todo = selected_turn_todo(envelope)
    lineage = _turn_lineage(envelope, selected_todo=selected_todo)
    session, session_error = _session_plan(
        route=route,
        lineage=lineage,
        session_binding=session_binding,
    )
    if session_error:
        route = LoopXTurnRoute.CONTRACT_ERROR
    would_invoke_host = route in {
        LoopXTurnRoute.READY_FOR_HOST,
        LoopXTurnRoute.REPAIR_REQUIRED,
        LoopXTurnRoute.REPLAN_REQUIRED,
    }
    child_operations = (
        _child_host_operations(envelope, host=host) if would_invoke_host else []
    )
    context_projection = execution_context.projection()
    payload = {
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
            turn_instance_id=turn_instance_id,
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
    if child_operations:
        payload["child_operations"] = child_operations
    return payload
