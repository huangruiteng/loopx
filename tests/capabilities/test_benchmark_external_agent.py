from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

from loopx.capabilities.benchmark_toolkit import (
    benchmark_integrity_policy_sha256,
    build_benchmark_launch_admission_receipt,
)
from loopx.capabilities.benchmark_toolkit.external_agent import (
    BENCHMARK_CONTINUATION_DECISION_SCHEMA_VERSION,
    EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION,
    EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
    EXTERNAL_AGENT_RESULT_SCHEMA_VERSION,
    EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION,
    EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
    build_benchmark_continuation_decision,
    execute_external_agent_request,
    normalize_external_agent_result_v2,
)
import loopx.capabilities.benchmark_toolkit.external_agent as external_agent
from loopx.cli import main


def _request(workspace: Path) -> dict[str, object]:
    return {
        "schema_version": EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION,
        "instruction": "Implement the requested task without reading evaluator files.",
        "workspace": str(workspace),
        "timeout_seconds": 10,
        "containment": {
            "schema_version": "external_agent_containment_v1",
            "kind": "container",
            "timeout_owner": "runner",
            "termination_postcondition": "drained_before_result_consumption",
            "verification": {
                "schema_version": "external_agent_containment_verification_v1",
                "status": "verified",
                "authority": "runner",
                "receipt_ref": "runner-containment-test",
            },
        },
    }


def _request_v2(workspace: Path) -> dict[str, object]:
    request = _request(workspace)
    instruction = str(request["instruction"])
    request["schema_version"] = EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION
    request["containment"]["termination_postcondition"] = (  # type: ignore[index]
        "destroyed_before_result_consumption"
    )
    request["containment"]["verification"]["status"] = "pending"  # type: ignore[index]
    request["launch_admission"] = build_benchmark_launch_admission_receipt(
        benchmark_id="fixture@v0",
        case_id="suite/case-1",
        run_id="run-1",
        arm_id="treatment",
        instruction_sha256=hashlib.sha256(instruction.encode()).hexdigest(),
        integrity_policy_sha256=benchmark_integrity_policy_sha256(None),
        expected_provider="trae",
        expected_model="GPT-5.4",
        containment_binding_sha256=hashlib.sha256(
            b"runner-containment-test"
        ).hexdigest(),
        runtime_binding_sha256="d" * 64,
        credential_isolation={
            "mechanism": "gateway",
            "authority": "runner",
            "evidence_sha256": "e" * 64,
        },
        controller_isolation={
            "mechanism": "namespace",
            "authority": "runner",
            "evidence_sha256": "f" * 64,
        },
        runner_authority="runner",
        provider_authority="trae-adapter",
        issued_at="2026-09-03T00:30:00Z",
    )
    return request


def test_external_agent_v2_validates_full_launch_receipt_and_echoes_digest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["schema_version"] == EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION
    assert set(result) == {"schema_version", "status", "exit_code", "receipt"}
    assert result["receipt"]["schema_version"] == (
        EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION
    )
    assert (
        result["receipt"]["launch_binding_digest"]
        == request["launch_admission"]["launch_binding_digest"]
    )
    assert not any(field.startswith("containment_") for field in result["receipt"])
    assert "timeout_owner" not in result["receipt"]
    assert normalize_external_agent_result_v2(result) == result


def test_external_agent_v2_exports_actual_request_schema_to_solver(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=tmp_path / "result.json",
        solver_command=[
            sys.executable,
            "-c",
            (
                "import os, pathlib; "
                "pathlib.Path('schema.txt').write_text("
                "os.environ['LOOPX_EXTERNAL_AGENT_REQUEST_SCHEMA_VERSION'])"
            ),
        ],
        execute=True,
    )

    assert result["status"] == "succeeded"
    assert (
        workspace / "schema.txt"
    ).read_text() == EXTERNAL_AGENT_REQUEST_V2_SCHEMA_VERSION


