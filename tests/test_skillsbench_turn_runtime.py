from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from loopx.benchmark_adapters import skillsbench_acp_relay as acp_relay
from loopx.benchmark_adapters import skillsbench_turn_runtime as runtime
from loopx.benchmark_adapters.skillsbench_acp_relay import (
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)
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
                if meaningful:
                    self.meaningful_operation_count += 1
                return {"ok": True, "exit_code": 0, "elapsed_ms": 1}
            if meaningful:
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
    assert validation["meaningful_operation_count"] == 1
    assert receipt["ready"] is False
    assert "pre_agent_postcondition_unsatisfied" in receipt["blocker_codes"]


def test_fixed_n_maps_accepted_exit_zero_to_nonterminal_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ProgressBridge:
        def __init__(self, _config: Any) -> None:
            self.meaningful_operation_count = 0

        def exec(
            self,
            _command: str,
            *,
            meaningful: bool = False,
            allow_nonzero: bool = False,
        ) -> dict[str, Any]:
            if allow_nonzero and not meaningful:
                return {"ok": False, "exit_code": 3, "elapsed_ms": 1}
            if meaningful:
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

    monkeypatch.setattr(runtime, "SkillsBenchTurnBridge", ProgressBridge)
    monkeypatch.setattr(runtime, "_turn_plan", lambda *_args: {"ok": True})
    monkeypatch.setattr(runtime, "run_loopx_turn_once", fake_turn_once)

    execution, validation = runtime.run_skillsbench_loopx_turn(
        prompt="synthetic progress prompt",
        agent_runner=lambda _prompt: "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{**_config(tmp_path).__dict__, "terminal_policy": "fixed-n"}
        ),
        sequence_step_kind="progress",
    )

    assert execution["validation"]["status"] == "progress"
    assert execution["validation"]["exit_code"] == 10
    assert validation["validated_progress"] is True
    assert validation["terminal_complete"] is False
    assert validation["terminal_policy"] == "fixed-n"


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
            if allow_nonzero and not meaningful:
                return {"ok": False, "exit_code": 3, "elapsed_ms": 1}
            if meaningful:
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


def test_adaptive_sequence_commits_progress_then_terminal_turns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validation_pairs = [(3, 10), (10, 0)]
    plan_instance_ids: list[str] = []
    agent_prompts: list[str] = []
    callback_counts = {"writeback": 0, "spend": 0}
    observed: list[tuple[dict[str, Any], dict[str, Any]]] = []

    class SequenceBridge:
        instance_count = 0

        def __init__(self, _config: Any) -> None:
            self.meaningful_operation_count = 0
            self.validation_codes = list(
                validation_pairs[SequenceBridge.instance_count]
            )
            SequenceBridge.instance_count += 1

        def exec(
            self,
            _command: str,
            *,
            meaningful: bool = False,
            allow_nonzero: bool = False,
        ) -> dict[str, Any]:
            if allow_nonzero:
                code = self.validation_codes.pop(0)
                if meaningful:
                    self.meaningful_operation_count += 1
                return {
                    "ok": code == 0,
                    "exit_code": code,
                    "elapsed_ms": 1,
                    **({"stdout": ""} if code == 0 else {}),
                }
            return {"ok": True, "exit_code": 0, "stdout": "", "elapsed_ms": 1}

        def loopx_json(self, command: str) -> dict[str, Any]:
            if "refresh-state" in command:
                callback_counts["writeback"] += 1
                return {"ok": True, "appended": True}
            if "spend-slot" in command:
                callback_counts["spend"] += 1
                return {"ok": True, "appended": True, "slots": 1}
            return {
                "scheduler_hint": {
                    "execution_phase": {
                        "disposition": "outer_controller_owned",
                        "completed": True,
                        "acknowledged": False,
                        "apply_needed": False,
                    }
                }
            }

    def fake_plan(
        _bridge: Any,
        _config: Any,
        *,
        turn_instance_id: str,
    ) -> dict[str, Any]:
        plan_instance_ids.append(turn_instance_id)
        return {"ok": True, "turn_key": f"turn-{len(plan_instance_ids)}"}

    def fake_turn_once(
        plan: dict[str, Any],
        *,
        host_runner: Any,
        task_validator: Any,
        writeback: Any,
        spend: Any,
        scheduler: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        result = host_runner({"turn_key": plan["turn_key"]})
        validation = dict(task_validator(plan, result))
        assert validation["status"] in {"progress", "passed"}
        writeback_payload = writeback(result)
        spend_payload = spend()
        scheduler(spend_payload)
        return {
            "status": "committed",
            "validation": validation,
            "quota_slot_spend_count": 1,
            "receipt": {"status": "committed"},
            "effects": {
                "host_invoked": True,
                "state_written": writeback_payload["appended"],
                "quota_spent": spend_payload["appended"],
                "scheduler_acknowledged": False,
            },
        }

    monkeypatch.setattr(runtime, "SkillsBenchTurnBridge", SequenceBridge)
    monkeypatch.setattr(runtime, "_turn_plan", fake_plan)
    monkeypatch.setattr(runtime, "run_loopx_turn_once", fake_turn_once)

    records, sequence = runtime.run_skillsbench_loopx_turn_sequence(
        prompt="original task prompt",
        agent_runner=lambda prompt: agent_prompts.append(prompt) or "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{**_config(tmp_path).__dict__, "max_turns": 4}
        ),
        turn_observer=lambda execution, validation: observed.append(
            (execution, validation)
        ),
    )

    assert len(records) == 2
    assert sequence["status"] == "terminal_complete"
    assert sequence["turn_count"] == 2
    assert len(set(plan_instance_ids)) == 2
    assert plan_instance_ids[0].endswith("turn-001")
    assert plan_instance_ids[1].endswith("turn-002")
    assert agent_prompts[0] == "original task prompt"
    assert "Continue the same task" in agent_prompts[1]
    assert callback_counts == {"writeback": 2, "spend": 2}
    assert [item[0]["quota_slot_spend_count"] for item in records] == [1, 1]
    assert records[0][1]["validated_progress"] is True
    assert records[0][1]["terminal_complete"] is False
    assert records[0][1]["sequence_stop_reason"] == "continue"
    assert records[1][1]["terminal_complete"] is True
    assert records[1][1]["sequence_stop_reason"] == "terminal_complete"
    assert len(observed) == 2


