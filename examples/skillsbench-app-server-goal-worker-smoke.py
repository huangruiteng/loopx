#!/usr/bin/env python3
"""Smoke-test the SkillsBench native Codex app-server Goal worker seam."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION,
    build_skillsbench_app_server_goal_worker_contract,
    build_skillsbench_benchmark_run,
    skillsbench_route_contract,
)
from goal_harness.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    run_skillsbench_local_acp_relay_probe,
)


ROUTE = "codex-app-server-goal-baseline"

FAKE_CODEX = """#!/usr/bin/env python3
import json
import sys

for line in sys.stdin:
    msg = json.loads(line)
    mid = msg.get("id")
    method = msg.get("method")
    if method == "initialized":
        continue
    if method == "initialize":
        result = {"serverInfo": {"name": "fake-codex"}}
    elif method == "thread/start":
        result = {"thread": {"id": "thread-skillsbench"}}
    elif method == "thread/goal/set":
        result = {"goal": {"threadId": "thread-skillsbench", "status": "active"}}
    elif method == "thread/goal/get":
        result = {"goal": {"threadId": "thread-skillsbench", "status": "active"}}
    elif method == "turn/start":
        if msg.get("params", {}).get("effort") != "high":
            print(json.dumps({
                "id": mid,
                "error": {"code": -32602, "message": "missing high effort"},
            }), flush=True)
            continue
        result = {"turn": {"id": "turn-skillsbench", "status": "running"}}
        print(json.dumps({"id": mid, "result": result}), flush=True)
        print(json.dumps({
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thread-skillsbench",
                "turnId": "turn-skillsbench",
                "itemId": "item-skillsbench",
                "delta": "private worker answer",
            },
        }), flush=True)
        print(json.dumps({
            "method": "turn/completed",
            "params": {
                "threadId": "thread-skillsbench",
                "turn": {"id": "turn-skillsbench", "status": "completed"},
            },
        }), flush=True)
        continue
    else:
        result = {}
    print(json.dumps({"id": mid, "result": result}), flush=True)
