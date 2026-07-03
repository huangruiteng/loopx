#!/usr/bin/env python3
"""Smoke-test monitor-quiet display candidate projection."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.projections.monitor_display import (  # noqa: E402
    attention_item_is_monitor_quiet_display_candidate as direct_monitor_candidate,
)
from loopx.status import (  # noqa: E402
    MAX_STATUS_TODOS_PER_ROLE,
    attention_item_is_monitor_quiet_display_candidate,
    open_todo_items,
    todo_item_is_actionable_open,
)


def todo(index: int, text: str) -> dict[str, object]:
    return {"index": index, "done": False, "status": "open", "text": text}


def monitor_item(*, with_advancement: bool = False, with_user_todo: bool = False) -> dict[str, object]:
    agent_todos = {
        "open_count": 1 + int(with_advancement),
        "monitor_open_items": [todo(1, "[P1 monitor] Observe one bounded public-safe signal.")],
        "first_executable_items": [],
        "executable_backlog_items": [],
        "claimed_advancement_open_items": [],
    }
    if with_advancement:
        agent_todos["claimed_advancement_open_items"] = [
            todo(2, "[P2] Continue canary-gated control-plane read-model cleanup.")
        ]
    return {
        "goal_id": "loopx-meta",
        "waiting_on": "codex",
        "severity": "action",
        "agent_todos": agent_todos,
        "user_todos": {
            "open_count": int(with_user_todo),
            "items": [todo(1, "[P0-user] Decide something.")] if with_user_todo else [],
        },
    }


def assert_status_and_projection_agree(item: dict[str, object], expected: bool) -> None:
    direct = direct_monitor_candidate(
        item,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        fallback_limit=MAX_STATUS_TODOS_PER_ROLE,
    )
    wrapper = attention_item_is_monitor_quiet_display_candidate(item)
    assert direct is expected, (direct, expected, item)
    assert wrapper == direct, (wrapper, direct, item)


def main() -> int:
    assert_status_and_projection_agree(monitor_item(), True)
    assert_status_and_projection_agree(monitor_item(with_advancement=True), False)
    assert_status_and_projection_agree(monitor_item(with_user_todo=True), False)
    print("monitor-display-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
