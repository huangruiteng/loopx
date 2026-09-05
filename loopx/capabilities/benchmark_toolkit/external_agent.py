"""Run one external-agent phase without taking benchmark ownership.

The surrounding benchmark harness owns task provisioning, container lifecycle,
verification, and score calculation. This module only consumes a small
versioned request, invokes a runner-selected solver command in the supplied
workspace, and writes a public-safe result receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any

from .launch_admission import normalize_benchmark_launch_admission_receipt

EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION = "external_agent_request_v1"
EXTERNAL_AGENT_RESULT_SCHEMA_VERSION = "external_agent_result_v1"
EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION = "external_agent_request_v2"
EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION = "external_agent_result_v2"
EXTERNAL_AGENT_CONTAINMENT_SCHEMA_VERSION = "external_agent_containment_v1"
EXTERNAL_AGENT_CONTAINMENT_VERIFICATION_SCHEMA_VERSION = (
    "external_agent_containment_verification_v1"
)
LOOPX_EXTERNAL_AGENT_PHASE_RECEIPT_SCHEMA_VERSION = (
    "loopx_external_agent_phase_receipt_v1"
)
EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION = "external_agent_phase_receipt_v2"
BENCHMARK_PUBLIC_PROGRESS_SCHEMA_VERSION = "benchmark_public_progress_v0"
BENCHMARK_CONTINUATION_DECISION_SCHEMA_VERSION = "benchmark_continuation_decision_v0"
_MAX_TIMEOUT_SECONDS = 86_400.0
_RESULT_STATUSES = {"succeeded", "failed"}
_TERMINAL_RESULT_CLASSIFICATIONS = {
    "solver_completed",
    "solver_exited_nonzero",
    "solver_startup_failed",
}
_CONTAINMENT_KINDS = {
    "container",
    "cgroup_v2",
    "pid_namespace",
    "virtual_machine",
    "windows_job_object",
}
_LEGACY_CONTAINMENT_POSTCONDITION = "drained_before_result_consumption"
EXTERNAL_AGENT_CONTAINMENT_TERMINATION_POSTCONDITION = (
    "destroyed_before_result_consumption"
)
_OPAQUE_REF_PATTERN = re.compile(r"^[A-Za-z0-9._:@/-]{1,160}$")
_SOLVER_ENVIRONMENT_ALLOWLIST = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)


class BenchmarkContinuationDecision(str, Enum):
    CONTINUE = "continue"
    STOP_COMPLETE = "stop_complete"
    STOP_PROGRESS_REGRESSION = "stop_progress_regression"
    STOP_PROMPT_MISMATCH = "stop_prompt_mismatch"
    STOP_ROUND_LIMIT = "stop_round_limit"
    STOP_TASK_SHAPE_MISMATCH = "stop_task_shape_mismatch"
    STOP_TIME_BUDGET = "stop_time_budget"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("external_agent_request_unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("external_agent_request_not_object")
    return value


def _validate_request(
    value: Mapping[str, Any],
) -> tuple[str, Path, float, str, str, str | None]:
    schema_version = value.get("schema_version")
    if schema_version not in {
        EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
        EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION,
    }:
        raise ValueError("external_agent_request_schema_unsupported")
    if schema_version == EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION:
        if set(value) != {
            "schema_version",
            "instruction",
            "workspace",
            "timeout_seconds",
            "containment",
            "launch_admission",
        }:
            raise ValueError("external_agent_request_v2_fields_invalid")
        launch_admission_value = value.get("launch_admission")
        if not isinstance(launch_admission_value, Mapping):
            raise ValueError("external_agent_launch_admission_invalid")
        launch_admission = normalize_benchmark_launch_admission_receipt(
            launch_admission_value
        )
        launch_binding_digest = str(launch_admission["launch_binding_digest"])
    else:
        launch_admission = None
        launch_binding_digest = None

    instruction = value.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError("external_agent_request_instruction_missing")

    workspace_value = value.get("workspace")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        raise ValueError("external_agent_request_workspace_missing")
    try:
        workspace = Path.cwd()
    except OSError as exc:
        raise ValueError("external_agent_runner_workspace_invalid") from exc
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError("external_agent_runner_workspace_invalid")
    if workspace_value != str(workspace):
        raise ValueError("external_agent_request_workspace_mismatch")

    timeout_value = value.get("timeout_seconds")
    if isinstance(timeout_value, bool) or not isinstance(timeout_value, (int, float)):
        raise ValueError("external_agent_request_timeout_invalid")
    timeout_seconds = float(timeout_value)
    if not 0 < timeout_seconds <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("external_agent_request_timeout_invalid")

    containment = value.get("containment")
    if not isinstance(containment, Mapping) or set(containment) != {
        "schema_version",
        "kind",
        "timeout_owner",
        "termination_postcondition",
        "verification",
    }:
        raise ValueError("external_agent_containment_contract_invalid")
    expected_postcondition = (
        EXTERNAL_AGENT_CONTAINMENT_TERMINATION_POSTCONDITION
        if schema_version == EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION
        else _LEGACY_CONTAINMENT_POSTCONDITION
    )
    if (
        containment.get("schema_version") != EXTERNAL_AGENT_CONTAINMENT_SCHEMA_VERSION
        or containment.get("kind") not in _CONTAINMENT_KINDS
        or containment.get("timeout_owner") != "runner"
        or containment.get("termination_postcondition") != expected_postcondition
    ):
        raise ValueError("external_agent_containment_contract_invalid")

    verification = containment.get("verification")
    if not isinstance(verification, Mapping) or set(verification) != {
        "schema_version",
        "status",
        "authority",
        "receipt_ref",
    }:
        raise ValueError("external_agent_containment_verification_invalid")
    receipt_ref = str(verification.get("receipt_ref") or "")
    expected_verification_status = (
        "pending"
        if schema_version == EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION
        else "verified"
    )
    if (
        verification.get("schema_version")
        != EXTERNAL_AGENT_CONTAINMENT_VERIFICATION_SCHEMA_VERSION
        or verification.get("status") != expected_verification_status
        or verification.get("authority") != "runner"
        or not _OPAQUE_REF_PATTERN.fullmatch(receipt_ref)
    ):
        raise ValueError("external_agent_containment_verification_invalid")
    if launch_admission is not None:
        if launch_admission["instruction_sha256"] != _sha256(instruction):
            raise ValueError("external_agent_launch_instruction_digest_mismatch")
        if launch_admission["containment_binding_sha256"] != _sha256(receipt_ref):
            raise ValueError("external_agent_launch_containment_digest_mismatch")

    return (
        instruction,
        workspace,
        timeout_seconds,
        str(containment["kind"]),
        receipt_ref,
        launch_binding_digest,
    )


def _validate_solver_command(value: Sequence[str]) -> list[str]:
    if isinstance(value, (str, bytes)):
        raise ValueError("external_agent_solver_command_invalid")
    command = [item for item in value if isinstance(item, str) and item]
    if len(command) != len(value) or not command:
        raise ValueError("external_agent_solver_command_invalid")
    return command


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return int(value)


def _non_negative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return int(value)


def _sha256_digest(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def normalize_benchmark_public_progress(
    value: Mapping[str, Any],
) -> dict[str, int | str]:
    """Validate one content-free progress observation from the benchmark runner."""

    if set(value) != {
        "schema_version",
        "total_unit_count",
        "completed_unit_count",
    }:
        raise ValueError("benchmark_public_progress_fields_invalid")
    if value.get("schema_version") != BENCHMARK_PUBLIC_PROGRESS_SCHEMA_VERSION:
        raise ValueError("benchmark_public_progress_schema_unsupported")
    total = _positive_int(value.get("total_unit_count"), field="total_unit_count")
    completed = _non_negative_int(
        value.get("completed_unit_count"), field="completed_unit_count"
    )
    if completed > total:
        raise ValueError("completed_unit_count exceeds total_unit_count")
    return {
        "schema_version": BENCHMARK_PUBLIC_PROGRESS_SCHEMA_VERSION,
        "total_unit_count": total,
        "completed_unit_count": completed,
    }


def build_benchmark_continuation_decision(
    progress: Mapping[str, Any],
    *,
    expected_first_prompt_sha256: str,
    observed_first_prompt_sha256: str,
    expected_total_unit_count: int,
    previous_completed_unit_count: int,
    completed_segment_count: int,
    max_agent_segments: int,
    elapsed_ms: int,
    total_budget_ms: int,
) -> dict[str, Any]:
    """Decide whether another solver segment fits the frozen run envelope."""

    normalized = normalize_benchmark_public_progress(progress)
    expected_prompt = _sha256_digest(
        expected_first_prompt_sha256, field="expected_first_prompt_sha256"
    )
    observed_prompt = _sha256_digest(
        observed_first_prompt_sha256, field="observed_first_prompt_sha256"
    )
    prompt_matches = expected_prompt == observed_prompt
    expected_total = _positive_int(
        expected_total_unit_count, field="expected_total_unit_count"
    )
    previous = _non_negative_int(
        previous_completed_unit_count, field="previous_completed_unit_count"
    )
    completed_segments = _positive_int(
        completed_segment_count, field="completed_segment_count"
    )
    max_segments = _positive_int(max_agent_segments, field="max_agent_segments")
    if completed_segments > max_segments:
        raise ValueError("completed_segment_count exceeds max_agent_segments")
    elapsed = _non_negative_int(elapsed_ms, field="elapsed_ms")
    budget = _positive_int(total_budget_ms, field="total_budget_ms")
    completed = int(normalized["completed_unit_count"])
    total = int(normalized["total_unit_count"])
    if previous > total:
        raise ValueError("previous_completed_unit_count exceeds total_unit_count")
    remaining_budget = max(0, budget - elapsed)
    remaining_segments = max_segments - completed_segments
    task_shape_matches = total == expected_total

    if not prompt_matches:
        decision = BenchmarkContinuationDecision.STOP_PROMPT_MISMATCH
        reason = "first_prompt_digest_mismatch"
    elif not task_shape_matches:
        decision = BenchmarkContinuationDecision.STOP_TASK_SHAPE_MISMATCH
        reason = "total_unit_count_mismatch"
    elif completed < previous:
        decision = BenchmarkContinuationDecision.STOP_PROGRESS_REGRESSION
        reason = "public_progress_regressed"
    elif completed == total:
        decision = BenchmarkContinuationDecision.STOP_COMPLETE
        reason = "all_units_complete"
    elif remaining_budget == 0:
        decision = BenchmarkContinuationDecision.STOP_TIME_BUDGET
        reason = "total_agent_budget_exhausted"
    elif remaining_segments == 0:
        decision = BenchmarkContinuationDecision.STOP_ROUND_LIMIT
        reason = "agent_segment_limit_reached"
    else:
        decision = BenchmarkContinuationDecision.CONTINUE
        reason = (
            "requirements_remain_after_progress"
            if completed > previous
            else "requirements_remain_without_progress"
        )

    next_timeout_ms = (
        max(1, remaining_budget // remaining_segments)
        if decision is BenchmarkContinuationDecision.CONTINUE
        else 0
    )
    return {
        "ok": True,
        "schema_version": BENCHMARK_CONTINUATION_DECISION_SCHEMA_VERSION,
        "decision": decision.value,
        "reason_code": reason,
        "continuation_allowed": decision is BenchmarkContinuationDecision.CONTINUE,
        "total_unit_count": total,
        "expected_total_unit_count": expected_total,
        "task_shape_matches": task_shape_matches,
        "completed_unit_count": completed,
        "progress_delta": completed - previous,
        "completed_segment_count": completed_segments,
        "max_agent_segments": max_segments,
        "remaining_budget_ms": remaining_budget,
        "next_segment_timeout_ms": next_timeout_ms,
        "first_prompt_matches": prompt_matches,
        "first_prompt_digest_recorded": False,
        "continuation_prompt_policy": "original_task_plus_public_progress",
        "public_progress_only": True,
        "raw_task_recorded": False,
        "unit_ids_recorded": False,
        "path_recorded": False,
        "read_only": True,
        "host_invoked": False,
        "state_written": False,
    }


def _solver_environment(environment: Mapping[str, str]) -> dict[str, str]:
    safe_environment = {
        key: os.environ[key]
        for key in _SOLVER_ENVIRONMENT_ALLOWLIST
        if key in os.environ
    }
    safe_environment.update(environment)
    return safe_environment


def _result(
    *,
    status: str,
    exit_code: int | None,
    duration_ms: int,
    instruction: str | None,
    command: Sequence[str],
    classification: str,
    containment_kind: str | None = None,
    containment_verification_ref: str | None = None,
    launch_binding_digest: str | None = None,
) -> dict[str, Any]:
    if status not in _RESULT_STATUSES:
        raise ValueError("external_agent_result_status_invalid")
    receipt: dict[str, Any] = {
        "schema_version": LOOPX_EXTERNAL_AGENT_PHASE_RECEIPT_SCHEMA_VERSION,
        "classification": classification,
        "command_recorded": False,
        "command_argument_count": len(command),
        "duration_ms": max(0, duration_ms),
        "instruction_recorded": False,
        "workspace_recorded": False,
    }
    if instruction is not None:
        receipt["instruction_sha256"] = _sha256(instruction)
        receipt["instruction_chars"] = len(instruction)
    # The v1 wire contract historically echoed the runner's pre-launch
    # containment declaration. Keep that compatibility surface unchanged. A v2
    # terminal result is emitted before its caller can destroy the containment,
    # so it must not turn that declaration into a post-exit observation.
    if containment_kind is not None and launch_binding_digest is None:
        receipt["containment_contract_validated"] = True
        receipt["containment_kind"] = containment_kind
        receipt["containment_verification_authority"] = "runner"
        receipt["containment_verification_status"] = "verified"
        receipt["containment_termination_postcondition"] = (
            _LEGACY_CONTAINMENT_POSTCONDITION
        )
        receipt["timeout_enforced_locally"] = False
        receipt["timeout_owner"] = "runner"
    if containment_verification_ref is not None and launch_binding_digest is None:
        receipt["containment_verification_ref_sha256"] = _sha256(
            containment_verification_ref
        )
    if launch_binding_digest is not None:
        receipt["schema_version"] = EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION
        receipt["launch_binding_digest"] = launch_binding_digest
    return {
        "schema_version": (
            EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION
            if launch_binding_digest is not None
            else EXTERNAL_AGENT_RESULT_SCHEMA_VERSION
        ),
        "status": status,
        "exit_code": exit_code,
        "receipt": receipt,
    }


def normalize_external_agent_result_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate solver terminal facts without accepting lifecycle claims."""

    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "status",
        "exit_code",
        "receipt",
    }:
        raise ValueError("external_agent_result_v2_fields_invalid")
    if value.get("schema_version") != EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION:
        raise ValueError("external_agent_result_v2_schema_unsupported")
    status = value.get("status")
    if not isinstance(status, str) or status not in _RESULT_STATUSES:
        raise ValueError("external_agent_result_status_invalid")
    exit_code = value.get("exit_code")
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int)
    ):
        raise ValueError("external_agent_result_exit_code_invalid")
    receipt = value.get("receipt")
    if not isinstance(receipt, Mapping):
        raise ValueError("external_agent_result_v2_receipt_invalid")
    required_receipt_fields = {
        "schema_version",
        "classification",
        "command_recorded",
        "command_argument_count",
        "duration_ms",
        "instruction_recorded",
        "workspace_recorded",
        "instruction_sha256",
        "instruction_chars",
        "launch_binding_digest",
    }
    if set(receipt) != required_receipt_fields:
        raise ValueError("external_agent_result_v2_receipt_fields_invalid")
    if receipt.get("schema_version") != EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION:
        raise ValueError("external_agent_result_v2_receipt_schema_unsupported")
    classification = receipt.get("classification")
    if (
        not isinstance(classification, str)
        or classification not in _TERMINAL_RESULT_CLASSIFICATIONS
    ):
        raise ValueError("external_agent_result_classification_invalid")
    terminal_state = (classification, status, exit_code)
    if not (
        terminal_state == ("solver_completed", "succeeded", 0)
        or (
            classification == "solver_exited_nonzero"
            and status == "failed"
            and isinstance(exit_code, int)
            and not isinstance(exit_code, bool)
            and exit_code != 0
        )
        or terminal_state == ("solver_startup_failed", "failed", None)
    ):
        raise ValueError("external_agent_result_v2_terminal_state_invalid")
    for field in (
        "launch_binding_digest",
        "instruction_sha256",
    ):
        digest = receipt.get(field)
        if not isinstance(digest, str) or _sha256_digest(digest, field=field) != digest:
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    for field in ("command_argument_count", "instruction_chars"):
        _positive_int(receipt.get(field), field=field)
    _non_negative_int(receipt.get("duration_ms"), field="duration_ms")
    if (
        receipt.get("command_recorded") is not False
        or receipt.get("instruction_recorded") is not False
        or receipt.get("workspace_recorded") is not False
    ):
        raise ValueError("external_agent_result_v2_receipt_contract_invalid")
    return dict(value)


