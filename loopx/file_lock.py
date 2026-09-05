from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import importlib
from typing import Any, Iterator, Literal, TextIO, overload
from uuid import uuid4

try:  # pragma: no cover - exercised on POSIX hosts in integration smokes.
    fcntl: Any = importlib.import_module("fcntl")
except ImportError:  # pragma: no cover
    fcntl = None

try:  # pragma: no cover - imported only on Windows hosts.
    msvcrt: Any = importlib.import_module("msvcrt")
except ImportError:  # pragma: no cover
    msvcrt = None


def _prepare_windows_lock(lock_file: TextIO) -> None:
    lock_file.seek(0, 2)
    if lock_file.tell() == 0:
        lock_file.write("0")
        lock_file.flush()
    lock_file.seek(0)


def _try_acquire_kernel_lock(lock_file: TextIO) -> bool:
    if fcntl is not None:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if not _lock_is_busy(exc):
                raise
            return False
        return True
    if msvcrt is None:
        raise RuntimeError("no supported file-lock backend is available")

    _prepare_windows_lock(lock_file)
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        if not _lock_is_busy(exc):
            raise
        return False
    return True


def _release_kernel_lock(lock_file: TextIO) -> None:
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    elif msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


LOCK_ACQUIRE_TIMEOUT_ERROR_CODE = "lock_acquire_timeout"
LOCK_HOLDER_SCHEMA_VERSION = "file_lock_holder_v0"
LOCK_INCIDENT_SCHEMA_VERSION = "file_lock_incident_v0"
_SAFE_LABEL_PATTERN = re.compile(r"[^A-Za-z0-9._:@-]+")


class LockAcquisitionPolicy(str, Enum):
    MUTATION = "mutation"
    MONITOR = "monitor"
    SINGLE_FLIGHT = "single_flight"


@dataclass(frozen=True, slots=True)
class LockPolicy:
    timeout_seconds: float
    poll_interval_seconds: float
    retry_mode: str


