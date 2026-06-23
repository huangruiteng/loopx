#!/usr/bin/env python3
"""Smoke-test the SkillsBench host-local ACP launch planning surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import builtins
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
    SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER,
    run_skillsbench_local_acp_relay_probe,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _apply_agent_message_only_no_tool_calls_attribution,
    _host_local_acp_docker_bridge_command,
    _host_local_acp_launch_command,
    _host_local_acp_target_env,
    _merge_host_local_acp_relay_trace_summary,
    _public_runner_prerequisites,
    _replace_option_value,
    _run_host_local_acp_codex_exec_preflight,
    build_runner_failure_compact,
    ensure_benchflow_runtime,
)

SCRIPT = REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"
RELAY_SCRIPT = REPO_ROOT / "scripts" / "skillsbench_local_acp_relay.py"
BRIDGE_SCRIPT = REPO_ROOT / "scripts" / "skillsbench_remote_command_file_bridge.py"
DOCKER_BRIDGE_SCRIPT = (
    REPO_ROOT / "scripts" / "skillsbench_docker_command_file_bridge.py"
)


def main() -> int:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def _filter_kwargs_for_signature(" in source
    assert "getattr(\n        benchflow_rollout_module, \"connect_acp\", _MISSING" in source
    assert "if original_rollout_connect_acp is not _MISSING:" in source
    assert "_filter_kwargs_for_signature(RolloutConfig, rollout_config_kwargs)" in source
    assert "env=target_env" in source
    assert "del (\n            env," not in source
    target_env = _host_local_acp_target_env(
        {
            "AI_ADDR": "127.0.0.1",
            "AI_PORT": 2022,
            "GOAL_HARNESS_REMOTE_BENCH_ROOT": "/tmp/bench",
            "SECRET_TOKEN": "must-not-forward",
        }
    )
    assert target_env == {
        "AI_ADDR": "127.0.0.1",
        "AI_PORT": "2022",
        "GOAL_HARNESS_REMOTE_BENCH_ROOT": "/tmp/bench",
    }
    replaced = _replace_option_value(
        ["relay", "--remote-command-file-bridge-command", "old", "--keep", "x"],
        "--remote-command-file-bridge-command",
        "new",
    )
    assert replaced == [
        "relay",
        "--remote-command-file-bridge-command",
        "new",
        "--keep",
        "x",
    ]
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-plan-") as tmp:
        root = Path(tmp) / "skillsbench"
        task = root / "tasks" / "demo-task" / "environment"
        task.mkdir(parents=True)
        (task / "Dockerfile").write_text("FROM ubuntu:22.04\n", encoding="utf-8")
        compose_file = Path(tmp) / "docker-compose.yaml"
        compose_file.write_text("services:\n  main:\n    image: ubuntu:22.04\n", encoding="utf-8")
        fake_env = SimpleNamespace(
            _docker_compose_paths=[compose_file],
            environment_dir=Path(tmp),
            session_id="Demo.Session",
        )
        docker_plan = {"jobs_dir": tmp, "job_name": "bridge-job", "runner_prerequisites": {}}
        docker_bridge_command = _host_local_acp_docker_bridge_command(
            fake_env,
            SimpleNamespace(loopx_source_dir=str(REPO_ROOT)),
            docker_plan,
        )
        assert docker_bridge_command is not None
        assert str(DOCKER_BRIDGE_SCRIPT) in docker_bridge_command
        assert "--project-name demo-session" in docker_bridge_command
        assert "--compose-file" in docker_bridge_command
        assert "SECRET_TOKEN" not in docker_bridge_command
        public_prerequisites = _public_runner_prerequisites(
            {
                **docker_plan["runner_prerequisites"],
                "host_local_acp_target_env_forwarded": True,
                "host_local_acp_target_env_key_count": 2,
                "host_local_acp_target_env_keys": [
                    "AI_ADDR",
                    "AI_PORT",
                    "SECRET_TOKEN",
                ],
            }
        )
        assert public_prerequisites["host_local_acp_sandbox_bridge_configured"] is True
        assert public_prerequisites["host_local_acp_sandbox_bridge_mode"] == "docker_compose"
        assert public_prerequisites["host_local_acp_sandbox_bridge_compose_file_count"] == 1
        assert public_prerequisites["host_local_acp_target_env_keys"] == [
            "AI_ADDR",
            "AI_PORT",
        ]
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "benchflow":
                raise ModuleNotFoundError(
                    "No module named 'benchflow'", name="benchflow"
                )
            return original_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            try:
                ensure_benchflow_runtime(
                    SimpleNamespace(
                        plan_only=False,
                        reduce_only=False,
                        skillsbench_root=str(root),
                    )
                )
            except RuntimeError as exc:
                assert "benchflow runtime unavailable" in str(exc)
                assert "skillsbench-root .venv/bin/python is missing" in str(exc)
            else:
                raise AssertionError("missing benchflow runtime should fail closed")
        finally:
            builtins.__import__ = original_import
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
        launch_command = _host_local_acp_launch_command(
            SimpleNamespace(
                app_server_acp_heartbeat_interval_sec=120.0,
                app_server_reasoning_effort="high",
                dataset="skillsbench-v1.1",
                host_local_acp_launch=True,
                local_acp_relay_command=None,
                local_codex_bin="codex",
                local_codex_exec_timeout_sec=7200,
                local_codex_sandbox="workspace-write",
                model=None,
                remote_command_file_bridge_probe=False,
                remote_command_file_bridge_probe_timeout_sec=5.0,
                remote_command_file_bridge_ready=False,
                remote_command_file_bridge_agent_command=None,
                remote_command_file_bridge_solver_command=None,
                route="loopx-product-mode",
                task_id="demo-task",
            ),
            {"host_local_acp_relay_trace_dir": str(Path(tmp) / "trace")},
        )
        heartbeat_index = launch_command.index("--stream-heartbeat-interval-sec")
        assert launch_command[heartbeat_index + 1] == "15.0"
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
        assert failure["remote_command_file_bridge_probe_command_configured"] is False
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
        blocked_probe_only = subprocess.run(
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
                f"{sys.executable} {BRIDGE_SCRIPT} --serve-probe",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert blocked_probe_only.returncode == 2, blocked_probe_only
        probe_only_failure = json.loads(blocked_probe_only.stderr)
        assert probe_only_failure["error_type"] == (
            "SkillsBenchReverseChannelBridgeNotSolverWired"
        ), probe_only_failure
        assert (
            probe_only_failure["remote_command_file_bridge_probe_command_configured"]
            is True
        )
        assert (
            probe_only_failure["remote_command_file_bridge_command_configured"]
            is False
        )
        blocked_fixture_solver = subprocess.run(
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
                "--remote-command-file-bridge-solver-command",
                f"{sys.executable} {BRIDGE_SCRIPT} --serve-probe",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert blocked_fixture_solver.returncode == 2, blocked_fixture_solver
        fixture_failure = json.loads(blocked_fixture_solver.stderr)
        assert fixture_failure["error_type"] == (
            "SkillsBenchReverseChannelBridgeFixtureOnlySolverCommand"
        ), fixture_failure
        bridge_command = f"{sys.executable} {BRIDGE_SCRIPT} --serve-probe"
        solver_bridge = Path(tmp) / "fake-solver-bridge"
        solver_bridge.write_text(
            f"""#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, {str(REPO_ROOT)!r})
