#!/usr/bin/env python3
"""Smoke-test active-state field projection into project_asset."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.project_asset import (  # noqa: E402
    attach_active_state_project_asset_fields,
)


def main() -> int:
    item = {
        "project_asset": {"goal_id": "fixture-goal"},
        "active_state_next_action": "[P1] Keep active-state projection stable.",
        "latest_run_recommended_action": "[P1] Old run recommendation.",
        "issue_meta_surface": {"issue_count": 1},
        "backlog_hygiene_warning": {"requires_agent_todo": True},
        "state_projection_gap": {"requires_todo_expansion": True},
        "completed_todo_archive_warning": {"requires_archive": True},
        "agent_todos": {"open_count": 1},
    }

    def warning_builder(**kwargs):
        assert kwargs["active_state_next_action"] == item["active_state_next_action"]
        assert kwargs["latest_run_recommended_action"] == item["latest_run_recommended_action"]
        return {"kind": "next_action_projection_gap"}

    def replan_from_runs(runs, *, agent_todos):
        assert runs == [{"classification": "stalled_turn"}]
        assert agent_todos == item["agent_todos"]
        return {"required": True, "trigger_count": 1}

    attached = attach_active_state_project_asset_fields(
        item,
        latest_runs=[{"classification": "stalled_turn"}],
        next_action_projection_warning=warning_builder,
        autonomous_replan_obligation_from_runs=replan_from_runs,
    )
    project_asset = item["project_asset"]
    for key in (
        "active_state_next_action",
        "issue_meta_surface",
        "next_action_projection_warning",
        "backlog_hygiene_warning",
        "state_projection_gap",
        "completed_todo_archive_warning",
        "autonomous_replan_obligation",
    ):
        assert attached[key] == project_asset[key], (key, attached, project_asset)
    assert item["next_action_projection_warning"]["kind"] == "next_action_projection_gap"
    assert item["autonomous_replan_obligation"]["required"] is True

    no_asset = {"active_state_next_action": "ignored"}
    assert attach_active_state_project_asset_fields(no_asset) == {}
    assert "project_asset" not in no_asset

    print("project-asset-active-state-fields-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
