#!/usr/bin/env python3
"""Smoke-test side-agent workspace guard in quota should-run."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import (  # noqa: E402
    build_quota_should_run,
    build_quota_slot_preview,
    render_quota_should_run_markdown,
)


GOAL_ID = "side-agent-workspace-goal"
PRIMARY_TODO = "Run the primary benchmark rotation."
UNCLAIMED_TODO = "Triage an unclaimed coordination task."
SIDE_TODO = "Continue the side-agent productization docs lane."


@contextmanager
def pushd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def run_git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def init_repo(primary: Path, side: Path) -> None:
    primary.mkdir(parents=True)
    run_git(primary, "init")
    run_git(primary, "config", "user.email", "loopx@example.invalid")
    run_git(primary, "config", "user.name", "LoopX Smoke")
    (primary / "README.md").write_text("fixture\n", encoding="utf-8")
    run_git(primary, "add", "README.md")
    run_git(primary, "commit", "-m", "initial fixture")
    run_git(primary, "worktree", "add", str(side), "-b", "side-fixture")


def status_payload(repo: Path, registry: Path) -> dict:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 1440,
        "spent_slots": 0,
        "state": "eligible",
        "reason": "fixture eligible quota",
    }
    coordination = {
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
        "primary_agent": "codex-main-control",
    }
    goal = {
        "id": GOAL_ID,
        "registry_member": True,
        "status": "active",
        "adapter_kind": "harness_self_improvement",
        "adapter_status": "connected-read-only",
        "coordination": coordination,
        "quota": quota,
        "latest_runs": [
            {
                "generated_at": "2026-06-20T00:00:00+08:00",
                "classification": "state_refreshed",
                "recommended_action": "Advance one public-safe side-agent slice.",
            }
        ],
    }
    item = {
        "goal_id": GOAL_ID,
        "status": "state_refreshed",
        "waiting_on": "codex",
        "severity": "action",
        "source": "fixture",
        "recommended_action": "Advance one public-safe side-agent slice.",
        "quota": quota,
        "project_asset": {
            "next_action": PRIMARY_TODO,
            "agent_todos": {
                "schema_version": "todo_summary_v0",
                "total_count": 3,
                "open_count": 3,
                "done_count": 0,
                "items": [
                    {
                        "index": 1,
                        "text": PRIMARY_TODO,
                        "schema_version": "todo_item_v0",
                        "todo_id": "todo_primary",
                        "role": "agent",
                        "status": "open",
                        "priority": "P0",
                        "task_class": "advancement_task",
                        "action_kind": "benchmark_rotation",
                        "claimed_by": "codex-main-control",
                    },
                    {
                        "index": 2,
                        "text": UNCLAIMED_TODO,
                        "schema_version": "todo_item_v0",
                        "todo_id": "todo_unclaimed",
                        "role": "agent",
                        "status": "open",
                        "priority": "P1",
                        "task_class": "advancement_task",
                        "action_kind": "coordination_task",
                    },
                    {
                        "index": 3,
                        "text": SIDE_TODO,
                        "schema_version": "todo_item_v0",
                        "todo_id": "todo_side",
                        "role": "agent",
                        "status": "open",
                        "priority": "P2",
                        "task_class": "advancement_task",
                        "action_kind": "productization_docs",
                        "claimed_by": "codex-side-bypass",
                    },
                ],
            },
        },
    }
    return {
        "ok": True,
        "registry": str(registry),
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "attention_queue": {"items": [item]},
        "run_history": {"goals": [goal]},
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-workspace-guard-") as tmp:
        root = Path(tmp)
        primary = root / "primary"
        side = root / "side-worktree"
        foreign = root / "foreign"
        registry = root / "registry.global.json"
        init_repo(primary, side)
        registry.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": GOAL_ID,
                            "repo": str(primary),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        foreign.mkdir(parents=True)
        run_git(foreign, "init")

        payload = status_payload(primary, registry)

        with pushd(primary):
            guarded = build_quota_should_run(
                payload,
                goal_id=GOAL_ID,
                agent_id="codex-side-bypass",
            )
            markdown = render_quota_should_run_markdown(guarded)
            preview = build_quota_slot_preview(
                payload,
                goal_id=GOAL_ID,
                agent_id="codex-side-bypass",
            )
            primary_agent = build_quota_should_run(
                payload,
                goal_id=GOAL_ID,
                agent_id="codex-main-control",
            )

        assert guarded["should_run"] is True, guarded
        assert guarded["normal_delivery_allowed"] is False, guarded
        assert guarded["workspace_repair_allowed"] is True, guarded
        assert guarded["effective_action"] == "side_agent_workspace_repair", guarded
        assert guarded["workspace_guard"]["current_workspace"] == "primary_checkout", guarded
        assert guarded["interaction_contract"]["mode"] == "side_agent_workspace_repair", guarded
        assert guarded["interaction_contract"]["agent_channel"]["delivery_allowed"] is False, guarded
        assert guarded["interaction_contract"]["cli_channel"]["spend_after_validation"] is False, guarded
        assert "workspace_guard: action=move_to_independent_worktree" in markdown, markdown
        assert preview["ok"] is False, preview
        assert "independent worktree" in preview["reason"], preview
        assert primary_agent["normal_delivery_allowed"] is True, primary_agent
        assert "workspace_guard" not in primary_agent, primary_agent
        assert primary_agent["recommended_action"] == PRIMARY_TODO, primary_agent

        with pushd(side):
            side_ok = build_quota_should_run(
                payload,
                goal_id=GOAL_ID,
                agent_id="codex-side-bypass",
            )
        assert side_ok["normal_delivery_allowed"] is True, side_ok
        assert "workspace_guard" not in side_ok, side_ok
        assert side_ok["recommended_action"] == SIDE_TODO, side_ok
        assert "state_action_projection_warning" not in side_ok, side_ok
        side_summary = side_ok["agent_todo_summary"]
        assert side_summary["first_executable_items"][0]["todo_id"] == "todo_side", side_summary
        assert side_summary["claim_scope"]["current_agent_claimed_open_count"] == 1, side_summary
        assert side_summary["claim_scope"]["blocked_claimed_items"][0]["todo_id"] == "todo_primary", side_summary

        with pushd(foreign):
            foreign_guarded = build_quota_should_run(
                payload,
                goal_id=GOAL_ID,
                agent_id="codex-side-bypass",
            )
        assert foreign_guarded["normal_delivery_allowed"] is False, foreign_guarded
        assert foreign_guarded["workspace_guard"]["current_workspace"] == "foreign_git_worktree", foreign_guarded

    print("side-agent-workspace-guard-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
