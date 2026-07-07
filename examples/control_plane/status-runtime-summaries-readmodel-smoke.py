#!/usr/bin/env python3
"""Smoke-test the status runtime-summary read-model adapter."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.runtime.time import now_utc, parse_timestamp, utc_isoformat  # noqa: E402
from loopx.control_plane.status_runtime_summaries import (  # noqa: E402
    StatusRuntimeSummaryContext,
    build_status_runtime_summaries,
)


GOAL_ID = "status-runtime-summary-fixture"


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal_id": run.get("goal_id"),
        "classification": run.get("classification"),
        "generated_at": run.get("generated_at"),
    }


def no_benchmark_projection(run: dict[str, Any]) -> None:
    return None


def build_context() -> StatusRuntimeSummaryContext:
    return StatusRuntimeSummaryContext(
        latest_run=lambda goal: (goal.get("latest_runs") or [None])[0],
        goal_lifecycle_fields=lambda goal, current_run: {
            "lifecycle_phase": "fixture",
            "lifecycle_flags": ["fixture"],
        },
        subagent_activity_for_goal=lambda goal: None,
        compact_run=compact_run,
        quota_status=lambda goal: {"state": "eligible"},
        parse_timestamp=parse_timestamp,
        compact_benchmark_run=no_benchmark_projection,
        compact_benchmark_result=no_benchmark_projection,
        compact_benchmark_comparison=no_benchmark_projection,
        compact_benchmark_learning_ledger=no_benchmark_projection,
        compact_benchmark_experiment_report=no_benchmark_projection,
        compact_active_user_assisted_pilot=no_benchmark_projection,
        run_has_external_evidence_watch_signal=lambda run: False,
        decision_classifications={"operator_gate_notify"},
        evidence_classifications=set(),
        evidence_hints=(),
        state_classifications={"state_refreshed"},
        promotion_readiness_classifications=set(),
        add_promotion_readiness_freshness=lambda readiness: {
            **readiness,
            "freshness_status": "unknown",
            "requires_readiness_run": True,
        },
        latest_promotion_readiness_event=lambda root, *, goal_id=None: {},
        promotion_readiness_freshness_hours=24,
        promotion_readiness_proxy_note="fixture readiness proxy",
        public_safe_compact_text=lambda value, *, limit=320: str(value or "").strip()[:limit],
    )


def build_history() -> dict[str, Any]:
    now = now_utc()
    accounting_run = {
        "goal_id": GOAL_ID,
        "classification": "quota_slot_spent",
        "generated_at": utc_isoformat(now),
        "quota_event": {"slots": 1, "source": "heartbeat"},
    }
    decision_run = {
        "goal_id": GOAL_ID,
        "classification": "operator_gate_notify",
        "generated_at": utc_isoformat(now),
        "operator_gate": {"state": "open"},
    }
    return {
        "goal_count": 1,
        "run_count": 2,
        "goals": [
            {
                "id": GOAL_ID,
                "domain": "loopx-platform",
                "status": "active",
                "registry_member": True,
                "latest_runs": [accounting_run, decision_run],
            }
        ],
        "runs": [accounting_run, decision_run],
    }


def build_queue() -> dict[str, Any]:
    return {
        "items": [
            {
                "goal_id": GOAL_ID,
                "agent_todos": {
                    "items": [
                        {
                            "todo_id": "todo_status_runtime_summary_fixture",
                            "status": "open",
                            "title": "Keep runtime summaries behind one read-model adapter.",
                            "index": 0,
                        }
                    ]
                },
                "user_todos": {"items": []},
            }
        ]
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as raw_root:
        summaries = build_status_runtime_summaries(
            history=build_history(),
            queue=build_queue(),
            runtime_root=Path(raw_root),
            goal_id_filter=GOAL_ID,
            display_limit=1,
            todo_index_limit=10,
            context=build_context(),
        )

    assert set(summaries) == {
        "run_history",
        "event_ledger_summary",
        "promotion_readiness_summary",
        "decision_freshness_summary",
        "usage_summary",
        "todo_index",
    }, summaries
    assert summaries["run_history"]["run_count"] == 2, summaries["run_history"]
    assert len(summaries["run_history"]["recent_runs"]) == 1, summaries["run_history"]
    assert summaries["event_ledger_summary"]["totals"]["events_24h"] == 2, summaries["event_ledger_summary"]
    assert summaries["usage_summary"]["totals"]["quota_spend_slots_24h"] == 1, summaries["usage_summary"]
    assert summaries["decision_freshness_summary"]["summary"]["decision_count"] == 1, summaries["decision_freshness_summary"]
    assert summaries["todo_index"]["total_count"] == 1, summaries["todo_index"]
    print("status-runtime-summaries-readmodel-smoke ok")


if __name__ == "__main__":
    main()