LOCK_POLICIES = {
    LockAcquisitionPolicy.MUTATION: LockPolicy(
        timeout_seconds=5.0,
        poll_interval_seconds=0.05,
        retry_mode="manual_after_holder_inspection",
    ),
    LockAcquisitionPolicy.MONITOR: LockPolicy(
        timeout_seconds=1.0,
        poll_interval_seconds=0.10,
        retry_mode="next_scheduled_poll_after_holder_inspection",
    ),
    LockAcquisitionPolicy.SINGLE_FLIGHT: LockPolicy(
        timeout_seconds=0.0,
        poll_interval_seconds=0.0,
        retry_mode="skip_duplicate_attempt",
    ),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_label(value: object, *, fallback: str) -> str:
    compact = _SAFE_LABEL_PATTERN.sub("_", str(value or "").strip()).strip("._-")
    return compact[:128] or fallback


def _policy(value: LockAcquisitionPolicy | str) -> LockAcquisitionPolicy:
    if isinstance(value, LockAcquisitionPolicy):
        return value
    return LockAcquisitionPolicy(str(value))


def _lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")


def lock_holder_path(path: Path) -> Path:
    lock_path = _lock_path(path)
    if os.name == "nt":
        return lock_path.with_name(f"{lock_path.name}.holder.json")
    return lock_path


def lock_incident_path(path: Path) -> Path:
    lock_path = _lock_path(path)
    return lock_path.with_name(f"{lock_path.name}.incidents.jsonl")


def _lock_id(path: Path) -> str:
    resolved = str(path.expanduser().resolve(strict=False)).encode("utf-8")
    return hashlib.sha256(resolved).hexdigest()[:16]


def _identity(
    *,
    agent_id: str | None,
    operation: str | None,
    policy: LockAcquisitionPolicy,
) -> dict[str, object]:
    return {
        "pid": os.getpid(),
        "agent_id": _safe_label(
            agent_id or os.environ.get("LOOPX_AGENT_ID"),
            fallback="unknown",
        ),
        "operation": _safe_label(operation or policy.value, fallback=policy.value),
    }


def _holder_record(
    path: Path,
    *,
    agent_id: str | None,
    operation: str | None,
    policy: LockAcquisitionPolicy,
) -> dict[str, object]:
    return {
        "schema_version": LOCK_HOLDER_SCHEMA_VERSION,
        "lock_id": _lock_id(path),
        "policy": policy.value,
        **_identity(agent_id=agent_id, operation=operation, policy=policy),
        "acquired_at": _utc_now_iso(),
    }


def _write_holder_record(lock_file: TextIO, record: dict[str, object]) -> None:
    lock_file.seek(0)
    lock_file.truncate()
    json.dump(
        record, lock_file, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    lock_file.write("\n")
    lock_file.flush()
    os.fsync(lock_file.fileno())


def _write_holder_sidecar(holder_path: Path, record: dict[str, object]) -> None:
    holder_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{holder_path.name}.",
        suffix=".tmp",
        dir=holder_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        try:
            holder_file = os.fdopen(descriptor, "w", encoding="utf-8")
        except BaseException:
            os.close(descriptor)
            raise
        with holder_file:
            json.dump(
                record,
                holder_file,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            holder_file.write("\n")
            holder_file.flush()
            os.fsync(holder_file.fileno())
        os.replace(temporary_path, holder_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _persist_holder_record(
    lock_file: TextIO,
    *,
    lock_path: Path,
    holder_path: Path,
    record: dict[str, object],
) -> None:
    if holder_path == lock_path:
        _write_holder_record(lock_file, record)
        return
    _write_holder_sidecar(holder_path, record)


def _mark_released(
    lock_file: TextIO,
    *,
    lock_path: Path,
    holder_path: Path,
    record: dict[str, object],
) -> None:
    released = {**record, "released_at": _utc_now_iso()}
    try:
        _persist_holder_record(
            lock_file,
            lock_path=lock_path,
            holder_path=holder_path,
            record=released,
        )
    except OSError:
        # Releasing the kernel lock is more important than refreshing advisory
        # metadata; a future holder overwrites the complete record.
        pass


def _read_holder_record(lock_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = {
        "schema_version",
        "lock_id",
        "policy",
        "pid",
        "agent_id",
        "operation",
        "acquired_at",
        "released_at",
    }
    return {key: payload[key] for key in allowed if key in payload}


def _operator_action(
    holder: dict[str, object], *, retry_mode: str
) -> dict[str, object]:
    return {
        "required": True,
        "action": "inspect_lock_holder",
        "holder_pid": holder.get("pid"),
        "retry_mode": retry_mode,
        "steps": [
            "Inspect the recorded holder PID and operation.",
            "Confirm the process is stalled before terminating it.",
            "Retry according to retry_mode after the holder exits.",
            "Do not delete the lock file; the kernel lock is authoritative.",
        ],
    }


def _append_incident(path: Path, record: dict[str, object]) -> bool:
    incident_path = lock_incident_path(path)
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    try:
        descriptor = _open_verified_incident_descriptor(incident_path)
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
            _assert_live_incident_path_matches_descriptor(incident_path, descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        return False
    return True


class LockAcquireTimeoutError(TimeoutError):
    code = LOCK_ACQUIRE_TIMEOUT_ERROR_CODE

    def __init__(
        self,
        *,
        incident: dict[str, object],
        incident_recorded: bool,
        incident_channel: str,
    ) -> None:
        self.incident = incident
        self.incident_recorded = incident_recorded
        self.incident_channel = incident_channel
        raw_holder = incident.get("holder")
        holder: dict[str, object] = raw_holder if isinstance(raw_holder, dict) else {}
        super().__init__(
            "file lock acquisition timed out"
            + (
                f" while waiting for holder pid {holder.get('pid')}"
                if holder.get("pid")
                else ""
            )
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "error_code": self.code,
            "lock_timeout": self.incident,
            "incident_recorded": self.incident_recorded,
            "incident_channel": self.incident_channel,
            "operator_action": self.incident["operator_action"],
        }


def lock_timeout_error_fields(error: BaseException) -> dict[str, object]:
    if isinstance(error, LockAcquireTimeoutError):
        return error.to_payload()
    return {}


def _timeout_error(
    path: Path,
    *,
    policy: LockAcquisitionPolicy,
    timeout_seconds: float,
    waited_seconds: float,
    started_at: str,
    agent_id: str | None,
    operation: str | None,
) -> LockAcquireTimeoutError:
    holder = _read_holder_record(lock_holder_path(path))
    waiter = {
        **_identity(agent_id=agent_id, operation=operation, policy=policy),
        "started_at": started_at,
        "timeout_seconds": round(timeout_seconds, 3),
        "waited_seconds": round(waited_seconds, 3),
    }
    action = _operator_action(holder, retry_mode=LOCK_POLICIES[policy].retry_mode)
    incident: dict[str, object] = {
        "schema_version": LOCK_INCIDENT_SCHEMA_VERSION,
        "error_code": LOCK_ACQUIRE_TIMEOUT_ERROR_CODE,
        "recorded_at": _utc_now_iso(),
        "lock_id": _lock_id(path),
        "policy": policy.value,
        "holder": holder,
        "waiter": waiter,
        "operator_action": action,
    }
    recorded = _append_incident(path, incident)
    return LockAcquireTimeoutError(
        incident=incident,
        incident_recorded=recorded,
        incident_channel=lock_incident_path(path).name,
    )


def _lock_is_busy(error: OSError) -> bool:
    return isinstance(error, BlockingIOError) or error.errno in {
        errno.EACCES,
        errno.EAGAIN,
    }


def _same_open_lock_identity(
    path_info: os.stat_result, descriptor_info: os.stat_result
) -> bool:
    path_identity = (
        int(getattr(path_info, "st_dev", 0)),
        int(getattr(path_info, "st_ino", 0)),
    )
    descriptor_identity = (
        int(getattr(descriptor_info, "st_dev", 0)),
        int(getattr(descriptor_info, "st_ino", 0)),
    )
    if path_identity == (0, 0) or descriptor_identity == (0, 0):
        return True
    return path_identity == descriptor_identity


def _open_verified_regular_descriptor(
    path: Path,
    *,
    flags: int,
    mode: int,
    symlink_error: str,
    nonregular_error: str,
    hardlink_error: str,
    replaced_error: str,
) -> int:
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    if os.name == "posix":
        flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as error:
        try:
            current = path.lstat()
        except OSError:
            raise error
        if stat.S_ISLNK(current.st_mode):
            raise OSError(symlink_error) from error
        raise
    try:
        descriptor_info = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_info.st_mode):
            raise OSError(nonregular_error)
        if descriptor_info.st_nlink != 1:
            raise OSError(hardlink_error)
        try:
            current = path.lstat()
        except OSError as error:
            raise OSError(replaced_error) from error
        if stat.S_ISLNK(current.st_mode):
            raise OSError(symlink_error)
        if not stat.S_ISREG(current.st_mode):
            raise OSError(nonregular_error)
        if current.st_nlink != 1:
            raise OSError(hardlink_error)
        if not _same_open_lock_identity(current, descriptor_info):
            raise OSError(replaced_error)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_verified_lock_descriptor(lock_path: Path) -> int:
    return _open_verified_regular_descriptor(
        lock_path,
        flags=os.O_CREAT | os.O_RDWR,
        mode=0o600,
        symlink_error="lock_file_symlink_rejected",
        nonregular_error="lock_file_not_regular",
        hardlink_error="lock_file_hardlink_rejected",
        replaced_error="lock_file_replaced_during_open",
    )


def _open_verified_incident_descriptor(incident_path: Path) -> int:
    return _open_verified_regular_descriptor(
        incident_path,
        flags=os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        mode=0o600,
        symlink_error="lock_incident_symlink_rejected",
        nonregular_error="lock_incident_not_regular",
        hardlink_error="lock_incident_hardlink_rejected",
        replaced_error="lock_incident_replaced_during_open",
    )


def _assert_live_lock_path_matches_descriptor(lock_path: Path, descriptor: int) -> None:
    descriptor_info = os.fstat(descriptor)
    if not stat.S_ISREG(descriptor_info.st_mode):
        raise OSError("lock_file_not_regular")
    if descriptor_info.st_nlink != 1:
        raise OSError("lock_file_hardlink_rejected")
    try:
        current = lock_path.lstat()
    except OSError as error:
        raise OSError("lock_file_replaced_during_lock") from error
    if stat.S_ISLNK(current.st_mode):
        raise OSError("lock_file_symlink_rejected")
    if not stat.S_ISREG(current.st_mode):
        raise OSError("lock_file_not_regular")
    if current.st_nlink != 1:
        raise OSError("lock_file_hardlink_rejected")
    if not _same_open_lock_identity(current, descriptor_info):
        raise OSError("lock_file_replaced_during_lock")


def _assert_live_incident_path_matches_descriptor(
    incident_path: Path, descriptor: int
) -> None:
    descriptor_info = os.fstat(descriptor)
    if not stat.S_ISREG(descriptor_info.st_mode):
        raise OSError("lock_incident_not_regular")
    if descriptor_info.st_nlink != 1:
        raise OSError("lock_incident_hardlink_rejected")
    try:
        current = incident_path.lstat()
    except OSError as error:
        raise OSError("lock_incident_replaced_during_open") from error
    if stat.S_ISLNK(current.st_mode):
        raise OSError("lock_incident_symlink_rejected")
    if not stat.S_ISREG(current.st_mode):
        raise OSError("lock_incident_not_regular")
    if current.st_nlink != 1:
        raise OSError("lock_incident_hardlink_rejected")
    if not _same_open_lock_identity(current, descriptor_info):
        raise OSError("lock_incident_replaced_during_open")


@dataclass(frozen=True, slots=True)
class ExclusiveFileLockLease:
    """A held kernel lock whose live pathname identity can be revalidated.

    Most callers only need the context-manager boundary and continue to receive
    a ``Path`` from :func:`exclusive_file_lock`. Multi-step transactions can
    request this lease and call :meth:`check` immediately before and after each
    mutation so a replaced lock pathname cannot silently admit another writer.
    """

    path: Path
    _descriptor: int

    def check(self) -> None:
        _assert_live_lock_path_matches_descriptor(self.path, self._descriptor)

    def exists(self) -> bool:
        return self.path.exists()


@overload
@contextmanager
def exclusive_file_lock(
    path: Path,
    *,
    policy: LockAcquisitionPolicy | str = LockAcquisitionPolicy.MUTATION,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    agent_id: str | None = None,
    operation: str | None = None,
    expose_lease: Literal[False] = False,
) -> Iterator[Path]: ...


@overload
@contextmanager
def exclusive_file_lock(
    path: Path,
    *,
    policy: LockAcquisitionPolicy | str = LockAcquisitionPolicy.MUTATION,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    agent_id: str | None = None,
    operation: str | None = None,
    expose_lease: Literal[True],
) -> Iterator[ExclusiveFileLockLease]: ...


@contextmanager
def exclusive_file_lock(
    path: Path,
    *,
    policy: LockAcquisitionPolicy | str = LockAcquisitionPolicy.MUTATION,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    agent_id: str | None = None,
    operation: str | None = None,
    expose_lease: bool = False,
) -> Iterator[Path | ExclusiveFileLockLease]:
    """Hold a sibling lock file with a finite cross-platform deadline."""

    selected_policy = _policy(policy)
    defaults = LOCK_POLICIES[selected_policy]
    timeout = (
        defaults.timeout_seconds
        if timeout_seconds is None
        else max(0.0, timeout_seconds)
    )
    poll_interval = (
        defaults.poll_interval_seconds
        if poll_interval_seconds is None
        else max(0.001, poll_interval_seconds)
    )
    lock_path = _lock_path(path)
    holder_path = lock_holder_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = _open_verified_lock_descriptor(lock_path)
    try:
        lock_file = os.fdopen(descriptor, "r+", encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise
    with lock_file:
        started = time.monotonic()
        started_at = _utc_now_iso()
        deadline = started + timeout
        while not _try_acquire_kernel_lock(lock_file):
            now = time.monotonic()
            if now >= deadline:
                raise _timeout_error(
                    path,
                    policy=selected_policy,
                    timeout_seconds=timeout,
                    waited_seconds=now - started,
                    started_at=started_at,
                    agent_id=agent_id,
                    operation=operation,
                ) from None
            time.sleep(min(poll_interval, max(0.0, deadline - now)))
        _assert_live_lock_path_matches_descriptor(lock_path, lock_file.fileno())
        record = _holder_record(
            path,
            agent_id=agent_id,
            operation=operation,
            policy=selected_policy,
        )
        try:
            _persist_holder_record(
                lock_file,
                lock_path=lock_path,
                holder_path=holder_path,
                record=record,
            )
            lease = ExclusiveFileLockLease(
                path=lock_path,
                _descriptor=lock_file.fileno(),
            )
            try:
                yield lease if expose_lease else lock_path
            finally:
                lease.check()
        finally:
            _mark_released(
                lock_file,
                lock_path=lock_path,
                holder_path=holder_path,
                record=record,
            )
            _release_kernel_lock(lock_file)


@contextmanager
def try_exclusive_file_lock(
    path: Path,
    *,
    agent_id: str | None = None,
    operation: str | None = None,
) -> Iterator[Path | None]:
    """Try once to hold a sibling lock file for single-flight work.

    ``None`` means another process already owns the lock. POSIX uses ``flock``;
    Windows uses the standard-library ``msvcrt`` byte-range lock.
    """

    lock_path = _lock_path(path)
    holder_path = lock_holder_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = _open_verified_lock_descriptor(lock_path)
    try:
        lock_file = os.fdopen(descriptor, "r+", encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise
    with lock_file:
        if not _try_acquire_kernel_lock(lock_file):
            yield None
            return
        _assert_live_lock_path_matches_descriptor(lock_path, lock_file.fileno())
        record = _holder_record(
            path,
            agent_id=agent_id,
            operation=operation,
            policy=LockAcquisitionPolicy.SINGLE_FLIGHT,
        )
        try:
            _persist_holder_record(
                lock_file,
                lock_path=lock_path,
                holder_path=holder_path,
                record=record,
            )
            try:
                yield lock_path
            finally:
                _assert_live_lock_path_matches_descriptor(lock_path, lock_file.fileno())
        finally:
            _mark_released(
                lock_file,
                lock_path=lock_path,
                holder_path=holder_path,
                record=record,
            )
            _release_kernel_lock(lock_file)


EFFECT_MUTATION_LOCK_SUFFIX = ".ts-effect.lock"
EFFECT_MUTATION_INVALID_STALE_SECONDS = 10.0
EFFECT_MUTATION_TOKEN_MAX_LENGTH = 256
_EFFECT_MUTATION_INVALID_CLAIM_TOKEN = "__invalid_lock_reclaim__"


def _effect_mutation_lock_path(path: Path) -> Path:
    return Path(f"{path}{EFFECT_MUTATION_LOCK_SUFFIX}")


def _effect_mutation_claim_path(path: Path, token: str) -> Path:
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return path.with_name(f"{path.name}.claim.{token_digest}")


def process_is_alive(pid: object) -> bool:
    """Probe a process without sending signals or console control events."""

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        # Windows signal 0 is CTRL_C_EVENT, not the side-effect-free POSIX
        # existence probe provided by kill(pid, 0).
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _windows_process_is_alive(pid: int) -> bool:
    """Probe a Windows process without sending a console control event."""

    import ctypes
    from ctypes import wintypes

    synchronize = 0x00100000
    wait_timeout = 0x00000102
    error_access_denied = 5
    kernel32 = getattr(ctypes, "WinDLL")("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(synchronize, False, pid)
    if not handle:
        return bool(getattr(ctypes, "get_last_error")() == error_access_denied)
    try:
        return bool(wait_for_single_object(handle, 0) == wait_timeout)
    finally:
        close_handle(handle)


def _effect_mutation_process_is_alive(pid: object) -> bool:
    return process_is_alive(pid)


def _read_effect_mutation_owner(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    token = payload.get("token")
    if (
        isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid <= 0
        or not isinstance(token, str)
        or not token
        or len(token) > EFFECT_MUTATION_TOKEN_MAX_LENGTH
        or not token.strip()
    ):
        return None
    return {"pid": pid, "token": token}


@dataclass(frozen=True)
class _EffectMutationClaim:
    path: Path
    token: str
    identity: tuple[int, int, int, int]


def _effect_file_identity_from_stat(info: os.stat_result) -> tuple[int, int, int, int]:
    """Capture a replacement-resistant identity on POSIX and Windows."""

    return (
        int(getattr(info, "st_dev", 0)),
        int(getattr(info, "st_ino", 0)),
        int(getattr(info, "st_birthtime_ns", 0)),
        int(getattr(info, "st_ctime_ns", 0)),
    )


def _effect_file_identity_from_fd(descriptor: int) -> tuple[int, int, int, int]:
    return _effect_file_identity_from_stat(os.fstat(descriptor))


def _effect_file_identity(path: Path) -> tuple[int, int, int, int] | None:
    try:
        return _effect_file_identity_from_stat(path.stat())
    except OSError:
        return None


def _same_effect_file_identity(
    left: tuple[int, int, int, int] | None,
    right: tuple[int, int, int, int] | None,
) -> bool:
    if left is None or right is None:
        return False
    left_has_device_identity = left[:2] != (0, 0)
    right_has_device_identity = right[:2] != (0, 0)
    if left_has_device_identity != right_has_device_identity:
        return False
    if left_has_device_identity:
        if left[:2] != right[:2]:
            return False
        # A birth marker protects against rapid inode reuse when both stat
        # calls expose it. On POSIX/macOS it may be absent; in that case the
        # stable device/inode pair remains the best available identity and is
        # not invalidated by ordinary content writes (which change ctime).
        if left[2] or right[2]:
            return left[2] != 0 and right[2] != 0 and left[2] == right[2]
        return True
    # Without device/inode identity, prefer a birth marker, then creation time.
    # Two all-zero identities are ambiguous and must fail closed.
    if left[2] or right[2]:
        return left[2] != 0 and right[2] != 0 and left[2] == right[2]
    # Some Windows filesystems expose no device/inode or birth marker.  ctime
    # is the last available creation-like marker; two zero identities are not
    # safe to compare.
    return left[3] != 0 and right[3] != 0 and left[3] == right[3]


def _remove_created_effect_file(
    path: Path,
    identity: tuple[int, int, int, int] | None,
) -> None:
    if identity is None:
        return
    try:
        if _same_effect_file_identity(identity, _effect_file_identity(path)):
            path.unlink(missing_ok=True)
    except OSError:
        # The path was already retired or replaced; never remove an unknown file.
        pass


def _remove_dead_effect_mutation_claim(path: Path) -> bool:
    identity = _effect_file_identity(path)
    if identity is None:
        return False
    owner = _read_effect_mutation_owner(path)
    if owner is not None and _effect_mutation_process_is_alive(owner.get("pid")):
        return False
    if owner is None:
        try:
            age_seconds = time.time() - path.stat().st_mtime
        except OSError:
            return False
        if age_seconds < EFFECT_MUTATION_INVALID_STALE_SECONDS:
            return False
    if not _same_effect_file_identity(identity, _effect_file_identity(path)):
        return False
    _remove_created_effect_file(path, identity)
    return _effect_file_identity(path) is None


def _claim_effect_mutation_lock(
    path: Path,
    token: str,
) -> _EffectMutationClaim | None:
    if not token or len(token) > EFFECT_MUTATION_TOKEN_MAX_LENGTH or not token.strip():
        return None
    claim_path = _effect_mutation_claim_path(path, token)
    for _attempt in range(2):
        try:
            descriptor = os.open(
                claim_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if not _remove_dead_effect_mutation_claim(claim_path):
                return None
            continue
        # Capture identity before publication so a write/fsync failure can
        # still retire the claim without relying on a later path read.
        identity: tuple[int, int, int, int] | None = _effect_file_identity_from_fd(
            descriptor
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as claim_file:
                json.dump(
                    {"pid": os.getpid(), "token": token},
                    claim_file,
                    separators=(",", ":"),
                )
                claim_file.flush()
                os.fsync(claim_file.fileno())
        except BaseException:
            _remove_created_effect_file(claim_path, identity)
            raise
        if identity is None:
            return None
        return _EffectMutationClaim(claim_path, token, identity)
    return None


def _release_effect_mutation_claim(
    claim: _EffectMutationClaim | Path,
    token: str | None = None,
) -> None:
    expected_token: str | None
    identity: tuple[int, int, int, int] | None
    if isinstance(claim, _EffectMutationClaim):
        path = claim.path
        expected_token = claim.token
        identity = claim.identity
    else:
        path = claim
        expected_token = token
        identity = _effect_file_identity(path)
    if not expected_token:
        return
    owner = _read_effect_mutation_owner(path)
    if isinstance(claim, _EffectMutationClaim):
        if (
            owner is None
            or owner.get("pid") != os.getpid()
            or owner.get("token") != expected_token
        ):
            # The pathname may have been corrupted or replaced after this
            # caller created the claim.  Its captured identity still permits
            # removing only its own inode, preventing claim leaks without
            # touching a later claimant.
            _remove_created_effect_file(path, identity)
            return
    elif (
        owner is None
        or owner.get("pid") != os.getpid()
        or owner.get("token") != expected_token
    ):
        return
    _remove_created_effect_file(path, identity)


def _reclaim_stale_effect_mutation_lock(path: Path) -> None:
    identity = _effect_file_identity(path)
    if identity is None:
        return
    owner = _read_effect_mutation_owner(path)
    if owner is not None and _effect_mutation_process_is_alive(owner.get("pid")):
        return
    if owner is None:
        try:
            age_seconds = time.time() - path.stat().st_mtime
        except OSError:
            return
        if age_seconds < EFFECT_MUTATION_INVALID_STALE_SECONDS:
            return
    claim_token = (
        str(owner["token"])
        if owner is not None
        else _EFFECT_MUTATION_INVALID_CLAIM_TOKEN
    )
    claim = _claim_effect_mutation_lock(path, claim_token)
    if claim is None:
        return
    stale_path = path.with_name(f"{path.name}.stale.{uuid4()}")
    try:
        current = _read_effect_mutation_owner(path)
        if owner is not None and (
            current is None or current.get("token") != owner.get("token")
        ):
            return
        if current is not None and _effect_mutation_process_is_alive(
            current.get("pid")
        ):
            return
        if current is None:
            try:
                if (
                    time.time() - path.stat().st_mtime
                    < EFFECT_MUTATION_INVALID_STALE_SECONDS
                ):
                    return
            except OSError:
                return
        if not _same_effect_file_identity(identity, _effect_file_identity(path)):
            return
        path.replace(stale_path)
    except FileNotFoundError:
        return
    finally:
        if claim is not None:
            _release_effect_mutation_claim(claim)
    stale_path.unlink(missing_ok=True)


def _release_effect_mutation_lock(
    path: Path,
    token: str,
    *,
    suppress_errors: bool = False,
) -> bool:
    claim: _EffectMutationClaim | None = None
    try:
        lock_identity = _effect_file_identity(path)
        if lock_identity is None:
            return False
        owner = _read_effect_mutation_owner(path)
        if owner is None or owner.get("token") != token:
            _release_effect_mutation_claim(
                _effect_mutation_claim_path(path, token),
                token,
            )
            return False
        claim = _claim_effect_mutation_lock(path, token)
        if claim is None:
            return False
        retired_path = path.with_name(f"{path.name}.released.{uuid4()}")
        try:
            current = _read_effect_mutation_owner(path)
            if current is None or current.get("token") != token:
                return False
            if not _same_effect_file_identity(
                lock_identity, _effect_file_identity(path)
            ):
                return False
            try:
                path.replace(retired_path)
            except FileNotFoundError:
                return False
            try:
                retired_path.unlink(missing_ok=True)
            except OSError:
                pass
            return True
        finally:
            if claim is not None:
                _release_effect_mutation_claim(claim)
            try:
                retired_path.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        if suppress_errors:
            return False
        raise
    finally:
        if claim is not None:
            _release_effect_mutation_claim(claim)


def release_cross_runtime_mutation_lock(path: Path, *, token: str) -> bool:
    """Safely abandon one token-owned TypeScript mutation lock.

    This recovery path is for a caller that still owns a long-lived lock but
    lost the managed-runtime response needed to close it. The token claim and
    file-identity checks make the operation race safely with an in-flight
    native closer: if that closer already owns the claim, this call returns
    ``False`` and leaves the lock untouched.
    """

    return _release_effect_mutation_lock(
        _effect_mutation_lock_path(path),
        token,
        suppress_errors=True,
    )


@contextmanager
def exclusive_cross_runtime_file_lock(
    path: Path,
    *,
    policy: LockAcquisitionPolicy | str = LockAcquisitionPolicy.MUTATION,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    agent_id: str | None = None,
    operation: str | None = None,
) -> Iterator[Path]:
    """Hold the TypeScript mutation lock, then the existing Python lock.

    This is a bounded migration lock for state whose writers span both
    runtimes. TypeScript coordinates through exclusive creation of
    ``<target>.ts-effect.lock``; Python keeps its kernel lock underneath so
    existing diagnostics and Python-to-Python exclusion remain unchanged.
    """

    selected_policy = _policy(policy)
    defaults = LOCK_POLICIES[selected_policy]
    timeout = (
        defaults.timeout_seconds
        if timeout_seconds is None
        else max(0.0, timeout_seconds)
    )
    poll_interval = (
        defaults.poll_interval_seconds
        if poll_interval_seconds is None
        else max(0.001, poll_interval_seconds)
    )
    effect_lock_path = _effect_mutation_lock_path(path)
    effect_lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = str(uuid4())
    started = time.monotonic()
    started_at = _utc_now_iso()
    deadline = started + timeout
    while True:
        try:
            descriptor = os.open(
                effect_lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            _reclaim_stale_effect_mutation_lock(effect_lock_path)
            now = time.monotonic()
            if now >= deadline:
                raise _timeout_error(
                    path,
                    policy=selected_policy,
                    timeout_seconds=timeout,
                    waited_seconds=now - started,
                    started_at=started_at,
                    agent_id=agent_id,
                    operation=operation,
                ) from None
            time.sleep(min(poll_interval, max(0.0, deadline - now)))
            continue
        identity = _effect_file_identity_from_fd(descriptor)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                json.dump(
                    {"pid": os.getpid(), "token": token},
                    lock_file,
                    separators=(",", ":"),
                )
                lock_file.flush()
                os.fsync(lock_file.fileno())
        except BaseException:
            _remove_created_effect_file(effect_lock_path, identity)
            raise
        break

    try:
        with exclusive_file_lock(
            path,
            policy=selected_policy,
            timeout_seconds=timeout,
            poll_interval_seconds=poll_interval,
            agent_id=agent_id,
            operation=operation,
        ) as lock_path:
            yield lock_path
    finally:
        _release_effect_mutation_lock(
            effect_lock_path,
            token,
            # Lock cleanup is secondary to the durable body result.  A cleanup
            # failure must not replace either a successful result or its
            # original exception; stale-owner recovery handles a later retry.
            suppress_errors=True,
        )