def test_skillsbench_n_turn_codex_exec_starts_then_resumes_same_thread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    argv_log = tmp_path / "argv.jsonl"
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

with pathlib.Path(os.environ["FAKE_CODEX_ARGV_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")
output_index = sys.argv.index("--output-last-message") + 1
pathlib.Path(sys.argv[output_index]).write_text("bounded turn complete", encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": "thread-fixture-001"}))
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_ARGV_LOG", str(argv_log))
    trace_dir = tmp_path / "public-traces"
    trace_dir.mkdir()
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(
            codex_bin=str(fake_codex),
            loopx_turn_agent_cli=True,
            loopx_turn_max_turns=3,
            remote_command_file_bridge_command="synthetic-bridge",
            worker_public_trace_dir=str(trace_dir),
            timeout_sec=30,
        )
    )
    monkeypatch.setattr(
        relay,
        "_consume_remote_bridge_for_solver",
        lambda: {"ready": True},
    )
    monkeypatch.setattr(
        relay,
        "_publish_remote_bridge_consumption_trace",
        lambda _probe: None,
    )
    monkeypatch.setattr(
        relay,
        "_start_json_file_bridge_server",
        lambda **_kwargs: ("synthetic-agent-bridge", None),
    )
    monkeypatch.setattr(
        relay,
        "_write_instrumented_bridge_wrapper",
        lambda **kwargs: kwargs["tmp_path"] / "synthetic-wrapper",
    )
    monkeypatch.setattr(
        relay,
        "_prompt_with_remote_bridge_packet",
        lambda prompt, **_kwargs: prompt,
    )
    monkeypatch.setattr(
        relay,
        "_publish_remote_bridge_agent_operations_trace",
        lambda **_kwargs: None,
    )
    session: dict[str, Any] = {"cwd": str(tmp_path), "model": None}
    deadline = time.monotonic() + 30

    first = relay._run_codex(
        "first bounded turn",
        session=session,
        session_id="fixture-session",
        stdout=SimpleNamespace(write=lambda _value: None, flush=lambda: None),
        _bypass_loopx_turn=True,
        _turn_deadline=deadline,
    )
    second = relay._run_codex(
        "continue bounded turn",
        session=session,
        session_id="fixture-session",
        stdout=SimpleNamespace(write=lambda _value: None, flush=lambda: None),
        _bypass_loopx_turn=True,
        _turn_deadline=deadline,
    )

    argv_rows = [json.loads(line) for line in argv_log.read_text().splitlines()]
    assert first == second == "bounded turn complete"
    assert "--ephemeral" not in argv_rows[0]
    assert argv_rows[0][:2] == ["exec", "--skip-git-repo-check"]
    assert argv_rows[1][:3] == ["exec", "resume", "--skip-git-repo-check"]
    assert "thread-fixture-001" in argv_rows[1]
    assert session["_loopx_turn_codex_thread_id"] == "thread-fixture-001"
    private_cwd_root = tmp_path / ".loopx-turn-codex-sessions"
    assert len(list(private_cwd_root.glob("*/cwd"))) == 1

    session.pop("_loopx_turn_codex_thread_id")

    def fake_turn_relay(**kwargs: Any) -> str:
        kwargs["agent_runner"]("first bounded turn")
        kwargs["agent_runner"]("continue bounded turn")
        return "sequence complete"

    monkeypatch.setattr(acp_relay, "run_skillsbench_loopx_turn_relay", fake_turn_relay)
    assert (
        relay._run_codex(
            "full sequence",
            session=session,
            session_id="fixture-session",
            stdout=SimpleNamespace(write=lambda _value: None, flush=lambda: None),
        )
        == "sequence complete"
    )
    assert "_loopx_turn_codex_thread_id" not in session
    assert not private_cwd_root.exists()


def test_skillsbench_n_turn_codex_exec_respects_expired_shared_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import pathlib
import sys

output_index = sys.argv.index("--output-last-message") + 1
pathlib.Path(sys.argv[output_index]).write_text("late", encoding="utf-8")
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    trace_dir = tmp_path / "public-traces"
    trace_dir.mkdir()
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(
            codex_bin=str(fake_codex),
            loopx_turn_agent_cli=True,
            loopx_turn_max_turns=2,
            worker_public_trace_dir=str(trace_dir),
            timeout_sec=30,
        )
    )

    response = relay._run_codex(
        "late turn",
        session={"cwd": str(tmp_path), "model": None},
        session_id="fixture-session",
        stdout=SimpleNamespace(write=lambda _value: None, flush=lambda: None),
        _bypass_loopx_turn=True,
        _turn_deadline=time.monotonic() - 1,
    )

    assert response.startswith(runtime.RECOVERABLE_CODEX_TURN_FAILURE_PREFIX)
    assert "time_budget_exhausted" in response


