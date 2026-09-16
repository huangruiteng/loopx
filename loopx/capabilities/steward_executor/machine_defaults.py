"""Own the machine-level executor default for the steward channel.

The steward channel is the surface a person talks to. It resolves which executor
answers, which model runs there, and at which reasoning effort from three typed
sources, in one order:

1. this machine-configuration namespace -- the operator's persistent choice for
   this machine, editable from the Dashboard and read back by
   ``loopx machine-config describe`` / ``inspect``;
2. the Chat service environment (``LOOPX_MANAGER_ENDPOINT`` and its model and
   effort siblings), which stays as the bootstrap and escape-hatch layer;
3. the shipped product default, which is the interactive CLI endpoint.

The namespace stores a decision, never a discovery: it holds no credential, and
nothing here reads one. A configured operator credential authenticates the
selected executor; it never selects one.

Only the endpoints LoopX ships as channel executors are accepted here, so a
machine default cannot name an adapter the channel has no product contract for.
An operator who needs an unlisted adapter still has the environment variable.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..machine_configuration.contract import (
    MACHINE_CONFIGURATION_SCHEMA,
    MachineConfigurationNamespace,
    machine_configuration_revision,
)

STEWARD_EXECUTOR_NAMESPACE = "steward_executor"
STEWARD_EXECUTOR_SCHEMA = "steward_executor_machine_defaults_v0"
STEWARD_EXECUTOR_EFFECTIVE_SCHEMA = "steward_executor_effective_defaults_v0"
EXECUTOR_ENDPOINT_FIELD = "executor_endpoint"
MODEL_FIELD = "executor_model"
REASONING_EFFORT_FIELD = "executor_reasoning_effort"
_TEXT_LIMIT = 100


def steward_executor_endpoints() -> frozenset[str]:
    """Return the executor ids this namespace accepts for the steward channel.

    The chat layer owns the endpoint vocabulary, so this reads it from the same
    owner that resolves the channel instead of restating a second list here.
    The import stays local because the chat layer resolves *through* this
    namespace, and a module-level import would close that loop.
    """

    from ...chat_manager import MANAGER_ENDPOINT_KINDS

    return frozenset(MANAGER_ENDPOINT_KINDS)


def steward_reasoning_efforts() -> tuple[str, ...]:
    """Return the reasoning-effort vocabulary a selected executor accepts."""

    from ...chat_manager import MANAGER_REASONING_EFFORTS

    return tuple(MANAGER_REASONING_EFFORTS)


def _optional_text(value: Any, *, field: str) -> str | None:
    """Normalize one absent-or-selected text field.

    A blank value and an absent value mean the same thing -- this namespace
    does not decide that field, and the channel keeps resolving it from the
    lower layers -- so both normalize to ``None`` instead of storing an empty
    string that reads like a selection.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > _TEXT_LIMIT:
        raise ValueError(f"steward_executor.{field} is too long")
    return text


