from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from ..file_lock import exclusive_file_lock
from .manifest import load_extension_manifest


EXTENSION_STATE_SCHEMA_VERSION = "loopx_extension_state_v0"
EXTENSION_OPERATION_SCHEMA_VERSION = "loopx_extension_operation_v0"
EXTENSION_DOCTOR_SCHEMA_VERSION = "loopx_extension_doctor_v0"
EXTENSION_BINDING_SCHEMA_VERSION = "loopx_extension_runtime_binding_v0"
MAX_REVISIONS = 5


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
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("extension manifest does not declare an executable runtime")
    return runtime


def _command_available(command: str) -> bool:
    if "/" in command or "\\" in command:
        path = Path(command).expanduser()
        return path.is_file() and path.stat().st_mode & 0o111 != 0
    return shutil.which(command) is not None


def extension_doctor(
    manifest: Mapping[str, Any],
    *,
    execute: bool = False,
) -> dict[str, Any]:
    runtime = _runtime(manifest)
    entrypoint = str(runtime["entrypoint"])
    available = _command_available(entrypoint)
    doctor_args = [str(value) for value in runtime.get("doctor_args") or []]
    status = "ready" if available else "entrypoint_missing"
    verified = False
    failure_kind = None
    if not doctor_args:
        status = "doctor_not_configured"
        available = False
        failure_kind = "doctor_not_configured"
    elif available and not execute:
        status = "probe_required"
    elif available:
        argv = [
            entrypoint,
            *[str(value) for value in runtime.get("args") or []],
            *doctor_args,
        ]
        try:
            completed = subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=int(runtime["timeout_seconds"]),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
            failure_kind = "probe_execution_failed"
        if completed is None or completed.returncode != 0:
            status = "provider_unavailable"
            available = False
            failure_kind = failure_kind or "probe_nonzero_exit"
        else:
            status = "ready"
            verified = True
    return {
        "ok": True,
        "schema_version": EXTENSION_DOCTOR_SCHEMA_VERSION,
        "extension_id": manifest["provider"]["id"],
        "version": manifest["provider"]["version"],
        "status": status,
        "available": available,
        "verified": verified,
        "failure_kind": failure_kind,
        "external_writes_performed": False,
    }


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
        if (
            isinstance(existing, dict)
            and existing.get("active_revision") == revision
        ):
            raise ValueError(
                f"extension `{extension_id}` revision is already active"
            )
        previous_revision = (
            str(existing.get("active_revision"))
            if isinstance(existing, dict)
            else None
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
                "doctor_verified": entry.get("doctor_verified_revision")
                == entry.get("active_revision"),
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
    state = _read_state(Path(state_file).expanduser())
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
            "failure_kind": None,
            "external_writes_performed": False,
        }
    active_revision = str(entry.get("active_revision") or "")
    snapshot = _entry_for_revision(entry, active_revision)
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("extension active manifest is invalid")
    return extension_doctor(manifest, execute=execute)


def resolve_extension_binding(
    extension_id: str,
    *,
    state_file: str | Path,
    capability_id: str,
    protocol: str,
    permission: str,
) -> dict[str, Any]:
    state = _read_state(Path(state_file).expanduser())
    entry = state["extensions"].get(extension_id)
    if not isinstance(entry, dict):
        raise ValueError(f"extension `{extension_id}` is not installed")
    if not entry.get("enabled"):
        raise ValueError(f"extension `{extension_id}` is disabled")
    active_revision = str(entry.get("active_revision") or "")
    if entry.get("doctor_verified_revision") != active_revision:
        raise ValueError(f"extension `{extension_id}` doctor readiness is stale")
    snapshot = _entry_for_revision(entry, active_revision)
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("extension active manifest is invalid")
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
        "argv": [runtime["entrypoint"], *(runtime.get("args") or [])],
        "doctor_argv": [
            runtime["entrypoint"],
            *(runtime.get("args") or []),
            *(runtime.get("doctor_args") or []),
        ],
        "timeout_seconds": runtime["timeout_seconds"],
    }
