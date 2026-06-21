from __future__ import annotations

from enum import Enum
from typing import Any, Iterable


RUN_PERMISSION_POLICY_SCHEMA_VERSION = "run_permission_policy_v0"
RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION = "run_permission_quota_projection_v0"


class RunPermissionAction(str, Enum):
    CODEX_MODEL_INVOCATION = "codex_model_invocation"
    LOCAL_DOCKER_RUNNER = "local_docker_runner"
    LOCAL_HARBOR_RUNNER = "local_harbor_runner"
    BENCHMARK_DEPENDENCY_FETCH = "benchmark_dependency_fetch"
    COMPACT_RESULT_REDUCTION = "compact_result_reduction"
    PUBLIC_RESULT_UPLOAD = "public_result_upload"
    LEADERBOARD_SUBMISSION = "leaderboard_submission"
    PUBLIC_BENCHMARK_CLAIM = "public_benchmark_claim"
    PRODUCTION_CLOUD_ACTION = "production_cloud_action"
    CREDENTIAL_SYNC = "credential_sync"
    RAW_ARTIFACT_PUBLICATION = "raw_artifact_publication"


DEFAULT_RUN_PERMISSION_ALLOWED_ACTIONS = (
    RunPermissionAction.CODEX_MODEL_INVOCATION.value,
    RunPermissionAction.LOCAL_DOCKER_RUNNER.value,
    RunPermissionAction.LOCAL_HARBOR_RUNNER.value,
    RunPermissionAction.BENCHMARK_DEPENDENCY_FETCH.value,
    RunPermissionAction.COMPACT_RESULT_REDUCTION.value,
)
DEFAULT_RUN_PERMISSION_FORBIDDEN_ACTIONS = (
    RunPermissionAction.PUBLIC_RESULT_UPLOAD.value,
    RunPermissionAction.LEADERBOARD_SUBMISSION.value,
    RunPermissionAction.PUBLIC_BENCHMARK_CLAIM.value,
    RunPermissionAction.PRODUCTION_CLOUD_ACTION.value,
    RunPermissionAction.CREDENTIAL_SYNC.value,
    RunPermissionAction.RAW_ARTIFACT_PUBLICATION.value,
)
RUN_PERMISSION_ACTION_VALUES = tuple(action.value for action in RunPermissionAction)


def _string_list(values: Iterable[Any] | Any) -> list[str]:
    if isinstance(values, str):
        raw_values: Iterable[Any] = [values]
    elif isinstance(values, Iterable):
        raw_values = values
    else:
        raw_values = []
    result: list[str] = []
    for value in raw_values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _bounded_positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return min(parsed, maximum)


def build_run_permission_policy(
    *,
    policy_id: str = "benchmark_no_upload_local_policy",
    allowed_actions: Iterable[str] = DEFAULT_RUN_PERMISSION_ALLOWED_ACTIONS,
    forbidden_actions: Iterable[str] = DEFAULT_RUN_PERMISSION_FORBIDDEN_ACTIONS,
    max_wall_time_minutes: int = 120,
    no_upload_required: bool = True,
    compact_observation_only: bool = True,
) -> dict[str, Any]:
    allowed = _string_list(allowed_actions)
    forbidden = _string_list(forbidden_actions)
    return {
        "schema_version": RUN_PERMISSION_POLICY_SCHEMA_VERSION,
        "policy_id": str(policy_id).strip() or "benchmark_no_upload_local_policy",
        "allowed_actions": allowed,
        "forbidden_actions": forbidden,
        "max_wall_time_minutes": _bounded_positive_int(
            max_wall_time_minutes,
            default=120,
            maximum=24 * 60,
        ),
        "no_upload_required": no_upload_required is True,
        "submit_allowed": False,
        "leaderboard_claim_allowed": False,
        "public_benchmark_claim_allowed": False,
        "production_cloud_allowed": False,
        "observation_boundary": {
            "compact_only": compact_observation_only is True,
            "raw_logs_public": False,
            "raw_task_text_public": False,
            "raw_trajectory_public": False,
            "local_paths_public": False,
        },
        "operator_gate_required_for": [
            action
            for action in forbidden
            if action
            in {
                RunPermissionAction.PUBLIC_RESULT_UPLOAD.value,
                RunPermissionAction.LEADERBOARD_SUBMISSION.value,
                RunPermissionAction.PUBLIC_BENCHMARK_CLAIM.value,
                RunPermissionAction.PRODUCTION_CLOUD_ACTION.value,
                RunPermissionAction.CREDENTIAL_SYNC.value,
                RunPermissionAction.RAW_ARTIFACT_PUBLICATION.value,
            }
        ],
    }

