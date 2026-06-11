#!/usr/bin/env python3
"""Smoke-test public-safe benchmark artifact path classification."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import filter_public_benchmark_artifact_paths  # noqa: E402


PRIVATE_ROOT = "/private/example/project/.local/private-benchmark-jobs/job-a"
PATHS = [
    f"{PRIVATE_ROOT}/paired_comparison.compact.json",
    f"{PRIVATE_ROOT}/launch_status.public.json",
    f"{PRIVATE_ROOT}/treatment/active-user-feed/goal-harness-active-user-observation.json",
    f"{PRIVATE_ROOT}/agent/trajectory.json",
    f"{PRIVATE_ROOT}/launch_private_manifest.local.json",
    f"{PRIVATE_ROOT}/tasks/demo/instruction.md",
]


def assert_no_path_leak(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/private/example",
        ".local/private-benchmark-jobs",
        "job-a/agent",
        "tasks/demo",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked


def main() -> None:
    payload = filter_public_benchmark_artifact_paths(PATHS)
    assert payload["schema_version"] == "benchmark_artifact_path_filter_v0", payload
    assert payload["path_recorded"] is False, payload
    assert payload["allowed_to_read_count"] == 3, payload
    assert payload["blocked_count"] == 3, payload
    assert payload["allowed_artifact_basenames"] == [
        "paired_comparison.compact.json",
        "launch_status.public.json",
        "goal-harness-active-user-observation.json",
    ], payload
    assert payload["blocked_reasons"]["raw_private_surface"] == 2, payload
    assert payload["blocked_reasons"]["private_or_local_manifest"] == 1, payload
    assert_no_path_leak(payload)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
            "--format",
            "json",
            "benchmark",
            "classify-artifacts",
            *PATHS,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    cli_payload = json.loads(result.stdout)
    assert cli_payload["allowed_to_read_count"] == 3, cli_payload
    assert cli_payload["blocked_count"] == 3, cli_payload
    assert_no_path_leak(cli_payload)
    print("ok")


if __name__ == "__main__":
    main()
