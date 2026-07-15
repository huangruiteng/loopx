#!/usr/bin/env python3
"""Smoke-test SkillsBench launcher gating for preinstalled agent runtime layers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import skillsbench_automation_loop as skillsbench_loop  # noqa: E402


def _fake_executable(path: Path, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env sh\necho {output!r}\n", encoding="utf-8")
    path.chmod(0o755)


def main() -> int:
    assert "/opt/benchflow/node/bin" in (
        skillsbench_loop.CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
    )
    assert "CODEX_ACP_RUNTIME_HOME=/opt/benchflow" in (
        skillsbench_loop.CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
    )
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-runtime-launch-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        task = skillsbench_root / "tasks" / "demo-task" / "environment"
        task.mkdir(parents=True)
        (task / "Dockerfile").write_text("FROM ubuntu:22.04\n", encoding="utf-8")

        runtime = root / "benchflow-agent-runtime"
        _fake_executable(runtime / "bin" / "node", "v22.20.0")
        _fake_executable(runtime / "bin" / "npm", "10.9.0")
        _fake_executable(runtime / "bin" / "codex-acp", "codex-acp 0.test")

        plan_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(skillsbench_root),
                "--task-id",
                "demo-task",
                "--route",
                "raw-codex-autonomous-max5",
                "--benchflow-agent-runtime-dir",
                str(runtime),
                "--require-preinstalled-benchflow-agent-runtime",
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert plan_proc.returncode == 0, plan_proc.stderr
        payload = json.loads(plan_proc.stdout)
        plan = payload["launch_plan"]
        layer = plan["benchflow_agent_runtime_layer"]
        prereq = plan["runner_prerequisites"]
        assert layer["ready"] is True, layer
        assert layer["source_path_recorded"] is False, layer
        assert str(runtime) not in json.dumps(layer, sort_keys=True), layer
        assert layer["mount_target"] == "/opt/benchflow", layer
        assert prereq["agent_execution_mode"] == (
            "container_codex_acp_preinstalled_runtime"
        ), prereq
        assert prereq["preinstalled_benchflow_agent_runtime_required"] is True
        assert prereq["benchflow_agent_runtime_layer_ready"] is True
        assert prereq["container_codex_acp_install_skipped"] is True
        assert prereq["benchflow_agent_install_skipped_by_runtime_layer"] is True
        assert prereq["codex_acp_runtime_dependency_setup_skipped"] is True
        assert prereq["benchflow_agent_runtime_mount_injected"] is False
        assert prereq["benchflow_agent_runtime_mount_read_only"] is True
        assert prereq["benchflow_agent_runtime_mount_source_recorded"] is False

        missing_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(skillsbench_root),
                "--task-id",
                "demo-task",
                "--route",
                "raw-codex-autonomous-max5",
                "--jobs-dir",
                str(root / "jobs"),
                "--benchflow-agent-runtime-dir",
                str(root / "missing-runtime"),
                "--require-preinstalled-benchflow-agent-runtime",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert missing_proc.returncode == 0, missing_proc.stderr
        missing_payload = json.loads(missing_proc.stderr)
        assert missing_payload["ok"] is False, missing_payload
        assert missing_payload["error_recorded"] is True, missing_payload
        compact_path = Path(missing_payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        attribution = compact["score_failure_attribution"]
        primary_label = (
            attribution.get("primary_label")
            if isinstance(attribution, dict)
            else attribution
        )
        assert (
            primary_label
            == "skillsbench_preinstalled_benchflow_agent_runtime_missing"
        ), compact
        compact_prereq = compact["runner_prerequisites"]
        assert compact_prereq["preinstalled_benchflow_agent_runtime_required"] is True
        assert compact_prereq["benchflow_agent_runtime_layer_ready"] is False
        assert compact_prereq["codex_acp_runtime_launch_preflight_status"] == "blocked"
        assert compact["runner_failure"]["raw_logs_read"] is False
        assert compact["runner_failure"]["raw_task_text_read"] is False

    print("skillsbench runtime-layer launch plan smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
