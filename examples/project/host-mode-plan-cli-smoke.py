#!/usr/bin/env python3
"""Subprocess smoke for `loopx host-mode-plan` as the real CLI call site."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def assert_public_safe(text: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"CLI output leaked private pattern {pattern.pattern!r}")


def test_cli_selects_headless_turn_and_scopes_agent_id() -> None:
    proc = run_cli(
        "--format",
        "json",
        "host-mode-plan",
        "--goal-id",
        "host-mode-plan-cli-fixture",
        "--intent",
        "continue_without_ui",
        "--host-capability",
        "loopx_turn",
        "--host-capability",
        "typed_host_adapter",
        "--host-capability",
        "independent_validator",
        "--agent-id",
        "codex-main-control",
        "--registered-agent",
        "codex-main-control",
        "--available-capability",
        "shell",
    )
    assert proc.returncode == 0, proc.stderr
    assert_public_safe(proc.stdout)
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "host_mode_plan_v0", payload
    assert payload["mode"] == "dry_run_host_mode_selector", payload
    assert payload["selected_mode"] == "isolated_headless_turn", payload
    assert payload["selected_connector_id"] == "loopx_turn", payload
    assert payload["selected_capability_ready"] is True, payload
    command = payload["next_preview_command"]
    assert "loopx turn plan" in command, command
    assert "--host generic-cli" in command, command
    assert "--execution-mode isolated-headless" in command, command
    assert "--scheduler-owner outer_controller" in command, command
    assert "--agent-id codex-main-control" in command, command
    assert "--available-capability shell" in command, command
    assert payload["selected_missing_host_capabilities"] == [], payload
    assert payload["selected_blocking_reasons"] == [], payload
    assert payload["operator_next_steps"][0]["kind"] == "state_preview", payload
    assert any(step["kind"] == "turn_preview" for step in payload["operator_next_steps"]), payload
    assert payload["boundary"]["turn_envelope_is_authoritative_for_execution"] is True, payload


def test_cli_markdown_explains_benefits() -> None:
    proc = run_cli(
        "host-mode-plan",
        "--goal-id",
        "host-mode-plan-cli-fixture",
        "--intent",
        "watch_each_turn",
        "--host-capability",
        "visible_session",
        "--host-identity",
        "claude-code",
    )
    assert proc.returncode == 0, proc.stderr
    assert "# LoopX Host Mode Plan" in proc.stdout, proc.stdout
    assert "selected_mode: `visible_tui`" in proc.stdout, proc.stdout
    assert "host_identity: `claude-code`" in proc.stdout, proc.stdout
    assert "Why This Helps" in proc.stdout, proc.stdout
    assert "Operator Next Steps" in proc.stdout, proc.stdout


def test_cli_visible_mode_preserves_host_identity() -> None:
    for host_identity in ["codex-cli", "claude-code"]:
        proc = run_cli(
            "--format",
            "json",
            "host-mode-plan",
            "--goal-id",
            "host-mode-plan-cli-fixture",
            "--intent",
            "watch_each_turn",
            "--host-capability",
            "visible_session",
            "--host-identity",
            host_identity,
            "--agent-id",
            "codex-main-control",
            "--registered-agent",
            "codex-main-control",
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["host_identity"] == host_identity, payload
        assert payload["selected_turn_mapping"]["host"] == host_identity, payload
        assert f"--host {host_identity}" in payload["next_preview_command"], payload


def test_cli_visible_mode_fails_closed_without_registered_host() -> None:
    for host_args, expected_identity in [
        ([], None),
        (["--host-identity", "generic-cli"], "generic-cli"),
    ]:
        proc = run_cli(
            "--format",
            "json",
            "host-mode-plan",
            "--goal-id",
            "host-mode-plan-cli-fixture",
            "--intent",
            "watch_each_turn",
            "--host-capability",
            "visible_session",
            *host_args,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        visible = next(
            option for option in payload["mode_options"] if option["mode"] == "visible_tui"
        )
        assert payload["selected_capability_ready"] is False, payload
        assert payload["selected_connector_id"] is None, payload
        assert payload["selected_turn_mapping"]["host"] is None, payload
        assert payload["operator_next_steps"][0]["kind"] == "stop", payload
        assert visible["host_identity"] == expected_identity, visible
        assert visible["recommended_next_steps"][0]["kind"] == "stop", visible


def test_cli_shell_service_fails_closed_without_adapter_and_validator() -> None:
    proc = run_cli(
        "--format",
        "json",
        "host-mode-plan",
        "--goal-id",
        "host-mode-plan-cli-fixture",
        "--intent",
        "timer_keepalive",
        "--host-capability",
        "service_timer",
        "--host-capability",
        "shell",
        "--host-capability",
        "loopx_turn",
        "--agent-id",
        "codex-main-control",
        "--registered-agent",
        "codex-main-control",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["selected_mode"] == "shell_service", payload
    assert payload["selected_capability_ready"] is False, payload
    assert payload["selected_missing_host_capabilities"] == [
        "typed_host_adapter",
        "independent_validator",
    ], payload
    assert payload["operator_next_steps"][0]["kind"] == "stop", payload


def test_cli_fails_closed_on_bad_intent() -> None:
    proc = run_cli(
        "--format",
        "json",
        "host-mode-plan",
        "--goal-id",
        "host-mode-plan-cli-fixture",
        "--intent",
        "launch_missiles",
    )
    assert proc.returncode == 1, proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False, payload
    assert payload["field"] == "user_intent", payload
    assert payload["suggestions"], payload


def test_cli_reports_missing_capabilities_and_stop_steps() -> None:
    proc = run_cli(
        "--format",
        "json",
        "host-mode-plan",
        "--goal-id",
        "host-mode-plan-cli-fixture",
        "--intent",
        "continue_without_ui",
        "--host-capability",
        "loopx_turn",
        "--agent-id",
        "codex-main-control",
        "--registered-agent",
        "codex-main-control",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["selected_capability_ready"] is False, payload
    assert payload["selected_missing_host_capabilities"] == [
        "typed_host_adapter",
        "independent_validator",
    ], payload
    assert payload["selected_blocking_reasons"], payload
    assert payload["operator_next_steps"][0]["kind"] == "stop", payload


def test_command_is_discoverable() -> None:
    proc = run_cli("--format", "json", "commands")
    assert proc.returncode == 0, proc.stderr
    assert "host-mode-plan" in proc.stdout, "host-mode-plan missing from loopx commands reference"


def main() -> int:
    test_cli_selects_headless_turn_and_scopes_agent_id()
    test_cli_markdown_explains_benefits()
    test_cli_visible_mode_preserves_host_identity()
    test_cli_visible_mode_fails_closed_without_registered_host()
    test_cli_shell_service_fails_closed_without_adapter_and_validator()
    test_cli_fails_closed_on_bad_intent()
    test_cli_reports_missing_capabilities_and_stop_steps()
    test_command_is_discoverable()
    print("host-mode-plan-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
