from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
import signal
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


def _wait_for_process(process: subprocess.Popen[bytes], timeout: float) -> bool:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return True


def _terminate_posix_process_group(process: subprocess.Popen[bytes]) -> None:
    process_group_id = process.pid
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    # Give every group member the full grace window before escalation. On
    # macOS, signaling a group whose leader is an unreaped zombie can fail with
    # EPERM, so reap an exited leader only after that window has elapsed.
    time.sleep(_PROCESS_TERMINATE_GRACE_SECONDS)
    process.poll()
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.returncode is None:
        process.wait()


def _terminate_windows_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if _wait_for_process(process, _PROCESS_TERMINATE_GRACE_SECONDS):
        return
    subprocess.run(
        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    process.wait()


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        _terminate_posix_process_group(process)
        return
    if os.name == "nt":  # pragma: no cover - exercised on Windows hosts.
        _terminate_windows_process_tree(process)
        return
    if process.poll() is not None:  # pragma: no cover - unsupported platform fallback.
        return
    process.terminate()
    if not _wait_for_process(process, _PROCESS_TERMINATE_GRACE_SECONDS):
        process.kill()
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

    process_options: dict[str, object] = {}
    if os.name == "posix":
        process_options["start_new_session"] = True
    elif os.name == "nt":  # pragma: no cover - exercised on Windows hosts.
        process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        list(argv),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=dict(env) if env is not None else None,
        **process_options,
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
            _terminate_process_tree(process)
            break
        if limit_event.wait(timeout=min(0.05, remaining)):
            _terminate_process_tree(process)
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
