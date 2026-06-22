#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "loopx" / "cli.py"
MODULE = REPO_ROOT / "loopx" / "cli_commands" / "agentissue_runner_flow.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise AssertionError(
            f"expected command success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def require_failure(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode == 0:
        raise AssertionError(
            f"expected command failure\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def main() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    forbidden_cli_markers = [
        "agentissue_runner_flow_parser = benchmark_sub.add_parser",
        "build_agentissue_codex_cli_runner_wrapper(",
        "materialize_agentissue_codex_cli_runner_private_script(",
        'if args.benchmark_command == "agentissue-codex-runner-flow":',
    ]
    for marker in forbidden_cli_markers:
        require(marker not in cli_source, f"cli.py still owns AgentIssue runner-flow marker: {marker}")

    required_module_markers = [
        "AGENTISSUE_RUNNER_FLOW_COMMANDS",
        "register_agentissue_runner_flow_commands",
        "handle_agentissue_runner_flow_command",
        "build_agentissue_codex_cli_runner_wrapper(",
        "materialize_agentissue_codex_cli_runner_private_script(",
    ]
    for marker in required_module_markers:
        require(marker in module_source, f"AgentIssue command module is missing marker: {marker}")

    help_text = require_success(
        run_cli("benchmark", "agentissue-codex-runner-flow", "--help")
    )
    for option in (
        "--synthetic-staging-root",
        "--execution-gate-root",
        "--target-runner-handoff-root",
        "--private-runner-root",
    ):
        require(option in help_text, f"help output omitted {option}")

    default_payload = json.loads(
        require_success(
            run_cli(
                "--format",
                "json",
                "benchmark",
                "agentissue-codex-runner-flow",
                "--goal-id",
                "loopx-meta",
                "--no-global-sync",
            )
        )
    )
    benchmark_cli = default_payload.get("benchmark_cli") or {}
    require(default_payload.get("ok") is True, "default dry-run should succeed")
    require(default_payload.get("dry_run") is True, "default invocation should dry-run")
    require(default_payload.get("appended") is False, "default dry-run should not append")
    require(benchmark_cli.get("benchmark") == "agentissue-bench", "benchmark id changed")
    require(benchmark_cli.get("real_codex_invoked") is False, "dry-run must not invoke Codex")
    require(benchmark_cli.get("real_docker_invoked") is False, "dry-run must not invoke Docker")
    require(benchmark_cli.get("submit_eligible") is False, "dry-run must not be submit eligible")
    require((default_payload.get("global_sync") or {}).get("skipped") is True, "no-global-sync should skip sync")

    with tempfile.TemporaryDirectory(prefix="loopx-agentissue-runner-flow-") as temp_root:
        staging_root = Path(temp_root) / "staging"
        synthetic_payload = json.loads(
            require_success(
                run_cli(
                    "--format",
                    "json",
                    "benchmark",
                    "agentissue-codex-runner-flow",
                    "--goal-id",
                    "loopx-meta",
                    "--synthetic-staging-root",
                    str(staging_root),
                    "--no-global-sync",
                )
            )
        )
        synthetic_cli = synthetic_payload.get("benchmark_cli") or {}
        require(synthetic_payload.get("ok") is True, "synthetic staging dry-run should succeed")
        require(synthetic_cli.get("synthetic_staging_materialized") is True, "synthetic staging flag missing")
        require(synthetic_cli.get("synthetic_staging_root_path_recorded") is False, "root path should not be public")
        require(str(staging_root) not in json.dumps(synthetic_payload), "payload leaked local staging root")

    conflict_payload = json.loads(
        require_failure(
            run_cli(
                "--format",
                "json",
                "benchmark",
                "agentissue-codex-runner-flow",
                "--goal-id",
                "loopx-meta",
                "--synthetic-staging-root",
                "one",
                "--execution-gate-root",
                "two",
                "--no-global-sync",
            )
        )
    )
    require(conflict_payload.get("ok") is False, "conflicting roots should fail")
    require("at most one root option" in str(conflict_payload.get("error")), "conflict error changed")

    print("ok: AgentIssue runner-flow CLI command is modularized")


if __name__ == "__main__":
    main()
