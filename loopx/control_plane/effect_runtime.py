from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..file_lock import process_is_alive

EFFECT_RUNTIME_REQUEST_SCHEMA_VERSION = "loopx_effect_runtime_request_v0"
EFFECT_RUNTIME_RESPONSE_SCHEMA_VERSION = "loopx_effect_runtime_response_v1"
EFFECT_RUNTIME_INFO_SCHEMA_VERSION = "loopx_effect_runtime_info_v0"
EFFECT_RUNTIME_READINESS_SCHEMA_VERSION = "loopx_effect_runtime_readiness_v0"
MINIMUM_NODE_VERSION = (22, 6, 0)
MINIMUM_NODE_VERSION_TEXT = ".".join(str(part) for part in MINIMUM_NODE_VERSION)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024
DEFAULT_EFFECT_RUNTIME_IDLE_MS = 5 * 60 * 1_000
MAX_EFFECT_RUNTIME_IDLE_MS = 2_147_483_647
STARTUP_LOCK_TIMEOUT_SECONDS = 15.0
STARTUP_READY_TIMEOUT_SECONDS = 15.0
STARTUP_POLL_SECONDS = 0.025
_NODE_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_RUNTIME_SOURCE_SUFFIXES = frozenset({".json", ".ts"})
_RuntimeSourceSnapshot = tuple[tuple[str, int, int, int], ...]


def _validate_effect_runtime_idle_ms(environment: Mapping[str, str]) -> int:
    raw = environment.get("LOOPX_EFFECT_RUNTIME_IDLE_MS")
    if raw is None:
        return DEFAULT_EFFECT_RUNTIME_IDLE_MS
    normalized = raw.strip()
    if not re.fullmatch(r"[0-9]+", normalized):
        raise EffectRuntimeStartupError(
            "LOOPX_EFFECT_RUNTIME_IDLE_MS must be a positive base-10 integer",
            diagnostic_code="invalid_runtime_idle_ms",
        )
    parsed = int(normalized)
    if not 1 <= parsed <= MAX_EFFECT_RUNTIME_IDLE_MS:
        raise EffectRuntimeStartupError(
            "LOOPX_EFFECT_RUNTIME_IDLE_MS must be between "
            f"1 and {MAX_EFFECT_RUNTIME_IDLE_MS}",
            diagnostic_code="invalid_runtime_idle_ms",
        )
    return parsed


def _require_matching_runtime_idle_ms(
    info: Mapping[str, Any],
    *,
    requested_idle_ms: int,
) -> None:
    if info.get("idle_ms") != requested_idle_ms:
        raise EffectRuntimeStartupError(
            "LOOPX_EFFECT_RUNTIME_IDLE_MS conflicts with the running managed runtime",
            diagnostic_code="runtime_idle_ms_conflict",
        )


class EffectRuntimeRemoteError(RuntimeError):
    """A typed exception returned by the managed TypeScript runtime."""

    def __init__(
        self,
        message: str,
        *,
        error_kind: str,
        diagnostic_code: str,
    ) -> None:
        super().__init__(message)
        self.error_kind = error_kind
        self.diagnostic_code = diagnostic_code


class EffectRuntimeRejected(EffectRuntimeRemoteError):
    """A typed request reached the runtime but failed semantic validation."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str = "invalid_request",
    ) -> None:
        super().__init__(
            message,
            error_kind="request_rejected",
            diagnostic_code=diagnostic_code,
        )


class EffectRuntimeConflict(EffectRuntimeRemoteError):
    """The request conflicted with newer persisted state."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(
            message,
            error_kind="conflict",
            diagnostic_code=diagnostic_code,
        )


class EffectRuntimeIOError(EffectRuntimeRemoteError):
    """A managed runtime filesystem operation failed."""

    def __init__(
        self,
        message: str,
        *,
        error_kind: str,
        diagnostic_code: str,
        transient: bool,
    ) -> None:
        super().__init__(
            message,
            error_kind=error_kind,
            diagnostic_code=diagnostic_code,
        )
        self.transient = transient


class EffectRuntimeTransientIOError(EffectRuntimeIOError):
    """A retryable managed runtime filesystem operation failed."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(
            message,
            error_kind="io_transient",
            diagnostic_code=diagnostic_code,
            transient=True,
        )


class EffectRuntimePermanentIOError(EffectRuntimeIOError):
    """A non-retryable managed runtime filesystem operation failed."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(
            message,
            error_kind="io_permanent",
            diagnostic_code=diagnostic_code,
            transient=False,
        )


