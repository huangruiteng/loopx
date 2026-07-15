#!/usr/bin/env python3
"""Smoke-test the SkillsBench host-local ACP launch planning surface."""

from __future__ import annotations

import json
import io
import os
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
    SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER,
    SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER,
    _codex_exec_failure_category,
    run_skillsbench_local_acp_relay_probe,
)
from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    build_skillsbench_remote_command_file_bridge_probe_request,
)
from scripts.skillsbench_automation_loop import (  # noqa: E402
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC,
    HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC,
    _apply_agent_message_only_no_tool_calls_attribution,
    _effective_benchflow_agent_timeout_sec,
    _effective_local_codex_exec_timeout_sec,
    _host_local_acp_codex_exec_preflight_command,
    _host_local_acp_docker_bridge_command,
    _host_local_acp_launch_command,
    _host_local_proxy_endpoint_probe,
    _host_local_acp_target_env,
    _merge_app_server_goal_worker_trace_summary,
    _merge_host_local_acp_relay_trace_summary,
    _public_runner_config,
    _public_runner_prerequisites,
    _replace_option_value,
    _run_host_local_acp_codex_exec_preflight,
    _set_option_value,
    build_runner_failure_compact,
    ensure_benchflow_runtime,
)
from scripts.skillsbench_reverse_channel_bridge import (  # noqa: E402
    _run_codex_payload,
)
from scripts.skillsbench_docker_command_file_bridge import (  # noqa: E402
    _safe_path as _docker_bridge_safe_path,
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
    assert "from benchflow.agents.protocol import ACPSessionAdapter" in source
    assert ") -> tuple[Any, ...]:" in source
    assert "session_adapter = ACPSessionAdapter(client)" in source
    assert "return client, session, session_adapter, agent_name" in source
    assert "_filter_kwargs_for_signature(RolloutConfig, rollout_config_kwargs)" in source
    assert "env=target_env" in source
    assert "local_acp_command = _set_option_value(" in source
    assert "del (\n            env," not in source
    assert _docker_bridge_safe_path("/app/.codex/goals/state.json") == (
        "/app/.codex/goals/state.json"
    )
    assert _docker_bridge_safe_path("/tmp/loopx/probe.txt") == (
        "/tmp/loopx/probe.txt"
    )
    assert _docker_bridge_safe_path("/root/test.bib") == "/root/test.bib"
    assert _docker_bridge_safe_path("/root/answer.json") == "/root/answer.json"
    for blocked_path in ("/home/agent/answer.json", "relative/path", "/"):
        try:
            _docker_bridge_safe_path(blocked_path)
        except ValueError as exc:
            assert str(exc) in {"path_outside_allowed_roots", "path_invalid"}
        else:
            raise AssertionError(f"unexpected allowed path: {blocked_path}")
    for protected_root in ("/app", "/tmp", "/root"):
        try:
            _docker_bridge_safe_path(protected_root, allow_file=False)
        except ValueError as exc:
            assert str(exc) == "path_refuses_sandbox_root"
        else:
            raise AssertionError(f"unexpected cleanup root: {protected_root}")
    with tempfile.TemporaryDirectory(prefix="skillsbench-agent-probe-count-") as tmp:
        tmp_path = Path(tmp)
        observed_request = tmp_path / "observed-request.json"
        fake_bridge = tmp_path / "fake-bridge"
        fake_bridge.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "from pathlib import Path\n"
            f"raw = sys.stdin.read() or '{{}}'; json.loads(raw); Path({str(observed_request)!r}).write_text(raw, encoding='utf-8')\n"
            "print(json.dumps({'ok': True, 'stdout': '', 'stderr': '', 'exit_code': 0}))\n",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o755)
        packet = SkillsBenchLocalAcpRelay(
            CodexExecConfig(remote_command_file_bridge_command=str(fake_bridge))
        )._prompt_with_remote_bridge_packet(
            "Task",
            bridge_probe={"operation_count": 1},
            bridge_command_for_agent=str(fake_bridge),
        )
        first_action_block = packet.split("FIRST ACTION REQUIRED:", 1)[1].split(
            "Request examples:", 1
        )[0]
        assert "pwd && ls -la" in first_action_block
        assert str(fake_bridge) in first_action_block
        assert "<private bridge command>" not in first_action_block
        assert "```sh" in first_action_block
        first_action_command = first_action_block.split("```sh", 1)[1].split("```", 1)[0].strip()
        proc = subprocess.run(first_action_command, shell=True, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        request = json.loads(observed_request.read_text(encoding="utf-8"))
        assert request == {"operation": "exec", "cwd": "/app", "command": "pwd && ls -la", "timeout_sec": 10}, request
        assert '/root/task-input-or-data' in packet and '/root/answer.json' not in packet and 'Do not force relative paths into `/root` or `/app`' in packet, packet
        assert "`/app`, `/tmp`, and `/root`" in packet, packet
        trace_dir = tmp_path / "traces"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                remote_command_file_bridge_command=str(fake_bridge),
                worker_public_trace_dir=str(trace_dir),
            )
        )
        summary_path = tmp_path / "summary.jsonl"
        wrapper_path = relay._write_instrumented_bridge_wrapper(
            tmp_path=tmp_path,
            summary_path=summary_path,
            bridge_command=str(fake_bridge),
        )
        proc = subprocess.run(
            [str(wrapper_path)],
            input=json.dumps(build_skillsbench_remote_command_file_bridge_probe_request()),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        assert proc.returncode == 0, proc
        relay._publish_remote_bridge_agent_operations_trace(
            bridge_summary_path=summary_path
        )
        traces = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in trace_dir.glob("*.compact.json")
        ]
        agent_ops = [
            trace["remote_command_file_bridge_agent_operations"]
            for trace in traces
            if trace.get("trace_kind") == "remote_command_file_bridge_agent_operations"
        ]
        assert len(agent_ops) == 1, traces
        assert agent_ops[0]["probe_operation_count"] == 1, agent_ops
        assert agent_ops[0]["task_facing_operation_count"] == 0, agent_ops
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
    timeout_args = SimpleNamespace(
        agent_idle_timeout=7200,
        host_local_acp_launch=True,
        local_codex_exec_timeout_sec=21600,
        route="loopx-product-mode",
    )
    assert _effective_local_codex_exec_timeout_sec(timeout_args) == 21600
    assert _effective_benchflow_agent_timeout_sec(timeout_args) == (
        21600 + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
    )
    default_host_local_timeout_args = SimpleNamespace(
        agent_idle_timeout=900,
        host_local_acp_launch=True,
        local_codex_bridge_idle_timeout_sec=None,
        local_codex_exec_timeout_sec=None,
        route="loopx-product-mode",
    )
    assert _effective_local_codex_exec_timeout_sec(
        default_host_local_timeout_args
    ) == (
        DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
        + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
    )
    non_host_local_timeout_args = SimpleNamespace(
        agent_idle_timeout=7200,
        host_local_acp_launch=False,
        local_codex_exec_timeout_sec=21600,
        route="loopx-product-mode",
    )
    assert _effective_benchflow_agent_timeout_sec(non_host_local_timeout_args) == 7200
    app_server_goal_timeout_args = SimpleNamespace(
        agent_idle_timeout=900,
        host_local_acp_launch=True,
        local_codex_bridge_idle_timeout_sec=None,
        local_codex_exec_timeout_sec=None,
        outer_timeout_sec=3600,
        route="codex-app-server-goal-baseline",
    )
    assert _effective_local_codex_exec_timeout_sec(app_server_goal_timeout_args) == (
        DEFAULT_TIMEOUT_SEC
    )
    assert _effective_benchflow_agent_timeout_sec(app_server_goal_timeout_args) == (
        DEFAULT_TIMEOUT_SEC + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
    )
    app_server_goal_outer_timeout_args = SimpleNamespace(
        agent_idle_timeout=900,
        host_local_acp_launch=True,
        local_codex_bridge_idle_timeout_sec=None,
        local_codex_exec_timeout_sec=None,
        outer_timeout_sec=21600,
        route="codex-app-server-goal-baseline",
    )
    assert _effective_local_codex_exec_timeout_sec(
        app_server_goal_outer_timeout_args
    ) == 21600
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
    appended = _set_option_value(
        ["relay", "--keep", "x"],
        "--remote-command-file-bridge-command",
        "generated",
    )
    assert appended == [
        "relay",
        "--keep",
        "x",
        "--remote-command-file-bridge-command",
        "generated",
    ]
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-plan-") as tmp:
        fake_bridge = Path(tmp) / "fake-json-bridge"
        fake_bridge.write_text(
            """#!/usr/bin/env python3
import json
import sys

request = json.loads(sys.stdin.read() or "{}")
print(json.dumps({"ok": True, "operation": request.get("operation"), "exit_code": 0}))
""",
            encoding="utf-8",
        )
        fake_bridge.chmod(0o755)
        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

