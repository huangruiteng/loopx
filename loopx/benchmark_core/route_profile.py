from __future__ import annotations

import ipaddress
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from .observable_handles import build_benchmark_launch_observable_handle
from .run_permissions import (
    RunPermissionAction,
    build_run_permission_policy,
    validate_run_permission_policy,
)


BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION = "benchmark_route_profile_v0"

BENCHMARK_ROUTE_PROFILE_EXECUTION_SURFACES = (
    "official_remote_runner",
    "managed_remote_runner",
    "local_dry_run",
)
BENCHMARK_ROUTE_PROFILE_REASONING_EFFORTS = (
    "default",
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
)
BENCHMARK_ROUTE_PROFILE_FAILURE_ATTRIBUTIONS = (
    "none",
    "pre_bridge_rate_limit",
    "pre_bridge_tui_error_prompt",
    "bridge_request_missing",
    "first_action_missing",
    "auth_or_tunnel_unavailable",
    "agent_setup_score_failure",
    "agent_setup_timeout_score_failure",
    "official_verifier_solution_failure",
    "official_score_missing",
    "runner_infrastructure_failure",
    "compact_artifact_missing",
)

_PRIVATE_VALUE_MARKERS = (
    "/",
    "\\",
    "~",
    "$HOME",
    "auth.json",
    "token",
    "secret",
    "credential",
    "cookie",
    "private_key",
)