def validate_run_permission_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "ok": False,
            "schema_version": RUN_PERMISSION_POLICY_SCHEMA_VERSION,
            "first_blocker": "run_permission_policy_missing",
        }
    if value.get("schema_version") != RUN_PERMISSION_POLICY_SCHEMA_VERSION:
        return {
            "ok": False,
            "schema_version": RUN_PERMISSION_POLICY_SCHEMA_VERSION,
            "first_blocker": "run_permission_policy_schema_mismatch",
        }
    allowed = set(_string_list(value.get("allowed_actions")))
    forbidden = set(_string_list(value.get("forbidden_actions")))
    unknown = sorted((allowed | forbidden) - set(RUN_PERMISSION_ACTION_VALUES))
    overlap = sorted(allowed & forbidden)
    observation = (
        value.get("observation_boundary")
        if isinstance(value.get("observation_boundary"), dict)
        else {}
    )
    blockers: list[str] = []
    if unknown:
        blockers.append("run_permission_policy_unknown_action")
    if overlap:
        blockers.append("run_permission_policy_allowed_forbidden_overlap")
    if value.get("no_upload_required") is not True:
        blockers.append("run_permission_policy_no_upload_not_required")
    if value.get("submit_allowed") is not False:
        blockers.append("run_permission_policy_submit_allowed")
    if value.get("leaderboard_claim_allowed") is not False:
        blockers.append("run_permission_policy_leaderboard_claim_allowed")
    if value.get("public_benchmark_claim_allowed") is not False:
        blockers.append("run_permission_policy_public_claim_allowed")
    if value.get("production_cloud_allowed") is not False:
        blockers.append("run_permission_policy_production_cloud_allowed")
    if observation.get("compact_only") is not True:
        blockers.append("run_permission_policy_compact_only_not_required")
    for field in (
        "raw_logs_public",
        "raw_task_text_public",
        "raw_trajectory_public",
        "local_paths_public",
    ):
        if observation.get(field) is not False:
            blockers.append(f"run_permission_policy_{field}_allowed")
    return {
        "ok": not blockers,
        "schema_version": RUN_PERMISSION_POLICY_SCHEMA_VERSION,
        "first_blocker": blockers[0] if blockers else "",
        "blockers": blockers,
        "unknown_actions": unknown,
        "overlap_actions": overlap,
    }


def compact_run_permission_policy_for_quota(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    validation = validate_run_permission_policy(value)
    observation = (
        value.get("observation_boundary")
        if isinstance(value.get("observation_boundary"), dict)
        else {}
    )
    return {
        "schema_version": RUN_PERMISSION_QUOTA_PROJECTION_SCHEMA_VERSION,
        "source_schema_version": value.get("schema_version"),
        "policy_id": str(value.get("policy_id") or ""),
        "valid": validation["ok"],
        "first_blocker": validation.get("first_blocker") or "",
        "delivery_allowed": validation["ok"],
        "no_upload_required": value.get("no_upload_required") is True,
        "submit_allowed": value.get("submit_allowed") is True,
        "leaderboard_claim_allowed": value.get("leaderboard_claim_allowed") is True,
        "public_benchmark_claim_allowed": value.get("public_benchmark_claim_allowed")
        is True,
        "production_cloud_allowed": value.get("production_cloud_allowed") is True,
        "compact_observation_only": observation.get("compact_only") is True,
        "max_wall_time_minutes": _bounded_positive_int(
            value.get("max_wall_time_minutes"),
            default=120,
            maximum=24 * 60,
        ),
        "allowed_actions": _string_list(value.get("allowed_actions"))[:8],
        "forbidden_actions": _string_list(value.get("forbidden_actions"))[:8],
        "operator_gate_required_for": _string_list(
            value.get("operator_gate_required_for")
        )[:8],
    }
