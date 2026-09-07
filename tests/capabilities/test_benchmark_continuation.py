from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.capabilities.benchmark_toolkit.continuation import (
    BENCHMARK_CONTINUATION_DECISION_SCHEMA_VERSION,
    build_benchmark_continuation_decision,
)
from loopx.cli import main


@pytest.mark.parametrize("execute", [False, True])
def test_removed_agent_phase_cannot_launch_or_replace_evidence(
    tmp_path: Path, execute: bool,
) -> None:
    marker = tmp_path / "solver-ran"
    result = tmp_path / "result.json"
    result.write_text("existing runner evidence", encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text("{}", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(
        LOOPSBENCH_EXTERNAL_AGENT_REQUEST=str(request),
        LOOPSBENCH_EXTERNAL_AGENT_RESULT=str(result),
        LOOPX_EXTERNAL_AGENT_SOLVER_COMMAND_JSON=json.dumps(
            [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"]
        ),
    )
    completed = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "benchmark", "agent-phase"]
        + (["--execute"] if execute else []),
        env=environment, capture_output=True, text=True, check=False, timeout=30,
    )
    assert completed.returncode == 2
    assert "invalid choice: 'agent-phase'" in completed.stderr
    assert not marker.exists()
    assert result.read_text(encoding="utf-8") == "existing runner evidence"
    assert request.read_text(encoding="utf-8") == "{}"


def test_benchmark_help_exposes_decisions_not_solver_execution(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["benchmark", "--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "continuation-decision" in output
    assert "agent-phase" not in output


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
