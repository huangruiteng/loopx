#!/usr/bin/env python3
"""Smoke-test per-project LoopX uninstall safety."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_GOAL_ID = "project-uninstall-target"
KEEP_GOAL_ID = "project-uninstall-keep"
OTHER_GOAL_ID = "other-project-goal"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def goal(project: Path, registry_path: Path, goal_id: str) -> dict[str, object]:
    return {
        "id": goal_id,
        "objective": f"Fixture {goal_id}.",
        "domain": "project-uninstall-smoke",
        "repo": str(project),
        "state_file": f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md",
        "status": "connected-read-only",
        "adapter": {"kind": "fixture", "status": "connected-read-only"},
        "source_registry": str(registry_path),
    }


def write_state(project: Path, goal_id: str) -> None:
    state = project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(f"# {goal_id}\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    runtime = root / "runtime"
    project = root / "project"
    other_project = root / "other-project"
    registry_path = project / ".loopx" / "registry.json"
    other_registry_path = other_project / ".loopx" / "registry.json"

    for goal_id in (TARGET_GOAL_ID, KEEP_GOAL_ID):
        write_state(project, goal_id)
    write_state(other_project, OTHER_GOAL_ID)

    local_goals = [
        goal(project, registry_path, TARGET_GOAL_ID),
        goal(project, registry_path, KEEP_GOAL_ID),
    ]
    write_json(
        registry_path,
        {
            "schema_version": "0.1",
            "registry_role": "project-local",
            "common_runtime_root": str(runtime),
            "goals": local_goals,
        },
    )
    write_json(
        runtime / "registry.global.json",
        {
            "schema_version": "0.1",
            "registry_role": "global-local",
            "common_runtime_root": str(runtime),
            "goals": [
                *local_goals,
                goal(other_project, other_registry_path, OTHER_GOAL_ID),
            ],
        },
    )
    return project, registry_path, runtime, runtime / "registry.global.json"


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"expected JSON output, got:\n{result.stdout}\n{result.stderr}") from exc


def goal_ids(registry_path: Path) -> list[str]:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    return [str(goal["id"]) for goal in data.get("goals", []) if isinstance(goal, dict)]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-project-uninstall-") as tmp:
        project, registry_path, runtime, global_registry = write_fixture(Path(tmp))
        local_before = registry_path.read_text(encoding="utf-8")
        global_before = global_registry.read_text(encoding="utf-8")

        dry_run = payload(
            run_cli(
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "uninstall-project",
                "--goal-id",
                TARGET_GOAL_ID,
                "--archive-state",
            )
        )
        assert dry_run["ok"] is True, dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["goal_ids"] == [TARGET_GOAL_ID], dry_run
        assert dry_run["global_registry_removed_goal_ids"] == [TARGET_GOAL_ID], dry_run
        assert registry_path.read_text(encoding="utf-8") == local_before
        assert global_registry.read_text(encoding="utf-8") == global_before

        no_local_fallback = payload(
            run_cli(
                "--runtime-root",
                str(runtime),
                "uninstall-project",
                "--goal-id",
                TARGET_GOAL_ID,
                check=False,
            )
        )
        assert no_local_fallback["ok"] is False, no_local_fallback
        assert "project registry does not exist" in no_local_fallback["error"], no_local_fallback

        applied = payload(
            run_cli(
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "uninstall-project",
                "--goal-id",
                TARGET_GOAL_ID,
                "--archive-state",
                "--execute",
            )
        )
        assert applied["ok"] is True, applied
        assert applied["dry_run"] is False, applied
        assert applied["wrote_local_registry"] is True, applied
        assert applied["wrote_global_registry"] is True, applied
        assert applied["global_registry_removed_goal_ids"] == [TARGET_GOAL_ID], applied
        assert Path(str(applied["local_registry_backup_path"])).exists(), applied
        assert Path(str(applied["global_registry_backup_path"])).exists(), applied
        assert goal_ids(registry_path) == [KEEP_GOAL_ID]
        assert goal_ids(global_registry) == [KEEP_GOAL_ID, OTHER_GOAL_ID]
        assert not (project / ".codex" / "goals" / TARGET_GOAL_ID).exists()
        archived = applied["state_actions"][0]["archive_path"]
        assert Path(str(archived)).exists(), applied
        assert (project / ".codex" / "goals" / KEEP_GOAL_ID / "ACTIVE_GOAL_STATE.md").exists()

        blocked = payload(
            run_cli(
                "--registry",
                str(global_registry),
                "--runtime-root",
                str(runtime),
                "uninstall-project",
                "--goal-id",
                KEEP_GOAL_ID,
                "--execute",
                check=False,
            )
        )
        assert blocked["ok"] is False, blocked
        assert "refused to operate on the global registry" in blocked["error"], blocked

    print("project-uninstall-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
