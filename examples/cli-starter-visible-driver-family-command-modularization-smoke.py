#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "loopx" / "cli_commands" / "starter.py"
VISIBLE_COMMON = ROOT / "loopx" / "cli_commands" / "starter_visible_common.py"
VISIBLE_DRIVER = ROOT / "loopx" / "cli_commands" / "starter_visible_driver.py"
VISIBLE_PILOT = ROOT / "loopx" / "cli_commands" / "starter_visible_pilot.py"
RUNTIME_IDLE = ROOT / "loopx" / "cli_commands" / "starter_runtime_idle.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"
VISIBLE_HELP_FIXTURE = (
    ROOT / "examples" / "fixtures" / "codex-cli-visible-proof" / "codex-visible-resume-help.public.json"
)
VISIBLE_PROOF_FIXTURE = (
    ROOT / "examples" / "fixtures" / "codex-cli-visible-proof" / "visible-resume-proof.public.json"
)


VISIBLE_PILOT_COMMANDS = {
    "codex-cli-one-message-loop-pilot": ["--proof-fixture", "--allow-headless-fallback"],
    "codex-cli-visible-local-driver-pilot": ["--idle-fixture", "--allow-headless-fallback"],
    "codex-cli-bounded-visible-pilot-adapter": ["--first-response-fixture", "--idle-fixture"],
    "codex-cli-visible-first-response-capture-plan": ["--first-response-path", "--idle-path"],
    "codex-cli-visible-attach-acceptance": ["--proof-fixture", "--idle-fixture"],
}
VISIBLE_DRIVER_COMMANDS = {
    "codex-cli-visible-driver-plan": ["--fixture", "--codex-bin"],
    "codex-cli-local-driver-plan": ["--fixture", "--codex-bin"],
    "codex-cli-visible-driver-run": ["--proof-fixture", "--allow-headless-fallback"],
}


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
    visible_common_source = VISIBLE_COMMON.read_text(encoding="utf-8")
    visible_driver_source = VISIBLE_DRIVER.read_text(encoding="utf-8")
    visible_pilot_source = VISIBLE_PILOT.read_text(encoding="utf-8")
    runtime_idle_source = RUNTIME_IDLE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_starter_markers = [
        "build_codex_cli_one_message_loop_pilot(",
        "build_codex_cli_visible_local_driver_pilot(",
        "build_codex_cli_bounded_visible_pilot_adapter(",
        "build_codex_cli_visible_first_response_capture_plan(",
        "build_codex_cli_visible_attach_acceptance(",
        "build_codex_cli_visible_driver_plan(",
        "build_codex_cli_local_driver_plan(",
        "build_codex_cli_visible_driver_run_packet(",
        "def handle_codex_cli_one_message_loop_pilot_command(",
        "def handle_codex_cli_visible_local_driver_pilot_command(",
        "def handle_codex_cli_bounded_visible_pilot_adapter_command(",
        "def handle_codex_cli_visible_first_response_capture_plan_command(",
        "def handle_codex_cli_visible_attach_acceptance_command(",
        "def handle_codex_cli_visible_driver_plan_command(",
        "def handle_codex_cli_local_driver_plan_command(",
        "def handle_codex_cli_visible_driver_run_command(",
    ]
    for marker in forbidden_starter_markers:
        require(marker not in starter_source, f"visible-driver marker leaked into starter.py: {marker}")

    for marker in (
        "register_starter_visible_driver_commands(subparsers)",
        "handle_starter_visible_driver_command(args, print_payload)",
    ):
        require(marker in starter_source, f"starter.py missing visible-driver delegation marker: {marker}")

    for command in VISIBLE_PILOT_COMMANDS:
        require(command in visible_pilot_source, f"starter_visible_pilot.py missing command: {command}")
        require(command not in visible_driver_source, f"pilot command leaked into starter_visible_driver.py: {command}")
    for command in VISIBLE_DRIVER_COMMANDS:
        require(command in visible_driver_source, f"starter_visible_driver.py missing command: {command}")

    for marker in (
        "def register_starter_visible_driver_commands(",
        "def handle_starter_visible_driver_command(",
        "def handle_codex_cli_visible_driver_run_command(",
        "_VISIBLE_DRIVER_HANDLERS",
    ):
        require(marker in visible_driver_source, f"starter_visible_driver.py missing marker: {marker}")
    for marker in (
        "register_starter_visible_pilot_commands(subparsers)",
        "handle_starter_visible_pilot_command(args, print_payload)",
    ):
        require(marker in visible_driver_source, f"starter_visible_driver.py missing pilot delegation marker: {marker}")
    for marker in (
        "def register_starter_visible_pilot_commands(",
        "def handle_starter_visible_pilot_command(",
        "def handle_codex_cli_one_message_loop_pilot_command(",
        "def handle_codex_cli_visible_attach_acceptance_command(",
        "_VISIBLE_PILOT_HANDLERS",
    ):
        require(marker in visible_pilot_source, f"starter_visible_pilot.py missing marker: {marker}")

    for marker in (
        "def _add_project_arguments(",
        "def _add_codex_probe_arguments(",
        "def _add_optional_proof_fixture(",
        "def _add_headless_fallback_argument(",
    ):
        require(marker in visible_common_source, f"starter_visible_common.py missing marker: {marker}")

    for marker in (
        "def _add_runtime_idle_observation_arguments(",
        "def _load_codex_cli_runtime_idle_payload(",
        "build_codex_cli_runtime_idle_observation_payload(",
    ):
        require(marker in runtime_idle_source, f"starter_runtime_idle.py missing marker: {marker}")

    for marker in (
        "handle_starter_visible_driver_command",
        "handle_starter_visible_pilot_command",
        "register_starter_visible_driver_commands",
        "register_starter_visible_pilot_commands",
        "handle_codex_cli_visible_driver_run_command",
    ):
        require(marker in init_source, f"__init__ omitted visible-driver export: {marker}")

    require(len(visible_driver_source.splitlines()) <= 220, "starter_visible_driver.py exceeded size guard")
    require(len(visible_pilot_source.splitlines()) <= 340, "starter_visible_pilot.py exceeded size guard")


