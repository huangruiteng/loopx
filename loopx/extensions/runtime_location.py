"""Host-local launch locations; package manifests remain portable and unchanged."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .readiness import extension_doctor, extension_runtime, resolve_runtime_entrypoint


def located_runtime(manifest: Mapping[str, Any], location: Any = None) -> Mapping[str, Any]:
    runtime = extension_runtime(manifest)
    if location is None:
        return runtime
    if (
        not isinstance(location, str) or not Path(location).is_absolute()
        or "python_module" in runtime
    ):
        raise ValueError("extension local executable location is invalid")
    return {**runtime, "entrypoint": location}


def probe_runtime_location(
    manifest: Mapping[str, Any], *, location: Any = None, execute: bool = False,
) -> tuple[dict[str, Any], str | None]:
    runtime = located_runtime(manifest, location)
    resolved = resolve_runtime_entrypoint(runtime)
    # Resolve once before probing so the saved location is the one actually
    # checked, even if the parent process changes PATH during the probe.
    if resolved is not None and "python_module" not in runtime:
        location = resolved.argv_prefix[0]
        runtime = {**runtime, "entrypoint": location}
    return extension_doctor({**manifest, "runtime": runtime}, execute=execute), location


def record_runtime_location(
    snapshot: dict[str, Any], *, location: str | None, expected: Any,
) -> None:
    if snapshot.get("entrypoint_path") != expected:
        raise ValueError("extension runtime location changed during doctor; retry")
    if location is not None:
        snapshot["entrypoint_path"] = location
