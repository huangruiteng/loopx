"""In-memory Markdown editing adapter; the TS provider owns the commit.

Only the explicitly requested text/note fields cross back. Unrepresented
canonical fields, section/index provenance and lease records never round-trip
through Markdown. The on-disk projection is not an input or a commit target.
"""

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
from .active_state_editing import find_todo_block, set_todo_text
from .contract import format_todo_metadata_line, metadata_line_for_todo_block
from .line_update import upsert_todo_metadata
from .provider_projection import settle_canonical_todo_projection


def edit_canonical_todo_if_promoted(
    *, registry_path: Path, runtime_root: Path, goal_id: str, todo_id: str,
    actor_agent_id: str | None, role: str | None, text: str | None,
    note: str | None, dry_run: bool,
    project: Path | None = None, state_file: Path | None = None,
) -> dict[str, Any] | None:
    canonical = read_canonical_todos_if_promoted(runtime_root=runtime_root, goal_id=goal_id)
    if canonical is None:
        return None
    todo = next((item for item in canonical["todos"] if item["todo_id"] == todo_id), None)
    if todo is None:
        raise ValueError("Todo is missing from canonical authority")
    if role is not None and role != todo["role"]:
        raise ValueError("Todo does not have the requested role")
    # Reuse the existing Markdown text/metadata editor as a codec, not an
    # authorization engine. This buffer is synthetic and is never persisted.
    lines = ["## Agent Todo", "", f"- [ ] {todo['text']}",
             format_todo_metadata_line(todo_id=todo_id, note=todo.get("note"))]
    found = find_todo_block(lines, todo_id=todo_id, role="agent")
    if found is None:
        raise ValueError("canonical Todo cannot be represented by the compatibility editor")
    block = found[4]
    if text is not None:
        set_todo_text(lines, block, text, status="open")
    if note is not None:
        upsert_todo_metadata(lines, block, metadata_line_for_todo_block(block, {"note": note}))
    edited = find_todo_block(lines, todo_id=todo_id, role="agent")
    if edited is None:
        raise ValueError("compatibility editor lost Todo identity")
    patch = {field: edited[4].get(field) for field, requested in
             (("text", text), ("note", note)) if requested is not None}
    result = effect_runtime_result("coordination.local_authority.todo_update", {
        "schema_version": "loopx_local_coordination_todo_update_request_v0",
        "runtime_root": str(runtime_root.resolve()), "goal_id": goal_id,
        "todo_id": todo_id, "role": role, "actor_agent_id": actor_agent_id,
        "registered_agents": registered_agent_ids_from_registry(registry_path, goal_id),
        "operation_id": f"todo-update:{uuid4().hex}",
        "patch": patch, "clear_fields": [], "dry_run": dry_run,
        "observed_at": now_local(),
    })
    if not isinstance(result, dict) or result.get("status") not in {
        "applied", "recovered", "replayed", "no_change", "planned",
    } or result.get("source_authority") != "file_v0" or (
        result.get("decision_read_from_provider") is not True
        or result.get("legacy_fallback_used") is not False
    ):
        payload = result if isinstance(result, dict) else {}
        raise LocalCoordinationAuthorityUnavailable(
            str(payload.get("reason") or "canonical compatibility edit failed; reread before retry"),
            code=str(payload.get("reason_code") or payload.get("conflict_kind")
                     or "compatibility_edit_failed"), payload=payload,
        )
    return settle_canonical_todo_projection(
        {"ok": True, "goal_id": goal_id, "todo_id": todo_id,
         "role": todo["role"], "dry_run": dry_run, **result},
        registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id,
        project=project, state_file=state_file,
    )