@pytest.mark.parametrize("mutation", ["instruction", "binding", "extra_field"])
def test_external_agent_v2_fails_closed_on_unbound_or_invalid_request(
    tmp_path: Path,
    monkeypatch,
    mutation: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    if mutation == "instruction":
        request["instruction"] = "different instruction"
    elif mutation == "binding":
        request["launch_admission"]["run_id"] = "run-2"
    else:
        request["unexpected"] = True
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["schema_version"] == EXTERNAL_AGENT_RESULT_SCHEMA_VERSION
    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"
    assert "launch_binding_digest" not in result["receipt"]


def test_external_agent_v2_rejects_containment_receipt_ref_digest_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    request["containment"]["verification"]["receipt_ref"] = "other-ref"
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


def test_external_agent_result_v2_rejects_unknown_classification_or_extra_field() -> (
    None
):
    result = {
        "schema_version": EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
        "status": "failed",
        "exit_code": 1,
        "receipt": {
            "schema_version": EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION,
            "classification": "unknown",
            "command_recorded": False,
            "command_argument_count": 1,
            "duration_ms": 1,
            "instruction_recorded": False,
            "workspace_recorded": False,
            "instruction_sha256": "b" * 64,
            "instruction_chars": 1,
            "launch_binding_digest": "a" * 64,
        },
    }
    with pytest.raises(ValueError, match="classification_invalid"):
        normalize_external_agent_result_v2(result)
    result["receipt"]["classification"] = "solver_exited_nonzero"
    result["extra"] = True
    with pytest.raises(ValueError, match="fields_invalid"):
        normalize_external_agent_result_v2(result)


def _external_agent_result_v2(
    *,
    classification: str = "solver_completed",
    status: str = "succeeded",
    exit_code: object = 0,
) -> dict[str, object]:
    return {
        "schema_version": EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
        "status": status,
        "exit_code": exit_code,
        "receipt": {
            "schema_version": EXTERNAL_AGENT_PHASE_RECEIPT_V2_SCHEMA_VERSION,
            "classification": classification,
            "command_recorded": False,
            "command_argument_count": 1,
            "duration_ms": 1,
            "instruction_recorded": False,
            "workspace_recorded": False,
            "instruction_sha256": "b" * 64,
            "instruction_chars": 1,
            "launch_binding_digest": "a" * 64,
        },
    }


@pytest.mark.parametrize(
    ("classification", "status", "exit_code"),
    [
        ("solver_completed", "succeeded", 0),
        ("solver_exited_nonzero", "failed", 7),
        ("solver_startup_failed", "failed", None),
    ],
)
def test_external_agent_result_v2_accepts_only_terminal_triples(
    classification: str, status: str, exit_code: int | None
) -> None:
    result = _external_agent_result_v2(
        classification=classification, status=status, exit_code=exit_code
    )

    assert normalize_external_agent_result_v2(result) == result


def test_external_agent_result_v2_rejects_self_reported_containment_claim() -> None:
    result = _external_agent_result_v2()
    result["receipt"]["containment_termination_postcondition"] = (  # type: ignore[index]
        "destroyed_before_result_consumption"
    )

    with pytest.raises(ValueError, match="receipt_fields_invalid"):
        normalize_external_agent_result_v2(result)


@pytest.mark.parametrize(
    ("classification", "status", "exit_code"),
    [
        ("request_validated_not_executed", "succeeded", 0),
        ("solver_completed", "failed", 0),
        ("solver_completed", "succeeded", 1),
        ("solver_exited_nonzero", "failed", 0),
        ("solver_exited_nonzero", "succeeded", 1),
        ("solver_startup_failed", "failed", 1),
    ],
)
def test_external_agent_result_v2_rejects_non_terminal_or_mismatched_triples(
    classification: str, status: str, exit_code: int | None
) -> None:
    with pytest.raises(
        ValueError, match="classification_invalid|terminal_state_invalid"
    ):
        normalize_external_agent_result_v2(
            _external_agent_result_v2(
                classification=classification, status=status, exit_code=exit_code
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("command_argument_count", -1),
        ("command_argument_count", 0),
        ("command_argument_count", True),
        ("duration_ms", -1),
        ("duration_ms", False),
        ("instruction_chars", -1),
        ("instruction_chars", 0),
        ("instruction_chars", 1.0),
    ],
)
def test_external_agent_result_v2_rejects_invalid_numeric_receipt_fields(
    field: str, value: object
) -> None:
    result = _external_agent_result_v2()
    result["receipt"][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match="positive integer|non-negative integer"):
        normalize_external_agent_result_v2(result)


def test_external_agent_result_v2_rejects_bool_exit_code() -> None:
    with pytest.raises(ValueError, match="exit_code_invalid"):
        normalize_external_agent_result_v2(
            _external_agent_result_v2(
                classification="solver_exited_nonzero",
                status="failed",
                exit_code=True,
            )
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("status", True, "status_invalid"),
        ("classification", True, "classification_invalid"),
        ("instruction_sha256", 1, "lowercase SHA-256 digest"),
    ],
)
def test_external_agent_result_v2_rejects_bool_or_numeric_string_fields(
    field: str, value: object, error: str
) -> None:
    result = _external_agent_result_v2()
    if field == "status":
        result[field] = value
    else:
        result["receipt"][field] = value  # type: ignore[index]

    with pytest.raises(ValueError, match=error):
        normalize_external_agent_result_v2(result)


