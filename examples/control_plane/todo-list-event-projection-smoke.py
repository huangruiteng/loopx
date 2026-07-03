#!/usr/bin/env python3
"""Smoke-test `loopx todo list` event projection with Markdown late-todo overlay."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    TODO_ADDED,
    TODO_COMPLETED,
    make_state_event,
)


GOAL_ID = "todo-list-event-projection-fixture"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    event_log = state_file.with_name("events.jsonl")
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Markdown fallback todo\n"
        "  <!-- loopx:todo todo_id=todo_markdown status=open task_class=advancement_task -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "todo-list-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "state_event_log": f".codex/goals/{GOAL_ID}/events.jsonl",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, state_file, event_log


def event(event_id: str, event_type: str, todo_id: str, payload: dict) -> dict:
    return make_state_event(
        event_id=event_id,
        goal_id=GOAL_ID,
        event_type=event_type,
        refs={"todo_id": todo_id},
        payload=payload,
        recorded_at=f"2026-06-27T00:00:{len(event_id):02d}Z",
        producer="todo-list-event-projection-smoke",
    )


def run_cli(registry_path: Path, *args: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def write_events(event_log: Path) -> None:
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        event(
            "evt-open",
            TODO_ADDED,
            "todo_event_open",
            {
                "role": "agent",
                "priority": "P0",
                "title": "Projected open todo",
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "implement",
            },
        )
    )
    store.append(
        event(
            "evt-done",
            TODO_ADDED,
            "todo_event_done",
            {
                "role": "agent",
                "priority": "P1",
                "title": "Projected completed todo",
                "planner_order": 2,
                "task_class": "advancement_task",
            },
        )
    )
    store.append(
        event(
            "evt-complete",
            TODO_COMPLETED,
            "todo_event_done",
            {"evidence": "projection smoke"},
        )
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-list-projection-") as tmp:
        registry_path, _, event_log = write_fixture(Path(tmp))
        write_events(event_log)

        projected = run_cli(registry_path, "todo", "list", "--goal-id", GOAL_ID, "--role", "agent")
        assert projected["ok"] is True, projected
        assert projected["read_only"] is True, projected
        assert projected["source"] == "event_projection_with_markdown_overlay", projected
        assert projected["todo_count"] == 3, projected
        assert [item["todo_id"] for item in projected["todos"]] == [
            "todo_event_open",
            "todo_markdown",
            "todo_event_done",
        ], projected
        assert projected["projection_overlay"]["markdown_only_todo_ids"] == [
            "todo_markdown"
        ], projected
        assert projected["projection_overlay"]["event_only_todo_ids"] == [
            "todo_event_open",
            "todo_event_done",
        ], projected
        assert projected["state_event_projection"]["source_event_count"] == 3, projected

        done_only = run_cli(
            registry_path,
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--status",
            "done",
        )
        assert done_only["source"] == "event_projection_with_markdown_overlay", done_only
        assert done_only["todo_count"] == 1, done_only
        assert done_only["todos"][0]["todo_id"] == "todo_event_done", done_only

        event_log.unlink()
        fallback = run_cli(registry_path, "todo", "list", "--goal-id", GOAL_ID, "--role", "agent")
        assert fallback["source"] == "markdown_active_state", fallback
        assert fallback["todo_count"] == 1, fallback
        assert fallback["todos"][0]["todo_id"] == "todo_markdown", fallback

    print("todo-list-event-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