def assert_cli_surfaces() -> None:
    for command, needles in {**VISIBLE_PILOT_COMMANDS, **VISIBLE_DRIVER_COMMANDS}.items():
        help_text = require_success(run_cli(command, "--help"))
        for needle in needles:
            require(needle in help_text, f"{command} help omitted {needle}")

    capture_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-first-response-capture-plan",
            "--project",
            ".",
            "--goal-id",
            "starter-visible-driver-smoke",
        )
    )
    require(capture_payload.get("goal_id") == "starter-visible-driver-smoke", capture_payload)

    plan_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-driver-plan",
            "--project",
            ".",
            "--goal-id",
            "starter-visible-driver-smoke",
            "--fixture",
            str(VISIBLE_HELP_FIXTURE),
        )
    )
    require(plan_payload.get("driver_mode") == "visible_resume_or_remote_control_spike", plan_payload)

    run_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-driver-run",
            "--project",
            ".",
            "--goal-id",
            "starter-visible-driver-smoke",
            "--fixture",
            str(VISIBLE_HELP_FIXTURE),
            "--proof-fixture",
            str(VISIBLE_PROOF_FIXTURE),
        )
    )
    require(run_payload.get("decision") == "visible_session_turn_candidate", run_payload)
    boundary = run_payload.get("boundary")
    require(isinstance(boundary, dict), run_payload)
    require(boundary.get("runs_codex") is False, run_payload)
    require(boundary.get("mutates_codex_session") is False, run_payload)


def main() -> None:
    assert_source_shape()
    assert_cli_surfaces()
    print("cli-starter-visible-driver-family-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
