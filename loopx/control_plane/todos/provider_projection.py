"""Recoverable Markdown delivery for provider-owned Todo state.

The canonical authority journal is the transaction-bound projection outbox:
each committed mutation already retains the complete canonical head and its
provider revision.  This adapter drains that durable intent into the legacy
Markdown compatibility view.  Delivery failure never rolls back or obscures
the canonical commit; a later mutation or explicit projection can replay the
current head idempotently.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...file_lock import exclusive_file_lock
from ...history import load_registry
from ...state_refresh import resolve_goal_state
from ..coordination.local_authority import (
    LocalCoordinationAuthorityUnavailable,
    read_canonical_todos_if_promoted,
)
from .machine_section_projection import (
    TodoSectionProjectionError,
    render_canonical_todo_sections,
)


TODO_PROJECTION_DELIVERY_SCHEMA = "loopx_todo_projection_delivery_v0"


def _read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _fsync_parent_directory(path: Path) -> None:
    if os.name != "posix":  # pragma: no cover - Windows has no directory fsync
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_text(path: Path, text: str) -> None:
    """Durably replace a compatibility projection without changing its mode."""

    original_mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            os.chmod(temporary_path, original_mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_parent_directory(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def project_current_canonical_todos(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    expected_provider_revision: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    execute: bool = True,
    registry_data: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render one exact canonical head into machine-owned Markdown regions."""

    registry = dict(registry_data) if registry_data is not None else load_registry(registry_path)
    goal, resolved_project, state_path = resolve_goal_state(
        registry=registry,
        goal_id=goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if goal is None:
        raise ValueError(f"goal {goal_id!r} is not present in the registry")
    if not state_path.exists():
        raise ValueError("Todo Markdown projection target does not exist")

    with exclusive_file_lock(state_path, operation="project_canonical_todo_sections"):
        authority_read = read_canonical_todos_if_promoted(
            runtime_root=runtime_root,
            goal_id=goal_id,
        )
        if not isinstance(authority_read, dict):
            raise ValueError(
                "Todo Markdown projection requires promoted canonical authority"
            )
        provider_revision = authority_read.get("provider_revision")
        if not isinstance(provider_revision, str) or not provider_revision:
            raise ValueError("canonical Todo authority omitted provider revision")
        if (
            expected_provider_revision is not None
            and provider_revision != expected_provider_revision
        ):
            raise ValueError(
                "Todo Markdown projection provider revision does not match the "
                "canonical read head"
            )
        source = _read_text_exact(state_path)
        projection = render_canonical_todo_sections(
            source,
            authority_read["todos"],
            provider_revision=provider_revision,
        )
        if execute and projection.changed:
            _atomic_write_text(state_path, projection.markdown)
            if _read_text_exact(state_path) != projection.markdown:
                raise RuntimeError("Todo Markdown projection readback mismatch")

    return {
        "schema_version": TODO_PROJECTION_DELIVERY_SCHEMA,
        "status": (
            "delivered" if execute and projection.changed else
            "current" if execute else
            "planned"
        ),
        "source": "committed_authority_journal",
        "goal_id": goal_id,
        "state_file": str(state_path),
        "project": str(resolved_project) if resolved_project else None,
        "source_authority": authority_read.get("source_authority"),
        "provider_revision": projection.provider_revision,
        "todo_count": projection.todo_count,
        "changed": projection.changed,
        "executed": execute,
        "source_sha256": projection.source_sha256,
        "rendered_sha256": projection.rendered_sha256,
        "narrative_sha256": projection.narrative_sha256,
        "section_record_sha256": projection.section_record_sha256,
        "parse_render_parity": True,
        "narrative_preserved": True,
        "legacy_fallback_used": False,
    }


def settle_canonical_todo_projection(
    payload: dict[str, Any],
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    """Drain the committed provider head, preserving a successful mutation."""

    if payload.get("dry_run") is True or payload.get("status") == "planned":
        payload["projection_delivery"] = "not_required"
        payload["projection_outbox"] = {
            "schema_version": TODO_PROJECTION_DELIVERY_SCHEMA,
            "status": "not_required",
            "source": "committed_authority_journal",
        }
        return payload
    trigger_revision = payload.get("provider_revision")
    trigger_cursor = payload.get("cursor")
    try:
        delivery = project_current_canonical_todos(
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id=goal_id,
            project=project,
            state_file=state_file,
            execute=True,
        )
    except Exception as error:  # noqa: BLE001 - canonical commit already landed
        if isinstance(error, LocalCoordinationAuthorityUnavailable):
            reason_code = "todo_projection_authority_unavailable"
        elif isinstance(error, TodoSectionProjectionError):
            reason_code = "todo_projection_render_rejected"
        elif isinstance(error, OSError):
            reason_code = "todo_projection_write_unavailable"
        else:
            reason_code = "todo_projection_target_unavailable"
        delivery = {
            "schema_version": TODO_PROJECTION_DELIVERY_SCHEMA,
            "status": "pending",
            "source": "committed_authority_journal",
            "reason_code": reason_code,
            "error_class": error.__class__.__name__,
            "retryable": True,
        }
    if isinstance(trigger_revision, str) and trigger_revision:
        delivery["trigger_provider_revision"] = trigger_revision
    if isinstance(trigger_cursor, str) and trigger_cursor:
        delivery["trigger_cursor"] = trigger_cursor
    payload["projection_delivery"] = delivery["status"]
    payload["projection_outbox"] = delivery
    return payload


__all__ = [
    "TODO_PROJECTION_DELIVERY_SCHEMA",
    "project_current_canonical_todos",
    "settle_canonical_todo_projection",
]
