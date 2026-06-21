from __future__ import annotations

import json
import shlex
import subprocess
import time
from typing import Any


SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_probe_request_v0"
)
SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_RESPONSE_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_probe_response_v0"
)
SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_probe_v0"
)

REQUIRED_REMOTE_COMMAND_FILE_BRIDGE_OPERATIONS = (
    "exec",
    "write_file",
    "read_file",
    "cleanup",
)

REMOTE_COMMAND_FILE_BRIDGE_FORBIDDEN_RESPONSE_FLAGS = (
    "raw_command_recorded",
    "raw_stdout_recorded",
    "raw_stderr_recorded",
    "raw_task_text_recorded",
    "raw_logs_recorded",
    "raw_trajectory_recorded",
    "credential_values_recorded",
    "host_paths_recorded",
    "remote_paths_recorded",
)


def _public_safe_label(value: Any, *, limit: int = 120) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    cleaned = []
    for char in text:
        cleaned.append(char.lower() if char.isalnum() or char in {"-", "_", "."} else "-")
    label = "".join(cleaned).strip("-_.")
    while "--" in label:
        label = label.replace("--", "-")
    return (label or None)[:limit]


def build_skillsbench_remote_command_file_bridge_probe_request() -> dict[str, Any]:
    """Build the non-sensitive operation probe sent to a remote bridge.

    The request intentionally contains only a fixed probe payload. It is not a
    benchmark task request and does not include task text, credentials, paths,
    uploads, submissions, or runner logs.
    """

    return {
        "schema_version": (
            SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION
        ),
        "benchmark_id": "skillsbench@1.1",
        "probe_id": "skillsbench_remote_command_file_bridge_probe",
        "no_upload": True,
        "submit_enabled": False,
        "operations": [
            {
                "kind": "exec",
                "label": "bounded_noop_command",
                "timeout_sec": 5,
                "expect_exit_code_zero": True,
            },
            {
                "kind": "write_file",
                "label": "probe_marker_write",
                "path_label": "bridge_probe_marker",
                "max_bytes": 64,
                "content": "loopx-skillsbench-bridge-probe\n",
            },
            {
                "kind": "read_file",
                "label": "probe_marker_read",
                "path_label": "bridge_probe_marker",
                "max_bytes": 64,
                "expect_content_match": True,
            },
            {
                "kind": "cleanup",
                "label": "probe_marker_cleanup",
                "path_label": "bridge_probe_marker",
            },
        ],
        "boundary": {
            "record_raw_command": False,
            "record_raw_stdout": False,
            "record_raw_stderr": False,
            "record_raw_task_text": False,
            "record_paths": False,
            "sync_credentials": False,
            "allow_upload": False,
            "allow_submit": False,
        },
    }


def build_skillsbench_remote_command_file_bridge_probe_response(
    *,
    ready: bool,
    operations: list[dict[str, Any]] | None = None,
    first_blocker: str | None = None,
    stage: str = "complete",
) -> dict[str, Any]:
    """Build a bridge-side response for tests or simple local probe servers."""

    op_list = list(operations or [])
    blocker = first_blocker
    if blocker is None:
        blocker = (
            "skillsbench_remote_command_file_bridge_ready"
            if ready
            else "skillsbench_remote_command_file_bridge_probe_failed"
        )
    return {
        "schema_version": (
            SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_RESPONSE_SCHEMA_VERSION
        ),
        "ready": ready,
        "first_blocker": blocker,
        "stage": _public_safe_label(stage, limit=80) or "unknown",
        "operations": op_list,
        "raw_command_recorded": False,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_recorded": False,
        "raw_logs_recorded": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
        "remote_paths_recorded": False,
        "upload_performed": False,
        "submit_performed": False,
    }


