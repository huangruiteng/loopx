#!/usr/bin/env python3
"""Smoke-test the Codex CLI visible attach acceptance packet."""

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
    build_codex_cli_visible_attach_acceptance,
    classify_codex_cli_session_surface,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


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
    "resume": "Usage: codex resume [OPTIONS] [SESSION_ID] [PROMPT]",
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


def proof_fixture(surface: str) -> dict[str, object]:
    return {
        "observed_surface": surface,
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


PASSING_IDLE_FIXTURE = {
    "observed_surface": "same_tui_visible_attach",
    "idle_guard": {
        "no_active_human_typing": True,
        "no_running_turn": True,
        "checked_before_prompt": True,
    },
    "turn_visibility": {"visible_to_user": True},
    "interruptibility": {
        "user_can_interrupt": True,
        "manual_takeover_available": True,
    },
    "boundary": {
        "reads_raw_transcripts": False,
        "reads_session_files": False,
        "reads_stdout_stderr": False,
        "reads_credentials": False,
        "mutates_hidden_session_state": False,
    },
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


def build(
    command_outputs: dict[str, str],
    *,
    proof: dict[str, object] | None = None,
    idle: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_codex_cli_visible_attach_acceptance(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=command_outputs),
        proof_payload=proof,
        idle_payload=idle,
    )


def assert_public_safe_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert boundary["acceptance_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_stdout_stderr"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload


def main() -> int:
    remote_without_proof = build(REMOTE_RESUME_HELP_FIXTURE)
    assert remote_without_proof["ok"] is True, remote_without_proof
    assert remote_without_proof["decision"] == "visible_session_proof_required", remote_without_proof
    assert remote_without_proof["accepted_for_same_tui_automation"] is False, remote_without_proof
    assert "visible_session_proof_missing" in remote_without_proof["blockers"], remote_without_proof
    assert_public_safe_boundary(remote_without_proof)

    remote_spike = build(
        REMOTE_RESUME_HELP_FIXTURE,
        proof=proof_fixture("remote_control_visible_prompt"),
        idle={**PASSING_IDLE_FIXTURE, "observed_surface": "remote_control_visible_prompt"},
    )
    assert remote_spike["decision"] == "visible_surface_spike_passed_not_same_tui", remote_spike
    assert remote_spike["accepted_for_visible_later_turn"] is True, remote_spike
    assert remote_spike["accepted_for_same_tui_automation"] is False, remote_spike
    assert "same_tui_visible_attach_not_proven" in remote_spike["blockers"], remote_spike
    assert_public_safe_boundary(remote_spike)

    same_tui_accepted = build(
        ATTACH_HELP_FIXTURE,
        proof=proof_fixture("same_tui_visible_attach"),
        idle=PASSING_IDLE_FIXTURE,
    )
    assert same_tui_accepted["decision"] == "same_tui_visible_attach_accepted", same_tui_accepted
    assert same_tui_accepted["accepted_for_same_tui_automation"] is True, same_tui_accepted
    assert same_tui_accepted["accepted_for_visible_later_turn"] is True, same_tui_accepted
    assert same_tui_accepted["blockers"] == [], same_tui_accepted
    assert_public_safe_boundary(same_tui_accepted)

    missing_idle = build(
        ATTACH_HELP_FIXTURE,
        proof=proof_fixture("same_tui_visible_attach"),
    )
    assert missing_idle["decision"] == "runtime_idle_evidence_required", missing_idle
    assert missing_idle["accepted_for_same_tui_automation"] is False, missing_idle
    assert "missing_runtime_idle_evidence" in missing_idle["blockers"], missing_idle
    assert_public_safe_boundary(missing_idle)

    fallback = build(FALLBACK_HELP_FIXTURE)
    assert fallback["decision"] == "tui_bootstrap_only", fallback
    assert fallback["accepted_for_same_tui_automation"] is False, fallback
    assert fallback["accepted_for_visible_later_turn"] is False, fallback
    assert fallback["requirements"]["headless_execution_disabled"] is True, fallback
    assert_public_safe_boundary(fallback)

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-visible-attach-") as tmp:
        tmpdir = Path(tmp)
        help_fixture = tmpdir / "codex-attach-help.json"
        proof_path = tmpdir / "same-tui-proof.json"
        idle_path = tmpdir / "runtime-idle.json"
        help_fixture.write_text(json.dumps({"command_outputs": ATTACH_HELP_FIXTURE}))
        proof_path.write_text(json.dumps(proof_fixture("same_tui_visible_attach")))
        idle_path.write_text(json.dumps(PASSING_IDLE_FIXTURE))

        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-attach-acceptance",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--fixture",
                str(help_fixture),
                "--proof-fixture",
                str(proof_path),
                "--idle-fixture",
                str(idle_path),
            )
        )
        assert cli_json["decision"] == "same_tui_visible_attach_accepted", cli_json
        assert cli_json["accepted_for_same_tui_automation"] is True, cli_json

        cli_markdown = run_cli(
            "codex-cli-visible-attach-acceptance",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
            "--proof-fixture",
            str(proof_path),
            "--idle-fixture",
            str(idle_path),
        )
        assert "# Codex CLI Visible Attach Acceptance" in cli_markdown, cli_markdown
        assert "accepted_for_same_tui_automation: `True`" in cli_markdown, cli_markdown
        assert "same_tui_visible_attach_accepted" in cli_markdown, cli_markdown

    print("codex-cli-visible-attach-acceptance-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
