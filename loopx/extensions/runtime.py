from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..file_lock import exclusive_file_lock
from .process_runtime import run_capped_process
from .manifest import load_extension_manifest
from .readiness import (
    EXTENSION_DOCTOR_SCHEMA_VERSION,
    ResolvedRuntimeEntrypoint,
    extension_doctor,
    extension_runtime,
    resolve_runtime_entrypoint,
)


EXTENSION_STATE_SCHEMA_VERSION = "loopx_extension_state_v0"
EXTENSION_OPERATION_SCHEMA_VERSION = "loopx_extension_operation_v0"
EXTENSION_BINDING_SCHEMA_VERSION = "loopx_extension_runtime_binding_v0"
EXTENSION_ACTIVATION_SCHEMA_VERSION = "loopx_extension_activation_v0"
EXTENSION_RUN_SCHEMA_VERSION = "loopx_extension_run_receipt_v0"
MAX_REVISIONS = 5
MAX_EXTENSION_REQUEST_BYTES = 1_000_000
MAX_EXTENSION_RESPONSE_BYTES = 1_000_000


def default_extension_state_file(runtime_root: str | Path | None = None) -> Path:
    root = (
        Path(runtime_root).expanduser()
        if runtime_root is not None
        else Path.home() / ".codex" / "loopx"
    )
    return root / "extensions" / "state.json"


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": EXTENSION_STATE_SCHEMA_VERSION,
        "extensions": {},
    }


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("extension runtime state is unreadable") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != EXTENSION_STATE_SCHEMA_VERSION
        or not isinstance(payload.get("extensions"), dict)
    ):
        raise ValueError(
            f"extension runtime state must use {EXTENSION_STATE_SCHEMA_VERSION}"
        )
    return payload


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _revision(manifest: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _runtime(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    return extension_runtime(manifest)


def _manifest_snapshot(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(manifest))


def _entry_for_revision(entry: Mapping[str, Any], revision: str) -> dict[str, Any]:
    revisions = entry.get("revisions")
    if not isinstance(revisions, list):
        raise ValueError("extension revision history is invalid")
    for item in revisions:
        if isinstance(item, dict) and item.get("revision") == revision:
            return item
    raise ValueError("extension active revision is missing")


def _retain_revisions(
    revisions: list[dict[str, Any]],
    new_revision: dict[str, Any],
    *,
    required_revision: str | None,
) -> list[dict[str, Any]]:
    deduplicated = [
        item
        for item in revisions
        if item.get("revision") != new_revision.get("revision")
    ]
    required = next(
        (
            item
            for item in deduplicated
            if required_revision and item.get("revision") == required_revision
        ),
        None,
    )
    retained = [*deduplicated, new_revision][-MAX_REVISIONS:]
    if required is not None and required not in retained:
        retained = [required, *retained[-(MAX_REVISIONS - 1) :]]
    return retained


def install_extension(
    manifest_path: str | Path,
    *,
    state_file: str | Path,
    operation: str = "install",
    execute: bool = False,
) -> dict[str, Any]:
    if operation not in {"install", "upgrade"}:
        raise ValueError("extension operation must be install or upgrade")
    manifest = load_extension_manifest(manifest_path)
    _runtime(manifest)
    provider = manifest["provider"]
    extension_id = str(provider["id"])
    revision = _revision(manifest)
    doctor = extension_doctor(manifest, execute=execute)
    if execute and not doctor["verified"]:
        raise ValueError(
            f"extension `{extension_id}` doctor is not ready: {doctor['status']}"
        )
    path = Path(state_file).expanduser()
    changed = False
    lock = exclusive_file_lock(path) if execute else nullcontext()
    with lock:
        state = _read_state(path)
        extensions = state["extensions"]
        existing = extensions.get(extension_id)
        if operation == "install" and existing is not None:
            raise ValueError(f"extension `{extension_id}` is already installed")
        if operation == "upgrade" and not isinstance(existing, dict):
            raise ValueError(f"extension `{extension_id}` is not installed")
        if isinstance(existing, dict) and existing.get("active_revision") == revision:
            raise ValueError(f"extension `{extension_id}` revision is already active")
        previous_revision = (
            str(existing.get("active_revision")) if isinstance(existing, dict) else None
        )
        if execute:
            revisions = (
                list(existing.get("revisions") or [])
                if isinstance(existing, dict)
                else []
            )
            revisions = _retain_revisions(
                revisions,
                {
                    "revision": revision,
                    "version": provider["version"],
                    "manifest": _manifest_snapshot(manifest),
                },
                required_revision=previous_revision,
            )
            extensions[extension_id] = {
                "id": extension_id,
                "enabled": True,
                "active_revision": revision,
                "rollback_revision": previous_revision,
                "doctor_verified_revision": revision,
                "doctor_verified_entrypoint_identity": doctor["entrypoint_identity"],
                "revisions": revisions,
            }
            _write_state(path, state)
            changed = True
    return {
        "ok": True,
        "schema_version": EXTENSION_OPERATION_SCHEMA_VERSION,
        "operation": operation,
        "dry_run": not execute,
        "changed": changed,
        "extension_id": extension_id,
        "version": provider["version"],
        "revision": revision,
        "previous_revision": previous_revision,
        "enabled": True if execute else None,
        "doctor": doctor,
        "rollback_available": previous_revision is not None,
    }


def enable_extension(
    extension_id: str,
    *,
    state_file: str | Path,
    execute: bool = False,
) -> dict[str, Any]:
    path = Path(state_file).expanduser()
    state = _read_state(path)
    entry = state["extensions"].get(extension_id)
    if not isinstance(entry, dict):
        raise ValueError(f"extension `{extension_id}` is not installed")
    active_revision = str(entry.get("active_revision") or "")
    snapshot = _entry_for_revision(entry, active_revision)
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("extension active manifest is invalid")
    already_enabled = bool(entry.get("enabled"))
    doctor = extension_doctor(manifest, execute=execute)
    if execute and not doctor["verified"]:
        with exclusive_file_lock(path):
            current_state = _read_state(path)
            current_entry = current_state["extensions"].get(extension_id)
            if (
                not isinstance(current_entry, dict)
                or current_entry.get("active_revision") != active_revision
                or bool(current_entry.get("enabled")) != already_enabled
            ):
                raise ValueError("extension state changed during enable; retry")
            current_entry.pop("doctor_verified_revision", None)
            current_entry.pop("doctor_verified_entrypoint_identity", None)
            _write_state(path, current_state)
        raise ValueError(
            f"extension `{extension_id}` enable doctor is not ready: {doctor['status']}"
        )
    changed = False
    if execute:
        with exclusive_file_lock(path):
            current_state = _read_state(path)
            current_entry = current_state["extensions"].get(extension_id)
            if (
                not isinstance(current_entry, dict)
                or current_entry.get("active_revision") != active_revision
                or bool(current_entry.get("enabled")) != already_enabled
            ):
                raise ValueError("extension state changed during enable; retry")
            current_entry["enabled"] = True
            current_entry["doctor_verified_revision"] = active_revision
            current_entry["doctor_verified_entrypoint_identity"] = doctor[
                "entrypoint_identity"
            ]
            _write_state(path, current_state)
            changed = not already_enabled
    return {
        "ok": True,
        "schema_version": EXTENSION_OPERATION_SCHEMA_VERSION,
        "operation": "enable",
        "dry_run": not execute,
        "changed": changed,
        "would_change": not already_enabled,
        "extension_id": extension_id,
        "enabled": True if execute else already_enabled,
        "active_revision": active_revision,
        "doctor": doctor,
    }


def disable_extension(
    extension_id: str,
    *,
    state_file: str | Path,
    execute: bool = False,
) -> dict[str, Any]:
    path = Path(state_file).expanduser()
    lock = exclusive_file_lock(path) if execute else nullcontext()
    with lock:
        state = _read_state(path)
        entry = state["extensions"].get(extension_id)
        if not isinstance(entry, dict):
            raise ValueError(f"extension `{extension_id}` is not installed")
        changed = bool(entry.get("enabled"))
        if execute and changed:
            entry["enabled"] = False
            _write_state(path, state)
    return {
        "ok": True,
        "schema_version": EXTENSION_OPERATION_SCHEMA_VERSION,
        "operation": "disable",
        "dry_run": not execute,
        "changed": changed if execute else False,
        "would_change": changed,
        "extension_id": extension_id,
        "enabled": False if execute else bool(entry.get("enabled")),
        "active_revision": entry.get("active_revision"),
    }


def rollback_extension(
    extension_id: str,
    *,
    state_file: str | Path,
    execute: bool = False,
) -> dict[str, Any]:
    path = Path(state_file).expanduser()
    state = _read_state(path)
    entry = state["extensions"].get(extension_id)
    if not isinstance(entry, dict):
        raise ValueError(f"extension `{extension_id}` is not installed")
    target_revision = str(entry.get("rollback_revision") or "")
    if not target_revision:
        raise ValueError(f"extension `{extension_id}` has no rollback revision")
    target = _entry_for_revision(entry, target_revision)
    manifest = target.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("extension rollback manifest is invalid")
    doctor = extension_doctor(manifest, execute=execute)
    if execute and not doctor["verified"]:
        raise ValueError(
            f"extension `{extension_id}` rollback doctor is not ready: {doctor['status']}"
        )
    previous_revision = str(entry.get("active_revision") or "")
    if execute:
        with exclusive_file_lock(path):
            current_state = _read_state(path)
            current_entry = current_state["extensions"].get(extension_id)
            if not isinstance(current_entry, dict):
                raise ValueError(f"extension `{extension_id}` is not installed")
            if (
                current_entry.get("active_revision") != previous_revision
                or current_entry.get("rollback_revision") != target_revision
            ):
                raise ValueError("extension state changed during rollback; retry")
            current_entry["active_revision"] = target_revision
            current_entry["rollback_revision"] = previous_revision
            current_entry["doctor_verified_revision"] = target_revision
            current_entry["doctor_verified_entrypoint_identity"] = doctor[
                "entrypoint_identity"
            ]
            current_entry["enabled"] = True
            _write_state(path, current_state)
    return {
        "ok": True,
        "schema_version": EXTENSION_OPERATION_SCHEMA_VERSION,
        "operation": "rollback",
        "dry_run": not execute,
        "changed": execute,
        "extension_id": extension_id,
        "version": target.get("version"),
        "revision": target_revision,
        "previous_revision": previous_revision,
        "enabled": True if execute else bool(entry.get("enabled")),
        "doctor": doctor,
    }


def extension_status(
    *,
    state_file: str | Path,
    extension_id: str | None = None,
) -> dict[str, Any]:
    state = _read_state(Path(state_file).expanduser())
    entries = state["extensions"]
    if extension_id is not None:
        entry = entries.get(extension_id)
        if not isinstance(entry, dict):
            raise ValueError(f"extension `{extension_id}` is not installed")
        visible = [entry]
    else:
        visible = [entry for entry in entries.values() if isinstance(entry, dict)]
    return {
        "ok": True,
        "schema_version": EXTENSION_STATE_SCHEMA_VERSION,
        "extensions": [
            {
                "id": entry.get("id"),
                "enabled": bool(entry.get("enabled")),
                "active_revision": entry.get("active_revision"),
                "rollback_available": bool(entry.get("rollback_revision")),
                "doctor_verified": bool(entry.get("enabled"))
                and _verified_entrypoint(entry) is not None,
                "revision_count": len(entry.get("revisions") or []),
            }
            for entry in visible
        ],
    }


def doctor_installed_extension(
    extension_id: str,
    *,
    state_file: str | Path,
    execute: bool = False,
) -> dict[str, Any]:
    path = Path(state_file).expanduser()
    state = _read_state(path)
    entry = state["extensions"].get(extension_id)
    if not isinstance(entry, dict):
        raise ValueError(f"extension `{extension_id}` is not installed")
    if not entry.get("enabled"):
        return {
            "ok": True,
            "schema_version": EXTENSION_DOCTOR_SCHEMA_VERSION,
            "extension_id": extension_id,
            "status": "disabled",
            "available": False,
            "verified": False,
            "entrypoint_identity": None,
            "failure_kind": None,
            "external_writes_performed": False,
        }
    active_revision = str(entry.get("active_revision") or "")
    snapshot = _entry_for_revision(entry, active_revision)
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("extension active manifest is invalid")
    doctor = extension_doctor(manifest, execute=execute)
    if execute:
        with exclusive_file_lock(path):
            current_state = _read_state(path)
            current_entry = current_state["extensions"].get(extension_id)
            if (
                not isinstance(current_entry, dict)
                or current_entry.get("active_revision") != active_revision
                or not current_entry.get("enabled")
            ):
                raise ValueError("extension state changed during doctor; retry")
            if doctor["verified"]:
                current_entry["doctor_verified_revision"] = active_revision
                current_entry["doctor_verified_entrypoint_identity"] = doctor[
                    "entrypoint_identity"
                ]
            else:
                current_entry.pop("doctor_verified_revision", None)
                current_entry.pop("doctor_verified_entrypoint_identity", None)
            _write_state(path, current_state)
    return doctor


def _verified_entrypoint(
    entry: Mapping[str, Any],
) -> ResolvedRuntimeEntrypoint | None:
    active_revision = str(entry.get("active_revision") or "")
    if entry.get("doctor_verified_revision") != active_revision:
        return None
    try:
        snapshot = _entry_for_revision(entry, active_revision)
    except ValueError:
        return None
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        return None
    runtime = _runtime(manifest)
    identity = resolve_runtime_entrypoint(runtime)
    if identity is None or identity.identity != entry.get(
        "doctor_verified_entrypoint_identity"
    ):
        return None
    return identity


def _active_manifest(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    active_revision = str(entry.get("active_revision") or "")
    snapshot = _entry_for_revision(entry, active_revision)
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("extension active manifest is invalid")
    return manifest


def extension_catalog_entries(
    extension_manifest_paths: Iterable[str | Path] = (),
    *,
    state_file: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Compose declared manifests with installed runtime lifecycle state."""

    manifests: dict[str, Mapping[str, Any]] = {}
    lifecycle: dict[str, dict[str, Any]] = {}
    for manifest_path in extension_manifest_paths:
        manifest = load_extension_manifest(manifest_path)
        extension_id = str(manifest["provider"]["id"])
        if extension_id in manifests:
            raise ValueError(f"duplicate capability provider `{extension_id}`")
        manifests[extension_id] = manifest
        lifecycle[extension_id] = {
            "declared": True,
            "installed": False,
            "enabled": False,
            "ready": False,
        }

    if state_file is not None:
        state = _read_state(Path(state_file).expanduser())
        for extension_id, entry in state["extensions"].items():
            if not isinstance(entry, Mapping):
                raise ValueError(f"extension `{extension_id}` runtime entry is invalid")
            manifest = _active_manifest(entry)
            provider = manifest.get("provider")
            if not isinstance(provider, Mapping) or provider.get("id") != extension_id:
                raise ValueError(
                    f"extension `{extension_id}` active manifest is invalid"
                )
            manifests[extension_id] = manifest
            enabled = bool(entry.get("enabled"))
            lifecycle[extension_id] = {
                "declared": True,
                "installed": True,
                "enabled": enabled,
                "ready": enabled and _verified_entrypoint(entry) is not None,
                "active_revision": str(entry.get("active_revision") or ""),
            }

    entries: list[dict[str, Any]] = []
    for extension_id, manifest in manifests.items():
        normalized = deepcopy(dict(manifest))
        normalized["provider"] = (
            deepcopy(dict(manifest["provider"])) | lifecycle[extension_id]
        )
        entries.append(normalized)
    return entries


def resolve_capability_extension_id(
    *,
    state_file: str | Path,
    capability_id: str,
    protocol: str,
) -> str:
    """Resolve one ready extension implementation without caller aliases."""

    matching: list[str] = []
    for entry in extension_catalog_entries(state_file=state_file):
        provider = entry.get("provider")
        if not isinstance(provider, Mapping) or not provider.get("ready"):
            continue
        implementations = entry.get("implementations")
        if not isinstance(implementations, list):
            continue
        if any(
            isinstance(item, Mapping)
            and item.get("capability_id") == capability_id
            and item.get("protocol") == protocol
            for item in implementations
        ):
            matching.append(str(entry["provider"]["id"]))
    if not matching:
        raise ValueError(
            f"no enabled, doctor-ready extension implements `{capability_id}` "
            f"with protocol `{protocol}`"
        )
    if len(matching) != 1:
        raise ValueError(
            f"multiple enabled, doctor-ready extensions implement `{capability_id}` "
            f"with protocol `{protocol}`: {matching}"
        )
    return matching[0]


def _resolved_active_extension(
    extension_id: str,
    *,
    state_file: str | Path,
) -> tuple[str, ResolvedRuntimeEntrypoint, Mapping[str, Any]]:
    state = _read_state(Path(state_file).expanduser())
    entry = state["extensions"].get(extension_id)
    if not isinstance(entry, dict):
        raise ValueError(f"extension `{extension_id}` is not installed")
    if not entry.get("enabled"):
        raise ValueError(f"extension `{extension_id}` is disabled")
    active_revision = str(entry.get("active_revision") or "")
    verified_entrypoint = _verified_entrypoint(entry)
    if verified_entrypoint is None:
        raise ValueError(f"extension `{extension_id}` doctor readiness is stale")
    manifest = _active_manifest(entry)
    return active_revision, verified_entrypoint, manifest


def resolve_extension_activation(
    extension_id: str,
    *,
    state_file: str | Path,
    required_permissions: Sequence[str] = (),
) -> dict[str, Any]:
    """Resolve one enabled, revision-bound extension compatibility delegate."""

    active_revision, _, manifest = _resolved_active_extension(
        extension_id,
        state_file=state_file,
    )
    provider = manifest.get("provider")
    if not isinstance(provider, Mapping):
        raise ValueError("extension active manifest is incomplete")
    declared_permissions = {
        str(permission)
        for permission in provider.get("permissions") or []
        if str(permission).strip()
    }
    required = {
        str(permission).strip()
        for permission in required_permissions
        if str(permission).strip()
    }
    missing = sorted(required - declared_permissions)
    if missing:
        raise ValueError(
            f"extension `{extension_id}` does not declare permissions {missing}"
        )
    return {
        "schema_version": EXTENSION_ACTIVATION_SCHEMA_VERSION,
        "extension_id": extension_id,
        "provider_version": provider.get("version"),
        "revision": active_revision,
        "enabled": True,
        "doctor_verified": True,
        "required_permissions": sorted(required),
    }


def resolve_extension_binding(
    extension_id: str,
    *,
    state_file: str | Path,
    capability_id: str,
    protocol: str,
    permission: str,
) -> dict[str, Any]:
    active_revision, verified_entrypoint, manifest = _resolved_active_extension(
        extension_id,
        state_file=state_file,
    )
    provider = manifest.get("provider")
    runtime = _runtime(manifest)
    implementations = manifest.get("implementations")
    if not isinstance(provider, Mapping) or not isinstance(implementations, list):
        raise ValueError("extension active manifest is incomplete")
    if permission not in (provider.get("permissions") or []):
        raise ValueError(
            f"extension `{extension_id}` does not declare permission `{permission}`"
        )
    if permission not in (runtime.get("required_permissions") or []):
        raise ValueError(
            f"extension `{extension_id}` runtime does not require permission "
            f"`{permission}`"
        )
    matching = [
        item
        for item in implementations
        if isinstance(item, Mapping)
        and item.get("capability_id") == capability_id
        and item.get("protocol") == protocol
    ]
    if len(matching) != 1 or runtime.get("protocol") != protocol:
        raise ValueError(
            f"extension `{extension_id}` does not implement `{capability_id}` "
            f"with protocol `{protocol}`"
        )
    return {
        "schema_version": EXTENSION_BINDING_SCHEMA_VERSION,
        "extension_id": extension_id,
        "provider_version": provider.get("version"),
        "revision": active_revision,
        "protocol": protocol,
        "argv": [*verified_entrypoint.argv_prefix, *(runtime.get("args") or [])],
        "doctor_argv": [
            *verified_entrypoint.argv_prefix,
            *(runtime.get("args") or []),
            *(runtime.get("doctor_args") or []),
        ],
        "timeout_seconds": runtime["timeout_seconds"],
    }


def resolve_extension_runtime_binding(
    extension_id: str,
    *,
    state_file: str | Path,
    protocol: str,
    permission: str,
) -> dict[str, Any]:
    """Resolve an extension runtime without coupling dispatch to capability metadata."""

    active_revision, verified_entrypoint, manifest = _resolved_active_extension(
        extension_id,
        state_file=state_file,
    )
    provider = manifest.get("provider")
    runtime = _runtime(manifest)
    if not isinstance(provider, Mapping):
        raise ValueError("extension active manifest is incomplete")
    if permission not in (provider.get("permissions") or []):
        raise ValueError(
            f"extension `{extension_id}` does not declare permission `{permission}`"
        )
    if permission not in (runtime.get("required_permissions") or []):
        raise ValueError(
            f"extension `{extension_id}` runtime does not require permission "
            f"`{permission}`"
        )
    if runtime.get("protocol") != protocol:
        raise ValueError(
            f"extension `{extension_id}` does not expose runtime protocol `{protocol}`"
        )
    return {
        "schema_version": EXTENSION_BINDING_SCHEMA_VERSION,
        "extension_id": extension_id,
        "provider_version": provider.get("version"),
        "revision": active_revision,
        "protocol": protocol,
        "argv": [*verified_entrypoint.argv_prefix, *(runtime.get("args") or [])],
        "doctor_argv": [
            *verified_entrypoint.argv_prefix,
            *(runtime.get("args") or []),
            *(runtime.get("doctor_args") or []),
        ],
        "timeout_seconds": runtime["timeout_seconds"],
    }


def run_standalone_extension(
    extension_id: str,
    *,
    state_file: str | Path,
    request: Mapping[str, Any],
    execute: bool = False,
) -> dict[str, Any]:
    """Run one lifecycle-gated standalone extension over bounded JSON stdin/stdout."""

    active_revision, verified_entrypoint, manifest = _resolved_active_extension(
        extension_id,
        state_file=state_file,
    )
    provider = manifest.get("provider")
    runtime = _runtime(manifest)
    if not isinstance(provider, Mapping):
        raise ValueError("extension active manifest is incomplete")
    if manifest.get("capabilities") or manifest.get("implementations"):
        raise ValueError(
            "extension run only accepts standalone extensions; invoke capability "
            "providers through their capability or domain command"
        )
    if not isinstance(request, Mapping):
        raise ValueError("extension run request must be a JSON object")

    required_permissions = [
        str(value) for value in runtime.get("required_permissions") or []
    ]
    declared_permissions = {str(value) for value in provider.get("permissions") or []}
    missing_permissions = sorted(set(required_permissions) - declared_permissions)
    if missing_permissions:
        raise ValueError(
            f"extension `{extension_id}` does not declare permissions "
            f"{missing_permissions}"
        )
    if declared_permissions:
        raise ValueError(
            f"extension `{extension_id}` declares permissions "
            f"{sorted(declared_permissions)}; standalone extension run grants no "
            "effect dispatch, so use a capability or domain command that owns "
            "policy checks and a request-bound execution envelope"
        )

    try:
        request_bytes = json.dumps(
            dict(request),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("extension run request must be JSON serializable") from exc
    if len(request_bytes) > MAX_EXTENSION_REQUEST_BYTES:
        raise ValueError("extension run request exceeds the 1000000-byte limit")

    receipt: dict[str, Any] = {
        "ok": True,
        "schema_version": EXTENSION_RUN_SCHEMA_VERSION,
        "operation": "run",
        "extension_id": extension_id,
        "provider_version": provider.get("version"),
        "revision": active_revision,
        "protocol": runtime["protocol"],
        "required_permissions": required_permissions,
        "dry_run": not execute,
        "executed": False,
        "status": "ready" if not execute else "running",
        "input_schema_version": request.get("schema_version"),
    }
    if not execute:
        return receipt

    argv = [*verified_entrypoint.argv_prefix, *(runtime.get("args") or [])]
    try:
        completed = run_capped_process(
            argv,
            stdin=request_bytes,
            timeout_seconds=int(runtime["timeout_seconds"]),
            output_limit_bytes=MAX_EXTENSION_RESPONSE_BYTES,
        )
    except OSError:
        return {
            **receipt,
            "ok": False,
            "executed": True,
            "status": "provider_failed",
            "failure_kind": "execution_failed",
            "exit_code": None,
        }
    if completed.failure_kind is not None:
        response_too_large = completed.failure_kind == "response_too_large"
        return {
            **receipt,
            "ok": False,
            "executed": True,
            "status": (
                "invalid_provider_output" if response_too_large else "provider_failed"
            ),
            "failure_kind": completed.failure_kind,
            "exit_code": (
                None if completed.failure_kind == "timeout" else completed.returncode
            ),
        }

    try:
        provider_result = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        provider_result = None
    if not isinstance(provider_result, dict):
        return {
            **receipt,
            "ok": False,
            "executed": True,
            "status": "invalid_provider_output",
            "failure_kind": "response_not_json_object",
            "exit_code": completed.returncode,
        }
    succeeded = completed.returncode == 0 and provider_result.get("ok") is not False
    return {
        **receipt,
        "ok": succeeded,
        "executed": True,
        "status": "succeeded" if succeeded else "provider_failed",
        "exit_code": completed.returncode,
        "provider_result": provider_result,
    }


def resolve_capability_binding(
    *,
    state_file: str | Path,
    capability_id: str,
    protocol: str,
    permission: str,
) -> dict[str, Any]:
    extension_id = resolve_capability_extension_id(
        state_file=state_file,
        capability_id=capability_id,
        protocol=protocol,
    )
    return resolve_extension_binding(
        extension_id,
        state_file=state_file,
        capability_id=capability_id,
        protocol=protocol,
        permission=permission,
    )


def execute_extension_runtime_binding(
    binding: Mapping[str, Any],
    *,
    request: Mapping[str, Any],
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute a resolved binding after its capability authorizes the request."""

    if binding.get("schema_version") != EXTENSION_BINDING_SCHEMA_VERSION:
        raise ValueError(
            f"extension runtime binding must use {EXTENSION_BINDING_SCHEMA_VERSION}"
        )
    argv = binding.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(value, str) and value for value in argv)
    ):
        raise ValueError("extension runtime binding argv is invalid")
    try:
        timeout_seconds = int(binding.get("timeout_seconds"))
    except (TypeError, ValueError) as exc:
        raise ValueError("extension runtime binding timeout is invalid") from exc
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("extension runtime binding timeout is invalid")
    try:
        request_bytes = json.dumps(
            dict(request),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("extension runtime request must be JSON serializable") from exc
    if len(request_bytes) > MAX_EXTENSION_REQUEST_BYTES:
        raise ValueError("extension runtime request exceeds the 1000000-byte limit")
    try:
        completed = run_capped_process(
            argv,
            stdin=request_bytes,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=MAX_EXTENSION_RESPONSE_BYTES,
            env=environment,
        )
    except OSError as exc:
        raise RuntimeError("extension provider execution failed") from exc
    if completed.failure_kind is not None:
        raise RuntimeError(
            f"extension provider execution failed: {completed.failure_kind}"
        )
    try:
        provider_result = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("extension provider returned invalid JSON") from exc
    if not isinstance(provider_result, dict):
        raise RuntimeError("extension provider returned a non-object")
    if completed.returncode != 0 or provider_result.get("ok") is False:
        raise RuntimeError("extension provider reported failure")
    return provider_result
