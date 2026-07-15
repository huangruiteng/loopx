from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from examples.control_plane.quota_plan_fixtures import write_cli_fixture


REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_runtime_paths_project_relative(
    *,
    registry_path: Path,
    runtime_root: Path,
    project: Path,
) -> Path:
    target_runtime = project / ".loopx" / "runtime"
    runtime_root.rename(target_runtime)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["common_runtime_root"] = ".loopx/runtime"
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for index_path in target_runtime.glob("goals/*/runs/index.jsonl"):
        rows = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            for field in ("json_path", "markdown_path"):
                raw_path = Path(str(row[field]))
                moved_path = target_runtime / raw_path.relative_to(runtime_root)
                row[field] = str(moved_path.relative_to(project))
            rows.append(json.dumps(row, ensure_ascii=False))
        index_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target_runtime


def _run_cli(*args: str, cwd: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(REPO_ROOT), env.get("PYTHONPATH", "")) if value
    )
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_history_and_quota_anchor_relative_runtime_to_registry_project(
    tmp_path: Path,
) -> None:
    registry_path, runtime_root, project = write_cli_fixture(tmp_path / "fixture")
    target_runtime = _make_runtime_paths_project_relative(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
    )
    independent_worktree = tmp_path / "independent-worktree"
    independent_worktree.mkdir()

    history = _run_cli(
        "--format",
        "json",
        "--registry",
        str(registry_path),
        "history",
        "--goal-id",
        "half-speed",
        "--limit",
        "1",
        cwd=independent_worktree,
    )

    assert Path(history["runtime_root"]) == target_runtime
    assert history["run_count"] == 1
    latest = history["goals"][0]["latest_status_run"]
    assert latest["json_exists"] is True
    assert latest["markdown_exists"] is True

    decision = _run_cli(
        "--format",
        "json",
        "--registry",
        str(registry_path),
        "quota",
        "should-run",
        "--goal-id",
        "half-speed",
        "--scan-path",
        str(project),
        cwd=independent_worktree,
    )

    assert decision["should_run"] is True
    assert decision["normal_delivery_allowed"] is True
    assert decision["decision"] == "run"
