#!/usr/bin/env python3
"""Smoke-test structured todo lifecycle transitions by todo_id."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-lifecycle-goal"
RUN_TODO = "Run a fresh-seed full PR3-r8 treatment repeat after the support-blocked seed failed."
REBUILD_TODO = "Rebuild labels and scorer after the fresh repeat."
VALIDATE_TODO = "Validate scorer labels and write back the compact result."
SIDE_TODO = "Refine todo ownership contract from a side worktree."
SIDE_CONTINUATION_TODO = "Continue the small side-agent productization lane after self-merge."
SIDE_REVIEW_TODO = "Refine todo ownership contract with primary review required."
REVIEW_TODO = "Primary agent review, verify, and merge the side-agent ownership contract work."


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Exercise todo lifecycle transitions.\n\n"
        "## Agent Todo\n\n"
        "- [ ] Legacy monitor-only placeholder.\n",
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
                        "domain": "todo-lifecycle-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".codex/goals/todo-lifecycle-goal/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "authority_sources": [],
                        "coordination": {
                            "registered_agents": ["codex-main-control", "codex-side-bypass"],
                            "primary_agent": "codex-main-control",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, state_file


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


def run_cli_error(registry_path: Path, *args: str) -> dict:
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
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    return json.loads(result.stdout)


def parsed_items(state_file: Path) -> list[dict]:
    fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return fields["agent_todos"]["items"]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-lifecycle-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)

        added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            RUN_TODO,
            "--task-class",
            "advancement_task",
            "--action-kind",
            "run_eval",
        )
        assert added["added"] is True, added
        run_todo_id = added["todo_id"]
        items = parsed_items(state_file)
        run_item = next(item for item in items if item["todo_id"] == run_todo_id)
        assert run_item["task_class"] == "advancement_task", run_item
        assert run_item["action_kind"] == "run_eval", run_item

        archive_open = run_cli(
            registry_path,
            "todo",
            "archive-completed",
            "--goal-id",
            GOAL_ID,
            "--execute",
            "--max-active-done",
            "0",
        )
        assert archive_open["moved_count"] == 0, archive_open
        assert any(item["todo_id"] == run_todo_id and not item["done"] for item in parsed_items(state_file))

        completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            run_todo_id,
            "--claimed-by",
            "codex-main-control",
            "--evidence",
            "fresh-repeat-result-ready",
            "--next-agent-todo",
            REBUILD_TODO,
            "--next-action-kind",
            "rebuild_score",
        )
        assert completed["changed"] is True, completed
        assert completed["next_todos"][0]["added"] is True, completed
        rebuild_todo_id = completed["next_todos"][0]["todo_id"]
        items = parsed_items(state_file)
        completed_item = next(item for item in items if item["todo_id"] == run_todo_id)
        rebuild_item = next(item for item in items if item["todo_id"] == rebuild_todo_id)
        assert completed_item["done"] is True and completed_item["status"] == "done", completed_item
        assert completed_item["evidence"] == "fresh-repeat-result-ready", completed_item
        assert completed_item["claimed_by"] == "codex-main-control", completed_item
        assert rebuild_item["done"] is False and rebuild_item["task_class"] == "advancement_task", rebuild_item
        assert rebuild_item["action_kind"] == "rebuild_score", rebuild_item

        side_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        assert side_added["added"] is True, side_added
        side_todo_id = side_added["todo_id"]
        missing_review = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
        )
        assert "side-agent completion" in missing_review["error"], missing_review
        assert "--next-agent-todo" in missing_review["error"], missing_review
        assert "--side-agent-self-merged" in missing_review["error"], missing_review

        missing_evidence = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--side-agent-self-merged",
        )
        assert "--side-agent-self-merged requires --evidence" in missing_evidence["error"], missing_evidence

        side_self_merged = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "self-merged commit abc123 after focused validation",
            "--side-agent-self-merged",
        )
        assert side_self_merged["changed"] is True, side_self_merged
        assert side_self_merged["side_agent_self_merged"] is True, side_self_merged
        assert side_self_merged["next_todos"] == [], side_self_merged

        side_continuation_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Prepare another small side-agent doc slice.",
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        side_continuation_todo_id = side_continuation_added["todo_id"]
        side_continuation_completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_continuation_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "self-merged commit def456 after focused validation",
            "--side-agent-self-merged",
            "--next-agent-todo",
            SIDE_CONTINUATION_TODO,
            "--next-claimed-by",
            "codex-side-bypass",
            "--next-action-kind",
            "contract_refine",
        )
        assert side_continuation_completed["changed"] is True, side_continuation_completed
        assert side_continuation_completed["side_agent_self_merged"] is True, side_continuation_completed
        assert side_continuation_completed["next_todos"][0]["claimed_by"] == "codex-side-bypass", (
            side_continuation_completed
        )
        side_successor_id = side_continuation_completed["next_todos"][0]["todo_id"]
        side_successor_item = next(item for item in parsed_items(state_file) if item["todo_id"] == side_successor_id)
        assert side_successor_item["done"] is False, side_successor_item
        assert side_successor_item["claimed_by"] == "codex-side-bypass", side_successor_item

        side_review_added = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            SIDE_REVIEW_TODO,
            "--claimed-by",
            "codex-side-bypass",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "contract_refine",
        )
        assert side_review_added["added"] is True, side_review_added
        side_review_todo_id = side_review_added["todo_id"]

        side_review_claim_error = run_cli_error(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_review_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            REVIEW_TODO,
            "--next-claimed-by",
            "codex-side-bypass",
        )
        assert "side-agent completion review todo must be claimed_by primary_agent" in (
            side_review_claim_error["error"]
        ), side_review_claim_error

        side_completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            side_review_todo_id,
            "--claimed-by",
            "codex-side-bypass",
            "--evidence",
            "side-worktree-contract-diff",
            "--next-agent-todo",
            REVIEW_TODO,
            "--next-action-kind",
            "primary_review",
        )
        assert side_completed["changed"] is True, side_completed
        review_todo_id = side_completed["next_todos"][0]["todo_id"]
        assert side_completed["next_todos"][0]["claimed_by"] == "codex-main-control", side_completed
        items = parsed_items(state_file)
        side_item = next(item for item in items if item["todo_id"] == side_todo_id)
        side_review_item = next(item for item in items if item["todo_id"] == side_review_todo_id)
        review_item = next(item for item in items if item["todo_id"] == review_todo_id)
        assert side_item["done"] is True and side_item["claimed_by"] == "codex-side-bypass", side_item
        assert side_review_item["done"] is True and side_review_item["claimed_by"] == "codex-side-bypass", (
            side_review_item
        )
        assert review_item["done"] is False and review_item["claimed_by"] == "codex-main-control", review_item

        repeated = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            run_todo_id,
            "--evidence",
            "fresh-repeat-result-ready",
            "--next-agent-todo",
            REBUILD_TODO,
            "--next-action-kind",
            "rebuild_score",
        )
        assert repeated["changed"] is False, repeated
        assert state_file.read_text(encoding="utf-8").count(REBUILD_TODO) == 1

        superseded = run_cli(
            registry_path,
            "todo",
            "supersede",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            rebuild_todo_id,
            "--reason",
            "folded-into-validation-step",
            "--next-agent-todo",
            VALIDATE_TODO,
            "--next-action-kind",
            "validate",
        )
        assert superseded["changed"] is True, superseded
        validate_todo_id = superseded["next_todos"][0]["todo_id"]
        items = parsed_items(state_file)
        rebuild_item = next(item for item in items if item["todo_id"] == rebuild_todo_id)
        validate_item = next(item for item in items if item["todo_id"] == validate_todo_id)
        assert rebuild_item["done"] is True and rebuild_item["superseded_by"] == validate_todo_id, rebuild_item
        assert validate_item["done"] is False and validate_item["task_class"] == "advancement_task", validate_item

        blocked = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            validate_todo_id,
            "--status",
            "blocked",
            "--reason",
            "waiting-on-public-scorer-source",
            "--task-class",
            "blocker",
        )
        assert blocked["changed"] is True, blocked
        validate_item = next(item for item in parsed_items(state_file) if item["todo_id"] == validate_todo_id)
        assert validate_item["status"] == "blocked", validate_item
        assert validate_item["done"] is False, validate_item
        assert validate_item["task_class"] == "blocker", validate_item
        fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        executable_ids = {
            item["todo_id"]
            for item in fields["agent_todos"].get("first_executable_items", [])
        }
        item_ids = {
            item["todo_id"]
            for item in fields["agent_todos"].get("items", [])
        }
        assert validate_todo_id in item_ids, fields
        assert validate_todo_id not in executable_ids, fields

    print("todo-lifecycle-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
