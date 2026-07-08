from __future__ import annotations

from typing import Any

from ...benchmark_core import compact_run_permission_policy_for_quota
from ...boundary_authority import checkpointed_boundary_authority_summary
from ...execution_profile import execution_profile_outcome_floor
from ...orchestration import compact_orchestration_policy
from ..todos.contract import (
    normalize_required_capabilities,
    normalize_required_write_scopes,
)


def quota_execution_profile_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact: dict[str, Any] = {}
    for field in ("cadence", "minimum_scale", "spend_rule"):
        if value.get(field):
            compact[field] = value[field]
    must_include = value.get("must_include")
    if isinstance(must_include, list) and must_include:
        compact["must_include"] = [str(item) for item in must_include[:3]]
    policy = (
        value.get("degradation_policy")
        if isinstance(value.get("degradation_policy"), dict)
        else {}
    )
    if policy.get("small_scale_streak_threshold") is not None:
        compact["small_scale_streak_threshold"] = policy.get("small_scale_streak_threshold")
    floor = execution_profile_outcome_floor(value)
    if floor:
        outcome_markers = (
            floor.get("outcome_markers")
            if isinstance(floor.get("outcome_markers"), list)
            else []
        )
        surface_hints = (
            floor.get("surface_only_hints")
            if isinstance(floor.get("surface_only_hints"), list)
            else []
        )
        compact["outcome_floor"] = {
            "configured": bool(outcome_markers or surface_hints),
            "surface_streak_threshold": floor.get("surface_streak_threshold"),
            "must_advance": [
                str(item)
                for item in (
                    floor.get("must_advance")
                    if isinstance(floor.get("must_advance"), list)
                    else []
                )[:2]
            ],
        }
    return compact or None


def quota_execution_profile_boundary_summary(value: Any) -> dict[str, Any] | None:
    summary = quota_execution_profile_summary(value)
    if not summary:
        return None
    compact = {}
    if summary.get("minimum_scale"):
        compact["minimum_scale"] = summary["minimum_scale"]
    return compact or None


def goal_boundary(goal: dict[str, Any], item: dict[str, Any] | None = None) -> dict[str, Any] | None:
    boundary: dict[str, Any] = {}
    adapter_kind = goal.get("adapter_kind")
    adapter_status = goal.get("adapter_status")
    if adapter_kind or adapter_status:
        boundary["adapter"] = {
            "kind": adapter_kind,
            "status": adapter_status,
        }
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    write_scope = coordination.get("write_scope") if isinstance(coordination.get("write_scope"), list) else []
    requires_approval = (
        coordination.get("requires_parent_approval")
        if isinstance(coordination.get("requires_parent_approval"), list)
        else []
    )
    normalized_write_scope: list[str] = []
    for value in write_scope:
        scope = str(value).strip()
        if scope and scope not in normalized_write_scope:
            normalized_write_scope.append(scope)
    boundary_authority = checkpointed_boundary_authority_summary(coordination)
    if boundary_authority:
        for scope in normalize_required_write_scopes(boundary_authority.get("active_write_scope")):
            if scope not in normalized_write_scope:
                normalized_write_scope.append(scope)
        boundary["checkpointed_boundary_authority"] = boundary_authority
    if normalized_write_scope:
        boundary["write_scope"] = normalized_write_scope
    available_capabilities = declared_available_capabilities(goal)
    if available_capabilities:
        boundary["available_capabilities"] = available_capabilities
    if requires_approval:
        boundary["requires_parent_approval"] = [
            str(value) for value in requires_approval if str(value).strip()
        ]
    guards = goal.get("guards") if isinstance(goal.get("guards"), list) else []
    if guards:
        boundary["guards"] = [str(value) for value in guards if str(value).strip()]
    if goal.get("next_probe"):
        boundary["next_probe"] = str(goal.get("next_probe"))
    spawn_policy = goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else None
    if spawn_policy is not None:
        boundary["orchestration"] = compact_orchestration_policy(spawn_policy)
    project_asset_source = item if item is not None else goal
    for policy_source in (goal, project_asset_source):
        if not isinstance(policy_source, dict):
            continue
        policy = compact_run_permission_policy_for_quota(
            policy_source.get("run_permission_policy")
            or policy_source.get("run_permission_policy_v0")
        )
        if policy:
            boundary["run_permission_policy"] = policy
            break
    if isinstance(project_asset_source, dict) and project_asset_source.get("project_asset"):
        project_asset = project_asset_source.get("project_asset")
        if isinstance(project_asset, dict):
            policy = compact_run_permission_policy_for_quota(
                project_asset.get("run_permission_policy")
                or project_asset.get("run_permission_policy_v0")
            )
            if policy:
                boundary["run_permission_policy"] = policy
            if project_asset.get("stop_condition"):
                boundary["stop_condition"] = project_asset.get("stop_condition")
            if isinstance(project_asset.get("execution_profile"), dict):
                boundary["execution_profile"] = quota_execution_profile_boundary_summary(
                    project_asset["execution_profile"]
                )
            if isinstance(project_asset.get("orchestration"), dict):
                boundary["orchestration"] = compact_orchestration_policy(project_asset["orchestration"])
    if boundary:
        boundary["rule"] = "stay_in_scope_or_stop"
        return boundary
    return None


def declared_available_capabilities(source: Any) -> list[str]:
    if not isinstance(source, dict):
        return []
    capabilities: list[str] = []

    def append(raw: Any) -> None:
        for capability in normalize_required_capabilities(raw):
            if capability not in capabilities:
                capabilities.append(capability)

    append(source.get("available_capabilities"))
    coordination = (
        source.get("coordination")
        if isinstance(source.get("coordination"), dict)
        else {}
    )
    append(coordination.get("available_capabilities"))
    project_asset = (
        source.get("project_asset")
        if isinstance(source.get("project_asset"), dict)
        else {}
    )
    append(project_asset.get("available_capabilities"))
    return capabilities


def effective_available_capabilities(
    runtime_available_capabilities: Any,
    *,
    item: dict[str, Any],
    project_asset: dict[str, Any],
) -> list[str]:
    capabilities: list[str] = []
    for raw in (
        declared_available_capabilities(item),
        declared_available_capabilities(project_asset),
        runtime_available_capabilities,
    ):
        for capability in normalize_required_capabilities(raw):
            if capability not in capabilities:
                capabilities.append(capability)
    return capabilities
