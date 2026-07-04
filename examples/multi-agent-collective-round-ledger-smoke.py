#!/usr/bin/env python3
"""Smoke-test the generic multi-agent collective-round ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.multi_agent.collective_round_ledger import (  # noqa: E402
    MULTI_AGENT_COLLECTIVE_ROUND_LEDGER_SCHEMA_VERSION,
    build_multi_agent_collective_round_ledger,
)


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    ledger = build_multi_agent_collective_round_ledger(
        source="smoke",
        expected_lanes=[
            {"agent_id": "agent-a", "lane_id": "curator", "role_id": "research_curator"},
            {"agent_id": "agent-b", "lane_id": "runner", "role_id": "research_executor"},
        ],
        lane_outcomes=[
            {
                "round": 1,
                "agent_id": "agent-a",
                "selected_todo_id": "todo_contract",
                "selected_action": "write_research_contract",
                "executed": True,
                "completion_status": "done",
            },
            {
                "round": 1,
                "agent_id": "agent-b",
                "selected_todo_id": "todo_dev",
                "selected_action": "run_dev_eval",
                "executed": True,
                "completion_status": "done",
                "dev_metric": 4.0,
                "appended_count": 2,
            },
            {
                "round": 2,
                "agent_id": "agent-a",
                "executed": True,
                "completion_status": "done",
            },
            {
                "round": 2,
                "agent_id": "agent-b",
                "selected_todo_id": "todo_holdout",
                "selected_action": "run_holdout_eval",
                "executed": True,
                "completion_status": "done",
                "holdout_metric": 4.5,
                "appended_count": 1,
            },
        ],
        integrated_evidence={
            "evidence_event_count": 3,
            "dev_metric": 4.0,
            "holdout_metric": 4.5,
            "dev_metric_sequence": [4.0],
            "holdout_metric_sequence": [4.5],
            "holdout_improvement_count": 1,
            "protected_scope_clean": True,
        },
        role_declared_successor_todos=[
            {
                "todo_id": "todo_holdout",
                "target_agent_id": "agent-b",
                "target_role_id": "research_executor",
                "source_todo_id": "todo_dev",
                "action_kind": "run_holdout_eval",
            }
        ],
        baseline_metric=1.0,
        required_full_participation_round_count=1,
        required_holdout_improvement_count=1,
    )
    assert ledger["schema_version"] == MULTI_AGENT_COLLECTIVE_ROUND_LEDGER_SCHEMA_VERSION
    assert ledger["owner_layer"] == "generic_multi_agent_kernel", ledger
    assert ledger["coordination_model"] == "decentralized_state_a2a", ledger
    assert ledger["round_unit"] == "collective_agent_pass", ledger
    assert ledger["expected_lane_count"] == 2, ledger
    assert ledger["expected_agent_ids"] == ["agent-a", "agent-b"], ledger
    assert ledger["lane_outcome_count"] == 4, ledger
    assert ledger["completed_lane_turn_count"] == 3, ledger
    assert ledger["completed_turn_count_by_agent"] == {"agent-a": 1, "agent-b": 2}, ledger
    assert ledger["collective_round_indexes"] == [1, 2], ledger
    assert ledger["collective_round_count"] == 2, ledger
    assert ledger["full_participation_round_indexes"] == [1], ledger
    assert ledger["synchronous_full_participation_round_count"] == 1, ledger
    assert ledger["asynchronous_full_participation_round_count"] == 1, ledger
    assert ledger["full_participation_round_count"] == 1, ledger
    assert ledger["full_participation_count_basis"] == "synchronous_and_asynchronous", ledger
    assert ledger["full_participation_requirement_gap"] == {
        "schema_version": "multi_agent_full_participation_gap_v0",
        "required_count": 1,
        "count_basis": "synchronous_and_asynchronous",
        "completed_turn_count_by_agent": {"agent-a": 1, "agent-b": 2},
        "shortfall_by_agent": {},
        "missing_agent_count": 0,
        "met": True,
    }, ledger
    assert ledger["full_participation_verified"] is False, ledger
    assert ledger["multi_round_interaction_verified"] is True, ledger
    assert ledger["integrated_evidence"]["evidence_event_count"] == 3, ledger
    assert ledger["integrated_evidence"]["dev_metric"] == 4.0, ledger
    assert ledger["integrated_evidence"]["holdout_metric"] == 4.5, ledger
    assert ledger["integrated_evidence"]["dev_metric_sequence"] == [4.0], ledger
    assert ledger["integrated_evidence"]["holdout_metric_sequence"] == [4.5], ledger
    assert ledger["integrated_evidence"]["holdout_improvement_count"] == 1, ledger
    verification = ledger["collective_research_verification"]
    assert verification["schema_version"] == "multi_agent_collective_research_verification_v0"
    assert verification["baseline_metric"] == 1.0, ledger
    assert verification["completed_turn_count_by_agent"] == {"agent-a": 1, "agent-b": 2}
    assert verification["full_participation_requirement_gap"]["met"] is True
    assert verification["full_participation_requirement_met"] is True, ledger
    assert verification["holdout_improvement_requirement_met"] is True, ledger
    assert verification["verified"] is True, ledger
    assert ledger["successor_todo_count"] == 1, ledger
    assert ledger["role_declared_successor_todos"][0]["target_agent_id"] == "agent-b"
    assert ledger["public_boundary"] == {
        "raw_logs_recorded": False,
        "private_artifacts_recorded": False,
        "absolute_paths_recorded": False,
        "credentials_recorded": False,
    }, ledger
    assert_public_safe(ledger)

    gap_ledger = build_multi_agent_collective_round_ledger(
        source="smoke-gap",
        expected_lanes=[
            {"agent_id": "agent-a", "lane_id": "curator", "role_id": "research_curator"},
            {"agent_id": "agent-b", "lane_id": "runner", "role_id": "research_executor"},
        ],
        lane_outcomes=[
            {
                "round": 1,
                "agent_id": "agent-a",
                "selected_todo_id": "todo_contract",
                "selected_action": "write_research_contract",
                "executed": True,
                "completion_status": "done",
            },
            {
                "round": 1,
                "agent_id": "agent-b",
                "selected_todo_id": "todo_dev",
                "selected_action": "run_dev_eval",
                "executed": True,
                "completion_status": "done",
            },
            {
                "round": 2,
                "agent_id": "agent-a",
                "selected_todo_id": "todo_review",
                "selected_action": "review_research_contract",
                "executed": True,
                "completion_status": "done",
            },
            {
                "round": 2,
                "agent_id": "agent-b",
                "executed": True,
                "completion_status": "done",
            },
        ],
        baseline_metric=1.0,
        required_full_participation_round_count=2,
    )
    assert gap_ledger["completed_turn_count_by_agent"] == {
        "agent-a": 2,
        "agent-b": 1,
    }, gap_ledger
    assert gap_ledger["full_participation_round_count"] == 1, gap_ledger
    gap = gap_ledger["full_participation_requirement_gap"]
    assert gap["count_basis"] == "synchronous_and_asynchronous", gap_ledger
    assert gap["shortfall_by_agent"] == {"agent-b": 1}, gap_ledger
    assert gap["missing_agent_count"] == 1, gap_ledger
    assert gap["met"] is False, gap_ledger
    assert (
        gap_ledger["collective_research_verification"][
            "full_participation_requirement_met"
        ]
        is False
    ), gap_ledger
    assert_public_safe(gap_ledger)
    print("multi-agent-collective-round-ledger-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