args = sys.argv[1:]
out = ""
for index, token in enumerate(args[:-1]):
    if token == "--output-last-message":
        out = args[index + 1]
prompt = sys.stdin.read()
if any("Private bridge command:" in item for item in args):
    raise SystemExit(42)
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "/app/.local/bin/loopx --format json quota should-run --goal-id skillsbench-case --agent-id codex-benchmark-agent",
    }),
    text=True,
    shell=True,
    check=True,
)
if out:
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("done")
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        reverse_payload = _run_codex_payload(
            {
                "args": [
                    "exec",
                    "--output-last-message",
                    str(Path(tmp) / "remote-last-message.txt"),
                    "--json",
                    "Private bridge command:\nremote-wrapper-that-must-be-replaced",
                ],
                "timeout_sec": 20,
            },
            codex_bin=str(fake_codex),
            default_timeout_sec=20,
            prompt_bridge_command=str(fake_bridge),
        )
        assert reverse_payload["exit_code"] == 0, reverse_payload
        operation_lines = [
            json.loads(line)
            for line in str(reverse_payload["agent_operations_jsonl"]).splitlines()
            if line.strip()
        ]
        assert len(operation_lines) == 2, reverse_payload
        operation_record = operation_lines[0]
        assert operation_record["operation"] == "exec", operation_record
        assert operation_record["record_phase"] == "start", operation_record
        assert operation_record["loopx_cli_call"] is True, operation_record
        assert operation_record["loopx_state_read"] is True, operation_record
        assert operation_record["task_facing_operation"] is False, operation_record
        assert operation_record["raw_request_recorded"] is False, operation_record
        complete_record = operation_lines[1]
        assert complete_record["record_phase"] == "complete", complete_record
        assert complete_record["returncode"] == 0, complete_record
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
            == "sandbox_bridge_auto_wiring_pending"
        )
        assert prerequisites["container_codex_acp_install_skipped"] is True
        assert plan["public_boundary"]["leaderboard_upload"] is False
        assert plan["public_boundary"]["public_submission"] is False
        app_trace_dir = Path(tmp) / "app-server-goal-trace"
        app_trace_dir.mkdir()
        (app_trace_dir / "turn.compact.json").write_text(
            json.dumps(
                {
                    "schema_version": (
                        "skillsbench_host_codex_goal_worker_public_trace_v0"
                    ),
                    "trace_kind": "turn",
                    "ok": True,
                    "turn": {
                        "reasoning_effort": "xhigh",
                        "goal_get_present": True,
                        "turn_id_present": True,
                        "turn_completed_observed": True,
                        "assistant_message_present": True,
                        "first_action_observed": True,
                        "effective_action_observed": True,
                    },
                    "worker_adapter": {"reasoning_effort": "xhigh"},
                    "boundary": {
                        "raw_task_text_recorded": False,
                        "raw_logs_recorded": False,
                        "raw_trajectory_recorded": False,
                        "credential_values_recorded": False,
                        "host_paths_recorded": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        app_server_plan = {
            "route": "codex-app-server-goal-baseline",
            "app_server_reasoning_effort": "xhigh",
            "app_server_goal_worker_trace_dir": str(app_trace_dir),
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_api_egress_preflight_required": True,
                "codex_api_egress_preflight_ready": True,
                "codex_api_egress_preflight_status": "ready",
                "codex_api_egress_mode_resolved": "reverse-tunnel",
                "codex_api_reverse_tunnel_required": True,
                "codex_api_reverse_tunnel_proxy_configured": True,
                "codex_api_reverse_tunnel_proxy_source": "env",
                "codex_api_reverse_tunnel_proxy_scheme": "http",
                "codex_api_reverse_tunnel_proxy_endpoint_kind": "ipv4",
                "codex_api_reverse_tunnel_proxy_endpoint_port": 3128,
                "codex_api_reverse_tunnel_proxy_url_recorded": False,
            },
        }
        app_controller_trace: dict[str, object] = {}
        _merge_app_server_goal_worker_trace_summary(
            app_server_plan,
            app_controller_trace,
        )
        app_server_config = _public_runner_config(app_server_plan)
        app_server_observability = app_server_config[
            "app_server_goal_worker_observability"
        ]
        assert app_server_observability["requested_reasoning_effort"] == "xhigh"
        assert app_server_observability["observed_reasoning_effort"] == "xhigh"
        assert app_server_observability["reasoning_effort_matches_request"] is True
        assert app_server_observability["public_trace_read"] is True
        assert app_server_observability["raw_material_recorded"] is False
        assert (
            app_server_observability[
                "codex_api_egress_preflight_observation_status"
            ]
            == "executed_ready"
        )
        assert app_server_observability[
            "codex_api_reverse_tunnel_proxy_url_recorded"
        ] is False
        app_failure_trace = Path(tmp) / "app-server-controller-trace.json"
        app_failure_trace.write_text("{}", encoding="utf-8")
        app_failure_compact = build_runner_failure_compact(
            SimpleNamespace(
                build_stall_timeout_sec=0,
                dataset="skillsbench-v1.1",
                model=None,
                run_group_id=None,
                route="codex-app-server-goal-baseline",
                task_id="demo-task",
            ),
            {
                "app_server_goal_worker_trace_dir": str(app_trace_dir),
                "app_server_reasoning_effort": "xhigh",
                "compact_benchmark_run_json": str(
                    Path(tmp) / "app-server-failure-compact.json"
                ),
                "controller_trace_json": str(app_failure_trace),
                "route": "codex-app-server-goal-baseline",
                "runner_prerequisites": dict(
                    app_server_plan["runner_prerequisites"]
                ),
            },
            RuntimeError("app-server worker failed before result"),
        )
        assert app_failure_compact["runner_config"][
            "app_server_goal_worker_observability"
        ]["observed_reasoning_effort"] == "xhigh"
        assert app_failure_compact["app_server_goal_worker_observability"][
            "reasoning_effort_matches_request"
        ] is True
        launch_args = SimpleNamespace(
            agent_idle_timeout=7200,
            app_server_acp_heartbeat_interval_sec=120.0,
            app_server_reasoning_effort="high",
            dataset="skillsbench-v1.1",
            host_local_acp_launch=True,
            local_acp_relay_command=None,
            local_codex_bin="codex",
            local_codex_bridge_idle_timeout_sec=None,
            local_codex_exec_timeout_sec=None,
            local_codex_sandbox="workspace-write",
            max_rounds=24,
            model=None,
            remote_command_file_bridge_probe=False,
            remote_command_file_bridge_probe_timeout_sec=5.0,
            remote_command_file_bridge_ready=False,
            remote_command_file_bridge_agent_command=None,
            remote_command_file_bridge_solver_command=None,
            route="loopx-product-mode",
            sandbox="docker",
            task_id="demo-task",
        )
        launch_plan = {"host_local_acp_relay_trace_dir": str(Path(tmp) / "trace")}
        launch_command = _host_local_acp_launch_command(launch_args, launch_plan)
        timeout_index = launch_command.index("--timeout-sec")
        assert launch_command[timeout_index + 1] == str(
            DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
            + HOST_LOCAL_ACP_AGENT_TIMEOUT_MARGIN_SEC
        )
        heartbeat_index = launch_command.index("--stream-heartbeat-interval-sec")
        assert launch_command[heartbeat_index + 1] == "15.0"
        bridge_idle_index = launch_command.index("--bridge-idle-timeout-sec")
        assert launch_command[bridge_idle_index + 1] == str(
            DEFAULT_HOST_LOCAL_CODEX_BRIDGE_IDLE_TIMEOUT_SEC
        )
        launch_args.local_codex_bridge_idle_timeout_sec = 0
        bridge_idle_disabled_command = _host_local_acp_launch_command(
            launch_args,
            launch_plan,
        )
        bridge_idle_disabled_index = bridge_idle_disabled_command.index(
            "--bridge-idle-timeout-sec"
        )
        assert bridge_idle_disabled_command[bridge_idle_disabled_index + 1] == "0"
        launch_args.local_codex_bridge_idle_timeout_sec = 1800
        bridge_idle_explicit_command = _host_local_acp_launch_command(
            launch_args,
            launch_plan,
        )
        bridge_idle_explicit_index = bridge_idle_explicit_command.index(
            "--bridge-idle-timeout-sec"
        )
        assert bridge_idle_explicit_command[bridge_idle_explicit_index + 1] == "1800"
        explicit_preflight_command = _host_local_acp_codex_exec_preflight_command(
            SimpleNamespace(
                dataset="skillsbench-v1.1",
                host_local_acp_codex_exec_preflight_timeout_sec=20,
                local_acp_relay_command=(
                    f"{sys.executable} /tmp/loopx-remote-codex-client.py"
                ),
                local_codex_bin="/unused/when-explicit-client-is-configured",
                local_codex_sandbox="workspace-write",
                model="gpt-5.5",
                reasoning_effort="xhigh",
                route="loopx-product-mode",
                task_id="demo-task",
            ),
            {"host_local_acp_relay_trace_dir": str(Path(tmp) / "trace")},
        )
        assert explicit_preflight_command[:2] == [
            sys.executable,
            "/tmp/loopx-remote-codex-client.py",
        ], explicit_preflight_command
        assert explicit_preflight_command.count("--codex-bin") == 1
        assert (
            explicit_preflight_command[
                explicit_preflight_command.index("--codex-bin") + 1
            ]
            == "/unused/when-explicit-client-is-configured"
        )
        assert "--reasoning-effort" in explicit_preflight_command
        assert (
            explicit_preflight_command[
                explicit_preflight_command.index("--reasoning-effort") + 1
            ]
            == "xhigh"
        )
        bridge_preflight_command = _host_local_acp_codex_exec_preflight_command(
            SimpleNamespace(
                dataset="skillsbench-v1.1",
                host_local_acp_codex_exec_preflight_timeout_sec=120,
                host_local_acp_launch=True,
                local_acp_relay_command=(
                    f"{sys.executable} /tmp/loopx-remote-codex-client.py"
                ),
                local_codex_bin="/unused/when-explicit-client-is-configured",
                local_codex_first_action_timeout_sec=1800,
                local_codex_sandbox="workspace-write",
                model=None,
                remote_command_file_bridge_agent_command="/tmp/local-agent-bridge",
                remote_command_file_bridge_probe=False,
                remote_command_file_bridge_probe_timeout_sec=5.0,
                remote_command_file_bridge_ready=True,
                remote_command_file_bridge_solver_command="/tmp/remote-solver-bridge",
                reasoning_effort="xhigh",
                route="loopx-product-mode",
                task_id="demo-task",
            ),
            {"host_local_acp_relay_trace_dir": str(Path(tmp) / "trace")},
        )
        assert "--remote-command-file-bridge-command" in bridge_preflight_command
        assert "--remote-command-file-bridge-agent-command" in bridge_preflight_command
        first_action_index = bridge_preflight_command.index(
            "--first-action-timeout-sec"
        )
        assert bridge_preflight_command[first_action_index + 1] == "90"
        auto_wiring_plan_proc = subprocess.run(
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
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert auto_wiring_plan_proc.returncode == 0, auto_wiring_plan_proc.stderr
        auto_wiring_plan = json.loads(auto_wiring_plan_proc.stdout)["launch_plan"]
        auto_wiring_prerequisites = auto_wiring_plan["runner_prerequisites"]
        assert (
            auto_wiring_prerequisites["remote_command_file_bridge_materialized"]
            is True
        )
        assert (
            auto_wiring_prerequisites["remote_command_file_bridge_command_configured"]
            is False
        )
        assert (
            auto_wiring_prerequisites[
                "remote_command_file_bridge_agent_operation_trace_required"
            ]
            is True
        )
        assert (
            auto_wiring_prerequisites["remote_command_file_bridge_consumption_status"]
            == "sandbox_bridge_auto_wiring_pending"
        )
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
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        assert blocked_probe_only.returncode == 0, blocked_probe_only.stderr
        probe_only_plan = json.loads(blocked_probe_only.stdout)["launch_plan"]
        probe_only_failure = probe_only_plan["runner_prerequisites"]
        assert (
            probe_only_failure["remote_command_file_bridge_probe_command_configured"]
            is True
        )
        assert (
            probe_only_failure["remote_command_file_bridge_command_configured"]
            is False
        )
        assert (
            probe_only_failure["remote_command_file_bridge_consumption_status"]
            == "sandbox_bridge_auto_wiring_pending"
        )
        for route in ("loopx-product-mode", "loopx-goal-start-product-mode"):
            auto_wiring_runtime_plan = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--skillsbench-root",
                    str(root),
                    "--task-id",
                    "demo-task",
                    "--route",
                    route,
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
            assert auto_wiring_runtime_plan.returncode == 0, (
                auto_wiring_runtime_plan.stderr
            )
            auto_wiring_prereqs = json.loads(auto_wiring_runtime_plan.stdout)[
                "launch_plan"
            ]["runner_prerequisites"]
            assert (
                auto_wiring_prereqs["remote_command_file_bridge_consumption_status"],
                auto_wiring_prereqs["container_codex_acp_install_skipped"],
            ) == ("sandbox_bridge_auto_wiring_pending", True), auto_wiring_prereqs
            source = SCRIPT.read_text(encoding="utf-8")
            assert "_host_local_acp_docker_bridge_command(" in source
            assert 'prerequisites["remote_command_file_bridge_command_configured"] = True' in source
            assert (
                'prerequisites["remote_command_file_bridge_solver_wiring_configured"] = True'
                in source
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
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()
if any("Private bridge command:" in item for item in args):
    raise SystemExit(42)
if "Private bridge command:" not in prompt:
    raise SystemExit(7)
if """ + repr(SKILLSBENCH_LOCAL_ACP_RELAY_READY_MARKER) + """ not in prompt:
    raise SystemExit(11)
bridge_command = prompt.split("Private bridge command:", 1)[1].strip().splitlines()[0]
if not bridge_command:
    raise SystemExit(10)
if "FIRST ACTION REQUIRED:" in prompt:
    copyable_packet = prompt.split("FIRST ACTION REQUIRED:", 1)[1].split("Request examples:", 1)[0]
    if "<private bridge command>" in copyable_packet:
        raise SystemExit(12)
    if "pwd && ls -la" not in copyable_packet:
        raise SystemExit(13)
    if bridge_command not in copyable_packet:
        raise SystemExit(14)
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
        assert agent_ops["success_count"] == 2, agent_ops
        assert agent_ops["failure_count"] == 0, agent_ops
        assert agent_ops["loopx_cli_call_count"] == 2, agent_ops
        assert agent_ops["loopx_state_read_count"] == 1, agent_ops
        assert agent_ops["loopx_state_write_count"] == 1, agent_ops
        assert agent_ops["successful_loopx_cli_subcommand_counts"] == {
            "quota should-run": 1,
            "todo update": 1,
        }, agent_ops
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
                "remote_command_file_bridge_agent_todo_closeout_count"
            ]
            == 1
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_agent_refresh_state_count"
            ]
            == 0
        )
        assert (
            controller_trace[
                "remote_command_file_bridge_agent_quota_spend_slot_count"
            ]
            == 0
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
        exit125_codex = Path(tmp) / "exit125-codex"
        exit125_codex.write_text(
            """#!/usr/bin/env python3
import sys

print("generic host wrapper failure", file=sys.stderr)
raise SystemExit(125)
""",
            encoding="utf-8",
        )
        exit125_codex.chmod(0o755)
        exit125_trace_dir = Path(tmp) / "relay-exit125-traces"
        exit125_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(exit125_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(exit125_trace_dir),
            ],
            timeout_sec=20,
        )
        assert exit125_probe["ready"] is False, exit125_probe
        exit125_failure = json.loads(
            next(exit125_trace_dir.glob("*.compact.json")).read_text(
                encoding="utf-8"
            )
        )
        exit125_process = exit125_failure["codex_exec_process"]
        assert exit125_process["failure_category"] == "codex_exec_exit_125"
        assert exit125_process["returncode"] == 125
        assert exit125_process["raw_stderr_recorded"] is False
        exit125_controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0"
        }
        exit125_reducer_plan = {
            "host_local_acp_relay_trace_dir": str(exit125_trace_dir),
            "runner_prerequisites": {},
        }
        _merge_host_local_acp_relay_trace_summary(
            exit125_reducer_plan,
            exit125_controller_trace,
        )
        assert (
            exit125_controller_trace["host_local_acp_codex_exec_failure_category"]
            == "codex_exec_exit_125"
        )
        agent_bridge_failure_trace_dir = Path(tmp) / "agent-bridge-failure-traces"
        agent_bridge_failure_trace_dir.mkdir(parents=True)
        (agent_bridge_failure_trace_dir / "worker-agent-failure.compact.json").write_text(
            json.dumps(
                {
                    "schema_version": (
                        "skillsbench_host_local_acp_relay_public_trace_v0"
                    ),
                    "ok": True,
                    "route": "loopx-goal-start-product-mode",
                    "trace_kind": "remote_command_file_bridge_agent_operations",
                    "remote_command_file_bridge_agent_operations": {
                        "schema_version": (
                            "skillsbench_remote_command_file_bridge_agent_operations_v0"
                        ),
                        "request_count": 1,
                        "success_count": 0,
                        "failure_count": 1,
                        "task_facing_operation_count": 1,
                        "task_facing_success_count": 0,
                        "task_facing_failure_count": 1,
                        "failure_category_counts": {
                            "bridge_client_permission_error": 1
                        },
                        "raw_material_recorded": False,
                    },
                    "boundary": {
                        "raw_command_recorded": False,
                        "raw_stdout_recorded": False,
                        "raw_stderr_recorded": False,
                        "raw_task_text_recorded": False,
                        "credential_values_recorded": False,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        agent_bridge_failure_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0"
        }
        agent_bridge_failure_plan = {
            "host_local_acp_relay_trace_dir": str(agent_bridge_failure_trace_dir),
            "runner_prerequisites": {},
        }
        _merge_host_local_acp_relay_trace_summary(
            agent_bridge_failure_plan,
            agent_bridge_failure_trace,
        )
        assert agent_bridge_failure_trace[
            "host_local_acp_codex_exec_failure_category"
        ] == "bridge_client_permission_error", agent_bridge_failure_trace
        assert agent_bridge_failure_plan["runner_prerequisites"][
            "host_local_acp_codex_exec_failure_category"
        ] == "bridge_client_permission_error"
        network_exit125_codex = Path(tmp) / "network-exit125-codex"
        network_exit125_codex.write_text(
            """#!/usr/bin/env python3
import sys

print(
    "failed to refresh available models: stream disconnected before completion",
    file=sys.stderr,
)
raise SystemExit(125)
""",
            encoding="utf-8",
        )
        network_exit125_codex.chmod(0o755)
        network_exit125_trace_dir = Path(tmp) / "relay-network-exit125-traces"
        network_exit125_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(network_exit125_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(network_exit125_trace_dir),
            ],
            timeout_sec=20,
        )
        assert network_exit125_probe["ready"] is False, network_exit125_probe
        network_exit125_failure = json.loads(
            next(network_exit125_trace_dir.glob("*.compact.json")).read_text(
                encoding="utf-8"
            )
        )
        network_exit125_process = network_exit125_failure["codex_exec_process"]
        assert network_exit125_process["returncode"] == 125
        assert network_exit125_process["failure_category"] == (
            "codex_network_or_api_unreachable"
        )
        assert network_exit125_process["raw_stderr_recorded"] is False
        exit1_codex = Path(tmp) / "exit1-codex"
        exit1_codex.write_text(
            """#!/usr/bin/env python3
import sys

print("opaque command failure", file=sys.stderr)
raise SystemExit(1)
""",
            encoding="utf-8",
        )
        exit1_codex.chmod(0o755)
        exit1_trace_dir = Path(tmp) / "relay-exit1-traces"
        exit1_probe = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(RELAY_SCRIPT),
                "--codex-bin",
                str(exit1_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(exit1_trace_dir),
            ],
            timeout_sec=20,
        )
        assert exit1_probe["ready"] is False, exit1_probe
        exit1_failure = json.loads(
            next(exit1_trace_dir.glob("*.compact.json")).read_text(
                encoding="utf-8"
            )
        )
        exit1_process = exit1_failure["codex_exec_process"]
        assert exit1_process["failure_category"] == "codex_exec_exit_1"
        assert exit1_process["returncode"] == 1
        assert exit1_process["raw_stderr_recorded"] is False
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
        assert (
            _codex_exec_failure_category(
                returncode=1,
                stderr_text=(
                    "failed to connect to websocket: IO error: Connection refused "
                    "(os error 111), url: "
                    "wss://chatgpt.com/backend-api/codex/responses"
                ),
            )
            == "codex_responses_stream_unavailable"
        )
        assert (
            _codex_exec_failure_category(
                returncode=1,
                stderr_text=(
                    "{\"type\":\"error\",\"status\":400,\"error\":{\"message\":"
                    "\"The 'gpt-5' model is not supported when using Codex "
                    "with a ChatGPT account.\"}}"
                ),
            )
            == "codex_model_unavailable"
        )

        saved_proxy_env = {
            key: os.environ.get(key)
            for key in (
                "HTTPS_PROXY",
                "https_proxy",
                "ALL_PROXY",
                "all_proxy",
                "HTTP_PROXY",
                "http_proxy",
            )
        }
        try:
            for key in saved_proxy_env:
                os.environ.pop(key, None)
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
            proxy_probe = _host_local_proxy_endpoint_probe()
            assert proxy_probe["status"] == "unreachable", proxy_probe
            assert proxy_probe["raw_proxy_url_recorded"] is False, proxy_probe
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:not-a-port"
            invalid_proxy_probe = _host_local_proxy_endpoint_probe()
            assert (
                invalid_proxy_probe["status"] == "invalid_loopback_proxy_port"
            ), invalid_proxy_probe
            assert (
                invalid_proxy_probe["raw_proxy_url_recorded"] is False
            ), invalid_proxy_probe
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"

            preflight_plan = {"runner_prerequisites": {}}
            proxy_blocked_args = SimpleNamespace(
                route="loopx-product-mode",
                dataset="skillsbench-v1.1",
                task_id="demo-task",
                local_acp_relay_command=None,
                local_codex_bin=str(Path(tmp) / "not-run-codex"),
                local_codex_sandbox="read-only",
                host_local_acp_launch=True,
                host_local_acp_codex_exec_preflight_timeout_sec=5,
                host_local_acp_codex_exec_preflight_attempts=1,
                model="gpt-5.5",
                remote_command_file_bridge_solver_command="",
                remote_command_file_bridge_ready=False,
                remote_command_file_bridge_probe=False,
                remote_command_file_bridge_probe_timeout_sec=10,
                remote_command_file_bridge_agent_command="",
                local_codex_first_action_timeout_sec=0,
            )
            try:
                _run_host_local_acp_codex_exec_preflight(
                    proxy_blocked_args,
                    preflight_plan,
                )
            except RuntimeError as exc:
                assert "proxy endpoint" in str(exc), exc
            else:
                raise AssertionError("proxy endpoint failure should block preflight")
            proxy_prereqs = preflight_plan["runner_prerequisites"]
            assert (
                proxy_prereqs["host_local_acp_codex_exec_preflight_first_blocker"]
                == "skillsbench_host_local_acp_proxy_endpoint_unreachable"
            ), proxy_prereqs
            assert (
                proxy_prereqs["host_local_acp_codex_exec_failure_category"]
                == "codex_proxy_endpoint_unreachable"
            ), proxy_prereqs
            assert (
                proxy_prereqs["host_local_acp_proxy_endpoint_raw_url_recorded"]
                is False
            ), proxy_prereqs
        finally:
            for key, value in saved_proxy_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        reverse_sleeping_codex = Path(tmp) / "reverse-sleeping-codex"
        reverse_sleeping_codex.write_text(
            """#!/usr/bin/env python3
import time

time.sleep(5)
""",
            encoding="utf-8",
        )
        reverse_sleeping_codex.chmod(0o755)
        reverse_timeout = _run_codex_payload(
            {
                "args": [
                    "exec",
                    (
                        "LoopX bridge test. Your first tool action should be "
                        "a shell pipeline that sends JSON to the private bridge.\n\n"
                        "Private bridge command:\n"
                        "/tmp/not-recorded"
                    ),
                ],
                "timeout_sec": 30,
            },
            codex_bin=str(reverse_sleeping_codex),
            default_timeout_sec=30,
            prompt_bridge_command="true",
            first_action_timeout_sec=1,
        )
        assert reverse_timeout["exit_code"] == 124, reverse_timeout
        assert "codex_exec_first_action_timeout" in reverse_timeout["stderr"]
        assert reverse_timeout["agent_operations_jsonl"] == ""
        assert reverse_timeout["agent_operations_raw_material_recorded"] is False
        assert reverse_timeout["raw_task_text_recorded"] is False
        reverse_hanging_bridge = Path(tmp) / "reverse-hanging-bridge"
        reverse_hanging_bridge.write_text(
            """#!/usr/bin/env python3
import sys
import time

sys.stdin.read()
time.sleep(30)
""",
            encoding="utf-8",
        )
        reverse_hanging_bridge.chmod(0o755)
        reverse_hanging_codex = Path(tmp) / "reverse-hanging-codex"
        reverse_hanging_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

prompt = sys.stdin.read()
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "python - <<'PY'\\nprint('task-facing')\\nPY",
        "timeout_sec": 10,
    }),
    text=True,
    shell=True,
    check=False,
)
""",
            encoding="utf-8",
        )
        reverse_hanging_codex.chmod(0o755)
        reverse_hanging_timeout = _run_codex_payload(
            {
                "args": [
                    "exec",
                    (
                        "LoopX bridge test. Your first tool action should be "
                        "a shell pipeline that sends JSON to the private bridge.\n\n"
                        "Private bridge command:\n"
                        "/tmp/not-recorded"
                    ),
                ],
                "timeout_sec": 2,
            },
            codex_bin=str(reverse_hanging_codex),
            default_timeout_sec=2,
            prompt_bridge_command=str(reverse_hanging_bridge),
            first_action_timeout_sec=1,
        )
        assert reverse_hanging_timeout["exit_code"] == 124, reverse_hanging_timeout
        assert any(
            marker in reverse_hanging_timeout["stderr"]
            for marker in (
                "codex_exec_timeout",
                "codex_exec_first_action_timeout",
                "codex_exec_bridge_idle_timeout",
            )
        ), reverse_hanging_timeout
        reverse_hanging_operations = [
            json.loads(line)
            for line in str(
                reverse_hanging_timeout["agent_operations_jsonl"]
            ).splitlines()
            if line.strip()
        ]
        if "codex_exec_first_action_timeout" in reverse_hanging_timeout["stderr"]:
            assert reverse_hanging_operations == [], reverse_hanging_timeout
        else:
            assert len(reverse_hanging_operations) == 1, reverse_hanging_timeout
            assert (
                reverse_hanging_operations[0]["task_facing_operation"] is True
            ), reverse_hanging_operations
            assert (
                reverse_hanging_operations[0]["raw_request_recorded"] is False
            ), reverse_hanging_operations
        fake_ssh = Path(tmp) / "ssh"
        fake_ssh.write_text("#!/usr/bin/env bash\nexit 255\n", encoding="utf-8")
        fake_ssh.chmod(0o755)
        ssh_bridge_codex = Path(tmp) / "ssh-bridge-codex"
        ssh_bridge_codex.write_text(
            f"""#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys

os.environ["PATH"] = {str(tmp)!r} + os.pathsep + os.environ.get("PATH", "")
prompt = sys.stdin.read()
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({{"operation": "exec", "cwd": "/app", "command": "true"}}),
    text=True,
    shell=True,
    check=False,
)
""",
            encoding="utf-8",
        )
        ssh_bridge_codex.chmod(0o755)
        ssh_bridge_payload = _run_codex_payload(
            {
                "args": [
                    "exec",
                    (
                        "LoopX bridge test. Your first tool action should be "
                        "a shell pipeline that sends JSON to the private bridge.\n\n"
                        "Private bridge command:\n"
                        "ssh loopx-unavailable.example"
                    ),
                ],
                "timeout_sec": 5,
            },
            codex_bin=str(ssh_bridge_codex),
            default_timeout_sec=5,
            prompt_bridge_command="ssh loopx-unavailable.example",
            first_action_timeout_sec=3,
        )
        ssh_bridge_operations = [
            json.loads(line)
            for line in str(ssh_bridge_payload["agent_operations_jsonl"]).splitlines()
            if line.strip()
        ]
        assert ssh_bridge_payload["exit_code"] == 0, ssh_bridge_payload
        assert ssh_bridge_operations[-1]["record_phase"] == "complete"
        assert ssh_bridge_operations[-1]["failure_category"] == (
            "bridge_ssh_unavailable"
        ), ssh_bridge_operations
        idle_bridge = Path(tmp) / "post-action-idle-bridge"
        idle_bridge.write_text(
            """#!/usr/bin/env python3
