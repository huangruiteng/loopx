#!/usr/bin/env python3
"""Smoke-test event ledger read-model parity outside benchmark fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.runtime import event_ledger as event_ledger_read_model  # noqa: E402


def direct_event_class(run: dict[str, Any]) -> str:
    return event_ledger_read_model.event_ledger_event_class(
        run,
        compact_benchmark_run=status_module.compact_benchmark_run,
        compact_benchmark_result=status_module.compact_benchmark_result,
        compact_benchmark_comparison=status_module.compact_benchmark_comparison,
        compact_benchmark_learning_ledger=status_module.compact_benchmark_learning_ledger,
        compact_benchmark_experiment_report=status_module.compact_benchmark_experiment_report,
        compact_active_user_assisted_pilot=status_module.compact_active_user_assisted_pilot,
        run_has_external_evidence_watch_signal=status_module.run_has_external_evidence_watch_signal,
        decision_classifications=status_module.EVENT_LEDGER_DECISION_CLASSIFICATIONS,
        evidence_classifications=status_module.EVENT_LEDGER_EVIDENCE_CLASSIFICATIONS,
        evidence_hints=status_module.EVENT_LEDGER_EVIDENCE_HINTS,
        state_classifications=status_module.EVENT_LEDGER_STATE_CLASSIFICATIONS,
    )


def direct_summary(history: dict[str, Any]) -> dict[str, Any]:
    return event_ledger_read_model.build_event_ledger_summary(
        history,
        parse_timestamp=status_module.parse_timestamp,
        event_class_for_run=direct_event_class,
        compact_benchmark_run=status_module.compact_benchmark_run,
    )


def normalize_generated_at(payload: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["generated_at"] = reference["generated_at"]
    return normalized


def main() -> None:
    now = datetime.now(timezone.utc)
    runs = [
        {
            "goal_id": "project-a",
            "generated_at": (now - timedelta(minutes=10)).isoformat(),
            "classification": "quota_slot_spent",
            "quota_event": {"event_type": "quota_slot_spent", "source": "heartbeat", "slots": 1},
        },
        {
            "goal_id": "project-a",
            "generated_at": (now - timedelta(minutes=20)).isoformat(),
            "classification": "operator_gate_approved",
            "operator_gate": {"decision": "approved"},
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=2)).isoformat(),
            "classification": "read_only_project_map",
            "project_map": {"count": 2},
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=3)).isoformat(),
            "classification": "state_refreshed",
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=4)).isoformat(),
            "classification": "implementation_batch",
        },
        {
            "goal_id": "project-a",
            "generated_at": (now - timedelta(days=2)).isoformat(),
            "classification": "cache_check",
            "cache_check": {"status": "hit"},
        },
        {
            "goal_id": "project-c",
            "generated_at": (now - timedelta(days=8)).isoformat(),
            "classification": "old_work",
        },
        {
            "goal_id": "project-c",
            "generated_at": "not-a-timestamp",
            "classification": "ignored_bad_time",
        },
    ]
    history = {"runs": runs}

    for run in runs:
        assert status_module.event_ledger_event_class(run) == direct_event_class(run), run

    with tempfile.TemporaryDirectory(prefix="loopx-event-ledger-summary-") as raw_tmp:
        wrapper = status_module.build_status_runtime_summaries(
            history=history,
            queue={"items": []},
            runtime_root=Path(raw_tmp),
            goal_id_filter=None,
            display_limit=10,
            todo_index_limit=10,
        )["event_ledger_summary"]
    direct = direct_summary(history)
    assert normalize_generated_at(direct, wrapper) == wrapper, (direct, wrapper)

    assert status_module.blank_event_class_counts() == event_ledger_read_model.blank_event_class_counts()
    assert status_module.blank_event_ledger_goal("project-z") == event_ledger_read_model.blank_event_ledger_goal(
        "project-z"
    )

    totals = wrapper["totals"]
    assert wrapper["available"] is True, wrapper
    assert wrapper["source"] == "run_history", wrapper
    assert wrapper["sample_run_count"] == len(runs), wrapper
    assert wrapper["event_classes"] == ["accounting", "decision", "evidence", "state", "work"], wrapper
    assert totals["events_24h"] == 5, totals
    assert totals["events_7d"] == 6, totals
    assert totals["benchmark_runs_24h"] == 0, totals
    assert totals["benchmark_runs_7d"] == 0, totals
    assert totals["by_class_24h"] == {
        "accounting": 1,
        "decision": 1,
        "evidence": 1,
        "state": 1,
        "work": 1,
    }, totals
    assert totals["by_class_7d"] == {
        "accounting": 1,
        "decision": 1,
        "evidence": 2,
        "state": 1,
        "work": 1,
    }, totals

    goals = {goal["goal_id"]: goal for goal in wrapper["goals"]}
    assert goals["project-a"]["events_24h"] == 2, goals
    assert goals["project-a"]["events_7d"] == 3, goals
    assert goals["project-a"]["latest_event_class"] == "accounting", goals
    assert goals["project-b"]["by_class_24h"] == {
        "accounting": 0,
        "decision": 0,
        "evidence": 1,
        "state": 1,
        "work": 1,
    }, goals
    assert goals["project-c"]["events_7d"] == 0, goals

    print("event-ledger-readmodel-smoke ok")


if __name__ == "__main__":
    main()
