#!/usr/bin/env python3
"""Smoke-test the Codex CLI visible session proof contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.codex_cli_probe import build_codex_cli_visible_session_proof  # noqa: E402


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"


PASSING_PROOF = {
    "observed_surface": "visible_resume_prompt",
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


FAILING_PROOF = {
    **PASSING_PROOF,
    "observed_surface": "headless_exec",
    "idle_guard": {
        "no_active_human_typing": True,
        "no_running_turn": False,
        "checked_before_prompt": True,
    },
    "boundary": {
        **PASSING_PROOF["boundary"],
        "reads_session_files": True,
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


def assert_common_boundary(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == "codex_cli_visible_session_proof_v0", payload
    assert payload["project"] == str(PROJECT), payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["agent_id"] == AGENT_ID, payload
    boundary = payload["boundary"]
    assert boundary["fixture_only"] is True, payload
    assert boundary["runs_codex"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["mutates_codex_session"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload


def build(proof: dict[str, object] | None) -> dict[str, object]:
    return build_codex_cli_visible_session_proof(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        proof_payload=proof,
    )


def main() -> int:
    missing = build(None)
    assert missing["ok"] is False, missing
    assert_common_boundary(missing)
    assert missing["decision"] == "proof_fixture_required", missing
    assert missing["approved_for_same_session_automation"] is False, missing
    assert "required_fixture_shape" in missing, missing

    passing = build(PASSING_PROOF)
    assert passing["ok"] is True, passing
    assert_common_boundary(passing)
    assert passing["decision"] == "visible_session_proof_passed", passing
    assert passing["approved_for_same_session_automation"] is True, passing
    assert passing["failures"] == [], passing
    assert all(check["passed"] for check in passing["checks"]), passing

    failing = build(FAILING_PROOF)
    assert failing["ok"] is True, failing
    assert_common_boundary(failing)
    assert failing["decision"] == "visible_session_proof_incomplete", failing
    assert failing["approved_for_same_session_automation"] is False, failing
    assert "idle_no_running_turn" in failing["failures"], failing
    assert "no_session_files_read" in failing["failures"], failing
    assert "unsupported_observed_surface" in failing["failures"], failing

    with tempfile.TemporaryDirectory(prefix="loopx-codex-cli-visible-proof-") as tmp:
        fixture = Path(tmp) / "visible-proof.json"
        fixture.write_text(json.dumps(PASSING_PROOF))
        cli_json = json.loads(
            run_cli(
                "--format",
                "json",
                "codex-cli-visible-session-proof",
                "--project",
                str(PROJECT),
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--proof-fixture",
                str(fixture),
            )
        )
        assert cli_json["approved_for_same_session_automation"] is True, cli_json
        assert cli_json["observed_surface"] == "visible_resume_prompt", cli_json

        cli_markdown = run_cli(
            "codex-cli-visible-session-proof",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--proof-fixture",
            str(fixture),
        )
        assert "# Codex CLI Visible Session Proof" in cli_markdown, cli_markdown
        assert "approved_for_same_session_automation: `True`" in cli_markdown, cli_markdown
        assert "- [x] visible_to_user" in cli_markdown, cli_markdown

    print("codex-cli-visible-session-proof-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
