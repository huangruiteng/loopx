#!/usr/bin/env python3
"""Smoke-test the SkillsBench host-local ACP launch planning surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    run_skillsbench_local_acp_relay_probe,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _merge_host_local_acp_relay_trace_summary,
)

SCRIPT = REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"
RELAY_SCRIPT = REPO_ROOT / "scripts" / "skillsbench_local_acp_relay.py"
BRIDGE_SCRIPT = REPO_ROOT / "scripts" / "skillsbench_remote_command_file_bridge.py"


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
        assert prerequisites["remote_command_file_bridge_consumed_by_solver"] is False
        assert (
            prerequisites["remote_command_file_bridge_consumption_status"]
            == "probe_only_not_solver_wired"
        )
        assert prerequisites["container_codex_acp_install_skipped"] is False
        assert plan["public_boundary"]["leaderboard_upload"] is False
        assert plan["public_boundary"]["public_submission"] is False
        blocked = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(root),
                "--task-id",
                "demo-task",
                "--route",
                "loopx-product-mode",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert blocked.returncode == 2, blocked
        failure = json.loads(blocked.stderr)
        assert failure["error_type"] == (
            "SkillsBenchReverseChannelBridgeNotSolverWired"
        ), failure
        assert failure["remote_command_file_bridge_materialized"] is True
        assert failure["remote_command_file_bridge_consumed_by_solver"] is False
        assert failure["raw_logs_recorded"] is False
        assert failure["raw_task_text_read"] is False
        assert failure["remote_command_file_bridge_command_configured"] is False
        preflight = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(root),
                "--task-id",
                "demo-task",
                "--route",
                "loopx-product-mode",
                "--local-driver-worker-handshake-preflight",
                "--local-codex-cli-participant-ready",
                "--local-acp-relay-probe",
                "--host-local-acp-transport-probe",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-probe",
                "--remote-command-file-bridge-probe-command",
                f"{sys.executable} {REPO_ROOT / 'scripts' / 'skillsbench_remote_command_file_bridge.py'} --serve-probe",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert preflight.returncode == 0, preflight.stderr
        preflight_payload = json.loads(preflight.stdout)
        assert (
            preflight_payload.get("error_type")
            != "SkillsBenchReverseChannelBridgeNotSolverWired"
        ), preflight_payload
        assert (
            preflight_payload["local_driver_contract"][
                "remote_command_file_bridge_materialized"
            ]
            is True
        ), preflight_payload
        bridge_command = f"{sys.executable} {BRIDGE_SCRIPT} --serve-probe"
        wired_plan_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--skillsbench-root",
                str(root),
                "--task-id",
                "demo-task",
                "--route",
                "loopx-product-mode",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-probe",
                "--remote-command-file-bridge-probe-command",
                bridge_command,
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert wired_plan_proc.returncode == 0, wired_plan_proc.stderr
        wired_plan = json.loads(wired_plan_proc.stdout)["launch_plan"]
        wired_prerequisites = wired_plan["runner_prerequisites"]
        assert wired_plan["host_local_acp_relay_trace_dir"], wired_plan
        assert wired_prerequisites["remote_command_file_bridge_materialized"] is True
        assert (
            wired_prerequisites["remote_command_file_bridge_command_configured"]
            is True
        )
        assert (
            wired_prerequisites[
                "remote_command_file_bridge_solver_wiring_configured"
            ]
            is True
        )
        assert (
            wired_prerequisites["remote_command_file_bridge_consumption_status"]
            == "solver_wiring_configured_pending_prompt"
        )
        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import select
import sys
from pathlib import Path

args = sys.argv[1:]
if "Private bridge command:" not in args[-1]:
    raise SystemExit(7)
ready, _, _ = select.select([sys.stdin], [], [], 0.2)
if not ready:
    raise SystemExit(8)
if sys.stdin.read():
    raise SystemExit(9)
output = Path(args[args.index("--output-last-message") + 1])
output.write_text("fake solver saw bridge packet\\n", encoding="utf-8")
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        trace_dir = Path(tmp) / "relay-traces"
        relay_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(fake_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(trace_dir),
                "--remote-command-file-bridge-command",
                bridge_command,
                "--remote-command-file-bridge-timeout-sec",
                "5",
            ],
            timeout_sec=20,
        )
        assert relay_probe["ready"] is True, relay_probe
        trace_files = sorted(trace_dir.glob("*.compact.json"))
        assert trace_files, relay_probe
        bridge_trace = json.loads(trace_files[0].read_text(encoding="utf-8"))
        assert (
            bridge_trace["schema_version"]
            == "skillsbench_host_local_acp_relay_public_trace_v0"
        )
        assert bridge_trace["trace_kind"] == (
            "remote_command_file_bridge_solver_consumption"
        )
        assert bridge_trace["benchmark_id"] == "skillsbench-v1.1"
        assert bridge_trace["task_id"] == "demo-task"
        bridge = bridge_trace["remote_command_file_bridge"]
        assert bridge["consumed_by_solver"] is True
        assert bridge["probe_ready"] is True
        assert bridge["operation_count"] >= 4
        assert bridge["bridge_command_recorded"] is False
        boundary = bridge_trace["boundary"]
        assert boundary["raw_command_recorded"] is False
        assert boundary["raw_stdout_recorded"] is False
        assert boundary["raw_stderr_recorded"] is False
        assert boundary["raw_task_text_recorded"] is False
        assert boundary["host_paths_recorded"] is False
        assert boundary["remote_paths_recorded"] is False
        controller_trace = {"schema_version": "skillsbench_loopx_controller_trace_v0"}
        reducer_plan = {
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {
                "remote_command_file_bridge_solver_wiring_configured": True
            },
        }
        _merge_host_local_acp_relay_trace_summary(reducer_plan, controller_trace)
        assert (
            controller_trace["remote_command_file_bridge_consumed_by_solver"]
            is True
        )
        assert (
            controller_trace["remote_command_file_bridge_solver_public_trace_read"]
            is True
        )
        assert controller_trace["remote_command_file_bridge_solver_trace_count"] == 1
        assert (
            controller_trace["remote_command_file_bridge_solver_probe_ready_count"]
            == 1
        )
        assert (
            controller_trace["remote_command_file_bridge_solver_operation_count"]
            >= 4
        )
        assert (
            reducer_plan["runner_prerequisites"][
                "remote_command_file_bridge_consumption_status"
            ]
            == "solver_prompt_probe_ready"
        )
    print("skillsbench host-local ACP launch plan smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
