#!/usr/bin/env python3
"""Smoke-test the Codex CLI session-attachment capability probe."""

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
    build_codex_cli_visible_driver_plan,
    classify_codex_cli_session_surface,
)


HELP_FIXTURE = {
    "root": """
Usage: codex [OPTIONS] [PROMPT]

Commands:
  exec      Run Codex non-interactively
  resume    Resume a previous conversation
""",
    "exec": """
Usage: codex exec [OPTIONS] [PROMPT]

Options:
  --resume <SESSION_ID>    Continue from a previous session
""",
    "resume": """
Usage: codex resume [SESSION_ID]

Resume a previous conversation in a new Codex invocation.
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


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_fallback_contract(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_session_probe_v0", payload
    capabilities = payload["capabilities"]
    assert capabilities["exec_supported"] is True, payload
    assert capabilities["resume_supported"] is True, payload
    assert capabilities["session_handle_detected"] is True, payload
    assert capabilities["visible_resume_supported"] is False, payload
    assert capabilities["remote_control_surface_detected"] is False, payload
    assert capabilities["same_tui_injection_detected"] is False, payload
    assert capabilities["safe_injection_supported"] is False, payload
    assert payload["recommended_mode"] == "tui_bootstrap_only", payload
    assert payload["automation_action"] == "ask_user_to_start_inside_codex_cli_tui", payload
    assert any("headless fallback is disabled" in warning for warning in payload["warnings"]), payload
    boundary = payload["boundary"]
    assert boundary["help_only_probe"] is True, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload


def main() -> int:
    payload = classify_codex_cli_session_surface(command_outputs=HELP_FIXTURE)
    assert_fallback_contract(payload)

    remote_payload = classify_codex_cli_session_surface(command_outputs=REMOTE_RESUME_HELP_FIXTURE)
    assert remote_payload["capabilities"]["visible_resume_supported"] is True, remote_payload
    assert remote_payload["capabilities"]["remote_control_surface_detected"] is True, remote_payload
    assert remote_payload["capabilities"]["same_tui_injection_detected"] is False, remote_payload
    assert remote_payload["recommended_mode"] == "visible_resume_or_remote_control_spike", remote_payload
    assert remote_payload["automation_action"] == "prototype_visible_resume_or_remote_control_with_idle_guard", remote_payload
    remote_plan = build_codex_cli_visible_driver_plan(
        project=Path("/tmp/public-codex-cli-project"),
        goal_id="public-codex-cli-goal",
        agent_id="codex-side-bypass",
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=remote_payload,
    )
    assert remote_plan["schema_version"] == "codex_cli_visible_driver_plan_v0", remote_plan
    assert remote_plan["driver_mode"] == "visible_resume_or_remote_control_spike", remote_plan
    assert remote_plan["boundary"]["dry_run_plan_only"] is True, remote_plan
    assert remote_plan["boundary"]["reads_raw_transcripts"] is False, remote_plan
    assert remote_plan["boundary"]["reads_session_files"] is False, remote_plan
    assert remote_plan["boundary"]["mutates_codex_session"] is False, remote_plan
    assert remote_plan["boundary"]["spends_loopx_quota"] is False, remote_plan
    assert "resume [PROMPT]" in " ".join(remote_plan["driver_steps"]), remote_plan
    assert remote_plan["commands"]["explicit_headless_fallback"] is None, remote_plan
    assert "headless codex exec is disabled" in remote_plan["commands"]["headless_fallback_disabled"], remote_plan

    attach_payload = classify_codex_cli_session_surface(command_outputs=ATTACH_HELP_FIXTURE)
    assert attach_payload["capabilities"]["safe_injection_supported"] is True, attach_payload
    assert attach_payload["recommended_mode"] == "session_attached_visible_turn", attach_payload
    attach_plan = build_codex_cli_visible_driver_plan(
        project=Path("/tmp/public-codex-cli-project"),
        goal_id="public-codex-cli-goal",
        agent_id="codex-side-bypass",
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=attach_payload,
    )
    assert attach_plan["driver_mode"] == "session_attached_visible_turn", attach_plan
    assert "visible attach primitive" in attach_plan["next_step"], attach_plan

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-probe-") as tmp:
        fixture = Path(tmp) / "codex-help.json"
        fixture.write_text(json.dumps({"command_outputs": HELP_FIXTURE}))
        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-session-probe",
                "--fixture",
                str(fixture),
            )
        )
        assert_fallback_contract(cli_json)

        cli_markdown = run_cli("codex-cli-session-probe", "--fixture", str(fixture))
        assert "# Codex CLI Session Probe" in cli_markdown, cli_markdown
        assert "recommended_mode: `tui_bootstrap_only`" in cli_markdown, cli_markdown
        assert "same_tui_injection_detected: `False`" in cli_markdown, cli_markdown

        remote_fixture = Path(tmp) / "codex-remote-help.json"
        remote_fixture.write_text(json.dumps({"command_outputs": REMOTE_RESUME_HELP_FIXTURE}))
        cli_plan_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-driver-plan",
                "--project",
                "/tmp/public-codex-cli-project",
                "--goal-id",
                "public-codex-cli-goal",
                "--agent-id",
                "codex-side-bypass",
                "--fixture",
                str(remote_fixture),
            )
        )
        assert cli_plan_json["driver_mode"] == "visible_resume_or_remote_control_spike", cli_plan_json
        assert cli_plan_json["boundary"]["dry_run_plan_only"] is True, cli_plan_json
        assert cli_plan_json["boundary"]["reads_raw_transcripts"] is False, cli_plan_json
        cli_plan_markdown = run_cli(
            "codex-cli-visible-driver-plan",
            "--project",
            "/tmp/public-codex-cli-project",
            "--goal-id",
            "public-codex-cli-goal",
            "--agent-id",
            "codex-side-bypass",
            "--fixture",
            str(remote_fixture),
        )
        assert "# Codex CLI Visible Driver Plan" in cli_plan_markdown, cli_plan_markdown
        assert "driver_mode: `visible_resume_or_remote_control_spike`" in cli_plan_markdown, cli_plan_markdown
        assert "dry_run_plan_only: `True`" in cli_plan_markdown, cli_plan_markdown

    print("codex-cli-session-probe-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
