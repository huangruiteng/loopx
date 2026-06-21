#!/usr/bin/env python3
"""Smoke-test the dry-run-first Codex CLI local driver plan."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.codex_cli_probe import (  # noqa: E402
    build_codex_cli_local_driver_plan,
    classify_codex_cli_session_surface,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


HELP_FIXTURE = {
    "root": """
Usage: codex [OPTIONS] [PROMPT]

Commands:
  exec      Run Codex non-interactively
  resume    Resume a previous conversation
""",
    "exec": "Usage: codex exec [OPTIONS] [PROMPT]",
    "resume": "Usage: codex resume [SESSION_ID]",
}


REMOTE_RESUME_HELP_FIXTURE = {
    "root": """
Usage: codex [OPTIONS] [PROMPT]

Commands:
  exec
  remote-control  Manage the app-server daemon with remote control enabled
  resume          Resume a previous interactive session

Options:
  --remote <ADDR>  Connect the TUI to a remote app server endpoint
""",
    "exec": "Usage: codex exec [OPTIONS] [PROMPT]",
    "resume": """
Usage: codex resume [OPTIONS] [SESSION_ID] [PROMPT]

Resume a previous interactive session.
""",
}


ATTACH_HELP_FIXTURE = {
    "root": """
Usage: codex [OPTIONS] [PROMPT]

Commands:
  exec
  resume
  attach-session    Send prompt to session after checking the idle TUI
""",
    "exec": "Usage: codex exec [OPTIONS] [PROMPT]",
    "resume": "Usage: codex resume [SESSION_ID]",
}


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_common_contract(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_local_driver_plan_v0", payload
    assert payload["driver_phase"] == "dry_run_plan", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["agent_id"] == AGENT_ID, payload
    commands = payload["commands"]
    assert "quota should-run --goal-id public-codex-cli-goal --agent-id codex-side-bypass" in commands["quota_guard"], payload
    assert "codex-cli-visible-driver-plan" in commands["visible_driver_plan"], payload
    assert "codex-cli-bootstrap-message" in commands["tui_bootstrap_message"], payload
    assert commands["explicit_headless_fallback"] is None, payload
    assert "headless codex exec is disabled" in commands["headless_fallback_disabled"], payload
    assert payload["idle_guard"]["required"] is True, payload
    assert payload["idle_guard"]["implemented"] is False, payload
    policy = payload["execution_policy"]
    assert policy["tui_bootstrap_primary"] is True, payload
    assert policy["headless_execution_disabled"] is True, payload
    assert policy["same_session_attachment_requires_visible_proof"] is True, payload
    boundary = payload["boundary"]
    assert boundary["dry_run_plan_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload


def build_plan(command_outputs: dict[str, str]) -> dict[str, object]:
    return build_codex_cli_local_driver_plan(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=command_outputs),
    )


def main() -> int:
    fallback_plan = build_plan(HELP_FIXTURE)
    assert_common_contract(fallback_plan)
    assert fallback_plan["driver_mode"] == "tui_bootstrap_only", fallback_plan
    assert fallback_plan["decision"] == "ask_user_to_start_from_tui", fallback_plan

    remote_plan = build_plan(REMOTE_RESUME_HELP_FIXTURE)
    assert_common_contract(remote_plan)
    assert remote_plan["driver_mode"] == "visible_resume_or_remote_control_spike", remote_plan
    assert remote_plan["decision"] == "run_visible_resume_or_remote_control_proof", remote_plan

    attach_plan = build_plan(ATTACH_HELP_FIXTURE)
    assert_common_contract(attach_plan)
    assert attach_plan["driver_mode"] == "session_attached_visible_turn", attach_plan
    assert attach_plan["decision"] == "attempt_visible_session_attach_after_idle_guard", attach_plan

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-local-driver-") as tmp:
        fixture = Path(tmp) / "codex-remote-help.json"
        fixture.write_text(json.dumps({"command_outputs": REMOTE_RESUME_HELP_FIXTURE}))
        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-local-driver-plan",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--fixture",
                str(fixture),
            )
        )
        assert_common_contract(cli_json)
        assert cli_json["driver_mode"] == "visible_resume_or_remote_control_spike", cli_json

        cli_markdown = run_cli(
            "codex-cli-local-driver-plan",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(fixture),
        )
        assert "# Codex CLI Local Driver Plan" in cli_markdown, cli_markdown
        assert "driver_phase: `dry_run_plan`" in cli_markdown, cli_markdown
        assert "headless_execution_disabled: `True`" in cli_markdown, cli_markdown

    print("codex-cli-local-driver-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
