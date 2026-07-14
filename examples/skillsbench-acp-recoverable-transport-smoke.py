#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.skillsbench_fixtures import write_official_skillsbench_result  # noqa: E402
from loopx.benchmark_adapters.skillsbench import (  # noqa: E402
    build_skillsbench_benchflow_result_benchmark_run,
)
from loopx.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
    run_skillsbench_local_acp_relay_probe,
)
from loopx.status import compact_benchmark_run  # noqa: E402
from scripts.skillsbench_automation_loop import (  # noqa: E402
    _merge_host_local_acp_relay_trace_summary,
    _public_runner_prerequisites,
)


def write_failing_codex(path: Path) -> None:
    path.write_text(
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
    path.chmod(0o755)


def test_runtime_transport_failure_is_recoverable() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-transport-") as tmp:
        root = Path(tmp)
        fake_codex = root / "network-failing-codex"
        write_failing_codex(fake_codex)

        preflight_trace_dir = root / "preflight-traces"
        preflight = run_skillsbench_local_acp_relay_probe(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_local_acp_relay.py"),
                "--codex-bin",
                str(fake_codex),
                "--route",
                "loopx-product-mode",
                "--dataset",
                "skillsbench-v1.1",
                "--task-id",
                "demo-task",
                "--worker-public-trace-dir",
                str(preflight_trace_dir),
            ],
            timeout_sec=20,
        )
        assert preflight["ready"] is False, preflight
        preflight_failure = read_only_trace(preflight_trace_dir)
        assert preflight_failure["codex_exec_process"][
            "recoverable_turn_failure"
        ] is False

        runtime_trace_dir = root / "runtime-traces"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                codex_bin=str(fake_codex),
                sandbox="workspace-write",
                route="loopx-product-mode",
                dataset="skillsbench-v1.1",
                task_id="demo-task",
                timeout_sec=20,
                worker_public_trace_dir=str(runtime_trace_dir),
            )
        )
        response = relay._run_codex(
            "Continue the current product-mode benchmark turn.",
            session={"cwd": str(root)},
            session_id="network-runtime-demo",
            stdout=io.StringIO(),
        )
        assert "LoopX recoverable Codex turn failure" in response
        assert "codex_network_or_api_unreachable" in response
        runtime_failure = read_only_trace(runtime_trace_dir)
        process = runtime_failure["codex_exec_process"]
        assert process["failure_category"] == "codex_network_or_api_unreachable"
        assert process["recoverable_turn_failure"] is True
        assert process["raw_stdout_recorded"] is False
        assert process["raw_stderr_recorded"] is False

        controller_trace, prerequisites = reduce_trace_dir(runtime_trace_dir)
        assert controller_trace[
            "host_local_acp_codex_exec_recoverable_failure_trace_count"
        ] == 1
        assert controller_trace[
            "host_local_acp_codex_exec_fatal_failure_trace_count"
        ] == 0
        public_prerequisites = _public_runner_prerequisites(prerequisites)
        assert public_prerequisites[
            "host_local_acp_codex_exec_recoverable_failure_trace_count"
        ] == 1

        legacy_trace = dict(runtime_failure)
        legacy_process = dict(legacy_trace["codex_exec_process"])
        legacy_process.pop("recoverable_turn_failure")
        legacy_trace["codex_exec_process"] = legacy_process
        legacy_trace_dir = root / "legacy-traces"
        legacy_trace_dir.mkdir()
        (legacy_trace_dir / "legacy.compact.json").write_text(
            json.dumps(legacy_trace, sort_keys=True),
            encoding="utf-8",
        )
        legacy_controller, _ = reduce_trace_dir(legacy_trace_dir)
        assert legacy_controller[
            "host_local_acp_codex_exec_recoverable_failure_trace_count"
        ] == 1
        assert legacy_controller[
            "host_local_acp_codex_exec_fatal_failure_trace_count"
        ] == 0


