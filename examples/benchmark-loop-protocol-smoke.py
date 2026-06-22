#!/usr/bin/env python3
"""Smoke-test the shared benchmark loop protocol contract."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core.loop_protocol import (
    BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
    LOOPX_PACKET_ONLY_OBSERVATION_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID,
    PACKET_ONLY_OBSERVATION_PROTOCOL_ID,
    PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID,
    RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
    LOOPX_PRODUCT_MODE_ROUTE,
    build_benchmark_loop_contract,
    build_benchmark_loop_controller_trace,
    build_blind_loop_continuation_prompt,
    build_blind_loop_initial_prompt,
    build_product_mode_main_table_comparison_contract,
    classify_loopx_treatment_claim,
    classify_product_mode_main_table_pair,
    render_loop_contract_packet_lines,
)


def main() -> int:
    treatment = build_benchmark_loop_contract(
        route=LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        max_rounds=BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    )
    assert treatment["protocol_id"] == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
    assert treatment["max_rounds_budget"] == 5
    assert treatment["official_feedback_forwarded"] is False
    assert treatment["official_feedback_blinded"] is True
    assert treatment["blind_loop"] is True
    assert treatment["strict_treatment_claim_allowed"] is True
    prompt_polling_test = build_benchmark_loop_contract(
        route=LOOPX_PROMPT_POLLING_TEST_ROUTE,
        max_rounds=BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    )
    assert prompt_polling_test["protocol_id"] == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
    assert prompt_polling_test["strict_treatment_claim_allowed"] is True

    packet_only = build_benchmark_loop_contract(
        route=LOOPX_PACKET_ONLY_OBSERVATION_ROUTE,
        protocol_id=PACKET_ONLY_OBSERVATION_PROTOCOL_ID,
    )
    assert packet_only["strict_treatment_claim_allowed"] is False
    assert packet_only["claim_blocker"] == "packet_only_no_max5_controller"

    raw_product = build_benchmark_loop_contract(
        route=RAW_CODEX_AUTONOMOUS_MAX5_ROUTE,
        max_rounds=5,
    )
    assert raw_product["protocol_id"] == PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID
    assert raw_product["product_mode"] is True
    assert raw_product["official_feedback_blinded"] is True

    product_contract = build_product_mode_main_table_comparison_contract()
    assert product_contract["protocol_id"] == PRODUCT_MODE_MAX5_NO_FEEDBACK_PROTOCOL_ID
    assert product_contract["baseline_arm"]["route"] == RAW_CODEX_AUTONOMOUS_MAX5_ROUTE
    assert product_contract["treatment_arm"]["route"] == LOOPX_PRODUCT_MODE_ROUTE
    assert product_contract["policy_gate"]["headline_metrics"] == [
        "best_score",
        "final_score",
        "first_success_round",
        "declared_done_score",
    ]
    assert product_contract["policy_gate"]["official_feedback_blinded"] is True

    trace = build_benchmark_loop_controller_trace(
        route=LOOPX_BLIND_LOOP_TREATMENT_ROUTE,
        max_rounds=5,
    )
    assert trace["loop_protocol_id"] == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
    assert trace["official_feedback_forwarded"] is False
    assert trace["round_rewards"] == []
    assert trace["raw_task_text_recorded"] is False

    initial = build_blind_loop_initial_prompt(
        route=LOOPX_PROMPT_POLLING_TEST_ROUTE,
        instruction="Synthetic instruction.",
        benchmark_surface="official synthetic benchmark sandbox",
    )
    assert "Structured prompt-polling test round 1" in initial
    assert "No official reward, pass/fail status" in initial
    assert "Synthetic instruction." in initial

    continuation = build_blind_loop_continuation_prompt(
        scheduled_round=2,
        max_rounds=5,
        persistent_constraint_clause=" Keep protected paths stable.",
    )
    assert "Scheduled blind-loop continuation round 2 of 5" in continuation
    assert "not evidence that the official verifier passed or failed" in continuation
    assert "Keep protected paths stable." in continuation

    strict_claim = classify_loopx_treatment_claim(
        {
            "benchmark_loop_contract": treatment,
            "controller_trace_present": True,
            "round_rewards": [{"agent_round": 1, "reward": 0.0}],
        }
    )
    assert strict_claim["strict_loopx_treatment_claim_allowed"] is True
    assert (
        strict_claim["loopx_treatment_evidence_tier"]
        == "strict_max5_prompt_polling_test"
    )

    packet_claim = classify_loopx_treatment_claim(
        {
            "benchmark_loop_contract": packet_only,
            "loopx_access_packet_injected": True,
            "worker_loopx_cli_call_total": 0,
        }
    )
    assert packet_claim["strict_loopx_treatment_claim_allowed"] is False
    assert packet_claim["loopx_treatment_evidence_tier"] == "packet_or_incomplete"
    assert "missing_max5_blind_loop_protocol" in packet_claim[
        "loopx_treatment_claim_blocker"
    ]

    baseline_run = {
        "benchmark_id": "skillsbench@1.1",
        "case_id": "citation-check",
        "benchmark_loop_contract": raw_product,
        "arm_id": "raw_codex_autonomous_max5",
        "product_mode": True,
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
        "official_score": 0.0,
        "round_rewards": [{"agent_round": 1, "reward": 0.0, "passed": False}],
    }
    treatment_run = {
        "benchmark_id": "skillsbench@1.1",
        "case_id": "citation-check",
        "benchmark_loop_contract": build_benchmark_loop_contract(
            route=LOOPX_PRODUCT_MODE_ROUTE,
            max_rounds=5,
        ),
        "arm_id": "loopx_product_mode",
        "product_mode": True,
        "loopx_inside_case": True,
        "loopx_prompt_driven_lifecycle_observed": True,
        "worker_loopx_cli_call_total": 8,
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
        "official_score": 1.0,
        "round_rewards": [
            {"agent_round": 1, "reward": 0.0, "passed": False},
            {"agent_round": 2, "reward": 1.0, "passed": True},
        ],
    }
    product_pair = classify_product_mode_main_table_pair(
        baseline_run=baseline_run,
        treatment_run=treatment_run,
    )
    assert product_pair["main_table_claim_allowed"] is True, product_pair
    assert product_pair["product_mode_pair_complete"] is True, product_pair
    assert product_pair["case_id"] == "citation-check", product_pair
    assert product_pair["treatment_loopx_lifecycle_observed"] is True, product_pair

    shallow_treatment = dict(treatment_run)
    shallow_treatment["loopx_prompt_driven_lifecycle_observed"] = False
    shallow_treatment["worker_loopx_cli_call_total"] = 0
    shallow_pair = classify_product_mode_main_table_pair(
        baseline_run=baseline_run,
        treatment_run=shallow_treatment,
    )
    assert shallow_pair["main_table_claim_allowed"] is False, shallow_pair
    assert "treatment_loopx_lifecycle_not_observed" in shallow_pair["claim_blocker"]

    final_score_only_baseline = dict(baseline_run)
    final_score_only_baseline.pop("round_rewards")
    final_score_only_pair = classify_product_mode_main_table_pair(
        baseline_run=final_score_only_baseline,
        treatment_run=treatment_run,
    )
    assert final_score_only_pair["main_table_claim_allowed"] is False, (
        final_score_only_pair
    )
    assert "baseline_compact_metrics_missing" in final_score_only_pair[
        "claim_blocker"
    ]

    lines = render_loop_contract_packet_lines(packet_only)
    assert "benchmark_loop_contract:" in lines
    assert "  protocol_id: packet_only_observation" in lines

    print("benchmark-loop-protocol-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
