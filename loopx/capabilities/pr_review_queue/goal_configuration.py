"""Goal overrides for the existing pull-request-review configuration owner."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .machine_defaults import (
    normalize_pull_request_review_machine_defaults,
    PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA,
)
from .scheduling import normalize_review_priority

GOAL_CONFIGURATION_SCHEMA = "pull_request_review_goal_configuration_v0"


def configuration_summary(goal: Mapping[str, Any]) -> dict[str, Any] | None:
    control = goal.get("control_plane", {})
    raw = control.get("pull_request_review") if isinstance(control, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError("pull_request_review Goal configuration must be an object")
    if raw.get("schema_version") != GOAL_CONFIGURATION_SCHEMA:
        raise ValueError(
            "pull_request_review Goal configuration has an unsupported schema"
        )
    return {
        "wait_for_ci": True,
        "review_priority": "other-developers-first",
        **normalize_configuration(
            {k: v for k, v in raw.items() if k != "schema_version"}
        ),
    }


def normalize_configuration(raw: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(raw) - {"wait_for_ci", "review_priority"}
    if unknown:
        raise ValueError(
            "unsupported pull_request_review fields: " + ", ".join(sorted(unknown))
        )
    result = dict(raw)
    if "wait_for_ci" in result and type(result["wait_for_ci"]) is not bool:
        raise TypeError("pull_request_review.wait_for_ci must be a boolean")
    if "review_priority" in result:
        result["review_priority"] = normalize_review_priority(
            result["review_priority"]
        ).value
    return result


def resolve_configuration(
    goal: Mapping[str, Any] | None = None,
    machine_configuration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw = (machine_configuration or {}).get("namespaces", {}).get("pull_request_review")
    config = normalize_pull_request_review_machine_defaults(
        raw or {"schema_version": PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA}
    )
    config.pop("schema_version")
    override = configuration_summary(goal or {})
    return override if override is not None else config


def apply_change(
    goal: dict[str, Any], configuration: Mapping[str, Any] | None, *, clear: bool
) -> None:
    if clear and configuration is not None:
        raise ValueError(
            "clear PR review configuration cannot be combined with settings"
        )
    if not clear and configuration is None:
        return
    control = dict(goal.get("control_plane") or {})
    if clear:
        control.pop("pull_request_review", None)
    else:
        current = configuration_summary(goal) or {
            "wait_for_ci": True,
            "review_priority": "other-developers-first",
        }
        current.update(normalize_configuration(configuration))
        control["pull_request_review"] = {
            "schema_version": GOAL_CONFIGURATION_SCHEMA,
            **current,
        }
    if control:
        goal["control_plane"] = control
    else:
        goal.pop("control_plane", None)
