#!/usr/bin/env python3
"""Smoke-test todo claim visibility lane projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.claim_visibility import (  # noqa: E402
    TODO_AGENT_CLAIM_SCOPE_SCHEMA_VERSION,
    build_agent_claim_scoped_open_items,
    build_todo_claim_visibility_lanes,
)


CURRENT_AGENT = "codex-product-capability"
OTHER_AGENT = "codex-main-control"


def todo(
    todo_id: str,
    *,
    index: int,
    text: str,
    task_class: str,
    claimed_by: str | None = None,
) -> dict:
    item = {
        "index": index,
        "todo_id": todo_id,
        "text": text,
        "status": "open",
        "task_class": task_class,
        "claimed_by": claimed_by,
        "required_write_scopes": [" loopx/** ", "loopx/**"],
        "decision_scope": "direction:action:claim",
    }
    return {key: value for key, value in item.items() if value is not None}


def assert_agent_claim_scope_prefers_current_then_unclaimed() -> None:
    current_p2 = todo(
        "todo_current_p2",
        index=4,
        text="[P2] Current agent lower priority.",
        task_class="advancement_task",
        claimed_by=CURRENT_AGENT,
    )
    current_p0 = todo(
        "todo_current_p0",
        index=5,
        text="[P0] Current agent higher priority.",
        task_class="advancement_task",
        claimed_by=CURRENT_AGENT,
    )
    unclaimed_p0 = todo(
        "todo_unclaimed_p0",
        index=1,
        text="[P0] Unclaimed high priority.",
        task_class="advancement_task",
    )
    other_p0 = todo(
        "todo_other_p0",
        index=2,
        text="[P0] Other agent work.",
        task_class="advancement_task",
        claimed_by=OTHER_AGENT,
    )
    open_items = [unclaimed_p0, other_p0, current_p2, current_p0]

    selectable, claim_scope = build_agent_claim_scoped_open_items(
        open_items,
        agent_identity={
            "agent_id": CURRENT_AGENT,
            "role": "side-agent",
            "primary_agent": OTHER_AGENT,
        },
        diagnostic_item_limit=3,
    )
    assert [item["todo_id"] for item in selectable] == [
        "todo_current_p0",
        "todo_current_p2",
        "todo_unclaimed_p0",
    ], selectable
    assert claim_scope is not None, claim_scope
    assert claim_scope["schema_version"] == TODO_AGENT_CLAIM_SCOPE_SCHEMA_VERSION
    assert claim_scope["agent_id"] == CURRENT_AGENT
    assert claim_scope["primary_agent"] == OTHER_AGENT
    assert claim_scope["selection_order"] == "current_agent_claimed_then_unclaimed"
    assert claim_scope["selectable_open_count"] == 3
    assert claim_scope["current_agent_claimed_open_count"] == 2
    assert claim_scope["unclaimed_open_count"] == 1
    assert claim_scope["other_agent_claimed_open_count"] == 1
    assert claim_scope["other_agent_claimed_weight"] == "diagnostic_only"
    assert claim_scope["other_agent_claimed_items"][0]["todo_id"] == "todo_other_p0"
    assert claim_scope["blocked_claimed_items"][0]["todo_id"] == "todo_other_p0"


def assert_claim_visibility_lanes_split_current_other_and_task_class() -> None:
    open_items = [
        todo(
            "todo_unclaimed_p0",
            index=1,
            text="[P0] Unclaimed high priority.",
            task_class="advancement_task",
        ),
        todo(
            "todo_current_advancement",
            index=2,
            text="[P1] Current advancement.",
            task_class="advancement_task",
            claimed_by=CURRENT_AGENT,
        ),
        todo(
            "todo_current_monitor",
            index=3,
            text="[P1 monitor] Current monitor.",
            task_class="continuous_monitor",
            claimed_by=CURRENT_AGENT,
        ),
        todo(
            "todo_other_advancement",
            index=4,
            text="[P1] Other advancement.",
            task_class="advancement_task",
            claimed_by=OTHER_AGENT,
        ),
    ]

    lanes = build_todo_claim_visibility_lanes(
        open_items,
        agent_identity={"agent_id": CURRENT_AGENT},
        backlog_item_limit=8,
        visibility_lane_limit=16,
    )
    assert lanes["unclaimed_priority_open_items"][0]["todo_id"] == "todo_unclaimed_p0"
    assert [item["todo_id"] for item in lanes["claimed_open_items"]] == [
        "todo_current_advancement",
        "todo_current_monitor",
        "todo_other_advancement",
    ], lanes
    assert lanes["claimed_advancement_open_count"] == 2, lanes
    assert lanes["claimed_monitor_open_count"] == 1, lanes
    assert lanes["current_agent_claimed_open_count"] == 2, lanes
    assert lanes["current_agent_claimed_advancement_count"] == 1, lanes
    assert lanes["current_agent_claimed_monitor_count"] == 1, lanes
    assert lanes["claimed_by_others_count"] == 1, lanes
    current = lanes["current_agent_claimed_advancement_items"][0]
    assert current["required_write_scopes"] == ["loopx/**"], current
    assert current["decision_scope"]["scope_key"] == "claim", current
    assert lanes["claimed_by_others_items"][0]["todo_id"] == "todo_other_advancement"


def main() -> int:
    assert_agent_claim_scope_prefers_current_then_unclaimed()
    assert_claim_visibility_lanes_split_current_other_and_task_class()
    print("todo-claim-visibility-lanes-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
