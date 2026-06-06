#!/usr/bin/env python3
"""Smoke-test the safe per-goal registry configuration command."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "configure-goal-fixture"


def write_registry(root: Path) -> Path:
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(root / "runtime"),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "configure-goal-smoke",
                        "status": "active",
                        "repo": str(root / "project"),
                        "state_file": ".codex/goals/configure-goal-fixture/STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "quota": {"compute": 1, "window_hours": 24},
                        "spawn_policy": {"mode": "default", "allowed": False, "max_children": 0},
                        "control_plane": {
                            "self_repair": {
                                "enabled": False,
                                "allow_health_blocker_repair": False,
                                "allow_waiting_projection_repair": False,
                            }
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
    return registry_path


def run_cli(registry_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        check=check,
        text=True,
        capture_output=True,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def goal_from_registry(registry_path: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    return registry["goals"][0]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-configure-goal-smoke-") as tmp:
        root = Path(tmp)
        registry_path = write_registry(root)
        original = registry_path.read_text(encoding="utf-8")

        dry = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
            "--self-repair-enabled",
            "--self-repair-health",
            "--self-repair-waiting-projection",
            "--orchestration-mode",
            "multi_subagent",
            "--spawn-allowed",
            "--max-children",
            "2",
            "--allowed-domain",
            "docs",
            "--allowed-domain",
            "validation",
        ))
        assert dry["ok"] is True, dry
        assert dry["dry_run"] is True, dry
        assert dry["changed"] is True, dry
        assert dry["written"] is False, dry
        assert registry_path.read_text(encoding="utf-8") == original

        applied = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
            "--self-repair-enabled",
            "--self-repair-health",
            "--self-repair-waiting-projection",
            "--orchestration-mode",
            "multi_subagent",
            "--spawn-allowed",
            "--max-children",
            "2",
            "--allowed-domain",
            "docs,validation",
            "--execute",
        ))
        assert applied["ok"] is True, applied
        assert applied["dry_run"] is False, applied
        assert applied["written"] is True, applied
        goal = goal_from_registry(registry_path)
        assert goal["quota"]["compute"] == 0.5, goal
        assert goal["control_plane"]["self_repair"]["enabled"] is True, goal
        assert goal["control_plane"]["self_repair"]["allow_health_blocker_repair"] is True, goal
        assert goal["control_plane"]["self_repair"]["allow_waiting_projection_repair"] is True, goal
        assert goal["spawn_policy"]["mode"] == "multi_subagent", goal
        assert goal["spawn_policy"]["allowed"] is True, goal
        assert goal["spawn_policy"]["max_children"] == 2, goal
        assert goal["spawn_policy"]["allowed_domains"] == ["docs", "validation"], goal

        no_change = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
        ))
        assert no_change["ok"] is True, no_change
        assert no_change["changed"] is False, no_change

        invalid = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0",
            check=False,
        ))
        assert invalid["ok"] is False, invalid
        assert "greater than 0" in invalid["error"], invalid

    print("configure-goal-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
