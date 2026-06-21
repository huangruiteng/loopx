#!/usr/bin/env python3
"""Smoke-test the Codex CLI visible driver run packet."""

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
    build_codex_cli_visible_driver_run_packet,
    classify_codex_cli_session_surface,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


FALLBACK_HELP_FIXTURE = {
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


VISIBLE_PROOF_FIXTURE = {
    "observed_surface": "visible_resume_prompt",
    "recommended_command": "codex resume public-session-id 'LoopX visible steering turn'",
    "user_opt_in": True,
    "quota_guard": {"passed": True},
    "idle_guard": {
        "no_active_human_typing": True,
        "no_running_turn": True,
        "checked_before_prompt": True,
    },
    "turn_visibility": {
        "visible_to_user": True,
        "prompt_public_safe": True,
    },
    "interruptibility": {
        "user_can_interrupt": True,
        "manual_takeover_available": True,
    },
    "boundary": {
        "reads_raw_transcripts": False,
        "reads_session_files": False,
        "reads_credentials": False,
        "mutates_hidden_session_state": False,
        "spends_quota_before_writeback": False,
    },
    "writeback": {"compact_evidence_planned": True},
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


def assert_boundary(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_visible_driver_run_packet_v0", payload
    assert payload["driver_phase"] == "run_packet_no_execution", payload
    boundary = payload["boundary"]
    assert boundary["run_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    policy = payload["execution_policy"]
    assert policy["tui_bootstrap_primary"] is True, payload
    assert policy["same_session_attachment_requires_visible_proof"] is True, payload
    assert policy["headless_execution_disabled"] is True, payload
    assert policy["quota_guard_required"] is True, payload
    assert policy["idle_guard_required_before_visible_prompt"] is True, payload
    assert policy["spend_after_validated_writeback_only"] is True, payload


def build_packet(
    command_outputs: dict[str, str],
    *,
    proof_payload: dict[str, object] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, object]:
    return build_codex_cli_visible_driver_run_packet(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=command_outputs),
        proof_payload=proof_payload,
        allow_headless_fallback=allow_headless_fallback,
    )


def main() -> int:
    proof_required = build_packet(REMOTE_RESUME_HELP_FIXTURE)
    assert_boundary(proof_required)
    assert proof_required["decision"] == "visible_session_proof_required", proof_required
    assert proof_required["next_driver_action"] == "capture_public_safe_visible_session_proof", proof_required
    assert proof_required["visible_session_proof"]["supplied"] is False, proof_required
    assert "codex-cli-visible-session-proof" in proof_required["recommended_command"], proof_required

    tui_only = build_packet(FALLBACK_HELP_FIXTURE)
    assert_boundary(tui_only)
    assert tui_only["decision"] == "tui_bootstrap_only", tui_only
    assert tui_only["next_driver_action"] == "ask_user_to_start_inside_codex_cli_tui", tui_only
    assert "codex-cli-bootstrap-message" in tui_only["recommended_command"], tui_only

    fallback_ignored = build_packet(FALLBACK_HELP_FIXTURE, allow_headless_fallback=True)
    assert_boundary(fallback_ignored)
    assert fallback_ignored["decision"] == "tui_bootstrap_only", fallback_ignored
    assert fallback_ignored["next_driver_action"] == "ask_user_to_start_inside_codex_cli_tui", fallback_ignored
    assert "codex-cli-bootstrap-message" in fallback_ignored["recommended_command"], fallback_ignored
    assert any("allow_headless_fallback was ignored" in warning for warning in fallback_ignored["warnings"]), fallback_ignored

    visible_candidate = build_packet(REMOTE_RESUME_HELP_FIXTURE, proof_payload=VISIBLE_PROOF_FIXTURE)
    assert_boundary(visible_candidate)
    assert visible_candidate["decision"] == "visible_session_turn_candidate", visible_candidate
    assert visible_candidate["visible_session_proof"]["approved"] is True, visible_candidate
    assert "codex resume public-session-id" in visible_candidate["recommended_command"], visible_candidate

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-driver-run-") as tmp:
        tmp_path = Path(tmp)
        help_fixture = tmp_path / "codex-remote-help.json"
        help_fixture.write_text(json.dumps({"command_outputs": REMOTE_RESUME_HELP_FIXTURE}))
        proof_fixture = tmp_path / "visible-proof.json"
        proof_fixture.write_text(json.dumps(VISIBLE_PROOF_FIXTURE))

        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-driver-run",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--fixture",
                str(help_fixture),
            )
        )
        assert_boundary(cli_json)
        assert cli_json["decision"] == "visible_session_proof_required", cli_json

        cli_proof_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-driver-run",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--fixture",
                str(help_fixture),
                "--proof-fixture",
                str(proof_fixture),
            )
        )
        assert_boundary(cli_proof_json)
        assert cli_proof_json["decision"] == "visible_session_turn_candidate", cli_proof_json

        cli_markdown = run_cli(
            "codex-cli-visible-driver-run",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
        )
        assert "# Codex CLI Visible Driver Run Packet" in cli_markdown, cli_markdown
        assert "decision: `visible_session_proof_required`" in cli_markdown, cli_markdown
        assert "runs_codex: `False`" in cli_markdown, cli_markdown

    print("codex-cli-visible-driver-run-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
