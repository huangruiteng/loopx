#!/usr/bin/env python3
"""Smoke-test agent-guided candidate todo suggestion prompts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "todo-suggestion-goal"


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
        "Exercise todo suggestion prompt generation.\n",
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
                        "domain": "todo-suggestion-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".codex/goals/todo-suggestion-goal/ACTIVE_GOAL_STATE.md",
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
    return registry_path, state_file


def run_cli(registry_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            *args,
        ],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-suggestion-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        original_state = state_file.read_text(encoding="utf-8")

        result = run_cli(
            registry_path,
            "--format",
            "json",
            "todo",
            "suggest",
            "--goal-id",
            GOAL_ID,
            "--project",
            ".",
            "--agent-id",
            "codex-main-control",
            "--from",
            "recent-repo",
            "--from",
            "loopx-deferred",
            "--limit",
            "9",
            "--trigger",
            "user-requested",
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["schema_version"] == "todo_suggestion_prompt_v0", payload
        assert payload["mode"] == "agent_guided_candidate_todo_queue", payload
        assert payload["analysis_owner"] == "user_project_agent", payload
        assert payload["loopx_role"] == "prompt_contract_only", payload
        assert payload["state_write_performed"] is False, payload
        assert payload["formal_todos_written"] is False, payload
        assert payload["effective_limit"] == 5, payload
        assert payload["max_limit"] == 5, payload
        assert payload["sources"] == ["recent-repo", "loopx-deferred"], payload
        assert payload["candidate_queue_field"] == "suggested_todos", payload
        assert payload["candidate_schema_version"] == "suggested_todo_candidate_v0", payload
        assert payload["promotion_policy"]["do_not_execute_in_suggestion_turn"] is True, payload
        task_body = payload["task_body"]
        assert "LoopX is not analyzing the repository itself" in task_body, task_body
        assert "Return at most 5 items in a `suggested_todos` list" in task_body, task_body
        assert "Do not call `loopx todo add`" in task_body, task_body
        assert "`promotion_preview`" in task_body, task_body
        assert "`requires_user_decision=true`" in task_body, task_body
        assert state_file.read_text(encoding="utf-8") == original_state

        markdown = run_cli(
            registry_path,
            "todo",
            "suggest",
            "--goal-id",
            GOAL_ID,
            "--from",
            "docs-smokes",
        ).stdout
        assert "LoopX Todo Suggestion Prompt" in markdown, markdown
        assert "Agent Task Body" in markdown, markdown
        assert "Suggested items are decision candidates" in markdown, markdown
        assert state_file.read_text(encoding="utf-8") == original_state

        rejected = run_cli(
            registry_path,
            "--format",
            "json",
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Do something.",
            "--agent-id",
            "codex-main-control",
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        error_payload = json.loads(rejected.stdout)
        assert "only supported by `todo suggest`" in error_payload["error"], error_payload

    print("todo-suggestion-prompt-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
