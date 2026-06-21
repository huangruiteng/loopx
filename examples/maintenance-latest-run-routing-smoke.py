#!/usr/bin/env python3
"""Smoke-test that maintenance runs do not mask actionable quota routing."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.status import autonomous_backlog_candidates, goal_attention  # noqa: E402


GOAL_ID = "loopx-meta"
READINESS_ACTION = (
    "Canary promotion-readiness smoke passed; promotion may proceed after "
    "doctor/status reports fresh evidence."
)
WORK_ACTION = "Continue the benchmark e2e-first evidence lane."
AGENT_TODO = "[P1] Benchmark e2e-first evidence lane: run one bounded hard-case treatment."


def main() -> int:
    goal = {
        "id": GOAL_ID,
        "status": "active",
        "registry_member": True,
        "adapter_status": "connected-read-only",
        "quota": {
            "compute": 1,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "fixture eligible quota",
        },
        "latest_runs": [
            {
                "generated_at": "2026-06-10T09:00:00+00:00",
                "classification": "canary_promotion_readiness_smoke_group",
                "recommended_action": READINESS_ACTION,
                "json_exists": True,
                "markdown_exists": True,
            },
            {
                "generated_at": "2026-06-10T08:00:00+00:00",
                "classification": "state_refreshed",
                "recommended_action": WORK_ACTION,
                "json_exists": True,
                "markdown_exists": True,
            },
        ],
    }
    item = goal_attention(goal)
    assert item is not None, goal
    item["quota"] = goal["quota"]
    item["agent_todos"] = {
        "source_section": "Agent Todo",
        "total_count": 1,
        "open_count": 1,
        "done_count": 0,
        "items": [{"index": 1, "done": False, "text": AGENT_TODO}],
    }
    item["project_asset"]["agent_todos"] = item["agent_todos"]
    item["project_asset"]["quota"] = goal["quota"]

    backlog = autonomous_backlog_candidates([item])
    status_payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 2,
        "attention_queue": {
            "items": [item],
            "autonomous_backlog_candidates": backlog,
        },
        "run_history": {"goals": [goal]},
        "promotion_readiness_summary": {
            "available": True,
            "source": "run_history",
            "goal_id": GOAL_ID,
            "generated_at": "2026-06-10T09:00:00+00:00",
            "classification": "canary_promotion_readiness_smoke_group",
            "freshness_status": "fresh",
            "requires_readiness_run": False,
            "freshness_window_hours": 24,
            "age_hours": 1.0,
            "sample_run_count": 1,
            "json_exists": True,
            "markdown_exists": True,
        },
    }

    decision = build_quota_should_run(status_payload, goal_id=GOAL_ID)
    assert decision["should_run"] is True, decision
    assert decision["state"] == "eligible", decision
    assert decision["status"] == "state_refreshed", decision
    assert decision["recommended_action"] == AGENT_TODO, decision
    protocol_summary = decision["protocol_action_packet"]["summary"]
    assert READINESS_ACTION not in protocol_summary, decision
    assert WORK_ACTION not in protocol_summary, decision
    assert "agent_action=[P1] Benchmark e2e-first evidence lane" in protocol_summary, decision
    assert "promotion_readiness_warning" not in decision, decision

    print("maintenance-latest-run-routing-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
