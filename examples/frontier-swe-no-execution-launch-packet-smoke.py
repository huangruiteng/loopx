#!/usr/bin/env python3
"""Smoke-test the public FrontierSWE no-execution launch packet."""

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


DOC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
PACKET_PATH = DOC_DIR / "frontier-swe-no-execution-launch-packet-v0.md"
SETUP_PATH = DOC_DIR / "frontier-swe-setup-readiness-v0.md"
README_PATH = DOC_DIR / "README.md"

FORBIDDEN_PATTERNS = [
    re.compile("/" + "Users/"),
    re.compile("/" + "private/"),
    re.compile(r"\." + "local/"),
    re.compile("trajectory_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("raw_logs_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("raw_task_text_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile("verifier_output_copied" + r"\"\\s*:\\s*" + "tr" + "ue"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
]


def assert_public_safe(text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def load_json_block(packet: str, heading: str) -> dict:
    match = re.search(
        rf"## {re.escape(heading)}\s+```json\s+(.*?)\s+```",
        packet,
        re.DOTALL,
    )
    assert match, f"missing {heading} block"
    return json.loads(match.group(1))


def test_packet_boundary_and_source() -> None:
    packet = PACKET_PATH.read_text(encoding="utf-8")
    setup = SETUP_PATH.read_text(encoding="utf-8")
    assert "# FrontierSWE No-Execution Launch Packet v0" in packet
    assert "This packet does not execute a benchmark task" in packet
    assert "Do not execute this command from an automatic heartbeat" in packet
    assert "Proximal-Labs/frontier-swe" in packet
    assert "Proximal-Labs/frontier-swe" in setup
    assert "frontier_swe_source_commit_unpinned_on_benchmark_host" in packet
    assert "source_and_inventory_no_execution_probe" in packet
    assert "Terminal-Bench or SkillsBench still lacks" in packet
    assert "goal_harness" not in packet
    assert_public_safe(packet)


def test_structured_readiness_packet() -> None:
    packet = PACKET_PATH.read_text(encoding="utf-8")
    readiness = load_json_block(packet, "Structured Readiness Packet")

    assert readiness["schema_version"] == "frontier_swe_no_execution_launch_packet_v0"
    assert readiness["benchmark_id"] == "frontier-swe"
    assert readiness["route"] == "cloud_ecs_harbor_family"
    assert readiness["ready_for_scored_launch"] is False
    assert (
        readiness["first_blocker"]
        == "frontier_swe_source_commit_unpinned_on_benchmark_host"
    )
    assert readiness["source"]["source_commit_pinned"] is False
    assert readiness["source"]["source_lock_required_before_run"] is True
    assert readiness["runner"]["prefer_wrapper_or_reducer_over_runner_patch"] is True
    assert readiness["task_inventory"]["inventory_required_before_run"] is True
    assert readiness["task_inventory"]["task_body_read"] is False
    assert readiness["boundary"]["task_started"] is False
    assert readiness["boundary"]["docker_started"] is False
    assert readiness["boundary"]["model_api_invoked"] is False
    assert readiness["boundary"]["upload_enabled"] is False
    assert readiness["boundary"]["leaderboard_enabled"] is False
    assert readiness["boundary"]["raw_logs_public"] is False
    assert readiness["boundary"]["raw_task_text_public"] is False
    assert readiness["boundary"]["verifier_output_public"] is False
    assert readiness["boundary"]["local_paths_public"] is False


def test_run_permission_policy_is_no_execution() -> None:
    packet = PACKET_PATH.read_text(encoding="utf-8")
    policy = load_json_block(packet, "Structured Run Permission Policy")
    validation = validate_run_permission_policy(policy)
    projection = compact_run_permission_policy_for_quota(policy)

    assert validation["ok"] is True, validation
    assert projection is not None, policy
    assert (
        projection["policy_id"]
        == "frontier_swe_no_execution_launch_packet_20260624"
    )
    assert policy["max_wall_time_minutes"] == 0, policy
    assert projection["delivery_allowed"] is True, projection
    assert projection["max_wall_time_minutes"] == 120, projection
    assert projection["no_upload_required"] is True, projection
    assert projection["submit_allowed"] is False, projection
    assert projection["leaderboard_claim_allowed"] is False, projection
    assert projection["compact_observation_only"] is True, projection
    assert "ready_for_scored_launch\": false" in packet
    assert (
        RunPermissionAction.LOCAL_HARBOR_RUNNER.value
        in projection["allowed_actions"]
    )
    assert (
        RunPermissionAction.CODEX_MODEL_INVOCATION.value
        in projection["forbidden_actions"]
    )


def test_readme_indexes_packet() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    assert "frontier-swe-no-execution-launch-packet-v0.md" in readme


if __name__ == "__main__":
    test_packet_boundary_and_source()
    test_structured_readiness_packet()
    test_run_permission_policy_is_no_execution()
    test_readme_indexes_packet()
    print("frontier-swe-no-execution-launch-packet-smoke ok")
