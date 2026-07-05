#!/usr/bin/env python3
"""Characterize the shared monitor todo due-time policy seam."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.scheduler.monitor_todo import (  # noqa: E402
    monitor_cadence_delta,
    monitor_next_due_at,
    monitor_todo_is_actionable_open,
    monitor_todo_is_due,
    monitor_todo_is_expired,
    monitor_todo_missing_schedule,
    monitor_todo_next_due_at,
    parse_monitor_counter,
)
from loopx.control_plane.scheduler.monitor_target import (  # noqa: E402
    build_quota_monitor_target,
    monitor_target_summary,
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
    assert monitor_todo_is_expired(item, now=NOW) is expired, item
    assert todo_item_is_expired_monitor(item, now=NOW) is expired, item
    assert monitor_todo_next_due_at(item) == todo_item_next_due_at(item), item
    assert monitor_todo_is_actionable_open(item) == todo_item_is_actionable_open(item), item
    assert monitor_todo_missing_schedule(item, now=NOW) == todo_item_missing_monitor_schedule(
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
    assert parse_monitor_counter("3") == 3
    assert parse_monitor_counter("not-a-number") == 0
    assert monitor_cadence_delta("2h").total_seconds() == 7200
    cadence_due_at = monitor_next_due_at(
        generated_at="2026-01-01T00:00:00+00:00",
        cadence="5m",
    )
    assert (
        datetime.fromisoformat(cadence_due_at).astimezone(timezone.utc).isoformat()
        == "2026-01-01T00:05:00+00:00"
    )
    assert monitor_next_due_at(
        generated_at="ignored",
        explicit_next_due_at="2026-01-01T00:05:00+00:00",
    ) == "2026-01-01T00:05:00+00:00"
    target_decision = {
        "goal_id": "loopx-meta",
        "agent_identity": {"agent_id": "codex-product-capability"},
        "effective_action": "monitor_quiet_skip",
        "recommended_action": " Observe due monitor without material transition. ",
    }
    assert monitor_target_summary("  Observe\n\nmonitor  ", limit=160) == "Observe monitor"
    monitor_target = build_quota_monitor_target(
        target_decision,
        monitor_mode="due_monitor_observed_without_material_transition",
    )
    assert monitor_target["schema_version"] == "quota_monitor_target_v0", monitor_target
    assert monitor_target["monitor_mode"] == "due_monitor_observed_without_material_transition", monitor_target
    assert monitor_target["action_summary"] == "Observe due monitor without material transition.", monitor_target
    print("monitor-todo-policy-seam-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
