from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


EXTENSION_DOCTOR_SCHEMA_VERSION = "loopx_extension_doctor_v0"


def extension_runtime(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise ValueError("extension manifest does not declare an executable runtime")
    return runtime


def resolved_entrypoint_identity(command: str) -> tuple[Path, str] | None:
    if "/" in command or "\\" in command:
        path = Path(command).expanduser()
    else:
        resolved = shutil.which(command)
        if resolved is None:
            return None
        path = Path(resolved)
    try:
        path = path.resolve(strict=True)
        stat = path.stat()
        if not path.is_file() or stat.st_mode & 0o111 == 0:
            return None
        with path.open("rb") as executable:
            content_digest = hashlib.file_digest(executable, "sha256").hexdigest()
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


def extension_doctor(
    manifest: Mapping[str, Any],
    *,
    execute: bool = False,
) -> dict[str, Any]:
    runtime = extension_runtime(manifest)
    entrypoint = str(runtime["entrypoint"])
    identity_before = resolved_entrypoint_identity(entrypoint)
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
            str(identity_before[0]),
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
            identity_after = resolved_entrypoint_identity(entrypoint)
            if identity_after is None or identity_after[1] != identity_before[1]:
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
        "entrypoint_identity": identity_before[1] if verified else None,
        "failure_kind": failure_kind,
        "external_writes_performed": False,
    }
