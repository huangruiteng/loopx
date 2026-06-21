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

from loopx.benchmark import filter_public_benchmark_artifact_paths  # noqa: E402


PRIVATE_ROOT = "/private/example/project/.local/private-benchmark-jobs/job-a"
PATHS = [
    f"{PRIVATE_ROOT}/paired_comparison.compact.json",
    f"{PRIVATE_ROOT}/launch_status.public.json",
    f"{PRIVATE_ROOT}/treatment/active-user-feed/loopx-active-user-observation.json",
    f"{PRIVATE_ROOT}/agent/trajectory.json",
    f"{PRIVATE_ROOT}/launch_private_manifest.local.json",
    f"{PRIVATE_ROOT}/tasks/demo/instruction.md",
]
ALE_POLICY_PATHS = [
    f"{PRIVATE_ROOT}/agents-last-exam-local-preflight.json",
    f"{PRIVATE_ROOT}/agents-last-exam-local-dry-run-plan.json",
    f"{PRIVATE_ROOT}/agents-last-exam-local-launch-packet.json",
    f"{PRIVATE_ROOT}/agents-last-exam-local-runner-readiness.json",
    f"{PRIVATE_ROOT}/agents-last-exam-local-source-readiness.json",
    f"{PRIVATE_ROOT}/agents-last-exam-task-material-readiness.json",
    f"{PRIVATE_ROOT}/agents-last-exam-candidate-task-data-scan.json",
    f"{PRIVATE_ROOT}/agents-last-exam-local-exact-dry-run-result.json",
    f"{PRIVATE_ROOT}/agents-last-exam-host-codex-cli-route.json",
    f"{PRIVATE_ROOT}/agents-last-exam-host-codex-cua-no-task-smoke.json",
    f"{PRIVATE_ROOT}/agents-last-exam-validation-run-gate.json",
    f"{PRIVATE_ROOT}/trajectory.json",
    f"{PRIVATE_ROOT}/screenshots/final.png",
]
CUSTOM_POLICY_PATHS = [
    f"{PRIVATE_ROOT}/custom-observation-proof.json",
    f"{PRIVATE_ROOT}/custom-observation-proof.private.json",
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
    assert payload["artifact_policy"]["adapter_kind"] == "default", payload
    assert payload["path_recorded"] is False, payload
    assert payload["allowed_to_read_count"] == 3, payload
    assert payload["blocked_count"] == 3, payload
    assert payload["allowed_artifact_basenames"] == [
        "paired_comparison.compact.json",
        "launch_status.public.json",
        "loopx-active-user-observation.json",
    ], payload
    assert payload["blocked_reasons"]["raw_private_surface"] == 2, payload
    assert payload["blocked_reasons"]["private_or_local_manifest"] == 1, payload
    assert_no_path_leak(payload)

    terminal_payload = filter_public_benchmark_artifact_paths(
        PATHS,
        adapter_kind="terminal-bench",
    )
    assert terminal_payload["allowed_artifact_basenames"] == payload["allowed_artifact_basenames"], terminal_payload
    assert terminal_payload["artifact_policy"]["adapter_kind"] == "terminal-bench", terminal_payload
    assert_no_path_leak(terminal_payload)

    default_ale_payload = filter_public_benchmark_artifact_paths(ALE_POLICY_PATHS)
    assert default_ale_payload["allowed_to_read_count"] == 0, default_ale_payload
    assert default_ale_payload["blocked_reasons"]["not_compact_public_artifact"] == 11, default_ale_payload
    assert default_ale_payload["blocked_reasons"]["raw_private_surface"] == 2, default_ale_payload
    assert_no_path_leak(default_ale_payload)

    ale_payload = filter_public_benchmark_artifact_paths(
        ALE_POLICY_PATHS,
        adapter_kind="agents-last-exam",
    )
    assert ale_payload["artifact_policy"]["adapter_kind"] == "agents-last-exam", ale_payload
    assert ale_payload["allowed_artifact_basenames"] == [
        "agents-last-exam-local-preflight.json",
        "agents-last-exam-local-dry-run-plan.json",
        "agents-last-exam-local-launch-packet.json",
        "agents-last-exam-local-runner-readiness.json",
        "agents-last-exam-local-source-readiness.json",
        "agents-last-exam-task-material-readiness.json",
        "agents-last-exam-candidate-task-data-scan.json",
        "agents-last-exam-local-exact-dry-run-result.json",
        "agents-last-exam-host-codex-cli-route.json",
        "agents-last-exam-host-codex-cua-no-task-smoke.json",
        "agents-last-exam-validation-run-gate.json",
    ], ale_payload
    assert ale_payload["blocked_reasons"]["raw_private_surface"] == 2, ale_payload
    assert_no_path_leak(ale_payload)

    custom_payload = filter_public_benchmark_artifact_paths(
        CUSTOM_POLICY_PATHS,
        extra_public_filenames=["custom-observation-proof.json"],
    )
    assert custom_payload["allowed_artifact_basenames"] == [
        "custom-observation-proof.json"
    ], custom_payload
    assert custom_payload["blocked_reasons"]["private_or_local_manifest"] == 1, custom_payload
    assert_no_path_leak(custom_payload)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "classify-artifacts",
            "--adapter-kind",
            "agents-last-exam",
            "--allow-public-filename",
            "custom-observation-proof.json",
            *PATHS,
            *ALE_POLICY_PATHS,
            *CUSTOM_POLICY_PATHS,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    cli_payload = json.loads(result.stdout)
    assert cli_payload["artifact_policy"]["adapter_kind"] == "agents-last-exam", cli_payload
    assert cli_payload["allowed_to_read_count"] == 15, cli_payload
    assert cli_payload["blocked_count"] == 6, cli_payload
    assert "agents-last-exam-local-launch-packet.json" in cli_payload["allowed_artifact_basenames"], cli_payload
    assert "agents-last-exam-candidate-task-data-scan.json" in cli_payload["allowed_artifact_basenames"], cli_payload
    assert "agents-last-exam-validation-run-gate.json" in cli_payload["allowed_artifact_basenames"], cli_payload
    assert "custom-observation-proof.json" in cli_payload["allowed_artifact_basenames"], cli_payload
    assert_no_path_leak(cli_payload)
    print("ok")


if __name__ == "__main__":
    main()