def _safe_label(value: Any, *, fallback: str, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = text.replace("\\", "/").rsplit("/", 1)[-1]
    text = re.sub(r"[^A-Za-z0-9._:-]+", "-", text).strip("-._:")
    return (text or fallback)[:limit]


def _endpoint_host(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if "://" in text:
        parsed = urlsplit(text)
        return parsed.hostname or ""
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    host_port = re.match(r"^([^:/\\]+):\d{1,5}$", text)
    if host_port:
        return host_port.group(1)
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return text if text.lower() == "localhost" else ""
    return text


def _looks_endpoint_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if "://" in text:
        return True
    if re.match(r"^([^:/\\]+):\d{1,5}$", text):
        return True
    host = _endpoint_host(text)
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        parsed.is_loopback
        or parsed.is_private
        or parsed.is_link_local
        or parsed.is_unspecified
        or parsed.is_reserved
    )


def _safe_transport_reference_label(
    value: Any, *, fallback: str, limit: int = 120
) -> str:
    if _looks_private_or_path(value):
        return fallback
    return _safe_label(value, fallback=fallback, limit=limit)


def _unique_labels(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        label = _safe_label(value, fallback="", limit=120)
        if label and label not in result:
            result.append(label)
    return result


def _bounded_positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, maximum)


def _looks_private_or_path(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if _looks_endpoint_value(text):
        return True
    lower = text.lower()
    if re.match(r"^[A-Za-z]:[\\/]", text):
        return True
    return any(marker.lower() in lower for marker in _PRIVATE_VALUE_MARKERS)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    else:
        try:
            raw_values = list(value)
        except TypeError:
            raw_values = [value]
    return _unique_labels(raw_values)


def build_benchmark_route_profile(
    *,
    benchmark_id: str,
    route_id: str,
    model: str,
    reasoning_effort: str = "default",
    profile_id: str | None = None,
    execution_surface: str = "official_remote_runner",
    requires_bridge_request: bool = True,
    requires_first_action: bool = True,
    private_auth_reference_label: str = "private-auth-handle",
    reverse_tunnel_reference_label: str = "private-reverse-tunnel-handle",
    max_wall_time_minutes: int = 120,
    first_action_timeout_seconds: int = 300,
    bridge_request_timeout_seconds: int = 300,
    poll_interval_seconds: int = 30,
    compact_artifact_refs: Iterable[Any] = (),
    failure_attribution_vocabulary: Iterable[
        str
    ] = BENCHMARK_ROUTE_PROFILE_FAILURE_ATTRIBUTIONS,
) -> dict[str, Any]:
    """Build a public-safe route/model/execution contract for benchmark runs.

    The profile is descriptive only. It does not launch a runner, select cases,
    change scoring, or store private auth/tunnel values.
    """

    safe_benchmark_id = _safe_label(benchmark_id, fallback="benchmark", limit=80)
    safe_route_id = _safe_label(route_id, fallback="benchmark-route", limit=100)
    safe_profile_id = _safe_label(
        profile_id or f"{safe_benchmark_id}:{safe_route_id}",
        fallback="benchmark-route-profile",
        limit=140,
    )
    safe_surface = _safe_label(
        execution_surface,
        fallback="official_remote_runner",
        limit=80,
    )
    if safe_surface not in BENCHMARK_ROUTE_PROFILE_EXECUTION_SURFACES:
        safe_surface = "official_remote_runner"
    safe_reasoning = _safe_label(reasoning_effort, fallback="default", limit=40)
    if safe_reasoning not in BENCHMARK_ROUTE_PROFILE_REASONING_EFFORTS:
        safe_reasoning = "default"

    official_remote = safe_surface in {"official_remote_runner", "managed_remote_runner"}
    local_fallback_allowed = safe_surface == "local_dry_run"
    allowed_actions = [
        RunPermissionAction.CODEX_MODEL_INVOCATION.value,
        RunPermissionAction.BENCHMARK_DEPENDENCY_FETCH.value,
        RunPermissionAction.COMPACT_RESULT_REDUCTION.value,
    ]
    forbidden_actions = [
        RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
        RunPermissionAction.LOCAL_HARBOR_RUNNER.value,
        RunPermissionAction.PUBLIC_RESULT_UPLOAD.value,
        RunPermissionAction.LEADERBOARD_SUBMISSION.value,
        RunPermissionAction.PUBLIC_BENCHMARK_CLAIM.value,
        RunPermissionAction.PRODUCTION_CLOUD_ACTION.value,
        RunPermissionAction.CREDENTIAL_SYNC.value,
        RunPermissionAction.RAW_ARTIFACT_PUBLICATION.value,
    ]
    if not official_remote:
        allowed_actions.extend(
            [
                RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
                RunPermissionAction.LOCAL_HARBOR_RUNNER.value,
            ]
        )
        forbidden_actions = [
            action
            for action in forbidden_actions
            if action
            not in {
                RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
                RunPermissionAction.LOCAL_HARBOR_RUNNER.value,
            }
        ]

    permission_policy = build_run_permission_policy(
        policy_id=f"{safe_profile_id}:no-upload-no-local-fallback",
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        max_wall_time_minutes=max_wall_time_minutes,
        no_upload_required=True,
        compact_observation_only=True,
    )
    compact_refs = _unique_labels(compact_artifact_refs)

    return {
        "schema_version": BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION,
        "profile_id": safe_profile_id,
        "benchmark_id": safe_benchmark_id,
        "route": {
            "route_id": safe_route_id,
            "model": _safe_label(model, fallback="model", limit=80),
            "reasoning_effort": safe_reasoning,
            "requires_first_action": requires_first_action is True,
            "requires_bridge_request": requires_bridge_request is True,
        },
        "execution": {
            "surface": safe_surface,
            "official_remote": official_remote,
            "local_fallback_allowed": local_fallback_allowed,
            "no_local_fallback_required": official_remote,
            "will_execute": False,
        },
        "permission_policy": permission_policy,
        "transport_handles": {
            "private_auth_reference_label": _safe_transport_reference_label(
                private_auth_reference_label,
                fallback="private-auth-handle",
                limit=120,
            ),
            "reverse_tunnel_reference_label": _safe_transport_reference_label(
                reverse_tunnel_reference_label,
                fallback="private-reverse-tunnel-handle",
                limit=120,
            ),
            "private_values_recorded": False,
            "credential_values_recorded": False,
            "local_paths_recorded": False,
        },
        "pacing_timeout_policy": {
            "max_wall_time_minutes": _bounded_positive_int(
                max_wall_time_minutes,
                default=120,
                maximum=24 * 60,
            ),
            "first_action_timeout_seconds": _bounded_positive_int(
                first_action_timeout_seconds,
                default=300,
                maximum=12 * 60 * 60,
            ),
            "bridge_request_timeout_seconds": _bounded_positive_int(
                bridge_request_timeout_seconds,
                default=300,
                maximum=12 * 60 * 60,
            ),
            "poll_interval_seconds": _bounded_positive_int(
                poll_interval_seconds,
                default=30,
                maximum=60 * 60,
            ),
            "retry_requires_new_quota_decision": True,
        },
        "compact_artifact_policy": {
            "compact_only": True,
            "compact_artifact_refs": compact_refs,
            "raw_logs_public": False,
            "raw_terminal_tail_public": False,
            "raw_task_text_public": False,
            "raw_trajectory_public": False,
            "local_paths_public": False,
        },
        "observable_handle_registration": build_benchmark_launch_observable_handle(
            benchmark_id=safe_benchmark_id,
            launch_mode=safe_surface,
            run_label=safe_profile_id,
            process_state="not_started",
            compact_artifact_refs=compact_refs,
            allowed_poll_command="benchmark_route_profile_observe",
            scheduler_kind="manual",
            will_execute=False,
            read_boundary={"compact_only": True},
        ),
        "failure_attribution_vocabulary": _unique_labels(
            failure_attribution_vocabulary
        ),
        "score_claim_policy": {
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "score_attempt_countable_requires_official_runner_closeout": True,
            "control_plane_only_evidence_must_not_be_called_score_uplift": True,
        },
        "public_boundary": {
            "raw_logs_recorded": False,
            "raw_terminal_tail_recorded": False,
            "raw_task_text_recorded": False,
            "raw_trajectory_recorded": False,
            "local_paths_recorded": False,
            "private_auth_values_recorded": False,
        },
    }


def validate_benchmark_route_profile(value: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(value, Mapping):
        return {
            "ok": False,
            "schema_version": BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION,
            "first_blocker": "benchmark_route_profile_missing",
            "blockers": ["benchmark_route_profile_missing"],
        }
    if value.get("schema_version") != BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION:
        blockers.append("benchmark_route_profile_schema_mismatch")

    route = value.get("route") if isinstance(value.get("route"), Mapping) else {}
    if not str(route.get("route_id") or "").strip():
        blockers.append("benchmark_route_profile_route_missing")
    if not str(route.get("model") or "").strip():
        blockers.append("benchmark_route_profile_model_missing")
    if route.get("reasoning_effort") not in BENCHMARK_ROUTE_PROFILE_REASONING_EFFORTS:
        blockers.append("benchmark_route_profile_unknown_reasoning_effort")

    execution = (
        value.get("execution") if isinstance(value.get("execution"), Mapping) else {}
    )
    surface = execution.get("surface")
    if surface not in BENCHMARK_ROUTE_PROFILE_EXECUTION_SURFACES:
        blockers.append("benchmark_route_profile_unknown_execution_surface")
    official_remote = execution.get("official_remote") is True
    if official_remote:
        if execution.get("no_local_fallback_required") is not True:
            blockers.append("benchmark_route_profile_no_local_fallback_not_required")
        if execution.get("local_fallback_allowed") is not False:
            blockers.append("benchmark_route_profile_local_fallback_allowed")

    permission_policy = value.get("permission_policy")
    permission_validation = validate_run_permission_policy(permission_policy)
    if not permission_validation["ok"]:
        blockers.append(
            permission_validation.get("first_blocker")
            or "run_permission_policy_invalid"
        )
    if isinstance(permission_policy, Mapping) and official_remote:
        forbidden = set(_string_list(permission_policy.get("forbidden_actions")))
        for action in (
            RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
            RunPermissionAction.LOCAL_HARBOR_RUNNER.value,
        ):
            if action not in forbidden:
                blockers.append("benchmark_route_profile_local_runner_not_forbidden")
                break

    transport_handles = (
        value.get("transport_handles")
        if isinstance(value.get("transport_handles"), Mapping)
        else {}
    )
    if transport_handles.get("private_values_recorded") is not False:
        blockers.append("benchmark_route_profile_private_handle_values_recorded")
    if transport_handles.get("credential_values_recorded") is not False:
        blockers.append("benchmark_route_profile_credentials_recorded")
    if transport_handles.get("local_paths_recorded") is not False:
        blockers.append("benchmark_route_profile_local_paths_recorded")
    for field in ("private_auth_reference_label", "reverse_tunnel_reference_label"):
        if _looks_private_or_path(transport_handles.get(field)):
            blockers.append(f"benchmark_route_profile_{field}_not_public_safe")

    compact_policy = (
        value.get("compact_artifact_policy")
        if isinstance(value.get("compact_artifact_policy"), Mapping)
        else {}
    )
    if compact_policy.get("compact_only") is not True:
        blockers.append("benchmark_route_profile_compact_only_not_required")
    for field in (
        "raw_logs_public",
        "raw_terminal_tail_public",
        "raw_task_text_public",
        "raw_trajectory_public",
        "local_paths_public",
    ):
        if compact_policy.get(field) is not False:
            blockers.append(f"benchmark_route_profile_{field}_allowed")

    observable = (
        value.get("observable_handle_registration")
        if isinstance(value.get("observable_handle_registration"), Mapping)
        else {}
    )
    boundary = (
        observable.get("boundary")
        if isinstance(observable.get("boundary"), Mapping)
        else {}
    )
    for field in (
        "raw_logs_recorded",
        "raw_task_text_recorded",
        "raw_trajectory_recorded",
        "local_paths_recorded",
        "credential_values_recorded",
    ):
        if boundary.get(field) is not False:
            blockers.append(f"benchmark_route_profile_observable_{field}_allowed")

    public_boundary = (
        value.get("public_boundary")
        if isinstance(value.get("public_boundary"), Mapping)
        else {}
    )
    for field in (
        "raw_logs_recorded",
        "raw_terminal_tail_recorded",
        "raw_task_text_recorded",
        "raw_trajectory_recorded",
        "local_paths_recorded",
        "private_auth_values_recorded",
    ):
        if public_boundary.get(field) is not False:
            blockers.append(f"benchmark_route_profile_public_{field}_recorded")

    vocabulary = set(_string_list(value.get("failure_attribution_vocabulary")))
    unknown_vocabulary = sorted(
        vocabulary - set(BENCHMARK_ROUTE_PROFILE_FAILURE_ATTRIBUTIONS)
    )
    if unknown_vocabulary:
        blockers.append("benchmark_route_profile_unknown_failure_attribution")
    for required in (
        "pre_bridge_tui_error_prompt",
        "pre_bridge_rate_limit",
        "bridge_request_missing",
    ):
        if required not in vocabulary:
            blockers.append("benchmark_route_profile_required_attribution_missing")
            break

    score_claim_policy = (
        value.get("score_claim_policy")
        if isinstance(value.get("score_claim_policy"), Mapping)
        else {}
    )
    if score_claim_policy.get("official_score_claim_allowed") is not False:
        blockers.append("benchmark_route_profile_official_score_claim_allowed")
    if score_claim_policy.get("leaderboard_claim_allowed") is not False:
        blockers.append("benchmark_route_profile_leaderboard_claim_allowed")
    if (
        score_claim_policy.get(
            "score_attempt_countable_requires_official_runner_closeout"
        )
        is not True
    ):
        blockers.append("benchmark_route_profile_countable_closeout_not_required")

    return {
        "ok": not blockers,
        "schema_version": BENCHMARK_ROUTE_PROFILE_SCHEMA_VERSION,
        "first_blocker": blockers[0] if blockers else "",
        "blockers": blockers,
        "permission_policy_validation": permission_validation,
        "unknown_failure_attributions": unknown_vocabulary,
    }