def run_external_agent_phase(
    request: Mapping[str, Any],
    *,
    solver_command: Sequence[str],
    request_path: Path | None = None,
) -> dict[str, Any]:
    """Execute one runner-owned solver command from an external-agent request."""

    (
        instruction,
        workspace,
        timeout_seconds,
        containment_kind,
        containment_verification_ref,
        launch_binding_digest,
    ) = _validate_request(request)
    command = _validate_solver_command(solver_command)
    environment = {
        "LOOPX_EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION": str(request["schema_version"]),
        "LOOPX_EXTERNAL_AGENT_INSTRUCTION_SHA256": _sha256(instruction),
        "LOOPX_EXTERNAL_AGENT_INSTRUCTION_CHARS": str(len(instruction)),
        "LOOPX_EXTERNAL_AGENT_WORKSPACE": str(workspace),
        "LOOPX_EXTERNAL_AGENT_TIMEOUT_SECONDS": str(timeout_seconds),
    }
    if launch_binding_digest is not None:
        environment["LOOPX_BENCHMARK_LAUNCH_BINDING_DIGEST"] = launch_binding_digest
    if request_path is not None:
        environment["LOOPX_EXTERNAL_AGENT_REQUEST"] = str(request_path)
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=workspace,
            env=_solver_environment(environment),
            stdin=subprocess.PIPE,
            stdout=None,
            stderr=None,
            text=True,
        )
        process.communicate(instruction)
        exit_code = process.returncode
    except OSError:
        return _result(
            status="failed",
            exit_code=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            instruction=instruction,
            command=command,
            classification="solver_startup_failed",
            containment_kind=containment_kind,
            containment_verification_ref=containment_verification_ref,
            launch_binding_digest=launch_binding_digest,
        )

    return _result(
        status="succeeded" if exit_code == 0 else "failed",
        exit_code=exit_code,
        duration_ms=int((time.monotonic() - started) * 1000),
        instruction=instruction,
        command=command,
        classification=(
            "solver_completed" if exit_code == 0 else "solver_exited_nonzero"
        ),
        containment_kind=containment_kind,
        containment_verification_ref=containment_verification_ref,
        launch_binding_digest=launch_binding_digest,
    )


def write_external_agent_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(dict(result), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def execute_external_agent_request(
    *,
    request_path: Path,
    result_path: Path,
    solver_command: Sequence[str],
    execute: bool,
) -> dict[str, Any]:
    """Validate one request and optionally run its solver command."""

    if execute:
        result_path.unlink(missing_ok=True)
    try:
        command = _validate_solver_command(solver_command)
        request = _load_json_object(request_path)
        (
            instruction,
            _workspace,
            _timeout_seconds,
            containment_kind,
            containment_verification_ref,
            launch_binding_digest,
        ) = _validate_request(request)
        result = (
            run_external_agent_phase(
                request,
                solver_command=command,
                request_path=request_path,
            )
            if execute
            else _result(
                status="succeeded",
                exit_code=0,
                duration_ms=0,
                instruction=instruction,
                command=command,
                classification="request_validated_not_executed",
                containment_kind=containment_kind,
                containment_verification_ref=containment_verification_ref,
            )
        )
    except (TypeError, ValueError):
        result = _result(
            status="failed",
            exit_code=None,
            duration_ms=0,
            instruction=None,
            command=(),
            classification="agent_phase_input_invalid",
        )
    if execute:
        write_external_agent_result(result_path, result)
    return result