import json
import sys

payload = json.loads(sys.stdin.read() or "{}")
if "operations" in payload:
    print(json.dumps({
        "schema_version": "skillsbench_remote_command_file_bridge_probe_response_v0",
        "ready": True,
        "stage": "complete",
        "operations": [
            {"kind": "exec", "status": "ok", "exit_code_zero": True},
            {"kind": "write_file", "status": "ok"},
            {"kind": "read_file", "status": "ok", "content_match": True},
            {"kind": "cleanup", "status": "ok"},
        ],
        "raw_command_recorded": False,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_recorded": False,
        "raw_logs_recorded": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
        "remote_paths_recorded": False,
        "upload_performed": False,
        "submit_performed": False,
    }))
else:
    print("{}")
""",
            encoding="utf-8",
        )
        idle_bridge.chmod(0o755)
        idle_codex = Path(tmp) / "post-action-idle-codex"
        idle_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import time

args = sys.argv[1:]
prompt = sys.stdin.read()
if any("Private bridge command:" in item for item in args):
    raise SystemExit(42)
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "python - <<'PY'\\nprint('task-facing')\\nPY",
        "timeout_sec": 10,
    }),
    text=True,
    shell=True,
    check=True,
)
time.sleep(30)
""",
            encoding="utf-8",
        )
        idle_codex.chmod(0o755)
        idle_trace_dir = Path(tmp) / "post-action-idle-traces"
        idle_relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                codex_bin=str(idle_codex),
                sandbox="workspace-write",
                route="loopx-product-mode",
                dataset="skillsbench-v1.1",
                task_id="demo-task",
                timeout_sec=30,
                first_action_timeout_sec=3,
                bridge_idle_timeout_sec=1,
                worker_public_trace_dir=str(idle_trace_dir),
                remote_command_file_bridge_command=str(idle_bridge),
                remote_command_file_bridge_agent_command=str(idle_bridge),
            )
        )
        idle_response = idle_relay._run_codex(
            "LoopX demo prompt.",
            session={"cwd": str(Path(tmp))},
            session_id="idle-demo",
            stdout=io.StringIO(),
        )
        assert "LoopX recoverable Codex turn failure" in idle_response
        assert "codex_exec_bridge_idle_timeout" in idle_response
        idle_traces = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in idle_trace_dir.glob("*.compact.json")
        ]
        idle_agent_ops = [
            trace
            for trace in idle_traces
            if trace.get("trace_kind") == "remote_command_file_bridge_agent_operations"
        ]
        assert len(idle_agent_ops) == 1, idle_traces
        idle_counts = idle_agent_ops[0]["remote_command_file_bridge_agent_operations"]
        assert idle_counts["request_count"] in {0, 1}, idle_counts
        if idle_counts["request_count"] == 1:
            assert idle_counts["task_facing_operation_count"] == 1, idle_counts
        else:
            assert idle_counts["task_facing_operation_count"] == 0, idle_counts
        assert idle_counts["raw_material_recorded"] is False, idle_counts
        idle_failures = [
            trace
            for trace in idle_traces
            if trace.get("trace_kind") == "codex_exec_process_failure"
        ]
        assert len(idle_failures) == 1, idle_traces
        assert idle_failures[0]["codex_exec_process"]["failure_category"] == (
            "codex_exec_bridge_idle_timeout"
        )
        inflight_bridge = Path(tmp) / "inflight-idle-bridge"
        inflight_bridge.write_text(
            """#!/usr/bin/env python3
import json
import sys
import time

payload = json.loads(sys.stdin.read() or "{}")
if "operations" in payload:
    print(json.dumps({
        "schema_version": "skillsbench_remote_command_file_bridge_probe_response_v0",
        "ready": True,
        "stage": "complete",
        "operations": [
            {"kind": "exec", "status": "ok", "exit_code_zero": True},
            {"kind": "write_file", "status": "ok"},
            {"kind": "read_file", "status": "ok", "content_match": True},
            {"kind": "cleanup", "status": "ok"},
        ],
        "raw_command_recorded": False,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_recorded": False,
        "raw_logs_recorded": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
        "remote_paths_recorded": False,
        "upload_performed": False,
        "submit_performed": False,
    }))
    raise SystemExit(0)
time.sleep(30)
""",
            encoding="utf-8",
        )
        inflight_bridge.chmod(0o755)
        inflight_codex = Path(tmp) / "inflight-idle-codex"
        inflight_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

