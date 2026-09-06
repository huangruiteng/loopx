"""Provider-first Todo create bridge for a promoted local authority."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from ...agent_registry import registered_agent_ids_from_registry
from ...state_refresh import now_local
from ..coordination.local_authority import (
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
    todo = {
        "schema_version": "todo_domain_record_v0",
        "todo_id": todo_id,
        "role": role,
        "status": status,
        "done": todo_done_for_status(status),
        "text": text,
        "archive_state": "active",
        "task_class": normalize_todo_task_class(
            normalized_metadata.get("task_class"), text=text,
            action_kind=normalized_metadata.get("action_kind"),
        ),
        **normalized_metadata,
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
    } or result.get("source_authority") != "file_v0" or (
        result.get("decision_read_from_provider") is not True
        or result.get("legacy_fallback_used") is not False
    ):
        payload = result if isinstance(result, dict) else {}
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical Todo create failed; reread before retry"),
            code=str(payload.get("reason_code") or payload.get("conflict_kind")
                     or "todo_create_failed"), payload=payload,
        )
    return settle_canonical_todo_projection({
        "ok": True,
        "goal_id": goal_id,
        "role": role,
        "todo_id": todo_id,
        "todo": text,
        "dry_run": dry_run,
        "added": result.get("status") not in {"replayed", "no_change"},
        "already_exists": result.get("status") in {"replayed", "no_change"},
        **result,
    }, registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id,
        project=project, state_file=state_file)
