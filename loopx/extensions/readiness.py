from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXTENSION_DOCTOR_SCHEMA_VERSION = "loopx_extension_doctor_v0"
RUNTIME_ENTRYPOINT_IDENTITY_SCHEMA_VERSION = "loopx_runtime_entrypoint_identity_v1"


@dataclass(frozen=True)
class ResolvedRuntimeEntrypoint:
    argv_prefix: tuple[str, ...]
    identity: str
    path_prefix: str | None = None


def runtime_process_environment(
    path_prefix: str | None,
    base: Mapping[str, str] | None = None,
) -> Mapping[str, str] | None:
    if path_prefix is None:
        return base
    if not isinstance(path_prefix, str) or not Path(path_prefix).is_absolute():
        raise ValueError("extension runtime search directory must be absolute")
    environment = dict(os.environ if base is None else base)
    environment["PATH"] = path_prefix + os.pathsep + environment.get("PATH", os.defpath)
    return environment


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
        "schema_version": RUNTIME_ENTRYPOINT_IDENTITY_SCHEMA_VERSION,
        "kind": "file_artifact",
        "executable": executable,
        "size": stat.st_size,
        "content_sha256": content_digest,
    }
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return path, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolved_entrypoint_identity(command: str) -> tuple[Path, str] | None:
    if "/" in command or "\\" in command:
        path = Path(command).expanduser()
        if not path.is_absolute():
            path = Path(os.path.abspath(path))
    else:
        resolved = shutil.which(command)
        if resolved is None:
            return None
        path = Path(resolved)
    identified = _file_identity(path, executable=True)
    if identified is None:
        return None
    # Hash the final executable artifact, but retain the launcher path selected
    # by the operator. Package managers commonly expose console scripts through
    # a shared symlink directory; sibling tools in that directory must remain
    # available to the provider subprocess even when the link target lives in
    # an isolated package environment.
    return path, identified[1]


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
            path_prefix=str(resolved[0].parent),
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
        assert identity_before is not None
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
                env=runtime_process_environment(identity_before.path_prefix),
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
        "entrypoint_identity": (
            identity_before.identity
            if verified and identity_before is not None
            else None
        ),
        "failure_kind": failure_kind,
        "external_writes_performed": False,
    }
