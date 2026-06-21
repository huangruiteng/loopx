#!/usr/bin/env python3
"""Smoke-test the disabled Codex CLI exec handoff boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.project_prompt import build_codex_cli_exec_handoff  # noqa: E402


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_handoff_contract(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_exec_handoff_v0", payload
    assert payload["mode"] == "headless_fallback_disabled_for_goal_mode_bootstrap", payload
    assert payload["primary_experience"] == "codex_cli_tui_goal_bootstrap", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["agent_id"] == AGENT_ID, payload
    command = str(payload["handoff_command"])
    message_only = str(payload["message_only_command"])
    assert command == "", payload
    assert "codex exec" not in command, payload
    assert "codex-cli-bootstrap-message" in message_only, payload
    assert "--message-only" in message_only, payload
    assert "disabled" in str(payload["disabled_reason"]).lower(), payload
    boundary = payload["boundary"]
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["headless_execution_disabled"] is True, payload
    assert boundary["provides_executable_headless_command"] is False, payload


def main() -> int:
    payload = build_codex_cli_exec_handoff(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
    )
    assert_handoff_contract(payload)

    cli_json = json.loads(
        run_cli(
            "--format",
            "json",
            "codex-cli-exec-handoff",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
    )
    assert_handoff_contract(cli_json)

    cli_markdown = run_cli(
        "codex-cli-exec-handoff",
        "--project",
        str(PROJECT),
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert "# Codex CLI Exec Handoff Disabled" in cli_markdown, cli_markdown
    assert "Headless `codex exec` handoff is disabled" in cli_markdown, cli_markdown
    assert "codex-cli-bootstrap-message" in cli_markdown, cli_markdown
    assert "cat <<'LOOPX_CODEX_PROMPT' | codex exec" not in cli_markdown, cli_markdown

    print("codex-cli-exec-handoff-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