def normalize_steward_executor_machine_defaults(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize one typed steward-executor machine default, fail closed."""

    unknown = sorted(
        set(raw)
        - {
            "schema_version",
            EXECUTOR_ENDPOINT_FIELD,
            MODEL_FIELD,
            REASONING_EFFORT_FIELD,
        }
    )
    if unknown:
        raise ValueError(
            "steward_executor contains unsupported fields: " + ", ".join(unknown)
        )
    if raw.get("schema_version") != STEWARD_EXECUTOR_SCHEMA:
        raise ValueError(f"steward_executor must use {STEWARD_EXECUTOR_SCHEMA}")
    endpoint = str(raw.get(EXECUTOR_ENDPOINT_FIELD) or "").strip()
    supported = steward_executor_endpoints()
    if endpoint not in supported:
        raise ValueError(
            "steward_executor.executor_endpoint must be one of "
            + ", ".join(sorted(supported))
        )
    reasoning_effort = _optional_text(
        raw.get(REASONING_EFFORT_FIELD), field=REASONING_EFFORT_FIELD
    )
    supported_efforts = steward_reasoning_efforts()
    if reasoning_effort is not None and reasoning_effort not in supported_efforts:
        raise ValueError(
            "steward_executor.reasoning_effort must be one of "
            + ", ".join(supported_efforts)
        )
    return {
        "schema_version": STEWARD_EXECUTOR_SCHEMA,
        EXECUTOR_ENDPOINT_FIELD: endpoint,
        MODEL_FIELD: _optional_text(raw.get(MODEL_FIELD), field=MODEL_FIELD),
        REASONING_EFFORT_FIELD: reasoning_effort,
    }


def steward_executor_machine_configuration_namespace() -> (
    MachineConfigurationNamespace
):
    return MachineConfigurationNamespace(
        namespace=STEWARD_EXECUTOR_NAMESPACE,
        schema_versions=frozenset({STEWARD_EXECUTOR_SCHEMA}),
        normalize=normalize_steward_executor_machine_defaults,
        project_public=lambda value: dict(value),
        apply_public_update=lambda _current, update: dict(update),
        title="Steward executor",
        description=(
            "Selects the executor, model, and reasoning effort the steward channel "
            "runs on this machine, ahead of the Chat service environment and the "
            "shipped default. It selects a provider-billed runtime; it grants no "
            "authority and stores no credential. A blank model or reasoning effort "
            "keeps the lower layer's value."
        ),
        documentation={
            "path": "docs/architecture/rfcs/harness-selection-dsh-pi-v0.md",
            "url": (
                "https://github.com/huangruiteng/loopx/blob/main/"
                "docs/architecture/rfcs/harness-selection-dsh-pi-v0.md"
            ),
        },
        default_configuration={
            "schema_version": STEWARD_EXECUTOR_SCHEMA,
            EXECUTOR_ENDPOINT_FIELD: "codex",
            MODEL_FIELD: None,
            REASONING_EFFORT_FIELD: None,
        },
    )


def _projection(
    *,
    status: str,
    source: str,
    revision: str,
    executor_endpoint: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    repair: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": STEWARD_EXECUTOR_EFFECTIVE_SCHEMA,
        "status": status,
        "source": source,
        "configuration_revision": revision,
        EXECUTOR_ENDPOINT_FIELD: executor_endpoint,
        MODEL_FIELD: model,
        REASONING_EFFORT_FIELD: reasoning_effort,
        **({"repair": repair} if repair else {}),
    }


def effective_steward_executor_defaults(
    machine_configuration: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Resolve the steward executor defaults from one machine document.

    ``None``, a document that carries no steward namespace, and a malformed
    document all resolve to "this machine decided nothing" rather than to a
    guessed endpoint, so the channel falls through to its lower layers with the
    reason visible in ``status``.
    """

    if machine_configuration is None:
        return _projection(
            status="absent", source="capability_default", revision="absent"
        )
    if machine_configuration.get("schema_version") != MACHINE_CONFIGURATION_SCHEMA:
        raise ValueError(
            f"machine_configuration must use {MACHINE_CONFIGURATION_SCHEMA}"
        )
    unknown = sorted(set(machine_configuration) - {"schema_version", "namespaces"})
    if unknown:
        raise ValueError(
            "machine_configuration contains unsupported fields: " + ", ".join(unknown)
        )
    namespaces = machine_configuration.get("namespaces")
    if not isinstance(namespaces, Mapping):
        raise TypeError("machine_configuration.namespaces must be an object")
    raw = namespaces.get(STEWARD_EXECUTOR_NAMESPACE)
    if raw is None:
        return _projection(
            status="absent", source="capability_default", revision="absent"
        )
    if not isinstance(raw, Mapping):
        raise TypeError(
            "machine_configuration.namespaces.steward_executor must be an object"
        )
    normalized = normalize_steward_executor_machine_defaults(raw)
    return _projection(
        status="ready",
        source="machine_configuration",
        revision=machine_configuration_revision(normalized),
        executor_endpoint=str(normalized[EXECUTOR_ENDPOINT_FIELD]),
        model=normalized[MODEL_FIELD],
        reasoning_effort=normalized[REASONING_EFFORT_FIELD],
    )


def load_effective_steward_executor_defaults(runtime_root: Path) -> dict[str, Any]:
    """Read this machine's steward executor default from the live store.

    Each namespace owns its runtime effect, so a malformed sibling cannot
    silently rewrite a valid steward selection: the document is read
    unnormalized and only this namespace is normalized here. A malformed
    steward value, or an unreadable store, resolves to the shipped default with
    a typed reason instead of failing the channel a person is talking to.
    """

    from ..machine_configuration.store import read_stored_machine_configuration

    try:
        configuration = read_stored_machine_configuration(runtime_root)
    except (OSError, TypeError, ValueError):
        return _projection(
            status="unavailable",
            source="unreadable_store",
            revision="unavailable",
            repair="Repair the machine-configuration store, then reopen the channel.",
        )
    try:
        return effective_steward_executor_defaults(configuration)
    except (TypeError, ValueError):
        return _projection(
            status="configuration_invalid",
            source="invalid_configuration_fallback",
            revision="unavailable",
            repair="Open machine capability settings and repair Steward executor.",
        )
