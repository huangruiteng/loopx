from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import subprocess
import threading
import time
from typing import BinaryIO


_PROCESS_IO_CHUNK_BYTES = 64 * 1024
_PROCESS_TERMINATE_GRACE_SECONDS = 1.0


@dataclass(frozen=True)
class CappedProcessResult:
    returncode: int
    stdout: bytes
    failure_kind: str | None = None


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=_PROCESS_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.wait()


def run_capped_process(
    argv: Sequence[str],
    *,
    stdin: bytes,
    timeout_seconds: int,
    output_limit_bytes: int,
    env: Mapping[str, str] | None = None,
) -> CappedProcessResult:
    """Run a provider while bounding both output streams during execution."""

    process = subprocess.Popen(
        list(argv),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=dict(env) if env is not None else None,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    stdout = bytearray()
    stderr = bytearray()
    limit_event = threading.Event()
    limit_lock = threading.Lock()
    limit_kind: str | None = None

    def record_limit(kind: str) -> None:
        nonlocal limit_kind
        with limit_lock:
            if limit_kind is None:
                limit_kind = kind
                limit_event.set()

    def read_stream(
        stream: BinaryIO,
        destination: bytearray,
        *,
        overflow_kind: str,
    ) -> None:
        try:
            while chunk := stream.read(_PROCESS_IO_CHUNK_BYTES):
                remaining = output_limit_bytes + 1 - len(destination)
                if remaining > 0:
                    destination.extend(chunk[:remaining])
                if len(destination) > output_limit_bytes:
                    record_limit(overflow_kind)
                    return
        except (OSError, ValueError):
            return

    def write_stdin() -> None:
        try:
            process.stdin.write(stdin)
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    threads = [
        threading.Thread(
            target=read_stream,
            args=(process.stdout, stdout),
            kwargs={"overflow_kind": "response_too_large"},
            name="loopx-extension-stdout-reader",
            daemon=True,
        ),
        threading.Thread(
            target=read_stream,
            args=(process.stderr, stderr),
            kwargs={"overflow_kind": "stderr_too_large"},
            name="loopx-extension-stderr-reader",
            daemon=True,
        ),
        threading.Thread(
            target=write_stdin,
            name="loopx-extension-stdin-writer",
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    while process.poll() is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            _terminate_process(process)
            break
        if limit_event.wait(timeout=min(0.05, remaining)):
            _terminate_process(process)
            break

    returncode = process.wait()
    for thread in threads:
        thread.join(timeout=_PROCESS_TERMINATE_GRACE_SECONDS)
    for stream in (process.stdout, process.stderr):
        try:
            stream.close()
        except (OSError, ValueError):
            pass
    return CappedProcessResult(
        returncode=returncode,
        stdout=bytes(stdout),
        failure_kind="timeout" if timed_out else limit_kind,
    )
