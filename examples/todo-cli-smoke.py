#!/usr/bin/env python3
"""Smoke-test the agent-facing todo add command."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-cli-goal"
USER_TODO = "Review the owner decision checklist before approving delivery."
AGENT_TODO = "Summarize the read-only evidence after the user checklist is done."


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Keep this fixture small.\n\n"
        "## Next Action\n\n"
        "- Choose the next bounded step.\n",
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
                        "domain": "todo-cli-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": ".codex/goals/todo-cli-goal/ACTIVE_GOAL_STATE.md",
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


def run_cli(registry_path: Path, *args: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-todo-cli-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        original = state_file.read_text(encoding="utf-8")

        dry_run = run_cli(registry_path, "todo", "add", "--goal-id", GOAL_ID, "--role", "user", "--text", USER_TODO, "--dry-run")
        assert dry_run["ok"] is True, dry_run
        assert dry_run["added"] is True, dry_run
        assert state_file.read_text(encoding="utf-8") == original

        user_payload = run_cli(registry_path, "todo", "add", "--goal-id", GOAL_ID, "--role", "user", "--text", USER_TODO)
        assert user_payload["added"] is True, user_payload
        after_user = state_file.read_text(encoding="utf-8")
        assert "## User Todo / Owner Review Reading Queue" in after_user, after_user
        assert f"- [ ] {USER_TODO}" in after_user, after_user
        assert after_user.index("## User Todo / Owner Review Reading Queue") < after_user.index("## Next Action")
        assert "updated_at: 2026-01-01T00:00:00+00:00" not in after_user

        duplicate = run_cli(registry_path, "todo", "add", "--goal-id", GOAL_ID, "--role", "user", "--text", USER_TODO)
        assert duplicate["added"] is False, duplicate
        assert duplicate["already_exists"] is True, duplicate
        assert state_file.read_text(encoding="utf-8").count(USER_TODO) == 1

        agent_payload = run_cli(registry_path, "todo", "add", "--goal-id", GOAL_ID, "--role", "agent", "--text", AGENT_TODO)
        assert agent_payload["added"] is True, agent_payload
        metadata_payload = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            AGENT_TODO,
            "--task-class",
            "advancement_task",
            "--action-kind",
            "run_eval",
        )
        assert metadata_payload["added"] is False, metadata_payload
        assert metadata_payload["already_exists"] is True, metadata_payload
        assert metadata_payload["metadata_updated"] is True, metadata_payload
        assert metadata_payload["task_class"] == "advancement_task", metadata_payload
        assert metadata_payload["action_kind"] == "run_eval", metadata_payload
        after_metadata = state_file.read_text(encoding="utf-8")
        assert after_metadata.count(AGENT_TODO) == 1, after_metadata
        assert "<!-- goal-harness:todo task_class=advancement_task action_kind=run_eval -->" in after_metadata
        fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        assert fields["user_todos"]["items"][0]["text"] == USER_TODO, fields
        assert fields["agent_todos"]["items"][0]["text"] == AGENT_TODO, fields
        assert fields["agent_todos"]["items"][0]["task_class"] == "advancement_task", fields
        assert fields["agent_todos"]["items"][0]["action_kind"] == "run_eval", fields
        assert fields["user_todos"]["source_section"] == "User Todo / Owner Review Reading Queue", fields
        assert fields["agent_todos"]["source_section"] == "Agent Todo", fields

    print("todo-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