"""


def assert_plan_prerequisites(plan: dict[str, Any]) -> None:
    prereq = plan["runner_prerequisites"]
    assert plan["route"] == ROUTE, plan
    assert plan["agent"] == "codex-app-server-goal", plan
    assert prereq["agent_execution_mode"] == "host_codex_app_server_goal_worker", prereq
    assert prereq["codex_acp_runtime_container_bootstrap"] is False, prereq
    assert prereq["codex_acp_runtime_dependency_preflight"] is False, prereq
    assert prereq["container_codex_acp_install_skipped"] is True, prereq
    assert prereq["codex_app_server_goal_worker_adapter_present"] is True, prereq
    assert prereq["codex_app_server_goal_worker_turn_start_required"] is True, prereq
    assert prereq["codex_app_server_goal_worker_goal_get_required"] is True, prereq
    assert (
        prereq["codex_app_server_goal_worker_remote_command_file_bridge_required"]
        is True
    ), prereq
    assert (
        prereq["codex_app_server_goal_worker_runner_integration_ready"] is False
    ), prereq
    assert (
        prereq["codex_app_server_goal_worker_remote_command_file_bridge_ready"]
        is False
    ), prereq


def test_route_contract_requires_native_goal_proof() -> None:
    contract = skillsbench_route_contract(ROUTE)
    assert contract["native_goal_mode_requested"] is True, contract
    assert contract["native_goal_mode_invoked"] is True, contract
    assert contract["codex_acp_protocol_used"] is False, contract
    assert "thread_goal_set_get" in contract["native_goal_mode_confirmation_status"], contract
    assert contract["reward_feedback_forwarded"] is False, contract


def test_worker_contract_is_public_safe() -> None:
    payload = build_skillsbench_app_server_goal_worker_contract(
        task_id="llm-prefix-cache-replay",
        model="gpt-5.5",
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is True, payload
    assert payload["runner_integration_ready"] is False, payload
    assert payload["worker_adapter"]["worker_surface"] == "codex_app_server", payload
    assert "turn/start" in payload["worker_adapter"]["native_goal_methods_required"], payload
    assert payload["proof_required"]["thread_goal_get"] is True, payload
    assert payload["proof_required"]["turn_start"] is True, payload
    assert payload["boundary"]["raw_task_text_read_into_public_state"] is False, payload
    assert payload["worker_plan"]["claim_boundary"]["requires_turn_start_evidence"] is True, payload


def test_skeleton_marks_app_server_goal_actor() -> None:
    run = build_skillsbench_benchmark_run(route=ROUTE, task_id="llm-prefix-cache-replay")
    counters = run["interaction_counters"]
    policy = run["episode_policy"]
    assert run["source_runner"] == "goal_harness_skillsbench_host_codex_app_server_goal_worker", run
    assert counters["native_goal_mode_requested"] is True, counters
    assert counters["native_goal_mode_invoked"] is True, counters
    assert counters["codex_acp_protocol_used"] is False, counters
    assert policy["outer_controller"] == "codex_app_server_goal_worker", policy
    assert policy["inner_case_actor"] == "host_codex_app_server_goal_worker", policy


def test_launcher_plan_only_uses_native_worker_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-plan-") as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "llm-prefix-cache-replay",
                "--route",
                ROUTE,
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    plan = payload["launch_plan"]
    assert_plan_prerequisites(plan)
    contract = plan["app_server_goal_worker_contract"]
    assert contract["route"] == ROUTE, contract
    assert contract["worker_plan"]["schema_version"] == "codex_app_server_goal_worker_v0", contract
    assert plan["app_server_goal_worker_trace_dir"].endswith(
        "app_server_goal_worker_traces"
    ), plan


def test_launcher_plan_only_marks_bridge_ready_when_explicit() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-plan-") as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "llm-prefix-cache-replay",
                "--route",
                ROUTE,
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--remote-command-file-bridge-ready",
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(result.stdout)
    prereq = payload["launch_plan"]["runner_prerequisites"]
    assert (
        prereq["codex_app_server_goal_worker_remote_command_file_bridge_ready"]
        is True
    ), prereq
    assert (
        prereq["codex_app_server_goal_worker_runner_integration_ready"] is False
    ), prereq


def test_launcher_plan_only_marks_runner_ready_with_host_acp_launch() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-plan-") as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "llm-prefix-cache-replay",
                "--route",
                ROUTE,
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--remote-command-file-bridge-ready",
                "--host-local-acp-launch",
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(result.stdout)
    prereq = payload["launch_plan"]["runner_prerequisites"]
    assert (
        prereq["codex_app_server_goal_worker_remote_command_file_bridge_ready"]
        is True
    ), prereq
    assert (
        prereq["codex_app_server_goal_worker_runner_integration_ready"] is True
    ), prereq


def test_host_worker_contract_only_cli() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_host_codex_goal_worker.py"),
            "--task-id",
            "tictoc-unnecessary-abort-detection",
            "--contract-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    contract = payload["worker_contract"]
    assert contract["route"] == ROUTE, contract
    assert contract["worker_adapter"]["script"] == "scripts/skillsbench_host_codex_goal_worker.py", contract
    assert contract["worker_adapter"]["reasoning_effort"] == "high", contract


def test_host_worker_waits_for_completion_and_keeps_public_json_compact() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-worker-") as tmp:
        root = Path(tmp)
        fake = root / "codex"
        prompt = root / "prompt.txt"
        output = root / "worker.compact.json"
        private_response = root / "private-response.txt"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        fake.chmod(0o755)
        prompt.write_text("Private task instruction placeholder.", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_host_codex_goal_worker.py"),
                "--task-id",
                "llm-prefix-cache-replay",
                "--codex-bin",
                str(fake),
                "--work-dir",
                str(root / "work"),
                "--prompt-file",
                str(prompt),
                "--output-json",
                str(output),
                "--response-text-file",
                str(private_response),
                "--response-timeout-sec",
                "5",
                "--turn-timeout-sec",
                "5",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        assert result.stdout == "", result
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["ok"] is True, payload
        assert payload["turn"]["turn_completed_observed"] is True, payload
        assert payload["turn"]["assistant_message_present"] is True, payload
        assert payload["private_response_text"]["written"] is True, payload
        assert payload["private_response_text"]["path_recorded"] is False, payload
        assert private_response.read_text(encoding="utf-8") == "private worker answer"
        public_json = json.dumps(payload)
        assert "private worker answer" not in public_json, payload
        assert "Private task instruction placeholder" not in public_json, payload


def test_acp_relay_delegates_to_app_server_goal_worker() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-acp-") as tmp:
        root = Path(tmp)
        fake = root / "codex"
        work = root / "work"
        fake.write_text(FAKE_CODEX, encoding="utf-8")
        fake.chmod(0o755)
        work.mkdir()
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_local_acp_relay.py"),
            "--app-server-goal-worker",
            "--task-id",
            "llm-prefix-cache-replay",
            "--codex-bin",
            str(fake),
            "--timeout-sec",
            "5",
            "--response-timeout-sec",
            "5",
        ]
        probe = run_skillsbench_local_acp_relay_probe(
            command,
            timeout_sec=10,
        )
    assert probe["ready"] is True, probe


def test_acp_relay_streams_public_keepalive_while_worker_runs() -> None:
    fake_worker = """#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--response-text-file")
