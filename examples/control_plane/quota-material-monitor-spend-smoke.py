#!/usr/bin/env python3
"""Smoke-test quota accounting after a material monitor transition."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.quota.slot_accounting import (  # noqa: E402
    build_quota_slot_preview_for_decision,
    build_quota_slot_spend_event,
)


GOAL_ID = "material-monitor-spend"


def write_run_index(runtime: Path, records: list[dict[str, Any]]) -> None:
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def preview(runtime: Path, *, agent_id: str | None = None) -> dict[str, Any]:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "spent_slots": 0,
        "allowed_slots": 1440,
    }
    before = {
        "ok": True,
        "goal_id": GOAL_ID,
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "state": "eligible",
        "safe_bypass_allowed": False,
        "quota": quota,
    }
    status = {
        "runtime_root": str(runtime),
        "attention_queue": {"items": [{"goal_id": GOAL_ID}]},
        "run_history": {"goals": [{"id": GOAL_ID, "quota": quota}]},
    }

    return build_quota_slot_preview_for_decision(
        status,
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**quota, "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=agent_id,
    )


def main() -> int:
    unchanged_poll = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "quota_monitor_poll",
        "delivery_outcome": "surface_only",
        "material_change": False,
    }
    material_poll = {
        "generated_at": "2026-01-01T00:01:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "quota_monitor_poll",
        "delivery_outcome": "outcome_progress",
        "material_change": True,
        "agent_id": "codex-monitor-a",
    }
    spent = {
        "generated_at": "2026-01-01T00:02:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "quota_slot_spent",
    }

    with tempfile.TemporaryDirectory(prefix="loopx-material-monitor-spend-") as tmp:
        runtime = Path(tmp) / "runtime"

        write_run_index(runtime, [unchanged_poll])
        unchanged_preview = preview(runtime)
        assert unchanged_preview["ok"] is False, unchanged_preview

        write_run_index(runtime, [unchanged_poll, material_poll])
        material_preview = preview(runtime, agent_id="codex-monitor-a")
        assert material_preview["ok"] is True, material_preview
        assert material_preview["delivery_completion_spend"] is True, material_preview
        assert material_preview["delivery_run_classification"] == "quota_monitor_poll", material_preview
        assert material_preview["delivery_run_generated_at"] == material_poll["generated_at"], material_preview
        assert material_preview["delivery_run_agent_id"] == "codex-monitor-a", material_preview
        spend_event = build_quota_slot_spend_event(
            material_preview,
            self_repair_spend_actions=frozenset(),
        )
        assert spend_event["agent_id"] == "codex-monitor-a", spend_event
        assert spend_event["quota_event"]["delivery_run_agent_id"] == "codex-monitor-a", spend_event

        cross_agent_preview = preview(runtime, agent_id="codex-monitor-b")
        assert cross_agent_preview["ok"] is False, cross_agent_preview

        unscoped_call_preview = preview(runtime)
        assert unscoped_call_preview["ok"] is True, unscoped_call_preview
        assert unscoped_call_preview["delivery_run_agent_id"] == "codex-monitor-a", unscoped_call_preview

        unscoped_material_poll = {key: value for key, value in material_poll.items() if key != "agent_id"}
        write_run_index(runtime, [unchanged_poll, unscoped_material_poll])
        legacy_run_preview = preview(runtime, agent_id="codex-monitor-a")
        assert legacy_run_preview["ok"] is True, legacy_run_preview
        assert legacy_run_preview["delivery_run_agent_id"] is None, legacy_run_preview

        write_run_index(runtime, [unchanged_poll, material_poll, spent])
        duplicate_preview = preview(runtime, agent_id="codex-monitor-a")
        assert duplicate_preview["ok"] is False, duplicate_preview

    print("quota-material-monitor-spend-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