args = sys.argv[1:]
prompt = sys.stdin.read()
if any("Private bridge command:" in item for item in args):
    raise SystemExit(42)
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({
        "operation": "exec",
        "cwd": "/app",
        "command": "python - <<'PY'\\nprint('task-facing')\\nPY",
        "timeout_sec": 10,
    }),
    text=True,
    shell=True,
    check=False,
)
""",
            encoding="utf-8",
        )
        inflight_codex.chmod(0o755)
        inflight_trace_dir = Path(tmp) / "inflight-idle-traces"
        inflight_relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                codex_bin=str(inflight_codex),
                sandbox="workspace-write",
                route="loopx-product-mode",
                dataset="skillsbench-v1.1",
                task_id="demo-task",
                timeout_sec=2,
                first_action_timeout_sec=3,
                bridge_idle_timeout_sec=1,
                worker_public_trace_dir=str(inflight_trace_dir),
                remote_command_file_bridge_command=str(inflight_bridge),
                remote_command_file_bridge_agent_command=str(inflight_bridge),
            )
        )
        inflight_response = inflight_relay._run_codex(
            "LoopX demo prompt.",
            session={"cwd": str(Path(tmp))},
            session_id="inflight-idle-demo",
            stdout=io.StringIO(),
        )
        assert "LoopX recoverable Codex turn failure" in inflight_response
        assert "codex_exec_timeout" in inflight_response
        inflight_traces = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in inflight_trace_dir.glob("*.compact.json")
        ]
        inflight_agent_ops = [
            trace
            for trace in inflight_traces
            if trace.get("trace_kind") == "remote_command_file_bridge_agent_operations"
        ]
        assert len(inflight_agent_ops) == 1, inflight_traces
        inflight_counts = inflight_agent_ops[0][
            "remote_command_file_bridge_agent_operations"
        ]
        assert inflight_counts["request_count"] in {0, 1}, inflight_counts
        if inflight_counts["request_count"] == 1:
            assert inflight_counts["task_facing_operation_count"] == 1, inflight_counts
            assert inflight_counts["failure_count"] == 0, inflight_counts
            assert inflight_counts["failure_category_counts"] == {}, inflight_counts
            assert inflight_counts["task_facing_interrupted_count"] == inflight_counts[
                "interrupted_operation_count"
            ], inflight_counts
        else:
            assert inflight_counts["task_facing_operation_count"] == 0, inflight_counts
        assert inflight_counts["inflight_operation_count"] >= 1, inflight_counts
        assert inflight_counts["raw_material_recorded"] is False, inflight_counts
        inflight_failures = [
            trace
            for trace in inflight_traces
            if trace.get("trace_kind") == "codex_exec_process_failure"
        ]
        assert len(inflight_failures) == 1, inflight_traces
        assert inflight_failures[0]["codex_exec_process"]["failure_category"] == (
            "codex_exec_timeout"
        )
        bridge_preflight_codex = Path(tmp) / "bridge-preflight-codex"
        bridge_preflight_codex.write_text(
            f"""#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
