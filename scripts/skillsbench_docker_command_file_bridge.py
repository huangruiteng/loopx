#!/usr/bin/env python3
"""Docker-compose backed SkillsBench command/file bridge.

The bridge implements the same stdin/stdout JSON contract as the remote
command-file bridge, but targets a live local BenchFlow Docker sandbox through
``docker compose exec`` instead of SSH. It is intentionally private-output
oriented: raw command/file output may be returned to the agent, while public
traces consume only the bounded operation status fields emitted by the probe.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION,
    build_skillsbench_remote_command_file_bridge_probe_response,
)
from loopx.benchmark_core.container_exec import (  # noqa: E402
    parse_container_exit_status,
    wrap_container_command_with_exit_status,
)


MARKER_CONTENT = "loopx-skillsbench-docker-bridge-probe"
OPERATION_RESPONSE_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_operation_response_v0"
)
MAX_CAPTURE_BYTES = 200_000
ALLOWED_SANDBOX_PATH_ROOTS = ("/app", "/tmp", "/root")
BRIDGE_TEMP_ROOT = "/tmp/loopx-skillsbench-command-file-bridge"


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True))
    return 0


def _safe_path(value: Any, *, allow_file: bool = True) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("path_missing")
    if "\x00" in text or not text.startswith("/"):
        raise ValueError("path_invalid")
    if not any(
        text == root or text.startswith(root + "/")
        for root in ALLOWED_SANDBOX_PATH_ROOTS
    ):
        raise ValueError("path_outside_allowed_roots")
    if not allow_file and text in ALLOWED_SANDBOX_PATH_ROOTS:
        raise ValueError("path_refuses_sandbox_root")
    return text


def _bounded_text(data: bytes, *, limit: int) -> tuple[str, bool]:
    clipped = data[:limit]
    return clipped.decode("utf-8", errors="replace"), len(data) > limit


def _operation_response(
    *,
    ok: bool,
    operation: str,
    first_blocker: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "schema_version": OPERATION_RESPONSE_SCHEMA_VERSION,
        "ok": ok,
        "operation": operation,
        "first_blocker": first_blocker,
        "raw_task_text_recorded": False,
        "credential_values_recorded": False,
        "upload_performed": False,
        "submit_performed": False,
    }
    payload.update(extra)
    return payload


class DockerCommandFileBridge:
    def __init__(
        self,
        *,
        project_name: str,
        project_dir: str,
        compose_files: list[str],
        service: str,
    ) -> None:
        self.project_name = project_name
        self.project_dir = project_dir
        self.compose_files = compose_files
        self.service = service

    def _compose_base(self) -> list[str]:
        command = [
            "docker",
            "compose",
            "-p",
            self.project_name,
            "--project-directory",
            self.project_dir,
        ]
        for compose_file in self.compose_files:
            command.extend(["-f", compose_file])
        return command

    def _compose_exec(
        self,
        shell_command: str,
        *,
        cwd: str | None = None,
        stdin: bytes | None = None,
        timeout_seconds: int = 30,
    ) -> subprocess.CompletedProcess[bytes]:
        command = [*self._compose_base(), "exec", "-T"]
        if cwd:
            command.extend(["-w", cwd])
        command.extend([self.service, "bash", "-lc", shell_command])
        return subprocess.run(
            command,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 10,
            check=False,
        )

    @staticmethod
    def _docker_socket_path() -> str | None:
        docker_host = os.environ.get("DOCKER_HOST", "").strip()
        if docker_host.startswith("unix://"):
            return docker_host.removeprefix("unix://")
        if docker_host:
            return None
        return "/var/run/docker.sock"

    def _resolve_container_id(self, *, timeout_seconds: int) -> str | None:
        socket_path = self._docker_socket_path()
        if not socket_path:
            return None
        filters = {
            "label": [
                f"com.docker.compose.project={self.project_name}",
                f"com.docker.compose.service={self.service}",
            ],
            "status": ["running"],
        }
        url = (
            "http://localhost/containers/json?all=1&filters="
            + quote(json.dumps(filters, separators=(",", ":")), safe="")
        )
        try:
            proc = subprocess.run(
                [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--fail",
                    "--unix-socket",
                    socket_path,
                    url,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds + 10,
                check=False,
            )
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        try:
            containers = json.loads(proc.stdout)
            matches = [
                str(container.get("Id") or "").strip()
                for container in containers
                if isinstance(container, dict) and container.get("Id")
            ]
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            return None
        return matches[0] if len(matches) == 1 else None

    def _remove_container_path(
        self, path: str, *, recursive: bool, timeout_seconds: int
    ) -> None:
        try:
            self._compose_exec(
                ("rm -rf -- " if recursive else "rm -f -- ") + shlex.quote(path),
                timeout_seconds=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _read_container_file_via_copy(
        self,
        path: str,
        *,
        max_bytes: int,
        timeout_seconds: int,
    ) -> tuple[int, bytes, bytes]:
        staged_path = f"{BRIDGE_TEMP_ROOT}/{uuid.uuid4().hex}.bounded"
        try:
            stage_proc = self._compose_exec(
                "mkdir -p "
                + shlex.quote(BRIDGE_TEMP_ROOT)
                + " && dd if="
                + shlex.quote(path)
                + " of="
                + shlex.quote(staged_path)
                + " bs="
                + shlex.quote(str(max_bytes + 1))
                + " count=1 status=none",
                timeout_seconds=timeout_seconds,
            )
            if stage_proc.returncode != 0:
                return stage_proc.returncode, b"", stage_proc.stderr
            container_id = self._resolve_container_id(
                timeout_seconds=timeout_seconds
            )
            if not container_id:
                return 1, b"", b"docker container resolution failed"
            with tempfile.TemporaryDirectory(
                prefix="loopx-skillsbench-docker-copy-"
            ) as tmp:
                destination = Path(tmp) / "payload"
                try:
                    copy_proc = subprocess.run(
                        [
                            "docker",
                            "cp",
                            f"{container_id}:{staged_path}",
                            str(destination),
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=timeout_seconds + 10,
                        check=False,
                    )
                except OSError:
                    return 1, b"", b"docker copy unavailable"
                if copy_proc.returncode != 0:
                    return copy_proc.returncode, b"", copy_proc.stderr
                try:
                    return 0, destination.read_bytes(), b""
                except OSError as exc:
                    return 1, b"", str(exc).encode("utf-8", errors="replace")
        finally:
            self._remove_container_path(
                staged_path,
                recursive=False,
                timeout_seconds=timeout_seconds,
            )

    def run_operation(self, request: dict[str, Any]) -> int:
        operation = str(request.get("operation") or "").strip()
        if operation not in {"exec", "read_file", "write_file", "cleanup"}:
            return _json_response(
                _operation_response(
                    ok=False,
                    operation=operation or "unknown",
                    first_blocker="operation_invalid",
                )
            )
        timeout_seconds = max(1, min(int(request.get("timeout_sec") or 30), 300))
        try:
            if operation == "exec":
                return self._run_exec(request, timeout_seconds)
            if operation == "read_file":
                return self._run_read_file(request, timeout_seconds)
            if operation == "write_file":
                return self._run_write_file(request, timeout_seconds)
            return self._run_cleanup(request, timeout_seconds)
        except subprocess.TimeoutExpired:
            return _json_response(
                _operation_response(
                    ok=False,
                    operation=operation,
                    first_blocker="operation_timeout",
                )
            )
        except ValueError as exc:
            return _json_response(
                _operation_response(
                    ok=False,
                    operation=operation,
                    first_blocker=str(exc) or "request_invalid",
                )
            )

    def _run_exec(self, request: dict[str, Any], timeout_seconds: int) -> int:
        cwd = _safe_path(request.get("cwd") or "/app")
        command = str(request.get("command") or "").strip()
        if not command:
            raise ValueError("command_missing")
        return _json_response(
            self._exec_response(
                cwd=cwd,
                command=command,
                timeout_seconds=timeout_seconds,
            )
        )

    def _exec_response(
        self,
        *,
        cwd: str,
        command: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        capture_dir = f"{BRIDGE_TEMP_ROOT}/{uuid.uuid4().hex}.exec"
        stdout_path = capture_dir + "/stdout"
        stderr_path = capture_dir + "/stderr"
        exit_code_path = capture_dir + "/exit_code"
        captured_command = (
            "timeout "
            + shlex.quote(str(timeout_seconds))
            + " sh -lc "
            + shlex.quote(command)
            + " > "
            + shlex.quote(stdout_path)
            + " 2> "
            + shlex.quote(stderr_path)
        )
        started_at = time.monotonic()
        proc = self._compose_exec(
            wrap_container_command_with_exit_status(
                captured_command,
                exit_code_path,
            ),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        deadline = started_at + timeout_seconds + 2
        exit_code_rc = 1
        exit_code_bytes = b""
        exit_code_copy_stderr = b"container exit status capture unavailable"
        captured_exit_code = None
        while captured_exit_code is None:
            remaining = deadline - time.monotonic()
            exit_code_rc, exit_code_bytes, exit_code_copy_stderr = (
                self._read_container_file_via_copy(
                    exit_code_path,
                    max_bytes=16,
                    timeout_seconds=max(1, min(5, int(max(remaining, 1)))),
                )
            )
            if exit_code_rc == 0:
                captured_exit_code = parse_container_exit_status(exit_code_bytes)
            if captured_exit_code is None:
                if remaining <= 0:
                    break
                time.sleep(min(0.5, max(0.0, remaining)))
        stdout_rc, stdout_bytes, stdout_copy_stderr = (
            self._read_container_file_via_copy(
                stdout_path,
                max_bytes=MAX_CAPTURE_BYTES,
                timeout_seconds=timeout_seconds,
            )
        )
        stderr_rc, stderr_bytes, stderr_copy_stderr = (
            self._read_container_file_via_copy(
                stderr_path,
                max_bytes=MAX_CAPTURE_BYTES,
                timeout_seconds=timeout_seconds,
            )
        )
        self._remove_container_path(
            capture_dir,
            recursive=True,
            timeout_seconds=timeout_seconds,
        )
        stdout, stdout_truncated = _bounded_text(
            stdout_bytes, limit=MAX_CAPTURE_BYTES
        )
        stderr_source = stderr_bytes
        if (
            proc.returncode != 0
            or stdout_rc != 0
            or stderr_rc != 0
            or exit_code_rc != 0
        ):
            stderr_source += (
                proc.stderr
                + stdout_copy_stderr
                + stderr_copy_stderr
                + exit_code_copy_stderr
            )
        if captured_exit_code is None:
            stderr_source += b"container exit status capture invalid\n"
        stderr, stderr_truncated = _bounded_text(
            stderr_source, limit=MAX_CAPTURE_BYTES
        )
        output_capture_ok = stdout_rc == 0 and stderr_rc == 0
        status_capture_ok = exit_code_rc == 0 and captured_exit_code is not None
        effective_exit_code = (
            proc.returncode
            if proc.returncode != 0
            else captured_exit_code if captured_exit_code is not None else 1
        )
        blocker = None
        if proc.returncode != 0:
            blocker = "exec_failed"
        elif not status_capture_ok:
            blocker = "exec_status_capture_failed"
        elif not output_capture_ok:
            blocker = "exec_output_capture_failed"
        elif effective_exit_code != 0:
            blocker = "exec_failed"
        return _operation_response(
            ok=(
                proc.returncode == 0
                and output_capture_ok
                and status_capture_ok
                and effective_exit_code == 0
            ),
            operation="exec",
            first_blocker=blocker,
            exit_code=effective_exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )

    def _run_read_file(self, request: dict[str, Any], timeout_seconds: int) -> int:
        path = _safe_path(request.get("path"))
        max_bytes = max(
            1,
            min(int(request.get("max_bytes") or MAX_CAPTURE_BYTES), MAX_CAPTURE_BYTES),
        )
        returncode, content_bytes, copy_stderr = self._read_container_file_via_copy(
            path,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
        )
        content, truncated = _bounded_text(content_bytes, limit=max_bytes)
        stderr, stderr_truncated = _bounded_text(
            copy_stderr, limit=MAX_CAPTURE_BYTES
        )
        return _json_response(
            _operation_response(
                ok=returncode == 0,
                operation="read_file",
                first_blocker=None if returncode == 0 else "read_file_failed",
                exit_code=returncode,
                content=content,
                content_truncated=truncated,
                stderr=stderr,
                stderr_truncated=stderr_truncated,
            )
        )

    def _run_write_file(self, request: dict[str, Any], timeout_seconds: int) -> int:
        path = _safe_path(request.get("path"))
        content = str(request.get("content") or "")
        proc = self._compose_exec(
            "mkdir -p "
            + shlex.quote(str(Path(path).parent))
            + " && cat > "
            + shlex.quote(path),
            stdin=content.encode("utf-8"),
            timeout_seconds=timeout_seconds,
        )
        stderr, stderr_truncated = _bounded_text(proc.stderr, limit=MAX_CAPTURE_BYTES)
        return _json_response(
            _operation_response(
                ok=proc.returncode == 0,
                operation="write_file",
                first_blocker=None if proc.returncode == 0 else "write_file_failed",
                exit_code=proc.returncode,
                bytes_written=len(content.encode("utf-8")),
                stderr=stderr,
                stderr_truncated=stderr_truncated,
            )
        )

    def _run_cleanup(self, request: dict[str, Any], timeout_seconds: int) -> int:
        path = _safe_path(request.get("path"), allow_file=False)
        proc = self._compose_exec(
            "rm -rf -- " + shlex.quote(path),
            timeout_seconds=timeout_seconds,
        )
        stderr, stderr_truncated = _bounded_text(proc.stderr, limit=MAX_CAPTURE_BYTES)
        return _json_response(
            _operation_response(
                ok=proc.returncode == 0,
                operation="cleanup",
                first_blocker=None if proc.returncode == 0 else "cleanup_failed",
                exit_code=proc.returncode,
                stderr=stderr,
                stderr_truncated=stderr_truncated,
            )
        )

    def probe(self, timeout_seconds: int) -> tuple[list[dict[str, Any]], str | None]:
        probe_dir = BRIDGE_TEMP_ROOT
        marker = probe_dir + "/marker.txt"
        exec_response = self._exec_response(
            cwd="/tmp",
            command="exit 7",
            timeout_seconds=timeout_seconds,
        )
        write_proc = self._compose_exec(
            "mkdir -p " + shlex.quote(probe_dir) + " && cat > " + shlex.quote(marker),
            stdin=MARKER_CONTENT.encode("utf-8"),
            timeout_seconds=timeout_seconds,
        )
        read_returncode, read_bytes, _ = self._read_container_file_via_copy(
            marker,
            max_bytes=MAX_CAPTURE_BYTES,
            timeout_seconds=timeout_seconds,
        )
        cleanup_proc = self._compose_exec(
            "rm -f " + shlex.quote(marker),
            timeout_seconds=timeout_seconds,
        )
        read_text, _ = _bounded_text(read_bytes, limit=MAX_CAPTURE_BYTES)
        exit_status_roundtrip_ok = (
            exec_response.get("ok") is False
            and exec_response.get("first_blocker") == "exec_failed"
            and exec_response.get("exit_code") == 7
        )
        operations = [
            {
                "kind": "exec",
                "label": "nonzero_exit_status_roundtrip",
                "status": "ok" if exit_status_roundtrip_ok else "failed",
                "nonzero_exit_status_detected": exit_status_roundtrip_ok,
            },
            {
                "kind": "write_file",
                "label": "probe_marker_write",
                "status": "ok" if write_proc.returncode == 0 else "failed",
            },
            {
                "kind": "read_file",
                "label": "probe_marker_read",
                "status": (
                    "ok"
                    if read_returncode == 0 and read_text == MARKER_CONTENT
                    else "failed"
                ),
                "content_match": read_returncode == 0 and read_text == MARKER_CONTENT,
            },
            {
                "kind": "cleanup",
                "label": "probe_marker_cleanup",
                "status": "ok" if cleanup_proc.returncode == 0 else "failed",
            },
        ]
        failed = [item["kind"] for item in operations if item["status"] != "ok"]
        blocker = None if not failed else f"skillsbench_docker_bridge_{failed[0]}_failed"
        return operations, blocker


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--compose-file", action="append", required=True)
    parser.add_argument("--service", default="main")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    bridge = DockerCommandFileBridge(
        project_name=args.project_name,
        project_dir=args.project_dir,
        compose_files=list(args.compose_file or []),
        service=args.service,
    )
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        response = build_skillsbench_remote_command_file_bridge_probe_response(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_request_invalid",
            stage="parse_request",
        )
        return _json_response(response)
    if "operation" in request:
        return bridge.run_operation(request)
    if (
        request.get("schema_version")
        != SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION
    ):
        response = build_skillsbench_remote_command_file_bridge_probe_response(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_request_schema_invalid",
            stage="validate_request",
        )
        return _json_response(response)
    timeout_seconds = max(1, min(int(request.get("timeout_sec") or 30), 300))
    operations, blocker = bridge.probe(timeout_seconds)
    response = build_skillsbench_remote_command_file_bridge_probe_response(
        ready=blocker is None and all(item["status"] == "ok" for item in operations),
        operations=operations,
        first_blocker=blocker,
        stage="docker_compose_probe",
    )
    return _json_response(response)


if __name__ == "__main__":
    raise SystemExit(main())
