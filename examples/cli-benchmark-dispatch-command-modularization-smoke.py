#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fixture_support import create_minimal_goal_registry


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "loopx" / "cli.py"
DISPATCH_MODULE = ROOT / "loopx" / "cli_commands" / "benchmark_dispatch.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise AssertionError(
            f"expected success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def require_json_success(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    payload = json.loads(require_success(result))
    require(isinstance(payload, dict), "expected JSON object payload")
    require(payload.get("ok") is True, f"payload was not ok: {payload}")
    return payload


def assert_source_shape() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    dispatch_source = DISPATCH_MODULE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_cli_markers = [
        "benchmark_parser = sub.add_parser",
        "benchmark_sub = benchmark_parser.add_subparsers",
        "register_benchmark_run_ledger_commands(",
        "register_agentissue_runner_flow_commands(",
        "register_benchmark_boundary_commands(",
        "register_terminal_bench_adapter_commands(",
        "register_agents_last_exam_commands(",
        "register_benchmark_review_lifecycle_commands(",
        "register_terminal_bench_environment_result_commands(",
        "handle_agentissue_runner_flow_command(",
        "handle_benchmark_boundary_command(",
        "handle_terminal_bench_adapter_command(",
        "handle_agents_last_exam_command(",
        "handle_benchmark_review_lifecycle_command(",
        "handle_terminal_bench_environment_result_command(",
        "handle_benchmark_run_ledger_command(",
    ]
    for marker in forbidden_cli_markers:
        require(marker not in cli_source, f"benchmark dispatch marker leaked into cli.py: {marker}")

    for marker in (
        "register_benchmark_command_group(sub, add_subcommand_format)",
        "handle_benchmark_command(",
    ):
        require(marker in cli_source, f"cli.py missing benchmark dispatch marker: {marker}")

    for marker in (
        "def register_benchmark_command_group(",
        "def handle_benchmark_command(",
        "benchmark_parser = subparsers.add_parser",
        "register_benchmark_run_ledger_commands(benchmark_sub, add_subcommand_format)",
        "register_agentissue_runner_flow_commands(benchmark_sub, add_subcommand_format)",
        "register_benchmark_boundary_commands(benchmark_sub, add_subcommand_format)",
        "register_terminal_bench_adapter_commands(benchmark_sub, add_subcommand_format)",
        "register_agents_last_exam_commands(benchmark_sub, add_subcommand_format)",
        "register_benchmark_review_lifecycle_commands(benchmark_sub, add_subcommand_format)",
        "register_terminal_bench_environment_result_commands(benchmark_sub, add_subcommand_format)",
        "handle_benchmark_run_ledger_command(",
    ):
        require(marker in dispatch_source, f"benchmark dispatch module missing marker: {marker}")

    require("register_benchmark_command_group" in init_source, "__init__ omitted benchmark group registrar")
    require("handle_benchmark_command" in init_source, "__init__ omitted benchmark group handler")


def assert_cli_surfaces() -> None:
    registry_path, runtime_root = create_minimal_goal_registry(
        goal_id="loopx-meta",
        objective="Validate benchmark dispatch modularization.",
    )
    help_text = require_success(run_cli("benchmark", "--help"))
    for subcommand in (
        "run",
        "agentissue-codex-runner-flow",
        "classify-artifacts",
        "terminal-bench-command-adapter",
        "ale-local-preflight",
        "review-claim",
        "summarize-post-launch",
    ):
        require(subcommand in help_text, f"benchmark help omitted {subcommand}")

    run_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime_root),
            "benchmark",
            "run",
            "terminal-bench",
            "--goal-id",
            "loopx-meta",
            "--mode",
            "codex-goal-mode",
        )
    )
    require(run_payload.get("dry_run") is True, "benchmark run default should dry-run")
    require(run_payload["benchmark_cli"].get("real_runner_invoked") is False, run_payload)

    adapter_payload = require_json_success(
        run_cli(
            "benchmark",
            "terminal-bench-command-adapter",
            "terminal-bench",
            "--format",
            "json",
        )
    )
    require(adapter_payload.get("dry_run") is True, "adapter default should dry-run")
    require(adapter_payload["command_adapter"]["boundary"].get("submit_allowed") is False, adapter_payload)


def main() -> None:
    assert_source_shape()
    assert_cli_surfaces()
    print("cli-benchmark-dispatch-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