def test_external_agent_v2_dry_run_stays_outside_terminal_result_schema(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request_v2(workspace)), encoding="utf-8")

    preview = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=False,
    )

    assert preview["schema_version"] == EXTERNAL_AGENT_RESULT_SCHEMA_VERSION
    assert preview["receipt"]["classification"] == ("request_validated_not_executed")
    assert "launch_binding_digest" not in preview["receipt"]
    with pytest.raises(ValueError, match="schema_unsupported"):
        normalize_external_agent_result_v2(preview)


def test_external_agent_dry_run_keeps_existing_terminal_result_unchanged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request_v2(workspace)), encoding="utf-8")
    existing = '{"schema_version":"external_agent_result_v2","terminal":true}\n'
    result_path.write_text(existing, encoding="utf-8")

    preview = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=False,
    )

    assert preview["receipt"]["classification"] == ("request_validated_not_executed")
    assert result_path.read_text(encoding="utf-8") == existing


def test_external_agent_dry_run_does_not_create_result_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request_v2(workspace)), encoding="utf-8")

    preview = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=False,
    )

    assert preview["receipt"]["classification"] == ("request_validated_not_executed")
    assert not result_path.exists()


def _progress(completed: int, total: int = 5) -> dict[str, object]:
    return {
        "schema_version": "benchmark_public_progress_v0",
        "total_unit_count": total,
        "completed_unit_count": completed,
    }


def test_benchmark_continuation_decision_continues_with_bounded_budget() -> None:
    decision = build_benchmark_continuation_decision(
        _progress(2),
        expected_first_prompt_sha256="a" * 64,
        observed_first_prompt_sha256="a" * 64,
        expected_total_unit_count=5,
        previous_completed_unit_count=1,
        completed_segment_count=1,
        max_agent_segments=3,
        elapsed_ms=400,
        total_budget_ms=1000,
    )

    assert decision["schema_version"] == BENCHMARK_CONTINUATION_DECISION_SCHEMA_VERSION
    assert decision["decision"] == "continue"
    assert decision["reason_code"] == "requirements_remain_after_progress"
    assert decision["next_segment_timeout_ms"] == 300
    assert decision["first_prompt_matches"] is True
    assert decision["first_prompt_digest_recorded"] is False
    assert decision["raw_task_recorded"] is False
    assert decision["read_only"] is True
    assert decision["host_invoked"] is False
    assert decision["state_written"] is False


