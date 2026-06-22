#!/usr/bin/env python3
"""Smoke-test the public ALE local Docker + host Codex route note."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    RunPermissionAction,
    compact_run_permission_policy_for_quota,
    validate_run_permission_policy,
)

DOC = (
    REPO_ROOT
    / "docs"
    / "research"
    / "long-horizon-agent-benchmarks"
    / "agents-last-exam-local-docker-host-codex-route-v0.md"
)
README = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks" / "README.md"


def normalized(text: str) -> str:
    return " ".join(text.split())


def load_run_permission_policy(text: str) -> dict:
    match = re.search(
        r"## Structured Run Permission Policy\s+.*?```json\s+(.*?)\s+```",
        text,
        re.DOTALL,
    )
    assert match, "missing structured run permission policy block"
    payload = json.loads(match.group(1))
    assert isinstance(payload, dict), payload
    return payload


def assert_structured_run_permission_policy(doc: str) -> None:
    policy = load_run_permission_policy(doc)
    validation = validate_run_permission_policy(policy)
    projection = compact_run_permission_policy_for_quota(policy)

    assert validation["ok"] is True, validation
    assert projection is not None, policy
    assert (
        projection["policy_id"]
        == "agents_last_exam_local_docker_host_codex_no_upload_20260622"
    )
    assert projection["delivery_allowed"] is True, projection
    assert projection["max_wall_time_minutes"] == 480, projection
    assert projection["no_upload_required"] is True, projection
    assert projection["submit_allowed"] is False, projection
    assert projection["leaderboard_claim_allowed"] is False, projection
    assert projection["compact_observation_only"] is True, projection
    assert (
        RunPermissionAction.LOCAL_DOCKER_RUNNER.value
        in projection["allowed_actions"]
    )
    assert (
        RunPermissionAction.PUBLIC_RESULT_UPLOAD.value
        in projection["forbidden_actions"]
    )


def main() -> None:
    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    compact = normalized(doc)
    compact_readme = normalized(readme)
    for phrase in (
        "non-GCP ALE route",
        "local Docker/Colima",
        "host Codex CLI",
        "Docker provider",
        "CUA/MCP bridge",
        "Google Cloud is the supported provider",
        "output_path: local",
        "run_permission_policy_v0",
        "agents_last_exam_local_docker_host_codex_no_upload_20260622",
        "does not authorize official GCP execution",
        "agentslastexam/ale-kasm:latest",
        "demo/tool_smoke",
        "score `1.0`",
        "computing_math/os_log_permission_guard_v1",
        "requires_task_data=True",
        "task_data_source=baked_in_sandbox",
        "gs://ale-data-public",
        "--requires-task-data false",
        "--enforce-task-data-source",
        "No upload, no submit, no leaderboard claim",
        "raw trajectories, screenshots, raw logs, credential values, or local host paths",
        "Colima",
        "gcloud",
        "GCP_PROJECT",
        "GCP_SA_KEY",
    ):
        assert phrase in compact, phrase

    assert "agents-last-exam-local-docker-host-codex-route-v0.md" in compact_readme
    assert "local Docker/Colima plus host Codex CLI" in compact_readme
    assert "score `1.0` canary as route evidence rather than uplift" in compact_readme
    assert_structured_run_permission_policy(doc)


if __name__ == "__main__":
    main()
    print("agents-last-exam-local-docker-host-codex-route-smoke ok")
