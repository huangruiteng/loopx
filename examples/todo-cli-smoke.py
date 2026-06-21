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

from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-cli-goal"
USER_TODO = "Review the owner decision checklist before approving delivery."
AGENT_TODO = "Summarize the read-only evidence after the user checklist is done."
UPDATED_AGENT_TODO = "Publish the compact evidence summary after validation passes."


def write_fixture(root: Path, *, register_agents: bool = True) -> tuple[Path, Path]:
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
        "Keep this fixture small.\n\n"
        "## Next Action\n\n"
        "- Choose the next bounded step.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    goal = {
        "id": GOAL_ID,
        "domain": "todo-cli-fixture",
        "status": "active",
        "repo": str(project),
        "state_file": ".codex/goals/todo-cli-goal/ACTIVE_GOAL_STATE.md",
        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
        "authority_sources": [],
    }
    if register_agents:
        goal["coordination"] = {
            "registered_agents": ["codex-main-control", "codex-side-bypass"],
            "primary_agent": "codex-main-control",
        }
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [goal],
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
    assert result.returncode != 0, result.stdout
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-cli-smoke-") as tmp:
        root = Path(tmp)
        registry_path, state_file = write_fixture(root)
        legacy_registry_path, _ = write_fixture(root / "legacy", register_agents=False)
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
        legacy_agent = run_cli(
            legacy_registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            AGENT_TODO,
        )
        legacy_claim = run_cli_error(
            legacy_registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            legacy_agent["todo_id"],
            "--claimed-by",
            "codex-main-control",
        )
        assert "legacy project" in legacy_claim["error"], legacy_claim
        assert "Register this agent identity first" in legacy_claim["error"], legacy_claim
        assert "--registered-agent codex-main-control" in legacy_claim["error"], legacy_claim
        wrapped_agent_todo = "- [ ] Summarize the read-only evidence after the user\n  checklist is done."
        state_file.write_text(
            state_file.read_text(encoding="utf-8").replace(f"- [ ] {AGENT_TODO}", wrapped_agent_todo),
            encoding="utf-8",
        )
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
            "--required-capability",
            "shell",
            "--required-capability",
            "benchmark_runner",
            "--target-capability",
            "benchmark_runner",
        )
        assert metadata_payload["added"] is False, metadata_payload
        assert metadata_payload["already_exists"] is True, metadata_payload
        assert metadata_payload["metadata_updated"] is True, metadata_payload
        assert metadata_payload["task_class"] == "advancement_task", metadata_payload
        assert metadata_payload["action_kind"] == "run_eval", metadata_payload
        assert metadata_payload["required_capabilities"] == ["shell", "benchmark_runner"], metadata_payload
        assert metadata_payload["target_capabilities"] == ["benchmark_runner"], metadata_payload
        after_metadata = state_file.read_text(encoding="utf-8")
        assert after_metadata.count("- [ ] Summarize the read-only evidence after the user") == 1, after_metadata
        agent_block_start = after_metadata.index("- [ ] Summarize the read-only evidence after the user")
        agent_metadata_start = after_metadata.index("<!-- loopx:todo", agent_block_start)
        assert after_metadata.index("checklist is done.", agent_block_start) < agent_metadata_start, after_metadata
        assert "status=open task_class=advancement_task action_kind=run_eval" in after_metadata
        assert "required_capabilities=shell%2Cbenchmark_runner" in after_metadata
        assert "target_capabilities=benchmark_runner" in after_metadata
        fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        assert fields["user_todos"]["items"][0]["text"] == USER_TODO, fields
        assert fields["user_todos"]["items"][0]["todo_id"].startswith("todo_"), fields
        assert fields["agent_todos"]["items"][0]["text"] == AGENT_TODO, fields
        assert fields["agent_todos"]["items"][0]["todo_id"].startswith("todo_"), fields
        assert fields["agent_todos"]["items"][0]["task_class"] == "advancement_task", fields
        assert fields["agent_todos"]["items"][0]["action_kind"] == "run_eval", fields
        assert fields["agent_todos"]["items"][0]["required_capabilities"] == [
            "shell",
            "benchmark_runner",
        ], fields
        assert fields["agent_todos"]["items"][0]["target_capabilities"] == [
            "benchmark_runner",
        ], fields
        assert fields["user_todos"]["source_section"] == "User Todo / Owner Review Reading Queue", fields
        assert fields["agent_todos"]["source_section"] == "Agent Todo", fields

        missing_claim = run_cli_error(
            registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
        )
        assert "requires --claimed-by" in missing_claim["error"], missing_claim

        unknown_claim = run_cli_error(
            registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--claimed-by",
            "unregistered-agent",
        )
        assert "is not registered" in unknown_claim["error"], unknown_claim

        claim_rejects_successor_args = run_cli_error(
            registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--claimed-by",
            "codex-main-control",
            "--next-agent-todo",
            "Review claimed work.",
        )
        assert "--next-agent-todo" in claim_rejects_successor_args["error"], claim_rejects_successor_args
        assert "todo claim only accepts" in claim_rejects_successor_args["error"], claim_rejects_successor_args

        claim_payload = run_cli(
            registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--claimed-by",
            "codex-main-control",
        )
        assert claim_payload["changed"] is True, claim_payload
        assert claim_payload["claimed_by"] == "codex-main-control", claim_payload
        claimed_fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        claimed_item = claimed_fields["agent_todos"]["items"][0]
        assert claimed_item["claimed_by"] == "codex-main-control", claimed_item
        assert claimed_fields["agent_todos"]["claimed_open_count"] == 1, claimed_fields
        assert claimed_fields["agent_todos"]["unclaimed_open_count"] == 0, claimed_fields

        preserve_claim_payload = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--note",
            "Claim-preserving progress note.",
        )
        assert preserve_claim_payload["changed"] is True, preserve_claim_payload
        assert preserve_claim_payload["claimed_by"] == "codex-main-control", preserve_claim_payload
        preserved_claim_fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        preserved_claim_item = preserved_claim_fields["agent_todos"]["items"][0]
        assert preserved_claim_item["claimed_by"] == "codex-main-control", preserved_claim_item
        assert preserved_claim_item["task_class"] == "advancement_task", preserved_claim_item
        assert preserved_claim_item["action_kind"] == "run_eval", preserved_claim_item
        assert preserved_claim_item["required_capabilities"] == [
            "shell",
            "benchmark_runner",
        ], preserved_claim_item
        assert preserved_claim_item["target_capabilities"] == [
            "benchmark_runner",
        ], preserved_claim_item

        conflicting_claim = run_cli_error(
            registry_path,
            "todo",
            "claim",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--claimed-by",
            "codex-side-bypass",
        )
        assert "already claimed_by='codex-main-control'" in conflicting_claim["error"], conflicting_claim
        assert "clear or transfer" in conflicting_claim["error"], conflicting_claim

        clear_claim_payload = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--clear-claim",
        )
        assert clear_claim_payload["changed"] is True, clear_claim_payload
        cleared_fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        assert "claimed_by" not in cleared_fields["agent_todos"]["items"][0], cleared_fields

        update_payload = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            metadata_payload["todo_id"],
            "--text",
            UPDATED_AGENT_TODO,
            "--status",
            "done",
            "--evidence",
            "Validated compact evidence summary.",
        )
        assert update_payload["changed"] is True, update_payload
        assert update_payload["text_changed"] is True, update_payload
        assert update_payload["status_changed"] is True, update_payload
        assert update_payload["todo"] == UPDATED_AGENT_TODO, update_payload
        after_update = state_file.read_text(encoding="utf-8")
        assert f"- [x] {UPDATED_AGENT_TODO}" in after_update, after_update
        assert "Summarize the read-only evidence after the user" not in after_update, after_update
        assert "status=done" in after_update, after_update
        assert "Validated%20compact%20evidence%20summary." in after_update, after_update
        updated_fields = parse_active_state_todos(after_update)
        updated_agent_item = updated_fields["agent_todos"]["items"][0]
        assert updated_agent_item["text"] == UPDATED_AGENT_TODO, updated_agent_item
        assert updated_agent_item["status"] == "done", updated_agent_item
        assert updated_agent_item["done"] is True, updated_agent_item

    print("todo-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