@pytest.mark.parametrize(
    ("progress", "overrides", "decision", "reason"),
    [
        (_progress(5), {}, "stop_complete", "all_units_complete"),
        (
            _progress(0),
            {},
            "stop_progress_regression",
            "public_progress_regressed",
        ),
        (
            _progress(2),
            {"observed_first_prompt_sha256": "b" * 64},
            "stop_prompt_mismatch",
            "first_prompt_digest_mismatch",
        ),
        (
            _progress(2),
            {"expected_total_unit_count": 6},
            "stop_task_shape_mismatch",
            "total_unit_count_mismatch",
        ),
        (
            _progress(2),
            {"elapsed_ms": 1000},
            "stop_time_budget",
            "total_agent_budget_exhausted",
        ),
        (
            _progress(2),
            {"completed_segment_count": 3},
            "stop_round_limit",
            "agent_segment_limit_reached",
        ),
    ],
)
def test_benchmark_continuation_decision_stops_at_frozen_boundaries(
    progress: dict[str, object],
    overrides: dict[str, object],
    decision: str,
    reason: str,
) -> None:
    arguments: dict[str, object] = {
        "expected_first_prompt_sha256": "a" * 64,
        "observed_first_prompt_sha256": "a" * 64,
        "expected_total_unit_count": 5,
        "previous_completed_unit_count": 1,
        "completed_segment_count": 1,
        "max_agent_segments": 3,
        "elapsed_ms": 400,
        "total_budget_ms": 1000,
    }
    arguments.update(overrides)

    result = build_benchmark_continuation_decision(
        progress,
        expected_first_prompt_sha256=str(arguments["expected_first_prompt_sha256"]),
        observed_first_prompt_sha256=str(arguments["observed_first_prompt_sha256"]),
        expected_total_unit_count=int(arguments["expected_total_unit_count"]),
        previous_completed_unit_count=int(arguments["previous_completed_unit_count"]),
        completed_segment_count=int(arguments["completed_segment_count"]),
        max_agent_segments=int(arguments["max_agent_segments"]),
        elapsed_ms=int(arguments["elapsed_ms"]),
        total_budget_ms=int(arguments["total_budget_ms"]),
    )

    assert result["decision"] == decision
    assert result["reason_code"] == reason
    assert result["continuation_allowed"] is False
    assert result["next_segment_timeout_ms"] == 0


def test_benchmark_continuation_decision_rejects_invalid_public_progress() -> None:
    with pytest.raises(ValueError, match="completed_unit_count exceeds"):
        build_benchmark_continuation_decision(
            _progress(6),
            expected_first_prompt_sha256="a" * 64,
            observed_first_prompt_sha256="a" * 64,
            expected_total_unit_count=5,
            previous_completed_unit_count=1,
            completed_segment_count=1,
            max_agent_segments=3,
            elapsed_ms=400,
            total_budget_ms=1000,
        )


