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
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION,
    build_skillsbench_remote_command_file_bridge_probe_response,
)


MARKER_CONTENT = "loopx-skillsbench-docker-bridge-probe"
OPERATION_RESPONSE_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_operation_response_v0"
)
MAX_CAPTURE_BYTES = 200_000


def _json_response(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True))
    return 0


def _safe_path(value: Any, *, allow_file: bool = True) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("path_missing")
    if "\x00" in text or not text.startswith("/"):
        raise ValueError("path_invalid")
    allowed_roots = ("/app", "/tmp")
    if not any(text == root or text.startswith(root + "/") for root in allowed_roots):
        raise ValueError("path_outside_allowed_roots")
    if not allow_file and text == "/app":
        raise ValueError("path_refuses_app_root")
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
        proc = self._compose_exec(
            "timeout "
            + shlex.quote(str(timeout_seconds))
            + " sh -lc "
            + shlex.quote(command),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
        )
        stdout, stdout_truncated = _bounded_text(proc.stdout, limit=MAX_CAPTURE_BYTES)
        stderr, stderr_truncated = _bounded_text(proc.stderr, limit=MAX_CAPTURE_BYTES)
        return _json_response(
            _operation_response(
                ok=proc.returncode == 0,
                operation="exec",
                first_blocker=None if proc.returncode == 0 else "exec_failed",
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                stdout_truncated=stdout_truncated,
                stderr_truncated=stderr_truncated,
            )
        )

    def _run_read_file(self, request: dict[str, Any], timeout_seconds: int) -> int:
        path = _safe_path(request.get("path"))
        max_bytes = max(
            1,
            min(int(request.get("max_bytes") or MAX_CAPTURE_BYTES), MAX_CAPTURE_BYTES),
        )
        proc = self._compose_exec(
            "dd if=" + shlex.quote(path) + " bs=1 count=" + shlex.quote(str(max_bytes)),
            timeout_seconds=timeout_seconds,
        )
        content, truncated = _bounded_text(proc.stdout, limit=max_bytes)
        stderr, stderr_truncated = _bounded_text(proc.stderr, limit=MAX_CAPTURE_BYTES)
        return _json_response(
            _operation_response(
                ok=proc.returncode == 0,
                operation="read_file",
                first_blocker=None if proc.returncode == 0 else "read_file_failed",
                exit_code=proc.returncode,
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
        probe_dir = "/tmp/loopx-skillsbench-command-file-bridge"
        marker = probe_dir + "/marker.txt"
        exec_proc = self._compose_exec(
            "mkdir -p "
            + shlex.quote(probe_dir)
            + " && test -d "
            + shlex.quote(probe_dir),
            timeout_seconds=timeout_seconds,
        )
        write_proc = self._compose_exec(
            "mkdir -p " + shlex.quote(probe_dir) + " && cat > " + shlex.quote(marker),
            stdin=MARKER_CONTENT.encode("utf-8"),
            timeout_seconds=timeout_seconds,
        )
        read_proc = self._compose_exec(
            "cat " + shlex.quote(marker),
            timeout_seconds=timeout_seconds,
        )
        cleanup_proc = self._compose_exec(
            "rm -f " + shlex.quote(marker),
            timeout_seconds=timeout_seconds,
        )
        read_text, _ = _bounded_text(read_proc.stdout, limit=MAX_CAPTURE_BYTES)
        operations = [
            {
                "kind": "exec",
                "label": "bounded_noop_command",
                "status": "ok" if exec_proc.returncode == 0 else "failed",
                "exit_code_zero": exec_proc.returncode == 0,
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
                    if read_proc.returncode == 0 and read_text == MARKER_CONTENT
                    else "failed"
                ),
                "content_match": read_proc.returncode == 0
                and read_text == MARKER_CONTENT,
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
