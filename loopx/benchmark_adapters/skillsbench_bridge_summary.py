from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def bridge_summary_has_inflight_operation(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    starts = 0
    completions = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        phase = str(record.get("record_phase") or "").strip().lower()
        if phase == "complete" and not bridge_operation_record_interrupted(record):
            completions += 1
        elif phase == "start" or record.get("operation_observed") is True:
            starts += 1
    return starts > completions


def bridge_summary_has_meaningful_agent_progress(
    path: Path | None,
    *,
    allow_loopx_closeout: bool,
) -> bool:
    """Return true once the worker has done task work or a real closeout action."""

    if path is None or not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    closeout_subcommands = {
        ("todo", "complete"),
        ("todo", "update"),
        ("refresh-state",),
        ("quota", "spend-slot"),
    }
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        phase = str(record.get("record_phase") or "").strip().lower()
        if phase == "complete" and bridge_operation_record_interrupted(record):
            continue
        if record.get("task_facing_operation") is True:
            return True
        if allow_loopx_closeout and record.get("loopx_state_write") is True:
            subcommands = record.get("loopx_subcommands")
            if isinstance(subcommands, list):
                key = tuple(str(item) for item in subcommands[:2])
                if key in closeout_subcommands:
                    return True
    return False


def bridge_summary_has_successful_task_file_write(path: Path | None) -> bool:
    """Return true after the worker successfully writes task-facing files."""

    return bridge_summary_has_successful_task_operation(path, operation="write_file")


def bridge_summary_has_successful_task_operation(
    path: Path | None,
    *,
    operation: str | None = None,
) -> bool:
    """Return true after a successful task-facing bridge operation."""

    if path is None or not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        phase = str(record.get("record_phase") or "").strip().lower()
        if phase != "complete" or bridge_operation_record_interrupted(record):
            continue
        if operation is not None and record.get("operation") != operation:
            continue
        if record.get("task_facing_operation") is not True:
            continue
        if record.get("success") is True or record.get("returncode") == 0:
            return True
    return False


def bridge_summary_task_progress_receipt(path: Path | None) -> dict[str, Any]:
    """Reduce one agent invocation to bounded task-facing content changes."""

    receipt: dict[str, Any] = {
        "schema_version": "skillsbench_bridge_task_progress_receipt_v0",
        "status": "no_verified_task_mutation",
        "task_facing_operation_count": 0,
        "task_facing_success_count": 0,
        "successful_task_file_write_count": 0,
        "successful_task_file_change_count": 0,
        "raw_material_recorded": False,
    }
    if path is None or not path.exists():
        return receipt
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return receipt
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        receipt["raw_material_recorded"] = receipt["raw_material_recorded"] or any(
            record.get(field) is True
            for field in (
                "raw_request_recorded",
                "raw_stdout_recorded",
                "raw_stderr_recorded",
                "raw_task_text_recorded",
                "credential_values_recorded",
                "host_paths_recorded",
                "remote_paths_recorded",
            )
        )
        phase = str(record.get("record_phase") or "").strip().lower()
        if phase != "complete" or bridge_operation_record_interrupted(record):
            continue
        if record.get("task_facing_operation") is not True:
            continue
        receipt["task_facing_operation_count"] += 1
        success = record.get("success")
        successful = (
            success if isinstance(success, bool) else record.get("returncode") == 0
        )
        if not successful:
            continue
        receipt["task_facing_success_count"] += 1
        if (
            record.get("operation") == "write_file"
            and record.get("durable_task_write") is True
        ):
            receipt["successful_task_file_write_count"] += 1
            if record.get("durable_task_content_changed") is True:
                receipt["successful_task_file_change_count"] += 1
    if (
        receipt["successful_task_file_change_count"] > 0
        and receipt["raw_material_recorded"] is False
    ):
        receipt["status"] = "verified_task_content_change"
    return receipt


def bridge_operation_record_interrupted(record: dict[str, Any]) -> bool:
    rc = record.get("returncode")
    if isinstance(rc, int) and not isinstance(rc, bool) and rc < 0:
        return True
    category = str(record.get("failure_category") or "")
    return record.get("interrupted") is True or category in {
        "bridge_operation_interrupted",
        "bridge_controller_interrupted",
    }


def prompt_requires_meaningful_bridge_progress(prompt: str, *, route: str) -> bool:
    text = prompt or ""
    if "Private bridge command:" not in text:
        return False
    if route == "codex-app-server-goal-baseline":
        return True
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "--- task instruction ---",
            "first action required",
            "mandatory product-mode solver checkpoint",
            "mandatory host-local bridge recovery checkpoint",
            "must start with either a task-facing sandbox bridge operation",
            "task-facing validation or repair operation",
        )
    )
