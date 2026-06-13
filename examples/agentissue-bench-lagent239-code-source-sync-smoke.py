#!/usr/bin/env python3
"""Smoke-test the no-run AgentIssue-Bench lagent_239 code-source sync plan."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "agentissue_bench_code_source_sync_plan_v0"
RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_ID = "agentissue-bench"
AGENTISSUE_SOURCE_COMMIT = "1d498dec35e347c4e7b9e1c318ef28fc5fa97318"
SELECTED_TAG = "lagent_239"
PATCH_OUTPUT_RELATIVE = "Patches/lagent_239/attempt.patch"
ISSUE_URL = "https://github.com/InternLM/lagent/issues/239"
ISSUE_BODY_HASH = "f4c8e9fdb337b030730c31e69ea7d62ffa1808fd9843ea17eeb4949d7533bb79"
ISSUE_COMMENTS_HASH = "6602126a5f058a9705f5e733cb4d1d5aad2c483e1a4f9cde114d97dca8fa3357"
LAGENT_REPO = "InternLM/lagent"
LAGENT_DEFAULT_BRANCH = "main"
LAGENT_HEAD_SHA = "0ab2e2f550477884743cd63fbca7bc4aa7b00290"
LAGENT_TREE_SHA = "e1fbfc26536a3bdb688c98a9a97732db84a0a2db"

FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "command_argv",
    "credential",
    "diff",
    "environment",
    "file_content",
    "local_path",
    "password",
    "patch_content",
    "raw_comment",
    "raw_issue_body",
    "raw_issue_title",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "source_diff",
    "test_body",
    "test_patch",
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
    "docker pull",
    "docker run",
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


def build_code_source_sync_plan() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "agentissue_source": {
            "repo": "alfin06/AgentIssue-Bench",
            "commit": AGENTISSUE_SOURCE_COMMIT,
        },
        "task_context": {
            "kind": "public_issue_hash_only",
            "issue_url": ISSUE_URL,
            "issue_body_hash": ISSUE_BODY_HASH,
            "issue_comments_hash": ISSUE_COMMENTS_HASH,
            "raw_issue_text_recorded_publicly": False,
        },
        "target_code_source": {
            "repo": LAGENT_REPO,
            "public": True,
            "private": False,
            "archived": False,
            "fork": False,
            "license_spdx": "Apache-2.0",
            "default_branch": LAGENT_DEFAULT_BRANCH,
            "head_sha": LAGENT_HEAD_SHA,
            "head_commit_date": "2026-04-20T07:14:00Z",
            "tree_sha": LAGENT_TREE_SHA,
            "root_tree_entry_count": 16,
            "root_tree_tree_count": 6,
            "root_tree_blob_count": 10,
            "root_tree_truncated": False,
            "repo_pushed_at": "2026-06-12T08:35:00Z",
            "repo_updated_at": "2026-06-11T08:40:16Z",
        },
        "sync_plan": {
            "method": "public_repo_checkout_or_sparse_checkout",
            "checkout_performed": False,
            "file_contents_read": False,
            "source_diffs_recorded": False,
            "local_paths_recorded": False,
            "future_workspace": "trusted_local_ephemeral_workspace",
            "future_record_public_metadata_only": True,
            "future_record_patch_hash_only": True,
        },
        "redacted_file_selection_rules": [
            {
                "rule_id": "issue_guided_public_repo_search",
                "description": "Future worker may inspect the public repository locally after execution gate; public artifacts keep only counts, hashes, and patch output metadata.",
                "raw_paths_recorded": False,
            },
            {
                "rule_id": "implementation_then_validation_scope",
                "description": "Future worker should identify candidate implementation and validation surfaces locally, then record only redacted counts until patch generation is approved.",
                "raw_paths_recorded": False,
            },
            {
                "rule_id": "no_generated_or_private_artifacts",
                "description": "Exclude generated outputs, credentials, sessions, local caches, raw trajectories, screenshots, and benchmark result directories from sync/writeback.",
                "raw_paths_recorded": False,
            },
        ],
        "future_patch_producer_inputs": {
            "selected_tag": SELECTED_TAG,
            "issue_body_hash": ISSUE_BODY_HASH,
            "issue_comments_hash": ISSUE_COMMENTS_HASH,
            "target_repo": LAGENT_REPO,
            "target_head_sha": LAGENT_HEAD_SHA,
            "target_tree_sha": LAGENT_TREE_SHA,
            "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
            "raw_issue_text_public": False,
            "raw_source_content_public": False,
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "docker_pulled": False,
            "docker_started": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "credentials_read": False,
            "raw_artifacts_read": False,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "agentissue-bench",
        "benchmark_id": packet["benchmark_id"],
        "source_commit": packet["agentissue_source"]["commit"],
        "mode": "public_code_source_sync_plan_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": packet["selected_tag"],
        "target_code_source": {
            "repo": packet["target_code_source"]["repo"],
            "head_sha": packet["target_code_source"]["head_sha"],
            "tree_sha": packet["target_code_source"]["tree_sha"],
            "root_tree_entry_count": packet["target_code_source"]["root_tree_entry_count"],
            "root_tree_truncated": packet["target_code_source"]["root_tree_truncated"],
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "validation": {
            "public_repo_metadata_available": True,
            "checkout_performed": False,
            "file_contents_read": False,
            "source_diffs_public": False,
            "raw_issue_text_public": False,
            "raw_source_content_public": False,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_patch_generation": True,
            "no_patch_evaluation": True,
            "no_docker_pull": True,
            "no_docker_run": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "paths_redacted": True,
        },
        "trials": [
            {
                "task_hash": packet["selected_tag"],
                "runner_status": "blocked",
                "exception_type": "not_run_code_source_sync_plan_only",
                "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
            }
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = []
    for path in key_paths(payload):
        leaf = path.rsplit(".", 1)[-1].strip("[]").lower()
        if leaf in FORBIDDEN_KEYS:
            key_hits.append(path)
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_code_source_sync_plan()
    run_event = reduce_to_benchmark_run(packet)
    source = packet["target_code_source"]
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert source["repo"] == LAGENT_REPO, packet
    assert source["public"] is True, packet
    assert source["private"] is False, packet
    assert source["default_branch"] == "main", packet
    assert source["head_sha"] == LAGENT_HEAD_SHA, packet
    assert source["tree_sha"] == LAGENT_TREE_SHA, packet
    assert source["root_tree_entry_count"] == 16, packet
    assert source["root_tree_truncated"] is False, packet
    assert packet["sync_plan"]["checkout_performed"] is False, packet
    assert packet["sync_plan"]["file_contents_read"] is False, packet
    assert packet["sync_plan"]["source_diffs_recorded"] is False, packet
    assert all(rule["raw_paths_recorded"] is False for rule in packet["redacted_file_selection_rules"]), packet
    assert packet["execution_boundary"]["codex_cli_invoked"] is False, packet
    assert packet["execution_boundary"]["docker_started"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["public_repo_metadata_available"] is True, run_event
    assert run_event["validation"]["checkout_performed"] is False, run_event
    assert run_event["validation"]["file_contents_read"] is False, run_event
    assert run_event["validation"]["no_patch_generation"] is True, run_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    return {
        "ok": True,
        "classification": "agentissue_bench_lagent239_code_source_sync_plan_v0",
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "target_repo": LAGENT_REPO,
        "target_head_sha": LAGENT_HEAD_SHA,
        "target_tree_sha": LAGENT_TREE_SHA,
        "root_tree_entry_count": source["root_tree_entry_count"],
        "events": [packet["schema_version"], run_event["schema_version"]],
        "checkout_performed": packet["sync_plan"]["checkout_performed"],
        "file_contents_read": packet["sync_plan"]["file_contents_read"],
        "source_diffs_recorded": packet["sync_plan"]["source_diffs_recorded"],
        "codex_cli_invoked": packet["execution_boundary"]["codex_cli_invoked"],
        "docker_started": packet["execution_boundary"]["docker_started"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
