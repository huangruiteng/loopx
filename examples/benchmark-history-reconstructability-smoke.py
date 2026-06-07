#!/usr/bin/env python3
"""Smoke-test compact benchmark history reconstructability after restart."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
NOTE = TOPIC_DIR / "benchmark-history-reconstructability-v0.md"
README = TOPIC_DIR / "README.md"
CHAIN_MAP = TOPIC_DIR / "benchmark-report-chain-map-v0.md"

SCHEMA = "benchmark_history_reconstructability_v0"
CHAIN_ORDER = [
    "benchmark_run_v0",
    "benchmark_result_v0",
    "benchmark_comparison_v0",
    "benchmark_comparison_decision_note_v0",
    "benchmark_experiment_report_v0",
    "benchmark_experiment_report_readiness_note_v0",
    "benchmark_experiment_report_replay_decision_v0",
]
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPEN" + "AI" + "_API" + "_KEY",
    "ANTH" + "ROPIC" + "_API" + "_KEY",
    "DAYTONA" + "_API" + "_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
    "s" + "k-" + "example",
]


def compact_history_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "sequence": 1,
            "schema_version": "benchmark_run_v0",
            "event_id": "run-bare-codex-cli-v0",
            "scenario_id": "bare_codex_cli",
            "real_run": False,
            "submit_eligible": False,
            "trace_publicness": "public_fixture_only",
        },
        {
            "sequence": 2,
            "schema_version": "benchmark_result_v0",
            "event_id": "result-mini-control-plane-repair-v0",
            "official_score": {"kind": "not_run", "delta": 0.0, "leaderboard_evidence": False},
            "control_plane_score": {"kind": "control_plane_score_core_v0", "delta": 0.125},
            "trace_publicness": "public_fixture_only",
        },
        {
            "sequence": 3,
            "schema_version": "benchmark_comparison_v0",
            "event_id": "comparison-mini-control-plane-repair-v0",
            "official_score_delta": 0.0,
            "control_plane_score_delta": 0.125,
            "claim_boundary": "control_plane_fixture_only",
        },
        {
            "sequence": 4,
            "schema_version": "benchmark_comparison_decision_note_v0",
            "event_id": "comparison-decision-mini-control-plane-repair-v0",
            "decision": "continue",
            "evidence_layer": "fixture_only",
            "minimum_next_evidence": "fixture replay with reconstructable compact history",
            "must_not_claim": ["official leaderboard uplift", "real benchmark pass/fail"],
        },
        {
            "sequence": 5,
            "schema_version": "benchmark_experiment_report_v0",
            "event_id": "report-mini-control-plane-repair-v0",
            "report_id": "mini-control-plane-repair-report-v0",
            "task_slice": "mini_control_plane_repair_v0",
            "official_score": {"kind": "not_run", "delta": 0.0, "leaderboard_evidence": False},
            "passive_control_plane_score": {
                "kind": "control_plane_score_core_v0",
                "delta": 0.125,
            },
            "claim_boundary": {
                "may_claim": ["fixture-level control-plane reconstructability"],
                "must_not_claim": ["official leaderboard uplift", "real benchmark pass/fail"],
            },
            "next_decision": {"decision": "continue", "minimum_next_evidence": "fixture replay"},
        },
        {
            "sequence": 6,
            "schema_version": "benchmark_experiment_report_readiness_note_v0",
            "event_id": "readiness-mini-control-plane-repair-v0",
            "readiness": "negative_or_control_plane_only",
            "next_run_authorization": "fixture_only",
            "report_decision": "continue",
            "negative_evidence_layers": ["readiness_only", "failure_analysis"],
            "must_not_claim": ["official leaderboard uplift", "real benchmark pass/fail"],
            "stop_condition": "stop before real benchmark execution or leaderboard claims",
        },
        {
            "sequence": 7,
            "schema_version": "benchmark_experiment_report_replay_decision_v0",
            "event_id": "replay-mini-control-plane-repair-v0",
            "readiness": "negative_or_control_plane_only",
            "authorization": "fixture_only",
            "replay_decision": "continue_fixture_replay",
            "next_run_mode": "fixture_replay",
            "surface": "status_review_packet_only",
            "stop_condition": "stop before real benchmark execution or leaderboard claims",
        },
        {
            "sequence": 0,
            "schema_version": "benchmark_experiment_report_replay_decision_v0",
            "event_id": "stale-replay-row-v0",
            "readiness": "stale",
            "authorization": "stale",
            "replay_decision": "stale_do_not_use",
            "next_run_mode": "stale",
            "stop_condition": "stale row must not win",
        },
    ]
    # Deliberately return out of order to model a fresh worker reloading history.
    return [rows[6], rows[1], rows[7], rows[3], rows[0], rows[5], rows[2], rows[4]]


def reconstruct_next_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest_by_schema: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: int(item["sequence"])):
        schema = row["schema_version"]
        if schema in CHAIN_ORDER:
            latest_by_schema[schema] = row

    missing = [schema for schema in CHAIN_ORDER if schema not in latest_by_schema]
    if missing:
        raise AssertionError(f"missing schemas: {missing}")

    ordered = [latest_by_schema[schema] for schema in CHAIN_ORDER]
    result = latest_by_schema["benchmark_result_v0"]
    comparison = latest_by_schema["benchmark_comparison_v0"]
    report = latest_by_schema["benchmark_experiment_report_v0"]
    readiness = latest_by_schema["benchmark_experiment_report_readiness_note_v0"]
    replay = latest_by_schema["benchmark_experiment_report_replay_decision_v0"]

    return {
        "schema_version": SCHEMA,
        "source_chain": [row["schema_version"] for row in ordered],
        "source_event_ids": [row["event_id"] for row in ordered],
        "official_score": {
            "kind": result["official_score"]["kind"],
            "delta": comparison["official_score_delta"],
            "leaderboard_evidence": result["official_score"]["leaderboard_evidence"],
        },
        "control_plane_score": {
            "kind": result["control_plane_score"]["kind"],
            "delta": comparison["control_plane_score_delta"],
        },
        "claim_boundary": report["claim_boundary"],
        "readiness": readiness["readiness"],
        "authorization": replay["authorization"],
        "replay_decision": replay["replay_decision"],
        "next_run_mode": replay["next_run_mode"],
        "negative_evidence_layers": readiness["negative_evidence_layers"],
        "must_not_claim": replay.get("must_not_claim") or readiness["must_not_claim"],
        "stop_condition": replay["stop_condition"],
        "state_reconstructable": True,
        "raw_inputs_required": False,
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 9000, len(text)


def assert_doc_contract() -> None:
    doc = NOTE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    chain_map = CHAIN_MAP.read_text(encoding="utf-8")

    required = [
        SCHEMA,
        "Chain Inputs",
        "Reconstructed Decision",
        "Failure Rules",
        "benchmark_run_v0",
        "benchmark_result_v0",
        "benchmark_comparison_v0",
        "benchmark_experiment_report_v0",
        "benchmark_experiment_report_readiness_note_v0",
        "benchmark_experiment_report_replay_decision_v0",
        "worker session history",
        "No real Terminal-Bench or Harbor runner execution",
    ]
    missing = [item for item in required if item not in doc]
    assert not missing, missing
    assert "benchmark-history-reconstructability-v0.md" in readme, readme
    for schema in CHAIN_ORDER:
        assert schema in chain_map, schema
    for text in (doc, readme):
        leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
        assert not leaked, leaked


def main() -> None:
    assert_doc_contract()
    rows = compact_history_rows()
    restarted_rows = json.loads(json.dumps(rows))
    decision = reconstruct_next_decision(restarted_rows)

    assert decision["schema_version"] == SCHEMA, decision
    assert decision["source_chain"] == CHAIN_ORDER, decision
    assert decision["source_event_ids"][-1] == "replay-mini-control-plane-repair-v0", decision
    assert "stale-replay-row-v0" not in decision["source_event_ids"], decision
    assert decision["official_score"] == {
        "kind": "not_run",
        "delta": 0.0,
        "leaderboard_evidence": False,
    }, decision
    assert decision["control_plane_score"] == {
        "kind": "control_plane_score_core_v0",
        "delta": 0.125,
    }, decision
    assert decision["readiness"] == "negative_or_control_plane_only", decision
    assert decision["authorization"] == "fixture_only", decision
    assert decision["replay_decision"] == "continue_fixture_replay", decision
    assert decision["next_run_mode"] == "fixture_replay", decision
    assert "official leaderboard uplift" in decision["must_not_claim"], decision
    assert decision["stop_condition"] == "stop before real benchmark execution or leaderboard claims", decision
    assert decision["state_reconstructable"] is True, decision
    assert decision["raw_inputs_required"] is False, decision
    assert_public_safe({"rows": rows, "decision": decision})

    print(
        "benchmark-history-reconstructability-smoke ok "
        f"schemas={len(decision['source_chain'])} replay={decision['replay_decision']} "
        f"raw_inputs={decision['raw_inputs_required']}"
    )


if __name__ == "__main__":
    main()
