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
            {"agent_id": "agent-b", "lane_id": "runner", "role_id": "evidence_runner"},
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
            "protected_scope_clean": True,
        },
        role_declared_successor_todos=[
            {
                "todo_id": "todo_holdout",
                "target_agent_id": "agent-b",
                "target_role_id": "evidence_runner",
                "source_todo_id": "todo_dev",
                "action_kind": "run_holdout_eval",
            }
        ],
    )
    assert ledger["schema_version"] == MULTI_AGENT_COLLECTIVE_ROUND_LEDGER_SCHEMA_VERSION
    assert ledger["owner_layer"] == "generic_multi_agent_kernel", ledger
    assert ledger["coordination_model"] == "decentralized_state_a2a", ledger
    assert ledger["round_unit"] == "collective_agent_pass", ledger
    assert ledger["expected_lane_count"] == 2, ledger
    assert ledger["lane_outcome_count"] == 3, ledger
    assert ledger["completed_lane_turn_count"] == 3, ledger
    assert ledger["collective_round_indexes"] == [1, 2], ledger
    assert ledger["collective_round_count"] == 2, ledger
    assert ledger["multi_round_interaction_verified"] is True, ledger
    assert ledger["integrated_evidence"]["evidence_event_count"] == 3, ledger
    assert ledger["integrated_evidence"]["dev_metric"] == 4.0, ledger
    assert ledger["integrated_evidence"]["holdout_metric"] == 4.5, ledger
    assert ledger["successor_todo_count"] == 1, ledger
    assert ledger["role_declared_successor_todos"][0]["target_agent_id"] == "agent-b"
    assert ledger["public_boundary"] == {
        "raw_logs_recorded": False,
        "private_artifacts_recorded": False,
        "absolute_paths_recorded": False,
        "credentials_recorded": False,
    }, ledger
    assert_public_safe(ledger)
    print("multi-agent-collective-round-ledger-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
