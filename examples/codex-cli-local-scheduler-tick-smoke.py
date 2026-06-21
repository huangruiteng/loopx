#!/usr/bin/env python3
"""Smoke-test the Codex CLI local scheduler tick packet."""

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
    build_codex_cli_local_scheduler_tick,
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


def assert_boundary(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_local_scheduler_tick_v0", payload
    assert payload["scheduler_phase"] == "tick_packet_no_execution", payload
    boundary = payload["boundary"]
    assert boundary["tick_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload
    assert boundary["visible_candidate_requires_runtime_idle_detector"] is True, payload
    assert boundary["headless_execution_disabled"] is True, payload


def build_tick(
    command_outputs: dict[str, str],
    *,
    proof_payload: dict[str, object] | None = None,
    idle_payload: dict[str, object] | None = None,
    allow_headless_fallback: bool = False,
) -> dict[str, object]:
    return build_codex_cli_local_scheduler_tick(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=command_outputs),
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=allow_headless_fallback,
    )


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
    proof_missing = build_tick(REMOTE_RESUME_HELP_FIXTURE)
    assert_boundary(proof_missing)
    assert proof_missing["scheduler_action"] == "write_precise_blocker", proof_missing
    assert proof_missing["precise_blocker"]["reason"] == "visible_session_proof_missing", proof_missing
    assert "refresh-state" in proof_missing["blocker_writeback_command"], proof_missing
    assert proof_missing["candidate_command"] is None, proof_missing

    tui_only = build_tick(FALLBACK_HELP_FIXTURE)
    assert_boundary(tui_only)
    assert tui_only["scheduler_action"] == "surface_tui_bootstrap", tui_only
    assert tui_only["candidate_command"] is None, tui_only
    assert tui_only["blocker_writeback_command"] is None, tui_only

    fallback_ignored = build_tick(FALLBACK_HELP_FIXTURE, allow_headless_fallback=True)
    assert_boundary(fallback_ignored)
    assert fallback_ignored["scheduler_action"] == "surface_tui_bootstrap", fallback_ignored
    assert fallback_ignored["candidate_command"] is None, fallback_ignored
    assert fallback_ignored["blocker_writeback_command"] is None, fallback_ignored
    assert any("allow_headless_fallback was ignored" in warning for warning in fallback_ignored["warnings"]), fallback_ignored

    visible_idle_missing = build_tick(REMOTE_RESUME_HELP_FIXTURE, proof_payload=VISIBLE_PROOF_FIXTURE)
    assert_boundary(visible_idle_missing)
    assert visible_idle_missing["scheduler_action"] == "write_precise_blocker", visible_idle_missing
    assert visible_idle_missing["precise_blocker"]["reason"] == "runtime_idle_evidence_missing", visible_idle_missing
    assert visible_idle_missing["runtime_idle_detector"]["approved"] is False, visible_idle_missing
    assert visible_idle_missing["candidate_command"] is None, visible_idle_missing

    visible_candidate = build_tick(
        REMOTE_RESUME_HELP_FIXTURE,
        proof_payload=VISIBLE_PROOF_FIXTURE,
        idle_payload=RUNTIME_IDLE_FIXTURE,
    )
    assert_boundary(visible_candidate)
    assert visible_candidate["scheduler_action"] == "external_visible_command_candidate", visible_candidate
    assert "codex resume public-session-id" in visible_candidate["candidate_command"], visible_candidate
    assert visible_candidate["runtime_idle_detector"]["approved"] is True, visible_candidate

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-scheduler-tick-") as tmp:
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
                "codex-cli-local-scheduler-tick",
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
        assert cli_json["scheduler_action"] == "write_precise_blocker", cli_json

        cli_proof_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-local-scheduler-tick",
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
        assert cli_proof_json["scheduler_action"] == "write_precise_blocker", cli_proof_json
        assert cli_proof_json["precise_blocker"]["reason"] == "runtime_idle_evidence_missing", cli_proof_json

        cli_proof_idle_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-local-scheduler-tick",
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
        assert_boundary(cli_proof_idle_json)
        assert cli_proof_idle_json["scheduler_action"] == "external_visible_command_candidate", cli_proof_idle_json
        assert cli_proof_idle_json["runtime_idle_detector"]["approved"] is True, cli_proof_idle_json

        cli_markdown = run_cli(
            "codex-cli-local-scheduler-tick",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
        )
        assert "# Codex CLI Local Scheduler Tick" in cli_markdown, cli_markdown
        assert "scheduler_action: `write_precise_blocker`" in cli_markdown, cli_markdown
        assert "runs_codex: `False`" in cli_markdown, cli_markdown

    print("codex-cli-local-scheduler-tick-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
