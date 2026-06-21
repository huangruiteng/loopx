#!/usr/bin/env python3
"""Validate the public Codex CLI proof-capture demo fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
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
FIXTURE_DIR = REPO_ROOT / "examples" / "fixtures" / "codex-cli-visible-proof"


def load_fixture(name: str) -> dict[str, object]:
    path = FIXTURE_DIR / name
    return json.loads(path.read_text())


def command_outputs(name: str) -> dict[str, str]:
    payload = load_fixture(name)
    outputs = payload["command_outputs"]
    assert isinstance(outputs, dict), payload
    return {str(key): str(value) for key, value in outputs.items()}


def build_acceptance(
    help_fixture: str,
    proof_fixture: str,
    idle_fixture: str,
) -> dict[str, object]:
    return build_codex_cli_visible_attach_acceptance(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="loopx",
        codex_bin="codex",
        probe_payload=classify_codex_cli_session_surface(
            command_outputs=command_outputs(help_fixture)
        ),
        proof_payload=load_fixture(proof_fixture),
        idle_payload=load_fixture(idle_fixture),
    )


def run_cli_acceptance(
    help_fixture: str,
    proof_fixture: str,
    idle_fixture: str,
) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
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
            str(FIXTURE_DIR / help_fixture),
            "--proof-fixture",
            str(FIXTURE_DIR / proof_fixture),
            "--idle-fixture",
            str(FIXTURE_DIR / idle_fixture),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


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


def assert_visible_resume_spike(payload: dict[str, object]) -> None:
    assert payload["decision"] == "visible_surface_spike_passed_not_same_tui", payload
    assert payload["accepted_for_visible_later_turn"] is True, payload
    assert payload["accepted_for_same_tui_automation"] is False, payload
    assert payload["observed_surface"] == "visible_resume_prompt", payload
    assert "same_tui_visible_attach_not_proven" in payload["blockers"], payload
    assert_public_safe_boundary(payload)


def assert_same_tui_accepted(payload: dict[str, object]) -> None:
    assert payload["decision"] == "same_tui_visible_attach_accepted", payload
    assert payload["accepted_for_visible_later_turn"] is True, payload
    assert payload["accepted_for_same_tui_automation"] is True, payload
    assert payload["observed_surface"] == "same_tui_visible_attach", payload
    assert payload["blockers"] == [], payload
    assert_public_safe_boundary(payload)


def main() -> int:
    visible_resume = build_acceptance(
        "codex-visible-resume-help.public.json",
        "visible-resume-proof.public.json",
        "runtime-idle-visible-resume.public.json",
    )
    assert_visible_resume_spike(visible_resume)

    visible_resume_cli = run_cli_acceptance(
        "codex-visible-resume-help.public.json",
        "visible-resume-proof.public.json",
        "runtime-idle-visible-resume.public.json",
    )
    assert_visible_resume_spike(visible_resume_cli)

    same_tui = build_acceptance(
        "codex-same-tui-help.public.json",
        "same-tui-proof.public.json",
        "runtime-idle-same-tui.public.json",
    )
    assert_same_tui_accepted(same_tui)

    same_tui_cli = run_cli_acceptance(
        "codex-same-tui-help.public.json",
        "same-tui-proof.public.json",
        "runtime-idle-same-tui.public.json",
    )
    assert_same_tui_accepted(same_tui_cli)

    print("codex-cli-proof-capture-demo-fixtures-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
