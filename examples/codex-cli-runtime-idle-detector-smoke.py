#!/usr/bin/env python3
"""Smoke-test the Codex CLI runtime idle detector packet."""

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
    build_codex_cli_runtime_idle_detector,
    build_codex_cli_runtime_idle_observation_payload,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


PASSING_IDLE_FIXTURE = {
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


def build_idle(payload: dict[str, object] | None) -> dict[str, object]:
    return build_codex_cli_runtime_idle_detector(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        idle_payload=payload,
    )


def assert_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_stdout_stderr"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
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


def run_cli_fail_closed(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", *extra_args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    return result.stdout


def main() -> int:
    missing = build_idle(None)
    assert missing["ok"] is False, missing
    assert missing["schema_version"] == "codex_cli_runtime_idle_detector_v0", missing
    assert missing["decision"] == "runtime_idle_evidence_required", missing
    assert missing["approved_for_visible_later_turn"] is False, missing
    assert "missing_runtime_idle_evidence" in missing["failures"], missing
    assert_boundary(missing)

    failing_fixture = dict(PASSING_IDLE_FIXTURE)
    failing_fixture["idle_guard"] = dict(PASSING_IDLE_FIXTURE["idle_guard"])
    failing_fixture["idle_guard"]["no_running_turn"] = False
    incomplete = build_idle(failing_fixture)
    assert incomplete["ok"] is True, incomplete
    assert incomplete["decision"] == "runtime_idle_detector_incomplete", incomplete
    assert incomplete["approved_for_visible_later_turn"] is False, incomplete
    assert "idle_no_running_turn" in incomplete["failures"], incomplete
    assert_boundary(incomplete)

    passing = build_idle(PASSING_IDLE_FIXTURE)
    assert passing["ok"] is True, passing
    assert passing["decision"] == "runtime_idle_detector_passed", passing
    assert passing["approved_for_visible_later_turn"] is True, passing
    assert passing["observed_surface"] == "visible_resume_prompt", passing
    assert not passing["failures"], passing
    assert passing["source"] == "idle_fixture", passing
    assert passing["boundary"]["fixture_only"] is True, passing
    assert_boundary(passing)

    local_observation = build_codex_cli_runtime_idle_observation_payload(
        observed_surface="visible_resume_prompt",
        turn_state="idle",
        human_input_idle_seconds=12.0,
        min_human_input_idle_seconds=5.0,
        checked_before_prompt=True,
        visible_to_user=True,
        user_can_interrupt=True,
        manual_takeover_available=True,
        probe_result={"ok": True, "source": "test_idle_counter"},
    )
    local_passing = build_idle(local_observation)
    assert local_passing["ok"] is True, local_passing
    assert local_passing["decision"] == "runtime_idle_detector_passed", local_passing
    assert local_passing["approved_for_visible_later_turn"] is True, local_passing
    assert local_passing["source"] == "local_runtime_observation", local_passing
    assert local_passing["boundary"]["fixture_only"] is False, local_passing
    assert local_passing["boundary"]["local_observation_adapter_supported"] is True, local_passing
    runtime_observation = local_passing["runtime_observation"]
    assert runtime_observation["human_input_idle_seconds"] == 12.0, local_passing
    assert runtime_observation["turn_state"] == "idle", local_passing
    assert_boundary(local_passing)

    local_unknown_turn = build_idle(
        build_codex_cli_runtime_idle_observation_payload(
            observed_surface="visible_resume_prompt",
            turn_state="unknown",
            human_input_idle_seconds=12.0,
            min_human_input_idle_seconds=5.0,
            checked_before_prompt=True,
            visible_to_user=True,
            user_can_interrupt=True,
            manual_takeover_available=True,
        )
    )
    assert local_unknown_turn["decision"] == "runtime_idle_detector_incomplete", local_unknown_turn
    assert "idle_no_running_turn" in local_unknown_turn["failures"], local_unknown_turn

    local_recent_input = build_idle(
        build_codex_cli_runtime_idle_observation_payload(
            observed_surface="visible_resume_prompt",
            turn_state="idle",
            human_input_idle_seconds=1.0,
            min_human_input_idle_seconds=5.0,
            checked_before_prompt=True,
            visible_to_user=True,
            user_can_interrupt=True,
            manual_takeover_available=True,
        )
    )
    assert local_recent_input["decision"] == "runtime_idle_detector_incomplete", local_recent_input
    assert "idle_no_human_typing" in local_recent_input["failures"], local_recent_input

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-runtime-idle-") as tmp:
        fixture = Path(tmp) / "runtime-idle.json"
        fixture.write_text(json.dumps(PASSING_IDLE_FIXTURE))

        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-runtime-idle-detector",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--idle-fixture",
                str(fixture),
            )
        )
        assert cli_json["decision"] == "runtime_idle_detector_passed", cli_json
        assert cli_json["approved_for_visible_later_turn"] is True, cli_json
        assert_boundary(cli_json)

        cli_local_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-runtime-idle-detector",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--observe-local-runtime",
                "--observed-surface",
                "visible_resume_prompt",
                "--turn-state",
                "idle",
                "--human-input-idle-seconds",
                "12",
                "--min-human-input-idle-seconds",
                "5",
                "--checked-before-prompt",
                "--visible-to-user",
                "--user-can-interrupt",
                "--manual-takeover-available",
            )
        )
        assert cli_local_json["decision"] == "runtime_idle_detector_passed", cli_local_json
        assert cli_local_json["source"] == "local_runtime_observation", cli_local_json
        assert cli_local_json["runtime_observation"]["human_input_idle_seconds"] == 12.0, cli_local_json
        assert_boundary(cli_local_json)

        cli_markdown = run_cli_fail_closed(
            "codex-cli-runtime-idle-detector",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
        )
        assert "# Codex CLI Runtime Idle Detector" in cli_markdown, cli_markdown
        assert "runtime_idle_evidence_required" in cli_markdown, cli_markdown
        assert "reads_stdout_stderr: `False`" in cli_markdown, cli_markdown

    print("codex-cli-runtime-idle-detector-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