output = Path(args[args.index("--output-last-message") + 1])
prompt = sys.stdin.read()
if any("Private bridge command:" in item for item in args):
    raise SystemExit(42)
match = re.search(r"Private bridge command:\\n([^\\n]+)", prompt)
assert match, prompt
subprocess.run(
    match.group(1),
    input=json.dumps({{
        "operation": "preflight",
    }}),
    text=True,
    shell=True,
    check=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
output.write_text({SKILLSBENCH_LOCAL_ACP_RELAY_BRIDGE_PREFLIGHT_MARKER!r}, encoding="utf-8")
""",
            encoding="utf-8",
        )
        bridge_preflight_codex.chmod(0o755)
        bridge_preflight_plan = {
            "host_local_acp_relay_trace_dir": str(
                Path(tmp) / "bridge-preflight-traces"
            ),
            "runner_prerequisites": {},
        }
        bridge_preflight_args = SimpleNamespace(
            dataset="skillsbench-v1.1",
            host_local_acp_codex_exec_preflight_attempts=1,
            host_local_acp_codex_exec_preflight_timeout_sec=20,
            host_local_acp_launch=True,
            local_acp_relay_command=None,
            local_codex_bin=str(bridge_preflight_codex),
            local_codex_first_action_timeout_sec=1800,
            local_codex_sandbox="workspace-write",
            model=None,
            remote_command_file_bridge_agent_command=str(idle_bridge),
            remote_command_file_bridge_probe=False,
            remote_command_file_bridge_probe_timeout_sec=5.0,
            remote_command_file_bridge_ready=True,
            remote_command_file_bridge_solver_command=str(idle_bridge),
            route="loopx-product-mode",
            task_id="demo-task",
        )
        _run_host_local_acp_codex_exec_preflight(
            bridge_preflight_args,
            bridge_preflight_plan,
        )
        bridge_preflight_prereqs = bridge_preflight_plan["runner_prerequisites"]
        assert (
            bridge_preflight_prereqs["host_local_acp_codex_exec_preflight_status"]
            == "passed"
        ), bridge_preflight_prereqs
        assert (
            bridge_preflight_prereqs[
                "host_local_acp_codex_exec_preflight_bridge_action_required"
            ]
            is True
        ), bridge_preflight_prereqs
        assert (
            bridge_preflight_prereqs[
                "host_local_acp_codex_exec_preflight_bridge_action_observed"
            ]
            is True
        ), bridge_preflight_prereqs
        assert (
            bridge_preflight_prereqs[
                "host_local_acp_codex_exec_preflight_bridge_task_facing_operation_count"
            ]
            == 0
        ), bridge_preflight_prereqs
        assert (
            bridge_preflight_prereqs[
                "host_local_acp_codex_exec_preflight_bridge_preflight_operation_count"
            ]
            == 1
        ), bridge_preflight_prereqs
        assert (
            bridge_preflight_prereqs[
                "host_local_acp_codex_exec_preflight_response_marker_observed"
            ]
            is True
        ), bridge_preflight_prereqs
        assert (
            "remote_command_file_bridge_agent_task_facing_operation_count"
            not in bridge_preflight_prereqs
        ), bridge_preflight_prereqs
        captured_preflight: dict[str, object] = {}
        original_relay_probe = _run_host_local_acp_codex_exec_preflight.__globals__[
            "run_skillsbench_local_acp_relay_probe"
        ]

        def fake_relay_probe(command, **kwargs):
            captured_preflight["command"] = list(command)
            captured_preflight["env"] = dict(kwargs.get("env") or {})
            return {
                "ready": True,
                "stage": "complete",
                "first_blocker": "skillsbench_local_acp_relay_ready",
                "response_marker_observed": True,
            }

        _run_host_local_acp_codex_exec_preflight.__globals__[
            "run_skillsbench_local_acp_relay_probe"
        ] = fake_relay_probe
        try:
            env_preflight_plan = {
                "host_local_acp_relay_trace_dir": str(
                    Path(tmp) / "env-preflight-traces"
                ),
                "runner_prerequisites": {},
            }
            env_preflight_args = SimpleNamespace(
                codex_api_egress_mode="reverse-tunnel",
                codex_api_reverse_tunnel_proxy=(
                    "http://reverse-proxy.example.invalid:18080"
                ),
                dataset="skillsbench-v1.1",
                host_local_acp_codex_exec_preflight_attempts=1,
                host_local_acp_codex_exec_preflight_timeout_sec=20,
                host_local_acp_launch=True,
                local_acp_relay_command=None,
                local_codex_bin=str(bridge_preflight_codex),
                local_codex_first_action_timeout_sec=0,
                local_codex_sandbox="workspace-write",
                model="gpt-5.5",
                remote_command_file_bridge_agent_command="",
                remote_command_file_bridge_probe=False,
                remote_command_file_bridge_probe_timeout_sec=5.0,
                remote_command_file_bridge_ready=False,
                remote_command_file_bridge_solver_command="",
                reasoning_effort="xhigh",
                route="codex-acp-blind-loop-baseline",
                task_id="demo-task",
            )
            _run_host_local_acp_codex_exec_preflight(
                env_preflight_args,
                env_preflight_plan,
            )
        finally:
            _run_host_local_acp_codex_exec_preflight.__globals__[
                "run_skillsbench_local_acp_relay_probe"
            ] = original_relay_probe
        env_preflight_prereqs = env_preflight_plan["runner_prerequisites"]
        assert (
            env_preflight_prereqs["host_local_acp_codex_exec_preflight_status"]
            == "passed"
        ), env_preflight_prereqs
        assert (
            env_preflight_prereqs["host_local_acp_target_env_forwarded"] is True
        ), env_preflight_prereqs
        assert "HTTPS_PROXY" in env_preflight_prereqs["host_local_acp_target_env_keys"]
        assert (
            "LOOPX_CODEX_API_REVERSE_TUNNEL_PROXY"
            in env_preflight_prereqs["host_local_acp_target_env_keys"]
        )
        assert (
            env_preflight_prereqs["host_local_acp_proxy_endpoint_status"]
            == "non_loopback_proxy"
        ), env_preflight_prereqs
        assert (
            env_preflight_prereqs["host_local_acp_proxy_endpoint_raw_url_recorded"]
            is False
        ), env_preflight_prereqs
        captured_env = captured_preflight["env"]
        assert isinstance(captured_env, dict)
        assert (
            captured_env["HTTPS_PROXY"]
            == "http://reverse-proxy.example.invalid:18080"
        )
        captured_command = captured_preflight["command"]
        assert isinstance(captured_command, list)
        assert "--reasoning-effort" in captured_command
        assert captured_command[captured_command.index("--reasoning-effort") + 1] == (
            "xhigh"
        )
        preflight_plan = {
            "host_local_acp_relay_trace_dir": str(Path(tmp) / "preflight-traces"),
            "runner_prerequisites": {},
        }
        preflight_args = SimpleNamespace(
            dataset="skillsbench-v1.1",
            host_local_acp_codex_exec_preflight_attempts=1,
            host_local_acp_codex_exec_preflight_timeout_sec=20,
            host_local_acp_launch=False,
            local_acp_relay_command=None,
            local_codex_bin=str(reverse_failing_codex),
            local_codex_first_action_timeout_sec=0,
            local_codex_sandbox="workspace-write",
            model="gpt-5.5",
            remote_command_file_bridge_probe=False,
            remote_command_file_bridge_ready=False,
            remote_command_file_bridge_solver_command=None,
            reasoning_effort="xhigh",
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
        interrupted_jobs_dir = Path(tmp) / "interrupted-jobs"
        interrupted_job_name = "skillsbench-interrupted-before-score-fixture"
        interrupted_rollout_name = "demo-task__loopx_product_mode"
        interruption_compact = build_runner_failure_compact(
            SimpleNamespace(build_stall_timeout_sec=0, dataset="skillsbench-v1.1", model=None, run_group_id=None, route="loopx-product-mode", task_id="demo-task"),
            {
                "jobs_dir": str(interrupted_jobs_dir),
                "job_name": interrupted_job_name,
                "rollout_name": interrupted_rollout_name,
                "task_id": "demo-task",
                "result_json": str(interrupted_jobs_dir / interrupted_job_name / interrupted_rollout_name / "result.json"),
                "compact_benchmark_run_json": str(Path(tmp) / "interrupted-compact.json"),
                "runner_prerequisites": {"schema_version": "skillsbench_runner_prerequisites_v0", "agent_execution_mode": "host_local_acp"},
            },
            KeyboardInterrupt(),
        )
        assert interruption_compact["score_failure_attribution"] == "skillsbench_runner_interrupted_before_official_result", interruption_compact
        assert interruption_compact["runner_return_status"] == "failed_before_official_result", interruption_compact
        assert ".local/private-benchmark-jobs" not in json.dumps(interruption_compact), interruption_compact
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