def test_benchmark_continuation_decision_cli_is_read_only_and_content_free(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_path = tmp_path / "private-progress.json"
    private_path.write_text(json.dumps(_progress(2)), encoding="utf-8")
    digest = "a" * 64

    exit_code = main(
        [
            "--format",
            "json",
            "benchmark",
            "continuation-decision",
            "--progress-json",
            str(private_path),
            "--expected-first-prompt-sha256",
            digest,
            "--observed-first-prompt-sha256",
            digest,
            "--expected-total-unit-count",
            "5",
            "--previous-completed-unit-count",
            "1",
            "--completed-segment-count",
            "1",
            "--max-agent-segments",
            "2",
            "--elapsed-ms",
            "400",
            "--total-budget-ms",
            "1000",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 0
    assert payload["decision"] == "continue"
    assert digest not in output
    assert str(tmp_path) not in output
    assert payload["first_prompt_digest_recorded"] is False
    assert payload["path_recorded"] is False
    assert payload["read_only"] is True
    assert payload["host_invoked"] is False
    assert payload["state_written"] is False


def test_benchmark_continuation_decision_cli_fails_closed_without_leaking_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_path = tmp_path / "private-progress.json"
    private_path.write_text("not-json", encoding="utf-8")
    digest = "b" * 64

    exit_code = main(
        [
            "--format",
            "json",
            "benchmark",
            "continuation-decision",
            "--progress-json",
            str(private_path),
            "--expected-first-prompt-sha256",
            digest,
            "--observed-first-prompt-sha256",
            digest,
            "--expected-total-unit-count",
            "5",
            "--previous-completed-unit-count",
            "1",
            "--completed-segment-count",
            "1",
            "--max-agent-segments",
            "2",
            "--elapsed-ms",
            "400",
            "--total-budget-ms",
            "1000",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 1
    assert payload["decision"] == "input_invalid"
    assert digest not in output
    assert str(tmp_path) not in output


def test_external_agent_phase_runs_solver_with_request_reference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    marker = workspace / "marker.txt"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")

    solver = [
        sys.executable,
        "-c",
        (
            "import os\n"
            "from pathlib import Path\n"
            "request = Path(os.environ['LOOPX_EXTERNAL_AGENT_REQUEST'])\n"
            "assert request.is_file()\n"
            "Path('marker.txt').write_text(os.environ['LOOPX_EXTERNAL_AGENT_INSTRUCTION_SHA256'])\n"
        ),
    ]
    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=solver,
        execute=True,
    )

    assert result["schema_version"] == EXTERNAL_AGENT_RESULT_SCHEMA_VERSION
    assert result["status"] == "succeeded"
    assert marker.read_text(encoding="utf-8") == result["receipt"]["instruction_sha256"]
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    assert persisted == result
    rendered = json.dumps(result, sort_keys=True)
    assert str(workspace) not in rendered
    assert "Implement the requested task" not in rendered
    assert "python" not in rendered
    assert result["receipt"]["containment_contract_validated"] is True
    assert result["receipt"]["containment_verification_authority"] == "runner"
    assert result["receipt"]["containment_verification_status"] == "verified"
    assert (
        result["receipt"]["containment_termination_postcondition"]
        == "drained_before_result_consumption"
    )
    assert result["receipt"]["timeout_enforced_locally"] is False
    assert result["receipt"]["timeout_owner"] == "runner"
    assert "runner-containment-test" not in rendered


def test_external_agent_phase_sends_instruction_to_solver_stdin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    instruction = str(_request(workspace)["instruction"])
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")

    solver = [
        sys.executable,
        "-c",
        (
            "import sys\n"
            "from pathlib import Path\n"
            "Path('instruction.txt').write_text(sys.stdin.read(), encoding='utf-8')\n"
        ),
    ]
    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=solver,
        execute=True,
    )

    assert result["status"] == "succeeded"
    assert (workspace / "instruction.txt").read_text(encoding="utf-8") == instruction


def test_external_agent_phase_does_not_inherit_ambient_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    marker = workspace / "ambient-secret.txt"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")
    monkeypatch.setenv("SYNTHETIC_AGENT_SECRET", "must-not-cross-boundary")

    solver = [
        sys.executable,
        "-c",
        (
            "import os\n"
            "from pathlib import Path\n"
            "value = os.environ.get('SYNTHETIC_AGENT_SECRET')\n"
            "Path('ambient-secret.txt').write_text(value or 'absent', encoding='utf-8')\n"
        ),
    ]
    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=solver,
        execute=True,
    )

    assert result["status"] == "succeeded"
    assert marker.read_text(encoding="utf-8") == "absent"


def test_external_agent_phase_requires_runner_owned_containment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request.pop("containment")
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


def test_external_agent_phase_rejects_process_group_before_detached_child_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["containment"]["kind"] = "process_group"  # type: ignore[index]
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    marker = workspace / "escaped-effect.txt"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    child_code = (
        "from pathlib import Path; "
        "Path('escaped-effect.txt').write_text('escaped', encoding='utf-8')"
    )
    solver_code = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}], "
        "start_new_session=True).wait()"
    )

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", solver_code],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"
    assert not marker.exists()


