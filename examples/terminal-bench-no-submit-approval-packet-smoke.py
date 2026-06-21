#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench no-submit approval packet contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
NOTE = TOPIC_DIR / "terminal-bench-no-submit-approval-packet-v0.md"
README = TOPIC_DIR / "README.md"

SCHEMA = "terminal_bench_no_submit_approval_packet_v0"
PACKET_ID = "terminal_bench_no_submit_setup_check_packet_v0"
BENCHMARK_ID = "terminal-bench@2.0"

PRE_APPROVAL_COMMANDS = [
    "python3 examples/terminal-bench-no-submit-approval-packet-smoke.py",
]

CANDIDATE_AFTER_APPROVAL_COMMANDS = [
    "git ls-remote https://github.com/laude-institute/harbor HEAD",
    "git ls-remote https://github.com/harbor-framework/terminal-bench HEAD",
    "harbor --help",
    "tb --help",
    "loopx history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
    "loopx history append-benchmark-result --benchmark-result-json <benchmark-result-v0.json>",
]

FORBIDDEN_SURFACES = [
    "harbor_run",
    "tb_run",
    "codex_exec",
    "custom_agent_wrapper",
    "docker",
    "container_runtime",
    "cloud_sandbox",
    "model_api",
    "paid_compute",
    "external_evaluator",
    "leaderboard_upload",
    "official_runner_mutation",
    "raw_runner_log",
    "private_trace",
    "host_absolute_path",
    "credential",
    "raw_agent_session_trace",
    "official_score_claim",
]

EXPECTED_PUBLIC_ARTIFACTS = [
    "terminal_bench_no_submit_setup_check_v0.json",
    "benchmark_run_v0:bare_codex_cli_no_submit_setup",
    "benchmark_run_v0:passive_loopx_wrapper_no_submit_setup",
    "benchmark_result_v0:readiness_only_not_run",
]

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench No-Submit Approval Packet V0",
    SCHEMA,
    PACKET_ID,
    BENCHMARK_ID,
    "Allowed Before Approval",
    "Candidate Commands After Approval",
    "Forbidden Surfaces",
    "Side-Effect Budget",
    "Expected Public Artifacts",
    "Ingestion Plan",
    "benchmark_run_v0",
    "benchmark_result_v0",
    "approval_state = requested",
    "execution_authorized = false",
    "submit_eligible = false",
    "real_run = false",
    "git ls-remote https://github.com/laude-institute/harbor HEAD",
    "git ls-remote https://github.com/harbor-framework/terminal-bench HEAD",
    "harbor --help",
    "tb --help",
    "official_task_score.kind = not_run",
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


def approval_packet() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "packet_id": PACKET_ID,
        "benchmark_id": BENCHMARK_ID,
        "approval_state": "requested",
        "execution_authorized": False,
        "submit_eligible": False,
        "real_run": False,
        "decision_scope": "terminal_bench_or_harbor_no_submit_setup_check",
        "allowed_before_approval": PRE_APPROVAL_COMMANDS,
        "candidate_after_approval_commands": CANDIDATE_AFTER_APPROVAL_COMMANDS,
        "forbidden_surfaces": FORBIDDEN_SURFACES,
        "side_effect_budget": {
            "public_git_metadata_after_approval": True,
            "cli_help_after_approval": True,
            "docker": False,
            "codex_cli": False,
            "model_api": False,
            "cloud_sandbox": False,
            "paid_compute": False,
            "leaderboard_upload": False,
            "official_runner_mutation": False,
        },
        "expected_public_artifacts": EXPECTED_PUBLIC_ARTIFACTS,
        "ingestion_plan": [
            {
                "schema_version": "benchmark_run_v0",
                "scenario_id": "bare_codex_cli_no_submit_setup",
                "runner_mode": "setup_check_no_submit",
                "real_run": False,
                "submit_eligible": False,
                "trace_publicness": "public_no_submit_setup_check",
            },
            {
                "schema_version": "benchmark_run_v0",
                "scenario_id": "passive_loopx_wrapper_no_submit_setup",
                "runner_mode": "setup_check_no_submit",
                "real_run": False,
                "submit_eligible": False,
                "trace_publicness": "public_no_submit_setup_check",
            },
            {
                "schema_version": "benchmark_result_v0",
                "scenario_id": "terminal_bench_no_submit_readiness",
                "terminal_state": "readiness_only",
                "official_task_score": {"kind": "not_run", "value": None},
                "claim_boundary": "approval_boundary_only_not_official_evidence",
            },
        ],
        "stop_conditions": [
            "stop_before_runner_execution",
            "stop_before_docker_or_container_runtime",
            "stop_before_codex_or_model_api",
            "stop_before_cloud_or_paid_compute",
            "stop_before_external_evaluator",
            "stop_before_leaderboard_upload",
            "stop_before_private_trace_or_raw_log_ingest",
            "stop_before_official_score_or_uplift_claim",
        ],
    }


