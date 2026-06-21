#!/usr/bin/env python3
"""Smoke-test the Codex CLI local scheduler executor wrapper."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.codex_cli_probe import (  # noqa: E402
    build_codex_cli_local_scheduler_executor,
    classify_codex_cli_session_surface,
    execute_codex_cli_local_scheduler_tick_result,
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
    "recommended_command": f"{shlex.quote(sys.executable)} -c 'pass'",
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


def fake_runner_calls() -> tuple[list[dict[str, object]], object]:
    calls: list[dict[str, object]] = []

    def runner(command: str, *, timeout_seconds: float, capture_output: bool = False) -> dict[str, object]:
        calls.append(
            {
                "command": command,
                "timeout_seconds": timeout_seconds,
                "capture_output": capture_output,
            }
        )
        return {
            "attempted": True,
            "returncode": 0,
            "timed_out": False,
            "output_captured": capture_output,
        }

    return calls, runner


def build_exec(
    *,
    proof_payload: dict[str, object] | None = VISIBLE_PROOF_FIXTURE,
    idle_payload: dict[str, object] | None = RUNTIME_IDLE_FIXTURE,
    execute_candidate: bool = False,
    execute_blocker_writeback: bool = False,
    guard_checked: bool = False,
    prefixes: list[str] | None = None,
    runner=None,
) -> dict[str, object]:
    return build_codex_cli_local_scheduler_executor(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(command_outputs=REMOTE_RESUME_HELP_FIXTURE),
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        execute_candidate=execute_candidate,
        execute_blocker_writeback=execute_blocker_writeback,
        guard_checked=guard_checked,
        candidate_command_prefixes=prefixes or [],
        runner=runner,
    )


def assert_executor_boundary(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == "codex_cli_local_scheduler_executor_v0", payload
    boundary = payload["boundary"]
    assert boundary["executor_wrapper"] is True, payload
    assert boundary["requires_explicit_execute_flag"] is True, payload
    assert boundary["requires_fresh_quota_guard_confirmation"] is True, payload
    assert boundary["candidate_prefix_required"] is True, payload
    assert boundary["runtime_idle_detector_required_for_visible_candidate"] is True, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["candidate_output_captured"] is False, payload
    assert boundary["blocker_output_captured"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload


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
    calls, runner = fake_runner_calls()

    no_execute = build_exec(runner=runner)
    assert no_execute["ok"] is True, no_execute
    assert_executor_boundary(no_execute)
    assert no_execute["execution"]["executed"] is False, no_execute
    assert no_execute["execution"]["reason"] == "no_execute_flag", no_execute
    assert calls == [], calls

    guard_missing = build_exec(
        execute_candidate=True,
        prefixes=[sys.executable],
        runner=runner,
    )
    assert guard_missing["execution"]["reason"] == "fresh_quota_guard_confirmation_required", guard_missing
    assert calls == [], calls

    idle_missing = build_exec(
        idle_payload=None,
        execute_candidate=True,
        guard_checked=True,
        prefixes=[sys.executable],
        runner=runner,
    )
    assert idle_missing["scheduler_action"] == "write_precise_blocker", idle_missing
    assert idle_missing["scheduler_tick"]["precise_blocker"]["reason"] == "runtime_idle_evidence_missing", idle_missing
    assert idle_missing["execution"]["reason"] == "scheduler_action_not_candidate", idle_missing
    assert calls == [], calls

    tampered_tick = {
        "schema_version": "codex_cli_local_scheduler_tick_v0",
        "project": str(PROJECT),
        "goal_id": GOAL_ID,
        "agent_id": AGENT_ID,
        "cli_bin": "loopx",
        "codex_bin": "codex",
        "scheduler_phase": "tick_packet_no_execution",
        "scheduler_action": "external_visible_command_candidate",
        "decision": "visible_session_turn_candidate",
        "next_safe_step": "tampered visible candidate",
        "candidate_command": f"{shlex.quote(sys.executable)} -c 'pass'",
        "commands": {"scheduler_tick": "loopx codex-cli-local-scheduler-tick"},
        "visible_driver_run_packet": {
            "visible_session_proof": {"supplied": True, "approved": True}
        },
        "runtime_idle_detector": {"supplied": False, "approved": False},
    }
    tampered_reject = execute_codex_cli_local_scheduler_tick_result(
        tampered_tick,
        execute_candidate=True,
        guard_checked=True,
        candidate_command_prefixes=[sys.executable],
        runner=runner,
    )
    assert tampered_reject["execution"]["reason"] == "runtime_idle_detector_required", tampered_reject
    assert calls == [], calls

    prefix_missing = build_exec(
        execute_candidate=True,
        guard_checked=True,
        runner=runner,
    )
    assert prefix_missing["execution"]["reason"] == "candidate_command_prefix_required", prefix_missing
    assert calls == [], calls

    prefix_mismatch = build_exec(
        execute_candidate=True,
        guard_checked=True,
        prefixes=["definitely-not-python"],
        runner=runner,
    )
    assert prefix_mismatch["execution"]["reason"] == "candidate_command_prefix_mismatch", prefix_mismatch
    assert calls == [], calls

    candidate = build_exec(
        execute_candidate=True,
        guard_checked=True,
        prefixes=[sys.executable],
        runner=runner,
    )
    assert candidate["ok"] is True, candidate
    assert candidate["execution"]["executed"] is True, candidate
    assert candidate["execution"]["kind"] == "candidate_command", candidate
    assert candidate["execution"]["reason"] == "candidate_command_executed", candidate
    assert candidate["boundary"]["runs_external_candidate"] is True, candidate
    assert calls[-1]["capture_output"] is False, calls

    blocker = build_exec(
        proof_payload=None,
        execute_blocker_writeback=True,
        guard_checked=True,
        runner=runner,
    )
    assert blocker["ok"] is True, blocker
    assert blocker["execution"]["kind"] == "blocker_writeback", blocker
    assert "refresh-state" in calls[-1]["command"], calls
    assert blocker["boundary"]["writes_loopx_state"] is True, blocker
    assert blocker["boundary"]["spends_loopx_quota"] is False, blocker
    assert calls[-1]["capture_output"] is False, calls

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-scheduler-exec-") as tmp:
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
                "codex-cli-local-scheduler-exec",
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
        assert_executor_boundary(cli_json)
        assert cli_json["execution"]["reason"] == "no_execute_flag", cli_json

        cli_prefix_reject = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-local-scheduler-exec",
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
                "--execute-candidate",
                "--guard-checked",
                "--candidate-command-prefix",
                "definitely-not-python",
            )
        )
        assert cli_prefix_reject["ok"] is True, cli_prefix_reject
        assert cli_prefix_reject["execution"]["executed"] is False, cli_prefix_reject
        assert cli_prefix_reject["execution"]["reason"] == "candidate_command_prefix_mismatch", cli_prefix_reject

        cli_markdown = run_cli(
            "codex-cli-local-scheduler-exec",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--fixture",
            str(help_fixture),
        )
        assert "# Codex CLI Local Scheduler Executor" in cli_markdown, cli_markdown
        assert "reason: `no_execute_flag`" in cli_markdown, cli_markdown
        assert "candidate_output_captured: `False`" in cli_markdown, cli_markdown

    print("codex-cli-local-scheduler-exec-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
