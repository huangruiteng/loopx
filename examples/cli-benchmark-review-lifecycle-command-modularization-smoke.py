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
    module_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_review_lifecycle.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "benchmark_claim_review_parser = benchmark_sub.add_parser",
        "benchmark_lifecycle_state_parser = benchmark_sub.add_parser",
        "def render_benchmark_claim_review_markdown",
        "build_benchmark_claim_review(",
        'if args.benchmark_command == "review-claim":',
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    assert_contains(
        cli_source,
        "register_benchmark_review_lifecycle_commands(benchmark_sub, add_subcommand_format)",
    )
    assert_contains(cli_source, "handle_benchmark_review_lifecycle_command(")
    assert_contains(init_source, "register_benchmark_review_lifecycle_commands")
    assert_contains(init_source, "handle_benchmark_review_lifecycle_command")
    assert_contains(module_source, "BENCHMARK_REVIEW_LIFECYCLE_COMMANDS")
    assert_contains(module_source, "lifecycle-state")

    help_result = run_cli("benchmark", "review-claim", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--benchmark-comparison-json")
    assert_contains(help_result.stdout, "--benchmark-run-json")

    kwarg_result = run_cli(
        "benchmark",
        "review-adapter-kwargs",
        "--agent-kwarg",
        "loopx_smoke=1",
        "--format",
        "json",
    )
    if kwarg_result.returncode != 0:
        raise AssertionError(kwarg_result.stderr or kwarg_result.stdout)
    kwarg_payload = json.loads(kwarg_result.stdout)
    if kwarg_payload.get("ok") is not True:
        raise AssertionError(kwarg_payload)
    if kwarg_payload.get("clean") is not False:
        raise AssertionError(kwarg_payload)
    if kwarg_payload["claim_boundary"].get("kwarg_values_recorded") is not False:
        raise AssertionError(kwarg_payload)

    lifecycle_result = run_cli("benchmark", "lifecycle-state", "--format", "json")
    if lifecycle_result.returncode != 0:
        raise AssertionError(lifecycle_result.stderr or lifecycle_result.stdout)
    lifecycle_payload = json.loads(lifecycle_result.stdout)
    if lifecycle_payload.get("ok") is not True:
        raise AssertionError(lifecycle_payload)
    if lifecycle_payload.get("current_phase") != "not_started":
        raise AssertionError(lifecycle_payload)
    if lifecycle_payload["read_boundary"].get("raw_artifacts_read") is not False:
        raise AssertionError(lifecycle_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        missing_run = Path(temp_dir) / "missing-run.json"
        gate_result = run_cli(
            "benchmark",
            "attempt-learning-gate",
            "--benchmark-run-json",
            str(missing_run),
            "--format",
            "json",
        )
    if gate_result.returncode != 1:
        raise AssertionError(
            f"expected attempt-learning-gate failure, got {gate_result.returncode}:\n"
            f"stdout={gate_result.stdout}\nstderr={gate_result.stderr}"
        )
    gate_payload = json.loads(gate_result.stdout)
    if gate_payload.get("ok") is not False:
        raise AssertionError(gate_payload)
    assert_contains(str(gate_payload.get("error")), "No such file")

    print("cli-benchmark-review-lifecycle-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
