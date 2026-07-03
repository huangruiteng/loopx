#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import run_compaction as run_compaction_read_model  # noqa: E402


def assert_run_compaction_wrapper_parity() -> None:
    reward = {
        "recorded_at": "2026-07-04T00:00:00Z",
        "decision": "approve",
        "reward": 1,
        "reason_summary": "validated bounded batch",
        "follow_up": "continue read-model cleanup",
        "lesson": {
            "schema_version": "lesson_v0",
            "kind": "process",
            "summary": "keep parity smokes first",
            "avoid": "large hot-path moves",
            "prefer": "small projection helpers",
            "private_note": "must not surface",
        },
        "ignored_field": "not compacted",
    }
    assert status_module.compact_human_reward(reward) == run_compaction_read_model.compact_human_reward(reward)

    operator_gate = {
        "recorded_at": "2026-07-04T00:01:00Z",
        "gate": "review",
        "decision": "approve",
        "operator_question": "Proceed?",
        "reason_summary": "owner approved",
        "follow_up": "merge after validation",
        "agent_command": "continue",
        "ignored_field": "not compacted",
    }
    assert status_module.compact_operator_gate(
        operator_gate
    ) == run_compaction_read_model.compact_operator_gate(operator_gate)

    resume_contract = {
        "version": "v1",
        "goal_id": "loopx-meta",
        "run_id": "run-1",
        "gate_id": "gate-1",
        "created_state_ref": "state-a",
        "created_policy_version": "policy-a",
        "allowed_decisions": ["approve", "reject"],
        "operator_decision": "approve",
        "latest_state_ref": "state-b",
        "freshness_check": "fresh",
        "precondition_check": "ok",
        "migration_or_rebase_result": "none",
        "resulting_action": "continue",
        "validation_after_resume": "required",
        "interrupt_payload": {
            "question": "Resume?",
            "choices": ["yes", "no"],
            "private_payload": "not compacted",
        },
        "ignored_field": "not compacted",
    }
    assert status_module.compact_operator_gate_resume_contract(
        resume_contract
    ) == run_compaction_read_model.compact_operator_gate_resume_contract(resume_contract)

    readiness = {
        "classification": "controller_ready",
        "read_only_observer_ready": True,
        "decision_advisor_ready": True,
        "write_controller_ready": False,
        "missing_gates": ["publish"],
        "review_judgment": "ready",
        "next_handoff_condition": "after smoke",
        "gates": [
            {"id": "smoke", "ok": True, "review": "passed", "private_note": "not compacted"},
            "invalid",
        ],
        "ignored_field": "not compacted",
    }
    assert status_module.compact_controller_readiness(
        readiness
    ) == run_compaction_read_model.compact_controller_readiness(readiness)


def main() -> None:
    assert_run_compaction_wrapper_parity()


if __name__ == "__main__":
    main()
