#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected to find {needle!r} in output:\n{text}")


def main() -> int:
    cli_source = (ROOT / "loopx" / "cli.py").read_text(encoding="utf-8")
    init_source = (ROOT / "loopx" / "cli_commands" / "__init__.py").read_text(
        encoding="utf-8"
    )
    dispatch_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_dispatch.py"
    ).read_text(encoding="utf-8")
    ale_source = (ROOT / "loopx" / "cli_commands" / "agents_last_exam.py").read_text(
        encoding="utf-8"
    )
    local_plan_source = (
        ROOT / "loopx" / "cli_commands" / "agents_last_exam_local_plan.py"
    ).read_text(encoding="utf-8")
    launch_dry_run_source = (
        ROOT / "loopx" / "cli_commands" / "agents_last_exam_launch_dry_run.py"
    ).read_text(encoding="utf-8")
    runner_source_source = (
        ROOT / "loopx" / "cli_commands" / "agents_last_exam_runner_source.py"
    ).read_text(encoding="utf-8")
    baked_input_source = (
        ROOT / "loopx" / "cli_commands" / "agents_last_exam_baked_input.py"
    ).read_text(encoding="utf-8")
    task_material_source = (
        ROOT / "loopx" / "cli_commands" / "agents_last_exam_task_material.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "ale_local_preflight_parser = benchmark_sub.add_parser",
        "ale_validation_run_gate_parser = benchmark_sub.add_parser",
        "def render_agents_last_exam_local_preflight_markdown",
        "build_agents_last_exam_local_preflight(",
        'if args.benchmark_command == "ale-local-preflight":',
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    assert_contains(
        dispatch_source,
        "register_agents_last_exam_commands(benchmark_sub, add_subcommand_format)",
    )
    assert_contains(dispatch_source, "handle_agents_last_exam_command(")
    assert_contains(init_source, "register_agents_last_exam_commands")
    assert_contains(init_source, "handle_agents_last_exam_command")
    assert_contains(init_source, "register_agents_last_exam_local_plan_commands")
    assert_contains(init_source, "handle_agents_last_exam_local_plan_command")
    assert_contains(init_source, "register_agents_last_exam_launch_dry_run_commands")
    assert_contains(init_source, "handle_agents_last_exam_launch_dry_run_command")
    assert_contains(init_source, "register_agents_last_exam_runner_source_commands")
    assert_contains(init_source, "handle_agents_last_exam_runner_source_command")
    assert_contains(init_source, "register_agents_last_exam_baked_input_commands")
    assert_contains(init_source, "handle_agents_last_exam_baked_input_command")
    assert_contains(init_source, "register_agents_last_exam_task_material_commands")
    assert_contains(init_source, "handle_agents_last_exam_task_material_command")
    assert_contains(ale_source, "AGENTS_LAST_EXAM_COMMANDS")
    assert_contains(ale_source, "ale-validation-run-gate")
    assert_contains(
        ale_source,
        "register_agents_last_exam_local_plan_commands(",
    )
    assert_contains(
        ale_source,
        "handle_agents_last_exam_local_plan_command(",
    )
    assert_contains(
        ale_source,
        "register_agents_last_exam_launch_dry_run_commands(",
    )
    assert_contains(
        ale_source,
        "handle_agents_last_exam_launch_dry_run_command(",
    )
    assert_contains(
        ale_source,
        "register_agents_last_exam_runner_source_commands(",
    )
    assert_contains(
        ale_source,
        "handle_agents_last_exam_runner_source_command(",
    )
    assert_contains(
        ale_source,
        "register_agents_last_exam_baked_input_commands(",
    )
    assert_contains(
        ale_source,
        "handle_agents_last_exam_baked_input_command(",
    )
    assert_contains(
        ale_source,
        "register_agents_last_exam_task_material_commands(",
    )
    assert_contains(
        ale_source,
        "handle_agents_last_exam_task_material_command(",
    )
    for marker in (
        "def render_agents_last_exam_local_preflight_markdown",
        "def render_agents_last_exam_local_dry_run_plan_markdown",
        "build_agents_last_exam_local_preflight(",
        "build_agents_last_exam_local_dry_run_plan(",
        'if args.benchmark_command == "ale-local-preflight":',
    ):
        if marker in ale_source:
            raise AssertionError(f"{marker} leaked back into agents_last_exam.py")
        assert_contains(local_plan_source, marker)
    for marker in (
        "def render_agents_last_exam_local_launch_packet_markdown",
        "def render_agents_last_exam_local_exact_dry_run_result_markdown",
        "build_agents_last_exam_local_launch_packet(",
        "build_agents_last_exam_local_exact_dry_run_result(",
        'if args.benchmark_command == "ale-local-launch-packet":',
        'if args.benchmark_command == "ale-local-exact-dry-run-result":',
    ):
        if marker in ale_source:
            raise AssertionError(f"{marker} leaked back into agents_last_exam.py")
        assert_contains(launch_dry_run_source, marker)
    for marker in (
        "def render_agents_last_exam_local_runner_readiness_markdown",
        "def render_agents_last_exam_local_source_readiness_markdown",
        "build_agents_last_exam_local_runner_readiness(",
        "build_agents_last_exam_local_source_readiness(",
        'if args.benchmark_command == "ale-local-runner-readiness":',
        'if args.benchmark_command == "ale-local-source-readiness":',
    ):
        if marker in ale_source:
            raise AssertionError(f"{marker} leaked back into agents_last_exam.py")
        assert_contains(runner_source_source, marker)
    for marker in (
        "def render_agents_last_exam_baked_task_input_readiness_markdown",
        "def render_agents_last_exam_baked_task_input_scan_markdown",
        "build_agents_last_exam_baked_task_input_readiness(",
        "build_agents_last_exam_baked_task_input_scan(",
        'if args.benchmark_command == "ale-baked-task-input-readiness":',
        'if args.benchmark_command == "ale-baked-task-input-scan":',
    ):
        if marker in ale_source:
            raise AssertionError(f"{marker} leaked back into agents_last_exam.py")
        assert_contains(baked_input_source, marker)
    for marker in (
        "def render_agents_last_exam_task_material_readiness_markdown",
        "def render_agents_last_exam_candidate_task_data_scan_markdown",
        "build_agents_last_exam_task_material_readiness(",
        "build_agents_last_exam_candidate_task_data_scan(",
        'if args.benchmark_command == "ale-task-material-readiness":',
        'if args.benchmark_command == "ale-candidate-task-data-scan":',
    ):
        if marker in ale_source:
            raise AssertionError(f"{marker} leaked back into agents_last_exam.py")
        assert_contains(task_material_source, marker)

    help_result = run_cli("benchmark", "ale-validation-run-gate", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--task-material-readiness-json")
    assert_contains(help_result.stdout, "--leaderboard-enabled")

    preflight_result = run_cli(
        "benchmark",
        "ale-local-preflight",
        "--no-docker-probe",
        "--format",
        "json",
    )
    if preflight_result.returncode != 0:
        raise AssertionError(preflight_result.stderr or preflight_result.stdout)
    preflight_payload = json.loads(preflight_result.stdout)
    if preflight_payload.get("ok") is not True:
        raise AssertionError(preflight_payload)
    boundary = preflight_payload["boundary"]
    if boundary.get("no_upload") is not True:
        raise AssertionError(preflight_payload)
    if boundary.get("submit_eligible") is not False:
        raise AssertionError(preflight_payload)

    host_route_result = run_cli(
        "benchmark",
        "ale-host-codex-cli-route",
        "--assume-codex-binary-available",
        "--codex-version-text",
        "codex-smoke",
        "--operator-authorized-host-codex-auth",
        "--format",
        "json",
    )
    if host_route_result.returncode != 0:
        raise AssertionError(host_route_result.stderr or host_route_result.stdout)
    host_route_payload = json.loads(host_route_result.stdout)
    if host_route_payload.get("ok") is not True:
        raise AssertionError(host_route_payload)
    if host_route_payload["host_auth"].get("credential_values_recorded") is not False:
        raise AssertionError(host_route_payload)
    if host_route_payload["boundary"].get("local_paths_recorded") is not False:
        raise AssertionError(host_route_payload)

    baked_input_result = run_cli(
        "benchmark",
        "ale-baked-task-input-readiness",
        "--selected-task-id",
        "demo/task",
        "--no-docker-run",
        "--format",
        "json",
    )
    if baked_input_result.returncode != 0:
        raise AssertionError(baked_input_result.stderr or baked_input_result.stdout)
    baked_input_payload = json.loads(baked_input_result.stdout)
    if baked_input_payload.get("ok") is not True:
        raise AssertionError(baked_input_payload)
    if baked_input_payload["boundary"].get("task_data_content_read") is not False:
        raise AssertionError(baked_input_payload)

    task_material_result = run_cli(
        "benchmark",
        "ale-task-material-readiness",
        "--source-root",
        ".",
        "--selected-task-id",
        "demo/task",
        "--format",
        "json",
    )
    if task_material_result.returncode != 0:
        raise AssertionError(
            task_material_result.stderr or task_material_result.stdout
        )
    task_material_payload = json.loads(task_material_result.stdout)
    if task_material_payload.get("ok") is not True:
        raise AssertionError(task_material_payload)
    if task_material_payload["boundary"].get("task_body_read") is not False:
        raise AssertionError(task_material_payload)

    candidate_scan_result = run_cli(
        "benchmark",
        "ale-candidate-task-data-scan",
        "--source-root",
        ".",
        "--format",
        "json",
    )
    if candidate_scan_result.returncode != 0:
        raise AssertionError(candidate_scan_result.stderr or candidate_scan_result.stdout)
    candidate_scan_payload = json.loads(candidate_scan_result.stdout)
    if candidate_scan_payload.get("ok") is not True:
        raise AssertionError(candidate_scan_payload)
    if candidate_scan_payload["boundary"].get("task_config_line_scan") is not True:
        raise AssertionError(candidate_scan_payload)

    launch_packet_result = run_cli(
        "benchmark",
        "ale-local-launch-packet",
        "--source-root",
        ".",
        "--experiment-spec",
        "examples/smoke.json",
        "--selected-task-id",
        "demo/task",
        "--no-docker-probe",
        "--format",
        "json",
    )
    if launch_packet_result.returncode != 0:
        raise AssertionError(launch_packet_result.stderr or launch_packet_result.stdout)
    launch_packet_payload = json.loads(launch_packet_result.stdout)
    if launch_packet_payload.get("ok") is not True:
        raise AssertionError(launch_packet_payload)
    launch_boundary = launch_packet_payload.get("boundary") or {}
    if launch_boundary.get("container_started") is not False:
        raise AssertionError(launch_packet_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        stdout_file = Path(temp_dir) / "dry-run.txt"
        stdout_file.write_text(
            "\n".join(
                [
                    "experiment: smoke",
                    "environment: local (docker->host)",
                    "concurrency: 1",
                    "units (1):",
                    "host_codex_gpt55_xhigh demo__task smoke",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        exact_dry_run_result = run_cli(
            "benchmark",
            "ale-local-exact-dry-run-result",
            "--stdout-file",
            str(stdout_file),
            "--exit-code",
            "0",
            "--expected-task-id",
            "demo/task",
            "--expected-agent-id",
            "host_codex_gpt55_xhigh",
            "--format",
            "json",
        )
    if exact_dry_run_result.returncode != 0:
        raise AssertionError(
            exact_dry_run_result.stderr or exact_dry_run_result.stdout
        )
    exact_dry_run_payload = json.loads(exact_dry_run_result.stdout)
    if exact_dry_run_payload.get("ok") is not True:
        raise AssertionError(exact_dry_run_payload)
    if exact_dry_run_payload["boundary"].get("raw_stdout_recorded") is not False:
        raise AssertionError(exact_dry_run_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        missing_gate = Path(temp_dir) / "missing-gate.json"
        gate_result = run_cli(
            "benchmark",
            "ale-validation-run-gate",
            "--selected-task-id",
            "demo/task",
            "--validation-hypothesis",
            "smoke",
            "--task-material-readiness-json",
            str(missing_gate),
            "--host-codex-no-task-e2e-json",
            str(missing_gate),
            "--exact-dry-run-json",
            str(missing_gate),
            "--format",
            "json",
        )
    if gate_result.returncode != 1:
        raise AssertionError(
            f"expected validation gate failure, got {gate_result.returncode}:\n"
            f"stdout={gate_result.stdout}\nstderr={gate_result.stderr}"
        )
    gate_payload = json.loads(gate_result.stdout)
    if gate_payload.get("ok") is not False:
        raise AssertionError(gate_payload)
    if gate_payload.get("error_type") != "FileNotFoundError":
        raise AssertionError(gate_payload)

    print("cli-agents-last-exam-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
