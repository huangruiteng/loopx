#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "loopx" / "cli.py"
STARTER_MODULE = ROOT / "loopx" / "cli_commands" / "starter.py"
VISIBLE_DRIVER_MODULE = ROOT / "loopx" / "cli_commands" / "starter_visible_driver.py"
SCHEDULER_MODULE = ROOT / "loopx" / "cli_commands" / "starter_scheduler.py"
SESSION_RUNTIME_MODULE = ROOT / "loopx" / "cli_commands" / "starter_session_runtime.py"
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
    cli_source = CLI.read_text(encoding="utf-8")
    starter_source = STARTER_MODULE.read_text(encoding="utf-8")
    visible_driver_source = VISIBLE_DRIVER_MODULE.read_text(encoding="utf-8")
    scheduler_source = SCHEDULER_MODULE.read_text(encoding="utf-8")
    session_runtime_source = SESSION_RUNTIME_MODULE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    starter_commands = [
        "new-project-prompt",
        "codex-cli-bootstrap-message",
        "codex-cli-tui-bootstrap-smoke-bundle",
        "codex-cli-one-message-loop-pilot",
        "codex-cli-visible-local-driver-pilot",
        "codex-cli-bounded-visible-pilot-adapter",
        "codex-cli-visible-first-response-capture-plan",
        "codex-cli-visible-attach-acceptance",
        "codex-cli-exec-handoff",
        "codex-cli-session-probe",
        "codex-cli-visible-driver-plan",
        "codex-cli-local-driver-plan",
        "codex-cli-visible-driver-run",
        "codex-cli-local-scheduler-tick",
        "codex-cli-local-scheduler-exec",
        "codex-cli-visible-session-proof",
        "codex-cli-runtime-idle-detector",
        "demo",
    ]
    for command in starter_commands:
        marker = f'if args.command == "{command}":'
        require(marker not in cli_source, f"starter dispatch branch leaked into cli.py: {marker}")

    forbidden_handler_markers = [
        "handle_new_project_prompt_command(",
        "handle_codex_cli_bootstrap_message_command(",
        "handle_codex_cli_visible_driver_run_command(",
        "handle_codex_cli_local_scheduler_exec_command(",
        "handle_demo_command(",
    ]
    for marker in forbidden_handler_markers:
        require(marker not in cli_source, f"starter handler marker leaked into cli.py: {marker}")

    require("register_starter_commands(sub)" in cli_source, "cli.py did not register starter commands")
    require("handle_starter_command(args, print_payload)" in cli_source, "cli.py did not call starter dispatcher")
    require("def handle_starter_command(" in starter_source, "starter module omitted dispatcher")
    require(
        "register_starter_visible_driver_commands(subparsers)" in starter_source,
        "starter module omitted visible-driver registration delegation",
    )
    require(
        "handle_starter_visible_driver_command(args, print_payload)" in starter_source,
        "starter module omitted visible-driver dispatch delegation",
    )
    require(
        "register_starter_session_runtime_commands(subparsers)" in starter_source,
        "starter module omitted session-runtime registration delegation",
    )
    require(
        "handle_starter_session_runtime_command(args, print_payload)" in starter_source,
        "starter module omitted session-runtime dispatch delegation",
    )
    require(
        "register_starter_scheduler_commands(subparsers)" in starter_source,
        "starter module omitted scheduler registration delegation",
    )
    require(
        "handle_starter_scheduler_command(args, print_payload)" in starter_source,
        "starter module omitted scheduler dispatch delegation",
    )
    require(
        '"codex-cli-visible-driver-run": handle_codex_cli_visible_driver_run_command' in visible_driver_source,
        "visible-driver module omitted visible driver run dispatch",
    )
    require(
        '"codex-cli-local-scheduler-exec": handle_codex_cli_local_scheduler_exec_command' in scheduler_source,
        "scheduler module omitted local scheduler exec dispatch",
    )
    require(
        '"codex-cli-runtime-idle-detector": handle_codex_cli_runtime_idle_detector_command' in session_runtime_source,
        "session-runtime module omitted runtime idle dispatch",
    )
    require('str(getattr(args, "command", "")) == "demo"' in starter_source, "starter dispatcher omitted demo")
    require("handle_starter_command" in init_source, "__init__ omitted starter dispatcher export")


def assert_cli_surfaces() -> None:
    help_expectations = {
        "new-project-prompt": ["--goal-doc", "--write-scope"],
        "codex-cli-bootstrap-message": ["--agent-id", "--message-only"],
        "codex-cli-visible-driver-run": ["--proof-fixture", "--allow-headless-fallback"],
        "codex-cli-local-scheduler-exec": ["--guard-checked", "--candidate-command-prefix"],
        "demo": ["--user-todo", "--agent-todo"],
    }
    for command, needles in help_expectations.items():
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
            "starter-dispatch-smoke",
        )
    )
    require(prompt_payload.get("goal_id") == "starter-dispatch-smoke", prompt_payload)

    bootstrap_text = require_success(
        run_cli(
            "codex-cli-bootstrap-message",
            "--project",
            ".",
            "--goal-id",
            "starter-dispatch-smoke",
            "--message-only",
        )
    )
    require("loopx" in bootstrap_text, "message-only bootstrap output lost LoopX command text")

    capture_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-first-response-capture-plan",
            "--project",
            ".",
            "--goal-id",
            "starter-dispatch-smoke",
        )
    )
    require(capture_payload.get("goal_id") == "starter-dispatch-smoke", capture_payload)

    handoff_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-exec-handoff",
            "--project",
            ".",
            "--goal-id",
            "starter-dispatch-smoke",
        )
    )
    require(handoff_payload.get("goal_id") == "starter-dispatch-smoke", handoff_payload)


def main() -> None:
    assert_source_shape()
    assert_cli_surfaces()
    print("cli-starter-dispatch-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