from loopx.benchmark_adapters.skillsbench_remote_bridge import (
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION,
    build_skillsbench_remote_command_file_bridge_probe_response,
)

request = json.loads(sys.stdin.read() or "{{}}")
if request.get("schema_version") == SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION:
    print(json.dumps(build_skillsbench_remote_command_file_bridge_probe_response(
        ready=True,
        operations=[
            {{"kind": "exec", "label": "bounded_noop_command", "status": "ok", "exit_code_zero": True}},
            {{"kind": "write_file", "label": "probe_marker_write", "status": "ok"}},
            {{"kind": "read_file", "label": "probe_marker_read", "status": "ok", "content_match": True}},
            {{"kind": "cleanup", "label": "probe_marker_cleanup", "status": "ok"}},
        ],
    ), sort_keys=True))
else:
    print(json.dumps({{"ok": True, "operation": request.get("operation"), "stdout": "bridge-used\\n", "stderr": "", "exit_code": 0}}, sort_keys=True))
""",
            encoding="utf-8",
        )
        solver_bridge.chmod(0o755)
        solver_bridge_command = str(solver_bridge)
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
                "--remote-command-file-bridge-solver-command",
                solver_bridge_command,
                "--remote-command-file-bridge-agent-command",
                "python3 managed-local-agent-bridge.py",
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
                "remote_command_file_bridge_agent_command_configured"
            ]
            is True
        )
        assert (
            wired_prerequisites[
                "remote_command_file_bridge_agent_command_instrumented"
            ]
            is True
        )
        assert (
            wired_prerequisites[
                "remote_command_file_bridge_agent_operation_trace_required"
            ]
            is True
        )
        assert (
            wired_prerequisites[
                "remote_command_file_bridge_agent_operation_trace_satisfied"
            ]
            is False
        )
        assert (
            wired_prerequisites[
                "remote_command_file_bridge_agent_operation_trace_status"
            ]
            == "external_agent_command_relay_wrapped_pending_trace"
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
import json
import select
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
prompt = args[-1]
if "Private bridge command:" not in prompt:
    raise SystemExit(7)
if """ + repr(SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER) + """ not in prompt:
    raise SystemExit(11)
bridge_command = prompt.split("Private bridge command:", 1)[1].strip().splitlines()[0]
if not bridge_command:
    raise SystemExit(10)
ready, _, _ = select.select([sys.stdin], [], [], 0.2)
if not ready:
    raise SystemExit(8)
if sys.stdin.read():
    raise SystemExit(9)
for command in (
    "/app/.local/bin/loopx quota should-run --goal-id skillsbench-case --agent-id codex-benchmark-agent",
    "/app/.local/bin/loopx todo update --goal-id skillsbench-case --todo-id todo_seed --status open --note checkpoint",
):
    subprocess.run(
        [bridge_command],
        input=json.dumps({"operation": "exec", "cwd": "/app", "command": command}),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
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
                solver_bridge_command,
                "--remote-command-file-bridge-agent-command",
                solver_bridge_command,
                "--remote-command-file-bridge-timeout-sec",
                "5",
                "--loopx-workflow-lifecycle-checkpoint",
                "--loopx-case-goal-id",
                "skillsbench-case",
                "--loopx-case-agent-id",
                "codex-benchmark-agent",
                "--loopx-case-todo-id",
                "todo_seed",
            ],
            timeout_sec=20,
        )
        assert relay_probe["ready"] is True, relay_probe
        trace_files = sorted(trace_dir.glob("*.compact.json"))
        assert len(trace_files) >= 3, relay_probe
        traces = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in trace_files
        ]
        bridge_trace = next(
            trace
            for trace in traces
            if trace.get("trace_kind") == "remote_command_file_bridge_solver_consumption"
        )
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
        assert bridge["missing_operations"] == []
        assert bridge["failed_operations"] == []
        assert bridge["boundary_violations"] == []
        assert isinstance(bridge["operations"], list)
        assert bridge["operations"], bridge
        assert all("kind" in operation for operation in bridge["operations"])
        assert bridge["bridge_command_recorded"] is False
        boundary = bridge_trace["boundary"]
        assert boundary["raw_command_recorded"] is False
        assert boundary["raw_stdout_recorded"] is False
        assert boundary["raw_stderr_recorded"] is False
        assert boundary["raw_task_text_recorded"] is False
        assert boundary["host_paths_recorded"] is False
        assert boundary["remote_paths_recorded"] is False
        agent_ops_trace = next(
            trace
            for trace in traces
            if trace.get("trace_kind") == "remote_command_file_bridge_agent_operations"
        )
        agent_ops = agent_ops_trace["remote_command_file_bridge_agent_operations"]
        assert agent_ops["request_count"] == 2, agent_ops
        assert agent_ops["loopx_cli_call_count"] == 2, agent_ops
        assert agent_ops["loopx_state_read_count"] == 1, agent_ops
        assert agent_ops["loopx_state_write_count"] == 1, agent_ops
        assert agent_ops["raw_material_recorded"] is False, agent_ops
        driver_lifecycle_trace = next(
            trace
            for trace in traces
            if trace.get("trace_kind")
            == "remote_command_file_bridge_driver_lifecycle_checkpoint"
        )
        driver_lifecycle = driver_lifecycle_trace[
            "remote_command_file_bridge_driver_lifecycle_checkpoint"
        ]
        assert (
            driver_lifecycle["execution_style"]
            == "orchestrated_agentloop_loopx_cli"
        ), driver_lifecycle
        assert driver_lifecycle["checkpoint_count"] == 1, driver_lifecycle
        assert driver_lifecycle["request_count"] == 4, driver_lifecycle
        assert driver_lifecycle["failure_count"] == 0, driver_lifecycle
        assert driver_lifecycle["loopx_cli_call_count"] == 4, driver_lifecycle
        assert driver_lifecycle["loopx_state_read_count"] == 1, driver_lifecycle
        assert driver_lifecycle["loopx_state_write_count"] == 3, driver_lifecycle
        assert driver_lifecycle["raw_material_recorded"] is False, driver_lifecycle
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
            controller_trace[
                "remote_command_file_bridge_agent_operation_trace_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_agent_loopx_state_read_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_agent_loopx_state_write_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_driver_lifecycle_trace_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_driver_lifecycle_checkpoint_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count"
            ]
            == 3
        )
        assert (
            reducer_plan["runner_prerequisites"][
                "remote_command_file_bridge_consumption_status"
            ]
            == "solver_prompt_probe_ready"
        )
        bridge_failure_projection_dir = Path(tmp) / "bridge-failure-projection"
        bridge_failure_relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                route="loopx-product-mode",
                dataset="skillsbench-v1.1",
                task_id="demo-task",
                worker_public_trace_dir=str(bridge_failure_projection_dir),
            )
        )
        bridge_failure_relay._publish_remote_bridge_consumption_trace(
            {
                "ready": False,
                "first_blocker": (
                    "skillsbench_remote_command_file_bridge_operation_failed"
                ),
                "response_first_blocker": (
                    "skillsbench_remote_bridge_target_env_missing"
                ),
                "stage": "probe",
                "response_schema_version": (
                    "skillsbench_remote_command_file_bridge_probe_response_v0"
                ),
                "elapsed_ms": 1234,
                "operation_count": 4,
                "required_operations": [
                    "exec",
                    "write_file",
                    "read_file",
                    "cleanup",
                ],
                "missing_operations": [],
                "failed_operations": ["read_file"],
                "boundary_violations": [],
                "operations": [
                    {"kind": "exec", "label": "exec", "status": "ok"},
                    {
                        "kind": "read_file",
                        "label": "read_file",
                        "status": "failed",
                        "content_match": False,
                    },
                ],
                "bridge_command_invoked": True,
                "raw_command_recorded": False,
                "raw_stdout_recorded": False,
                "raw_stderr_recorded": False,
                "raw_task_text_recorded": False,
            }
        )
        bridge_failure_trace_path = next(
            bridge_failure_projection_dir.glob("*.compact.json")
        )
        bridge_failure_trace = json.loads(
            bridge_failure_trace_path.read_text(encoding="utf-8")
        )
        bridge_failure = bridge_failure_trace["remote_command_file_bridge"]
        assert bridge_failure["probe_ready"] is False
        assert (
            bridge_failure["response_first_blocker"]
            == "skillsbench_remote_bridge_target_env_missing"
        )
        assert bridge_failure["failed_operations"] == ["read_file"]
        assert bridge_failure["operations"][1]["status"] == "failed"
        assert bridge_failure["operations"][1]["content_match"] is False
        assert bridge_failure["bridge_command_recorded"] is False
        assert bridge_failure_trace["boundary"]["raw_stdout_recorded"] is False
        failing_codex = Path(tmp) / "failing-codex"
        failing_codex.write_text(
            """#!/usr/bin/env python3
