#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench no-submit boundary probe contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
NOTE = TOPIC_DIR / "terminal-bench-no-submit-boundary-probe-v0.md"
README = TOPIC_DIR / "README.md"
DOSSIER = TOPIC_DIR / "paper-runner-dossier.md"

SCHEMA = "runner_boundary_probe_v0"
DECISION_ID = "terminal_bench_official_pilot_decision_packet_v0"
BENCHMARK_ID = "terminal-bench@2.0"

STOP_CONDITIONS = [
    "do_not_execute_harbor_run",
    "do_not_execute_tb_run",
    "do_not_execute_codex_exec",
    "do_not_execute_custom_agent_wrapper",
    "do_not_start_docker",
    "do_not_use_cloud_sandbox",
    "do_not_invoke_model_api",
    "do_not_use_paid_compute",
    "do_not_upload_or_submit_leaderboard_trace",
    "do_not_modify_official_tasks_timeouts_resources_or_scoring",
    "do_not_copy_credentials_host_paths_private_logs_or_raw_sessions",
    "do_not_claim_official_pass_fail_reward_accuracy_or_uplift",
]

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench No-Submit Boundary Probe V0",
    SCHEMA,
    DECISION_ID,
    BENCHMARK_ID,
    "no-submit runner-boundary probe",
    "Allowed Now",
    "Forbidden Now",
    "benchmark_run_v0",
    "benchmark_result_v0",
    "bare_codex_cli",
    "passive_goal_harness_wrapper",
    "execution_authorized = false",
    "submit_eligible = false",
    "real_run = false",
    "public_boundary_probe_only",
    "custom `--agent-import-path` path remains a",
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


def probe_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "decision_id": DECISION_ID,
        "benchmark_id": BENCHMARK_ID,
        "probe_state": "no_submit_boundary_only",
        "real_run": False,
        "submit_eligible": False,
        "trace_publicness": "public_boundary_probe_only",
        "runner_sources": [
            {
                "name": "harbor",
                "role": "terminal_bench_2_official_runner_candidate",
                "source_kind": "public_repository",
                "repo_url": "https://github.com/laude-institute/harbor",
                "inspected_commit": "8cfac6ad91c5c566ff14040cc4acbfe94ad42356",
            },
            {
                "name": "terminal-bench",
                "role": "legacy_tb_runner_compatibility_candidate",
                "source_kind": "public_repository",
                "repo_url": "https://github.com/harbor-framework/terminal-bench",
                "inspected_commit": "1a6ffa9674b571da0ed040c470cb40c4d85f9b9b",
            },
        ],
        "mode_boundaries": [
            {
                "mode": "bare_codex_cli",
                "runner": "harbor",
                "agent_surface": "built_in_codex_agent",
                "command_template": (
                    "harbor run --dataset terminal-bench@2.0 --agent codex "
                    "--model <model> --n-concurrent 1 --jobs-dir <private-output-dir>"
                ),
                "execution_authorized": False,
                "submit_eligible": False,
                "real_run": False,
                "expected_future_event": "benchmark_run_v0",
            },
            {
                "mode": "passive_goal_harness_wrapper",
                "runner": "harbor",
                "agent_surface": "passive_observer_after_official_outputs_exist",
                "command_template": "goal-harness history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
                "execution_authorized": False,
                "submit_eligible": False,
                "real_run": False,
                "expected_future_event": "benchmark_run_v0",
            },
        ],
        "custom_agent_boundary": {
            "surface": "--agent-import-path",
            "state": "deferred_local_only_experiment_gate",
            "execution_authorized": False,
            "submit_eligible": False,
        },
        "expected_future_events": [
            "benchmark_run_v0:bare_codex_cli",
            "benchmark_run_v0:passive_goal_harness_wrapper",
            "benchmark_result_v0:paired_comparison",
        ],
        "official_task_score": {
            "kind": "not_run",
            "value": None,
        },
        "side_effect_budget": {
            "docker": False,
            "codex_cli": False,
            "model_api": False,
            "cloud_sandbox": False,
            "paid_compute": False,
            "leaderboard_upload": False,
            "official_runner_mutation": False,
        },
        "stop_conditions": STOP_CONDITIONS,
    }


def assert_doc_contract() -> None:
    text = NOTE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    dossier = DOSSIER.read_text(encoding="utf-8")

    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing

    assert "terminal-bench-no-submit-boundary-probe-v0.md" in readme
    assert "runner_boundary_probe_v0" in dossier
    assert "no-submit boundary probe" in dossier

    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 9000, len(text)


def assert_payload_contract(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == SCHEMA, payload
    assert payload["decision_id"] == DECISION_ID, payload
    assert payload["benchmark_id"] == BENCHMARK_ID, payload
    assert payload["probe_state"] == "no_submit_boundary_only", payload
    assert payload["real_run"] is False, payload
    assert payload["submit_eligible"] is False, payload
    assert payload["trace_publicness"] == "public_boundary_probe_only", payload
    assert payload["official_task_score"] == {"kind": "not_run", "value": None}, payload
    assert {source["source_kind"] for source in payload["runner_sources"]} == {"public_repository"}, payload
    assert {source["name"] for source in payload["runner_sources"]} == {"harbor", "terminal-bench"}, payload

    boundaries = {item["mode"]: item for item in payload["mode_boundaries"]}
    assert set(boundaries) == {"bare_codex_cli", "passive_goal_harness_wrapper"}, payload
    assert all(item["execution_authorized"] is False for item in boundaries.values()), payload
    assert all(item["submit_eligible"] is False for item in boundaries.values()), payload
    assert all(item["real_run"] is False for item in boundaries.values()), payload
    assert all(item["expected_future_event"] == "benchmark_run_v0" for item in boundaries.values()), payload
    assert payload["custom_agent_boundary"]["execution_authorized"] is False, payload
    assert payload["custom_agent_boundary"]["submit_eligible"] is False, payload

    assert set(payload["stop_conditions"]) == set(STOP_CONDITIONS), payload
    assert all(value is False for value in payload["side_effect_budget"].values()), payload
    assert "benchmark_result_v0:paired_comparison" in payload["expected_future_events"], payload
    assert_public_safe(payload)


def main() -> None:
    assert_doc_contract()
    payload = probe_payload()
    assert_payload_contract(payload)
    print(
        "terminal-bench-no-submit-boundary-probe-smoke ok "
        f"sources={len(payload['runner_sources'])} modes={len(payload['mode_boundaries'])} "
        f"real_run={payload['real_run']} submit={payload['submit_eligible']}"
    )


if __name__ == "__main__":
    main()
