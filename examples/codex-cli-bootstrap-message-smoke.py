#!/usr/bin/env python3
"""Smoke-test Codex CLI TUI bootstrap message generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.project_prompt import build_codex_cli_bootstrap_message  # noqa: E402


PROJECT = Path("/tmp/public-codex-cli-project")
GOAL_ID = "public-codex-cli-goal"
AGENT_ID = "codex-side-bypass"

MUST_HAVE = (
    "one-message TUI bootstrap",
    "same Codex CLI TUI session",
    "hidden headless `codex exec`",
    "explicit fallback",
    "current goal id",
    "top user todo",
    "top agent todo",
    "next safe action",
    "goal-harness doctor",
    "goal-harness bootstrap",
    "quota should-run",
    "--agent-id codex-side-bypass",
    "interaction_contract",
    "user_channel.action_required=true",
    "workspace_guard",
    "independent worktree",
    "runnable agent todo",
    "Do not store raw Codex transcripts",
    "refresh-state",
    "quota spend-slot",
    "--source controller",
    "not first-run prerequisites",
)


def assert_message_contract(payload: dict[str, object]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "codex_cli_bootstrap_message_v0", payload
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["agent_id"] == AGENT_ID, payload
    message = str(payload["message"])
    normalized = " ".join(message.split())
    for phrase in MUST_HAVE:
        assert phrase in normalized, (phrase, message)
    assert normalized.index("quota should-run") < normalized.index("interaction_contract"), message
    assert normalized.index("workspace_guard") < normalized.index("independent worktree"), message
    assert normalized.index("refresh-state") < normalized.index("quota spend-slot"), message
    assert "Headless fallback should never be the only way" not in message, message
    assert "quota spend-slot --goal-id public-codex-cli-goal --slots 1 --source controller --execute --agent-id codex-side-bypass" in message, message


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def assert_docs_surface_codex_cli_quickstart() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    getting_started = (REPO_ROOT / "docs/guides/getting-started.md").read_text(encoding="utf-8")
    product_contract = (REPO_ROOT / "docs/product/codex-cli-tui-loop.md").read_text(encoding="utf-8")

    for text in (readme, getting_started, product_contract):
        assert "Codex CLI" in text and "TUI" in text, text[:500]
        assert "Start Goal Harness for this repo" in text, text[:500]
        assert "goal-harness codex-cli-bootstrap-message --project . --goal-id <goal-id>" in text, text[:500]

    normalized_readme = " ".join(readme.split())
    normalized_getting_started = " ".join(getting_started.split())
    normalized_product_contract = " ".join(product_contract.split())
    assert "Headless `codex exec` is an explicit fallback" in normalized_readme, readme
    assert "paste one message" in normalized_readme, readme
    assert "show the current goal, user gate, top todos, and next safe action" in normalized_readme, readme
    assert "first-run path should not require you to understand registry paths" in normalized_getting_started, getting_started
    assert "optional automation checks after the one-message path works" in normalized_getting_started, getting_started
    assert "first useful TUI response should be a control-plane snapshot" in normalized_product_contract, product_contract
    assert "goal-harness codex-cli-session-probe" in getting_started, getting_started
    assert "goal-harness codex-cli-exec-handoff --project . --goal-id <goal-id>" in getting_started, getting_started


def main() -> int:
    payload = build_codex_cli_bootstrap_message(
        project=PROJECT,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        cli_bin="goal-harness",
    )
    assert_message_contract(payload)

    cli_json = json.loads(
        run_cli(
            "--format",
            "json",
            "codex-cli-bootstrap-message",
            "--project",
            str(PROJECT),
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
        )
    )
    assert_message_contract(cli_json)

    cli_markdown = run_cli(
        "codex-cli-bootstrap-message",
        "--project",
        str(PROJECT),
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert "# Codex CLI Goal Harness Bootstrap Message" in cli_markdown, cli_markdown
    assert "Copy the block below into Codex CLI TUI" in cli_markdown, cli_markdown
    assert "one-message TUI bootstrap" in cli_markdown, cli_markdown
    assert_docs_surface_codex_cli_quickstart()

    print("codex-cli-bootstrap-message-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
