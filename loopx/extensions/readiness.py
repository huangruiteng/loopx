from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


EXTENSION_DOCTOR_SCHEMA_VERSION = "loopx_extension_doctor_v0"


@dataclass(frozen=True)
class ResolvedRuntimeEntrypoint:
    argv_prefix: tuple[str, ...]
    identity: str


def extension_runtime(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("extension manifest does not declare an executable runtime")
    return runtime


def _file_identity(path: Path, *, executable: bool) -> tuple[Path, str] | None:
    try:
        path = path.resolve(strict=True)
        stat = path.stat()
        if not path.is_file() or (executable and stat.st_mode & 0o111 == 0):
            return None
        with path.open("rb") as file:
            content_digest = hashlib.file_digest(file, "sha256").hexdigest()
    except OSError:
        return None
    identity = {
        "path": str(path),
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "content_sha256": content_digest,
    }
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return path, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolved_entrypoint_identity(command: str) -> tuple[Path, str] | None:
    if "/" in command or "\\" in command:
        path = Path(command).expanduser()
    else:
        resolved = shutil.which(command)
        if resolved is None:
            return None
        path = Path(resolved)
    return _file_identity(path, executable=True)


def resolve_runtime_entrypoint(
    runtime: Mapping[str, Any],
) -> ResolvedRuntimeEntrypoint | None:
    python_module = runtime.get("python_module")
    if python_module is None:
        resolved = resolved_entrypoint_identity(str(runtime["entrypoint"]))
        if resolved is None:
            return None
        return ResolvedRuntimeEntrypoint(
            argv_prefix=(str(resolved[0]),),
            identity=resolved[1],
        )

    interpreter_path = Path(sys.executable).expanduser()
    interpreter = _file_identity(interpreter_path, executable=True)
    try:
        spec = importlib.util.find_spec(str(python_module))
    except (ImportError, AttributeError, ValueError):
        spec = None
    if interpreter is None or spec is None or not spec.origin:
        return None
    module = _file_identity(Path(spec.origin), executable=False)
    if module is None:
        return None
    identity_payload = {
        "kind": "python_module",
        "interpreter_identity": interpreter[1],
        "module": str(python_module),
        "module_identity": module[1],
    }
    serialized = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ResolvedRuntimeEntrypoint(
        argv_prefix=(str(interpreter_path), "-m", str(python_module)),
        identity=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    )


def extension_doctor(
    manifest: Mapping[str, Any],
    *,
    execute: bool = False,
) -> dict[str, Any]:
    runtime = extension_runtime(manifest)
    identity_before = resolve_runtime_entrypoint(runtime)
    available = identity_before is not None
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
            *identity_before.argv_prefix,
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
            identity_after = resolve_runtime_entrypoint(runtime)
            if (
                identity_after is None
                or identity_after.identity != identity_before.identity
            ):
                status = "provider_unavailable"
                available = False
                failure_kind = "entrypoint_changed_during_probe"
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
        "entrypoint_identity": identity_before.identity if verified else None,
        "failure_kind": failure_kind,
        "external_writes_performed": False,
    }
