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
        "benchmark_baseline_gate_parser = benchmark_sub.add_parser",
        "benchmark_claim_review_parser = benchmark_sub.add_parser",
        "benchmark_lifecycle_state_parser = benchmark_sub.add_parser",
        "benchmark_runner_invariant_parser = benchmark_sub.add_parser",
        "benchmark_verifier_attribution_parser = benchmark_sub.add_parser",
        "def render_benchmark_claim_review_markdown",
        "def render_benchmark_baseline_failure_gate_markdown",
        "build_benchmark_baseline_failure_gate_comparison(",
        "build_benchmark_claim_review(",
        "build_benchmark_runner_invariant_review(",
        "build_benchmark_verifier_attribution_review(",
        'if args.benchmark_command == "baseline-failure-gate":',
        'if args.benchmark_command == "review-claim":',
        'if args.benchmark_command == "review-runner-invariants":',
        'if args.benchmark_command == "review-verifier-attribution":',
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
    assert_contains(module_source, "baseline-failure-gate")
    assert_contains(module_source, "lifecycle-state")
    assert_contains(module_source, "review-runner-invariants")
    assert_contains(module_source, "review-verifier-attribution")

    help_result = run_cli("benchmark", "review-claim", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--benchmark-comparison-json")
    assert_contains(help_result.stdout, "--benchmark-run-json")

    baseline_help = run_cli("benchmark", "baseline-failure-gate", "--help")
    if baseline_help.returncode != 0:
        raise AssertionError(baseline_help.stderr or baseline_help.stdout)
    assert_contains(baseline_help.stdout, "--baseline-result-json")
    assert_contains(baseline_help.stdout, "--trace-publicness-verified")

    verifier_help = run_cli("benchmark", "review-verifier-attribution", "--help")
    if verifier_help.returncode != 0:
        raise AssertionError(verifier_help.stderr or verifier_help.stdout)
    assert_contains(verifier_help.stdout, "--benchmark-run-json")

    runner_help = run_cli("benchmark", "review-runner-invariants", "--help")
    if runner_help.returncode != 0:
        raise AssertionError(runner_help.stderr or runner_help.stdout)
    assert_contains(runner_help.stdout, "--expect-compact-only")

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

    generated_run_result = run_cli(
        "--format",
        "json",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        "loopx-meta",
        "--no-global-sync",
    )
    if generated_run_result.returncode != 0:
        raise AssertionError(generated_run_result.stderr or generated_run_result.stdout)
    benchmark_run = json.loads(generated_run_result.stdout)["benchmark_run"]
    with tempfile.TemporaryDirectory() as temp_dir:
        run_json = Path(temp_dir) / "benchmark-run.json"
        run_json.write_text(json.dumps(benchmark_run), encoding="utf-8")

        runner_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "review-runner-invariants",
            "--benchmark-run-json",
            str(run_json),
        )
        if runner_result.returncode != 0:
            raise AssertionError(runner_result.stderr or runner_result.stdout)
        runner_payload = json.loads(runner_result.stdout)
        if runner_payload.get("ok") is not True:
            raise AssertionError(runner_payload)
        if runner_payload.get("schema_version") != "benchmark_runner_invariant_review_v0":
            raise AssertionError(runner_payload)
        if runner_payload["read_boundary"].get("raw_artifacts_read") is not False:
            raise AssertionError(runner_payload)

        verifier_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "review-verifier-attribution",
            "--benchmark-run-json",
            str(run_json),
        )
        if verifier_result.returncode != 0:
            raise AssertionError(verifier_result.stderr or verifier_result.stdout)
        verifier_payload = json.loads(verifier_result.stdout)
        if verifier_payload.get("ok") is not True:
            raise AssertionError(verifier_payload)
        if verifier_payload.get("reviewed_run_count") != 1:
            raise AssertionError(verifier_payload)

        baseline_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "baseline-failure-gate",
            "--benchmark-id",
            "terminal-bench@2.0",
            "--baseline-result-json",
            str(run_json),
            "--control-plane-addressable",
            "--same-task-semantics",
            "--same-runner-protocol",
            "--trace-publicness-verified",
            "--no-global-sync",
        )
        if baseline_result.returncode != 0:
            raise AssertionError(baseline_result.stderr or baseline_result.stdout)
        baseline_payload = json.loads(baseline_result.stdout)
        if baseline_payload.get("ok") is not True:
            raise AssertionError(baseline_payload)
        if baseline_payload.get("appended") is not False:
            raise AssertionError(baseline_payload)
        if baseline_payload["baseline_gate_cli"].get("source") != "compact_benchmark_run_v0":
            raise AssertionError(baseline_payload)
        if str(run_json) in json.dumps(baseline_payload):
            raise AssertionError("baseline gate payload leaked the local fixture path")

    print("cli-benchmark-review-lifecycle-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