def run_skillsbench_remote_command_file_bridge_probe(
    command: str | list[str] | tuple[str, ...] | None,
    *,
    timeout_sec: float = 10.0,
) -> dict[str, Any]:
    """Run a public-safe command/file probe against a remote bridge command."""

    if not command:
        return _bridge_probe_payload(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_probe_command_missing",
            stage="command_missing",
            bridge_command_invoked=False,
            response=None,
            elapsed_ms=0,
        )

    argv = _command_to_argv(command)
    request = build_skillsbench_remote_command_file_bridge_probe_request()
    started = time.monotonic()
    stage = "spawn"
    try:
        stage = "communicate"
        proc = subprocess.run(
            argv,
            input=json.dumps(request, separators=(",", ":")),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if proc.returncode != 0:
            return _bridge_probe_payload(
                ready=False,
                first_blocker="skillsbench_remote_command_file_bridge_probe_command_failed",
                stage="command_exit",
                bridge_command_invoked=True,
                response=None,
                elapsed_ms=elapsed_ms,
            )
        stage = "parse_response"
        response = json.loads(proc.stdout)
        return _payload_from_bridge_response(response, elapsed_ms=elapsed_ms)
    except subprocess.TimeoutExpired:
        return _bridge_probe_payload(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_probe_timeout",
            stage=stage,
            bridge_command_invoked=True,
            response=None,
            elapsed_ms=int(timeout_sec * 1000),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _bridge_probe_payload(
            ready=False,
            first_blocker=f"skillsbench_remote_command_file_bridge_{stage}_failed",
            stage=stage,
            bridge_command_invoked=True,
            response=None,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )


def _payload_from_bridge_response(
    response: dict[str, Any],
    *,
    elapsed_ms: int,
) -> dict[str, Any]:
    if not isinstance(response, dict):
        return _bridge_probe_payload(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_response_invalid",
            stage="validate_response",
            bridge_command_invoked=True,
            response=None,
            elapsed_ms=elapsed_ms,
        )

    schema_ok = (
        response.get("schema_version")
        == SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_RESPONSE_SCHEMA_VERSION
    )
    operations = response.get("operations")
    op_list = operations if isinstance(operations, list) else []
    op_kinds = [
        str(op.get("kind") or "")
        for op in op_list
        if isinstance(op, dict) and str(op.get("kind") or "")
    ]
    missing_ops = [
        kind
        for kind in REQUIRED_REMOTE_COMMAND_FILE_BRIDGE_OPERATIONS
        if kind not in op_kinds
    ]
    failed_ops = [
        str(op.get("kind") or "unknown")
        for op in op_list
        if isinstance(op, dict) and op.get("status") != "ok"
    ]
    boundary_violations = [
        flag
        for flag in REMOTE_COMMAND_FILE_BRIDGE_FORBIDDEN_RESPONSE_FLAGS
        if response.get(flag) is True
    ]
    if response.get("upload_performed") is True:
        boundary_violations.append("upload_performed")
    if response.get("submit_performed") is True:
        boundary_violations.append("submit_performed")

    ready = (
        schema_ok
        and response.get("ready") is True
        and not missing_ops
        and not failed_ops
        and not boundary_violations
    )
    if ready:
        first_blocker = "skillsbench_remote_command_file_bridge_ready"
    elif not schema_ok:
        first_blocker = "skillsbench_remote_command_file_bridge_response_schema_invalid"
    elif boundary_violations:
        first_blocker = "skillsbench_remote_command_file_bridge_boundary_violation"
    elif missing_ops:
        first_blocker = "skillsbench_remote_command_file_bridge_operations_incomplete"
    elif failed_ops:
        first_blocker = "skillsbench_remote_command_file_bridge_operation_failed"
    else:
        first_blocker = (
            _public_safe_label(response.get("first_blocker"), limit=120)
            or "skillsbench_remote_command_file_bridge_probe_failed"
        )
    return _bridge_probe_payload(
        ready=ready,
        first_blocker=first_blocker,
        stage=_public_safe_label(response.get("stage"), limit=80) or "complete",
        bridge_command_invoked=True,
        response=response,
        elapsed_ms=elapsed_ms,
        missing_operations=missing_ops,
        failed_operations=failed_ops,
        boundary_violations=boundary_violations,
    )


def _bridge_probe_payload(
    *,
    ready: bool,
    first_blocker: str,
    stage: str,
    bridge_command_invoked: bool,
    response: dict[str, Any] | None,
    elapsed_ms: int,
    missing_operations: list[str] | None = None,
    failed_operations: list[str] | None = None,
    boundary_violations: list[str] | None = None,
) -> dict[str, Any]:
    operations = response.get("operations") if isinstance(response, dict) else []
    op_summaries: list[dict[str, Any]] = []
    if isinstance(operations, list):
        for op in operations[:8]:
            if not isinstance(op, dict):
                continue
            summary: dict[str, Any] = {}
            for field in ("kind", "label", "status"):
                value = _public_safe_label(op.get(field), limit=80)
                if value:
                    summary[field] = value
            if isinstance(op.get("exit_code_zero"), bool):
                summary["exit_code_zero"] = op["exit_code_zero"]
            if isinstance(op.get("content_match"), bool):
                summary["content_match"] = op["content_match"]
            if summary:
                op_summaries.append(summary)

    response_schema = None
    if isinstance(response, dict):
        response_schema = _public_safe_label(response.get("schema_version"), limit=120)

    elapsed = max(0, min(int(elapsed_ms), 600_000))
    return {
        "schema_version": SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION,
        "ready": ready,
        "first_blocker": _public_safe_label(first_blocker, limit=120)
        or "skillsbench_remote_command_file_bridge_probe_failed",
        "stage": _public_safe_label(stage, limit=80) or "unknown",
        "elapsed_ms": elapsed,
        "bridge_command_invoked": bridge_command_invoked,
        "request_schema_version": (
            SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION
        ),
        "response_schema_version": response_schema,
        "required_operations": list(REQUIRED_REMOTE_COMMAND_FILE_BRIDGE_OPERATIONS),
        "operation_count": len(op_summaries),
        "operations": op_summaries,
        "missing_operations": [
            _public_safe_label(item, limit=80) or "unknown"
            for item in (missing_operations or [])
        ],
        "failed_operations": [
            _public_safe_label(item, limit=80) or "unknown"
            for item in (failed_operations or [])
        ],
        "boundary_violations": [
            _public_safe_label(item, limit=80) or "unknown"
            for item in (boundary_violations or [])
        ],
        "raw_command_recorded": False,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_recorded": False,
        "raw_logs_recorded": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
        "remote_paths_recorded": False,
        "upload_performed": False,
        "submit_performed": False,
    }


def _command_to_argv(command: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]
