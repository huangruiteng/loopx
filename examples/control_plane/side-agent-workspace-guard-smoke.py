#!/usr/bin/env python3
"""Exercise the side-agent workspace guard across real git worktrees."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "workspace-guard-canary"
PRIMARY_AGENT_ID = "codex-main-control"
SIDE_AGENT_ID = "codex-product-capability"


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def run_cli(cwd: Path, *args: str, registry_path: Path, runtime: Path) -> dict:
    env = os.environ.copy()
    python_path = str(REPO_ROOT)
    if env.get("PYTHONPATH"):
        python_path = f"{python_path}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = python_path
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
    primary = root / "primary-project"
    independent = root / "side-agent-worktree"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = primary / state_file
    registry_path = primary / ".loopx" / "registry.json"

    primary.mkdir(parents=True)
    (primary / "README.md").write_text("# Workspace Guard Canary\n", encoding="utf-8")
    run_git(primary, "init", "--initial-branch", "main")
    run_git(primary, "add", "README.md")
    run_git(
        primary,
        "-c",
        "user.name=LoopX Canary",
        "-c",
        "user.email=loopx-canary@example.invalid",
        "commit",
        "-m",
        "initial fixture",
    )
    run_git(primary, "worktree", "add", "-b", "side-agent-work", str(independent))

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "owner_mode: goal\n"
        'objective: "Exercise side-agent workspace guard."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Workspace Guard Canary\n\n"
        "## Objective\n\n"
        "Exercise side-agent workspace guard.\n\n"
        "## Next Action\n\n"
        "- Run one bounded side-agent delivery batch from an independent worktree.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Run one bounded side-agent delivery batch from an independent worktree.\n"
        f"  <!-- loopx:todo todo_id=todo_workspace_guard status=open "
        f"task_class=advancement_task action_kind=state_machine_canary_refactor "
        f"claimed_by={SIDE_AGENT_ID} -->\n\n"
        "## Progress Ledger\n\n"
        "- Initialized workspace guard fixture.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "workspace-guard-fixture",
                        "status": "active",
                        "repo": str(primary),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "workspace_guard_fixture_v0",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                        "coordination": {
                            "registered_agents": [PRIMARY_AGENT_ID, SIDE_AGENT_ID],
                            "primary_agent": PRIMARY_AGENT_ID,
                        },
                        "workspace_guard_policy": {
                            "side_agent_independent_worktree_required": True,
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
    return primary, independent, runtime, registry_path


def enable_peer_runtime(
    primary: Path,
    registry_path: Path,
    *,
    claimed_by: str,
) -> None:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    goal = payload["goals"][0]
    goal["coordination"] = {
        "agent_model": "peer_v1",
        "registered_agents": [PRIMARY_AGENT_ID, SIDE_AGENT_ID],
    }
    goal.pop("workspace_guard_policy", None)
    registry_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state_path = primary / goal["state_file"]
    state = state_path.read_text(encoding="utf-8")
    state = state.replace(
        "action_kind=state_machine_canary_refactor",
        "action_kind=fix",
    )
    for agent_id in (PRIMARY_AGENT_ID, SIDE_AGENT_ID):
        state = state.replace(f"claimed_by={agent_id}", f"claimed_by={claimed_by}")
    state_path.write_text(state, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-side-agent-workspace-guard-") as tmp:
        root = Path(tmp)
        primary, independent, runtime, registry_path = write_fixture(root)
        side_from_primary = run_cli(
            primary,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            SIDE_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert side_from_primary["ok"] is True, side_from_primary
        assert side_from_primary["should_run"] is True, side_from_primary
        assert side_from_primary["decision"] == "workspace_guard", side_from_primary
        assert side_from_primary["effective_action"] == "side_agent_workspace_repair", side_from_primary
        assert side_from_primary["normal_delivery_allowed"] is False, side_from_primary
        guard = side_from_primary["workspace_guard"]
        assert guard["blocks_delivery"] is True, guard
        assert guard["current_workspace"] == "primary_checkout", guard
        assert guard["required_workspace"] == "independent_git_worktree", guard
        assert guard["agent_id"] == SIDE_AGENT_ID, guard

        side_from_independent = run_cli(
            independent,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            SIDE_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert side_from_independent["ok"] is True, side_from_independent
        assert side_from_independent["should_run"] is True, side_from_independent
        assert side_from_independent["decision"] == "run", side_from_independent
        assert side_from_independent["effective_action"] == "normal_run", side_from_independent
        assert side_from_independent["normal_delivery_allowed"] is True, side_from_independent
        assert "workspace_guard" not in side_from_independent, side_from_independent

        primary_from_primary = run_cli(
            primary,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            PRIMARY_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert primary_from_primary["ok"] is True, primary_from_primary
        assert primary_from_primary["agent_identity"]["role"] == "primary-agent", primary_from_primary
        assert primary_from_primary["effective_action"] != "side_agent_workspace_repair", primary_from_primary
        assert "workspace_guard" not in primary_from_primary, primary_from_primary

        enable_peer_runtime(primary, registry_path, claimed_by=SIDE_AGENT_ID)
        peer_from_primary = run_cli(
            primary,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            SIDE_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert peer_from_primary["effective_action"] == "agent_workspace_repair", peer_from_primary
        assert peer_from_primary["workspace_guard"]["schema_version"] == (
            "agent_workspace_guard_v1"
        ), peer_from_primary
        assert "primary_agent" not in peer_from_primary["workspace_guard"], peer_from_primary
        assert peer_from_primary["interaction_contract"]["mode"] == (
            "agent_workspace_repair"
        ), peer_from_primary

        peer_from_independent = run_cli(
            independent,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            SIDE_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert "workspace_guard" not in peer_from_independent, peer_from_independent

        enable_peer_runtime(primary, registry_path, claimed_by=PRIMARY_AGENT_ID)
        other_peer_from_primary = run_cli(
            primary,
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            PRIMARY_AGENT_ID,
            "--scan-path",
            str(primary),
            registry_path=registry_path,
            runtime=runtime,
        )
        assert other_peer_from_primary["effective_action"] == (
            "agent_workspace_repair"
        ), other_peer_from_primary


if __name__ == "__main__":
    main()
