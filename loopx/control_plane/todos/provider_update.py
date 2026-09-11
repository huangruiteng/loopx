"""Input transport for the native update transaction, never a Markdown editor.

The provider owns target lookup, planning, authority and CAS at one revision.
This adapter preserves CLI text encoding and drains the committed projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ...agent_registry import registered_agent_ids_from_registry
from ...state_refresh import now_local
from ..coordination.local_authority import (
    LOCAL_AUTHORITY_SOURCES,
    LocalCoordinationAuthorityUnavailable,
    local_authority_is_promoted,
)
from ..effect_runtime import effect_runtime_result
from .contract import compact_todo_text
from .provider_projection import settle_canonical_todo_projection
from .text import normalize_new_todo


def update_canonical_todo_if_promoted(
    *, registry_path: Path, runtime_root: Path, goal_id: str, todo_id: str,
    actor_agent_id: str | None, role: str | None, text: str | None,
    note: str | None, dry_run: bool,
    project: Path | None = None, state_file: Path | None = None,
    operation_id: str | None = None, task_lease_idempotency_key: str | None = None,
    task_lease_expected_version: int | None = None,
    planning_intent: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not local_authority_is_promoted(runtime_root=runtime_root, goal_id=goal_id):
        return None
    patch: dict[str, Any] = {}
    if text is not None:
        patch["text"] = normalize_new_todo(text)
    if note is not None:
        # Empty notes have always meant omission at the public update boundary.
        # Clearing a persisted note requires a future explicit contract; never
        # reinterpret an empty CLI/Python value as an implicit clear here.
        normalized_note = compact_todo_text(note)
        if normalized_note:
            patch["note"] = normalized_note
    result = effect_runtime_result("coordination.local_authority.todo_update", {
        "schema_version": ("loopx_local_coordination_todo_update_request_v1" if planning_intent
                           else "loopx_local_coordination_todo_update_request_v0"),
        "runtime_root": str(runtime_root.resolve()), "goal_id": goal_id,
        "todo_id": todo_id, "role": role, "actor_agent_id": actor_agent_id,
        "registered_agents": registered_agent_ids_from_registry(registry_path, goal_id),
        "operation_id": operation_id if operation_id is not None else f"todo-update:{uuid4().hex}",
        "lease_idempotency_key": task_lease_idempotency_key,
        "lease_expected_version": task_lease_expected_version,
        "patch": patch, "clear_fields": [], "dry_run": dry_run,
        "planning_intent": planning_intent or {},
        "observed_at": now_local(),
    })
    # Keep the public lookup-error contract, without a second pre-transaction read.
    if isinstance(result, dict) and result.get("status") == "failed":
        if result.get("reason_code") == "todo_not_found":
            raise ValueError("Todo is missing from canonical authority")
        if result.get("reason_code") == "todo_role_mismatch":
            raise ValueError("Todo does not have the requested role")
    if isinstance(result, dict) and (
        result.get("status") == "missing"
        and result.get("source_authority") in LOCAL_AUTHORITY_SOURCES
        and result.get("decision_read_from_provider") is True
        and result.get("legacy_fallback_used") is False
    ):
        payload = dict(result)
        payload["recovery"] = {
            "action": "restore_canonical_authority",
            "runtime_root": str(runtime_root.expanduser().resolve(strict=False)),
            "goal_id": goal_id,
            "legacy_markdown_fallback_allowed": False,
            "retry_after": "canonical_provider_readback_loaded",
        }
        raise LocalCoordinationAuthorityUnavailable(
            "canonical Todo authority is unavailable",
            code="local_authority_todo_list_unavailable",
            payload=payload,
        )
    if not isinstance(result, dict) or result.get("status") not in {
        "applied", "recovered", "replayed", "no_change", "planned",
    } or result.get("source_authority") not in LOCAL_AUTHORITY_SOURCES or (
        result.get("decision_read_from_provider") is not True
        or result.get("legacy_fallback_used") is not False
    ):
        payload = result if isinstance(result, dict) else {}
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical Todo update failed; reread before retry"),
            code=str(payload.get("reason_code") or payload.get("conflict_kind")
                     or "local_authority_todo_update_failed"), payload=payload,
        )
    return settle_canonical_todo_projection(
        {"ok": True, "goal_id": goal_id, "todo_id": todo_id,
         "role": "agent", "dry_run": dry_run, **result},
        registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id,
        project=project, state_file=state_file,
    )
