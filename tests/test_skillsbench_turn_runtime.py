from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from loopx.benchmark_adapters import skillsbench_turn_runtime as runtime
from loopx.benchmark_adapters.skillsbench_turn_route import (
    SkillsBenchTurnTraceSummary,
    sync_skillsbench_loopx_turn_trace_into_compact,
)


def _config(tmp_path: Path) -> runtime.SkillsBenchTurnRuntimeConfig:
    return runtime.SkillsBenchTurnRuntimeConfig(
        bridge_command="synthetic-bridge",
        validation_command="synthetic-postcondition",
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        runtime_root=tmp_path,
    )


def test_nonzero_validation_probe_does_not_return_private_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": runtime.SKILLSBENCH_BRIDGE_OPERATION_SCHEMA_VERSION,
        "ok": False,
        "exit_code": 17,
        "stdout": "private validation output",
        "stderr": "private validation error",
    }
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    result = runtime.SkillsBenchTurnBridge(_config(tmp_path)).exec(
        "synthetic-postcondition",
        allow_nonzero=True,
    )

    assert result["ok"] is False
    assert result["exit_code"] == 17
    assert set(result) == {"ok", "exit_code", "elapsed_ms"}
    assert "private" not in json.dumps(result)


def test_satisfied_pre_agent_postcondition_runs_but_does_not_claim_readiness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent_calls: list[str] = []

    class BaselineSatisfiedBridge:
        def __init__(self, _config: Any) -> None:
            self.meaningful_operation_count = 0

        def exec(
            self,
            _command: str,
            *,
            meaningful: bool = False,
            allow_nonzero: bool = False,
        ) -> dict[str, Any]:
            if allow_nonzero:
                return {"ok": True, "exit_code": 0, "elapsed_ms": 1}
            assert meaningful is True
            self.meaningful_operation_count += 1
            return {"ok": True, "exit_code": 0, "stdout": "", "elapsed_ms": 1}

    def fake_turn_once(
        plan: dict[str, Any],
        *,
        host_runner: Any,
        task_validator: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        result = host_runner({"turn_key": "synthetic-turn"})
        return {
            "status": "committed",
            "validation": dict(task_validator(plan, result)),
        }

    monkeypatch.setattr(runtime, "SkillsBenchTurnBridge", BaselineSatisfiedBridge)
    monkeypatch.setattr(runtime, "_turn_plan", lambda *_args: {"ok": True})
    monkeypatch.setattr(runtime, "run_loopx_turn_once", fake_turn_once)

    execution, validation = runtime.run_skillsbench_loopx_turn(
        prompt="synthetic prompt",
        agent_runner=lambda prompt: agent_calls.append(prompt) or "done",
        config=_config(tmp_path),
    )
    receipt = runtime.build_skillsbench_benchmark_runner_readiness(
        execution=execution,
        scored_workspace_validation=validation,
    )

    assert agent_calls == ["synthetic prompt"]
    assert validation["pre_agent_postcondition_status"] == "already_satisfied"
    assert receipt["ready"] is False
    assert "pre_agent_postcondition_unsatisfied" in receipt["blocker_codes"]


def test_unsatisfied_baseline_then_satisfied_postcondition_is_runner_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent_calls: list[str] = []

    class TransitionBridge:
        def __init__(self, _config: Any) -> None:
            self.meaningful_operation_count = 0

        def exec(
            self,
            _command: str,
            *,
            meaningful: bool = False,
            allow_nonzero: bool = False,
        ) -> dict[str, Any]:
            if allow_nonzero:
                return {"ok": False, "exit_code": 3, "elapsed_ms": 1}
            assert meaningful is True
            self.meaningful_operation_count += 1
            return {"ok": True, "exit_code": 0, "stdout": "", "elapsed_ms": 1}

    def fake_turn_once(
        plan: dict[str, Any],
        *,
        host_runner: Any,
        task_validator: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        result = host_runner({"turn_key": "synthetic-turn"})
        validation = dict(task_validator(plan, result))
        return {
            "status": "committed",
            "validation": validation,
            "receipt": {"status": "committed"},
            "effects": {
                "host_invoked": True,
                "state_written": True,
                "quota_spent": True,
                "scheduler_acknowledged": True,
            },
        }

    monkeypatch.setattr(runtime, "SkillsBenchTurnBridge", TransitionBridge)
    monkeypatch.setattr(
        runtime,
        "_turn_plan",
        lambda *_args: {"ok": True, "turn_key": "synthetic-turn"},
    )
    monkeypatch.setattr(runtime, "run_loopx_turn_once", fake_turn_once)

    execution, validation = runtime.run_skillsbench_loopx_turn(
        prompt="synthetic prompt",
        agent_runner=lambda prompt: agent_calls.append(prompt) or "done",
        config=_config(tmp_path),
    )
    trace = runtime.build_skillsbench_loopx_turn_trace(
        route="loopx-turn-agent-cli",
        benchmark_id="synthetic-benchmark",
        task_id="synthetic-task",
        execution=execution,
        scored_workspace_validation=validation,
    )

    assert agent_calls == ["synthetic prompt"]
    assert validation["pre_agent_postcondition_status"] == "unsatisfied"
    assert validation["post_agent_postcondition_status"] == "satisfied"
    assert validation["meaningful_operation_count"] == 1
    assert trace["benchmark_runner_readiness"]["ready"] is True
    assert trace["benchmark_runner_readiness"]["blocker_codes"] == []
    assert trace["benchmark_runner_readiness"]["raw_task_text_recorded"] is False


@pytest.mark.parametrize(
    ("execution_status", "baseline_status", "post_status", "blocker"),
    [
        ("failed", "unsatisfied", "satisfied", "turn_transaction_committed"),
        (
            "committed",
            "already_satisfied",
            "satisfied",
            "pre_agent_postcondition_unsatisfied",
        ),
        (
            "committed",
            "unsatisfied",
            "unsatisfied",
            "post_agent_postcondition_satisfied",
        ),
    ],
)
def test_runner_readiness_fails_closed_on_partial_evidence(
    execution_status: str,
    baseline_status: str,
    post_status: str,
    blocker: str,
) -> None:
    receipt = runtime.build_skillsbench_benchmark_runner_readiness(
        execution={"status": execution_status},
        scored_workspace_validation={
            "pre_agent_postcondition_checked": True,
            "pre_agent_postcondition_status": baseline_status,
            "post_agent_postcondition_status": post_status,
            "oracle_feedback_used": False,
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["ready"] is False
    assert blocker in receipt["blocker_codes"]


def test_runner_readiness_survives_public_trace_aggregation() -> None:
    ready_trace = runtime.build_skillsbench_loopx_turn_trace(
        route="loopx-turn-agent-cli",
        benchmark_id="synthetic-benchmark",
        task_id="synthetic-task",
        execution={"status": "committed"},
        scored_workspace_validation={
            "status": "passed",
            "validator_kind": "skillsbench_scored_workspace_command",
            "independent": True,
            "pre_agent_postcondition_checked": True,
            "pre_agent_postcondition_status": "unsatisfied",
            "post_agent_postcondition_status": "satisfied",
            "baseline_contract": "task_declared_independent_postcondition",
            "oracle_feedback_used": False,
        },
    )
    already_satisfied_trace = runtime.build_skillsbench_loopx_turn_trace(
        route="loopx-turn-agent-cli",
        benchmark_id="synthetic-benchmark",
        task_id="synthetic-task",
        execution={"status": "committed"},
        scored_workspace_validation={
            "status": "passed",
            "validator_kind": "skillsbench_scored_workspace_command",
            "independent": True,
            "pre_agent_postcondition_checked": True,
            "pre_agent_postcondition_status": "already_satisfied",
            "post_agent_postcondition_status": "satisfied",
            "baseline_contract": "task_declared_independent_postcondition",
            "oracle_feedback_used": False,
        },
    )
    ready_trace["benchmark_runner_readiness"]["checks"][
        "private_path_should_not_project"
    ] = True
    summary = SkillsBenchTurnTraceSummary()
    for trace in (ready_trace, already_satisfied_trace):
        summary.merge(trace, trace["boundary"])
    assert (
        "private_path_should_not_project" not in summary.readiness_receipts[0]["checks"]
    )
    controller_trace: dict[str, Any] = {}
    summary.apply(controller_trace)
    compact: dict[str, Any] = {}
    sync_skillsbench_loopx_turn_trace_into_compact(compact, controller_trace)

    receipt = compact["benchmark_runner_readiness"]
    assert receipt["ready"] is True
    assert receipt["proven_turn_count"] == 1
    assert receipt["observed_turn_count"] == 2
    assert receipt["blocker_codes"] == []
    assert receipt["raw_task_text_recorded"] is False
    assert (
        compact["scored_workspace_validation"]["raw_validator_output_recorded"] is False
    )
