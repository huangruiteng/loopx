#!/usr/bin/env python3
"""Smoke-test the reusable heartbeat automation prompt contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.heartbeat_prompt import build_heartbeat_prompt  # noqa: E402

DOC = REPO_ROOT / "docs" / "heartbeat-automation-prompt.md"
README = REPO_ROOT / "README.md"
GOAL_ID = "public-heartbeat-goal"
ACTIVE_STATE = Path("/tmp/public-heartbeat-goal/ACTIVE_GOAL_STATE.md")


def normalized(text: str) -> str:
    return " ".join(text.split())


def assert_ordered(text: str, phrases: tuple[str, ...]) -> None:
    compact = normalized(text)
    positions = []
    for phrase in phrases:
        assert phrase in compact, phrase
        positions.append(compact.index(phrase))
    assert positions == sorted(positions), positions


def main() -> int:
    payload = build_heartbeat_prompt(goal_id=GOAL_ID, active_state=ACTIVE_STATE)
    assert payload["quota_guard_command"] == (
        "goal-harness --format json quota should-run --goal-id public-heartbeat-goal"
    ), payload
    assert payload["quota_spend_command"] == (
        "goal-harness quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute"
    ), payload

    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    generated = str(payload["task_body"])

    must_have = (
        "<ACTIVE_GOAL_STATE_PATH>",
        "<GOAL_ID>",
        "goal-harness --format json quota should-run --goal-id <GOAL_ID>",
        "should_run=false",
        "DONT_NOTIFY",
        "do not do implementation work, adapter work, file edits, research, or project exploration",
        "should_run=true",
        "Choose exactly one bounded, verifiable step",
        "Run the smallest useful validation",
        "Write back changed files, validation, critic, and next action",
        "goal-harness refresh-state --goal-id <GOAL_ID>",
        "goal-harness quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute",
        "append exactly one",
        "Do not append spend for should_run=false skips, preflight failures, pure dry-run previews, or duplicate accounting attempts",
        "Return a compact final report",
    )
    compact_doc = normalized(doc)
    for phrase in must_have:
        assert phrase in compact_doc, phrase
    for phrase in (
        "goal-harness --format json quota should-run --goal-id public-heartbeat-goal",
        "should_run=false",
        "DONT_NOTIFY",
        "Choose exactly one bounded, verifiable step",
        "goal-harness refresh-state --goal-id public-heartbeat-goal",
        "goal-harness quota spend-slot --goal-id public-heartbeat-goal --slots 1 --source heartbeat --execute",
        "Do not append spend for `should_run=false` skips",
    ):
        assert phrase in generated, phrase

    assert_ordered(
        doc,
        (
            "Before spending delivery compute, run:",
            "If the result says should_run=false",
            "If the result says should_run=true",
            "Run the smallest useful validation",
            "goal-harness refresh-state --goal-id <GOAL_ID>",
            "goal-harness quota spend-slot --goal-id <GOAL_ID> --slots 1 --source heartbeat --execute",
            "Return a compact final report",
        ),
    )

    assert "docs/heartbeat-automation-prompt.md" in readme, readme
    assert "goal-harness heartbeat-prompt" in readme, readme
    assert "goal-harness heartbeat-prompt" in doc, doc

    cli_json = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--format",
            "json",
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(ACTIVE_STATE),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cli_payload = json.loads(cli_json.stdout)
    assert cli_payload["task_body"] == payload["task_body"], cli_payload

    cli_markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            "--active-state",
            str(ACTIVE_STATE),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "# Heartbeat Automation Prompt" in cli_markdown, cli_markdown
    assert "Copy this task body into a Codex App heartbeat automation." in cli_markdown, cli_markdown
    assert str(ACTIVE_STATE) in cli_markdown, cli_markdown
    print("heartbeat-prompt-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
