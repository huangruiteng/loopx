#!/usr/bin/env python3
"""Smoke-test benchmark candidate-selection source boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_benchmark_candidate_source_boundary  # noqa: E402


PRIVATE_ROOT = "/private/example/project/.local/private-benchmark-jobs/job-a"
ALLOWED_SOURCES = [
    "docs/research/long-horizon-agent-benchmarks/terminal-bench-next-candidate-selection-20260614.md",
    "examples/terminal-bench-candidate-routing-packets-smoke.py",
    ".local/goals/loopx-meta/ACTIVE_GOAL_STATE.md",
    f"{PRIVATE_ROOT}/paired_comparison.compact.json",
    f"{PRIVATE_ROOT}/launch_observation.public.json",
]
BLOCKED_SOURCES = [
    PRIVATE_ROOT,
    f"{PRIVATE_ROOT}/treatment/jobs/job-a/trial/agent/codex.txt",
    f"{PRIVATE_ROOT}/treatment/jobs/job-a/trial/agent/trajectory.json",
    f"{PRIVATE_ROOT}/treatment/jobs/job-a/trial/result.json",
    f"{PRIVATE_ROOT}/tasks/demo/instruction.md",
    "scratch/candidate-notes.txt",
]


def assert_no_path_leak(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/private/example",
        ".local/private-benchmark-jobs",
        "treatment/jobs",
        "tasks/demo",
        "scratch/candidate-notes.txt",
    ]
    leaked = [marker for marker in forbidden if marker in rendered]
    assert not leaked, leaked


def assert_boundary(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == "benchmark_candidate_source_boundary_v0", payload
    assert payload["path_recorded"] is False, payload
    assert payload["allowed_source_count"] == len(ALLOWED_SOURCES), payload
    assert payload["blocked_source_count"] == len(BLOCKED_SOURCES), payload
    assert payload["clean"] is False, payload
    assert payload["read_boundary"]["files_opened"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
    assert payload["read_boundary"]["task_text_read"] is False, payload
    assert payload["read_boundary"]["trajectory_read"] is False, payload
    assert payload["read_boundary"]["codex_transcript_read"] is False, payload
    assert payload["read_boundary"]["local_paths_recorded"] is False, payload
    assert "paired_comparison.compact.json" in payload["allowed_source_basenames"], payload
    assert "launch_observation.public.json" in payload["allowed_source_basenames"], payload
    assert "codex.txt" in payload["blocked_source_basenames"], payload
    assert "trajectory.json" in payload["blocked_source_basenames"], payload
    assert "result.json" in payload["blocked_source_basenames"], payload
    assert payload["blocked_reasons"]["private_runner_artifact_root_or_raw_child"] == 5, payload
    assert payload["blocked_reasons"]["unregistered_candidate_source"] == 1, payload
    assert_no_path_leak(payload)


def main() -> None:
    payload = build_benchmark_candidate_source_boundary(
        [*ALLOWED_SOURCES, *BLOCKED_SOURCES],
        adapter_kind="terminal-bench",
    )
    assert_boundary(payload)

    clean_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "candidate-source-boundary",
            "--adapter-kind",
            "terminal-bench",
            "--require-clean",
            *ALLOWED_SOURCES,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    clean_payload = json.loads(clean_result.stdout)
    assert clean_payload["clean"] is True, clean_payload
    assert clean_payload["blocked_source_count"] == 0, clean_payload
    assert_no_path_leak(clean_payload)

    blocked_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "candidate-source-boundary",
            "--adapter-kind",
            "terminal-bench",
            "--require-clean",
            *ALLOWED_SOURCES,
            *BLOCKED_SOURCES,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert blocked_result.returncode == 1, blocked_result
    cli_payload = json.loads(blocked_result.stdout)
    assert_boundary(cli_payload)
    print("benchmark-candidate-source-boundary-smoke ok")


if __name__ == "__main__":
    main()
