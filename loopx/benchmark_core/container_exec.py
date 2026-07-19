"""Container command completion markers shared by benchmark runners."""

from __future__ import annotations

import asyncio
import contextlib
import re
import shlex
import tempfile
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any


_EXIT_STATUS_PATTERN = re.compile(r"^[0-9]{1,3}$")


def wrap_container_command_with_exit_status(command: str, status_path: str) -> str:
    """Run *command* in a subshell and atomically leave its exit status behind."""

    parent = str(PurePosixPath(status_path).parent)
    return (
        f"mkdir -p {shlex.quote(parent)} && {{ "
        f"( {command} ); loopx_command_rc=$?; "
        f"printf '%s\\n' \"$loopx_command_rc\" > {shlex.quote(status_path)}; "
        'exit "$loopx_command_rc"; }'
    )


def parse_container_exit_status(payload: bytes | str | None) -> int | None:
    """Return a valid POSIX shell exit status from a completion marker."""

    if isinstance(payload, bytes):
        try:
            text = payload.decode("ascii")
        except UnicodeDecodeError:
            return None
    elif isinstance(payload, str):
        text = payload
    else:
        return None
    text = text.strip()
    if not _EXIT_STATUS_PATTERN.fullmatch(text):
        return None
    value = int(text)
    return value if 0 <= value <= 255 else None


async def read_container_file_via_compose_copy(
    compose_fn: Callable[..., Awaitable[Any]],
    container_path: str,
    *,
    service: str,
    timeout_sec: float,
) -> bytes | None:
    """Copy a container file to the host when exec stdout is unreliable."""

    with tempfile.TemporaryDirectory(prefix="loopx-container-file-") as tmp_dir:
        destination = Path(tmp_dir) / "payload"
        try:
            result = await compose_fn(
                ["cp", f"{service}:{container_path}", str(destination)],
                check=False,
                timeout_sec=max(1, min(10, int(timeout_sec))),
            )
        except (OSError, RuntimeError, TimeoutError):
            return None
        if getattr(result, "return_code", 1) != 0:
            return None
        try:
            return destination.read_bytes()
        except OSError:
            return None


async def run_container_command_with_exit_status(
    exec_fn: Callable[..., Awaitable[Any]],
    command: str,
    *,
    timeout_sec: float,
    exec_args: tuple[Any, ...] = (),
    exec_kwargs: Mapping[str, Any] | None = None,
    poll_interval_sec: float = 0.5,
    status_reader_fn: Callable[[str, str, float], Awaitable[bytes | str | None]]
    | None = None,
) -> Any:
    """Run a container command and wait for its side-channel completion marker."""

    status_path = f"/tmp/loopx-benchmark-exec-status/{uuid.uuid4().hex}.status"
    kwargs = dict(exec_kwargs or {})
    kwargs["timeout_sec"] = timeout_sec
    service = kwargs.get("service", "main")
    deadline = time.monotonic() + timeout_sec
    try:
        result = await exec_fn(
            wrap_container_command_with_exit_status(command, status_path),
            *exec_args,
            **kwargs,
        )
        captured_exit_code = None
        while captured_exit_code is None:
            remaining = deadline - time.monotonic()
            if status_reader_fn is not None:
                payload = await status_reader_fn(status_path, service, remaining)
            else:
                probe = await exec_fn(
                    f"cat {shlex.quote(status_path)} 2>/dev/null",
                    timeout_sec=max(1.0, min(10.0, max(remaining, 1.0))),
                    user="root",
                    service=service,
                )
                payload = getattr(probe, "stdout", None)
            captured_exit_code = parse_container_exit_status(payload)
            if captured_exit_code is None:
                if remaining <= 0:
                    raise asyncio.TimeoutError("container completion marker timed out")
                await asyncio.sleep(min(poll_interval_sec, remaining))
        if hasattr(result, "model_copy"):
            return result.model_copy(update={"return_code": captured_exit_code})
        setattr(result, "return_code", captured_exit_code)
        return result
    finally:
        with contextlib.suppress(Exception):
            await exec_fn(
                f"rm -f {shlex.quote(status_path)}",
                timeout_sec=10,
                user="root",
                service=service,
            )


async def run_container_command_with_output_capture(
    exec_fn: Callable[..., Awaitable[Any]],
    command: str,
    *,
    timeout_sec: float,
    exec_args: tuple[Any, ...] = (),
    exec_kwargs: Mapping[str, Any] | None = None,
    poll_interval_sec: float = 0.5,
    file_reader_fn: Callable[[str, str, float], Awaitable[bytes | str | None]],
) -> Any:
    """Run a command when attached container exec output is untrustworthy.

    Some Docker client/daemon combinations execute ``compose exec`` but return
    empty output and status 0 immediately. Capture all three result channels in
    container files, then read them through the compose copy path.
    """

    capture_dir = f"/tmp/loopx-benchmark-exec-capture/{uuid.uuid4().hex}"
    stdout_path = f"{capture_dir}/stdout"
    stderr_path = f"{capture_dir}/stderr"
    status_path = f"{capture_dir}/status"
    kwargs = dict(exec_kwargs or {})
    kwargs["timeout_sec"] = timeout_sec
    service = kwargs.get("service", "main")
    deadline = time.monotonic() + timeout_sec
    bounded_command = (
        f"timeout {shlex.quote(str(max(1.0, timeout_sec)))} "
        f"sh -c {shlex.quote(command)}"
    )
    captured_command = (
        f"{bounded_command} > {shlex.quote(stdout_path)} "
        f"2> {shlex.quote(stderr_path)}"
    )
    try:
        result = await exec_fn(
            wrap_container_command_with_exit_status(
                captured_command,
                status_path,
            ),
            *exec_args,
            **kwargs,
        )
        captured_exit_code = None
        while captured_exit_code is None:
            remaining = deadline - time.monotonic()
            payload = await file_reader_fn(status_path, service, remaining)
            captured_exit_code = parse_container_exit_status(payload)
            if captured_exit_code is None:
                if remaining <= 0:
                    raise asyncio.TimeoutError(
                        "container output capture completion marker timed out"
                    )
                await asyncio.sleep(min(poll_interval_sec, remaining))

        remaining = max(1.0, deadline - time.monotonic())
        stdout = await file_reader_fn(stdout_path, service, remaining)
        stderr = await file_reader_fn(stderr_path, service, remaining)
        if stdout is None or stderr is None:
            raise RuntimeError("container output capture unavailable")

        def decoded(value: bytes | str) -> str:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value

        update = {
            "return_code": captured_exit_code,
            "stdout": decoded(stdout),
            "stderr": decoded(stderr),
        }
        if hasattr(result, "model_copy"):
            return result.model_copy(update=update)
        for field, value in update.items():
            setattr(result, field, value)
        return result
    finally:
        with contextlib.suppress(Exception):
            await exec_fn(
                f"rm -rf {shlex.quote(capture_dir)}",
                timeout_sec=10,
                user="root",
                service=service,
            )
