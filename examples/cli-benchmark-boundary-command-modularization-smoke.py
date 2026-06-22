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
    boundary_source = (
        ROOT / "loopx" / "cli_commands" / "benchmark_boundary.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "benchmark_artifact_filter_parser = benchmark_sub.add_parser",
        "benchmark_candidate_source_parser = benchmark_sub.add_parser",
        "split_control_execution_parser = benchmark_sub.add_parser",
        "def render_benchmark_artifact_path_filter_markdown",
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    assert_contains(cli_source, "register_benchmark_boundary_commands(benchmark_sub, add_subcommand_format)")
    assert_contains(cli_source, "handle_benchmark_boundary_command(")
    assert_contains(init_source, "register_benchmark_boundary_commands")
    assert_contains(init_source, "handle_benchmark_boundary_command")
    assert_contains(boundary_source, "BENCHMARK_BOUNDARY_COMMANDS")
    assert_contains(boundary_source, "split-control-execution-seam")

    help_result = run_cli("benchmark", "classify-artifacts", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--adapter-kind")
    assert_contains(help_result.stdout, "--allow-public-filename")

    classify_result = run_cli(
        "benchmark",
        "classify-artifacts",
        "benchmark_run.compact.json",
        "--format",
        "json",
    )
    if classify_result.returncode != 0:
        raise AssertionError(classify_result.stderr or classify_result.stdout)
    classify_payload = json.loads(classify_result.stdout)
    if classify_payload.get("path_recorded") is not False:
        raise AssertionError(classify_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        missing_readiness = Path(temp_dir) / "missing-readiness.json"
        seam_result = run_cli(
            "benchmark",
            "split-control-execution-seam",
            "--readiness-json",
            str(missing_readiness),
            "--format",
            "json",
        )
    if seam_result.returncode != 1:
        raise AssertionError(
            f"expected split-control validation failure, got {seam_result.returncode}:\n"
            f"stdout={seam_result.stdout}\nstderr={seam_result.stderr}"
        )
    seam_payload = json.loads(seam_result.stdout)
    if seam_payload.get("ok") is not False:
        raise AssertionError(seam_payload)
    assert_contains(str(seam_payload.get("error")), "No such file")

    print("cli-benchmark-boundary-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