def test_recoverable_transport_score_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-score-") as tmp:
        result_path = write_official_skillsbench_result(Path(tmp), reward=0.0)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["error"] = "synthetic codex network transport interruption"
        result_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")

        trace = product_mode_trace()
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=trace,
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), compact
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_runner_setup_error" not in labels, compact
        assert "skillsbench_product_mode_transport_failure" not in labels, compact
        assert (
            "skillsbench_host_local_acp_recoverable_transport_after_bridge_attempt"
            in compact["runner_warning_labels"]
        ), compact
        assert "runner_failure" not in compact, compact
        accounting = compact["attempt_accounting"]
        assert accounting["case_attempt_countable"] is True, accounting
        assert accounting["official_score_attempt_countable"] is True, accounting

        mixed_trace = dict(trace)
        mixed_trace.update(
            {
                "host_local_acp_codex_exec_failure_trace_count": 2,
                "host_local_acp_codex_exec_recoverable_failure_trace_count": 1,
                "host_local_acp_codex_exec_fatal_failure_trace_count": 1,
                "host_local_acp_codex_exec_failure_categories": [
                    "codex_network_or_api_unreachable",
                    "codex_usage_limit",
                ],
            }
        )
        mixed = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=mixed_trace,
            )
        )
        assert mixed is not None
        assert "skillsbench_runner_setup_error" in mixed["failure_attribution_labels"]
        assert mixed["attempt_accounting"]["case_attempt_countable"] is False
        assert mixed["attempt_accounting"][
            "official_score_attempt_countable"
        ] is False


def read_only_trace(trace_dir: Path) -> dict[str, Any]:
    paths = list(trace_dir.glob("*.compact.json"))
    assert len(paths) == 1, paths
    return json.loads(paths[0].read_text(encoding="utf-8"))


def reduce_trace_dir(trace_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    controller_trace: dict[str, Any] = {
        "schema_version": "skillsbench_loopx_controller_trace_v0"
    }
    plan: dict[str, Any] = {
        "host_local_acp_relay_trace_dir": str(trace_dir),
        "runner_prerequisites": {},
    }
    _merge_host_local_acp_relay_trace_summary(plan, controller_trace)
    return controller_trace, plan["runner_prerequisites"]


def product_mode_trace() -> dict[str, Any]:
    return {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-goal-start-product-mode",
        "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        "product_mode": True,
        "remote_command_file_bridge_driver_lifecycle_execution_style": (
            "orchestrated_agentloop_loopx_cli"
        ),
        "remote_command_file_bridge_driver_lifecycle_trace_count": 3,
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count": 3,
        "remote_command_file_bridge_driver_lifecycle_request_count": 12,
        "remote_command_file_bridge_driver_lifecycle_success_count": 12,
        "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count": 12,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count": 3,
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count": 9,
        "remote_command_file_bridge_agent_operation_trace_status": (
            "agent_operation_trace_recorded"
        ),
        "remote_command_file_bridge_agent_operation_trace_count": 3,
        "remote_command_file_bridge_agent_operation_trace_satisfied": True,
        "remote_command_file_bridge_agent_request_count": 8,
        "remote_command_file_bridge_agent_task_facing_operation_count": 6,
        "remote_command_file_bridge_agent_task_facing_success_count": 6,
        "remote_command_file_bridge_agent_loopx_state_read_count": 3,
        "remote_command_file_bridge_agent_loopx_state_write_count": 3,
        "remote_command_file_bridge_agent_todo_closeout_count": 1,
        "remote_command_file_bridge_agent_refresh_state_count": 1,
        "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        "host_local_acp_codex_exec_failure_trace_present": True,
        "host_local_acp_codex_exec_failure_trace_count": 1,
        "host_local_acp_codex_exec_recoverable_failure_trace_count": 1,
        "host_local_acp_codex_exec_fatal_failure_trace_count": 0,
        "host_local_acp_codex_exec_failure_category": (
            "codex_network_or_api_unreachable"
        ),
        "host_local_acp_codex_exec_failure_categories": [
            "codex_network_or_api_unreachable"
        ],
        "host_local_acp_codex_exec_failure_raw_material_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
    }


if __name__ == "__main__":
    test_runtime_transport_failure_is_recoverable()
    test_recoverable_transport_score_policy()
    print("skillsbench ACP recoverable transport smoke passed")
