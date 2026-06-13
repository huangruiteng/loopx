#!/usr/bin/env python3
"""Smoke-test PerfBench alternate-source selection as a no-run blocker."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "perfbench_alternate_source_selection_v0"
RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_ID = "perfbench"
PAPER_ID = "arxiv:2509.24091"
ADVERTISED_REPO = "glGarg/PerfBench"
ADVERTISED_REPO_URL = "https://github.com/glGarg/PerfBench"
BROWSER_METADATA_SUMMARY_SHA256 = "658416db34c02ff9012911fe6d4b0039d3660c56eaa0a7fb3662e359564dbb9c"
TRANSPORT_PROBES = {
    "git_ls_remote_head": {
        "target": "https://github.com/glGarg/PerfBench.git",
        "ok": False,
        "failure_class": "repository_not_found",
    },
    "github_repo_api": {
        "target": "https://api.github.com/repos/glGarg/PerfBench",
        "ok": False,
        "failure_class": "http_404",
    },
    "github_contents_api": {
        "target": "https://api.github.com/repos/glGarg/PerfBench/contents/",
        "ok": False,
        "failure_class": "http_404",
    },
    "raw_readme": {
        "target": "https://raw.githubusercontent.com/glGarg/PerfBench/main/README.md",
        "ok": False,
        "failure_class": "http_404",
    },
    "raw_examples_head": {
        "target": "https://raw.githubusercontent.com/glGarg/PerfBench/main/examples.jsonl",
        "ok": False,
        "failure_class": "http_404",
    },
}
REPO_SEARCH_PROBES = {
    "PerfBench performance bug benchmark": 0,
    "glGarg PerfBench": 0,
    "PerfBench Performance Issue Benchmark Software Engineering Agents": 0,
}
FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "command_argv",
    "credential",
    "environment",
    "file_content",
    "local_path",
    "password",
    "problem_statement",
    "raw_artifact",
    "raw_benchmark_row",
    "raw_issue_body",
    "raw_output",
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
    "docker build",
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


def build_source_selection_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "paper_id": PAPER_ID,
        "advertised_source": {
            "repo": ADVERTISED_REPO,
            "url": ADVERTISED_REPO_URL,
            "browser_metadata_visible": True,
            "browser_metadata_summary_sha256": BROWSER_METADATA_SUMMARY_SHA256,
            "browser_metadata_sufficient_for_runner": False,
        },
        "transport_probes": TRANSPORT_PROBES,
        "github_repository_search": {
            "queries": REPO_SEARCH_PROBES,
            "alternate_official_repo_found": False,
        },
        "selection": {
            "alternate_source_selected": False,
            "selected_source_kind": "none",
            "selected_source_url": None,
            "reason": "no_transport_reachable_official_or_equivalent_source",
            "runner_source_ready": False,
            "task_rows_ready": False,
            "execution_ready": False,
        },
        "read_boundary": {
            "browser_metadata_read": True,
            "readme_raw_read": False,
            "examples_jsonl_read": False,
            "task_rows_read": False,
            "solution_or_gold_material_read": False,
            "test_material_read": False,
            "local_paths_recorded": False,
        },
        "execution_boundary": {
            "repository_cloned": False,
            "dotnet_build_run": False,
            "benchmarkdotnet_run": False,
            "docker_image_built": False,
            "docker_container_started": False,
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
        "next_gate": {
            "kind": "perfbench_source_transport_restored_or_new_candidate",
            "ready": False,
            "needs_reachable_official_source": True,
            "needs_runner_source_pin": True,
            "needs_no_task_source_preflight": True,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "perfbench",
        "benchmark_id": packet["benchmark_id"],
        "benchmark_revision": None,
        "source_commit": None,
        "mode": "alternate_source_selection_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "none_transport_blocked",
        "task_selector_hash": None,
        "progress": {
            "n_total_trials": 0,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "validation": {
            "advertised_browser_metadata_visible": True,
            "git_transport_available": False,
            "api_transport_available": False,
            "raw_transport_available": False,
            "alternate_official_repo_found": False,
            "alternate_source_selected": False,
            "runner_source_ready": False,
            "no_task_rows_read": True,
            "no_docker_run": True,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
        },
        "trials": [],
        "failure_attribution_labels": [
            "transport_blocked",
            "no_alternate_official_source_selected",
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
    packet = build_source_selection_packet()
    run_event = reduce_to_benchmark_run(packet)
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["advertised_source"]["browser_metadata_visible"] is True, packet
    assert packet["advertised_source"]["browser_metadata_sufficient_for_runner"] is False, packet
    assert all(not item["ok"] for item in packet["transport_probes"].values()), packet
    assert packet["github_repository_search"]["alternate_official_repo_found"] is False, packet
    assert packet["selection"]["alternate_source_selected"] is False, packet
    assert packet["selection"]["runner_source_ready"] is False, packet
    assert packet["read_boundary"]["examples_jsonl_read"] is False, packet
    assert packet["read_boundary"]["task_rows_read"] is False, packet
    assert packet["execution_boundary"]["repository_cloned"] is False, packet
    assert packet["execution_boundary"]["docker_container_started"] is False, packet
    assert packet["execution_boundary"]["codex_cli_invoked"] is False, packet
    assert run_event["validation"]["alternate_source_selected"] is False, run_event
    assert run_event["validation"]["runner_source_ready"] is False, run_event
    assert run_event["validation"]["no_task_rows_read"] is True, run_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "advertised_repo": ADVERTISED_REPO,
        "browser_metadata_visible": True,
        "transport_available": False,
        "alternate_source_selected": False,
        "runner_source_ready": False,
        "events": [packet["schema_version"], run_event["schema_version"]],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