import sys

print("hit your usage limit", file=sys.stderr)
raise SystemExit(42)
""",
            encoding="utf-8",
        )
        failing_codex.chmod(0o755)
        failure_trace_dir = Path(tmp) / "relay-failure-traces"
        failing_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(failing_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(failure_trace_dir),
            ],
            timeout_sec=20,
        )
        assert failing_probe["ready"] is False, failing_probe
        failure_trace_files = sorted(failure_trace_dir.glob("*.compact.json"))
        assert len(failure_trace_files) == 1, failure_trace_files
        failure_trace = json.loads(
            failure_trace_files[0].read_text(encoding="utf-8")
        )
        assert failure_trace["trace_kind"] == "codex_exec_process_failure"
        process = failure_trace["codex_exec_process"]
        assert process["failure_category"] == "codex_usage_limit"
        assert process["returncode"] == 42
        assert process["stderr_bytes"] > 0
        assert process["raw_stderr_recorded"] is False
        assert process["raw_task_text_recorded"] is False
        failure_controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0"
        }
        failure_reducer_plan = {
            "host_local_acp_relay_trace_dir": str(failure_trace_dir),
            "runner_prerequisites": {},
        }
        _merge_host_local_acp_relay_trace_summary(
            failure_reducer_plan,
            failure_controller_trace,
        )
        assert (
            failure_controller_trace[
                "host_local_acp_codex_exec_failure_trace_present"
            ]
            is True
        )
        assert (
            failure_controller_trace["host_local_acp_codex_exec_failure_category"]
            == "codex_usage_limit"
        )
        assert (
            failure_reducer_plan["runner_prerequisites"][
                "host_local_acp_codex_exec_failure_trace_count"
            ]
            == 1
        )
        reverse_failing_codex = Path(tmp) / "reverse-failing-codex"
        reverse_failing_codex.write_text(
            """#!/usr/bin/env python3
