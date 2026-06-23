#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        text=True,
        input=input_text,
        capture_output=True,
        check=False,
    )


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected to find {needle!r} in output:\n{text}")


def payload_from(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"expected JSON stdout, got:\nstdout={result.stdout}\nstderr={result.stderr}"
        ) from exc
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


def main() -> int:
    cli_source = (ROOT / "loopx" / "cli.py").read_text(encoding="utf-8")
    init_source = (ROOT / "loopx" / "cli_commands" / "__init__.py").read_text(
        encoding="utf-8"
    )
    dispatch_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_dispatch.py"
    ).read_text(encoding="utf-8")
    module_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger.py"
    ).read_text(encoding="utf-8")
    maintenance_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger_maintenance.py"
    ).read_text(encoding="utf-8")
    case_analysis_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_run_ledger_case_analysis.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "benchmark_run_parser = benchmark_sub.add_parser",
        "benchmark_run_ledger_upsert_parser = benchmark_sub.add_parser",
        "benchmark_case_analysis_candidates_parser = benchmark_sub.add_parser",
        "def render_benchmark_run_ledger_upsert_markdown",
        "build_terminal_bench_benchmark_run(",
        "build_case_analysis_candidate_report(",
        'if args.benchmark_command == "run":',
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    assert_contains(dispatch_source, "register_benchmark_run_ledger_commands(")
    assert_contains(dispatch_source, "handle_benchmark_run_ledger_command(")
    assert_contains(init_source, "register_benchmark_run_ledger_commands")
    assert_contains(init_source, "handle_benchmark_run_ledger_command")
    assert_contains(init_source, "register_benchmark_run_ledger_case_analysis_commands")
    assert_contains(init_source, "handle_benchmark_run_ledger_case_analysis_command")
    assert_contains(init_source, "register_benchmark_run_ledger_maintenance_commands")
    assert_contains(init_source, "handle_benchmark_run_ledger_maintenance_command")
    assert_contains(module_source, "BENCHMARK_RUN_LEDGER_COMMANDS")
    assert_contains(
        module_source,
        "register_benchmark_run_ledger_case_analysis_commands(benchmark_subparsers)",
    )
    assert_contains(module_source, "handle_benchmark_run_ledger_case_analysis_command(")
    assert_contains(
        module_source,
        "register_benchmark_run_ledger_maintenance_commands(benchmark_subparsers)",
    )
    assert_contains(module_source, "handle_benchmark_run_ledger_maintenance_command(")

    ownership_markers = [
        "benchmark_run_ledger_upsert_parser = benchmark_subparsers.add_parser",
        "benchmark_run_ledger_check_parser = benchmark_subparsers.add_parser",
        "def render_benchmark_run_ledger_upsert_markdown",
        "def render_benchmark_run_ledger_check_markdown",
        'if args.benchmark_command == "run-ledger-upsert":',
        'if args.benchmark_command == "run-ledger-check":',
        "compact_benchmark_post_launch_materialization",
        "check_benchmark_run_ledger_drift(",
    ]
    for marker in ownership_markers:
        if marker in module_source:
            raise AssertionError(f"{marker} leaked back into benchmark_run_ledger.py")
        assert_contains(maintenance_source, marker)

    case_analysis_markers = [
        "benchmark_case_analysis_candidates_parser = benchmark_subparsers.add_parser",
        "def render_benchmark_case_analysis_candidates_markdown",
        'if args.benchmark_command == "case-analysis-candidates":',
        "build_case_analysis_candidate_report(",
        "apply_accepted_case_analysis_records(",
        "render_case_analysis_markdown(",
    ]
    for marker in case_analysis_markers:
        if marker in module_source:
            raise AssertionError(f"{marker} leaked back into benchmark_run_ledger.py")
        assert_contains(case_analysis_source, marker)

    help_result = run_cli("benchmark", "run", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--update-run-ledger")
    assert_contains(help_result.stdout, "--skillsbench-route")

    terminal_result = run_cli(
        "--format",
        "json",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        "loopx-meta",
        "--mode",
        "codex-goal-mode",
    )
    if terminal_result.returncode != 0:
        raise AssertionError(terminal_result.stderr or terminal_result.stdout)
    terminal_payload = payload_from(terminal_result)
    if terminal_payload.get("ok") is not True:
        raise AssertionError(terminal_payload)
    if terminal_payload.get("dry_run") is not True:
        raise AssertionError(terminal_payload)
    if terminal_payload["benchmark_cli"].get("real_runner_invoked") is not False:
        raise AssertionError(terminal_payload)
    if terminal_payload["benchmark_cli"].get("submit_eligible") is not False:
        raise AssertionError(terminal_payload)

    skillsbench_result = run_cli(
        "--format",
        "json",
        "benchmark",
        "run",
        "skillsbench",
        "--goal-id",
        "loopx-meta",
    )
    if skillsbench_result.returncode != 0:
        raise AssertionError(skillsbench_result.stderr or skillsbench_result.stdout)
    skillsbench_payload = payload_from(skillsbench_result)
    if skillsbench_payload.get("ok") is not True:
        raise AssertionError(skillsbench_payload)
    if skillsbench_payload["benchmark_cli"].get("benchmark") != "skillsbench":
        raise AssertionError(skillsbench_payload)
    if skillsbench_payload["benchmark_cli"].get("skillsbench_route") != "loopx-blind-loop-treatment":
        raise AssertionError(skillsbench_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        benchmark_run_path = temp_root / "benchmark-run.json"
        benchmark_run_path.write_text(
            json.dumps(terminal_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        parity_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "parity-check",
            "--benchmark-run-json",
            str(benchmark_run_path),
        )
        if parity_result.returncode != 0:
            raise AssertionError(parity_result.stderr or parity_result.stdout)
        parity_payload = payload_from(parity_result)
        if parity_payload.get("ok") is not True:
            raise AssertionError(parity_payload)
        parity_check = parity_payload["codex_app_parity_posthoc_check"]
        if parity_check["read_boundary"].get("raw_task_text_read") is not False:
            raise AssertionError(parity_payload)

        ledger_path = temp_root / "benchmark-run-ledger.json"
        upsert_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-upsert",
            "--benchmark-run-json",
            str(benchmark_run_path),
            "--run-ledger-path",
            str(ledger_path),
        )
        if upsert_result.returncode != 0:
            raise AssertionError(upsert_result.stderr or upsert_result.stdout)
        upsert_payload = payload_from(upsert_result)
        if upsert_payload.get("ok") is not True:
            raise AssertionError(upsert_payload)
        if upsert_payload["read_boundary"].get("raw_logs_read") is not False:
            raise AssertionError(upsert_payload)

        post_launch = {
            "schema_version": "terminal_bench_post_launch_materialization_v0",
            "checked": True,
            "ready_for_launch_state": False,
            "ready_for_compact_result_ingest": False,
            "ready_for_compact_failure_marker": True,
            "first_blocker": "smoke_failure",
            "job_name": "smoke-job",
            "external_handle_terminal": True,
            "trial_result_present_count": 0,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
        }
        post_launch_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-upsert",
            "--post-launch-json",
            "-",
            "--run-ledger-path",
            str(temp_root / "post-launch-ledger.json"),
            input_text=json.dumps(post_launch),
        )
        if post_launch_result.returncode != 0:
            raise AssertionError(post_launch_result.stderr or post_launch_result.stdout)
        post_launch_payload = payload_from(post_launch_result)
        if post_launch_payload.get("input_kind") != "terminal_bench_post_launch_materialization_v0":
            raise AssertionError(post_launch_payload)
        if post_launch_payload["read_boundary"].get("task_text_read") is not False:
            raise AssertionError(post_launch_payload)

        compact_ledger = {
            "schema_version": "benchmark_run_ledger_v0",
            "benchmarks": {
                "terminal-bench@2.0": {
                    "cases": {
                        "smoke-case": {
                            "latest_decision": {"decision": "single_arm_recorded"},
                            "runs": [{"run_id": "r1"}],
                        }
                    }
                }
            },
        }
        ledger_path.write_text(
            json.dumps(compact_ledger, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        analysis_path = temp_root / "benchmark-case-analysis.json"
        analysis_path.write_text(
            json.dumps(
                {"schema_version": "benchmark_case_analysis_v0", "cases": []},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        candidates_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "case-analysis-candidates",
            "--run-ledger-path",
            str(ledger_path),
            "--case-analysis-path",
            str(analysis_path),
            "--include-proposed-records",
        )
        if candidates_result.returncode != 0:
            raise AssertionError(candidates_result.stderr or candidates_result.stdout)
        candidates_payload = payload_from(candidates_result)
        if candidates_payload.get("ok") is not True:
            raise AssertionError(candidates_payload)
        if candidates_payload["report"].get("candidate_count") != 1:
            raise AssertionError(candidates_payload)
        if candidates_payload["read_boundary"].get("trajectory_read") is not False:
            raise AssertionError(candidates_payload)

        check_result = run_cli(
            "--format",
            "json",
            "benchmark",
            "run-ledger-check",
            "--goal-id",
            "loopx-meta",
            "--history-limit",
            "0",
            "--run-ledger-path",
            str(ledger_path),
        )
        if check_result.returncode != 0:
            raise AssertionError(check_result.stderr or check_result.stdout)
        check_payload = payload_from(check_result)
        if check_payload.get("ok") is not True:
            raise AssertionError(check_payload)
        drift = check_payload["benchmark_run_ledger_drift"]
        if drift.get("drift_detected") is not False:
            raise AssertionError(check_payload)
        if check_payload["read_boundary"].get("upload_invoked") is not False:
            raise AssertionError(check_payload)

    print("cli-benchmark-run-ledger-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
