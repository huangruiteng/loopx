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
                        "adapter": {
                            "kind": "generic_project_goal_v0",
                            "status": "connected",
                        },
                        "authority_sources": [],
                        "coordination": {
                            "registered_agents": [
                                "codex-main-control",
                                "codex-side-bypass",
                            ],
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


def set_claimed_by(state_file: Path, *, todo_id: str, owner: str | None) -> None:
    lines = state_file.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"todo_id={todo_id}" not in line:
            continue
        line = re.sub(r"\s+claimed_by=[^\s<>]+", "", line)
        if owner:
            line = line.replace(" -->", f" claimed_by={owner} -->")
        lines[index] = line
        state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    raise AssertionError(f"todo metadata not found: {todo_id}")


def command(
    registry_path: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        check=check,
        text=True,
        capture_output=True,
    )


def cli(
    registry_path: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return command(registry_path, "task-lease", *args, check=check)


def lifecycle_cli(
    registry_path: Path,
    action: str,
    owner: str,
    idempotency_key: str,
    expected_version: int,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return cli(
        registry_path,
        action,
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        TODO_A,
        "--owner",
        owner,
        "--idempotency-key",
        idempotency_key,
        "--expected-version",
        str(expected_version),
        check=check,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def inspected_lease(registry_path: Path, todo_id: str) -> dict[str, Any]:
    return payload(
        cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", todo_id)
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-task-lease-smoke-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))

        set_claimed_by(
            state_file,
            todo_id=TODO_A,
            owner="codex-main-control",
        )
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
        assert first["lease"]["lease_epoch"] == 1, first
        assert first["lease"]["acquire_ttl_seconds"] == 120, first

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
        assert conflict_payload["error_code"] == "write_scope_conflict", (
            conflict_payload
        )
        assert conflict_payload["conflicts"][0]["todo_id"] == TODO_A, conflict_payload
        after_scope_conflict = inspected_lease(registry_path, TODO_A)
        assert after_scope_conflict["lease"] == first["lease"], after_scope_conflict
        rejected_scope = inspected_lease(registry_path, TODO_C)
        assert rejected_scope["active"] is False, rejected_scope
        assert rejected_scope["lease"] is None, rejected_scope

        renewed = payload(
            lifecycle_cli(
                registry_path,
                "renew",
                "codex-main-control",
                "turn-1",
                1,
            )
        )
        assert renewed["ok"] is True and renewed["lease"]["version"] == 2, renewed
        assert renewed["lease"]["lease_epoch"] == 1, renewed

        claim_blocked_transfer = cli(
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
        assert claim_blocked_transfer.returncode == 1, claim_blocked_transfer.stdout
        assert payload(claim_blocked_transfer)["error_code"] == (
            "owner_conflicts_with_claim"
        )
        set_claimed_by(state_file, todo_id=TODO_A, owner=None)
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
        assert transferred["lease"]["lease_epoch"] == 2, transferred

        stale_owner = lifecycle_cli(
            registry_path,
            "renew",
            "codex-main-control",
            "turn-1",
            3,
            check=False,
        )
        assert stale_owner.returncode == 1, stale_owner.stdout
        assert payload(stale_owner)["error_code"] == "lease_cas_mismatch"
        after_stale_owner = inspected_lease(registry_path, TODO_A)
        assert after_stale_owner["lease"] == transferred["lease"], after_stale_owner

        renewed_after_transfer = payload(
            lifecycle_cli(
                registry_path,
                "renew",
                "codex-side-bypass",
                "side-transfer",
                3,
            )
        )
        assert renewed_after_transfer["lease"]["owner"] == "codex-side-bypass"
        assert renewed_after_transfer["lease"]["version"] == 4
        assert renewed_after_transfer["lease"]["lease_epoch"] == 2

        stale_version = lifecycle_cli(
            registry_path,
            "release",
            "codex-side-bypass",
            "side-transfer",
            3,
            check=False,
        )
        assert stale_version.returncode == 1, stale_version.stdout
        assert payload(stale_version)["error_code"] == "version_mismatch"
        after_stale_version = inspected_lease(registry_path, TODO_A)
        assert after_stale_version["lease"] == renewed_after_transfer["lease"], (
            after_stale_version
        )

        released = payload(
            lifecycle_cli(
                registry_path,
                "release",
                "codex-side-bypass",
                "side-transfer",
                4,
            )
        )
        assert released["released"] is True, released
        assert released["lease"]["status"] == "released", released
        assert released["lease"]["version"] == 4, released
        assert released["lease"]["lease_epoch"] == 2, released
        assert released["lease"]["released_at"] == released["lease"]["updated_at"], (
            released
        )
        inspected = payload(
            cli(registry_path, "inspect", "--goal-id", GOAL_ID, "--todo-id", TODO_A)
        )
        assert inspected["active"] is False, inspected
        assert inspected["lease"]["status"] == "released", inspected

        release_replay = payload(
            lifecycle_cli(
                registry_path,
                "release",
                "codex-side-bypass",
                "side-transfer",
                4,
            )
        )
        assert release_replay["released"] is True, release_replay
        assert release_replay["idempotent"] is True, release_replay

        reused_key = cli(
            registry_path,
            "acquire",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--owner",
            "codex-side-bypass",
            "--idempotency-key",
            "side-transfer",
            "--ttl-seconds",
            "120",
            "--write-scope",
            "loopx/**",
            check=False,
        )
        assert reused_key.returncode == 1, reused_key.stdout
        assert payload(reused_key)["error_code"] == "idempotency_key_reuse"

        next_generation = payload(
            cli(
                registry_path,
                "acquire",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--owner",
                "codex-side-bypass",
                "--idempotency-key",
                "side-next-generation",
                "--ttl-seconds",
                "120",
                "--write-scope",
                "loopx/**",
            )
        )
        assert next_generation["lease"]["version"] == 5, next_generation
        assert next_generation["lease"]["lease_epoch"] == 3, next_generation

        stale_completion = command(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            TODO_A,
            "--agent-id",
            "codex-side-bypass",
            "--task-lease-idempotency-key",
            "side-transfer",
            "--task-lease-expected-version",
            "4",
            "--evidence",
            "stale execution must not commit",
            "--no-follow-up",
            check=False,
        )
        assert stale_completion.returncode == 1, stale_completion.stdout
        assert payload(stale_completion)["error_code"] == "lease_cas_mismatch"

        completed = payload(
            command(
                registry_path,
                "todo",
                "complete",
                "--goal-id",
                GOAL_ID,
                "--todo-id",
                TODO_A,
                "--agent-id",
                "codex-side-bypass",
                "--task-lease-idempotency-key",
                "side-next-generation",
                "--task-lease-expected-version",
                "5",
                "--evidence",
                "current execution committed",
                "--no-follow-up",
            )
        )
        assert completed["ok"] is True, completed
        assert completed["task_lease_fence"]["lease_epoch"] == 3, completed

    print("task-lease-runtime-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
