#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench official-pilot readiness fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
DOSSIER = TOPIC_DIR / "paper-runner-dossier.md"
READINESS_DOC = TOPIC_DIR / "terminal-bench-official-pilot-readiness-v0.md"

DECISION_ID = "terminal_bench_official_pilot_decision_packet_v0"
BENCHMARK_ID = "terminal-bench@2.0"
RESULT_SCHEMA = "benchmark_result_v0"
COMPARISON_SCHEMA = "benchmark_comparison_v0"

REQUIRED_DOC_SNIPPETS = [
    DECISION_ID,
    "benchmark_result_v0",
    "benchmark_comparison_v0",
    "benchmark_run_v0",
    "bare_codex_cli_readiness",
    "passive_goal_harness_wrapper_readiness",
    "official_task_score.kind = not_run",
    "readiness_checklist_v0",
    "no real benchmark",
    "no Docker",
    "no model API",
    "no cloud sandbox",
    "no paid compute",
    "no leaderboard upload",
    "no private trace",
]

REQUIRED_README_SNIPPET = "terminal-bench-official-pilot-readiness-v0.md"

CHECKLIST_ITEMS = [
    "runner_source_placeholder",
    "runner_version_or_commit_placeholder",
    "task_id_or_split_placeholder",
    "agent_command_boundary",
    "official_score_fields",
    "goal_harness_control_plane_score_fields",
    "benchmark_run_pairing_rule",
    "public_artifact_manifest",
    "side_effect_audit",
    "forbidden_surface_audit",
    "stop_conditions_before_real_execution",
]

STOP_CONDITIONS = [
    "do_not_run_terminal_bench",
    "do_not_run_harbor",
    "do_not_start_docker",
    "do_not_invoke_codex_or_model_api",
    "do_not_use_cloud_sandbox",
    "do_not_use_paid_compute",
    "do_not_upload_leaderboard_trace",
    "do_not_copy_private_trace",
    "do_not_claim_official_leaderboard_uplift",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPENAI" + "_API_KEY",
    "ANTHROPIC" + "_API_KEY",
    "DAYTONA" + "_API_KEY",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
]


def checklist() -> list[dict[str, Any]]:
    return [
        {
            "id": item,
            "present": True,
            "source": "terminal_bench_official_pilot_decision_packet_v0",
        }
        for item in CHECKLIST_ITEMS
    ]


def result_shell(scenario_id: str, harness_identity: str) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "decision_id": DECISION_ID,
        "benchmark_id": BENCHMARK_ID,
        "task_id": "readiness_only_no_task_selected",
        "scenario_id": scenario_id,
        "harness_identity": harness_identity,
        "worker_surface": "codex_cli_official_or_custom_agent_boundary_under_review",
        "terminal_state": "readiness_only",
        "official_task_score": {
            "kind": "not_run",
            "value": None,
            "reason": "readiness fixture does not run Terminal-Bench, Harbor, Docker, Codex, model APIs, cloud sandboxes, paid compute, or leaderboard upload paths",
        },
        "control_plane_score": {
            "kind": "readiness_checklist_v0",
            "value": None,
            "components": checklist(),
        },
        "benchmark_run_pairing_rule": {
            "schema_version": "benchmark_run_v0",
            "future_modes": ["bare_codex_cli", "passive_goal_harness_wrapper"],
            "one_compact_row_per_mode": True,
            "append_runtime_history_now": False,
        },
        "evidence_manifest": {
            "runner_source": "placeholder: official Terminal-Bench or Harbor path",
            "runner_version_or_commit": "placeholder: record before real pilot",
            "task_id_or_split": "placeholder: record before real pilot",
            "agent_command_boundary": "placeholder: record exact Codex CLI/custom-agent command before real pilot",
            "artifact_publicness": "public_readiness_only",
        },
        "trace_publicness": "public_readiness_only",
        "side_effect_audit_passed": True,
        "forbidden_surface_audit_passed": True,
        "runner_protocol_compliance_passed": None,
        "capability_violation_count": 0,
        "validation_pass_count": len(CHECKLIST_ITEMS),
        "validation_fail_count": 0,
        "stop_conditions": STOP_CONDITIONS,
    }


def comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_ids = [result["scenario_id"] for result in results]
    return {
        "schema_version": COMPARISON_SCHEMA,
        "decision_id": DECISION_ID,
        "benchmark_id": BENCHMARK_ID,
        "mode_pair": scenario_ids,
        "official_task_score_delta": "not_applicable_readiness_only",
        "control_plane_score_delta": "not_applicable_readiness_only",
        "ready_to_attempt_no_submit_setup_probe": True,
        "ready_to_run_real_benchmark": False,
        "ready_to_submit_leaderboard": False,
        "requires_explicit_authorization_for_real_execution": True,
        "checklist_pass_count": sum(
            1
            for result in results
            for item in result["control_plane_score"]["components"]
            if item["present"]
        ),
        "stop_conditions": STOP_CONDITIONS,
        "next_action": (
            "inspect official runner/custom-agent boundary and record source, version, "
            "task placeholder, exact command boundary, and stop condition without "
            "running Terminal-Bench"
        ),
    }


def assert_doc_contract() -> None:
    text = READINESS_DOC.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert DECISION_ID in DOSSIER.read_text(encoding="utf-8")
    assert REQUIRED_README_SNIPPET in README.read_text(encoding="utf-8")


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 12000, len(text)


def assert_result_contract(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    assert {result["schema_version"] for result in results} == {RESULT_SCHEMA}
    assert {result["benchmark_id"] for result in results} == {BENCHMARK_ID}
    assert {result["decision_id"] for result in results} == {DECISION_ID}
    assert {result["terminal_state"] for result in results} == {"readiness_only"}
    assert {result["official_task_score"]["kind"] for result in results} == {"not_run"}
    assert all(result["official_task_score"]["value"] is None for result in results)
    assert {result["control_plane_score"]["kind"] for result in results} == {"readiness_checklist_v0"}
    assert all(result["benchmark_run_pairing_rule"]["append_runtime_history_now"] is False for result in results)
    assert all(result["side_effect_audit_passed"] for result in results)
    assert all(result["forbidden_surface_audit_passed"] for result in results)
    assert all(result["capability_violation_count"] == 0 for result in results)
    assert all(result["runner_protocol_compliance_passed"] is None for result in results)
    assert all(set(result["stop_conditions"]) == set(STOP_CONDITIONS) for result in results)
    assert {item["id"] for item in results[0]["control_plane_score"]["components"]} == set(CHECKLIST_ITEMS)

    assert summary["schema_version"] == COMPARISON_SCHEMA, summary
    assert summary["official_task_score_delta"] == "not_applicable_readiness_only", summary
    assert summary["control_plane_score_delta"] == "not_applicable_readiness_only", summary
    assert summary["ready_to_attempt_no_submit_setup_probe"] is True, summary
    assert summary["ready_to_run_real_benchmark"] is False, summary
    assert summary["ready_to_submit_leaderboard"] is False, summary
    assert summary["requires_explicit_authorization_for_real_execution"] is True, summary
    assert summary["checklist_pass_count"] == len(results) * len(CHECKLIST_ITEMS), summary

    assert_public_safe({"results": results, "summary": summary})


def main() -> None:
    assert_doc_contract()
    results = [
        result_shell("bare_codex_cli_readiness", "none"),
        result_shell("passive_goal_harness_wrapper_readiness", "goal_harness_passive_wrapper"),
    ]
    summary = comparison(results)
    assert_result_contract(results, summary)
    print(
        "terminal-bench-official-pilot-readiness-smoke ok "
        f"scenarios={len(results)} checklist={summary['checklist_pass_count']} "
        f"real_run={summary['ready_to_run_real_benchmark']}"
    )


if __name__ == "__main__":
    main()