@pytest.mark.parametrize(
    ("validated_progress", "max_turns", "expected_reason", "expected_turns"),
    [
        (False, 4, "no_validated_progress", 1),
        (True, 3, "max_turns_reached", 3),
    ],
)
def test_adaptive_sequence_stops_on_missing_progress_or_fixed_maximum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    validated_progress: bool,
    max_turns: int,
    expected_reason: str,
    expected_turns: int,
) -> None:
    calls = 0

    def fake_turn(**_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal calls
        calls += 1
        return (
            {
                "status": "committed",
                "quota_slot_spend_count": 1,
                "receipt": {"status": "committed"},
                "effects": {"state_written": True, "quota_spent": True},
            },
            {
                "status": "passed" if validated_progress else "failed",
                "validated_progress": validated_progress,
                "terminal_complete": False,
            },
        )

    monkeypatch.setattr(runtime, "run_skillsbench_loopx_turn", fake_turn)

    records, sequence = runtime.run_skillsbench_loopx_turn_sequence(
        prompt="original task prompt",
        agent_runner=lambda _prompt: "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{**_config(tmp_path).__dict__, "max_turns": max_turns}
        ),
    )

    assert calls == expected_turns
    assert len(records) == expected_turns
    assert sequence["status"] == expected_reason


def test_fixed_n_sequence_promotes_only_final_validated_step_to_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    step_kinds: list[str] = []

    def fake_turn(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        step_kind = kwargs["sequence_step_kind"]
        step_kinds.append(step_kind)
        terminal = step_kind == "terminal"
        return (
            {"status": "committed"},
            {
                "status": "passed",
                "validated_progress": True,
                "terminal_complete": terminal,
            },
        )

    monkeypatch.setattr(runtime, "run_skillsbench_loopx_turn", fake_turn)

    records, sequence = runtime.run_skillsbench_loopx_turn_sequence(
        prompt="original task prompt",
        agent_runner=lambda _prompt: "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{
                **_config(tmp_path).__dict__,
                "max_turns": 3,
                "terminal_policy": "fixed-n",
            }
        ),
    )

    assert step_kinds == ["progress", "progress", "terminal"]
    assert len(records) == 3
    assert sequence["status"] == "terminal_complete"
    assert sequence["terminal_policy"] == "fixed-n"


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
            "terminal_policy": "fixed-n",
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
            "terminal_policy": "fixed-n",
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
    assert compact["scored_workspace_validation"]["terminal_policy"] == "fixed-n"
