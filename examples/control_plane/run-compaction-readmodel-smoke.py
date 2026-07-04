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


def _direct_compact_run_base(run: dict[str, object]) -> dict[str, object]:
    return run_compaction_read_model.compact_run_base(
        run,
        run_compact_fields=status_module.RUN_COMPACT_FIELDS,
        run_lifecycle_flags=status_module.run_lifecycle_flags,
        primary_lifecycle_phase=status_module.primary_lifecycle_phase,
        compact_human_reward=status_module.compact_human_reward,
        compact_operator_gate=status_module.compact_operator_gate,
        compact_autonomous_replan_ack=status_module.compact_autonomous_replan_ack,
        compact_operator_gate_resume_contract=status_module.compact_operator_gate_resume_contract,
        compact_controller_readiness=status_module.compact_controller_readiness,
        public_safe_compact_text=status_module.public_safe_compact_text,
        compact_subagent_run=status_module.compact_subagent_run,
        max_subagent_activity_items=status_module.MAX_SUBAGENT_ACTIVITY_ITEMS,
    )


def assert_compact_run_base_parity() -> None:
    mapped_run = {
        "generated_at": "2026-07-04T00:02:00Z",
        "run_id": "run-base",
        "goal_id": "loopx-meta",
        "classification": "read_only_project_map",
        "recommended_action": "continue bounded cleanup",
        "merge_decision": "self-merged after focused validation",
        "human_reward": {"decision": "approve", "reward": 1, "private_note": "not compacted"},
        "operator_gate": {"decision": "approve", "operator_question": "Proceed?"},
        "operator_gate_resume_contract": {
            "version": "v1",
            "goal_id": "loopx-meta",
            "interrupt_payload": {"question": "Resume?", "private_payload": "not compacted"},
        },
        "controller_readiness": {
            "classification": "controller_ready",
            "decision_advisor_ready": True,
            "gates": [{"id": "smoke", "ok": True, "review": "passed", "private_note": "not compacted"}],
        },
        "subagents": [
            {
                "run_id": "child-1",
                "agent_role": "review",
                "status": "completed",
                "changed_files": ["AGENTS.md", "loopx/status.py"],
                "private_note": "not compacted",
            }
        ],
        "ignored_field": "not compacted",
    }
    assert status_module.compact_run(mapped_run) == _direct_compact_run_base(mapped_run)

    explicit_lifecycle_run = {
        "generated_at": "2026-07-04T00:03:00Z",
        "classification": "custom_event",
        "lifecycle_phase": "controller_gated",
        "lifecycle_flags": ["controller_gated"],
    }
    assert status_module.compact_run(explicit_lifecycle_run) == _direct_compact_run_base(
        explicit_lifecycle_run
    )


def main() -> None:
    assert_run_compaction_wrapper_parity()
    assert_compact_run_base_parity()


if __name__ == "__main__":
    main()
