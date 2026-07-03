#!/usr/bin/env python3
"""Smoke-test parseable Agent Todo durability and completed-work archives."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import parse_active_state_todos  # noqa: E402
from loopx.rollout_event_log import (  # noqa: E402
    append_rollout_event,
    build_rollout_event,
    rollout_event_log_path,
)


GOAL_ID = "todo-durability-fixture-goal"
FIRST_OPEN_TODO = (
    "[P1] Add a parseable todo fixture when discovered planning work cannot be "
    "represented by the current Markdown parser."
)
SECOND_OPEN_TODO = "[P2] Keep the todo archive warning visible in quota should-run."
ACTIVE_DONE_TODO = "[P2] Prior completed implementation remains in active Agent Todo until archived."
DEFERRED_TODO = "[P1] Resume the issue surface fixture after CLI extraction stabilizes."
PR_DEFERRED_TODO = "[P1] Resume the Lark Kanban follow-up after PR #532 merges."
ARCHIVED_DONE_TODOS = 25


def run_cli(*args: str, registry_path: Path, runtime: Path) -> dict:
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
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def state_text() -> str:
    archived_lines = "".join(
        f"- [x] [P1] Archived completed work item {index}.\n"
        for index in range(1, ARCHIVED_DONE_TODOS + 1)
    )
    return (
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Todo Durability Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Add a parseable todo fixture when discovered planning work\n"
        "  cannot be represented by the current Markdown parser.\n"
        f"- [x] {ACTIVE_DONE_TODO}\n"
        "  <!-- loopx:todo todo_id=todo_done_cli status=done task_class=advancement_task -->\n"
        f"- [-] {DEFERRED_TODO}\n"
        "  <!-- loopx:todo todo_id=todo_deferred_surface status=deferred task_class=advancement_task claimed_by=codex-product-capability resume_when=todo_done:todo_done_cli -->\n"
        f"- [-] {PR_DEFERRED_TODO}\n"
        "  <!-- loopx:todo todo_id=todo_pr_deferred status=deferred task_class=advancement_task claimed_by=codex-side-bypass resume_when=pr_merged:#532 -->\n"
        f"- [ ] {SECOND_OPEN_TODO}\n\n"
        "## Completed Work Archive\n\n"
        f"{archived_lines}"
    )


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state_text(), encoding="utf-8")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    append_rollout_event(
        rollout_event_log_path(runtime, GOAL_ID),
        pr_merged_event(),
    )
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "todo-durability-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime


def assert_parseable_agent_todos(agent_todos: dict) -> None:
    assert agent_todos["schema_version"] == "todo_summary_v0", agent_todos
    assert agent_todos["total_count"] == 5, agent_todos
    assert agent_todos["open_count"] == 2, agent_todos
    assert agent_todos["done_count"] == 3, agent_todos
    assert agent_todos["deferred_count"] == 2, agent_todos
    assert [item["index"] for item in agent_todos["first_open_items"]] == [1, 5], agent_todos

    first_open = agent_todos["first_open_items"][0]
    assert first_open["schema_version"] == "todo_item_v0", first_open
    assert first_open["role"] == "agent", first_open
    assert first_open["status"] == "open", first_open
    assert first_open["priority"] == "P1", first_open
    assert first_open["archive_state"] == "active", first_open
    assert first_open["source_section"] == "Agent Todo", first_open
    assert first_open["text"] == FIRST_OPEN_TODO, first_open
    assert (
        first_open["title"]
        == "Add a parseable todo fixture when discovered planning work cannot be represented by the current Markdown parser."
    ), first_open
    assert str(first_open["todo_id"]).startswith("todo_"), first_open

    second_open = agent_todos["first_open_items"][1]
    assert second_open["priority"] == "P2", second_open
    assert second_open["status"] == "open", second_open
    assert second_open["text"] == SECOND_OPEN_TODO, second_open

    deferred = agent_todos["deferred_items"][0]
    deferred_by_id = {item["todo_id"]: item for item in agent_todos["deferred_items"]}
    assert set(deferred_by_id) == {"todo_deferred_surface", "todo_pr_deferred"}, agent_todos
    deferred = deferred_by_id["todo_deferred_surface"]
    assert deferred["status"] == "deferred", deferred
    assert deferred["resume_when"] == "todo_done:todo_done_cli", deferred
    assert deferred["resume_ready"] is True, deferred
    assert deferred["resume_condition"]["target_status"] == "done", deferred
    pr_deferred = deferred_by_id["todo_pr_deferred"]
    assert pr_deferred["resume_when"] == "pr_merged:#532", pr_deferred
    assert pr_deferred["resume_ready"] is True, pr_deferred
    assert pr_deferred["resume_condition"]["kind"] == "pr_merged", pr_deferred
    assert pr_deferred["resume_condition"]["pr_number"] == 532, pr_deferred
    assert pr_deferred["resume_condition"]["pr_repo"] is None, pr_deferred
    assert pr_deferred["resume_condition"]["matched_pr_ref"] == "huangruiteng/loopx#532", pr_deferred
    resume_candidate_ids = {item["todo_id"] for item in agent_todos["deferred_resume_candidates"]}
    assert {"todo_deferred_surface", "todo_pr_deferred"} <= resume_candidate_ids, agent_todos
    if "items" in agent_todos:
        statuses = [item["status"] for item in agent_todos["items"][:3]]
        assert statuses == ["open", "open", "deferred"], agent_todos


def attention_item(status_payload: dict) -> dict:
    items = status_payload.get("attention_queue", {}).get("items") or []
    assert len(items) == 1, status_payload
    return items[0]


def pr_merged_event() -> dict:
    return build_rollout_event(
        goal_id=GOAL_ID,
        event_kind="pr_merge",
        pr_ref="huangruiteng/loopx#532",
        status="ready",
        summary="PR #532 merged and can resume dependent deferred todos.",
    )


def main() -> int:
    parsed = parse_active_state_todos(state_text(), rollout_events=[pr_merged_event()])
    assert_parseable_agent_todos(parsed["agent_todos"])

    with tempfile.TemporaryDirectory(prefix="loopx-todo-durability-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp))
        status_payload = run_cli("status", registry_path=registry_path, runtime=runtime)
        item = attention_item(status_payload)

        assert_parseable_agent_todos(item["agent_todos"])
        assert "completed_todo_archive_warning" not in item, item
        assert "completed_todo_archive_warning" not in item["project_asset"], item
        assert item["project_asset"]["agent_todos"]["open"] == 2, item
        assert item["project_asset"]["agent_todos"]["done"] == 3, item
        assert item["project_asset"]["agent_todos"]["deferred_count"] == 2, item
        assert (
            {
                candidate["todo_id"]
                for candidate in item["project_asset"]["agent_todos"]["deferred_resume_candidates"]
            }
            >= {"todo_deferred_surface", "todo_pr_deferred"}
        ), item
        assert item["project_asset"]["agent_todos"]["next"] == FIRST_OPEN_TODO, item
        assert item["project_asset"]["agent_todos"]["next_index"] == 1, item

        guard = run_cli("quota", "should-run", "--goal-id", GOAL_ID, registry_path=registry_path, runtime=runtime)
        assert guard["should_run"] is True, guard
        assert_parseable_agent_todos(guard["agent_todo_summary"])
        assert "completed_todo_archive_warning" not in guard, guard

        first_todo_id = guard["agent_todo_summary"]["first_open_items"][0]["todo_id"]
        lifecycle_result = run_cli(
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            first_todo_id,
            "--evidence",
            "fixture completed",
            "--next-agent-todo",
            "Continue lifecycle follow-up without an explicit priority prefix.",
            "--next-task-class",
            "advancement_task",
            "--next-action-kind",
            "fixture_follow_up",
            registry_path=registry_path,
            runtime=runtime,
        )
        next_todo = lifecycle_result["next_todos"][0]
        assert next_todo["todo"].startswith("[P1] Continue lifecycle"), lifecycle_result

        post_lifecycle_status = run_cli("status", registry_path=registry_path, runtime=runtime)
        post_lifecycle_item = attention_item(post_lifecycle_status)
        post_agent_todos = post_lifecycle_item["agent_todos"]
        assert post_agent_todos["open_count"] == 2, post_agent_todos
        assert post_agent_todos["done_count"] == 4, post_agent_todos
        assert post_agent_todos["deferred_count"] == 2, post_agent_todos
        assert post_agent_todos["first_open_items"][0]["priority"] == "P1", post_agent_todos
        assert post_agent_todos["first_open_items"][0]["todo_id"] == next_todo["todo_id"], post_agent_todos
        assert post_agent_todos["first_open_items"][0]["action_kind"] == "fixture_follow_up", post_agent_todos

    print("todo-durability-fixture-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
