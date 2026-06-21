#!/usr/bin/env python3
"""Smoke-test the Codex CLI bounded visible pilot adapter packet."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.codex_cli_probe import (  # noqa: E402
    build_codex_cli_bounded_visible_pilot_adapter,
)


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"
LIVE_PILOT_DOC = REPO_ROOT / "docs" / "product" / "codex-cli-live-tui-first-message-pilot.md"
PRODUCT_README = REPO_ROOT / "docs" / "product" / "README.md"


PASSING_FIRST_RESPONSE_FIXTURE = {
    "observed_surface": "codex_cli_tui_visible_window",
    "prompt_delivery": {
        "manual_or_visible_delivery": True,
        "prompt_public_safe": True,
        "argv_prompt_used": False,
    },
    "first_response": {
        "goal_id_visible": True,
        "user_gate_or_none_visible": True,
        "top_user_todo_or_none_visible": True,
        "top_agent_todo_visible": True,
        "next_safe_action_visible": True,
        "bounded_segment_started_or_blocker_written": True,
    },
    "interruptibility": {
        "user_can_interrupt": True,
        "manual_takeover_available": True,
    },
    "writeback": {
        "compact_evidence_planned": True,
        "quota_spend_after_writeback_only": True,
    },
    "boundary": {
        "reads_raw_transcripts": False,
        "reads_session_files": False,
        "reads_stdout_stderr": False,
        "reads_credentials": False,
        "mutates_hidden_session_state": False,
        "spends_quota_before_writeback": False,
    },
}


PASSING_IDLE_FIXTURE = {
    "observed_surface": "codex_cli_tui_visible_window",
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


def build_adapter(
    *,
    first_response: dict[str, object] | None = None,
    idle: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_codex_cli_bounded_visible_pilot_adapter(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="goal-harness",
        first_response_payload=first_response,
        idle_payload=idle,
    )


def assert_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert boundary["adapter_packet_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_stdout_stderr"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["writes_goal_harness_state"] is False, payload
    assert boundary["spends_goal_harness_quota"] is False, payload
    assert boundary["requires_visible_delivery"] is True, payload
    assert boundary["argv_prompt_rejected"] is True, payload
    assert boundary["success_claim_requires_first_response_and_idle"] is True, payload


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_docs() -> None:
    live_pilot = LIVE_PILOT_DOC.read_text(encoding="utf-8")
    product_readme = PRODUCT_README.read_text(encoding="utf-8")
    assert "codex-cli-bounded-visible-pilot-adapter" in live_pilot, live_pilot
    assert "public-first-response.json" in live_pilot, live_pilot
    assert "argv prompt" in live_pilot, live_pilot
    assert "Codex CLI bounded visible pilot adapter" in product_readme, product_readme
    assert "codex-cli-bounded-visible-pilot-adapter-smoke.py" in product_readme, product_readme


def main() -> int:
    missing = build_adapter()
    assert missing["ok"] is True, missing
    assert missing["schema_version"] == "codex_cli_bounded_visible_pilot_adapter_v0", missing
    assert missing["decision"] == "bounded_visible_completion_evidence_required", missing
    assert missing["approved_for_live_tui_success_claim"] is False, missing
    assert "missing_first_response_evidence" in missing["blockers"], missing
    assert "missing_runtime_idle_evidence" in missing["blockers"], missing
    assert "codex-cli-bootstrap-message" in missing["commands"]["bootstrap_message"], missing
    assert "codex-cli-bounded-visible-pilot-adapter" in missing["commands"]["bounded_visible_pilot_adapter"], missing
    assert_boundary(missing)

    argv_leaking = copy.deepcopy(PASSING_FIRST_RESPONSE_FIXTURE)
    argv_leaking["prompt_delivery"]["argv_prompt_used"] = True
    rejected = build_adapter(first_response=argv_leaking, idle=PASSING_IDLE_FIXTURE)
    assert rejected["decision"] == "bounded_visible_first_response_incomplete", rejected
    assert rejected["approved_for_live_tui_success_claim"] is False, rejected
    assert "no_argv_prompt" in rejected["blockers"], rejected
    assert "argv_prompt_leakage_risk" in rejected["blockers"], rejected
    assert rejected["runtime_idle_detector"]["approved"] is True, rejected
    assert_boundary(rejected)

    passing = build_adapter(
        first_response=PASSING_FIRST_RESPONSE_FIXTURE,
        idle=PASSING_IDLE_FIXTURE,
    )
    assert passing["decision"] == "bounded_visible_pilot_ready_for_success_claim", passing
    assert passing["approved_for_live_tui_success_claim"] is True, passing
    assert passing["first_response"]["approved"] is True, passing
    assert passing["runtime_idle_detector"]["approved"] is True, passing
    assert passing["blockers"] == [], passing
    assert "--delivery-outcome outcome_progress" in passing["commands"]["success_writeback"], passing
    assert_boundary(passing)

    with tempfile.TemporaryDirectory(prefix="goal-harness-codex-cli-bounded-visible-") as tmp:
        tmp_path = Path(tmp)
        first_response_fixture = tmp_path / "public-first-response.json"
        first_response_fixture.write_text(json.dumps(PASSING_FIRST_RESPONSE_FIXTURE))
        idle_fixture = tmp_path / "public-runtime-idle.json"
        idle_fixture.write_text(json.dumps(PASSING_IDLE_FIXTURE))

        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-bounded-visible-pilot-adapter",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--first-response-fixture",
                str(first_response_fixture),
                "--idle-fixture",
                str(idle_fixture),
            )
        )
        assert cli_json["decision"] == "bounded_visible_pilot_ready_for_success_claim", cli_json
        assert cli_json["approved_for_live_tui_success_claim"] is True, cli_json
        assert_boundary(cli_json)

        markdown = run_cli(
            "codex-cli-bounded-visible-pilot-adapter",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--first-response-fixture",
            str(first_response_fixture),
            "--idle-fixture",
            str(idle_fixture),
        )
        assert "# Codex CLI Bounded Visible Pilot Adapter" in markdown, markdown
        assert "approved_for_live_tui_success_claim" in markdown, markdown
        assert "argv_prompt_rejected" in markdown, markdown

    assert_docs()
    print("codex-cli-bounded-visible-pilot-adapter-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
