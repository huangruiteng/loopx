"""Provider-first Todo create bridge for a promoted local authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from ...agent_registry import registered_agent_ids_from_registry
from ...state_refresh import now_local
from ..coordination.local_authority import (
    LOCAL_AUTHORITY_SOURCES,
    LocalCoordinationAuthorityUnavailable,
    read_canonical_todos_if_promoted,
)
from ..effect_runtime import effect_runtime_result
from .contract import (
    build_todo_id,
    normalize_todo_metadata_for_write,
    normalize_todo_task_class,
    todo_done_for_status,
)
from .completion_validation_projection import (
    completion_validation_declaration,
    completion_validation_declaration_sha256,
    project_completion_validation_authority,
)
from .completion_validation_store import (
    persist_completion_validation_declaration,
    read_completion_validation_declaration,
)
from .provider_projection import settle_canonical_todo_projection


def create_canonical_todo_if_promoted(
    *, registry_path: Path, runtime_root: Path, goal_id: str, role: str,
    text: str, status: str, actor_agent_id: str | None,
    claimed_by: str | None, metadata: dict[str, Any], dry_run: bool,
    project: Path | None = None, state_file: Path | None = None,
) -> dict[str, Any] | None:
    canonical = read_canonical_todos_if_promoted(
        runtime_root=runtime_root, goal_id=goal_id
    )
    if canonical is None:
        return None
    section = "Agent Todo" if role == "agent" else "User Todo"
    same_role_count = sum(1 for item in canonical["todos"] if item["role"] == role)
    todo_id = build_todo_id(
        role=role, source_section=section, index=same_role_count + 1, text=text
    )
    normalized_metadata = normalize_todo_metadata_for_write(metadata)
    validation_source = {
        **normalized_metadata,
        **{
            field: metadata[field]
            for field in (
                "validation_command",
                "validation_command_argv",
                "validation_label",
                "validation_timeout_seconds",
            )
            if field in metadata
        },
    }
    validation_declaration = completion_validation_declaration(validation_source)
    provider_metadata = project_completion_validation_authority(validation_source)
    todo = {
        "schema_version": "todo_domain_record_v0",
        "todo_id": todo_id,
        "role": role,
        "status": status,
        "done": todo_done_for_status(status),
        "text": text,
        "archive_state": "active",
        "task_class": normalize_todo_task_class(
            provider_metadata.get("task_class"), text=text,
            action_kind=provider_metadata.get("action_kind"),
        ),
        **provider_metadata,
        **({"claimed_by": claimed_by} if claimed_by else {}),
    }
    result = effect_runtime_result(
        "coordination.local_authority.todo_create",
        {
            "schema_version": "loopx_local_coordination_todo_create_request_v0",
            "runtime_root": str(runtime_root.resolve()),
            "goal_id": goal_id,
            "todo": todo,
            "actor_agent_id": actor_agent_id,
            "registered_agents": registered_agent_ids_from_registry(
                registry_path, goal_id
            ),
            "operation_id": f"todo-create:{uuid4().hex}",
            "dry_run": dry_run,
            "observed_at": now_local(),
        },
    )
    if not isinstance(result, dict) or result.get("status") not in {
        "applied", "recovered", "replayed", "no_change", "planned",
    } or result.get("source_authority") not in LOCAL_AUTHORITY_SOURCES or (
        result.get("decision_read_from_provider") is not True
        or result.get("legacy_fallback_used") is not False
    ):
        payload = result if isinstance(result, dict) else {}
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical Todo create failed; reread before retry"),
            code=str(payload.get("reason_code") or payload.get("conflict_kind")
                     or "todo_create_failed"), payload=payload,
        )
    canonical_todo_id = str(result.get("todo_id") or "")
    canonical_todo = result.get("todo")
    if validation_declaration is not None and not dry_run:
        expected_digest = completion_validation_declaration_sha256(
            validation_declaration
        )
        if (
            not canonical_todo_id
            or not isinstance(canonical_todo, dict)
            or canonical_todo.get("todo_id") != canonical_todo_id
            or canonical_todo.get("completion_validation_required") is not True
            or canonical_todo.get("completion_validation_sha256") != expected_digest
        ):
            raise LocalCoordinationAuthorityUnavailable(
                "accepted canonical Todo does not match its private validation declaration",
                code="todo_create_validation_publication_mismatch",
                payload={
                    "source_authority": "file_v0",
                    "goal_id": goal_id,
                    "todo_id": canonical_todo_id or None,
                    "provider_status": result.get("status"),
                },
            )
        persist_completion_validation_declaration(
            runtime_root=runtime_root,
            goal_id=goal_id,
            todo_id=canonical_todo_id,
            declaration=validation_declaration,
        )
        if read_completion_validation_declaration(
            runtime_root=runtime_root,
            goal_id=goal_id,
            todo_id=canonical_todo_id,
        ) != validation_declaration:
            raise LocalCoordinationAuthorityUnavailable(
                "accepted Todo validation declaration failed private-store readback",
                code="todo_create_validation_publication_readback_mismatch",
                payload={
                    "source_authority": "file_v0",
                    "goal_id": goal_id,
                    "todo_id": canonical_todo_id,
                    "provider_status": result.get("status"),
                },
            )
    settled = settle_canonical_todo_projection({
        "ok": True,
        "goal_id": goal_id,
        "role": role,
        "todo_id": canonical_todo_id or todo_id,
        "todo": text,
        "dry_run": dry_run,
        "added": result.get("changed") is True,
        "already_exists": result.get("changed") is not True,
        **result,
    }, registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id,
        project=project, state_file=state_file)
    return cast(dict[str, Any], settled)
