#!/usr/bin/env python3
"""Serve a public-safe SkillsBench remote command/file bridge probe.

This helper is a local fake bridge for validation and developer wiring. Real
remote executors can implement the same stdin/stdout JSON contract behind SSH
or another private transport. The response intentionally records only compact
operation facts, never raw command text, stdout, stderr, paths, credentials,
logs, trajectories, uploads, or submissions.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION,
    build_skillsbench_remote_command_file_bridge_probe_response,
)


def _operation(
    *,
    kind: str,
    label: str,
    status: str = "ok",
    exit_code_zero: bool | None = None,
    content_match: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": kind, "label": label, "status": status}
    if exit_code_zero is not None:
        payload["exit_code_zero"] = exit_code_zero
    if content_match is not None:
        payload["content_match"] = content_match
    return payload


def serve_probe(*, fail_operation: str | None = None) -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        response = build_skillsbench_remote_command_file_bridge_probe_response(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_request_invalid",
            stage="parse_request",
        )
        print(json.dumps(response, sort_keys=True))
        return 0

    if (
        request.get("schema_version")
        != SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_REQUEST_SCHEMA_VERSION
    ):
        response = build_skillsbench_remote_command_file_bridge_probe_response(
            ready=False,
            first_blocker="skillsbench_remote_command_file_bridge_request_schema_invalid",
            stage="validate_request",
        )
        print(json.dumps(response, sort_keys=True))
        return 0

    content = "loopx-skillsbench-bridge-probe\n"
    operations: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-bridge-") as tmp:
        marker = Path(tmp) / "marker.txt"

        exec_status = "failed" if fail_operation == "exec" else "ok"
        operations.append(
            _operation(
                kind="exec",
                label="bounded_noop_command",
                status=exec_status,
                exit_code_zero=exec_status == "ok",
            )
        )

        write_status = "failed" if fail_operation == "write_file" else "ok"
        if write_status == "ok":
            marker.write_text(content, encoding="utf-8")
        operations.append(
            _operation(
                kind="write_file",
                label="probe_marker_write",
                status=write_status,
            )
        )

        read_status = "failed" if fail_operation == "read_file" else "ok"
        read_match = False
        if read_status == "ok":
            try:
                read_match = marker.read_text(encoding="utf-8") == content
            except OSError:
                read_status = "failed"
        operations.append(
            _operation(
                kind="read_file",
                label="probe_marker_read",
                status=read_status,
                content_match=read_match,
            )
        )

        cleanup_status = "failed" if fail_operation == "cleanup" else "ok"
        if cleanup_status == "ok":
            try:
                marker.unlink()
            except FileNotFoundError:
                pass
        operations.append(
            _operation(
                kind="cleanup",
                label="probe_marker_cleanup",
                status=cleanup_status,
            )
        )

    ready = all(item["status"] == "ok" for item in operations)
    response = build_skillsbench_remote_command_file_bridge_probe_response(
        ready=ready,
        operations=operations,
        first_blocker=(
            None
            if ready
            else "skillsbench_remote_command_file_bridge_operation_failed"
        ),
    )
    print(json.dumps(response, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-probe", action="store_true")
    parser.add_argument(
        "--fail-operation",
        choices=["exec", "write_file", "read_file", "cleanup"],
        default=None,
    )
    args = parser.parse_args(argv)
    if args.serve_probe:
        return serve_probe(fail_operation=args.fail_operation)
    parser.error("--serve-probe is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
