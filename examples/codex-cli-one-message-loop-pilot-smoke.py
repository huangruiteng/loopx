#!/usr/bin/env python3
"""Smoke-test the Codex CLI one-message loop pilot packet."""

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
    build_codex_cli_one_message_loop_pilot,
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


RUNTIME_IDLE_FIXTURE = {
    "observed_surface": "visible_resume_prompt",
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


def build_pilot(
    proof_payload: dict[str, object] | None = None,
    idle_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_codex_cli_one_message_loop_pilot(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=REMOTE_RESUME_HELP_FIXTURE),
        proof_payload=proof_payload,
        idle_payload=idle_payload,
    )


def assert_pilot_boundary(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_one_message_loop_pilot_v0", payload
    boundary = payload["boundary"]
    assert boundary["pilot_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["runs_scheduler_result"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["requires_user_visible_start"] is True, payload
    assert boundary["headless_execution_disabled"] is True, payload


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    no_proof = build_pilot()
    assert_pilot_boundary(no_proof)
    assert no_proof["start_surface"] == "codex_cli_tui_one_message", no_proof
    assert no_proof["pilot_decision"] == "first_message_then_visible_blocker_writeback", no_proof
    assert no_proof["first_turn"]["autostarts_loopx_loop"] is True, no_proof
    assert no_proof["first_turn"]["setup_then_loop_activation"] is True, no_proof
    assert no_proof["first_turn"]["loop_activation"]["codex_cli"] == "/goal <thin task_body>", no_proof
    assert no_proof["first_turn"]["loop_activation"]["codex_app"] == "<thin task_body> heartbeat automation", no_proof
    assert no_proof["first_turn"]["preserve_tui"] is True, no_proof
    assert "workspace_guard" in no_proof["first_turn"]["stop_only_for"], no_proof
    assert no_proof["first_turn"]["message"].startswith("Install and connect LoopX for this repo"), no_proof
    assert not no_proof["first_turn"]["message"].startswith("/goal "), no_proof
    assert "Codex CLI TUI" in no_proof["first_turn"]["message"], no_proof
    assert "headless `codex exec`" in no_proof["first_turn"]["message"], no_proof
    assert "runtime_idle_evidence" in no_proof["later_turn_contract"]["visible_steering_requires"], no_proof
    assert no_proof["bootstrap_message"]["invocation_mode"] == "codex_cli_setup_then_goal_mode", no_proof
    assert "heartbeat-prompt --thin" in no_proof["bootstrap_message"]["heartbeat_prompt_json_command"], no_proof
    assert no_proof["later_turn_contract"]["default_without_proof"] == "write_blocker_or_keep_tui_bootstrap_primary", no_proof
    assert no_proof["automation_bridge"]["command"] == "codex-cli-local-scheduler-exec", no_proof
    assert no_proof["automation_bridge"]["default_executes"] is False, no_proof
    assert no_proof["automation_bridge"]["scheduler_action"] == "write_precise_blocker", no_proof
    assert no_proof["automation_bridge"]["executor_reason"] == "no_execute_flag", no_proof
    assert "codex-cli-bootstrap-message" in no_proof["commands"]["bootstrap_message"], no_proof
    assert "codex-cli-local-scheduler-exec" in no_proof["commands"]["scheduler_exec_dry_run"], no_proof
    assert "--execute-blocker-writeback" in no_proof["commands"]["scheduler_exec_blocker_template"], no_proof

    with_proof = build_pilot(VISIBLE_PROOF_FIXTURE)
    assert_pilot_boundary(with_proof)
    assert with_proof["pilot_decision"] == "first_message_then_runtime_idle_required", with_proof
    assert with_proof["automation_bridge"]["scheduler_action"] == "write_precise_blocker", with_proof
    assert with_proof["scheduler_executor"]["execution"]["executed"] is False, with_proof

    with_proof_and_idle = build_pilot(VISIBLE_PROOF_FIXTURE, RUNTIME_IDLE_FIXTURE)
    assert_pilot_boundary(with_proof_and_idle)
    assert with_proof_and_idle["pilot_decision"] == "first_message_then_candidate_available", with_proof_and_idle
    assert with_proof_and_idle["automation_bridge"]["scheduler_action"] == "external_visible_command_candidate", with_proof_and_idle
    assert with_proof_and_idle["scheduler_executor"]["scheduler_tick"]["runtime_idle_detector"]["approved"] is True, with_proof_and_idle

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-one-message-") as tmp:
        tmp_path = Path(tmp)
        help_fixture = tmp_path / "codex-remote-help.json"
        help_fixture.write_text(json.dumps({"command_outputs": REMOTE_RESUME_HELP_FIXTURE}))
        proof_fixture = tmp_path / "visible-proof.json"
        proof_fixture.write_text(json.dumps(VISIBLE_PROOF_FIXTURE))
        idle_fixture = tmp_path / "runtime-idle.json"
        idle_fixture.write_text(json.dumps(RUNTIME_IDLE_FIXTURE))
        missing_registry = tmp_path / "missing-registry.json"
        runtime_root = tmp_path / "runtime"

        cli_json = json.loads(
            run_cli(
                "--registry",
                str(missing_registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "codex-cli-one-message-loop-pilot",
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
        assert_pilot_boundary(cli_json)
        assert cli_json["pilot_decision"] == "first_message_then_visible_blocker_writeback", cli_json

        cli_proof_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-one-message-loop-pilot",
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
        assert_pilot_boundary(cli_proof_json)
        assert cli_proof_json["pilot_decision"] == "first_message_then_runtime_idle_required", cli_proof_json

        cli_proof_idle_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-one-message-loop-pilot",
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
                "--idle-fixture",
                str(idle_fixture),
            )
        )
        assert_pilot_boundary(cli_proof_idle_json)
        assert cli_proof_idle_json["pilot_decision"] == "first_message_then_candidate_available", cli_proof_idle_json

        cli_markdown = run_cli(
            "codex-cli-one-message-loop-pilot",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
        )
        assert "# Codex CLI One-Message Loop Pilot" in cli_markdown, cli_markdown
        assert "requires_user_visible_start: `True`" in cli_markdown, cli_markdown
        assert "candidate_execution_requires_guard_and_prefix: `True`" in cli_markdown, cli_markdown

    print("codex-cli-one-message-loop-pilot-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
