#!/usr/bin/env python3
"""Smoke-test the benchmark experiment report template."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import benchmark_comparison_decision_note  # noqa: E402

TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"
TEMPLATE = TOPIC_DIR / "benchmark-experiment-report-template-v0.md"

REPORT_SCHEMA = "benchmark_experiment_report_v0"
COMPARISON_SCHEMA = "benchmark_comparison_v0"
DECISION_NOTE_SCHEMA = "benchmark_comparison_decision_note_v0"
REQUIRED_SECTIONS = [
    "experiment_identity",
    "official_score",
    "passive_control_plane_score",
    "operator_simulator_ablation",
    "cost_latency_overhead",
    "failure_taxonomy",
    "reproducibility_artifacts",
    "claim_boundary",
    "negative_results",
    "next_decision",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "DAYTONA" + "_API_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
    "s" + "k-" + "example",
]


def comparison_summary_payload() -> dict[str, Any]:
    return {
        "schema_version": COMPARISON_SCHEMA,
        "task_id": "mini_control_plane_repair_v0",
        "comparison_id": "mini_control_plane_repair_v0_ab",
        "mode_pair": ["bare_codex_cli", "passive_loopx_wrapper"],
        "official_task_score_delta": 0.0,
        "control_plane_score_delta": 0.143,
        "both_success": True,
        "ready_to_run_real_benchmark": False,
        "ready_to_submit_leaderboard": False,
    }


def readiness_summary_payload() -> dict[str, Any]:
    return {
        "schema_version": COMPARISON_SCHEMA,
        "task_id": "terminal_bench_official_pilot_readiness_v0",
        "comparison_id": "terminal_bench_official_pilot_readiness_ab",
        "mode_pair": ["bare_codex_cli_readiness", "passive_loopx_wrapper_readiness"],
        "official_task_score_delta": "not_applicable_readiness_only",
        "control_plane_score_delta": 0.0,
        "both_success": None,
        "ready_to_run_real_benchmark": False,
        "ready_to_submit_leaderboard": False,
    }


def failure_summary_payload() -> dict[str, Any]:
    return {
        "schema_version": COMPARISON_SCHEMA,
        "task_id": "mini_control_plane_repair_failure_probe_v0",
        "comparison_id": "mini_control_plane_repair_failure_probe_ab",
        "mode_pair": ["bare_codex_cli", "passive_loopx_wrapper"],
        "official_task_score_delta": 0.0,
        "control_plane_score_delta": 0.0,
        "both_success": False,
        "ready_to_run_real_benchmark": False,
        "ready_to_submit_leaderboard": False,
    }


def decision_note_payload(summary: dict[str, Any]) -> dict[str, Any]:
    note = benchmark_comparison_decision_note(summary)
    assert note is not None, "comparison note should be generated from compact summary"
    assert note["schema_version"] == DECISION_NOTE_SCHEMA, note
    return note


def report_payload(note: dict[str, Any], readiness_note: dict[str, Any], failure_note: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "experiment_identity": {
            "report_id": "mini-control-plane-repair-report-v0",
            "benchmark_id": "loopx-local-passive-baseline@v0",
            "task_slice": "mini_control_plane_repair_v0",
            "worker_surface": "codex_cli_fixture",
            "harness_identity": "loopx_passive_wrapper",
            "harness_policy_version": "local-smoke-v0",
            "trace_publicness": "public_contract_fixture",
        },
        "official_score": {
            "kind": "local_fixture_not_leaderboard",
            "native_score": 1.0,
            "wrapped_score": 1.0,
            "delta": note["official_task_score_delta"],
            "task_id_or_split": "mini_control_plane_repair_v0",
            "repetitions": 1,
            "runner_source": "loopx-local-fixture",
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "passive_control_plane_score": {
            "restartability": 1.0,
            "stale_state_avoidance": 1.0,
            "evidence_discipline": 1.0,
            "writeback_quality": 1.0,
            "failure_attribution": 1.0,
            "overhead_bounded": True,
            "regression_avoidance_passed": True,
            "source_events": [
                "benchmark_run_v0:bare_codex_cli:fixture",
                "benchmark_run_v0:passive_loopx_wrapper:fixture",
                "benchmark_result_v0:paired_comparison:fixture",
                f"{DECISION_NOTE_SCHEMA}:mini_control_plane_repair_v0_ab:fixture",
            ],
        },
        "operator_simulator_ablation": {
            "enabled": False,
            "reason": "passive report template keeps assisted mode separate unless an operator_simulator_run_v0 row exists",
            "assisted_setting": None,
            "visibility_policy": None,
            "intervention_budget": None,
            "intervention_count": 0,
            "simulator_induced_failure_labels": [],
            "leaderboard_evidence": False,
            "source_events": [],
        },
        "cost_latency_overhead": {
            "wall_time_seconds": 0,
            "worker_steps": 3,
            "simulator_turns": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "writeback_count": 3,
            "validation_count": 4,
        },
        "failure_taxonomy": {
            "worker_failures": [],
            "harness_failures": [],
            "simulator_failures": [],
            "benchmark_boundary_failures": [],
            "unknown_failures": [],
        },
        "reproducibility_artifacts": {
            "source_events": [
                "benchmark_run_v0:bare_codex_cli:fixture",
                "benchmark_run_v0:passive_loopx_wrapper:fixture",
                "benchmark_result_v0:paired_comparison:fixture",
                f"{DECISION_NOTE_SCHEMA}:mini_control_plane_repair_v0_ab:fixture",
            ],
            "runner_versions": ["loopx-local-fixture@v0"],
            "task_identifiers": ["mini_control_plane_repair_v0"],
            "validation_commands": [
                "python3 examples/codex-cli-long-run-benchmark-smoke.py",
                "python3 examples/passive-baseline-protocol-smoke.py",
                "python3 examples/operator-simulator-overlay-smoke.py",
            ],
            "artifact_manifest": [
                "fixture:benchmark_result_v0",
                "fixture:benchmark_comparison_v0",
                f"fixture:{DECISION_NOTE_SCHEMA}",
                "fixture:public_artifact_manifest",
            ],
        },
        "claim_boundary": {
            "may_claim": [
                "local control-plane score can be reported for coordination dimensions",
                "official score delta is zero in this local fixture",
                *note["may_claim"],
            ],
            "must_not_claim": [
                "official leaderboard uplift",
                "assisted-mode uplift without operator_simulator_run_v0 evidence",
                "benchmark pass/fail improvement from local fixture evidence",
                *note["must_not_claim"],
            ],
            "source_decision_note_schema": note["schema_version"],
            "source_evidence_layer": note["evidence_layer"],
            "evidence_layer_by_claim": {
                "official_task_score": "official_score",
                "control_plane_coordination": "passive_control_plane_score",
                "assisted_collaboration": "operator_simulator_ablation",
            },
        },
        "negative_results": {
            "null_official_delta": True,
            "overhead_regressions": [],
            "failed_hypotheses": [
                {
                    "source_decision_note_schema": readiness_note["schema_version"],
                    "evidence_layer": readiness_note["evidence_layer"],
                    "hypothesis": "readiness-only evidence is enough for benchmark uplift claims",
                    "result": "rejected",
                    "minimum_next_evidence": readiness_note["minimum_next_evidence"],
                    "must_not_claim": readiness_note["must_not_claim"],
                },
                {
                    "source_decision_note_schema": failure_note["schema_version"],
                    "evidence_layer": failure_note["evidence_layer"],
                    "hypothesis": "failed paired comparison can be broadened without attribution",
                    "result": "rejected",
                    "minimum_next_evidence": failure_note["minimum_next_evidence"],
                    "must_not_claim": failure_note["must_not_claim"],
                },
            ],
            "why_it_matters": "null official delta prevents overclaiming benchmark improvement from control-plane-only evidence",
        },
        "next_decision": {
            "decision": note["decision"],
            "minimum_next_evidence": note["minimum_next_evidence"],
            "stop_condition": note["stop_condition"],
            "source_decision_note_schema": note["schema_version"],
            "readiness_decision": readiness_note["decision"],
            "failure_decision": failure_note["decision"],
        },
    }


def assert_doc_contract() -> None:
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    compact_template = " ".join(template.split())
    required = [
        "Benchmark Experiment Report Template V0",
        REPORT_SCHEMA,
        "official_score",
        "passive_control_plane_score",
        "operator_simulator_ablation",
        "cost_latency_overhead",
        "failure_taxonomy",
        "reproducibility_artifacts",
        "claim_boundary",
        "negative_results",
        "next_decision",
        DECISION_NOTE_SCHEMA,
        "readiness/failure decision notes",
        "Do not include credentials",
        "python3 examples/benchmark-experiment-report-template-smoke.py",
    ]
    missing = [snippet for snippet in required if snippet not in compact_template]
    assert not missing, missing
    assert "benchmark-experiment-report-template-v0.md" in readme, readme
    assert "Publication Readiness" in roadmap, roadmap
    assert "paper-style report" in roadmap, roadmap

    leaked = [marker for marker in FORBIDDEN_TEXT if marker in template]
    assert not leaked, leaked


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 16000, len(text)


def assert_report_contract(report: dict[str, Any]) -> None:
    assert report["schema_version"] == REPORT_SCHEMA, report
    for section in REQUIRED_SECTIONS:
        assert section in report, section

    official = report["official_score"]
    assert official["leaderboard_evidence"] is False, official
    assert official["submit_eligible"] is False, official
    assert official["delta"] == 0.0, official

    passive = report["passive_control_plane_score"]
    assert passive["restartability"] >= 1.0, passive
    assert passive["regression_avoidance_passed"] is True, passive
    assert all(
        event.startswith(("benchmark_run_v0:", "benchmark_result_v0:", f"{DECISION_NOTE_SCHEMA}:"))
        for event in passive["source_events"]
    ), passive

    assisted = report["operator_simulator_ablation"]
    assert assisted["enabled"] is False, assisted
    assert assisted["intervention_count"] == 0, assisted
    assert assisted["leaderboard_evidence"] is False, assisted

    overhead = report["cost_latency_overhead"]
    assert overhead["simulator_turns"] == 0, overhead
    assert overhead["cost_usd"] == 0.0, overhead

    boundary = report["claim_boundary"]
    assert "official leaderboard uplift" in boundary["must_not_claim"], boundary
    assert boundary["source_decision_note_schema"] == DECISION_NOTE_SCHEMA, boundary
    assert boundary["source_evidence_layer"] == "control_plane_only", boundary
    assert "control-plane delta improved while official score delta stayed zero" in boundary["may_claim"], boundary
    assert boundary["evidence_layer_by_claim"]["official_task_score"] == "official_score", boundary
    assert boundary["evidence_layer_by_claim"]["control_plane_coordination"] == "passive_control_plane_score", boundary
    assert boundary["evidence_layer_by_claim"]["assisted_collaboration"] == "operator_simulator_ablation", boundary

    assert report["negative_results"]["null_official_delta"] is True, report
    failed_hypotheses = report["negative_results"]["failed_hypotheses"]
    layers = {item["evidence_layer"] for item in failed_hypotheses}
    assert layers == {"readiness_only", "failure_analysis"}, failed_hypotheses
    readiness_failure = next(item for item in failed_hypotheses if item["evidence_layer"] == "readiness_only")
    assert "benchmark pass/fail or score uplift" in readiness_failure["must_not_claim"], readiness_failure
    attributed_failure = next(item for item in failed_hypotheses if item["evidence_layer"] == "failure_analysis")
    assert attributed_failure["minimum_next_evidence"] == "attribute the failed scenario before broadening", attributed_failure
    assert report["next_decision"]["decision"] in {"continue", "repeat", "broaden", "defer", "stop"}, report
    assert report["next_decision"]["source_decision_note_schema"] == DECISION_NOTE_SCHEMA, report
    assert report["next_decision"]["readiness_decision"] == "continue", report
    assert report["next_decision"]["failure_decision"] == "repeat", report
    assert_public_safe(report)


def main() -> None:
    assert_doc_contract()
    note = decision_note_payload(comparison_summary_payload())
    readiness_note = decision_note_payload(readiness_summary_payload())
    failure_note = decision_note_payload(failure_summary_payload())
    report = report_payload(note, readiness_note, failure_note)
    assert_report_contract(report)
    print(
        "benchmark-experiment-report-template-smoke ok "
        f"sections={len(REQUIRED_SECTIONS)} "
        f"leaderboard={report['official_score']['leaderboard_evidence']} "
        f"assisted={report['operator_simulator_ablation']['enabled']} "
        f"negative_layers={','.join(item['evidence_layer'] for item in report['negative_results']['failed_hypotheses'])}"
    )


if __name__ == "__main__":
    main()
