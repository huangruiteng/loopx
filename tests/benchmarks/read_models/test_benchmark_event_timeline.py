from __future__ import annotations

from loopx.benchmarks.read_models.benchmark_event_timeline import (
    compact_benchmark_case_event_timeline,
)


def test_compact_benchmark_event_timeline_preserves_public_contract() -> None:
    compact = compact_benchmark_case_event_timeline(
        {
            "events": [
                {
                    "phase": "agent",
                    "event": "task_facing_activity",
                    "status": "observed",
                    "required": True,
                    "checkpoint_count": -3,
                    "official_score_value": 0.5,
                    "failure_attribution_labels": ["a", "b", "c", "d", "e", "f"],
                    "private_detail": "drop",
                },
                {"phase": "missing-status", "event": "ignored"},
            ]
        }
    )

    assert compact == {
        "schema_version": "skillsbench_case_event_timeline_v0",
        "source": "compact_public_signals",
        "raw_material_recorded": False,
        "event_count": 1,
        "events": [
            {
                "phase": "agent",
                "event": "task_facing_activity",
                "status": "observed",
                "required": True,
                "checkpoint_count": 0,
                "official_score_value": 0.5,
                "failure_attribution_labels": ["a", "b", "c", "d", "e"],
            }
        ],
    }


def test_compact_benchmark_event_timeline_caps_visible_events() -> None:
    compact = compact_benchmark_case_event_timeline(
        {
            "events": [
                {"phase": "agent", "event": f"event-{index}", "status": "observed"}
                for index in range(14)
            ]
        }
    )

    assert compact["event_count"] == 14
    assert len(compact["events"]) == 12
    assert compact["events"][-1]["event"] == "event-11"