import sys

print("ConnectionRefusedError: [Errno 111] Connection refused", file=sys.stderr)
raise SystemExit(1)
""",
            encoding="utf-8",
        )
        reverse_failing_codex.chmod(0o755)
        reverse_failure_trace_dir = Path(tmp) / "reverse-failure-traces"
        reverse_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(reverse_failing_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--model",
                "gpt-5.5",
                "--worker-public-trace-dir",
                str(reverse_failure_trace_dir),
            ],
            timeout_sec=20,
        )
        assert reverse_probe["ready"] is False, reverse_probe
        reverse_failure = json.loads(
            next(reverse_failure_trace_dir.glob("*.compact.json")).read_text(
                encoding="utf-8"
            )
        )
        assert (
            reverse_failure["codex_exec_process"]["failure_category"]
            == "codex_reverse_channel_unavailable"
        ), reverse_failure
        preflight_plan = {
            "host_local_acp_relay_trace_dir": str(Path(tmp) / "preflight-traces"),
            "runner_prerequisites": {},
        }
        preflight_args = SimpleNamespace(
            dataset="skillsbench-v1.1",
            host_local_acp_codex_exec_preflight_timeout_sec=20,
            local_codex_bin=str(reverse_failing_codex),
            local_codex_sandbox="workspace-write",
            model="gpt-5.5",
            route="loopx-product-mode",
            task_id="demo-task",
        )
        try:
            _run_host_local_acp_codex_exec_preflight(preflight_args, preflight_plan)
        except RuntimeError as exc:
            assert "codex exec preflight failed" in str(exc)
        else:
            raise AssertionError("reverse-channel preflight should fail closed")
        preflight_prereqs = preflight_plan["runner_prerequisites"]
        assert (
            preflight_prereqs["host_local_acp_codex_exec_preflight_status"]
            == "failed"
        ), preflight_prereqs
        assert (
            preflight_prereqs["host_local_acp_codex_exec_failure_category"]
            == "codex_reverse_channel_unavailable"
        ), preflight_prereqs
        compact_failure = {
            "score_failure_attribution": (
                "skillsbench_host_local_acp_codex_exec_failed_codex_usage_limit"
            ),
            "interaction_counters": {
                "private_trajectory_event_count": 1,
                "private_trajectory_round_count": 1,
                "private_trajectory_tool_call_count": 0,
                "controller_action_decisions": 1,
            },
            "failure_attribution_labels": [],
        }
        assert _apply_agent_message_only_no_tool_calls_attribution(compact_failure)
        assert compact_failure["score_failure_attribution"] == (
            "skillsbench_host_local_acp_codex_exec_failed_codex_usage_limit"
        )
        assert compact_failure["first_blocker"] == (
            "skillsbench_host_local_acp_codex_exec_failed_codex_usage_limit"
        )
        assert "skillsbench_agent_behavior_gap" not in (
            compact_failure["failure_attribution_labels"]
        )
        interruption_compact = build_runner_failure_compact(
            SimpleNamespace(
                build_stall_timeout_sec=0,
                dataset="skillsbench-v1.1",
                model=None,
                route="loopx-product-mode",
                task_id="demo-task",
            ),
            {
                "compact_benchmark_run_json": str(
                    Path(tmp) / "interrupted-compact.json"
                ),
                "runner_prerequisites": {
                    "schema_version": "skillsbench_runner_prerequisites_v0",
                    "agent_execution_mode": "host_local_acp",
                },
            },
            KeyboardInterrupt(),
        )
        assert interruption_compact["score_failure_attribution"] == (
            "skillsbench_runner_interrupted_before_official_result"
        ), interruption_compact
        assert "skillsbench_compact_closeout_recorded" in (
            interruption_compact["failure_attribution_labels"]
        )
        interruption_prereqs = interruption_compact["runner_prerequisites"]
        assert interruption_prereqs["runner_interrupted_before_official_result"] is True
        assert interruption_prereqs["runner_interruption_kind"] == (
            "keyboard_interrupt"
        )
        assert (
            interruption_prereqs["runner_interruption_raw_material_recorded"]
            is False
        )
        assert interruption_compact["validation"]["runner_failure_compact_recorded"]
        assert interruption_compact["validation"]["no_raw_logs_read"]
        assert interruption_compact["validation"]["no_raw_task_text_read"]
        assert interruption_compact["validation"]["no_raw_trajectory_read"]
    print("skillsbench host-local ACP launch plan smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
