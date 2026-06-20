#!/usr/bin/env python3
"""Smoke-test structured benchmark run permission policy projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark_core import (  # noqa: E402
    RUN_PERMISSION_POLICY_SCHEMA_VERSION,
    RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION,
    RunPermissionAction,
    build_run_permission_policy,
    compact_run_permission_policy_for_quota,
    validate_run_permission_policy,
)
from goal_harness.quota import _goal_boundary  # noqa: E402


def assert_default_policy_is_quota_readable() -> None:
    policy = build_run_permission_policy(max_wall_time_minutes=90)
    validation = validate_run_permission_policy(policy)
    projection = compact_run_permission_policy_for_quota(policy)

    assert policy["schema_version"] == RUN_PERMISSION_POLICY_SCHEMA_VERSION, policy
    assert validation["ok"] is True, validation
    assert projection is not None, policy
    assert projection["schema_version"] == RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION
    assert projection["delivery_allowed"] is True, projection
    assert projection["no_upload_required"] is True, projection
    assert projection["submit_allowed"] is False, projection
    assert projection["leaderboard_claim_allowed"] is False, projection
    assert projection["public_benchmark_claim_allowed"] is False, projection
    assert projection["production_cloud_allowed"] is False, projection
    assert projection["compact_observation_only"] is True, projection
    assert projection["max_wall_time_minutes"] == 90, projection
    assert RunPermissionAction.CODEX_MODEL_INVOCATION.value in projection["allowed_actions"]
    assert RunPermissionAction.PUBLIC_RESULT_UPLOAD.value in projection["forbidden_actions"]


def assert_policy_rejects_narrative_widening() -> None:
    policy = build_run_permission_policy()
    widened = dict(policy)
    widened["allowed_actions"] = [
        *policy["allowed_actions"],
        RunPermissionAction.PUBLIC_RESULT_UPLOAD.value,
    ]
    widened["submit_allowed"] = True
    widened["observation_boundary"] = {
        **policy["observation_boundary"],
        "compact_only": False,
    }

    validation = validate_run_permission_policy(widened)
    projection = compact_run_permission_policy_for_quota(widened)

    assert validation["ok"] is False, validation
    assert "run_permission_policy_allowed_forbidden_overlap" in validation["blockers"]
    assert "run_permission_policy_submit_allowed" in validation["blockers"]
    assert "run_permission_policy_compact_only_not_required" in validation["blockers"]
    assert projection is not None
    assert projection["delivery_allowed"] is False, projection
    assert projection["first_blocker"], projection


def assert_quota_goal_boundary_consumes_structured_policy() -> None:
    policy = build_run_permission_policy(policy_id="terminal_bench_cloud_no_upload")
    boundary = _goal_boundary(
        {
            "goal_id": "fixture",
            "adapter_kind": "benchmark_runner_v0",
            "adapter_status": "connected",
            "run_permission_policy": policy,
        }
    )

    assert boundary is not None
    projected = boundary["run_permission_policy"]
    assert projected["policy_id"] == "terminal_bench_cloud_no_upload", boundary
    assert projected["delivery_allowed"] is True, boundary
    assert projected["no_upload_required"] is True, boundary
    assert projected["leaderboard_claim_allowed"] is False, boundary
    rendered = json.dumps(boundary, sort_keys=True)
    assert "OWNER APPROVED" not in rendered
    assert "ask user" not in rendered.lower()


def main() -> int:
    assert_default_policy_is_quota_readable()
    assert_policy_rejects_narrative_widening()
    assert_quota_goal_boundary_consumes_structured_policy()
    print("benchmark-run-permission-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