def assert_doc_contract() -> None:
    text = NOTE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-no-submit-approval-packet-v0.md" in readme, readme
    assert SCHEMA in readme, readme

    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 10000, len(text)


def assert_packet_contract(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == SCHEMA, payload
    assert payload["packet_id"] == PACKET_ID, payload
    assert payload["benchmark_id"] == BENCHMARK_ID, payload
    assert payload["approval_state"] == "requested", payload
    assert payload["execution_authorized"] is False, payload
    assert payload["submit_eligible"] is False, payload
    assert payload["real_run"] is False, payload

    assert payload["allowed_before_approval"] == PRE_APPROVAL_COMMANDS, payload
    assert payload["candidate_after_approval_commands"] == CANDIDATE_AFTER_APPROVAL_COMMANDS, payload
    assert set(payload["forbidden_surfaces"]) == set(FORBIDDEN_SURFACES), payload
    assert set(payload["expected_public_artifacts"]) == set(EXPECTED_PUBLIC_ARTIFACTS), payload

    side_effect_budget = payload["side_effect_budget"]
    assert side_effect_budget["public_git_metadata_after_approval"] is True, payload
    assert side_effect_budget["cli_help_after_approval"] is True, payload
    assert side_effect_budget["docker"] is False, payload
    assert side_effect_budget["codex_cli"] is False, payload
    assert side_effect_budget["model_api"] is False, payload
    assert side_effect_budget["cloud_sandbox"] is False, payload
    assert side_effect_budget["paid_compute"] is False, payload
    assert side_effect_budget["leaderboard_upload"] is False, payload
    assert side_effect_budget["official_runner_mutation"] is False, payload

    run_rows = [row for row in payload["ingestion_plan"] if row["schema_version"] == "benchmark_run_v0"]
    result_rows = [
        row for row in payload["ingestion_plan"] if row["schema_version"] == "benchmark_result_v0"
    ]
    assert len(run_rows) == 2, payload
    assert len(result_rows) == 1, payload
    assert all(row["runner_mode"] == "setup_check_no_submit" for row in run_rows), payload
    assert all(row["real_run"] is False for row in run_rows), payload
    assert all(row["submit_eligible"] is False for row in run_rows), payload
    assert result_rows[0]["terminal_state"] == "readiness_only", payload
    assert result_rows[0]["official_task_score"] == {"kind": "not_run", "value": None}, payload
    assert result_rows[0]["claim_boundary"] == "approval_boundary_only_not_official_evidence", payload

    forbidden_command_fragments = ["harbor run", "tb run", "codex exec", "--agent-import-path"]
    command_text = "\n".join(payload["candidate_after_approval_commands"])
    assert not any(fragment in command_text for fragment in forbidden_command_fragments), payload
    assert_public_safe(payload)


def main() -> None:
    assert_doc_contract()
    payload = approval_packet()
    assert_packet_contract(payload)
    print(
        "terminal-bench-no-submit-approval-packet-smoke ok "
        f"commands={len(payload['candidate_after_approval_commands'])} "
        f"artifacts={len(payload['expected_public_artifacts'])} "
        f"authorized={payload['execution_authorized']}"
    )


if __name__ == "__main__":
    main()
