"""Python adapter for provider-first local coordination reads.

TypeScript remains the semantic owner of canonical projection validation.  The
Python CLI only detects whether cutover is engaged, invokes that owner, and
fails closed instead of consulting the legacy Markdown projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...agent_registry import registered_agent_ids_from_registry
from ...state_refresh import now_local
from ..effect_runtime import effect_runtime_result
from .coordination_state_contract import (
    TODO_CANONICAL_READ_RECORD_SCHEMA_VERSION,
    TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION,
    TODO_DOMAIN_ITEM_SCHEMA_VERSION,
    TODO_ITEM_SCHEMA_VERSION,
)
from .coordination_state_contract_generated import (
    LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA,
)
from .legacy_writer_fence import legacy_coordination_writer_fence_path


LOCAL_COORDINATION_TODO_LIST_METHOD = "coordination.local_authority.todo_list"
LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA = (
    "loopx_local_coordination_todo_claim_request_v0"
)
LOCAL_COORDINATION_TODO_CLAIM_METHOD = "coordination.local_authority.todo_claim"


class LocalCoordinationAuthorityUnavailable(RuntimeError):
    """Canonical coordination state cannot safely answer a post-cutover read."""

    def __init__(self, message: str, *, code: str, payload: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.code = code
        self.payload = dict(payload)


class LocalCoordinationAuthorityRejection(LocalCoordinationAuthorityUnavailable, ValueError):
    """The TypeScript coordination owner definitively rejected a claim.

    The legacy Python kernel raised ``ValueError`` for every claim rejection
    (todo_not_open, claim_owner_mismatch, unregistered actor, ...).  After
    promotion those rejections surface as ``status="failed"`` results from the
    TypeScript transaction owner; re-raising them through this class keeps the
    legacy ``except ValueError`` contract intact for Python API callers while
    remaining catchable as an authority outage.  Infrastructure and protocol
    failures keep raising :class:`LocalCoordinationAuthorityUnavailable`, which
    is not a ``ValueError``.
    """

    def __init__(self, message: str, *, code: str, payload: Mapping[str, Any]) -> None:
        super().__init__(message, code=code, payload=payload)


def local_authority_is_promoted(*, runtime_root: Path, goal_id: str) -> bool:
    fence_path = legacy_coordination_writer_fence_path(
        runtime_root=runtime_root,
        goal_id=goal_id,
    )
    try:
        fence_path.stat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise LocalCoordinationAuthorityUnavailable(
            "local coordination authority mode cannot be inspected",
            code="local_authority_mode_read_failed",
            payload={"source_authority": "unknown_fail_closed"},
        ) from exc
    return True


def claim_canonical_todo_if_promoted(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    role: str | None,
    claimed_by: str,
    actor_agent_id: str | None,
    dry_run: bool,
    operation_id: str | None = None,
) -> dict[str, Any] | None:
    """Route a post-cutover claim to the TypeScript transaction owner."""

    if not local_authority_is_promoted(runtime_root=runtime_root, goal_id=goal_id):
        return None
    result = effect_runtime_result(
        LOCAL_COORDINATION_TODO_CLAIM_METHOD,
        {
            "schema_version": LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA,
            "runtime_root": str(runtime_root.expanduser().resolve(strict=False)),
            "goal_id": goal_id,
            "todo_id": todo_id,
            "role": role,
            "claimed_by": claimed_by,
            "actor_agent_id": actor_agent_id,
            "registered_agents": registered_agent_ids_from_registry(
                registry_path, goal_id
            ),
            "operation_id": operation_id if operation_id is not None else f"todo-claim:{goal_id}:{todo_id}:{uuid4().hex}",
            "observed_at": now_local(),
            "dry_run": dry_run,
        },
    )
    if not isinstance(result, Mapping):
        raise LocalCoordinationAuthorityUnavailable(
            "local coordination authority returned an invalid Todo claim result",
            code="local_authority_todo_claim_invalid_result",
            payload={"source_authority": "file_v0"},
        )
    payload = dict(result)
    accepted = {"applied", "recovered", "replayed", "no_change", "planned"}
    if (
        payload.get("status") == "failed"
        and payload.get("reason_code") != "invalid_local_coordination_todo_claim_request"
    ):
        # The TypeScript owner returned a definitive decision rejection. The
        # legacy kernel raised ValueError for the same rejections, so keep that
        # caller-observable contract; the wrapper error code is a protocol
        # failure and stays an infrastructure outage instead.
        raise LocalCoordinationAuthorityRejection(
            str(payload.get("reason") or "canonical Todo claim was rejected"),
            code=str(payload.get("reason_code") or "claim_rejected"),
            payload=payload,
        )
    if (
        payload.get("status") not in accepted
        or payload.get("source_authority") != "file_v0"
        or payload.get("decision_read_from_provider") is not True
        or payload.get("legacy_fallback_used") is not False
    ):
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical Todo claim failed"),
            code=str(payload.get("reason_code") or "local_authority_todo_claim_failed"),
            payload=payload,
        )
    return {
        "ok": True,
        "dry_run": dry_run,
        "goal_id": goal_id,
        "role": "agent",
        "section": "Agent Todo",
        "todo_id": todo_id,
        **payload,
    }


def read_canonical_todos_if_promoted(
    *, runtime_root: Path, goal_id: str
) -> dict[str, Any] | None:
    """Return canonical Todos after cutover, or ``None`` before cutover.

    Presence of the durable writer fence is the mode switch. Once present,
    every malformed, missing, or unavailable provider response is terminal for
    this read; callers must never recover by reading Markdown.
    """

    if not local_authority_is_promoted(runtime_root=runtime_root, goal_id=goal_id):
        return None

    result = effect_runtime_result(
        LOCAL_COORDINATION_TODO_LIST_METHOD,
        {
            "schema_version": LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA,
            "runtime_root": str(runtime_root.expanduser().resolve(strict=False)),
            "goal_id": goal_id,
        },
    )
    if not isinstance(result, Mapping):
        raise LocalCoordinationAuthorityUnavailable(
            "local coordination authority returned an invalid Todo list",
            code="local_authority_todo_list_invalid_result",
            payload={"source_authority": "file_v0"},
        )
    payload = dict(result)
    todos = payload.get("todos")
    todo_read_model = payload.get("todo_read_model")
    if (
        payload.get("status") != "loaded"
        or payload.get("source_authority") != "file_v0"
        or payload.get("decision_read_from_provider") is not True
        or payload.get("legacy_fallback_used") is not False
        or not isinstance(todos, list)
        or any(not isinstance(item, Mapping) for item in todos)
        or not isinstance(todo_read_model, Mapping)
        or todo_read_model.get("schema_version")
        not in {
            TODO_CANONICAL_READ_RECORD_SCHEMA_VERSION,
            TODO_DOMAIN_READ_RECORD_SCHEMA_VERSION,
        }
        or todo_read_model.get("todo_count") != len(todos)
    ):
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical Todo authority is unavailable"),
            code=str(payload.get("reason_code") or "local_authority_todo_list_unavailable"),
            payload=payload,
        )
    payload["todos"] = [dict(item) for item in todos]
    return payload


def canonical_todo_summary_fields(
    todos: list[dict[str, Any]],
    *,
    rollout_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Adapt canonical records into the existing Todo summary read model."""

    from ..todos.active_state_editing import TODO_SECTION_HEADINGS
    from ..todos.todo_summary import compact_todo_group, count_advancement_todos

    native_archived = {
        item["todo_id"] for item in todos
        if item.get("schema_version") == TODO_DOMAIN_ITEM_SCHEMA_VERSION
        and item.get("archive_state") == "archive"
    }
    # Native provider records have no Markdown address. Allocate display
    # positions from stable provider order; never read legacy Markdown here.
    todos = [
        {
            **item,
            "schema_version": TODO_ITEM_SCHEMA_VERSION,
            "source_section": (
                "Completed Work Archive" if item["archive_state"] == "archive"
                else TODO_SECTION_HEADINGS[item["role"]]
            ),
            "index": index,
        }
        if item.get("schema_version") == TODO_DOMAIN_ITEM_SCHEMA_VERSION else item
        for index, item in enumerate(todos, 1)
    ]
    fields: dict[str, Any] = {}
    for role in ("user", "agent"):
        items = [
            item
            for item in todos
            if ("user" if item.get("role") == "user" else "agent") == role
            and item.get("todo_id") not in native_archived
        ]
        summary = compact_todo_group(
            items,
            source_section=TODO_SECTION_HEADINGS[role],
            role=role,
            resume_source_items=todos,
            rollout_events=rollout_events,
            item_limit=None,
        )
        if summary:
            if role == "agent":
                archived_done = count_advancement_todos([
                    item for item in todos
                    if item.get("todo_id") in native_archived and item.get("done") is True
                ])
                if archived_done:
                    summary["archived_advancement_done_count"] = archived_done
                    summary["advancement_done_count"] = (
                        int(summary.get("advancement_done_count") or 0) + archived_done
                    )
            fields[f"{role}_todos"] = summary
    return fields
