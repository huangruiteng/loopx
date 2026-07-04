#!/usr/bin/env python3
"""Smoke-test decision freshness read-model parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.runtime import decision_freshness as decision_read_model  # noqa: E402


def direct_decision_kinds(run: dict[str, Any]) -> list[str]:
    return decision_read_model.decision_event_kinds(
        run,
        decision_classifications=status_module.EVENT_LEDGER_DECISION_CLASSIFICATIONS,
        classification_prefixes=status_module.DECISION_FRESHNESS_CLASSIFICATION_PREFIXES,
    )


def direct_summary(history: dict[str, Any]) -> dict[str, Any]:
    return decision_read_model.build_decision_freshness_summary(
        history,
        parse_timestamp=status_module.parse_timestamp,
        decision_event_kinds=direct_decision_kinds,
        event_class_for_run=status_module.event_ledger_event_class,
        blank_event_class_counts=status_module.blank_event_class_counts,
        window_days=status_module.DECISION_FRESHNESS_WINDOW_DAYS,
        item_limit=status_module.DECISION_FRESHNESS_ITEM_LIMIT,
        proxy_note=status_module.DECISION_FRESHNESS_PROXY_NOTE,
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
            "generated_at": (now - timedelta(minutes=40)).isoformat(),
            "classification": "operator_gate_approved",
            "operator_gate": {"decision": "approved"},
        },
        {
            "goal_id": "project-a",
            "generated_at": (now - timedelta(minutes=20)).isoformat(),
            "classification": "state_refreshed",
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(days=8)).isoformat(),
            "classification": "human_reward_recorded",
            "human_reward": {"decision": "continue"},
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=3)).isoformat(),
            "classification": "implementation_batch",
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=2)).isoformat(),
            "classification": "read_only_project_map",
            "project_map": {"count": 2},
        },
        {
            "goal_id": "project-b",
            "generated_at": (now - timedelta(hours=1)).isoformat(),
            "classification": "quota_slot_spent",
            "quota_event": {"event_type": "quota_slot_spent", "slots": 1},
        },
        {
            "goal_id": "project-c",
            "generated_at": (now - timedelta(days=1)).isoformat(),
            "classification": "reward_overlay_acknowledged",
        },
        {
            "goal_id": "project-d",
            "generated_at": "not-a-timestamp",
            "classification": "operator_gate_approved",
            "operator_gate": {"decision": "approved"},
        },
    ]
    history = {"runs": runs}

    assert status_module.decision_event_kinds(runs[0]) == direct_decision_kinds(runs[0]) == ["operator_gate"]
    assert status_module.decision_event_kinds(runs[2]) == direct_decision_kinds(runs[2]) == ["human_reward"]
    assert status_module.decision_event_kinds(runs[6]) == direct_decision_kinds(runs[6]) == [
        "decision_classification"
    ]
    assert status_module.decision_freshness_reason(
        stale_by_age=True,
        newer_event_count=1,
    ) == decision_read_model.decision_freshness_reason(stale_by_age=True, newer_event_count=1)

    wrapper = status_module.build_decision_freshness_summary(history)
    direct = direct_summary(history)
    assert normalize_generated_at(direct, wrapper) == wrapper, (direct, wrapper)

    summary = wrapper["summary"]
    assert wrapper["available"] is True, wrapper
    assert wrapper["source"] == "run_history", wrapper
    assert wrapper["sample_run_count"] == len(runs), wrapper
    assert wrapper["window_days"] == 7, wrapper
    assert summary == {
        "decision_count": 3,
        "stale_count": 1,
        "rebase_required_count": 2,
        "fresh_count": 1,
    }, summary

    items = {
        (item["goal_id"], item["decision_kind"]): item
        for item in wrapper["items"]
    }
    project_a = items[("project-a", "operator_gate")]
    assert project_a["freshness_state"] == "rebase_required", project_a
    assert project_a["newer_event_count_7d"] == 1, project_a
    assert project_a["newer_event_classes_7d"]["state"] == 1, project_a
    assert project_a["stale_by_age"] is False, project_a

    project_b = items[("project-b", "human_reward")]
    assert project_b["freshness_state"] == "stale_rebase_required", project_b
    assert project_b["stale_by_age"] is True, project_b
    assert project_b["newer_event_count_7d"] == 3, project_b
    assert project_b["newer_event_classes_7d"]["accounting"] == 1, project_b
    assert project_b["newer_event_classes_7d"]["evidence"] == 1, project_b
    assert project_b["newer_event_classes_7d"]["work"] == 1, project_b

    project_c = items[("project-c", "decision_classification")]
    assert project_c["freshness_state"] == "fresh", project_c
    assert project_c["requires_decision_point_rebase"] is False, project_c

    assert ("project-d", "operator_gate") not in items, items
    print("decision-freshness-readmodel-smoke ok")


if __name__ == "__main__":
    main()