class EffectRuntimeLockTimeout(EffectRuntimeRemoteError):
    """A managed mutation lock could not be acquired before its deadline."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(
            message,
            error_kind="lock_timeout",
            diagnostic_code=diagnostic_code,
        )


class EffectRuntimeInternalError(EffectRuntimeRemoteError):
    """The managed handler failed outside a declared request or I/O error."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(
            message,
            error_kind="internal_failure",
            diagnostic_code=diagnostic_code,
        )


class EffectRuntimeStartupError(RuntimeError):
    """The managed runtime could not reach a request-serving state."""

    def __init__(self, message: str, *, diagnostic_code: str) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code


def _control_plane_root() -> Path:
    return Path(__file__).resolve().parent


def _scan_runtime_source_files(root: Path) -> tuple[str, ...]:
    files: list[str] = []
    for directory, child_directories, filenames in os.walk(root):
        child_directories.sort()
        relative_directory = os.path.relpath(directory, root)
        if relative_directory == ".":
            relative_directory = ""
        files.extend(
            Path(relative_directory, filename).as_posix()
            for filename in sorted(filenames)
            if Path(filename).suffix in _RUNTIME_SOURCE_SUFFIXES
            and Path(directory, filename).is_file()
        )
    return tuple(sorted(files))


def _runtime_file_snapshot(
    root: Path,
    files: tuple[str, ...],
) -> _RuntimeSourceSnapshot:
    return tuple(
        (
            relative,
            (metadata := (root / relative).stat()).st_mtime_ns,
            metadata.st_ctime_ns,
            metadata.st_size,
        )
        for relative in files
    )


def _runtime_source_snapshot(root: Path | None = None) -> _RuntimeSourceSnapshot:
    """Return cheap metadata that invalidates the packaged-source hash."""

    source_root = (root or _control_plane_root()).resolve()
    return _runtime_file_snapshot(source_root, _scan_runtime_source_files(source_root))


def _runtime_source_files(root: Path | None = None) -> tuple[str, ...]:
    """Return the packaged source boundary owned by the managed runtime."""

    return tuple(relative for relative, *_metadata in _runtime_source_snapshot(root))


@lru_cache(maxsize=8)
def _runtime_fingerprint_for_snapshot(
    root: str,
    snapshot: _RuntimeSourceSnapshot,
) -> str:
    digest = hashlib.sha256()
    source_root = Path(root)
    for relative, *_metadata in snapshot:
        digest.update(relative.encode("utf-8"))
        digest.update((source_root / relative).read_bytes())
    return digest.hexdigest()


def _runtime_fingerprint() -> str:
    root = _control_plane_root()
    resolved_root = os.fspath(root.resolve())
    try:
        return _runtime_fingerprint_for_snapshot(
            resolved_root,
            _runtime_source_snapshot(root),
        )
    except FileNotFoundError:
        try:
            return _runtime_fingerprint_for_snapshot(
                resolved_root,
                _runtime_source_snapshot(root),
            )
        except FileNotFoundError as exc:
            raise EffectRuntimeStartupError(
                "TypeScript Effect runtime source topology did not stabilize",
                diagnostic_code="packaged_runtime_source_unstable",
            ) from exc


def _runtime_dir() -> Path:
    owner = str(getattr(os, "getuid", lambda: Path.home())())
    suffix = hashlib.sha256(owner.encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"loopx-effect-runtime-{suffix}"


def _runtime_info_path(fingerprint: str) -> Path:
    return _runtime_dir() / f"runtime-{fingerprint[:16]}.json"


def _runtime_server_path() -> Path:
    return _control_plane_root() / "effect_runtime_server.ts"


def _node_executable() -> str:
    status, executable, _version = _probe_node()
    if status != "ready" or executable is None:
        raise EffectRuntimeStartupError(
            f"LoopX Effect runtime requires Node.js {MINIMUM_NODE_VERSION_TEXT} "
            "or newer",
            diagnostic_code="node_unavailable",
        )
    return executable


def _probe_node() -> tuple[str, str | None, str | None]:
    executable = shutil.which("node")
    if executable is None:
        return "missing", None, None
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "probe_failed", executable, None
    match = _NODE_VERSION_RE.fullmatch(completed.stdout.strip())
    version = tuple(int(part) for part in match.groups()) if match else None
    if completed.returncode != 0 or version is None:
        return "probe_failed", executable, None
    version_text = ".".join(str(part) for part in version)
    if version < MINIMUM_NODE_VERSION:
        return "unsupported", executable, version_text
    return "ready", executable, version_text


def _pid_is_alive(value: object) -> bool:
    return process_is_alive(value)


def _start_lock_holder_pid(path: Path) -> int | None:
    try:
        value = int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, OSError, ValueError):
        return None
    return value if value > 0 else None


