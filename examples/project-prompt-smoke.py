#!/usr/bin/env python3
"""Smoke-test the new-project handoff prompt quota guard."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.project_prompt import build_new_project_prompt  # noqa: E402


DOC = REPO_ROOT / "docs/new-project-codex-prompt.md"
GOAL_ID = "new-project-main-control"
PROJECT = Path("/tmp/public-example-project")
GOAL_DOC = Path("/tmp/public-example-project/GOAL.md")
MUST_HAVE = (
    "不要执行任何 `agent_command`",
    "只有当返回 `should_run=true` 且 payload 里包含 `agent_command` 时，才执行该命令。",
    "如果 `should_run=true` 但没有 `agent_command`，只按 `recommended_action` 选择下一个安全只读动作。",
)


def assert_quota_guard(text: str) -> None:
    normalized = " ".join(text.split())
    assert "goal-harness --format json quota should-run --goal-id" in text, text
    positions = []
    for phrase in MUST_HAVE:
        assert phrase in normalized, text
        positions.append(normalized.index(phrase))
    assert positions == sorted(positions), positions


def run_cli(*extra_args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *extra_args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def cli_prompt_args() -> list[str]:
    return [
        "new-project-prompt",
        "--project",
        str(PROJECT),
        "--goal-doc",
        str(GOAL_DOC),
        "--goal-id",
        GOAL_ID,
        "--objective",
        "Public example objective",
        "--domain",
        "example",
    ]


def main() -> int:
    payload = build_new_project_prompt(
        project=PROJECT,
        goal_doc=GOAL_DOC,
        goal_id=GOAL_ID,
        objective="Public example objective",
        domain="example",
        adapter_kind="read_only_project_map_v0",
        adapter_status="connected-read-only",
        next_probe=None,
        spawn_allowed=False,
        allowed_domains=None,
        write_scope=None,
    )
    assert payload["quota_guard_command"] == (
        "goal-harness --format json quota should-run --goal-id new-project-main-control"
    ), payload
    assert_quota_guard(payload["prompt"])
    assert_quota_guard(DOC.read_text(encoding="utf-8"))

    cli_json = json.loads(run_cli("--format", "json", *cli_prompt_args()))
    assert cli_json["quota_guard_command"] == payload["quota_guard_command"], cli_json
    assert_quota_guard(cli_json["prompt"])

    cli_markdown = run_cli(*cli_prompt_args())
    assert "# New Project Codex Handoff Prompt" in cli_markdown, cli_markdown
    assert_quota_guard(cli_markdown)
    print("project-prompt-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
