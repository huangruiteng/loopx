from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .policy import (
    CHANGE_QUALITY_POLICY_SCHEMA_VERSION,
    change_quality_goal_policy_summary,
)

GoalChangeQualityChange = tuple[bool, bool | None, bool | None, bool | None]


def configuration_summary(goal: Mapping[str, Any]) -> dict[str, Any] | None:
    control_plane = goal.get("control_plane")
    if not isinstance(control_plane, Mapping) or not isinstance(
        control_plane.get("change_quality_qualification"), Mapping
    ):
        return None
    return dict(change_quality_goal_policy_summary(dict(goal)))


def normalize_change(
    enabled: bool | None,
    safe_fix: bool | None,
    strict_receipt: bool | None,
    *,
    clear: bool,
) -> GoalChangeQualityChange:
    if clear and any(
        value is not None for value in (enabled, safe_fix, strict_receipt)
    ):
        raise ValueError(
            "--clear-change-quality-configuration cannot be combined with "
            "change-quality settings"
        )
    return clear, enabled, safe_fix, strict_receipt


def apply_change(goal: dict[str, Any], change: GoalChangeQualityChange) -> None:
    clear, enabled, safe_fix, strict_receipt = change
    if not clear and all(value is None for value in (enabled, safe_fix, strict_receipt)):
        return
    raw_control_plane = goal.get("control_plane")
    control_plane: dict[str, Any] = (
        dict(raw_control_plane) if isinstance(raw_control_plane, dict) else {}
    )
    if clear:
        control_plane.pop("change_quality_qualification", None)
        if control_plane:
            goal["control_plane"] = control_plane
        else:
            goal.pop("control_plane", None)
        return
    current = change_quality_goal_policy_summary(goal)
    control_plane["change_quality_qualification"] = {
        "schema_version": CHANGE_QUALITY_POLICY_SCHEMA_VERSION,
        "enabled": enabled if enabled is not None else current["enabled"],
        "safe_fix": safe_fix if safe_fix is not None else current["safe_fix"],
        "strict_receipt": (
            strict_receipt
            if strict_receipt is not None
            else current["strict_receipt"]
        ),
    }
    goal["control_plane"] = control_plane


__all__ = [
    "GoalChangeQualityChange",
    "apply_change",
    "configuration_summary",
    "normalize_change",
]
