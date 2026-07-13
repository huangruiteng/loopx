#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_json(runtime_root: Path, *args: str, expect_success: bool = True) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "--runtime-root",
            str(runtime_root),
            "retire-global-goal",
            *args,
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"expected failure, got: {result.stdout}")
    return json.loads(result.stdout)


def goal(goal_id: str, repo: Path, source_registry: Path) -> dict[str, object]:
    return {
        "id": goal_id,
        "repo": str(repo),
        "source_registry": str(source_registry),
        "state_file": f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md",
        "status": "active",
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-retire-global-goal-") as tmp:
        root = Path(tmp)
        runtime_root = root / "runtime"
        global_path = runtime_root / "registry.global.json"
        orphan_repo = root / "missing-orphan-repo"
        live_source_repo = root / "live-source-repo"
        live_source = live_source_repo / ".loopx" / "registry.json"
        live_state_repo = root / "live-state-repo"
        live_state = live_state_repo / ".codex" / "goals" / "live-state" / "ACTIVE_GOAL_STATE.md"
        write_json(live_source, {"schema_version": "0.1", "goals": []})
        live_state.parent.mkdir(parents=True, exist_ok=True)
        live_state.write_text("# Live State\n", encoding="utf-8")
        write_json(
            global_path,
            {
                "schema_version": "0.1",
                "registry_role": "global-local",
                "common_runtime_root": str(runtime_root),
                "goals": [
                    goal("orphan-a", orphan_repo, orphan_repo / ".loopx" / "registry.json"),
                    goal("orphan-b", orphan_repo, orphan_repo / ".loopx" / "other.json"),
                    goal("live-source", live_source_repo, live_source),
                    goal("live-state", live_state_repo, root / "missing-live-state-source.json"),
                ],
            },
        )
        before = global_path.read_text(encoding="utf-8")

        preview = run_json(runtime_root, "--goal-id", "orphan-a")
        assert preview["ok"] is True and preview["dry_run"] is True
        assert preview["planned_retired_goal_ids"] == ["orphan-a"]
        assert preview["retired_goal_ids"] == []
        assert preview["backup_written"] is False and preview["wrote"] is False
        assert global_path.read_text(encoding="utf-8") == before

        blocked_source = run_json(
            runtime_root,
            "--goal-id",
            "live-source",
            expect_success=False,
        )
        assert blocked_source["ok"] is False
        assert "live source_registry or state_file" in blocked_source["error"]

        blocked_state = run_json(
            runtime_root,
            "--goal-id",
            "live-state",
            expect_success=False,
        )
        assert blocked_state["ok"] is False
        assert "live source_registry or state_file" in blocked_state["error"]

        mixed_batch = run_json(
            runtime_root,
            "--goal-id",
            "orphan-a",
            "--goal-id",
            "live-source",
            "--execute",
            expect_success=False,
        )
        assert mixed_batch["ok"] is False
        assert global_path.read_text(encoding="utf-8") == before

        executed = run_json(
            runtime_root,
            "--goal-id",
            "orphan-a",
            "--goal-id",
            "orphan-b",
            "--execute",
        )
        assert executed["ok"] is True and executed["wrote"] is True
        assert executed["retired_goal_ids"] == ["orphan-a", "orphan-b"]
        backup_path = Path(str(executed["backup_path"]))
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == before
        remaining = json.loads(global_path.read_text(encoding="utf-8"))["goals"]
        assert [item["id"] for item in remaining] == ["live-source", "live-state"]

        missing = run_json(
            runtime_root,
            "--goal-id",
            "unknown-goal",
            expect_success=False,
        )
        assert missing["ok"] is False
        assert "goal_id not found" in missing["error"]

    print("global registry goal retirement smoke: ok")


if __name__ == "__main__":
    main()
