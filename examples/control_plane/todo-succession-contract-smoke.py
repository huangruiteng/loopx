#!/usr/bin/env python3
"""Smoke-test completed todo succession warnings in status and quota views."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.control_plane.todos.succession_warning import (  # noqa: E402
    build_todo_succession_warning_lanes,
)


GOAL_ID = "todo-succession-contract-fixture"
AGENT_ID = "codex-product-capability"


def build_agent_todos() -> dict:
    summary = quota_todo_summary(
        [
            quota_todo_item(
                todo_id="todo_open_next",
                text="[P1] Continue the next canary-backed control-plane cleanup.",
                priority="P1",
                claimed_by=AGENT_ID,
            ),
            quota_todo_item(
                todo_id="todo_missing_successor",
                text="[P1] Complete a tracked canary cleanup without recording the next slice.",
                status="done",
                priority="P1",
                action_kind="canary_gated_control_plane_cleanup",
                claimed_by=AGENT_ID,
                updated_at="2026-07-04T20:00:00+08:00",
            ),
            quota_todo_item(
                todo_id="todo_no_followup",
                text="[P2] Complete a tracked cleanup that intentionally needs no follow-up.",
                status="done",
                priority="P2",
                action_kind="documentation_cleanup",
                claimed_by=AGENT_ID,
                no_followup=True,
                updated_at="2026-07-04T19:00:00+08:00",
            ),
            quota_todo_item(
                todo_id="todo_with_successor",
                text="[P2] Complete a tracked cleanup and link the next slice.",
                status="done",
                priority="P2",
                action_kind="projection_cleanup",
                claimed_by=AGENT_ID,
                updated_at="2026-07-04T18:00:00+08:00",
            ),
            quota_todo_item(
                todo_id="todo_with_explicit_successor",
                text="[P2] Complete a tracked cleanup and link existing successor metadata.",
                status="done",
                priority="P2",
                action_kind="projection_cleanup",
                claimed_by=AGENT_ID,
                successor_todo_ids=["todo_explicit_successor"],
                updated_at="2026-07-04T17:30:00+08:00",
            ),
            quota_todo_item(
                todo_id="todo_successor",
                text="[P2] Continue after the linked cleanup.",
                priority="P2",
                claimed_by=AGENT_ID,
                resume_when="todo_done:todo_with_successor",
            ),
            quota_todo_item(
                todo_id="todo_explicit_successor",
                text="[P2] Continue after the explicit successor link.",
                priority="P2",
                claimed_by=AGENT_ID,
            ),
            {
                "todo_id": "todo_legacy_done",
                "index": 6,
                "status": "done",
                "done": True,
                "role": "agent",
                "task_class": "advancement_task",
                "text": "[P3] Legacy markdown checkbox without tracking metadata.",
            },
        ],
        role="agent",
    )
    return summary


def status_payload(agent_todos: dict) -> dict:
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Continue the next canary-backed cleanup.",
        agent_todos=agent_todos,
        source="active_state",
        registry_status="active",
        coordination={
            "primary_agent": "codex-main-control",
            "registered_agents": ["codex-main-control", AGENT_ID],
        },
        latest_runs=[],
        goal_extra={
            "adapter_kind": "fixture_adapter_v0",
            "adapter_status": "connected",
        },
    )


def assert_status_summary_warning() -> None:
    summary = build_agent_todos()
    assert summary["completed_without_successor_count"] == 1, summary
    warning = summary["todo_succession_warning"]
    assert warning["schema_version"] == "todo_succession_warning_v0", warning
    assert warning["reason_code"] == "completed_advancement_without_successor", warning
    assert warning["items"][0]["todo_id"] == "todo_missing_successor", warning
    assert warning["items"][0]["succession_tracked"] is True, warning
    assert "todo_no_followup" not in {
        item["todo_id"] for item in warning["items"] if item.get("todo_id")
    }, warning
    assert "todo_with_successor" not in {
        item["todo_id"] for item in warning["items"] if item.get("todo_id")
    }, warning
    assert "todo_with_explicit_successor" not in {
        item["todo_id"] for item in warning["items"] if item.get("todo_id")
    }, warning
    assert "todo_legacy_done" not in {
        item["todo_id"] for item in warning["items"] if item.get("todo_id")
    }, warning


def assert_quota_projects_warning() -> None:
    payload = build_quota_should_run(
        status_payload(build_agent_todos()),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert payload["decision"] == "run", payload
    warning = payload["agent_todo_summary"]["todo_succession_warning"]
    assert warning["count"] == 1, payload
    assert warning["items"][0]["todo_id"] == "todo_missing_successor", payload
    markdown = render_quota_should_run_markdown(payload)
    assert "agent_todo_succession_warning" in markdown, markdown
    assert "todo_missing_successor" in markdown, markdown


def assert_quota_warning_lanes_strip_transient_evidence() -> None:
    lanes = build_todo_succession_warning_lanes(
        {
            "todo_succession_warning": {
                "count": 1,
                "items": [
                    {
                        "todo_id": "todo_missing_successor",
                        "text": "[P1] Missing successor.",
                        "note": "operator-only note should not project",
                        "evidence": "local run evidence should not project",
                        "reason": "local rationale should not project",
                        "required_write_scopes": "loopx/quota.py,../unsafe-scope.txt",
                        "decision_scope": "write_scope:goal:loopx-meta",
                        "required_decision_scopes": (
                            "private_read:goal:loopx-meta,private_read:goal:loopx-meta"
                        ),
                        "action_kind": "monitor",
                        "succession_tracked": True,
                    }
                ],
            }
        },
        item_limit=8,
    )
    item = lanes["todo_succession_warning"]["items"][0]
    assert item["todo_id"] == "todo_missing_successor", lanes
    assert item["succession_tracked"] is True, lanes
    assert "note" not in item, lanes
    assert "evidence" not in item, lanes
    assert "reason" not in item, lanes
    assert item["required_write_scopes"] == ["loopx/quota.py"], lanes
    assert item["decision_scope"]["kind"] == "write_scope", lanes
    assert item["required_decision_scopes"] == [
        {
            "schema_version": "decision_scope_v0",
            "kind": "private_read",
            "granularity": "goal",
            "scope_key": "loopx-meta",
        }
    ], lanes
    assert item["task_class"] == "continuous_monitor", lanes


def main() -> int:
    assert_status_summary_warning()
    assert_quota_projects_warning()
    assert_quota_warning_lanes_strip_transient_evidence()
    print("todo-succession-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
