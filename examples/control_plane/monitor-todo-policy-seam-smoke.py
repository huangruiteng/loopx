#!/usr/bin/env python3
"""Characterize the shared monitor todo due-time policy seam."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import quota as quota_module  # noqa: E402
from loopx.policies.monitor_todo import (  # noqa: E402
    monitor_todo_is_actionable_open,
    monitor_todo_is_due,
    monitor_todo_is_expired,
    monitor_todo_missing_schedule,
    monitor_todo_next_due_at,
)
from loopx.status import (  # noqa: E402
    todo_item_is_actionable_open,
    todo_item_is_due_monitor,
    todo_item_is_expired_monitor,
    todo_item_missing_monitor_schedule,
    todo_item_next_due_at,
)


NOW = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
PAST = "2025-12-31T23:59:00Z"
FUTURE = "2026-01-01T00:01:00+00:00"
EXPIRED = "2025-12-31T23:58:00+00:00"


def monitor_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "text": "[P1] Monitor update-note draft PR.",
        "status": "open",
        "task_class": "continuous_monitor",
        "next_due_at": PAST,
    }
    item.update(overrides)
    return item


def assert_policy_matches_wrappers(item: dict[str, object], *, due: bool, expired: bool) -> None:
    assert monitor_todo_is_due(item, now=NOW) is due, item
    assert todo_item_is_due_monitor(item, now=NOW) is due, item
    assert quota_module._todo_item_is_due_monitor(item, now=NOW) is due, item
    assert monitor_todo_is_expired(item, now=NOW) is expired, item
    assert todo_item_is_expired_monitor(item, now=NOW) is expired, item
    assert quota_module._todo_item_is_expired_monitor(item, now=NOW) is expired, item
    assert monitor_todo_next_due_at(item) == todo_item_next_due_at(item), item
    assert monitor_todo_next_due_at(item) == quota_module._todo_item_next_due_at(item), item
    assert monitor_todo_is_actionable_open(item) == todo_item_is_actionable_open(item), item
    assert monitor_todo_is_actionable_open(item) == quota_module._todo_item_is_actionable_open(item), item
    assert monitor_todo_missing_schedule(item, now=NOW) == todo_item_missing_monitor_schedule(
        item,
        now=NOW,
    ), item
    assert monitor_todo_missing_schedule(item, now=NOW) == quota_module._todo_item_missing_monitor_schedule(
        item,
        now=NOW,
    ), item


def main() -> int:
    assert_policy_matches_wrappers(monitor_item(), due=True, expired=False)
    assert_policy_matches_wrappers(monitor_item(next_due_at=FUTURE), due=False, expired=False)
    assert_policy_matches_wrappers(
        monitor_item(expires_at=EXPIRED),
        due=False,
        expired=True,
    )
    assert_policy_matches_wrappers(
        monitor_item(status="blocked"),
        due=False,
        expired=False,
    )
    assert_policy_matches_wrappers(
        monitor_item(done=True),
        due=False,
        expired=False,
    )
    assert_policy_matches_wrappers(
        monitor_item(task_class="advancement_task"),
        due=False,
        expired=False,
    )
    unscheduled = monitor_item()
    unscheduled.pop("next_due_at")
    assert_policy_matches_wrappers(unscheduled, due=False, expired=False)
    assert monitor_todo_missing_schedule(unscheduled, now=NOW) is True, unscheduled
    assert monitor_todo_next_due_at({"next_due_at": "2026-01-01T00:00:00"}) == NOW
    print("monitor-todo-policy-seam-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
