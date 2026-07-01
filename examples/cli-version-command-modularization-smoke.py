#!/usr/bin/env python3
"""Smoke-test the low-risk version command module boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "loopx" / "cli.py"
INIT = REPO_ROOT / "loopx" / "cli_commands" / "__init__.py"
MODULE = REPO_ROOT / "loopx" / "cli_commands" / "version.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        env=env,
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


def assert_source_shape() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")

    for marker in [
        'sub.add_parser("version"',
        "def build_version_payload(",
        "def render_version_markdown(",
    ]:
        require(marker not in cli_source, f"version implementation leaked into loopx/cli.py: {marker}")
    for marker in [
        "register_version_command(sub, add_subcommand_format)",
        "handle_version_command(",
    ]:
        require(marker in cli_source, f"loopx/cli.py missing {marker}")
    for marker in [
        "handle_version_command",
        "register_version_command",
    ]:
        require(marker in init_source, f"cli_commands/__init__.py missing {marker}")
    for marker in [
        "def build_version_payload(",
        "def register_version_command(",
        "def handle_version_command(",
        "output_format(args)",
    ]:
        require(marker in module_source, f"version module missing {marker}")


def assert_version_outputs() -> None:
    legacy_flag = require_success(run_cli("--version")).strip()
    markdown = require_success(run_cli("version")).strip()
    require(legacy_flag == markdown, f"--version and version disagree: {legacy_flag!r} != {markdown!r}")
    require(markdown.startswith("loopx "), markdown)

    for args in [("--format", "json", "version"), ("version", "--format", "json")]:
        payload = json.loads(require_success(run_cli(*args)))
        require(payload["ok"] is True, str(payload))
        require(payload["schema_version"] == "loopx_version_v0", str(payload))
        require(payload["name"] == "loopx", str(payload))
        require(payload["version"] == markdown.removeprefix("loopx "), str(payload))

    help_text = require_success(run_cli("version", "--help"))
    require("--format {markdown,json}" in help_text, help_text)


def main() -> int:
    assert_source_shape()
    assert_version_outputs()
    print("cli-version-command-modularization-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
