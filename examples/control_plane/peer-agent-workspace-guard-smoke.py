#!/usr/bin/env python3
"""Exercise the peer workspace guard across real git worktrees."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "workspace-guard-canary"
PEER_ALPHA = "codex-alpha"
PEER_BETA = "codex-beta"


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def run_cli(cwd: Path, *args: str, registry_path: Path, runtime: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(REPO_ROOT), env.get("PYTHONPATH")) if value
    )
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
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout)


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    independent = root / "peer-worktree"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    project.mkdir(parents=True)
    (project / "README.md").write_text("# Workspace Guard Canary\n", encoding="utf-8")
    run_git(project, "init", "--initial-branch", "main")
    run_git(project, "add", "README.md")
    run_git(
        project,
        "-c",
        "user.name=LoopX Canary",
        "-c",
        "user.email=loopx-canary@example.invalid",
        "commit",
        "-m",
        "initial fixture",
    )
    run_git(project, "worktree", "add", "-b", "peer-work", str(independent))

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\nstatus: active\nowner_mode: goal\n"
        'objective: "Exercise peer workspace guard."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n---\n\n"
        "# Workspace Guard Canary\n\n## Agent Todo\n\n"
        "- [ ] [P1] Run one bounded peer delivery batch from an independent worktree.\n"
        f"  <!-- loopx:todo todo_id=todo_workspace_guard status=open "
        f"task_class=advancement_task action_kind=fix claimed_by={PEER_ALPHA} -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "workspace-guard-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "workspace_guard_fixture_v1",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [PEER_ALPHA, PEER_BETA],
                        },
                        "workspace_guard_policy": {
                            "peer_independent_worktree_required": True,
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
    return project, independent, runtime, registry_path


def should_run(
    cwd: Path,
    project: Path,
    runtime: Path,
    registry_path: Path,
) -> dict:
    return run_cli(
        cwd,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        PEER_ALPHA,
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime=runtime,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-peer-workspace-guard-") as tmp:
        project, independent, runtime, registry_path = write_fixture(Path(tmp))

        guarded = should_run(project, project, runtime, registry_path)
        assert guarded["decision"] == "workspace_guard", guarded
        assert guarded["effective_action"] == "agent_workspace_repair", guarded
        assert guarded["normal_delivery_allowed"] is False, guarded
        assert guarded["agent_identity"]["agent_model"] == "peer_v1", guarded
        assert "role" not in guarded["agent_identity"], guarded
        guard = guarded["workspace_guard"]
        assert guard["schema_version"] == "agent_workspace_guard_v1", guard
        assert guard["current_workspace"] == "canonical_checkout", guard
        assert guard["agent_id"] == PEER_ALPHA, guard
        assert "primary_agent" not in guard, guard

        allowed = should_run(independent, project, runtime, registry_path)
        assert allowed["decision"] == "run", allowed
        assert allowed["effective_action"] == "normal_run", allowed
        assert allowed["normal_delivery_allowed"] is True, allowed
        assert "workspace_guard" not in allowed, allowed


if __name__ == "__main__":
    main()
