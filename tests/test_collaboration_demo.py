"""A fresh public demo must reach the real Turn admission without credentials."""

import json
from pathlib import Path
import subprocess
import sys


def test_demo_preparation_has_executable_independent_worktree(tmp_path):
    demo = (
        Path(__file__).resolve().parents[1] / "examples/collaboration-delivery/demo.py"
    )
    root = tmp_path / "demo"
    subprocess.run(
        [sys.executable, str(demo), "prepare", "--root", str(root)],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(root / "registry.json"),
            "--runtime-root",
            str(root / "runtime"),
            "--format",
            "json",
            "todo",
            "add",
            "--goal-id",
            "allocation-demo",
            "--role",
            "agent",
            "--claimed-by",
            "builder",
            "--text",
            "Implement the allocation planner",
            "--action-kind",
            "implement",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["ok"]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(root / "registry.json"),
            "--runtime-root",
            str(root / "runtime"),
            "--format",
            "json",
            "turn",
            "plan",
            "--goal-id",
            "allocation-demo",
            "--agent-id",
            "builder",
            "--host",
            "dsh",
            "--execution-mode",
            "isolated-headless",
            "--scan-root",
            str(root / "agents/builder"),
        ],
        cwd=root / "agents/builder",
        check=True,
        capture_output=True,
        text=True,
    )
    plan = json.loads(result.stdout)
    # The test supplies no provider credentials. Qualify the Goal/worktree
    # admission independently of provider availability and never invoke a host.
    assert plan["turn_envelope"]["execution_policy"]["normal_delivery_allowed"], plan[
        "turn_envelope"
    ]["reason"]
    assert not plan["effects"]["host_invoked"]
    # Preparation cannot overwrite an existing state; model runs need explicit opt-in.
    for args in (["prepare"], ["run", "--phase", "builder-1"]):
        result = subprocess.run(
            [sys.executable, str(demo), *args, "--root", str(root)], capture_output=True
        )
        assert result.returncode != 0
