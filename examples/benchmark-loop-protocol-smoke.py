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
    build_benchmark_loop_contract,
    build_benchmark_loop_controller_trace,
    build_blind_loop_continuation_prompt,
    build_blind_loop_initial_prompt,
    classify_loopx_treatment_claim,
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

    lines = render_loop_contract_packet_lines(packet_only)
    assert "benchmark_loop_contract:" in lines
    assert "  protocol_id: packet_only_observation" in lines

    print("benchmark-loop-protocol-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
