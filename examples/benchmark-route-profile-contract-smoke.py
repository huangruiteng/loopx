#!/usr/bin/env python3
"""Smoke-test the public benchmark route profile contract."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION,
    RunPermissionAction,
    build_benchmark_route_profile,
    validate_benchmark_route_profile,
)


PRIVATE_AUTH_REF = "private-auth-dir/auth.json"
PRIVATE_TAIL_REF = "private-run-artifacts/case-a/tmux-tail.txt"


def assert_no_private_path_leak(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        "private-auth-dir",
        "private-run-artifacts",
        "case-a/tmux-tail",
        "127.0.0.1",
        "18180",
    ]
    leaked = [marker for marker in forbidden if marker in rendered]
    assert not leaked, leaked


def assert_transport_endpoint_blocked(payload: dict[str, object]) -> None:
    raw_tunnel = copy.deepcopy(payload)
    raw_tunnel["transport_handles"][
        "reverse_tunnel_reference_label"
    ] = "127.0.0.1:18180"
    validation = validate_benchmark_route_profile(raw_tunnel)
    assert validation["ok"] is False, validation
    assert (
        "benchmark_route_profile_reverse_tunnel_reference_label_not_public_safe"
        in validation["blockers"]
    ), validation

    raw_auth_endpoint = copy.deepcopy(payload)
    raw_auth_endpoint["transport_handles"][
        "private_auth_reference_label"
    ] = "http://localhost:18180/auth.json"
    validation = validate_benchmark_route_profile(raw_auth_endpoint)
    assert validation["ok"] is False, validation
    assert (
        "benchmark_route_profile_private_auth_reference_label_not_public_safe"
        in validation["blockers"]
    ), validation


def assert_official_remote_xhigh_profile(payload: dict[str, object]) -> None:
    assert payload["schema_version"] == BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION, payload
    assert payload["benchmark_id"] == "skillsbench-1.1", payload
    assert payload["route"]["route_id"] == "codex-cli-goal", payload
    assert payload["route"]["model"] == "codex-cli", payload
    assert payload["route"]["reasoning_effort"] == "xhigh", payload
    assert payload["route"]["requires_first_action"] is True, payload
    assert payload["route"]["requires_bridge_request"] is True, payload

    execution = payload["execution"]
    assert execution["surface"] == "official_remote_runner", payload
    assert execution["official_remote"] is True, payload
    assert execution["local_fallback_allowed"] is False, payload
    assert execution["no_local_fallback_required"] is True, payload
    assert execution["will_execute"] is False, payload

    permission = payload["permission_policy"]
    assert permission["no_upload_required"] is True, payload
    assert permission["submit_allowed"] is False, payload
    assert permission["leaderboard_claim_allowed"] is False, payload
    assert (
        RunPermissionAction.LOCAL_DOCKER_RUNNER.value
        in permission["forbidden_actions"]
    )
    assert (
        RunPermissionAction.LOCAL_HARBOR_RUNNER.value
        in permission["forbidden_actions"]
    )
    assert (
        RunPermissionAction.PUBLIC_RESULT_UPLOAD.value
        in permission["forbidden_actions"]
    )
    assert (
        RunPermissionAction.LEADERBOARD_SUBMISSION.value
        in permission["forbidden_actions"]
    )

    handles = payload["transport_handles"]
    assert handles["private_auth_reference_label"] == "cloud-auth-handle", payload
    assert handles["reverse_tunnel_reference_label"] == "reverse-tunnel-handle", payload
    assert handles["private_values_recorded"] is False, payload
    assert handles["credential_values_recorded"] is False, payload
    assert handles["local_paths_recorded"] is False, payload

    compact = payload["compact_artifact_policy"]
    assert compact["compact_only"] is True, payload
    assert "launch_status.public.json" in compact["compact_artifact_refs"], payload
    assert compact["raw_terminal_tail_public"] is False, payload
    assert compact["raw_logs_public"] is False, payload
    assert compact["raw_task_text_public"] is False, payload
    assert compact["raw_trajectory_public"] is False, payload
    assert compact["local_paths_public"] is False, payload

    observable = payload["observable_handle_registration"]
    assert observable["schema_version"] == "benchmark_launch_observable_handle_v0", (
        observable
    )
    assert observable["will_execute"] is False, observable
    assert observable["monitor_poll_allowed"] is False, observable
    assert observable["allowed_poll_command"]["argv_recorded"] is False, observable
    assert observable["boundary"]["raw_logs_recorded"] is False, observable
    assert observable["boundary"]["credential_values_recorded"] is False, observable

    score_policy = payload["score_claim_policy"]
    assert score_policy["official_score_claim_allowed"] is False, payload
    assert score_policy["leaderboard_claim_allowed"] is False, payload
    assert (
        score_policy["score_attempt_countable_requires_official_runner_closeout"]
        is True
    ), payload
    assert (
        score_policy["control_plane_only_evidence_must_not_be_called_score_uplift"]
        is True
    ), payload

    vocabulary = set(payload["failure_attribution_vocabulary"])
    assert "pre_bridge_tui_error_prompt" in vocabulary, payload
    assert "pre_bridge_rate_limit" in vocabulary, payload
    assert "bridge_request_missing" in vocabulary, payload
    assert validate_benchmark_route_profile(payload)["ok"] is True, payload
    assert_no_private_path_leak(payload)


def main() -> None:
    payload = build_benchmark_route_profile(
        benchmark_id="skillsbench-1.1",
        route_id="codex-cli-goal",
        model="codex-cli",
        reasoning_effort="xhigh",
        private_auth_reference_label="cloud-auth-handle",
        reverse_tunnel_reference_label="reverse-tunnel-handle",
        compact_artifact_refs=[
            "launch_status.public.json",
            "case-final.compact.json",
            PRIVATE_TAIL_REF,
        ],
    )
    assert_official_remote_xhigh_profile(payload)

    raw_tunnel_payload = build_benchmark_route_profile(
        benchmark_id="skillsbench-1.1",
        route_id="codex-cli-goal",
        model="codex-cli",
        reasoning_effort="xhigh",
        private_auth_reference_label="cloud-auth-handle",
        reverse_tunnel_reference_label="http://127.0.0.1:18180",
        compact_artifact_refs=["launch_status.public.json"],
    )
    assert raw_tunnel_payload["transport_handles"][
        "reverse_tunnel_reference_label"
    ] == "private-reverse-tunnel-handle", raw_tunnel_payload
    assert validate_benchmark_route_profile(raw_tunnel_payload)["ok"] is True, (
        raw_tunnel_payload
    )
    assert_no_private_path_leak(raw_tunnel_payload)
    assert_transport_endpoint_blocked(payload)

    local_fallback = copy.deepcopy(payload)
    local_fallback["execution"]["local_fallback_allowed"] = True
    validation = validate_benchmark_route_profile(local_fallback)
    assert validation["ok"] is False, validation
    assert "benchmark_route_profile_local_fallback_allowed" in validation["blockers"], (
        validation
    )

    raw_auth = copy.deepcopy(payload)
    raw_auth["transport_handles"]["private_auth_reference_label"] = PRIVATE_AUTH_REF
    validation = validate_benchmark_route_profile(raw_auth)
    assert validation["ok"] is False, validation
    assert (
        "benchmark_route_profile_private_auth_reference_label_not_public_safe"
        in validation["blockers"]
    ), validation

    raw_tail = copy.deepcopy(payload)
    raw_tail["compact_artifact_policy"]["raw_terminal_tail_public"] = True
    validation = validate_benchmark_route_profile(raw_tail)
    assert validation["ok"] is False, validation
    assert "benchmark_route_profile_raw_terminal_tail_public_allowed" in validation[
        "blockers"
    ], validation

    unknown_attribution = copy.deepcopy(payload)
    unknown_attribution["failure_attribution_vocabulary"].append("private_tmux_tail")
    validation = validate_benchmark_route_profile(unknown_attribution)
    assert validation["ok"] is False, validation
    assert "benchmark_route_profile_unknown_failure_attribution" in validation[
        "blockers"
    ], validation

    print("benchmark-route-profile-contract-smoke ok")


if __name__ == "__main__":
    main()
