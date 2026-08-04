from __future__ import annotations

from contextlib import contextmanager
import errno
import importlib
from pathlib import Path
import time
from typing import Any, BinaryIO, Iterator

try:  # pragma: no cover - exercised on POSIX hosts in integration smokes.
    fcntl: Any = importlib.import_module("fcntl")
except ImportError:  # pragma: no cover
    fcntl = None

try:  # pragma: no cover - imported only on Windows hosts.
    msvcrt: Any = importlib.import_module("msvcrt")
except ImportError:  # pragma: no cover
    msvcrt = None


def _prepare_windows_lock(lock_file: BinaryIO) -> None:
    lock_file.seek(0, 2)
    if lock_file.tell() == 0:
        lock_file.write(b"0")
        lock_file.flush()
    lock_file.seek(0)


def _acquire(lock_file: BinaryIO, *, blocking: bool) -> bool:
    if fcntl is not None:
        operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(lock_file.fileno(), operation)
        except BlockingIOError:
            return False
        return True
    if msvcrt is None:
        return True

    _prepare_windows_lock(lock_file)
    while True:
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            if not blocking:
                return False
            time.sleep(0.05)


def _release(lock_file: BinaryIO) -> None:
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    elif msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[Path]:
    """Hold a small sibling lock file for read-modify-write file updates."""

    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        acquired = _acquire(lock_file, blocking=True)
        if not acquired:  # pragma: no cover - blocking acquisition cannot return false.
            raise RuntimeError(f"failed to acquire blocking file lock: {lock_path}")
        try:
            yield lock_path
        finally:
            _release(lock_file)


@contextmanager
def try_exclusive_file_lock(path: Path) -> Iterator[Path | None]:
    """Try to hold a sibling lock file without waiting for another process.

    ``None`` means another process already owns the lock. POSIX uses ``flock``;
    Windows uses the standard-library ``msvcrt`` byte-range lock.
    """

    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if not _acquire(lock_file, blocking=False):
            yield None
            return
        try:
            yield lock_path
        finally:
            _release(lock_file)
