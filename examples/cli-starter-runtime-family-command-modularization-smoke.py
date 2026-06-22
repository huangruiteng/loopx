#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "loopx" / "cli_commands" / "starter.py"
SCHEDULER = ROOT / "loopx" / "cli_commands" / "starter_scheduler.py"
SESSION_RUNTIME = ROOT / "loopx" / "cli_commands" / "starter_session_runtime.py"
RUNTIME_IDLE = ROOT / "loopx" / "cli_commands" / "starter_runtime_idle.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"
VISIBLE_HELP_FIXTURE = (
    ROOT / "examples" / "fixtures" / "codex-cli-visible-proof" / "codex-visible-resume-help.public.json"
)
VISIBLE_PROOF_FIXTURE = (
    ROOT / "examples" / "fixtures" / "codex-cli-visible-proof" / "visible-resume-proof.public.json"
)
RUNTIME_IDLE_FIXTURE = (
    ROOT / "examples" / "fixtures" / "codex-cli-visible-proof" / "runtime-idle-visible-resume.public.json"
)


SESSION_RUNTIME_COMMANDS = {
    "codex-cli-session-probe": ["--fixture", "--codex-bin"],
    "codex-cli-visible-session-proof": ["--proof-fixture", "--cli-bin"],
    "codex-cli-runtime-idle-detector": ["--idle-fixture", "--observe-local-runtime"],
}
SCHEDULER_COMMANDS = {
    "codex-cli-local-scheduler-tick": ["--proof-fixture", "--idle-fixture", "--allow-headless-fallback"],
    "codex-cli-local-scheduler-exec": ["--guard-checked", "--candidate-command-prefix", "--executor-timeout-seconds"],
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
    scheduler_source = SCHEDULER.read_text(encoding="utf-8")
    session_runtime_source = SESSION_RUNTIME.read_text(encoding="utf-8")
    runtime_idle_source = RUNTIME_IDLE.read_text(encoding="utf-8")
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_starter_markers = [
        "codex-cli-session-probe",
        "codex-cli-local-scheduler-tick",
        "codex-cli-local-scheduler-exec",
        "codex-cli-visible-session-proof",
        "codex-cli-runtime-idle-detector",
        "def handle_codex_cli_session_probe_command(",
        "def handle_codex_cli_local_scheduler_tick_command(",
        "def handle_codex_cli_local_scheduler_exec_command(",
        "def handle_codex_cli_visible_session_proof_command(",
        "def handle_codex_cli_runtime_idle_detector_command(",
        "build_codex_cli_local_scheduler_tick(",
        "build_codex_cli_local_scheduler_executor(",
        "build_codex_cli_visible_session_proof(",
        "build_codex_cli_runtime_idle_detector(",
    ]
    for marker in forbidden_starter_markers:
        require(marker not in starter_source, f"runtime/scheduler marker leaked into starter.py: {marker}")

    for marker in (
        "register_starter_session_runtime_commands(subparsers)",
        "handle_starter_session_runtime_command(args, print_payload)",
        "register_starter_scheduler_commands(subparsers)",
        "handle_starter_scheduler_command(args, print_payload)",
    ):
        require(marker in starter_source, f"starter.py missing delegation marker: {marker}")

    for command in SESSION_RUNTIME_COMMANDS:
        require(command in session_runtime_source, f"starter_session_runtime.py missing command: {command}")
    for marker in (
        "def register_starter_session_runtime_commands(",
        "def handle_starter_session_runtime_command(",
        "_SESSION_RUNTIME_HANDLERS",
        "build_codex_cli_visible_session_proof(",
        "build_codex_cli_runtime_idle_detector(",
    ):
        require(marker in session_runtime_source, f"starter_session_runtime.py missing marker: {marker}")

    for command in SCHEDULER_COMMANDS:
        require(command in scheduler_source, f"starter_scheduler.py missing command: {command}")
    for marker in (
        "def register_starter_scheduler_commands(",
        "def handle_starter_scheduler_command(",
        "_SCHEDULER_HANDLERS",
        "build_codex_cli_local_scheduler_tick(",
        "build_codex_cli_local_scheduler_executor(",
    ):
        require(marker in scheduler_source, f"starter_scheduler.py missing marker: {marker}")

    for marker in (
        "def _add_runtime_idle_observation_arguments(",
        "def _load_codex_cli_runtime_idle_payload(",
    ):
        require(marker in runtime_idle_source, f"starter_runtime_idle.py missing marker: {marker}")

    for marker in (
        "handle_starter_scheduler_command",
        "register_starter_scheduler_commands",
        "handle_starter_session_runtime_command",
        "register_starter_session_runtime_commands",
        "handle_codex_cli_runtime_idle_detector_command",
        "handle_codex_cli_local_scheduler_exec_command",
    ):
        require(marker in init_source, f"__init__ omitted runtime/scheduler export: {marker}")


def assert_cli_surfaces() -> None:
    for command, needles in {**SESSION_RUNTIME_COMMANDS, **SCHEDULER_COMMANDS}.items():
        help_text = require_success(run_cli(command, "--help"))
        for needle in needles:
            require(needle in help_text, f"{command} help omitted {needle}")

    probe_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-session-probe",
            "--fixture",
            str(VISIBLE_HELP_FIXTURE),
        )
    )
    require(probe_payload.get("recommended_mode") == "visible_resume_or_remote_control_spike", probe_payload)

    proof_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-visible-session-proof",
            "--project",
            ".",
            "--goal-id",
            "starter-runtime-family-smoke",
            "--proof-fixture",
            str(VISIBLE_PROOF_FIXTURE),
        )
    )
    require(proof_payload.get("decision") == "visible_session_proof_passed", proof_payload)

    idle_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-runtime-idle-detector",
            "--project",
            ".",
            "--goal-id",
            "starter-runtime-family-smoke",
            "--idle-fixture",
            str(RUNTIME_IDLE_FIXTURE),
        )
    )
    require(idle_payload.get("decision") == "runtime_idle_detector_passed", idle_payload)

    scheduler_payload = require_json_success(
        run_cli(
            "--format",
            "json",
            "codex-cli-local-scheduler-exec",
            "--project",
            ".",
            "--goal-id",
            "starter-runtime-family-smoke",
            "--fixture",
            str(VISIBLE_HELP_FIXTURE),
            "--proof-fixture",
            str(VISIBLE_PROOF_FIXTURE),
            "--idle-fixture",
            str(RUNTIME_IDLE_FIXTURE),
        )
    )
    require(scheduler_payload.get("decision") == "visible_session_turn_candidate", scheduler_payload)
    boundary = scheduler_payload.get("boundary")
    require(isinstance(boundary, dict), scheduler_payload)
    require(boundary.get("runs_external_candidate") is False, scheduler_payload)
    require(boundary.get("runs_codex_candidate_possible") is False, scheduler_payload)
    require(boundary.get("requires_fresh_quota_guard_confirmation") is True, scheduler_payload)


def main() -> None:
    assert_source_shape()
    assert_cli_surfaces()
    print("cli-starter-runtime-family-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
