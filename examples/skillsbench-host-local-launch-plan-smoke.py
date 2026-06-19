#!/usr/bin/env python3
"""Smoke-test the SkillsBench host-local ACP launch planning surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"


def main() -> int:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def _filter_kwargs_for_signature(" in source
    assert "getattr(\n        benchflow_rollout_module, \"connect_acp\", _MISSING" in source
    assert "if original_rollout_connect_acp is not _MISSING:" in source
    assert "_filter_kwargs_for_signature(RolloutConfig, rollout_config_kwargs)" in source
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-plan-") as tmp:
        root = Path(tmp) / "skillsbench"
        task = root / "tasks" / "demo-task" / "environment"
        task.mkdir(parents=True)
        (task / "Dockerfile").write_text("FROM ubuntu:22.04\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(root),
                "--task-id",
                "demo-task",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        plan = payload["launch_plan"]
        prerequisites = plan["runner_prerequisites"]
        assert plan["host_local_acp_launch"] is True
        assert plan["remote_command_file_bridge_ready"] is True
        assert prerequisites["agent_execution_mode"] == "host_local_acp"
        assert prerequisites["host_local_acp_launch"] is True
        assert prerequisites["host_local_acp_launch_status"] == "pending"
        assert prerequisites["remote_command_file_bridge_materialized"] is True
        assert prerequisites["container_codex_acp_install_skipped"] is False
        assert plan["public_boundary"]["leaderboard_upload"] is False
        assert plan["public_boundary"]["public_submission"] is False
    print("skillsbench host-local ACP launch plan smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