@pytest.mark.parametrize("status", ["declared", "pending"])
def test_external_agent_v1_requires_verified_containment_receipt(
    tmp_path: Path,
    monkeypatch,
    status: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["containment"]["verification"]["status"] = status  # type: ignore[index]
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


@pytest.mark.parametrize("status", ["declared", "verified"])
def test_external_agent_v2_requires_pending_containment_verification(
    tmp_path: Path,
    monkeypatch,
    status: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    request["containment"]["verification"]["status"] = status  # type: ignore[index]
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


def test_external_agent_v1_preserves_legacy_drain_postcondition(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["containment"]["termination_postcondition"] = (  # type: ignore[index]
        "destroyed_before_result_consumption"
    )
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


@pytest.mark.parametrize(
    "termination_postcondition",
    [
        "drained_before_result_consumption",
        "destroyed_before_timeout_result",
    ],
)
def test_external_agent_v2_requires_destroy_before_any_result_consumption(
    tmp_path: Path,
    monkeypatch,
    termination_postcondition: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request_v2(workspace)
    request["containment"]["termination_postcondition"] = (  # type: ignore[index]
        termination_postcondition
    )
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


def test_external_agent_phase_does_not_emit_local_timeout_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request = _request(workspace)
    request["timeout_seconds"] = 0.05
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    started = time.monotonic()

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[
            sys.executable,
            "-c",
            "import time; time.sleep(0.15); raise SystemExit(0)",
        ],
        execute=True,
    )

    assert time.monotonic() - started >= 0.1
    assert result["status"] == "succeeded"
    assert result["receipt"]["classification"] == "solver_completed"


def test_external_agent_phase_removes_stale_result_before_runner_lifecycle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")
    result_path.write_text('{"status":"succeeded"}\n', encoding="utf-8")

    def interrupted_runner(*_args, **_kwargs):
        assert not result_path.exists()
        raise KeyboardInterrupt

    monkeypatch.setattr(
        external_agent,
        "run_external_agent_phase",
        interrupted_runner,
    )

    with pytest.raises(KeyboardInterrupt):
        execute_external_agent_request(
            request_path=request_path,
            result_path=result_path,
            solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
            execute=True,
        )

    assert not result_path.exists()


def test_external_agent_phase_fails_closed_for_invalid_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    result_path = tmp_path / "result.json"
    result = execute_external_agent_request(
        request_path=tmp_path / "missing.json",
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"
    assert json.loads(result_path.read_text(encoding="utf-8")) == result


def test_external_agent_phase_rejects_string_solver_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command="not-an-argv",  # type: ignore[arg-type]
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"


def test_benchmark_agent_phase_cli_reads_environment_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")
    solver = [sys.executable, "-c", "raise SystemExit(0)"]

    monkeypatch.setenv("LOOPSBENCH_EXTERNAL_AGENT_REQUEST", str(request_path))
    monkeypatch.setenv("LOOPSBENCH_EXTERNAL_AGENT_RESULT", str(result_path))
    monkeypatch.setenv("LOOPX_EXTERNAL_AGENT_SOLVER_COMMAND_JSON", json.dumps(solver))

    assert main(["benchmark", "agent-phase", "--execute"]) == 0
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "succeeded"


def test_external_agent_phase_rejects_request_workspace_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    other_workspace = tmp_path / "other-workspace"
    other_workspace.mkdir()
    monkeypatch.chdir(other_workspace)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(_request(workspace)), encoding="utf-8")

    result = execute_external_agent_request(
        request_path=request_path,
        result_path=result_path,
        solver_command=[sys.executable, "-c", "raise SystemExit(0)"],
        execute=True,
    )

    assert result["status"] == "failed"
    assert result["receipt"]["classification"] == "agent_phase_input_invalid"
