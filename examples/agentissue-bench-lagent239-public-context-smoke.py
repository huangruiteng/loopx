#!/usr/bin/env python3
"""Smoke-test public-safe AgentIssue-Bench lagent_239 issue context packet."""

from __future__ import annotations

import json
from typing import Any


SCHEMA_VERSION = "agentissue_bench_public_context_packet_v0"
BENCHMARK_RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_ID = "agentissue-bench"
SOURCE_COMMIT = "1d498dec35e347c4e7b9e1c318ef28fc5fa97318"
SELECTED_TAG = "lagent_239"
ISSUE_URL = "https://github.com/InternLM/lagent/issues/239"
ISSUE_CONTEXT = {
    "url": ISSUE_URL,
    "number": 239,
    "state": "closed",
    "locked": False,
    "created_at": "2024-08-21T10:43:51Z",
    "updated_at": "2024-08-28T07:04:09Z",
    "closed_at": "2024-08-28T07:04:09Z",
    "title_hash": "9a0600fe2e0c88d886847e3afe433508b458463e978a99eb86e0d743102408b2",
    "title_chars": 57,
    "body_hash": "f4c8e9fdb337b030730c31e69ea7d62ffa1808fd9843ea17eeb4949d7533bb79",
    "body_chars": 125,
    "comment_count": 1,
    "comments_hash": "6602126a5f058a9705f5e733cb4d1d5aad2c483e1a4f9cde114d97dca8fa3357",
    "comments_chars": 168,
    "label_count": 0,
    "pull_request": False,
}

FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "body",
    "codex_auth",
    "comment_body",
    "credential",
    "docker_output",
    "gold_patch",
    "local_path",
    "password",
    "problem_statement",
    "raw_body",
    "raw_comment",
    "raw_output",
    "raw_title",
    "screenshot",
    "session",
    "solution",
    "test_list",
    "test_patch",
    "title",
    "trajectory",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI_API_KEY",
    "CODEX_ACCESS_TOKEN",
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


def build_context_packet() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": BENCHMARK_ID,
        "source_repo": "alfin06/AgentIssue-Bench",
        "source_commit": SOURCE_COMMIT,
        "selected_tag": SELECTED_TAG,
        "selected_image": "alfin06/agentissue-bench:lagent_239",
        "context_route": {
            "kind": "public_github_issue_hash_only",
            "repo": "InternLM/lagent",
            "issue_number": ISSUE_CONTEXT["number"],
            "issue_url": ISSUE_CONTEXT["url"],
            "issue_visible": True,
            "issue_state": ISSUE_CONTEXT["state"],
            "issue_locked": ISSUE_CONTEXT["locked"],
            "issue_created_at": ISSUE_CONTEXT["created_at"],
            "issue_updated_at": ISSUE_CONTEXT["updated_at"],
            "issue_closed_at": ISSUE_CONTEXT["closed_at"],
            "title_hash": ISSUE_CONTEXT["title_hash"],
            "title_chars": ISSUE_CONTEXT["title_chars"],
            "body_hash": ISSUE_CONTEXT["body_hash"],
            "body_chars": ISSUE_CONTEXT["body_chars"],
            "comment_count": ISSUE_CONTEXT["comment_count"],
            "comments_hash": ISSUE_CONTEXT["comments_hash"],
            "comments_chars": ISSUE_CONTEXT["comments_chars"],
            "label_count": ISSUE_CONTEXT["label_count"],
            "pull_request": ISSUE_CONTEXT["pull_request"],
        },
        "read_boundary": {
            "public_issue_title_read": True,
            "public_issue_body_read": True,
            "public_issue_comments_read": True,
            "public_issue_raw_text_recorded": False,
            "problem_statement_recorded": False,
            "solution_or_gold_material_recorded": False,
            "test_material_recorded": False,
            "local_paths_recorded": False,
        },
        "execution_boundary": {
            "docker_manifest_already_ready": True,
            "docker_pulled": False,
            "docker_started": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "credentials_read": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
        "next_packet": {
            "kind": "local_codex_patch_producer_no_run_packet",
            "ready": True,
            "needs_code_source_sync": True,
            "needs_execution_gate": True,
            "recommended_action": (
                "prepare a no-run local Codex patch-producer packet that uses "
                "the public issue context and keeps raw issue text, code diffs, "
                "patches, tests, credentials, Docker execution, and uploads out "
                "of public artifacts"
            ),
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": BENCHMARK_RUN_SCHEMA,
        "source_runner": "agentissue-bench",
        "benchmark_id": BENCHMARK_ID,
        "source_commit": packet["source_commit"],
        "mode": "public_context_hash_only_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": "lagent_239",
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
            "public_issue_context_available": True,
            "raw_issue_text_public": False,
            "raw_patch_or_test_material_public": False,
            "no_docker_pull": True,
            "no_docker_run": True,
            "no_model_call": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "paths_redacted": True,
        },
        "trials": [
            {
                "task_hash": "lagent_239",
                "runner_status": "blocked",
                "exception_type": "not_run_context_packet_only",
            }
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    bad_keys = []
    for path in key_paths(payload):
        leaf = path.rsplit(".", 1)[-1].strip("[]").lower()
        if leaf in FORBIDDEN_KEYS:
            bad_keys.append(path)
    assert not bad_keys, bad_keys
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_context_packet()
    run_event = reduce_to_benchmark_run(packet)
    assert packet["schema_version"] == SCHEMA_VERSION, packet
    assert packet["context_route"]["issue_visible"] is True, packet
    assert packet["context_route"]["issue_state"] == "closed", packet
    assert packet["context_route"]["title_chars"] == 57, packet
    assert packet["context_route"]["body_chars"] == 125, packet
    assert packet["context_route"]["comment_count"] == 1, packet
    assert packet["read_boundary"]["public_issue_body_read"] is True, packet
    assert packet["read_boundary"]["public_issue_raw_text_recorded"] is False, packet
    assert packet["execution_boundary"]["docker_pulled"] is False, packet
    assert packet["execution_boundary"]["docker_started"] is False, packet
    assert packet["execution_boundary"]["model_api_invoked"] is False, packet
    assert packet["execution_boundary"]["upload"] is False, packet
    assert packet["execution_boundary"]["submit"] is False, packet
    assert run_event["schema_version"] == BENCHMARK_RUN_SCHEMA, run_event
    assert run_event["validation"]["public_issue_context_available"] is True, run_event
    assert run_event["validation"]["raw_issue_text_public"] is False, run_event
    assert run_event["validation"]["no_docker_run"] is True, run_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    return {
        "ok": True,
        "classification": "agentissue_bench_lagent239_public_context_packet_v0",
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "issue_url": ISSUE_URL,
        "issue_state": packet["context_route"]["issue_state"],
        "body_hash": packet["context_route"]["body_hash"],
        "comment_count": packet["context_route"]["comment_count"],
        "raw_issue_text_recorded": packet["read_boundary"]["public_issue_raw_text_recorded"],
        "docker_started": packet["execution_boundary"]["docker_started"],
        "model_api_invoked": packet["execution_boundary"]["model_api_invoked"],
        "events": [packet["schema_version"], run_event["schema_version"]],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