def _read_info(path: Path, *, fingerprint: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("schema_version") != EFFECT_RUNTIME_INFO_SCHEMA_VERSION
        or payload.get("fingerprint") != fingerprint
        or payload.get("host") != "127.0.0.1"
        or not isinstance(payload.get("port"), int)
        or not isinstance(payload.get("token"), str)
        or isinstance(payload.get("idle_ms"), bool)
        or not isinstance(payload.get("idle_ms"), int)
        or not 1 <= payload["idle_ms"] <= MAX_EFFECT_RUNTIME_IDLE_MS
        or not _pid_is_alive(payload.get("pid"))
    ):
        return None
    return payload


def _request_with_info(
    info: Mapping[str, Any],
    *,
    request_id: str,
    method: str,
    params: Mapping[str, Any],
    timeout: float,
) -> dict[str, Any]:
    request = {
        "schema_version": EFFECT_RUNTIME_REQUEST_SCHEMA_VERSION,
        "token": info["token"],
        "request_id": request_id,
        "method": method,
        "params": dict(params),
    }
    encoded = (json.dumps(request, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_REQUEST_BYTES:
        raise EffectRuntimeRejected(
            "TypeScript Effect runtime request is oversized",
            diagnostic_code="request_too_large",
        )
    chunks: list[bytes] = []
    size = 0
    with socket.create_connection(
        (str(info["host"]), int(info["port"])), timeout=timeout
    ) as connection:
        connection.settimeout(timeout)
        connection.sendall(encoded)
        while True:
            chunk = connection.recv(64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise RuntimeError("TypeScript Effect runtime response is oversized")
            if b"\n" in chunk:
                break
    try:
        response = json.loads(b"".join(chunks).split(b"\n", 1)[0])
    except (json.JSONDecodeError, IndexError):
        raise RuntimeError(
            "TypeScript Effect runtime returned malformed JSON"
        ) from None
    if (
        not isinstance(response, dict)
        or response.get("schema_version") != EFFECT_RUNTIME_RESPONSE_SCHEMA_VERSION
        or response.get("request_id") != request_id
    ):
        raise RuntimeError("TypeScript Effect runtime response shape mismatch")
    if response.get("ok") is not True:
        raise _remote_runtime_error(response.get("error"))
    return response


def _remote_runtime_error(value: object) -> EffectRuntimeRemoteError:
    if not isinstance(value, Mapping):
        return EffectRuntimeInternalError(
            "TypeScript Effect runtime returned an invalid error envelope",
            diagnostic_code="invalid_error_envelope",
        )
    kind = value.get("kind")
    code = value.get("code")
    message = value.get("message")
    if (
        not isinstance(kind, str)
        or not kind
        or not isinstance(code, str)
        or not code
    ):
        return EffectRuntimeInternalError(
            "TypeScript Effect runtime returned an invalid error envelope",
            diagnostic_code="invalid_error_envelope",
        )
    rendered = " ".join(
        str(message or "TypeScript Effect runtime request failed").split()
    )
    rendered = rendered[:240] or "TypeScript Effect runtime request failed"
    if kind == "request_rejected":
        return EffectRuntimeRejected(rendered, diagnostic_code=code)
    if kind == "conflict":
        return EffectRuntimeConflict(rendered, diagnostic_code=code)
    if kind == "io_transient":
        return EffectRuntimeTransientIOError(rendered, diagnostic_code=code)
    if kind == "io_permanent":
        return EffectRuntimePermanentIOError(rendered, diagnostic_code=code)
    if kind == "lock_timeout":
        return EffectRuntimeLockTimeout(rendered, diagnostic_code=code)
    if kind == "internal_failure":
        return EffectRuntimeInternalError(rendered, diagnostic_code=code)
    return EffectRuntimeInternalError(
        "TypeScript Effect runtime returned an unsupported error kind",
        diagnostic_code="unsupported_error_kind",
    )


def _start_runtime(
    *,
    fingerprint: str,
    info_path: Path,
    requested_idle_ms: int | None = None,
) -> dict[str, Any]:
    if requested_idle_ms is None:
        requested_idle_ms = _validate_effect_runtime_idle_ms(os.environ)
    runtime_dir = info_path.parent
    runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        runtime_dir.chmod(0o700)
    except OSError:
        pass
    lock = runtime_dir / f"start-{fingerprint[:16]}.lock"
    lock_deadline = time.monotonic() + STARTUP_LOCK_TIMEOUT_SECONDS
    acquired = False
    while time.monotonic() < lock_deadline:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                lock_file.write(f"{os.getpid()}\n")
                lock_file.flush()
                os.fsync(lock_file.fileno())
            acquired = True
            break
        except FileExistsError:
            existing = _read_info(info_path, fingerprint=fingerprint)
            if existing is not None:
                _require_matching_runtime_idle_ms(
                    existing,
                    requested_idle_ms=requested_idle_ms,
                )
                return existing
            holder_pid = _start_lock_holder_pid(lock)
            if holder_pid is not None and not _pid_is_alive(holder_pid):
                try:
                    lock.unlink()
                except FileNotFoundError:
                    pass
                continue
            try:
                if time.time() - lock.stat().st_mtime > 10:
                    lock.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(STARTUP_POLL_SECONDS)
    if not acquired:
        existing = _read_info(info_path, fingerprint=fingerprint)
        if existing is not None:
            _require_matching_runtime_idle_ms(
                existing,
                requested_idle_ms=requested_idle_ms,
            )
            return existing
        raise EffectRuntimeStartupError(
            "TypeScript Effect runtime startup lock timed out",
            diagnostic_code="startup_lock_timeout",
        )
    try:
        existing = _read_info(info_path, fingerprint=fingerprint)
        if existing is not None:
            _require_matching_runtime_idle_ms(
                existing,
                requested_idle_ms=requested_idle_ms,
            )
            return existing
        token = secrets.token_urlsafe(32)
        environment = os.environ.copy()
        environment["LOOPX_EFFECT_RUNTIME_TOKEN"] = token
        try:
            process = subprocess.Popen(
                [
                    _node_executable(),
                    "--no-warnings",
                    "--experimental-strip-types",
                    str(_runtime_server_path()),
                    "--info",
                    str(info_path),
                    "--fingerprint",
                    fingerprint,
                ],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
                close_fds=True,
            )
        except OSError as exc:
            raise EffectRuntimeStartupError(
                "TypeScript Effect runtime process could not be launched",
                diagnostic_code="runtime_launch_failed",
            ) from exc
        ready_deadline = time.monotonic() + STARTUP_READY_TIMEOUT_SECONDS
        while time.monotonic() < ready_deadline:
            info = _read_info(info_path, fingerprint=fingerprint)
            if info is not None:
                _require_matching_runtime_idle_ms(
                    info,
                    requested_idle_ms=requested_idle_ms,
                )
                return info
            exit_code = process.poll()
            if exit_code is not None:
                raise EffectRuntimeStartupError(
                    "TypeScript Effect runtime exited before becoming ready "
                    f"(exit_code={exit_code})",
                    diagnostic_code="runtime_exited_before_ready",
                )
            time.sleep(STARTUP_POLL_SECONDS)
        if process.poll() is None:
            process.terminate()
        raise EffectRuntimeStartupError(
            "TypeScript Effect runtime did not become ready before the startup deadline",
            diagnostic_code="runtime_startup_timeout",
        )
    finally:
        lock.unlink(missing_ok=True)


def effect_runtime_request(
    method: str,
    params: Mapping[str, Any],
    *,
    timeout: float = 5.0,
    retry_safe: bool = True,
) -> dict[str, Any]:
    """Call the managed TS runtime, retrying only idempotent typed effects."""

    requested_idle_ms = _validate_effect_runtime_idle_ms(os.environ)
    fingerprint = _runtime_fingerprint()
    info_path = _runtime_info_path(fingerprint)
    request_id = str(uuid.uuid4())
    last_error: OSError | RuntimeError | None = None
    for attempt in range(2 if retry_safe else 1):
        try:
            info = _read_info(info_path, fingerprint=fingerprint)
            if info is None:
                info = _start_runtime(
                    fingerprint=fingerprint,
                    info_path=info_path,
                    requested_idle_ms=requested_idle_ms,
                )
            else:
                _require_matching_runtime_idle_ms(
                    info,
                    requested_idle_ms=requested_idle_ms,
                )
            return _request_with_info(
                info,
                request_id=request_id,
                method=method,
                params=params,
                timeout=timeout,
            )
        except EffectRuntimeRemoteError:
            raise
        except EffectRuntimeStartupError as exc:
            last_error = exc
            if exc.diagnostic_code == "runtime_idle_ms_conflict":
                raise
            if attempt == 0 and retry_safe:
                info_path.unlink(missing_ok=True)
                continue
            raise
        except (OSError, RuntimeError) as exc:
            last_error = exc
            if attempt == 0 and retry_safe:
                info_path.unlink(missing_ok=True)
                continue
            break
    raise EffectRuntimeStartupError(
        "TypeScript Effect runtime request failed",
        diagnostic_code="runtime_request_failed",
    ) from last_error


def effect_runtime_result(
    method: str,
    params: Mapping[str, Any],
    *,
    timeout: float = 5.0,
    retry_safe: bool = True,
) -> Any:
    return effect_runtime_request(
        method,
        params,
        timeout=timeout,
        retry_safe=retry_safe,
    ).get("result")


def collect_effect_runtime_readiness(*, deep: bool = False) -> dict[str, object]:
    """Report whether the managed TS Effect runtime can serve control-plane work."""

    status, _executable, version = _probe_node()
    ready = status == "ready"
    runtime_state = "unavailable"
    runtime_diagnostic_code: str | None = None
    if ready:
        try:
            requested_idle_ms = _validate_effect_runtime_idle_ms(os.environ)
            fingerprint = _runtime_fingerprint()
            info = _read_info(
                _runtime_info_path(fingerprint),
                fingerprint=fingerprint,
            )
            if info is not None:
                _require_matching_runtime_idle_ms(
                    info,
                    requested_idle_ms=requested_idle_ms,
                )
            runtime_state = (
                "running"
                if info is not None
                else "stopped"
            )
        except (OSError, EffectRuntimeStartupError) as exc:
            ready = False
            status = "package_invalid"
            runtime_diagnostic_code = getattr(
                exc,
                "diagnostic_code",
                "packaged_runtime_source_unreadable",
            )
    runtime_lifecycle: dict[str, object] = {
        "schema_version": "loopx_effect_runtime_lifecycle_v0",
        "management": "on_demand_managed",
        "state": runtime_state,
        "manual_start_required": False,
        "restart_policy": "automatic_on_next_control_plane_request",
        "idle_shutdown": True,
        "diagnostic_code": runtime_diagnostic_code,
    }
    result: dict[str, object] = {
        "schema_version": EFFECT_RUNTIME_READINESS_SCHEMA_VERSION,
        "ready": ready,
        "status": status,
        "required_for": ["control_plane"],
        "default_cli_blocking": True,
        "minimum_node_version": MINIMUM_NODE_VERSION_TEXT,
        "detected_node_version": version,
        "semantic_probe": "not_requested" if not deep else "not_run",
        "runtime_lifecycle": runtime_lifecycle,
        "recommended_action": (
            None
            if ready
            else (
                f"Install Node.js {MINIMUM_NODE_VERSION_TEXT} or newer, then "
                "rerun `loopx doctor --deep`."
                if status in {"missing", "unsupported"}
                else "Repair Node.js on PATH, then rerun `loopx doctor --deep`."
            )
        ),
    }
    if not ready or not deep:
        return result
    try:
        ping = effect_runtime_result("runtime.ping", {})
        identity = effect_runtime_result(
            "settlement.identity",
            {
                "goal_id": "doctor-probe",
                "agent_id": "doctor-probe",
                "todo_id": "doctor-probe",
                "turn_instance_id": "doctor-probe",
            },
        )
    except RuntimeError as exc:
        diagnostic_code = getattr(exc, "diagnostic_code", "semantic_probe_failed")
        return {
            **result,
            "ready": False,
            "status": "probe_failed",
            "semantic_probe": "failed",
            "runtime_lifecycle": {
                **runtime_lifecycle,
                "state": "unavailable",
                "diagnostic_code": diagnostic_code,
            },
            "recommended_action": (
                "Run `loopx doctor --deep` again after any concurrent startup "
                "finishes. If the same diagnostic code remains, reinstall LoopX "
                "and verify Node.js before retrying."
            ),
        }
    if (
        not isinstance(ping, Mapping)
        or ping.get("ready") is not True
        or not isinstance(identity, Mapping)
        or identity.get("effect_id")
        != "doctor-probe:doctor-probe:doctor-probe:doctor-probe"
    ):
        return {
            **result,
            "ready": False,
            "status": "probe_failed",
            "semantic_probe": "failed",
            "runtime_lifecycle": {
                **runtime_lifecycle,
                "state": "unavailable",
                "diagnostic_code": "semantic_probe_shape_mismatch",
            },
            "recommended_action": (
                "Reinstall LoopX and verify the packaged TypeScript runtime with "
                "`loopx doctor --deep`."
            ),
        }
    return {
        **result,
        "semantic_probe": "passed",
        "runtime_lifecycle": {
            **runtime_lifecycle,
            "state": "running",
            "diagnostic_code": None,
        },
    }
