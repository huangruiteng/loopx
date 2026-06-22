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
    adapter_source = (
        ROOT / "loopx" / "cli_commands" / "terminal_bench_adapter.py"
    ).read_text(encoding="utf-8")

    leaked_markers = [
        "terminal_bench_command_adapter_parser = benchmark_sub.add_parser",
        "terminal_bench_remote_materializer_parser = benchmark_sub.add_parser",
        "terminal_bench_remote_launch_adapter_parser = benchmark_sub.add_parser",
        "def render_terminal_bench_remote_executor_command_adapter_markdown",
        "build_terminal_bench_remote_executor_command_adapter(",
    ]
    for marker in leaked_markers:
        if marker in cli_source:
            raise AssertionError(f"{marker} leaked back into loopx/cli.py")
    assert_contains(
        cli_source,
        "register_terminal_bench_adapter_commands(benchmark_sub, add_subcommand_format)",
    )
    assert_contains(cli_source, "handle_terminal_bench_adapter_command(")
    assert_contains(init_source, "register_terminal_bench_adapter_commands")
    assert_contains(init_source, "handle_terminal_bench_adapter_command")
    assert_contains(adapter_source, "TERMINAL_BENCH_ADAPTER_COMMANDS")
    assert_contains(adapter_source, "terminal-bench-remote-launch-adapter")

    help_result = run_cli("benchmark", "terminal-bench-remote-materializer", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "--local-codex-credential-sync")
    assert_contains(help_result.stdout, "--raw-material-allowed")

    adapter_result = run_cli(
        "benchmark",
        "terminal-bench-command-adapter",
        "terminal-bench",
        "--format",
        "json",
    )
    if adapter_result.returncode != 0:
        raise AssertionError(adapter_result.stderr or adapter_result.stdout)
    adapter_payload = json.loads(adapter_result.stdout)
    if adapter_payload.get("ok") is not True:
        raise AssertionError(adapter_payload)
    if adapter_payload.get("dry_run") is not True:
        raise AssertionError(adapter_payload)
    boundary = adapter_payload["command_adapter"]["boundary"]
    if boundary.get("upload_allowed") is not False:
        raise AssertionError(adapter_payload)
    if boundary.get("submit_allowed") is not False:
        raise AssertionError(adapter_payload)

    with tempfile.TemporaryDirectory() as temp_dir:
        missing_request = Path(temp_dir) / "missing-request.json"
        launch_result = run_cli(
            "benchmark",
            "terminal-bench-remote-launch-adapter",
            "terminal-bench",
            "--request-json",
            str(missing_request),
            "--format",
            "json",
        )
    if launch_result.returncode != 1:
        raise AssertionError(
            f"expected remote launch validation failure, got {launch_result.returncode}:\n"
            f"stdout={launch_result.stdout}\nstderr={launch_result.stderr}"
        )
    launch_payload = json.loads(launch_result.stdout)
    if launch_payload.get("ok") is not False:
        raise AssertionError(launch_payload)
    assert_contains(str(launch_payload.get("error")), "could not be read as a JSON object")

    print("cli-terminal-bench-adapter-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
