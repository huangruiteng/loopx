from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ..machine_configuration.contract import (
    MACHINE_CONFIGURATION_SCHEMA,
    MachineConfigurationNamespace,
)
from .policy import CHANGE_QUALITY_POLICY_SCHEMA_VERSION

CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA = "change_quality_machine_defaults_v0"


def normalize_change_quality_machine_defaults(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    unknown = sorted(
        set(raw) - {"schema_version", "enabled", "safe_fix", "strict_receipt"}
    )
    if unknown:
        raise ValueError(
            "change_quality_qualification contains unsupported fields: "
            + ", ".join(unknown)
        )
    if raw.get("schema_version") != CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA:
        raise ValueError(
            "change_quality_qualification must use "
            + CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA
        )
    normalized: dict[str, Any] = {
        "schema_version": CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA,
    }
    for field in ("enabled", "safe_fix", "strict_receipt"):
        value = raw.get(field)
        if not isinstance(value, bool):
            raise TypeError(f"change_quality_qualification.{field} must be a boolean")
        normalized[field] = value
    return normalized


def change_quality_machine_configuration_namespace() -> MachineConfigurationNamespace:
    return MachineConfigurationNamespace(
        namespace="change_quality_qualification",
        schema_versions=frozenset({CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA}),
        normalize=normalize_change_quality_machine_defaults,
        project_public=lambda value: dict(value),
        apply_public_update=lambda _current, update: dict(update),
        title="Change quality qualification",
        description=(
            "Live exact-diff qualification policy for Goals without an explicit "
            "override. It does not grant file, permission, or merge authority."
        ),
        default_configuration={
            "schema_version": CHANGE_QUALITY_MACHINE_DEFAULTS_SCHEMA,
            "enabled": False,
            "safe_fix": False,
            "strict_receipt": False,
        },
    )


def _machine_default(
    machine_configuration: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if machine_configuration is None:
        return None
    if machine_configuration.get("schema_version") != MACHINE_CONFIGURATION_SCHEMA:
        raise ValueError(
            f"machine_configuration must use {MACHINE_CONFIGURATION_SCHEMA}"
        )
    namespaces = machine_configuration.get("namespaces")
    if not isinstance(namespaces, Mapping):
        raise TypeError("machine_configuration.namespaces must be an object")
    raw = namespaces.get("change_quality_qualification")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError(
            "machine_configuration.namespaces.change_quality_qualification must be an object"
        )
    normalized = normalize_change_quality_machine_defaults(raw)
    return {
        "schema_version": CHANGE_QUALITY_POLICY_SCHEMA_VERSION,
        "enabled": normalized["enabled"],
        "safe_fix": normalized["safe_fix"],
        "strict_receipt": normalized["strict_receipt"],
    }


def apply_change_quality_machine_default(
    goal: Mapping[str, Any],
    machine_configuration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project the live machine policy without overwriting a Goal override."""

    projected = deepcopy(dict(goal))
    raw_control_plane = goal.get("control_plane")
    if isinstance(raw_control_plane, Mapping) and isinstance(
        raw_control_plane.get("change_quality_qualification"), Mapping
    ):
        return projected
    machine_default = _machine_default(machine_configuration)
    if machine_default is None:
        return projected
    control_plane = (
        dict(raw_control_plane) if isinstance(raw_control_plane, Mapping) else {}
    )
    control_plane["change_quality_qualification"] = machine_default
    projected["control_plane"] = control_plane
    return projected
