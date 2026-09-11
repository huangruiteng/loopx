"""Transport lifecycle inputs to the typed capability context owner."""

from collections.abc import Mapping
from typing import Any

from .effect_runtime import effect_runtime_result


def project_agent_context(
    *,
    phase: str,
    scope: Mapping[str, Any],
    orchestration: Mapping[str, Any],
    observations: Mapping[str, Any] | None = None,
):
    return effect_runtime_result(
        "capability_hook.agent_context.project",
        {
            "phase": phase,
            "scope": dict(scope),
            "orchestration": dict(orchestration),
            "observations": dict(observations or {}),
        },
    )


def envelope_agent_context(
    envelope: Mapping[str, Any],
    *,
    phase: str,
    observations: Mapping[str, Any] | None = None,
):
    """The signed planning contribution binds later phases to the coordinator."""
    context = envelope.get("agent_context")
    if not isinstance(context, Mapping):
        return None
    boundary = envelope.get("boundary") or {}
    return project_agent_context(
        phase=phase,
        scope=context["scope"],
        orchestration=boundary.get("orchestration") or {},
        observations=observations,
    )


def agent_context_descriptor():
    return effect_runtime_result("capability_hook.agent_context.describe", {})
