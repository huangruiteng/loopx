from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ...capabilities.periodic_report.profile import (
    ACTIVATION_SCHEMA,
    build_periodic_report_activation,
)
from ..runtime import (
    default_extension_state_file,
    resolve_extension_binding,
)


OPENVIKING_PERIODIC_REPORT_EXTENSION_ID = "openviking-periodic-report"
OPENVIKING_PERIODIC_REPORT_EXTENSION_VERSION = "1.0.0"
OPENVIKING_PERIODIC_REPORT_PERMISSION = "openviking_context_write"
PERIODIC_REPORT_SINK_PROTOCOL = "periodic_report_sink_v0"
REPORT_ARCHIVE_CAPABILITY_ID = "report.archive.write"
REPORT_ARCHIVE_CAPABILITY_VERSION = "v0"


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _available_capabilities(values: Sequence[str]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip()}


def validate_openviking_periodic_report_activation(
    activation_receipt: Mapping[str, Any],
    *,
    available_capabilities: Sequence[str],
    sink_id: str,
    sink_kind: str = "project_resource",
) -> dict[str, Any]:
    """Fail closed unless the core capability and OV archive sink are active."""

    activation = _mapping(activation_receipt, "activation_receipt")
    if activation.get("schema_version") != ACTIVATION_SCHEMA:
        raise ValueError(f"activation_receipt must use {ACTIVATION_SCHEMA}")
    profile = _mapping(activation.get("profile"), "activation_receipt.profile")
    expected = build_periodic_report_activation(profile)
    if activation != expected:
        raise ValueError("activation_receipt does not match its normalized profile")
    if not (
        activation.get("active") is True
        and activation.get("status") == "enabled"
        and activation.get("generation_allowed") is True
    ):
        raise ValueError("periodic-report capability profile must be enabled")
    available = _available_capabilities(available_capabilities)
    if OPENVIKING_PERIODIC_REPORT_PERMISSION not in available:
        raise ValueError(
            "openviking-periodic-report requires observed runtime capability "
            f"`{OPENVIKING_PERIODIC_REPORT_PERMISSION}`"
        )

    matching: list[dict[str, Any]] = []
    for raw_binding in profile.get("sink_bindings", []):
        binding = _mapping(raw_binding, "activation_receipt.profile.sink_bindings[]")
        capability = _mapping(binding.get("capability"), "sink_binding.capability")
        extension = _mapping(binding.get("extension"), "sink_binding.extension")
        if binding.get("sink_id") != sink_id:
            continue
        if not (
            binding.get("sink_kind") == sink_kind
            and binding.get("sink_role") == "archive"
            and binding.get("dependency_policy") in {"optional", "required"}
            and capability.get("capability_id") == REPORT_ARCHIVE_CAPABILITY_ID
            and capability.get("capability_version")
            == REPORT_ARCHIVE_CAPABILITY_VERSION
            and extension.get("extension_id")
            == OPENVIKING_PERIODIC_REPORT_EXTENSION_ID
            and extension.get("extension_version")
            == OPENVIKING_PERIODIC_REPORT_EXTENSION_VERSION
            and extension.get("protocol") == PERIODIC_REPORT_SINK_PROTOCOL
        ):
            raise ValueError(
                "periodic-report OpenViking archive sink binding is incompatible "
                "or disabled"
            )
        matching.append(binding)
    if len(matching) != 1:
        raise ValueError(
            "periodic-report profile must bind exactly one enabled OpenViking "
            f"archive sink `{sink_id}`"
        )
    return {
        "activation": activation,
        "binding": matching[0],
        "available_capabilities": sorted(available),
    }


def resolve_openviking_periodic_report_activation(
    activation_receipt: Mapping[str, Any],
    *,
    available_capabilities: Sequence[str],
    sink_id: str,
    state_file: str | Path | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    """Bind an enabled profile to one revision-bound LoopX extension runtime."""

    validated = validate_openviking_periodic_report_activation(
        activation_receipt,
        available_capabilities=available_capabilities,
        sink_id=sink_id,
    )
    resolved_state = (
        Path(state_file).expanduser()
        if state_file is not None
        else default_extension_state_file(runtime_root)
    )
    runtime_binding = resolve_extension_binding(
        OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        state_file=resolved_state,
        capability_id="periodic-report",
        protocol=PERIODIC_REPORT_SINK_PROTOCOL,
        permission=OPENVIKING_PERIODIC_REPORT_PERMISSION,
    )
    if runtime_binding.get("provider_version") != (
        OPENVIKING_PERIODIC_REPORT_EXTENSION_VERSION
    ):
        raise ValueError("periodic-report profile and installed extension versions differ")
    extension_receipt = {
        "extension_id": OPENVIKING_PERIODIC_REPORT_EXTENSION_ID,
        "extension_version": OPENVIKING_PERIODIC_REPORT_EXTENSION_VERSION,
        "protocol": PERIODIC_REPORT_SINK_PROTOCOL,
        "status": "ready",
        "readback_verified": True,
        "capabilities": [
            {
                "capability_id": REPORT_ARCHIVE_CAPABILITY_ID,
                "capability_version": REPORT_ARCHIVE_CAPABILITY_VERSION,
            }
        ],
        "activation_verified": True,
        "runtime_capability_verified": True,
        "extension_revision": runtime_binding["revision"],
    }
    return {
        "ok": True,
        "schema_version": "openviking_periodic_report_activation_v0",
        **validated,
        "runtime_binding": runtime_binding,
        "extension_receipt": extension_receipt,
        "external_writes_performed": False,
    }
