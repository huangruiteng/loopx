from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ...control_plane.goals.goal_vision_policy import (
    COMPLETED_TODO_CHAIN_REPLAN_THRESHOLD,
    normalize_completed_todo_replan_threshold,
)
from ..machine_configuration.contract import (
    MACHINE_CONFIGURATION_SCHEMA,
    MachineConfigurationNamespace,
)

TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA = (
    "todo_replan_cadence_machine_defaults_v0"
)


def normalize_todo_replan_cadence_machine_defaults(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    unknown = sorted(set(raw) - {"schema_version", "completed_todos"})
    if unknown:
        raise ValueError(
            "todo_replan_cadence contains unsupported fields: " + ", ".join(unknown)
        )
    if raw.get("schema_version") != TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA:
        raise ValueError(
            "todo_replan_cadence must use "
            + TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA
        )
    return {
        "schema_version": TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA,
        "completed_todos": normalize_completed_todo_replan_threshold(
            raw.get("completed_todos")
        ),
    }


def todo_replan_cadence_machine_configuration_namespace(
) -> MachineConfigurationNamespace:
    return MachineConfigurationNamespace(
        namespace="todo_replan_cadence",
        schema_versions=frozenset({TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA}),
        normalize=normalize_todo_replan_cadence_machine_defaults,
        project_public=lambda value: dict(value),
        apply_public_update=lambda _current, update: dict(update),
        title="Goal review cadence",
        description=(
            "Live review threshold for Goals without an explicit cadence override. "
            "It changes when LoopX reviews a completed Todo chain; it does not create "
            "turns, spend quota, or grant authority."
        ),
        default_configuration={
            "schema_version": TODO_REPLAN_CADENCE_MACHINE_DEFAULTS_SCHEMA,
            "completed_todos": COMPLETED_TODO_CHAIN_REPLAN_THRESHOLD,
        },
    )


def _machine_default(
    machine_configuration: Mapping[str, Any] | None,
) -> int | None:
    if machine_configuration is None:
        return None
    if machine_configuration.get("schema_version") != MACHINE_CONFIGURATION_SCHEMA:
        raise ValueError(
            f"machine_configuration must use {MACHINE_CONFIGURATION_SCHEMA}"
        )
    namespaces = machine_configuration.get("namespaces")
    if not isinstance(namespaces, Mapping):
        raise TypeError("machine_configuration.namespaces must be an object")
    raw = namespaces.get("todo_replan_cadence")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise TypeError(
            "machine_configuration.namespaces.todo_replan_cadence must be an object"
        )
    return int(
        normalize_todo_replan_cadence_machine_defaults(raw)["completed_todos"]
    )


def apply_todo_replan_cadence_machine_default(
    goal: Mapping[str, Any],
    machine_configuration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project the live machine default without overwriting a Goal override."""

    projected = deepcopy(dict(goal))
    raw_profile = goal.get("execution_profile")
    if isinstance(raw_profile, Mapping) and "replan_after_completed_todos" in raw_profile:
        return projected
    completed_todos = _machine_default(machine_configuration)
    if completed_todos is None:
        return projected
    profile = dict(raw_profile) if isinstance(raw_profile, Mapping) else {}
    profile["replan_after_completed_todos"] = completed_todos
    projected["execution_profile"] = profile
    return projected
