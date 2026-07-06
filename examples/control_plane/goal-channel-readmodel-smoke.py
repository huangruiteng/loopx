#!/usr/bin/env python3
"""Smoke-test goal channel attachment read-model parity."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.goals import goal_channel as goal_channel_read_model  # noqa: E402
from loopx.control_plane.goals.goal_channel_projection import (  # noqa: E402
    build_goal_channel_projection,
)


def _attach_direct(
    item: dict[str, Any],
    *,
    goal: dict[str, Any],
    goal_latest_runs: list[dict[str, Any]],
) -> None:
    goal_channel_read_model.attach_goal_channel_projection(
        item,
        goal=goal,
        goal_latest_runs=goal_latest_runs,
        build_goal_channel_projection=build_goal_channel_projection,
    )


def base_item() -> dict[str, Any]:
    return {
        "status": "state_refreshed",
        "waiting_on": "codex",
        "recommended_action": "continue bounded control-plane cleanup",
        "quota": {
            "state": "eligible",
            "spent_slots": 7,
            "allowed_slots": 100,
        },
        "project_asset": {
            "display_name": "Goal channel read model",
            "user_todos": {
                "first_open_items": [
                    {
                        "todo_id": "todo_user_gate",
                        "text": "Approve the visible route",
                        "status": "open",
                        "task_class": "user_gate",
                    }
                ]
            },
            "agent_todos": {
                "first_open_items": [
                    {
                        "todo_id": "todo_agent_work",
                        "text": "Keep the status projection read-only",
                        "status": "open",
                        "task_class": "advancement_task",
                        "claimed_by": "codex-product-capability",
                    }
                ]
            },
        },
    }


def base_goal() -> dict[str, Any]:
    return {
        "id": "goal-channel-readmodel-smoke",
        "domain": "control-plane",
        "status": "active",
    }


def latest_runs() -> list[dict[str, Any]]:
    private_path = "/" + "tmp" + "/goal-channel-private-trace.log"
    return [
        {
            "generated_at": "2026-07-04T10:00:00Z",
            "classification": "validated_progress",
            "recommended_action": "continue bounded cleanup",
            "raw_log_path": private_path,
            "json_exists": True,
            "markdown_exists": True,
        }
    ]


def assert_attach_parity() -> None:
    wrapper_item = base_item()
    direct_item = deepcopy(wrapper_item)
    goal = base_goal()
    runs = latest_runs()

    status_module.attach_goal_channel_projection(
        wrapper_item,
        goal=goal,
        goal_latest_runs=deepcopy(runs),
    )
    _attach_direct(
        direct_item,
        goal=goal,
        goal_latest_runs=deepcopy(runs),
    )
    assert wrapper_item == direct_item, (wrapper_item, direct_item)

    projection = wrapper_item["goal_channel_projection"]
    projection_text = str(projection)
    assert projection["schema_version"] == "goal_channel_projection_v0", projection
    assert projection["mode"] == "read_only", projection
    assert projection["goal_id"] == "goal-channel-readmodel-smoke", projection
    assert projection["quota"]["state"] == "eligible", projection
    assert projection["user_todos"][0]["todo_id"] == "todo_user_gate", projection
    assert projection["agent_todos"][0]["claimed_by"] == "codex-product-capability", projection
    assert projection["recent_events"][0]["classification"] == "validated_progress", projection
    assert projection["truth_contract"]["projection_is_writable"] is False, projection
    assert projection["source_warnings"], projection
    assert "goal-channel-private-trace.log" not in projection_text, projection


def main() -> int:
    assert_attach_parity()
    print("goal-channel-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
