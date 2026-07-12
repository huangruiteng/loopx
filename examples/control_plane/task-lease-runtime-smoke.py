#!/usr/bin/env python3
"""Smoke-test the task_lease_v0 runtime and CLI contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.task_lease import write_scopes_overlap  # noqa: E402


GOAL_ID = "task-lease-runtime-goal"
TODO_A = "todo_taskleasea"
TODO_B = "todo_taskleaseb"
TODO_C = "todo_taskleasec"


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Agent Todo\n\n"
        f"- [ ] First independently claimable todo.\n"
        f"  <!-- loopx: todo_id={TODO_A} status=open -->\n"
        f"- [ ] Second independently claimable todo.\n"
        f"  <!-- loopx: todo_id={TODO_B} status=open -->\n"
        f"- [ ] Conflicting write-scope todo.\n"
        f"  <!-- loopx: todo_id={TODO_C} status=open -->\n",
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
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "authority_sources": [],
                        "coordination": {
                            "registered_agents": ["codex-main-control", "codex-side-bypass"],
                            "agent_model": "peer_v1",
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


def set_excluded_agents(state_file: Path, *, todo_id: str, agents: list[str]) -> None:
    lines = state_file.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"todo_id={todo_id}" not in line:
            continue
        line = re.sub(r"\s+excluded_agents=[^\s<>]+", "", line)
        if agents:
            line = line.replace(" -->", f" excluded_agents={','.join(agents)} -->")
        lines[index] = line
        state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"todo metadata not found: {todo_id}")


def set_todo_status(state_file: Path, *, todo_id: str, status: str) -> None:
    lines = state_file.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"todo_id={todo_id}" not in line:
            continue
        lines[index] = re.sub(r"\bstatus=[^\s<>]+", f"status={status}", line)
        state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"todo metadata not found: {todo_id}")


def cli(registry_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            "task-lease",
            *args,
        ],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def quota_should_run(registry_path: Path, *, agent_id: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            agent_id,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.stdout, result.stderr
    return json.loads(result.stdout)


def main() -> int:
    assert write_scopes_overlap(["docs/**"], ["docs/a.md"])
    assert write_scopes_overlap(["docs/sub/**"], ["docs/sub/a.md"])
    assert write_scopes_overlap(["docs/a*.md"], ["docs/ab.md"])
    assert not write_scopes_overlap(["docs/a.md"], ["docs/b.md"])

    with tempfile.TemporaryDirectory(prefix="loopx-task-lease-smoke-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))

        first = payload(
            cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "turn-1",
                "--ttl-seconds",
                "120",
                "--write-scope",
                "loopx/**",
            )
        )
        assert first["ok"] is True and first["acquired"] is True, first
        assert first["lease"]["schema_version"] == "task_lease_v0", first
        assert first["lease"]["version"] == 1, first
        assert first["lease"]["acquire_ttl_seconds"] == 120, first

        set_todo_status(state_file, todo_id=TODO_A, status="done")
        terminal_inspect = payload(
            cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", TODO_A)
        )
        assert terminal_inspect["active"] is False, terminal_inspect
        assert terminal_inspect["executor_constraint"]["reason"] == "todo_not_open", (
            terminal_inspect
        )
        terminal_renew = cli(
            registry_path,
            "renew",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-main-control",
            "--idempotency-key",
            "turn-1",
            check=False,
        )
        assert terminal_renew.returncode == 1, terminal_renew.stdout
        assert payload(terminal_renew)["error_code"] == "todo_not_open", terminal_renew.stdout
        set_todo_status(state_file, todo_id=TODO_A, status="open")

        set_todo_status(state_file, todo_id=TODO_C, status="deferred")
        terminal_acquire = cli(
            registry_path,
            "acquire",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_C,
            "--owner",
            "codex-side-bypass",
            "--idempotency-key",
            "deferred-acquire",
            check=False,
        )
        assert terminal_acquire.returncode == 1, terminal_acquire.stdout
        assert payload(terminal_acquire)["error_code"] == "todo_not_open", terminal_acquire.stdout
        set_todo_status(state_file, todo_id=TODO_C, status="open")

        unregistered_acquire = cli(
            registry_path,
            "acquire",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_C,
            "--owner",
            "codex-unregistered-peer",
            "--idempotency-key",
            "unregistered-acquire",
            "--write-scope",
            "scripts/**",
            check=False,
        )
        assert unregistered_acquire.returncode == 1, unregistered_acquire.stdout
        assert payload(unregistered_acquire)["error_code"] == "owner_not_registered", (
            unregistered_acquire.stdout
        )

        legacy_unregistered_path = Path(first["lease_path"]).with_name(f"{TODO_C}.json")
        legacy_unregistered_path.write_text(
            json.dumps(
                {
                    **first["lease"],
                    "todo_id": TODO_C,
                    "owner": "codex-unregistered-peer",
                    "write_scopes": ["scripts/**"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        legacy_inspect = payload(
            cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", TODO_C)
        )
        assert legacy_inspect["active"] is False, legacy_inspect
        assert legacy_inspect["executor_constraint"]["reason"] == "owner_not_registered", (
            legacy_inspect
        )
        legacy_unregistered_path.unlink()

        idempotent = payload(
            cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "turn-1",
                "--ttl-seconds",
                "120",
                "--write-scope",
                "loopx/**",
            )
        )
        assert idempotent["ok"] is True and idempotent["idempotent"] is True, idempotent
        assert idempotent["lease"]["version"] == 1, idempotent

        for retry_ttl, retry_scope in ((120, "docs/**"), (600, "loopx/**")):
            changed_retry = cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "turn-1",
                "--ttl-seconds",
                str(retry_ttl),
                "--write-scope",
                retry_scope,
                check=False,
            )
            assert changed_retry.returncode == 1, changed_retry.stdout
            assert payload(changed_retry)["error_code"] == "idempotency_key_reuse", (
                changed_retry.stdout
            )

        set_excluded_agents(
            state_file,
            todo_id=TODO_B,
            agents=["codex-side-bypass"],
        )
        blocked_acquire = cli(
            registry_path,
            "acquire",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_B,
            "--owner",
            "codex-side-bypass",
            "--idempotency-key",
            "side-blocked",
            check=False,
        )
        assert blocked_acquire.returncode == 1, blocked_acquire.stdout
        assert payload(blocked_acquire)["error_code"] == "owner_excluded_from_todo", (
            blocked_acquire.stdout
        )

        set_excluded_agents(state_file, todo_id=TODO_B, agents=[])
        same_goal_different_scope = payload(
            cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_B,
                "--owner",
                "codex-side-bypass",
                "--idempotency-key",
                "side-1",
                "--ttl-seconds",
                "120",
                "--write-scope",
                "docs/**",
            )
        )
        assert same_goal_different_scope["ok"] is True, same_goal_different_scope

        conflict = cli(
            registry_path,
            "acquire",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_C,
            "--owner",
            "codex-side-bypass",
            "--idempotency-key",
            "side-2",
            "--ttl-seconds",
            "120",
            "--write-scope",
            "loopx/cli_commands/todo.py",
            check=False,
        )
        assert conflict.returncode == 1, conflict.stdout
        conflict_payload = payload(conflict)
        assert conflict_payload["error_code"] == "write_scope_conflict", conflict_payload
        assert conflict_payload["conflicts"][0]["todo_id"] == TODO_A, conflict_payload

        mismatch = cli(
            registry_path,
            "renew",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-main-control",
            "--idempotency-key",
            "turn-1",
            "--expected-version",
            "99",
            check=False,
        )
        assert mismatch.returncode == 1, mismatch.stdout
        assert payload(mismatch)["error_code"] == "version_mismatch", mismatch.stdout

        renewed = payload(
            cli(
                registry_path,
                "renew",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "turn-1",
                "--expected-version",
                "1",
            )
        )
        assert renewed["ok"] is True and renewed["lease"]["version"] == 2, renewed

        set_excluded_agents(
            state_file,
            todo_id=TODO_A,
            agents=["codex-side-bypass"],
        )
        blocked_transfer = cli(
            registry_path,
            "transfer",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-main-control",
            "--idempotency-key",
            "turn-1",
            "--new-owner",
            "codex-side-bypass",
            "--new-idempotency-key",
            "side-transfer",
            "--expected-version",
            "2",
            check=False,
        )
        assert blocked_transfer.returncode == 1, blocked_transfer.stdout
        assert payload(blocked_transfer)["error_code"] == "owner_excluded_from_todo", (
            blocked_transfer.stdout
        )

        unregistered_transfer = cli(
            registry_path,
            "transfer",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-main-control",
            "--idempotency-key",
            "turn-1",
            "--new-owner",
            "codex-unregistered-peer",
            "--new-idempotency-key",
            "unregistered-transfer",
            "--expected-version",
            "2",
            check=False,
        )
        assert unregistered_transfer.returncode == 1, unregistered_transfer.stdout
        assert payload(unregistered_transfer)["error_code"] == "owner_not_registered", (
            unregistered_transfer.stdout
        )

        set_excluded_agents(state_file, todo_id=TODO_A, agents=[])
        transferred = payload(
            cli(
                registry_path,
                "transfer",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "turn-1",
                "--new-owner",
                "codex-side-bypass",
                "--new-idempotency-key",
                "side-transfer",
                "--expected-version",
                "2",
            )
        )
        assert transferred["lease"]["owner"] == "codex-side-bypass", transferred
        assert transferred["lease"]["version"] == 3, transferred

        set_excluded_agents(
            state_file,
            todo_id=TODO_A,
            agents=["codex-side-bypass"],
        )
        inspected = payload(cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", TODO_A))
        assert inspected["active"] is False and inspected["lease"]["version"] == 3, inspected
        assert inspected["executor_constraint"]["reason"] == "owner_excluded_from_todo", inspected

        blocked_renew = cli(
            registry_path,
            "renew",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-side-bypass",
            "--idempotency-key",
            "side-transfer",
            "--expected-version",
            "3",
            check=False,
        )
        assert blocked_renew.returncode == 1, blocked_renew.stdout
        assert payload(blocked_renew)["error_code"] == "owner_excluded_from_todo", (
            blocked_renew.stdout
        )

        quota = quota_should_run(registry_path, agent_id="codex-side-bypass")
        assert (quota.get("selected_todo") or {}).get("todo_id") != TODO_A, quota

        reacquired = payload(
            cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "main-takeover",
                "--expected-version",
                "3",
                "--write-scope",
                "loopx/**",
            )
        )
        assert reacquired["acquired"] is True, reacquired
        assert reacquired["lease"]["owner"] == "codex-main-control", reacquired
        assert reacquired["lease"]["version"] == 4, reacquired

        released = payload(
            cli(
                registry_path,
                "release",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-main-control",
                "--idempotency-key",
                "main-takeover",
                "--expected-version",
                "4",
            )
        )
        assert released["released"] is True, released
        assert payload(cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", TODO_A))["active"] is False

    print("task-lease-runtime-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
