from __future__ import annotations

import json
from enum import StrEnum


class QuotaCommandValidationError(ValueError):
    """Public-safe diagnostic for an invalid ``loopx quota`` invocation."""


class HeartbeatReceiptIdentityConflictError(ValueError):
    """Public-safe diagnostic for a same-turn settlement identity conflict."""


class QuotaIdentityPrecondition(StrEnum):
    """Typed identity admission preconditions for scoped quota decisions."""

    PUBLIC_SAFE_AGENT_ID = "public_safe_agent_id"
    REGISTERED_AGENT_ROSTER_PRESENT = "registered_agent_roster_present"
    REQUESTED_AGENT_REGISTERED = "requested_agent_registered"


class QuotaIdentityPreconditionError(ValueError):
    """Public-safe failure raised before a scoped quota decision can be built."""

    def __init__(
        self,
        precondition: QuotaIdentityPrecondition,
        *,
        agent_id: str | None = None,
    ) -> None:
        self.precondition = precondition
        self.agent_id = agent_id
        if precondition is QuotaIdentityPrecondition.PUBLIC_SAFE_AGENT_ID:
            self.error_code = "quota_agent_id_invalid"
            self.recommended_action = (
                "use a public-safe agent id registered in the selected registry, "
                "then retry"
            )
            reason = "agent_id must be a public-safe registered agent id"
        elif precondition is QuotaIdentityPrecondition.REGISTERED_AGENT_ROSTER_PRESENT:
            self.error_code = "quota_agent_registry_roster_missing"
            self.recommended_action = (
                "register this agent in coordination.registered_agents of the "
                "selected registry, then rerun quota should-run with the same "
                "--registry and --agent-id"
            )
            reason = "selected registry goal is missing coordination.registered_agents"
        else:
            self.error_code = "quota_agent_not_registered"
            self.recommended_action = (
                "register this agent in coordination.registered_agents of the "
                "selected registry, then rerun quota should-run with the same "
                "--registry and --agent-id"
            )
            reason = (
                f"agent_id={agent_id!r} is not registered in the selected registry goal"
            )
        super().__init__(reason)


class QuotaActionSelectionConflictKind(StrEnum):
    """Why a requested ``--todo-id`` could not be reconciled with the projection."""

    UNQUALIFIED = "unqualified"
    CONFLICT = "conflict"


class QuotaActionSelectionConflictError(RuntimeError):
    """Public-safe diagnostic for an unreconcilable requested action selection.

    A guard bound to a ``--todo-id`` has to agree with the current projection.
    When it cannot, this error names what was requested, what the projection
    currently selects, and what the caller should do next, so the failure is not
    reported as an opaque quota collection failure.
    """

    error_code = "quota_action_selection_conflict"

    def __init__(
        self,
        kind: QuotaActionSelectionConflictKind,
        *,
        requested_todo_id: str | None,
        selected_todo_id: str | None = None,
        qualification_state: str | None = None,
    ) -> None:
        self.kind = kind
        self.requested_todo_id = requested_todo_id
        self.selected_todo_id = selected_todo_id
        self.qualification_state = qualification_state
        if kind is QuotaActionSelectionConflictKind.UNQUALIFIED:
            reason = (
                "the current projection carries no typed action-selection "
                "qualification, so the requested Todo "
                f"{requested_todo_id or '(none)'} cannot be reconciled with the "
                "delivery frontier"
            )
        else:
            reason = (
                f"requested Todo {requested_todo_id or '(none)'} is neither the "
                "projection's current selection "
                f"({selected_todo_id or 'none'}) nor deferred or rejected by it "
                f"(qualification state: {qualification_state or 'absent'})"
            )
        self.recommended_action = (
            "rerun `loopx quota should-run` without --todo-id to read the current "
            "selection, then bind that Todo, a deferred Todo, or the Todo the "
            "recovery obligation must settle"
        )
        super().__init__(reason)


def quota_error_code(exc: BaseException) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "quota_state_invalid_json"
    if isinstance(exc, QuotaCommandValidationError):
        return "quota_invalid_arguments"
    if isinstance(exc, QuotaIdentityPreconditionError):
        return exc.error_code
    if isinstance(exc, QuotaActionSelectionConflictError):
        return exc.error_code
    if isinstance(exc, HeartbeatReceiptIdentityConflictError):
        return "heartbeat_receipt_identity_conflict"
    if isinstance(exc, PermissionError):
        return "quota_state_permission_denied"
    if isinstance(exc, OSError):
        return "quota_state_io_failed"
    if isinstance(exc, KeyError):
        return "quota_state_missing_field"
    if isinstance(exc, TypeError):
        return "quota_state_shape_error"
    return "quota_unexpected_collection_error"
