from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..machine_configuration.contract import (
    MACHINE_CONFIGURATION_SCHEMA,
    MachineConfigurationNamespace,
)
from .scheduling import (
    DEFAULT_REVIEW_PRIORITY,
    PullRequestReviewPriority,
    normalize_review_priority,
)

PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA = (
    "pull_request_review_machine_defaults_v0"
)


def normalize_pull_request_review_machine_defaults(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    unknown = sorted(set(raw) - {"schema_version", "review_priority", "wait_for_ci"})
    if unknown:
        raise ValueError(
            "pull_request_review contains unsupported fields: "
            + ", ".join(unknown)
        )
    if raw.get("schema_version") != PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA:
        raise ValueError(
            "pull_request_review must use "
            + PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA
        )
    wait_for_ci = raw.get("wait_for_ci", True)
    if type(wait_for_ci) is not bool:
        raise TypeError("pull_request_review.wait_for_ci must be a boolean")
    return {
        "wait_for_ci": wait_for_ci,
        "schema_version": PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA,
        "review_priority": normalize_review_priority(raw.get("review_priority")).value,
    }


def pull_request_review_machine_configuration_namespace() -> MachineConfigurationNamespace:
    return MachineConfigurationNamespace(
        namespace="pull_request_review",
        schema_versions=frozenset({PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA}),
        normalize=normalize_pull_request_review_machine_defaults,
        project_public=lambda value: dict(value),
        apply_public_update=lambda _current, update: dict(update),
        title="Pull-request review",
        description=(
            "Machine defaults for review priority and CI waiting, with complete "
            "Goal overrides. Other developers rank first and CI waiting is enabled "
            "by default. Disabling CI waiting preserves required local validation "
            "and grants no GitHub, Todo, push, or merge authority."
        ),
        default_configuration={
            "schema_version": PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA,
            "review_priority": DEFAULT_REVIEW_PRIORITY.value,
            "wait_for_ci": True,
        },
    )


def review_priority_machine_default(
    machine_configuration: Mapping[str, Any] | None,
) -> PullRequestReviewPriority | None:
    """Read this capability's typed value from the generic machine envelope."""

    if machine_configuration is None:
        return None
    if machine_configuration.get("schema_version") != MACHINE_CONFIGURATION_SCHEMA:
        raise ValueError(
            f"machine_configuration must use {MACHINE_CONFIGURATION_SCHEMA}"
        )
    namespaces = machine_configuration.get("namespaces")
    if not isinstance(namespaces, Mapping):
        raise TypeError("machine_configuration.namespaces must be an object")
    raw = namespaces.get("pull_request_review")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError(
            "machine_configuration.namespaces.pull_request_review must be an object"
        )
    normalized = normalize_pull_request_review_machine_defaults(raw)
    return normalize_review_priority(normalized["review_priority"])


__all__ = [
    "PULL_REQUEST_REVIEW_MACHINE_DEFAULTS_SCHEMA",
    "normalize_pull_request_review_machine_defaults",
    "pull_request_review_machine_configuration_namespace",
    "review_priority_machine_default",
]
