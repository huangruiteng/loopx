#!/usr/bin/env python3
"""Smoke-test the Codex CLI visible local driver pilot packet."""

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
    build_codex_cli_visible_local_driver_pilot,
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
    return build_codex_cli_visible_local_driver_pilot(
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
    assert payload["schema_version"] == "codex_cli_visible_local_driver_pilot_v0", payload
    assert payload["pilot_phase"] == "visible_local_driver_loop_no_execution", payload
    boundary = payload["boundary"]
    assert boundary["pilot_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["runs_scheduler_result"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_stdout_stderr"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["candidate_execution_requires_guard_and_prefix"] is True, payload
    assert boundary["blocker_writeback_requires_guard_checked"] is True, payload


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
    assert no_proof["loop_decision"] == "visible_loop_blocker_writeback_ready", no_proof
    assert no_proof["next_driver_action"] == "write_precise_blocker_after_fresh_guard", no_proof
    assert no_proof["scheduler_executor"]["scheduler_action"] == "write_precise_blocker", no_proof
    assert no_proof["scheduler_executor"]["executor_reason"] == "no_execute_flag", no_proof
    assert no_proof["scheduler_executor"]["executed"] is False, no_proof
    assert no_proof["visible_session_proof"]["approved"] is False, no_proof
    assert no_proof["runtime_idle_detector"]["approved"] is False, no_proof
    assert no_proof["runtime_idle_detector"]["decision"] == "runtime_idle_evidence_required", no_proof
    assert no_proof["idle_guard_contract"]["required_before_visible_prompt"] is True, no_proof
    assert no_proof["idle_guard_contract"]["current_pilot_implements_runtime_idle_detection"] is True, no_proof
    assert no_proof["idle_guard_contract"]["fixture_backed_runtime_idle_detector"] is True, no_proof
    assert no_proof["idle_guard_contract"]["runtime_sensor_implemented"] is True, no_proof
    assert no_proof["idle_guard_contract"]["local_observation_adapter_supported"] is True, no_proof
    assert no_proof["idle_guard_contract"]["no_private_state_observation"] is True, no_proof
    assert "codex-cli-local-scheduler-exec" in no_proof["commands"]["scheduler_exec_dry_run"], no_proof
    assert "codex-cli-runtime-idle-detector" in no_proof["commands"]["runtime_idle_detector"], no_proof
    assert "--observe-local-runtime" in no_proof["commands"]["runtime_idle_detector"], no_proof
    assert "runtime_idle_detector_fixture" in no_proof["commands"], no_proof
    assert "--idle-fixture" in no_proof["commands"]["runtime_idle_detector_fixture"], no_proof
    assert "--execute-blocker-writeback" in no_proof["commands"]["scheduler_exec_blocker_template"], no_proof

    with_proof = build_pilot(VISIBLE_PROOF_FIXTURE)
    assert_pilot_boundary(with_proof)
    assert with_proof["loop_decision"] == "runtime_idle_detector_required", with_proof
    assert with_proof["next_driver_action"] == "capture_public_safe_runtime_idle_observation", with_proof
    assert with_proof["scheduler_executor"]["scheduler_action"] == "write_precise_blocker", with_proof
    assert with_proof["visible_session_proof"]["supplied"] is True, with_proof
    assert with_proof["visible_session_proof"]["approved"] is True, with_proof
    assert with_proof["runtime_idle_detector"]["supplied"] is False, with_proof
    assert with_proof["runtime_idle_detector"]["approved"] is False, with_proof

    with_proof_and_idle = build_pilot(VISIBLE_PROOF_FIXTURE, RUNTIME_IDLE_FIXTURE)
    assert_pilot_boundary(with_proof_and_idle)
    assert with_proof_and_idle["loop_decision"] == "visible_candidate_ready_for_guarded_execution", with_proof_and_idle
    assert with_proof_and_idle["next_driver_action"] == "run_scheduler_exec_candidate_after_fresh_guard_and_prefix", with_proof_and_idle
    assert with_proof_and_idle["scheduler_executor"]["scheduler_action"] == "external_visible_command_candidate", with_proof_and_idle
    assert with_proof_and_idle["visible_session_proof"]["approved"] is True, with_proof_and_idle
    assert with_proof_and_idle["runtime_idle_detector"]["supplied"] is True, with_proof_and_idle
    assert with_proof_and_idle["runtime_idle_detector"]["approved"] is True, with_proof_and_idle
    assert with_proof["execution_policy"]["later_turns_visible_to_user"] is True, with_proof
    assert with_proof["execution_policy"]["user_can_interrupt_or_take_over"] is True, with_proof

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-visible-local-driver-") as tmp:
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
                "codex-cli-visible-local-driver-pilot",
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
        assert cli_json["loop_decision"] == "visible_loop_blocker_writeback_ready", cli_json

        cli_proof_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-local-driver-pilot",
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
        assert cli_proof_json["loop_decision"] == "runtime_idle_detector_required", cli_proof_json

        cli_proof_idle_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-local-driver-pilot",
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
        assert cli_proof_idle_json["loop_decision"] == "visible_candidate_ready_for_guarded_execution", cli_proof_idle_json
        assert cli_proof_idle_json["runtime_idle_detector"]["approved"] is True, cli_proof_idle_json

        cli_markdown = run_cli(
            "codex-cli-visible-local-driver-pilot",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
        )
        assert "# Codex CLI Visible Local Driver Pilot" in cli_markdown, cli_markdown
        assert "loop_decision: `visible_loop_blocker_writeback_ready`" in cli_markdown, cli_markdown
        assert "## Runtime Idle Detector" in cli_markdown, cli_markdown
        assert "reads_raw_transcripts: `False`" in cli_markdown, cli_markdown
        assert "user_can_interrupt_or_take_over: `True`" in cli_markdown, cli_markdown

    print("codex-cli-visible-local-driver-pilot-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
