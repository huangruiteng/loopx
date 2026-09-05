"""Run bounded external-agent segments under runner-owned containment."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...registry import atomic_write_json
from .external_agent import (
    EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
    BenchmarkContinuationDecision,
    _load_json_object,
    _positive_int,
    _result,
    _sha256,
    _sha256_digest,
    _solver_environment,
    _validate_request,
    _validate_solver_command,
    build_benchmark_continuation_decision,
    normalize_benchmark_public_progress,
    write_external_agent_result,
)

BENCHMARK_CONTINUATION_PRIVATE_EVIDENCE_SCHEMA_VERSION = (
    "benchmark_continuation_private_evidence_v0"
)

SegmentRunner = Callable[[Sequence[str], Path, Mapping[str, str], str, Path], int]
ProgressRunner = Callable[
    [Sequence[str], Path, Mapping[str, str], int], Mapping[str, Any]
]
Clock = Callable[[], float]
_PROGRESS_PROBE_TIMEOUT_CAP_MS = 30_000


class BenchmarkSegmentTimeout(RuntimeError):
    pass


def _continuation_instruction(instruction: str, progress: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            instruction,
            "",
            "LoopX continuation:",
            (
                "- Public progress: "
                f"{progress['completed_unit_count']}/{progress['total_unit_count']} "
                "units complete."
            ),
            "- Continue from the current workspace state.",
            "- Re-read the task and requirement files in the workspace.",
            "- Preserve completed work and repair regressions before finishing.",
        ]
    )


def _private_evidence_root(path: Path, *, execute: bool) -> Path:
    root = path.expanduser()
    if not root.is_absolute() or root.is_symlink():
        raise ValueError("benchmark_private_evidence_root_invalid")
    workspace = Path.cwd().resolve()
    resolved_root = root.resolve()
    if (
        resolved_root == workspace
        or resolved_root in workspace.parents
        or workspace in resolved_root.parents
    ):
        raise ValueError("benchmark_private_evidence_root_overlaps_workspace")
    if execute:
        root.mkdir(parents=True, exist_ok=True)
        root.chmod(0o700)
    if root.exists() and not root.is_dir():
        raise ValueError("benchmark_private_evidence_root_invalid")
    if not execute and not root.exists():
        return root
    if root.is_dir() and any(root.iterdir()):
        raise ValueError("benchmark_private_evidence_root_not_clean")
    return root


def _write_private_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_json(path, dict(payload))
    path.chmod(0o600)


def _run_solver_segment(
    command: Sequence[str],
    workspace: Path,
    environment: Mapping[str, str],
    instruction: str,
    stdout_path: Path,
) -> int:
    try:
        timeout_ms_value = int(environment["LOOPX_BENCHMARK_SEGMENT_TIMEOUT_MS"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("segment_timeout_ms must be a positive integer") from exc
    timeout_ms = _positive_int(timeout_ms_value, field="segment_timeout_ms")
    descriptor = os.open(stdout_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stdout:
        process_options: dict[str, Any] = {}
        if os.name == "posix":
            process_options["start_new_session"] = True
        elif os.name == "nt":  # pragma: no cover - Windows-only branch.
            process_options["creationflags"] = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP"
            )
        process = subprocess.Popen(
            list(command),
            cwd=workspace,
            env=dict(environment),
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            text=True,
            **process_options,
        )
        try:
            process.communicate(instruction, timeout=timeout_ms / 1000)
        except subprocess.TimeoutExpired as exc:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif os.name == "nt":  # pragma: no cover - Windows-only branch.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:  # pragma: no cover - unsupported platform fallback.
                process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:  # pragma: no cover - unsupported platform fallback.
                    process.kill()
                process.wait()
            raise BenchmarkSegmentTimeout from exc
    if process.returncode is None:
        raise RuntimeError("benchmark_solver_returncode_missing")
    return int(process.returncode)


def _run_progress_probe(
    command: Sequence[str],
    workspace: Path,
    environment: Mapping[str, str],
    timeout_ms: int,
) -> Mapping[str, Any]:
    bounded_timeout_ms = _positive_int(timeout_ms, field="progress_probe_timeout_ms")
    completed = subprocess.run(
        list(command),
        cwd=workspace,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=bounded_timeout_ms / 1000,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("benchmark_progress_probe_failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("benchmark_progress_probe_output_invalid") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("benchmark_progress_probe_output_invalid")
    return payload


def _remaining_budget_ms(*, started: float, total_budget_ms: int, clock: Clock) -> int:
    elapsed_ms = max(0, int((clock() - started) * 1000))
    return max(0, total_budget_ms - elapsed_ms)


def _run_bounded_progress_probe(
    progress_runner: ProgressRunner,
    command: Sequence[str],
    workspace: Path,
    environment: Mapping[str, str],
    *,
    started: float,
    total_budget_ms: int,
    clock: Clock,
) -> Mapping[str, Any]:
    timeout_ms = min(
        _PROGRESS_PROBE_TIMEOUT_CAP_MS,
        _remaining_budget_ms(
            started=started, total_budget_ms=total_budget_ms, clock=clock
        ),
    )
    if timeout_ms == 0:
        raise subprocess.TimeoutExpired(command, 0)
    return progress_runner(command, workspace, environment, timeout_ms)


def _private_evidence(
    *,
    instruction: str,
    expected_total_unit_count: int,
    max_agent_segments: int,
    total_budget_ms: int,
    initial_progress: Mapping[str, Any] | None,
    segments: Sequence[Mapping[str, Any]],
    terminal_decision: str,
) -> dict[str, Any]:
    return {
        "schema_version": BENCHMARK_CONTINUATION_PRIVATE_EVIDENCE_SCHEMA_VERSION,
        "instruction_sha256": _sha256(instruction),
        "expected_total_unit_count": expected_total_unit_count,
        "max_agent_segments": max_agent_segments,
        "total_budget_ms": total_budget_ms,
        "initial_progress": (
            dict(initial_progress) if initial_progress is not None else None
        ),
        "segments": [dict(segment) for segment in segments],
        "terminal_decision": terminal_decision,
        "raw_task_recorded": False,
        "unit_ids_recorded": False,
        "verifier_evidence_recorded": False,
    }


def _public_result(
    *,
    status: str,
    exit_code: int | None,
    classification: str,
    started: float,
    clock: Clock,
    instruction: str,
    command: Sequence[str],
    containment_kind: str,
    containment_verification_ref: str,
) -> dict[str, Any]:
    result: dict[str, Any] = _result(
        status=status,
        exit_code=exit_code,
        duration_ms=max(0, int((clock() - started) * 1000)),
        instruction=instruction,
        command=command,
        classification=classification,
        containment_kind=containment_kind,
        containment_verification_ref=containment_verification_ref,
    )
    return result


def run_external_agent_continuation_phase(
    request: Mapping[str, Any],
    *,
    solver_command: Sequence[str],
    progress_command: Sequence[str],
    expected_first_prompt_sha256: str,
    expected_total_unit_count: int,
    max_agent_segments: int,
    private_evidence_root: Path,
    request_path: Path | None = None,
    segment_runner: SegmentRunner = _run_solver_segment,
    progress_runner: ProgressRunner = _run_progress_probe,
    clock: Clock = time.monotonic,
) -> dict[str, Any]:
    """Run bounded solver segments while the benchmark runner owns containment."""

    (
        instruction,
        workspace,
        timeout_seconds,
        containment_kind,
        containment_verification_ref,
    ) = _validate_request(request)
    command = _validate_solver_command(solver_command)
    progress_argv = _validate_solver_command(progress_command)
    expected_prompt = _sha256_digest(
        expected_first_prompt_sha256, field="expected_first_prompt_sha256"
    )
    expected_total = _positive_int(
        expected_total_unit_count, field="expected_total_unit_count"
    )
    max_segments = _positive_int(max_agent_segments, field="max_agent_segments")
    evidence_root = _private_evidence_root(private_evidence_root, execute=True)
    evidence_path = evidence_root / "continuation-private.json"
    total_budget_ms = max(1, int(timeout_seconds * 1000))
    environment = {
        "LOOPX_EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION": (
            EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION
        ),
        "LOOPX_EXTERNAL_AGENT_INSTRUCTION_SHA256": _sha256(instruction),
        "LOOPX_EXTERNAL_AGENT_INSTRUCTION_CHARS": str(len(instruction)),
        "LOOPX_EXTERNAL_AGENT_WORKSPACE": str(workspace),
        "LOOPX_EXTERNAL_AGENT_TIMEOUT_SECONDS": str(timeout_seconds),
    }
    if request_path is not None:
        environment["LOOPX_EXTERNAL_AGENT_REQUEST"] = str(request_path)
    safe_environment = _solver_environment(environment)
    started = clock()
    segments: list[dict[str, Any]] = []
    initial_progress: dict[str, int | str] | None = None
    classification = "solver_completed"
    status = "succeeded"
    result_exit_code: int | None = 0
    terminal_decision = "not_started"

    try:
        initial_progress = normalize_benchmark_public_progress(
            _run_bounded_progress_probe(
                progress_runner,
                progress_argv,
                workspace,
                safe_environment,
                started=started,
                total_budget_ms=total_budget_ms,
                clock=clock,
            )
        )
    except subprocess.TimeoutExpired:
        terminal_decision = "progress_probe_timed_out"
        classification = "continuation_progress_probe_timed_out"
        status = "failed"
        result_exit_code = None
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        terminal_decision = "progress_probe_failed"
        classification = "continuation_progress_probe_failed"
        status = "failed"
        result_exit_code = None

    if initial_progress is not None:
        if int(initial_progress["total_unit_count"]) != expected_total:
            terminal_decision = "task_shape_mismatch"
            classification = "continuation_task_shape_mismatch"
            status = "failed"
            result_exit_code = None
        elif _sha256(instruction) != expected_prompt:
            terminal_decision = "first_prompt_mismatch"
            classification = "continuation_first_prompt_mismatch"
            status = "failed"
            result_exit_code = None
        elif int(initial_progress["completed_unit_count"]) == expected_total:
            terminal_decision = BenchmarkContinuationDecision.STOP_COMPLETE.value
            classification = "continuation_not_needed_complete"

    previous_progress = initial_progress
    for segment_index in range(1, max_segments + 1):
        if status == "failed" or terminal_decision == (
            BenchmarkContinuationDecision.STOP_COMPLETE.value
        ):
            break
        elapsed_before_ms = total_budget_ms - _remaining_budget_ms(
            started=started, total_budget_ms=total_budget_ms, clock=clock
        )
        remaining_segments = max_segments - segment_index + 1
        remaining_budget_ms = max(0, total_budget_ms - elapsed_before_ms)
        if remaining_budget_ms == 0:
            terminal_decision = BenchmarkContinuationDecision.STOP_TIME_BUDGET.value
            classification = "continuation_time_budget_exhausted"
            break
        segment_timeout_ms = max(1, remaining_budget_ms // remaining_segments)
        segment_environment = {
            **safe_environment,
            "LOOPX_BENCHMARK_SEGMENT_INDEX": str(segment_index),
            "LOOPX_BENCHMARK_SEGMENT_TIMEOUT_MS": str(segment_timeout_ms),
        }
        prompt_kind = "original" if segment_index == 1 else "continuation"
        if previous_progress is None:
            raise RuntimeError("benchmark_continuation_progress_missing")
        segment_instruction = (
            instruction
            if segment_index == 1
            else _continuation_instruction(instruction, previous_progress)
        )
        stdout_path = evidence_root / f"segment-{segment_index:04d}.stdout.jsonl"
        segment_started = clock()
        segment_timed_out = False
        try:
            segment_exit_code = segment_runner(
                command,
                workspace,
                segment_environment,
                segment_instruction,
                stdout_path,
            )
        except BenchmarkSegmentTimeout:
            segment_exit_code = None
            segment_timed_out = True
        except (OSError, RuntimeError, subprocess.SubprocessError):
            segment_exit_code = -1
        segment_record: dict[str, Any] = {
            "segment_index": segment_index,
            "prompt_kind": prompt_kind,
            "prompt_sha256": _sha256(segment_instruction),
            "stdout_file": stdout_path.name,
            "exit_code": segment_exit_code,
            "timed_out": segment_timed_out,
            "duration_ms": max(0, int((clock() - segment_started) * 1000)),
        }
        segments.append(segment_record)
        if stdout_path.is_file():
            stdout_path.chmod(0o600)
        if not stdout_path.is_file() or stdout_path.stat().st_size == 0:
            terminal_decision = "segment_evidence_missing"
            classification = "continuation_segment_evidence_missing"
            status = "failed"
            result_exit_code = None
            segment_record["stdout_status"] = "missing_or_empty"
            break
        if segment_exit_code != 0 and not segment_timed_out:
            terminal_decision = "solver_exited_nonzero"
            classification = "solver_exited_nonzero"
            status = "failed"
            result_exit_code = segment_exit_code
            break
        try:
            progress = normalize_benchmark_public_progress(
                _run_bounded_progress_probe(
                    progress_runner,
                    progress_argv,
                    workspace,
                    safe_environment,
                    started=started,
                    total_budget_ms=total_budget_ms,
                    clock=clock,
                )
            )
        except subprocess.TimeoutExpired:
            terminal_decision = "progress_probe_timed_out"
            classification = "continuation_progress_probe_timed_out"
            status = "failed"
            result_exit_code = None
            segment_record["progress_probe_status"] = "timed_out"
            break
        except (OSError, subprocess.SubprocessError, TypeError, ValueError):
            terminal_decision = "progress_probe_failed"
            classification = "continuation_progress_probe_failed"
            status = "failed"
            result_exit_code = None
            segment_record["progress_probe_status"] = "failed"
            break
        decision = build_benchmark_continuation_decision(
            progress,
            expected_first_prompt_sha256=expected_prompt,
            observed_first_prompt_sha256=_sha256(instruction),
            expected_total_unit_count=expected_total,
            previous_completed_unit_count=int(
                previous_progress["completed_unit_count"]
            ),
            completed_segment_count=segment_index,
            max_agent_segments=max_segments,
            elapsed_ms=max(0, int((clock() - started) * 1000)),
            total_budget_ms=total_budget_ms,
        )
        terminal_decision = str(decision["decision"])
        segment_record["progress"] = progress
        segment_record["decision"] = decision
        if decision["continuation_allowed"] is True:
            previous_progress = progress
            continue
        if terminal_decision in {
            BenchmarkContinuationDecision.STOP_PROGRESS_REGRESSION.value,
            BenchmarkContinuationDecision.STOP_PROMPT_MISMATCH.value,
            BenchmarkContinuationDecision.STOP_TASK_SHAPE_MISMATCH.value,
        }:
            classification = "continuation_contract_mismatch"
            status = "failed"
            result_exit_code = None
        elif terminal_decision == BenchmarkContinuationDecision.STOP_ROUND_LIMIT.value:
            classification = "continuation_segment_limit_reached"
        elif terminal_decision == BenchmarkContinuationDecision.STOP_TIME_BUDGET.value:
            classification = "continuation_time_budget_exhausted"
        break

    _write_private_evidence(
        evidence_path,
        _private_evidence(
            instruction=instruction,
            expected_total_unit_count=expected_total,
            max_agent_segments=max_segments,
            total_budget_ms=total_budget_ms,
            initial_progress=initial_progress,
            segments=segments,
            terminal_decision=terminal_decision,
        ),
    )
    return _public_result(
        status=status,
        exit_code=result_exit_code,
        classification=classification,
        started=started,
        clock=clock,
        instruction=instruction,
        command=command,
        containment_kind=containment_kind,
        containment_verification_ref=containment_verification_ref,
    )


def execute_external_agent_continuation_request(
    *,
    request_path: Path,
    result_path: Path,
    solver_command: Sequence[str],
    progress_command: Sequence[str],
    expected_first_prompt_sha256: str,
    expected_total_unit_count: int,
    max_agent_segments: int,
    private_evidence_root: Path,
    execute: bool,
) -> dict[str, Any]:
    """Validate or execute one bounded continuation phase."""

    evidence_root = private_evidence_root.expanduser().resolve()
    protected_paths = {
        request_path.expanduser().resolve(),
        result_path.expanduser().resolve(),
    }
    if any(
        path == evidence_root or evidence_root in path.parents
        for path in protected_paths
    ):
        raise ValueError("benchmark_private_evidence_result_path_overlap")
    if execute:
        result_path.unlink(missing_ok=True)
    try:
        command = _validate_solver_command(solver_command)
        progress_argv = _validate_solver_command(progress_command)
        request = _load_json_object(request_path)
        (
            instruction,
            _workspace,
            _timeout_seconds,
            containment_kind,
            containment_verification_ref,
        ) = _validate_request(request)
        _sha256_digest(
            expected_first_prompt_sha256, field="expected_first_prompt_sha256"
        )
        _positive_int(expected_total_unit_count, field="expected_total_unit_count")
        _positive_int(max_agent_segments, field="max_agent_segments")
        _private_evidence_root(evidence_root, execute=False)
        result = (
            run_external_agent_continuation_phase(
                request,
                solver_command=command,
                progress_command=progress_argv,
                expected_first_prompt_sha256=expected_first_prompt_sha256,
                expected_total_unit_count=expected_total_unit_count,
                max_agent_segments=max_agent_segments,
                private_evidence_root=evidence_root,
                request_path=request_path,
            )
            if execute
            else _result(
                status="succeeded",
                exit_code=0,
                duration_ms=0,
                instruction=instruction,
                command=command,
                classification="continuation_request_validated_not_executed",
                containment_kind=containment_kind,
                containment_verification_ref=containment_verification_ref,
            )
        )
    except (OSError, TypeError, ValueError):
        result = _result(
            status="failed",
            exit_code=None,
            duration_ms=0,
            instruction=None,
            command=(),
            classification="continuation_phase_input_invalid",
        )
    write_external_agent_result(result_path, result)
    return result


__all__ = [
    "BENCHMARK_CONTINUATION_PRIVATE_EVIDENCE_SCHEMA_VERSION",
    "execute_external_agent_continuation_request",
    "run_external_agent_continuation_phase",
]
