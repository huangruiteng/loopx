#!/usr/bin/env python3
"""Smoke-test the official Terminal-Bench hard-case selection contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-official-hard-case-selection-v0.md"
README = TOPIC_DIR / "README.md"

SCHEMA = "terminal_bench_official_hard_case_selection_v0"
BENCHMARK_ID = "terminal-bench@2.0"
TASK_COUNT = 89
PRIMARY_TASKS = (
    "fix-code-vulnerability",
    "modernize-scientific-stack",
    "llm-inference-batching-scheduler",
)
BACKUP_TASKS = (
    "qemu-startup",
    "qemu-alpine-ssh",
    "compile-compcert",
    "git-leak-recovery",
)

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Official Hard-Case Selection V0",
    BENCHMARK_ID,
    "89 tasks",
    "fix-code-vulnerability",
    "modernize-scientific-stack",
    "llm-inference-batching-scheduler",
    "codex-goal-mode",
    "codex-loopx",
    "case_semantics_changed_by_harness=true",
    "official_score_comparable_to_native_codex=false",
    "python3 examples/terminal-bench-official-hard-case-selection-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
]


def selection_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "official_task_count": TASK_COUNT,
        "source_surface": "harbor_registry_terminal_bench_2_0",
        "real_run": False,
        "submit_eligible": False,
        "full_benchmark_run_requested": False,
        "primary_batch": [
            {
                "rank": index + 1,
                "task_id": task_id,
                "run_pair": ["codex-goal-mode", "codex-loopx"],
            }
            for index, task_id in enumerate(PRIMARY_TASKS)
        ],
        "backup_queue": list(BACKUP_TASKS),
        "selection_policy": {
            "prefer_long_horizon_debugging": True,
            "prefer_failure_attribution_value": True,
            "avoid_simple_parsing_first": True,
            "batch_size": len(PRIMARY_TASKS),
            "run_all_89_first": False,
        },
        "paired_run_invariants": {
            "same_benchmark_id": True,
            "same_task_id": True,
            "same_model": True,
            "same_runner_source": True,
            "same_attempts_and_concurrency": True,
            "same_prompt_tests_scoring_resources": True,
            "no_upload_private_jobs": True,
        },
        "managed_mode_claim_boundary": {
            "model_plus_harness_pair": True,
            "case_semantics_changed_by_harness": True,
            "loopx_inside_case": True,
            "official_score_comparable_to_native_codex": False,
            "leaderboard_evidence": False,
        },
        "required_metrics": [
            "official_verifier_reward",
            "runner_return_status",
            "wall_time_and_timeout_tier",
            "codex_usage_when_available",
            "loopx_cli_calls",
            "codex_runtime_goal_tool_calls",
            "worker_benchmark_run_schema_validity",
            "failure_attribution",
        ],
        "stop_conditions": [
            "do_not_run_all_89_tasks",
            "do_not_upload_share_publish_or_submit_leaderboard",
            "do_not_record_raw_prompts_sessions_logs_paths_or_credentials",
            "do_not_change_task_prompt_tests_scoring_resources_or_files",
            "do_not_claim_paper_style_uplift_from_too_few_cases",
            "do_not_treat_sample_results_as_official_benchmark_evidence",
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 12000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    leaked = [snippet for snippet in FORBIDDEN_TEXT if snippet in text]
    assert not leaked, leaked
    assert "terminal-bench-official-hard-case-selection-v0.md" in readme, readme


def assert_selection_payload(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == SCHEMA, payload
    assert payload["benchmark_id"] == BENCHMARK_ID, payload
    assert payload["official_task_count"] == TASK_COUNT, payload
    assert payload["real_run"] is False, payload
    assert payload["submit_eligible"] is False, payload
    assert payload["full_benchmark_run_requested"] is False, payload
    assert [item["task_id"] for item in payload["primary_batch"]] == list(PRIMARY_TASKS), payload
    assert payload["backup_queue"] == list(BACKUP_TASKS), payload
    assert payload["selection_policy"]["run_all_89_first"] is False, payload
    assert payload["selection_policy"]["batch_size"] == 3, payload
    for item in payload["primary_batch"]:
        assert item["run_pair"] == ["codex-goal-mode", "codex-loopx"], item
    invariants = payload["paired_run_invariants"]
    assert all(invariants.values()), invariants
    managed = payload["managed_mode_claim_boundary"]
    assert managed["model_plus_harness_pair"] is True, managed
    assert managed["case_semantics_changed_by_harness"] is True, managed
    assert managed["loopx_inside_case"] is True, managed
    assert managed["official_score_comparable_to_native_codex"] is False, managed
    assert managed["leaderboard_evidence"] is False, managed
    assert "loopx_cli_calls" in payload["required_metrics"], payload
    assert "do_not_run_all_89_tasks" in payload["stop_conditions"], payload
    assert_public_safe(payload)


def main() -> None:
    assert_doc_contract()
    payload = selection_payload()
    assert_selection_payload(payload)
    print(
        "ok "
        f"benchmark={payload['benchmark_id']} "
        f"tasks={payload['official_task_count']} "
        f"primary={','.join(PRIMARY_TASKS)} "
        f"real_run={payload['real_run']}"
    )


if __name__ == "__main__":
    main()
