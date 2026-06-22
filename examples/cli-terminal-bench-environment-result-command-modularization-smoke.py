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
    review_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_review_lifecycle.py"
    ).read_text(encoding="utf-8")
    module_source = (
        ROOT / "loopx" / "cli_commands" / "terminal_bench_environment_result.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "benchmark_post_launch_parser = benchmark_sub.add_parser",
        "benchmark_environment_setup_gate_parser = benchmark_sub.add_parser",
        "benchmark_worker_materialization_probe_launch_parser = benchmark_sub.add_parser",
        "def render_terminal_bench_post_launch_materialization_markdown",
        "build_terminal_bench_environment_setup_probe_gate(",
        "launch_terminal_bench_case_run(",
        'if args.benchmark_command == "launch-terminal-bench-run":',
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    if "render_terminal_bench_environment_setup_gate_markdown" in review_source:
        raise AssertionError("Terminal-Bench environment renderers leaked into review lifecycle module")
    assert_contains(
        cli_source,
        "register_terminal_bench_environment_result_commands(benchmark_sub, add_subcommand_format)",
    )
    assert_contains(cli_source, "handle_terminal_bench_environment_result_command(")
    assert_contains(init_source, "register_terminal_bench_environment_result_commands")
    assert_contains(init_source, "handle_terminal_bench_environment_result_command")
    assert_contains(module_source, "TERMINAL_BENCH_ENVIRONMENT_RESULT_COMMANDS")
    assert_contains(module_source, "launch-terminal-bench-run")
    assert_contains(module_source, "resume-terminal-bench-job")

    help_result = run_cli("benchmark", "launch-terminal-bench-run", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--codex-install-strategy")
    assert_contains(help_result.stdout, "--resume-after-materialization")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        summarize_result = run_cli(
            "benchmark",
            "summarize-post-launch",
            "terminal-bench",
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--format",
            "json",
        )
        if summarize_result.returncode != 0:
            raise AssertionError(summarize_result.stderr or summarize_result.stdout)
        summarize_payload = payload_from(summarize_result)
        if summarize_payload.get("ok") is not True:
            raise AssertionError(summarize_payload)
        if summarize_payload["read_boundary"].get("raw_logs_read") is not False:
            raise AssertionError(summarize_payload)
        if summarize_payload["read_boundary"].get("upload_invoked") is not False:
            raise AssertionError(summarize_payload)

        post_launch_json = json.dumps(
            {
                "schema_version": "terminal_bench_post_launch_materialization_v0",
                "ready_for_launch_state": True,
                "ready_for_compact_result_ingest": False,
                "ready_for_compact_failure_marker": True,
                "external_handle_terminal": True,
                "trial_result_present_count": 0,
            }
        )
        finalization_result = run_cli(
            "benchmark",
            "result-finalization-gate",
            "terminal-bench",
            "--post-launch-json",
            "-",
            "--format",
            "json",
            input_text=post_launch_json,
        )
        if finalization_result.returncode != 0:
            raise AssertionError(finalization_result.stderr or finalization_result.stdout)
        finalization_payload = payload_from(finalization_result)
        if finalization_payload.get("ok") is not True:
            raise AssertionError(finalization_payload)
        if finalization_payload["read_boundary"].get("compact_only") is not True:
            raise AssertionError(finalization_payload)
        if finalization_payload["read_boundary"].get("upload_invoked") is not False:
            raise AssertionError(finalization_payload)

        worker_launch_result = run_cli(
            "benchmark",
            "launch-worker-materialization-probe",
            "terminal-bench",
            "--run-root",
            str(temp_root / "worker-run"),
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--format",
            "json",
        )
        if worker_launch_result.returncode != 0:
            raise AssertionError(worker_launch_result.stderr or worker_launch_result.stdout)
        worker_payload = payload_from(worker_launch_result)
        if worker_payload.get("dry_run") is not True:
            raise AssertionError(worker_payload)
        if worker_payload.get("process_started") is not False:
            raise AssertionError(worker_payload)
        if worker_payload["boundary"].get("task_solver_invoked_by_probe") is not False:
            raise AssertionError(worker_payload)
        if worker_payload["boundary"].get("upload_invoked") is not False:
            raise AssertionError(worker_payload)

        case_launch_result = run_cli(
            "benchmark",
            "launch-terminal-bench-run",
            "terminal-bench",
            "--run-root",
            str(temp_root / "case-run"),
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--format",
            "json",
        )
        if case_launch_result.returncode != 0:
            raise AssertionError(case_launch_result.stderr or case_launch_result.stdout)
        case_payload = payload_from(case_launch_result)
        if case_payload.get("dry_run") is not True:
            raise AssertionError(case_payload)
        if case_payload.get("process_started") is not False:
            raise AssertionError(case_payload)
        if case_payload["boundary"].get("task_solver_invoked") is not False:
            raise AssertionError(case_payload)
        if case_payload["boundary"].get("upload_invoked") is not False:
            raise AssertionError(case_payload)

        invalid_gate = temp_root / "invalid-environment-gate.json"
        invalid_gate.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_environment_setup_probe_gate_v0",
                    "environment_setup_probe_allowed": True,
                    "probe_contract": {"agent": "not-nop"},
                }
            ),
            encoding="utf-8",
        )
        environment_launch_result = run_cli(
            "benchmark",
            "launch-environment-setup-probe",
            "terminal-bench",
            "--gate-json",
            str(invalid_gate),
            "--run-root",
            str(temp_root / "environment-run"),
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--format",
            "json",
        )
        if environment_launch_result.returncode != 1:
            raise AssertionError(
                f"expected environment launch failure, got {environment_launch_result.returncode}:\n"
                f"stdout={environment_launch_result.stdout}\nstderr={environment_launch_result.stderr}"
            )
        environment_launch_payload = payload_from(environment_launch_result)
        if environment_launch_payload.get("ok") is not False:
            raise AssertionError(environment_launch_payload)
        if environment_launch_payload["boundary"].get("codex_invoked") is not False:
            raise AssertionError(environment_launch_payload)
        if environment_launch_payload["boundary"].get("upload_invoked") is not False:
            raise AssertionError(environment_launch_payload)

        resume_result = run_cli(
            "benchmark",
            "resume-terminal-bench-job",
            "terminal-bench",
            "--run-root",
            str(temp_root / "resume-run"),
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--job-name",
            "smoke-job",
            "--format",
            "json",
        )
        if resume_result.returncode != 0:
            raise AssertionError(resume_result.stderr or resume_result.stdout)
        resume_payload = payload_from(resume_result)
        if resume_payload.get("dry_run") is not True:
            raise AssertionError(resume_payload)
        if resume_payload["boundary"].get("resume_invoked") is not False:
            raise AssertionError(resume_payload)
        if resume_payload["boundary"].get("upload_invoked") is not False:
            raise AssertionError(resume_payload)

        poll_result = run_cli(
            "benchmark",
            "poll-worker-materialization-probe",
            "terminal-bench",
            "--run-root",
            str(temp_root / "worker-run"),
            "--jobs-dir",
            str(temp_root / "jobs"),
            "--job-name",
            "smoke-job",
            "--format",
            "json",
        )
        if poll_result.returncode != 0:
            raise AssertionError(poll_result.stderr or poll_result.stdout)
        poll_payload = payload_from(poll_result)
        if poll_payload["boundary"].get("command_line_read") is not False:
            raise AssertionError(poll_payload)
        if poll_payload["boundary"].get("upload_invoked") is not False:
            raise AssertionError(poll_payload)

        missing_run = temp_root / "missing-run.json"
        setup_gate_result = run_cli(
            "benchmark",
            "environment-setup-gate",
            "terminal-bench",
            "--benchmark-run-json",
            str(missing_run),
            "--format",
            "json",
        )
    if setup_gate_result.returncode != 1:
        raise AssertionError(
            f"expected environment setup gate failure, got {setup_gate_result.returncode}:\n"
            f"stdout={setup_gate_result.stdout}\nstderr={setup_gate_result.stderr}"
        )
    setup_gate_payload = payload_from(setup_gate_result)
    if setup_gate_payload.get("ok") is not False:
        raise AssertionError(setup_gate_payload)
    if setup_gate_payload["read_boundary"].get("raw_logs_read") is not False:
        raise AssertionError(setup_gate_payload)
    if setup_gate_payload["read_boundary"].get("upload_invoked") is not False:
        raise AssertionError(setup_gate_payload)

    print("cli-terminal-bench-environment-result-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
