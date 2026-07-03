#!/usr/bin/env python3
"""Smoke-test refresh-state goal vision budget enforcement."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "goal-vision-budget-fixture"
AGENT_ID = "research-curator"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Goal Vision Budget Fixture\n\n"
        "## Next Action\n\n"
        "- Refresh the compact goal vision packet.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "goal-vision-budget-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                        "authority_sources": [],
                        "coordination": {
                            "registered_agents": [AGENT_ID],
                            "primary_agent": AGENT_ID,
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
    return registry_path, runtime, project


def run_cli(
    registry_path: Path,
    runtime: Path,
    *,
    vision_path: Path,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--classification",
            "goal_vision_patch_recorded",
            "--delivery-batch-scale",
            "single_surface",
            "--delivery-outcome",
            "outcome_progress",
            "--autonomous-replan-recorded",
            "--agent-vision-json",
            str(vision_path),
            "--dry-run",
            "--no-global-sync",
        ],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-goal-vision-budget-") as tmp:
        root = Path(tmp)
        registry_path, runtime, _project = write_fixture(root)
        valid_path = root / "valid-vision.json"
        invalid_path = root / "invalid-vision.json"

        write_json(
            valid_path,
            {
                "schema_version": "goal_vision_replan_contract_v0",
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "state": "vision_patch_proposed",
                "vision_patch": {
                    "vision_summary": "Map the next evidence frontier and hand off one runnable claim.",
                    "role_scope": "Owns framing; does not run evaluation.",
                    "acceptance_summary": "One successor todo plus evidence references.",
                    "replan_trigger_summary": "Frontier exhausted while acceptance remains open.",
                },
                "todo_delta": ["create_successor"],
                "validation": {"write_correctness_checked": True},
            },
        )
        valid = payload(
            run_cli(registry_path, runtime, vision_path=valid_path, check=True)
        )
        assert valid["ok"] is True, valid
        assert valid["dry_run"] is True, valid
        assert valid["autonomous_replan_recorded"] is True, valid
        assert valid["repair_delta_contract"]["delta_present"] is True, valid
        assert "goal_vision_patch" in valid["repair_delta_contract"]["delta_kinds"], valid
        assert valid["agent_vision"]["vision_budget"]["status"] == "ok", valid
        assert valid["agent_vision"]["validation"]["budget_checked"] is True, valid
        assert valid["agent_vision"]["schema_version"] == "goal_vision_replan_contract_v0", valid

        write_json(
            invalid_path,
            {
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "vision_patch": {"vision_summary": "x" * 421},
            },
        )
        invalid_result = run_cli(
            registry_path,
            runtime,
            vision_path=invalid_path,
            check=False,
        )
        assert invalid_result.returncode == 1, invalid_result
        invalid = payload(invalid_result)
        assert invalid["ok"] is False, invalid
        assert "vision_budget_exceeded" in invalid["error"], invalid
        assert "vision_summary" in invalid["error"], invalid

    print("goal-vision-refresh-state-budget-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
