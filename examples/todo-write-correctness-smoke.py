#!/usr/bin/env python3
"""Smoke-test todo add/update dry-run write correctness packets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "todo-write-correctness-goal"
AGENT_ID = "codex-product-capability"
TODO_TEXT = "Preview a todo write correctness packet before mutating state."


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
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
        "# Todo Write Correctness Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Existing todo for update preview.\n"
        "  <!-- loopx:todo todo_id=todo_existing status=open task_class=advancement_task -->\n",
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
                        "domain": "todo-write-correctness-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "authority_sources": [],
                        "coordination": {
                            "registered_agents": ["codex-main-control", AGENT_ID],
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
    return registry_path, state_file, project


def run_cli(registry_path: Path, *args: str, as_json: bool = True) -> dict | str:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--registry",
        str(registry_path),
    ]
    if as_json:
        command.extend(["--format", "json"])
    command.extend(args)
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout) if as_json else result.stdout


def assert_packet(
    payload: dict,
    *,
    state_file: Path,
    project: Path,
    write_class: str,
    todo_id: str,
    claimed_by: str | None,
) -> dict:
    packet = payload.get("local_state_write_correctness")
    assert isinstance(packet, dict), payload
    assert packet["schema_version"] == "local_state_write_correctness_v0", packet
    assert str(project) not in json.dumps(packet, ensure_ascii=False), packet

    intent = packet["write_intent"]
    assert intent["goal_id"] == GOAL_ID, packet
    assert intent["writer_id"] == "loopx.todo", packet
    assert intent["write_class"] == write_class, packet
    assert intent["target_refs"]["state_file_ref"] == "registry.goal.state_file", packet
    assert intent["target_refs"]["todo_id"] == todo_id, packet
    assert intent["expected_revision"]["value"] == "sha256:" + hashlib.sha256(
        state_file.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest(), packet
    assert intent["idempotency_key"].startswith(f"{GOAL_ID}:{write_class}:"), packet

    assert packet["lock_boundary"] == {
        "kind": "per_goal",
        "lock_key": f"goal:{GOAL_ID}",
        "narrower_lock_allowed": "per_todo_when_patch_is_single_todo_and_order_independent",
    }, packet
    assert packet["preview"]["mode"] == "dry_run", packet
    assert packet["preview"]["non_destructive"] is True, packet
    assert packet["preview"]["expected_write_scopes"] == ["active_state"], packet
    assert packet["apply_result"]["status"] == "preview_only", packet
    boundary = packet["projection"]["public_boundary"]
    assert boundary == {
        "raw_logs_copied": False,
        "private_paths_copied": False,
        "credentials_copied": False,
        "production_action_authorized": False,
    }, packet

    if claimed_by:
        assert intent["lease_ref"]["todo_id"] == todo_id, packet
        assert intent["lease_ref"]["claimed_by"] == claimed_by, packet
        assert packet["projection"]["lease_projection"] == {
            "todo_id": todo_id,
            "claimed_by": claimed_by,
            "lease_state": "preview_only",
        }, packet
    else:
        assert intent["lease_ref"] is None, packet
        assert packet["projection"]["lease_projection"] is None, packet
    return packet


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-write-correctness-") as tmp:
        registry_path, state_file, project = write_fixture(Path(tmp))
        original = state_file.read_text(encoding="utf-8")

        add_dry_run = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--claimed-by",
            AGENT_ID,
            "--dry-run",
        )
        add_dry_run_repeat = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--claimed-by",
            AGENT_ID,
            "--dry-run",
        )
        assert add_dry_run["dry_run"] is True, add_dry_run
        assert add_dry_run["added"] is True, add_dry_run
        assert state_file.read_text(encoding="utf-8") == original
        add_packet = assert_packet(
            add_dry_run,
            state_file=state_file,
            project=project,
            write_class="todo_add",
            todo_id=add_dry_run["todo_id"],
            claimed_by=AGENT_ID,
        )
        repeat_packet = add_dry_run_repeat["local_state_write_correctness"]
        assert (
            add_packet["write_intent"]["idempotency_key"]
            == repeat_packet["write_intent"]["idempotency_key"]
        )

        add_markdown = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
            "--dry-run",
            as_json=False,
        )
        assert "## Local State Write Correctness" in add_markdown, add_markdown
        assert "status: `preview_only`" in add_markdown, add_markdown

        real_add = run_cli(
            registry_path,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            TODO_TEXT,
        )
        assert real_add["dry_run"] is False, real_add
        assert "local_state_write_correctness" not in real_add, real_add

        update_dry_run = run_cli(
            registry_path,
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            "todo_existing",
            "--claimed-by",
            AGENT_ID,
            "--note",
            "Preview update without writing state.",
            "--dry-run",
        )
        assert update_dry_run["dry_run"] is True, update_dry_run
        assert update_dry_run["changed"] is True, update_dry_run
        assert_packet(
            update_dry_run,
            state_file=state_file,
            project=project,
            write_class="todo_update",
            todo_id="todo_existing",
            claimed_by=AGENT_ID,
        )
        assert "Preview update without writing state." not in state_file.read_text(
            encoding="utf-8"
        )

    print("todo-write-correctness-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