parser.add_argument("--output-json")
args, _ = parser.parse_known_args()
time.sleep(0.25)
Path(args.response_text_file).write_text("private delayed answer", encoding="utf-8")
Path(args.output_json).write_text(json.dumps({"ok": True}), encoding="utf-8")
"""
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-keepalive-") as tmp:
        root = Path(tmp)
        worker = root / "fake_worker.py"
        work = root / "work"
        trace_dir = root / "worker-traces"
        worker.write_text(fake_worker, encoding="utf-8")
        worker.chmod(0o755)
        work.mkdir()
        proc = subprocess.Popen(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_local_acp_relay.py"),
                "--app-server-goal-worker",
                "--task-id",
                "llm-prefix-cache-replay",
                "--worker-script",
                str(worker),
                "--timeout-sec",
                "5",
                "--stream-heartbeat-interval-sec",
                "0.05",
                "--worker-public-trace-dir",
                str(trace_dir),
            ],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        def send(message: dict[str, Any]) -> None:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()

        def read_response(request_id: int) -> dict[str, Any]:
            while True:
                line = proc.stdout.readline()
                assert line, proc.stderr.read()
                message = json.loads(line)
                if message.get("id") == request_id and "method" not in message:
                    return message

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        read_response(1)
        send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "session/new",
                "params": {"cwd": str(work), "mcpServers": []},
            }
        )
        session_id = read_response(2)["result"]["sessionId"]
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "session/set_model",
                "params": {"sessionId": session_id, "modelId": "probe-model"},
            }
        )
        read_response(3)
        send(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "session/prompt",
                "params": {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": "private task placeholder"}],
                },
            }
        )
        keepalive_seen = False
        final_response = None
        for _ in range(20):
            line = proc.stdout.readline()
            assert line, proc.stderr.read()
            message = json.loads(line)
            if message.get("method") == "session/update":
                update = message["params"]["update"]
                if update.get("sessionUpdate") == "agent_thought_chunk":
                    keepalive_seen = True
                    assert "task placeholder" not in json.dumps(update), update
            if message.get("id") == 4 and "method" not in message:
                final_response = message
                break
        assert keepalive_seen
        assert final_response is not None
        assert final_response["result"]["stopReason"] == "end_turn"
        trace_files = sorted(trace_dir.glob("*.compact.json"))
        assert len(trace_files) == 1, trace_files
        trace = json.loads(trace_files[0].read_text(encoding="utf-8"))
        assert (
            trace["schema_version"]
            == "skillsbench_host_codex_goal_worker_public_trace_v0"
        ), trace
        assert trace["ok"] is True, trace
        assert trace["private_response_text"].get("path_recorded") is not True, trace
        assert "private delayed answer" not in json.dumps(trace), trace
        proc.terminate()
        proc.wait(timeout=2)


def test_full_run_fails_closed_until_bridge_is_materialized() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--task-id",
            "llm-prefix-cache-replay",
            "--route",
            ROUTE,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2, result
    payload = json.loads(result.stderr)
    assert payload["error_type"] == "SkillsBenchNativeGoalWorkerBridgePending", payload
    assert "command/file bridge" in payload["reason"], payload


def test_full_run_with_bridge_ready_requires_host_acp_launch() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--task-id",
            "llm-prefix-cache-replay",
            "--route",
            ROUTE,
            "--remote-command-file-bridge-ready",
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2, result
    payload = json.loads(result.stderr)
    assert payload["error_type"] == "SkillsBenchNativeGoalWorkerIntegrationPending", payload
    assert "--host-local-acp-launch" in payload["reason"], payload


def test_launcher_patches_rollout_planes_connect_acp() -> None:
    source = (REPO_ROOT / "scripts" / "skillsbench_automation_loop.py").read_text(
        encoding="utf-8"
    )
    assert "original_rollout_planes_connect_acp" in source, source
    assert (
        "benchflow_rollout_planes_module.connect_acp = connect_host_local_acp"
        in source
    ), source
    assert (
        "benchflow_rollout_planes_module.connect_acp = (\n"
        "                original_rollout_planes_connect_acp\n"
        "            )"
        in source
    ), source


if __name__ == "__main__":
    test_route_contract_requires_native_goal_proof()
    test_worker_contract_is_public_safe()
    test_skeleton_marks_app_server_goal_actor()
    test_launcher_plan_only_uses_native_worker_route()
    test_launcher_plan_only_marks_bridge_ready_when_explicit()
    test_launcher_plan_only_marks_runner_ready_with_host_acp_launch()
    test_host_worker_contract_only_cli()
    test_host_worker_waits_for_completion_and_keeps_public_json_compact()
    test_acp_relay_delegates_to_app_server_goal_worker()
    test_full_run_fails_closed_until_bridge_is_materialized()
    test_full_run_with_bridge_ready_requires_host_acp_launch()
    test_launcher_patches_rollout_planes_connect_acp()
    print("skillsbench-app-server-goal-worker smoke ok")
