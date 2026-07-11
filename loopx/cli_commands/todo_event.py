from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path


RolloutEventAppender = Callable[..., dict[str, object]]

TODO_EVENT_KINDS = {
    "add": "todo_add",
    "claim": "todo_claim",
    "update": "todo_update",
    "complete": "todo_complete",
    "supersede": "todo_supersede",
    "archive-completed": "todo_archive_completed",
    "capture-followups": "todo_capture_followups",
}


def append_todo_rollout_event(
    payload: dict[str, object],
    *,
    args: argparse.Namespace,
    registry_path: Path,
    runtime_root_arg: str | None,
    append_cli_rollout_event: RolloutEventAppender,
) -> None:
    if not payload.get("ok") or payload.get("dry_run"):
        return
    append_cli_rollout_event(
        payload,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        event_kind=TODO_EVENT_KINDS.get(args.todo_command, "todo_update"),
        agent_id=args.agent_id or args.claimed_by,
        todo_id=args.todo_id or str(payload.get("todo_id") or "").strip() or None,
        status=str(payload.get("status") or args.todo_command or "").strip(),
        summary=(
            f"todo {args.todo_command} recorded for "
            f"{payload.get('todo_id') or args.todo_id or 'unstructured todo'}"
        ),
        details={
            "command": "todo",
            "todo_command": args.todo_command,
            "role": payload.get("role") or args.role or "",
            "changed": bool(payload.get("changed")),
            "added": bool(payload.get("added")),
            "already_exists": bool(payload.get("already_exists")),
        },
    )
