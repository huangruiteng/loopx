#!/usr/bin/env python3
"""Smoke-test the LoopX slash command catalog and CLI help."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def main() -> int:
    payload = json.loads(run_cli("--format", "json", "slash-commands").stdout)
    assert payload["schema_version"] == "loopx_slash_command_catalog_v0", payload
    assert payload["canonical_prefix"] == "/loopx", payload
    commands = {item["command"]: item for item in payload["commands"]}
    for command in [
        "/loopx",
        "/loopx <goal text>",
        "/loopx-global-summary",
        "/loopx-global-gates",
        "/loopx-global-todos",
        "/loopx-global-risks",
        "/loopx-pr-review",
    ]:
        assert command in commands, commands
    assert "/loop-global-summary" in commands["/loopx-global-summary"]["legacy_aliases"]
    assert "/loopx-summary-all" not in json.dumps(payload)
    pr_review = commands["/loopx-pr-review"]
    assert pr_review["agent_contract"]["must_run_cli_first"] is True, pr_review
    assert "loopx pr-review" in pr_review["agent_contract"]["primary_cli"], pr_review
    assert "review_groups.unmerged" in pr_review["agent_contract"]["authoritative_fields"], pr_review
    assert "review_groups.merged" in pr_review["agent_contract"]["authoritative_fields"], pr_review
    assert "do not reconstruct" in pr_review["agent_contract"]["manual_gh_policy"], pr_review
    onboarding = payload["onboarding"]
    assert onboarding["tell_new_users"] is True, onboarding
    assert "CLI help: `loopx slash-commands`." in onboarding["suggested_user_note"], onboarding

    compact = json.loads(run_cli("--format", "json", "slash-commands", "--no-legacy-aliases").stdout)
    compact_text = json.dumps(compact)
    assert "/loop-global-summary" not in compact_text, compact

    markdown = run_cli("slash-commands").stdout
    assert "# LoopX Slash Commands" in markdown, markdown
    assert "`/loopx-global-summary`" in markdown, markdown
    assert "`loopx global-summary`" in markdown, markdown
    assert "`/loopx-pr-review`" in markdown, markdown
    assert "`loopx pr-review [--repo owner/repo] [--state open\\|merged\\|all] [--since ISO]`" in markdown, markdown
    assert "Agent contract: run the CLI reference first" in markdown, markdown
    assert "`/loopx-summary-all`" not in markdown, markdown

    top_help = run_cli("--help").stdout
    assert "slash-commands" in top_help, top_help

    print("slash-command-catalog-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
