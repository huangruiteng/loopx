from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .file_lock import exclusive_file_lock
from .state_refresh import now_local
from .status import normalize_todo_text
from .control_plane.todos.contract import TODO_TASK_CLASS_ADVANCEMENT
from .todos import (
    TODO_SECTION_HEADINGS,
    add_todo_to_lines,
    replace_updated_at,
    resolve_todo_state_path,
    section_bounds,
    todo_blocks,
)


MAX_CAPTURED_FOLLOWUP_TODOS = 2

_UNSAFE_FOLLOWUP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("local_absolute_path", re.compile(r"(?i)(?:/Users/|/private/|/var/folders/|file://)")),
    ("local_state_path", re.compile(r"(?i)(?:^|[\s\"'`])(?:\.local/|\.codex/|\.loopx/)")),
    ("credential_literal", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\s*[:=]")),
    ("internal_only_marker", re.compile(r"(?i)\binternal[-_\s]?only\b")),
)


def _unsafe_followup_reason(value: str) -> str | None:
    for reason, pattern in _UNSAFE_FOLLOWUP_PATTERNS:
        if pattern.search(value):
            return reason
    return None


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _existing_agent_todo_texts(lines: list[str]) -> set[str]:
    bounds = section_bounds(lines, "agent")
    if not bounds:
        return set()
    start, end, section = bounds
    return {
        normalize_todo_text(str(block.get("text") or ""))
        for block in todo_blocks(lines, start, end, role="agent", source_section=section)
        if block.get("text")
    }


def capture_followup_todos(
    *,
    registry_path: Path,
    goal_id: str,
    followups: list[str],
    evidence: str,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    required_decision_scopes: Any = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not followups:
        raise ValueError("todo capture-followups requires at least one --follow-up")
    evidence_text = _compact_text(evidence)
    if not evidence_text:
        raise ValueError("todo capture-followups requires --evidence with a public-safe pointer")
    evidence_reason = _unsafe_followup_reason(evidence_text)
    if evidence_reason:
        raise ValueError(f"todo capture-followups evidence is not public-safe: {evidence_reason}")

    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )

    items: list[dict[str, Any]] = []
    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        existing_texts = _existing_agent_todo_texts(lines)
        seen_texts: set[str] = set()
        updated_at = now_local()
        changed = False
        recorded_count = 0

        for raw_followup in followups:
            todo_text = _compact_text(raw_followup)
            item: dict[str, Any] = {
                "todo": todo_text,
                "added": False,
                "already_exists": False,
                "skipped": False,
                "skipped_reason": None,
            }
            if not todo_text:
                item.update({"skipped": True, "skipped_reason": "empty"})
                items.append(item)
                continue

            unsafe_reason = _unsafe_followup_reason(todo_text)
            if unsafe_reason:
                item.update({"skipped": True, "skipped_reason": f"unsafe_boundary:{unsafe_reason}"})
                items.append(item)
                continue

            normalized = normalize_todo_text(todo_text)
            if normalized in existing_texts or normalized in seen_texts:
                item.update({"already_exists": True, "skipped": True, "skipped_reason": "duplicate"})
                items.append(item)
                continue

            if recorded_count >= MAX_CAPTURED_FOLLOWUP_TODOS:
                item.update({"skipped": True, "skipped_reason": "max_items_exceeded"})
                items.append(item)
                continue

            add_result = add_todo_to_lines(
                lines,
                role="agent",
                text=todo_text,
                task_class=task_class or TODO_TASK_CLASS_ADVANCEMENT,
                action_kind=action_kind,
                required_write_scopes=required_write_scopes,
                required_capabilities=required_capabilities,
                target_capabilities=target_capabilities,
                required_decision_scopes=required_decision_scopes,
                evidence=evidence_text,
                updated_at=updated_at,
            )
            changed = changed or bool(add_result.get("added")) or bool(add_result.get("metadata_updated"))
            recorded_count += 1
            seen_texts.add(normalized)
            item.update(add_result)
            items.append(item)

        if changed:
            new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
            new_text = replace_updated_at(new_text, updated_at)
            if not dry_run:
                resolved_state_file.write_text(new_text, encoding="utf-8")

    return {
        "ok": True,
        "dry_run": dry_run,
        "changed": changed,
        "goal_id": goal_id,
        "role": "agent",
        "section": TODO_SECTION_HEADINGS["agent"],
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "max_items": MAX_CAPTURED_FOLLOWUP_TODOS,
        "requested_count": len(followups),
        "recorded_count": recorded_count,
        "skipped_count": sum(1 for item in items if item.get("skipped")),
        "evidence": evidence_text,
        "items": items,
        "updated_at": updated_at if changed else None,
    }
