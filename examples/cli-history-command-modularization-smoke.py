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
    history_source = (ROOT / "loopx" / "cli_commands" / "history.py").read_text(
        encoding="utf-8"
    )

    if "history_parser = sub.add_parser" in cli_source:
        raise AssertionError("history parser registration leaked back into loopx/cli.py")
    assert_contains(cli_source, "register_history_command(sub)")
    assert_contains(cli_source, "handle_history_command(")
    assert_contains(init_source, "register_history_command")
    assert_contains(init_source, "handle_history_command")
    assert_contains(history_source, "append_benchmark_run_rollout_event")
    assert_contains(history_source, "render_index_duplicate_repair_markdown")
    assert_contains(history_source, "build_agents_last_exam_result_benchmark_report")

    help_result = run_cli("history", "--help")
    if help_result.returncode != 0:
        raise AssertionError(help_result.stderr or help_result.stdout)
    assert_contains(help_result.stdout, "append-benchmark-run")
    assert_contains(help_result.stdout, "append-agents-last-exam-result-report")
    assert_contains(help_result.stdout, "repair-index-duplicates")
    assert_contains(help_result.stdout, "rebuild-index-collisions")
    assert_contains(help_result.stdout, "--active-user-pilot-json")

    with tempfile.TemporaryDirectory() as temp_dir:
        missing_registry = Path(temp_dir) / "missing-registry.json"
        error_result = run_cli(
            "--format",
            "json",
            "--registry",
            str(missing_registry),
            "history",
            "append-benchmark-run",
            "--goal-id",
            "history-modular-smoke",
            "--dry-run",
        )
    if error_result.returncode != 1:
        raise AssertionError(
            f"expected validation failure, got {error_result.returncode}:\n"
            f"stdout={error_result.stdout}\nstderr={error_result.stderr}"
        )
    payload = json.loads(error_result.stdout)
    if payload.get("ok") is not False:
        raise AssertionError(payload)
    assert_contains(str(payload.get("error")), "requires --benchmark-run-json")

    print("cli-history-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
