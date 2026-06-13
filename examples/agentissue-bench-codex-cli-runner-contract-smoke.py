#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench Codex CLI runner contract."""

from __future__ import annotations

import json
from typing import Any


SCHEMA_VERSION = "agentissue_bench_codex_cli_runner_contract_v0"
BENCHMARK_ID = "agentissue-bench"
SELECTED_TAG = "lagent_239"
IMAGE = "alfin06/agentissue-bench:lagent_239"
ISSUE_URL = "https://github.com/InternLM/lagent/issues/239"
LEADERBOARD_URL = "https://alfin06.github.io/AgentIssue-Bench-Leaderboard/"
OFFICIAL_REPO = "https://github.com/alfin06/AgentIssue-Bench"

FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "codex_auth",
    "credential",
    "environment",
    "file_content",
    "fixed_diff",
    "gold_material",
    "local_path",
    "password",
    "patch_content",
    "raw_log",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "test_body",
    "trajectory",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "show_diff",
)


def key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def leaf(path: str) -> str:
    segment = path.rsplit(".", 1)[-1]
    if "[" in segment:
        segment = segment.split("[", 1)[0]
    return segment.lower()


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": BENCHMARK_ID,
        "official_metric_status": {
            "codex_cli_official_metric_found": False,
            "official_leaderboard_url": LEADERBOARD_URL,
            "official_repo": OFFICIAL_REPO,
            "official_leaderboard_rows_checked": [
                "AutoCodeRover + Claude 3.5 Sonnet",
                "Agentless + Claude 3.5 Sonnet",
                "Agentless + GPT-4o",
                "SWE-agent + Claude 3.5 Sonnet",
                "AutoCodeRover + GPT-4o",
                "SWE-agent + GPT-4o",
            ],
            "codex_cli_row_present": False,
        },
        "active_scope": {
            "only_active_benchmark": BENCHMARK_ID,
            "initial_tag": SELECTED_TAG,
            "expand_tags_after_single_tag_runner_passes": True,
            "no_other_benchmarks_until": "agentissue_codex_cli_runner_e2e_clean",
        },
        "runner_phases": [
            {
                "phase": "prepare_isolated_job",
                "runner_owned": True,
                "public_writeback": "counts_hashes_status_only",
                "copy_codex_home": False,
            },
            {
                "phase": "fetch_public_issue_context",
                "issue_url": ISSUE_URL,
                "raw_issue_context_allowed_private": True,
                "raw_issue_context_public": False,
            },
            {
                "phase": "pull_selected_image",
                "image": IMAGE,
                "single_tag_only": True,
                "all_tag_loop_allowed": False,
            },
            {
                "phase": "extract_buggy_source_from_container",
                "source": "container_buggy_snapshot",
                "host_git_baseline_required": True,
                "use_current_public_head_for_patch_generation": False,
            },
            {
                "phase": "run_codex_cli_patch_worker",
                "command_template": (
                    "codex exec --ephemeral --ignore-rules --sandbox workspace-write "
                    "--cd <buggy-source> --add-dir <job-root> --output-last-message "
                    "<job-root>/codex-last-message.txt <prompt-file>"
                ),
                "codex_auth_local_only": True,
                "copy_codex_home": False,
                "worker_network_allowed": False,
                "worker_docker_allowed": False,
                "worker_reads_fixed_diff": False,
            },
            {
                "phase": "write_attempt_patch",
                "patch_output": "Patches/lagent_239/attempt.patch",
                "patch_content_public": False,
                "patch_hash_public": True,
            },
            {
                "phase": "single_tag_container_eval",
                "command_template": (
                    "docker run --platform linux/amd64 --rm --entrypoint bash "
                    "-v <patch-dir>:/patches:ro alfin06/agentissue-bench:lagent_239 "
                    "-c '<apply_patch_and_test_patched>'"
                ),
                "official_helper_scripts_used": False,
                "docker_env_credentials": False,
                "upload": False,
                "submit": False,
                "public_ranking_path": False,
            },
            {
                "phase": "compact_reducer",
                "allowed_public_fields": [
                    "tag",
                    "image_digest",
                    "patch_sha256",
                    "patch_bytes",
                    "exit_code",
                    "resolved",
                    "duration_seconds",
                    "log_sha256",
                    "no_upload",
                    "no_submit",
                ],
                "raw_log_public": False,
            },
        ],
        "stop_rules": {
            "do_not_run_manual_agent_worker": True,
            "do_not_use_current_head_as_patch_source": True,
            "do_not_read_fixed_diff_before_patch_generation": True,
            "do_not_run_official_all_tag_helpers": True,
            "do_not_sync_codex_auth_to_shared_host_or_container": True,
            "do_not_publish_raw_patch_or_logs": True,
        },
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    bad_keys = [path for path in key_paths(payload) if leaf(path) in FORBIDDEN_KEYS]
    assert not bad_keys, bad_keys
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    contract = build_contract()
    phases = {item["phase"]: item for item in contract["runner_phases"]}
    assert contract["schema_version"] == SCHEMA_VERSION, contract
    assert contract["official_metric_status"]["codex_cli_official_metric_found"] is False, contract
    assert contract["official_metric_status"]["codex_cli_row_present"] is False, contract
    assert contract["active_scope"]["only_active_benchmark"] == BENCHMARK_ID, contract
    assert contract["active_scope"]["initial_tag"] == SELECTED_TAG, contract
    assert phases["extract_buggy_source_from_container"]["host_git_baseline_required"] is True, contract
    assert phases["extract_buggy_source_from_container"]["use_current_public_head_for_patch_generation"] is False
    assert phases["run_codex_cli_patch_worker"]["codex_auth_local_only"] is True, contract
    assert phases["run_codex_cli_patch_worker"]["copy_codex_home"] is False, contract
    assert phases["run_codex_cli_patch_worker"]["worker_reads_fixed_diff"] is False, contract
    assert phases["single_tag_container_eval"]["official_helper_scripts_used"] is False, contract
    assert phases["single_tag_container_eval"]["docker_env_credentials"] is False, contract
    assert phases["single_tag_container_eval"]["upload"] is False, contract
    assert contract["stop_rules"]["do_not_run_manual_agent_worker"] is True, contract
    assert contract["stop_rules"]["do_not_use_current_head_as_patch_source"] is True, contract
    assert contract["stop_rules"]["do_not_read_fixed_diff_before_patch_generation"] is True, contract
    assert_public_safe(contract)
    return {
        "ok": True,
        "classification": SCHEMA_VERSION,
        "contract": contract,
        "official_codex_cli_metric_found": False,
        "only_active_benchmark": BENCHMARK_ID,
        "initial_tag": SELECTED_TAG,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
