#!/usr/bin/env python3
"""Smoke-test strict LoopX Turn benchmark treatment and pair fidelity."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    build_loopx_turn_benchmark_fidelity_check,
    build_loopx_turn_goal_matched_pair_check,
)


def _attempt_accounting() -> dict[str, bool]:
    return {
        "launcher_attempt_countable": True,
        "case_attempt_countable": True,
        "solver_attempt_countable": True,
        "verifier_attempt_countable": True,
        "official_score_attempt_countable": True,
    }


def _common() -> dict[str, object]:
    return {
        "benchmark_id": "skillsbench@1.1",
        "case_id": "public-fixture-case",
        "agent_model": "gpt-fixture",
        "reasoning_effort": "xhigh",
        "max_rounds_budget": 5,
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
        "loopx_runner_source_fingerprint": {
            "fingerprint": "sha256:public-fixture-runner"
        },
        **_attempt_accounting(),
    }


def _baseline() -> dict[str, object]:
    return {
        **_common(),
        "route": "codex-cli-goal-baseline",
        "official_score": 0.0,
    }


def _treatment() -> dict[str, object]:
    return {
        **_common(),
        "route": "loopx-turn-agent-cli",
        "official_score": 1.0,
        "loopx_turn_executions": [
            {
                "schema_version": "loopx_turn_execution_v0",
                "mode": "run_once",
                "status": "committed",
                "result_kind": "validated_progress",
                "execution_mode": "isolated-headless",
                "host": {"executable": "built-in", "kind": "codex-cli"},
                "validation": {"status": "passed"},
                "receipt": {"status": "committed"},
                "effects": {
                    "host_invoked": True,
                    "state_written": True,
                    "quota_spent": True,
                    "scheduler_acknowledged": False,
                },
                "quota_slot_spend_count": 1,
            },
        ],
        "scored_workspace_validation": {
            "status": "passed",
            "independent": True,
            "oracle_feedback_used": False,
            "meaningful_operation_count": 2,
        },
        "public_boundary": {
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
            "raw_host_output_recorded": False,
            "credentials_recorded": False,
            "local_paths_recorded": False,
        },
    }


def test_real_turn_pair_is_countable_without_claiming_advantage() -> None:
    treatment = _treatment()
    executions = treatment["loopx_turn_executions"]
    assert isinstance(executions, list)
    executions.append(copy.deepcopy(executions[0]))
    fidelity = build_loopx_turn_benchmark_fidelity_check(treatment)
    assert fidelity["turn_treatment_fidelity_allowed"] is True, fidelity
    assert fidelity["turn_count"] == 2, fidelity

    pair = build_loopx_turn_goal_matched_pair_check(
        baseline_run=_baseline(),
        treatment_run=treatment,
    )
    assert pair["matched_pair_countable"] is True, pair
    assert pair["effect_analysis_allowed"] is True, pair
    assert pair["advantage_claim_allowed"] is False, pair
    assert pair["official_scores"]["delta"] == 1.0, pair


def test_old_product_mode_cannot_impersonate_turn() -> None:
    treatment = _treatment()
    treatment["route"] = "loopx-goal-start-product-mode"
    fidelity = build_loopx_turn_benchmark_fidelity_check(treatment)
    assert fidelity["turn_treatment_fidelity_allowed"] is False, fidelity
    assert "canonical_turn_route" in fidelity["missing_evidence"], fidelity


def test_missing_validator_or_duplicate_spend_is_not_countable() -> None:
    treatment = _treatment()
    executions = treatment["loopx_turn_executions"]
    assert isinstance(executions, list)
    execution = executions[0]
    assert isinstance(execution, dict)
    execution["validation"] = {"status": "failed"}
    execution["quota_slot_spend_count"] = 2
    executions.append("invalid-turn-entry")
    fidelity = build_loopx_turn_benchmark_fidelity_check(treatment)
    assert fidelity["turn_treatment_fidelity_allowed"] is False, fidelity
    assert "turn_execution_items_valid" in fidelity["missing_evidence"]
    assert "independent_turn_validation_passed" in fidelity["missing_evidence"]
    assert "exactly_one_quota_spend_per_turn" in fidelity["missing_evidence"]


def test_setup_or_parity_mismatch_blocks_effect_analysis() -> None:
    treatment = _treatment()
    treatment["case_id"] = "different-case"
    treatment["loopx_runner_source_fingerprint"] = {
        "fingerprint": "sha256:different-runner"
    }
    treatment["official_score_attempt_countable"] = False
    pair = build_loopx_turn_goal_matched_pair_check(
        baseline_run=_baseline(),
        treatment_run=treatment,
    )
    assert pair["matched_pair_countable"] is False, pair
    assert "treatment_not_official_countable" in pair["blockers"], pair
    assert "case_id_mismatch_or_missing" in pair["blockers"], pair
    assert "runner_source_fingerprint_mismatch_or_missing" in pair["blockers"], pair
    assert pair["official_scores"]["delta"] is None, pair


def test_oracle_or_raw_evidence_leak_blocks_turn_fidelity() -> None:
    treatment = copy.deepcopy(_treatment())
    treatment["reward_feedback_forwarded"] = True
    boundary = treatment["public_boundary"]
    assert isinstance(boundary, dict)
    boundary["raw_host_output_recorded"] = True
    fidelity = build_loopx_turn_benchmark_fidelity_check(treatment)
    assert fidelity["turn_treatment_fidelity_allowed"] is False, fidelity
    assert "official_feedback_blinded" in fidelity["missing_evidence"], fidelity
    assert "raw_host_output_absent" in fidelity["safety_failures"], fidelity


def test_public_ledger_old_treatments_do_not_impersonate_turn() -> None:
    ledger_path = (
        REPO_ROOT
        / "docs"
        / "research"
        / "long-horizon-agent-benchmarks"
        / "benchmark-run-ledger.json"
    )
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    old_routes = {
        "loopx-product-mode",
        "loopx-goal-start-product-mode",
        "loopx-blind-loop-treatment",
        "loopx-prompt-polling-test",
    }
    old_treatments: list[dict[str, object]] = []
    for benchmark in ledger.get("benchmarks", {}).values():
        for case in benchmark.get("cases", {}).values():
            for run in case.get("runs", []):
                route = str(run.get("route") or "")
                arm = str(run.get("arm_id") or "")
                if route in old_routes or "loopx" in arm.lower():
                    old_treatments.append(run)

    assert old_treatments, "public ledger should retain historical LoopX controls"
    for run in old_treatments:
        fidelity = build_loopx_turn_benchmark_fidelity_check(run)
        assert fidelity["turn_treatment_fidelity_allowed"] is False, fidelity
        assert "canonical_turn_route" in fidelity["missing_evidence"], fidelity


def main() -> int:
    test_real_turn_pair_is_countable_without_claiming_advantage()
    test_old_product_mode_cannot_impersonate_turn()
    test_missing_validator_or_duplicate_spend_is_not_countable()
    test_setup_or_parity_mismatch_blocks_effect_analysis()
    test_oracle_or_raw_evidence_leak_blocks_turn_fidelity()
    test_public_ledger_old_treatments_do_not_impersonate_turn()
    print("benchmark LoopX Turn fidelity smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
