#!/usr/bin/env python3
"""Smoke-test the scheduler next-batch dispatch contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "scheduler-next-batch-smoke"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.scheduler_plan_reporter import render_scheduler_next_batch_chat_text  # noqa: E402
from loopx.scheduler import build_scheduler_next_batch, render_scheduler_next_batch_markdown  # noqa: E402


def todo(
    todo_id: str,
    text: str,
    *,
    claimed_by: str | None = None,
    write_scope: str | None = None,
) -> dict:
    item = {
        "todo_id": todo_id,
        "text": text,
        "status": "open",
        "done": False,
        "role": "agent",
        "task_class": "advancement_task",
        "safety_class": "local_write" if write_scope else "read_only",
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if write_scope:
        item["required_write_scopes"] = [write_scope]
    return item


def status_payload(items: list[dict]) -> dict:
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "open_count": len(items),
        "first_executable_items": items,
        "executable_backlog_items": items,
        "items": items,
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "codex",
                    "agent_todos": agent_todos,
                    "project_asset": {"agent_todos": agent_todos},
                }
            ]
        },
    }


def assert_next_batch_summarizes_parallel_dispatch() -> None:
    payload = build_scheduler_next_batch(
        status_payload(
            [
                todo("todo_docs", "Update docs.", claimed_by="agent-a", write_scope="docs/**"),
                todo("todo_view", "Inspect UI.", claimed_by="agent-b"),
                todo("todo_later", "Update docs later.", claimed_by="agent-a", write_scope="docs/later.md"),
            ]
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert payload["schema_version"] == "scheduler_next_batch_v0", payload
    assert payload["ready_to_dispatch"] is True, payload
    assert payload["dispatch_mode"] == "parallel_batch", payload
    assert payload["batch_size"] == 2, payload
    assert payload["runnable_todo_ids"] == ["todo_docs", "todo_view"], payload
    assert payload["waiting_reason_counts"] == {"agent_lane_capacity": 1}, payload
    slots = {item["todo_id"]: item for item in payload["worker_slots"]}
    assert slots["todo_docs"]["agent_lane"] == "agent-a", slots
    assert slots["todo_view"]["agent_lane"] == "agent-b", slots
    assert slots["todo_docs"]["quota_guard_command"].endswith("--agent-id agent-a"), slots
    assert "complete_command_template" in slots["todo_docs"], slots
    assert "blocked_command_template" in slots["todo_docs"], slots
    markdown = render_scheduler_next_batch_markdown(payload)
    assert "# LoopX Scheduler Next Batch" in markdown, markdown
    assert "dispatch_mode: `parallel_batch`" in markdown, markdown
    chat_text = render_scheduler_next_batch_chat_text(payload)
    assert "Next batch: parallel_batch" in chat_text, chat_text
    assert "Workers: todo_docs->agent-a, todo_view->agent-b" in chat_text, chat_text


def write_cli_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Scheduler Next Batch Smoke\n\n"
        "## Agent Todo\n\n"
        "- [ ] Update docs.\n"
        "  <!-- loopx:todo todo_id=todo_cli_docs status=open task_class=advancement_task "
        "required_write_scopes=docs/** safety_class=local_write claimed_by=agent-a -->\n"
        "- [ ] Inspect status.\n"
        "  <!-- loopx:todo todo_id=todo_cli_read status=open task_class=advancement_task "
        "safety_class=read_only claimed_by=agent-b -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "harness_self_improvement"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, runtime


def assert_cli_scheduler_next_batch_uses_status_collection() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-scheduler-next-batch-") as tmp:
        registry_path, runtime = write_cli_fixture(Path(tmp))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "scheduler",
                "next-batch",
                "--goal-id",
                GOAL_ID,
                "--max-parallel",
                "2",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == "scheduler_next_batch_v0", payload
        assert payload["dispatch_mode"] == "parallel_batch", payload
        assert payload["batch_size"] == 2, payload
        assert payload["runnable_todo_ids"] == ["todo_cli_docs", "todo_cli_read"], payload


def main() -> int:
    assert_next_batch_summarizes_parallel_dispatch()
    assert_cli_scheduler_next_batch_uses_status_collection()
    print("scheduler next batch smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
