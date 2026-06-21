from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - exercised on POSIX hosts in integration smokes.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[Path]:
    """Hold a small sibling lock file for read-modify-write file updates."""

    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield lock_path
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
