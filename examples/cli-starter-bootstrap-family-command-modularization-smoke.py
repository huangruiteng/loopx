#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "loopx" / "cli_commands" / "starter.py"
BOOTSTRAP = ROOT / "loopx" / "cli_commands" / "starter_bootstrap.py"
BOOTSTRAP_REGISTRATION = ROOT / "loopx" / "cli_commands" / "starter_bootstrap_registration.py"
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
    starter_source = STARTER.read_text(encoding="utf-8")
    bootstrap_source = BOOTSTRAP.read_text(encoding="utf-8")
    registration_source = BOOTSTRAP_REGISTRATION.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_starter_markers = [
        "DEFAULT_HANDOFF_ADAPTER_KIND",
        "build_new_project_prompt(",
        "render_new_project_prompt_markdown",
        "build_codex_cli_bootstrap_message(",
        "render_codex_cli_bootstrap_message_markdown",
        "build_codex_cli_tui_bootstrap_smoke_bundle(",
        "build_codex_cli_exec_handoff(",
        "def handle_new_project_prompt_command(",
        "def handle_codex_cli_bootstrap_message_command(",
        "def handle_codex_cli_tui_bootstrap_smoke_bundle_command(",
        "def handle_codex_cli_exec_handoff_command(",
    ]
    for marker in forbidden_starter_markers:
        require(marker not in starter_source, f"bootstrap/message marker leaked into starter.py: {marker}")

    for marker in (
        "register_starter_bootstrap_commands(subparsers)",
        "handle_starter_bootstrap_command(args, print_payload)",
    ):
        require(marker in starter_source, f"starter.py missing bootstrap delegation marker: {marker}")

    for marker in (
        "def handle_starter_bootstrap_command(",
        "def handle_new_project_prompt_command(",
        "def handle_codex_cli_bootstrap_message_command(",
        "def handle_codex_cli_tui_bootstrap_smoke_bundle_command(",
        "def handle_codex_cli_exec_handoff_command(",
        "build_new_project_prompt(",
        "build_codex_cli_exec_handoff(",
    ):
        require(marker in bootstrap_source, f"starter_bootstrap.py missing marker: {marker}")

    for marker in (
        "def register_starter_bootstrap_commands(",
        'subparsers.add_parser(\n        "agent-onboard"',
        'subparsers.add_parser(\n        "bootstrap-command-pack"',
        'subparsers.add_parser(\n        "start-goal"',
        'subparsers.add_parser(\n        "new-project-prompt"',
    ):
        require(
            marker in registration_source,
            f"starter_bootstrap_registration.py missing marker: {marker}",
        )

    for marker in (
        "handle_starter_bootstrap_command",
        "register_starter_bootstrap_commands",
        "handle_new_project_prompt_command",
        "handle_codex_cli_exec_handoff_command",
    ):
        require(marker in init_source, f"__init__ omitted bootstrap export: {marker}")


def assert_cli_surfaces() -> None:
    for command, needles in {
        "new-project-prompt": ["--goal-doc", "--adapter-status", "--write-scope"],
        "codex-cli-bootstrap-message": ["--agent-id", "--message-only"],
        "codex-cli-tui-bootstrap-smoke-bundle": ["--agent-id", "--cli-bin"],
        "codex-cli-exec-handoff": ["--codex-bin", "--cli-bin"],
    }.items():
        help_text = require_success(run_cli(command, "--help"))
        for needle in needles:
            require(needle in help_text, f"{command} help omitted {needle}")

    prompt_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "new-project-prompt",
            "--project",
            ".",
            "--goal-doc",
            "README.md",
            "--goal-id",
            "starter-bootstrap-smoke",
        )
    )
    require(prompt_payload.get("goal_id") == "starter-bootstrap-smoke", prompt_payload)

    bootstrap_text = require_success(
        run_cli(
            "codex-cli-bootstrap-message",
            "--project",
            ".",
            "--goal-id",
            "starter-bootstrap-smoke",
            "--message-only",
        )
    )
    require("loopx" in bootstrap_text, "bootstrap message lost LoopX text")

    bundle_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-tui-bootstrap-smoke-bundle",
            "--project",
            ".",
            "--goal-id",
            "starter-bootstrap-smoke",
        )
    )
    require(bundle_payload.get("goal_id") == "starter-bootstrap-smoke", bundle_payload)

    handoff_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-exec-handoff",
            "--project",
            ".",
            "--goal-id",
            "starter-bootstrap-smoke",
        )
    )
    require(handoff_payload.get("goal_id") == "starter-bootstrap-smoke", handoff_payload)


def main() -> None:
    assert_source_shape()
    assert_cli_surfaces()
    print("cli-starter-bootstrap-family-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
