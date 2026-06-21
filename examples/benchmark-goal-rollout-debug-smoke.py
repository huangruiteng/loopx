#!/usr/bin/env python3
"""Smoke-test the public-safe benchmark rollout debug artifact."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROLLUP_JSON = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/benchmark-goal-rollout-debug-20260620.json"
)
ROLLUP_MD = (
    REPO_ROOT
    / "docs/research/long-horizon-agent-benchmarks/benchmark-goal-rollout-debug-20260620.md"
)


FORBIDDEN_MARKERS = [
    "/Users/",
    "/private/",
    "/home/",
    "/root/",
    ".local/private-benchmark-jobs",
    "BEGIN OPENSSH PRIVATE KEY",
    "OPENAI_API_KEY",
    # Keep active leak markers split in source so `loopx check` can
    # scan this public smoke while the runtime assertion still tests the full
    # forbidden marker in rendered artifacts.
    "Author" + "ization:",
    '"raw_task_text_copied": true',
    '"raw_logs_copied": true',
    '"raw_verifier_output_copied": true',
    '"raw_trajectory_copied": true',
    '"credential_material_copied": true',
    '"private_or_absolute_paths_copied": true',
]


def main() -> None:
    payload = json.loads(ROLLUP_JSON.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "benchmark_goal_rollout_debug_v0", payload
    boundary = payload["public_boundary"]
    assert boundary["raw_task_text_copied"] is False, boundary
    assert boundary["raw_logs_copied"] is False, boundary
    assert boundary["raw_verifier_output_copied"] is False, boundary
    assert boundary["raw_trajectory_copied"] is False, boundary
    assert boundary["credential_material_copied"] is False, boundary
    assert boundary["private_or_absolute_paths_copied"] is False, boundary

    cases = {
        (case["benchmark_id"], case["case_id"]): case
        for case in payload["case_rollouts"]
    }
    assert ("terminal-bench@2.0", "build-cython-ext") in cases, cases
    assert ("terminal-bench@2.0", "multi-source-data-merger") in cases, cases
    assert ("terminal-bench@2.0", "nginx-request-logging") in cases, cases
    assert ("skillsbench@1.1", "react-performance-debugging") in cases, cases
    assert ("skillsbench@1.1", "llm-prefix-cache-replay") in cases, cases
    assert ("skillsbench@1.1", "tictoc-unnecessary-abort-detection") in cases, cases
    assert ("swe-marathon", "find-network-alignments") in cases, cases

    assert cases[("terminal-bench@2.0", "build-cython-ext")][
        "native_codex_goal_evidence"
    ] is True
    assert cases[("swe-marathon", "find-network-alignments")][
        "native_codex_goal_evidence"
    ] is True
    assert cases[("terminal-bench@2.0", "nginx-request-logging")][
        "official_passed"
    ] is True
    assert cases[("terminal-bench@2.0", "multi-source-data-merger")][
        "failure_class"
    ] == "official_verifier_solution_failure"
    assert cases[("skillsbench@1.1", "react-performance-debugging")][
        "native_codex_goal_evidence"
    ] is True
    assert cases[("skillsbench@1.1", "react-performance-debugging")][
        "failure_scope"
    ] == "runner_or_route"
    assert cases[("skillsbench@1.1", "llm-prefix-cache-replay")][
        "native_codex_goal_evidence"
    ] is False

    rendered = json.dumps(payload, sort_keys=True) + "\n" + ROLLUP_MD.read_text(
        encoding="utf-8"
    )
    leaks = [marker for marker in FORBIDDEN_MARKERS if marker in rendered]
    assert not leaks, leaks
    print("ok")


if __name__ == "__main__":
    main()
