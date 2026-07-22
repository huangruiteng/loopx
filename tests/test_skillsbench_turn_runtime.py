from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Union, get_args, get_origin

import pytest

from loopx.benchmark_adapters import skillsbench_acp_relay as acp_relay
from loopx.benchmark_adapters import skillsbench_bridge_summary as bridge_summary
from loopx.benchmark_adapters import skillsbench_turn_runtime as runtime
from loopx.benchmark_adapters.skillsbench_acp_relay import (
    CodexExecConfig,
    SkillsBenchLocalAcpRelay,
)
from loopx.benchmark_adapters.skillsbench_turn_route import (
    SkillsBenchTurnTraceSummary,
    skillsbench_loopx_turn_launch_error,
    skillsbench_loopx_turn_runner_prerequisites,
    sync_skillsbench_loopx_turn_trace_into_compact,
)
from loopx.control_plane.turn_driver import executor as turn_executor


def test_agent_prompt_runner_alias_is_bootstrap_python_39_safe() -> None:
    return_type = get_args(runtime.AgentPromptRunner)[1]

    assert get_origin(return_type) is Union


def _config(tmp_path: Path) -> runtime.SkillsBenchTurnRuntimeConfig:
    return runtime.SkillsBenchTurnRuntimeConfig(
        bridge_command="synthetic-bridge",
        validation_command="synthetic-postcondition",
        goal_id="synthetic-goal",
        agent_id="synthetic-agent",
        runtime_root=tmp_path,
    )


def _install_sequence_runtime(
    monkeypatch: pytest.MonkeyPatch,
    validation_runs: list[list[int] | tuple[int, ...]],
) -> tuple[list[str], dict[str, int], list[str], list[str]]:
    plan_instance_ids: list[str] = []
    callback_counts = {"writeback": 0, "spend": 0}
    bridge_commands: list[str] = []
    sequence_baseline_paths: list[str] = []

    class SequenceBridge:
        instance_count = 0

        def __init__(self, _config: Any) -> None:
            self.meaningful_operation_count = 0
            self.validation_codes = list(
                validation_runs[SequenceBridge.instance_count]
            )
            SequenceBridge.instance_count += 1

        def exec(
            self,
            command: str,
            *,
            meaningful: bool = False,
            allow_nonzero: bool = False,
        ) -> dict[str, Any]:
            bridge_commands.append(command)
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
        sequence_baseline_paths.append(_config.sequence_baseline_path)
        return {"ok": True, "turn_key": turn_instance_id}

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
        validation = turn_executor._run_task_validator(
            plan,
            result,
            validator=task_validator,
        )
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
    return (
        plan_instance_ids,
        callback_counts,
        bridge_commands,
        sequence_baseline_paths,
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


def test_bridge_progress_receipt_requires_successful_task_content_change(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "bridge-summary.jsonl"
    records = [
        {
            "record_phase": "complete",
            "operation": "read_file",
            "task_facing_operation": True,
            "success": True,
        },
        {
            "record_phase": "complete",
            "operation": "write_file",
            "task_facing_operation": True,
            "durable_task_write": True,
            "success": False,
            "returncode": 1,
        },
        {
            "record_phase": "start",
            "operation": "write_file",
            "task_facing_operation": True,
        },
        {
            "record_phase": "complete",
            "operation": "write_file",
            "task_facing_operation": True,
            "durable_task_write": False,
            "success": True,
            "returncode": 0,
        },
        {
            "record_phase": "complete",
            "operation": "write_file",
            "task_facing_operation": True,
            "durable_task_write": True,
            "durable_task_content_changed": True,
            "success": True,
            "returncode": 0,
        },
    ]
    summary_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    receipt = bridge_summary.bridge_summary_task_progress_receipt(summary_path)

    assert receipt == {
        "schema_version": "skillsbench_bridge_task_progress_receipt_v0",
        "status": "verified_task_content_change",
        "task_facing_operation_count": 4,
        "task_facing_success_count": 3,
        "successful_task_file_write_count": 1,
        "successful_task_file_change_count": 1,
        "raw_material_recorded": False,
    }


def test_instrumented_bridge_emits_durable_root_without_raw_path(
    tmp_path: Path,
) -> None:
    fake_bridge = tmp_path / "fake-bridge"
    bridge_state = tmp_path / "bridge-state.json"
    fake_bridge.write_text(
        "#!/usr/bin/env python3\n"
        "import json, shlex, sys\n"
        "from pathlib import Path\n"
        f"state_path = Path({str(bridge_state)!r})\n"
        "state = json.loads(state_path.read_text()) if state_path.exists() else {}\n"
        "request = json.loads(sys.stdin.read())\n"
        "operation = request.get('operation')\n"
        "path = str(request.get('path', ''))\n"
        "if operation == 'exec':\n"
        "    tokens = shlex.split(str(request.get('command', '')))\n"
        "    path = tokens[-1] if len(tokens) >= 3 else ''\n"
        "    ok = path in state\n"
        "    response = {'ok': ok, 'exit_code': 0 if ok else 1}\n"
        "elif operation == 'read_file':\n"
        "    ok = path in state\n"
        "    response = {'ok': ok, 'exit_code': 0 if ok else 1, "
        "'content': state.get(path, ''), 'content_truncated': False}\n"
        "elif operation == 'write_file':\n"
        "    ok = not path.endswith('failed.txt')\n"
        "    if ok:\n"
        "        state[path] = str(request.get('content', ''))\n"
        "        state_path.write_text(json.dumps(state))\n"
        "    response = {'ok': ok, 'exit_code': 0 if ok else 1}\n"
        "else:\n"
        "    response = {'ok': True, 'exit_code': 0}\n"
        "print(json.dumps(response))\n",
        encoding="utf-8",
    )
    fake_bridge.chmod(0o755)
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(remote_command_file_bridge_command=str(fake_bridge))
    )
    summary_path = tmp_path / "bridge-summary.jsonl"
    wrapper = relay._write_instrumented_bridge_wrapper(
        tmp_path=tmp_path,
        summary_path=summary_path,
    )
    requests = [
        {
            "operation": "write_file",
            "path": "/root/task-output.txt",
            "content": "private task output",
        },
        {
            "operation": "write_file",
            "path": "/root/task-output.txt",
            "content": "private task output",
        },
        {
            "operation": "write_file",
            "path": "/root/task-output.txt",
            "content": "updated private task output",
        },
        {
            "operation": "write_file",
            "path": "/tmp/temporary-note.txt",
            "content": "temporary private note",
        },
        {
            "operation": "write_file",
            "path": "/root/failed.txt",
            "content": "failed private output",
        },
    ]
    for request in requests:
        subprocess.run(
            [str(wrapper)],
            input=json.dumps(request),
            text=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    receipt = bridge_summary.bridge_summary_task_progress_receipt(summary_path)
    summary_text = summary_path.read_text(encoding="utf-8")

    assert receipt["successful_task_file_write_count"] == 3
    assert receipt["successful_task_file_change_count"] == 2
    assert receipt["status"] == "verified_task_content_change"
    assert '"durable_task_write_root": "root"' in summary_text
    assert "/root/task-output.txt" not in summary_text
    assert "/tmp/temporary-note.txt" not in summary_text
    assert "/root/failed.txt" not in summary_text
    assert "private task output" not in summary_text
    assert "updated private task output" not in summary_text
    assert "temporary private note" not in summary_text
    assert "failed private output" not in summary_text
    assert '"failure_category": "bridge_operation_failed"' in summary_text


@pytest.mark.parametrize(
    ("write_count", "change_count", "raw_material_recorded", "expected_status"),
    [
        (1, 1, False, "committed"),
        (1, 0, False, "failed"),
        (0, 0, False, "failed"),
        (1, 1, True, "failed"),
    ],
)
def test_bridge_content_progress_can_commit_when_workspace_command_cannot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    write_count: int,
    change_count: int,
    raw_material_recorded: bool,
    expected_status: str,
) -> None:
    class NonFileProgressBridge:
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
                return {"ok": False, "exit_code": 3, "elapsed_ms": 1}
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
            "status": (
                "committed"
                if validation.get("status") in {"progress", "passed"}
                else "failed"
            ),
            "validation": validation,
        }

    monkeypatch.setattr(runtime, "SkillsBenchTurnBridge", NonFileProgressBridge)
    monkeypatch.setattr(runtime, "_turn_plan", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(runtime, "run_loopx_turn_once", fake_turn_once)
    evidence = {
        "schema_version": "skillsbench_bridge_task_progress_receipt_v0",
        "status": (
            "verified_task_content_change"
            if change_count and not raw_material_recorded
            else "no_verified_task_mutation"
        ),
        "task_facing_operation_count": 4,
        "task_facing_success_count": 4,
        "successful_task_file_write_count": write_count,
        "successful_task_file_change_count": change_count,
        "raw_material_recorded": raw_material_recorded,
    }

    execution, validation = runtime.run_skillsbench_loopx_turn(
        prompt="synthetic prompt",
        agent_runner=lambda _prompt: runtime.SkillsBenchTurnAgentResult(
            response_text="done",
            progress_evidence=evidence,
        ),
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{
                **_config(tmp_path).__dict__,
                "terminal_policy": "fixed-n",
            }
        ),
        sequence_step_kind="progress",
    )

    assert execution["status"] == expected_status
    if expected_status == "committed":
        assert validation["status"] == "passed"
        assert validation["post_agent_postcondition_status"] == "progress_validated"
        assert validation["validator_kind"] == "skillsbench_bridge_content_progress"
        assert validation["progress_evidence_kind"] == "verified_task_content_change"
        assert validation["successful_task_file_write_count"] == 1
        assert validation["successful_task_file_change_count"] == 1
    else:
        assert validation["status"] == "failed"
        assert validation["post_agent_postcondition_status"] == "unsatisfied"


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
    assert receipt["turn_proven"] is True
    assert "pre_agent_postcondition_eligible" in receipt["blocker_codes"]


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
    (
        plan_instance_ids,
        callback_counts,
        _bridge_commands,
        sequence_baseline_paths,
    ) = _install_sequence_runtime(monkeypatch, [(3, 10), (10, 0)])
    agent_prompts: list[str] = []
    observed: list[tuple[dict[str, Any], dict[str, Any]]] = []

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
    assert sequence["official_feedback_blinded"] is True
    assert sequence["turn_count"] == 2
    assert len(set(plan_instance_ids)) == 2
    assert plan_instance_ids[0].endswith("turn-001")
    assert plan_instance_ids[1].endswith("turn-002")
    assert agent_prompts[0] == "original task prompt"
    assert "Continue the same task" in agent_prompts[1]
    assert callback_counts == {"writeback": 2, "spend": 2}
    assert sequence_baseline_paths == ["", ""]
    assert [item[0]["quota_slot_spend_count"] for item in records] == [1, 1]
    assert records[0][1]["validated_progress"] is True
    assert records[0][1]["terminal_complete"] is False
    assert records[0][1]["sequence_stop_reason"] == "continue"
    assert records[1][1]["terminal_complete"] is True
    assert records[1][1]["sequence_stop_reason"] == "terminal_complete"
    assert len(observed) == 2


def test_adaptive_sequence_reviews_verified_content_after_validator_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    progress_kinds = iter(
        ["verified_task_content_change", "scored_workspace_command"]
    )
    prompts: list[str] = []

    def fake_turn(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        prompts.append(kwargs["prompt"])
        return (
            {"status": "committed"},
            {
                "status": "passed",
                "validated_progress": True,
                "terminal_complete": True,
                "progress_evidence_kind": next(progress_kinds),
            },
        )

    monkeypatch.setattr(runtime, "run_skillsbench_loopx_turn", fake_turn)

    records, sequence = runtime.run_skillsbench_loopx_turn_sequence(
        prompt="original task prompt",
        agent_runner=lambda _prompt: "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{**_config(tmp_path).__dict__, "max_turns": 4}
        ),
    )

    assert len(records) == 2
    assert sequence["status"] == "terminal_complete"
    assert sequence["official_feedback_blinded"] is True
    assert prompts[0] == "original task prompt"
    assert "Continue the same task" in prompts[1]
    assert records[0][1]["terminal_complete"] is True
    assert records[0][1]["sequence_terminal_complete"] is False
    assert records[0][1]["sequence_stop_reason"] == "continue"
    assert records[1][1]["sequence_terminal_complete"] is True
    assert records[1][1]["sequence_stop_reason"] == "terminal_complete"
    first_trace = runtime.build_skillsbench_loopx_turn_trace(
        route="loopx-turn-agent-cli",
        benchmark_id="synthetic-benchmark",
        task_id="synthetic-task",
        execution=records[0][0],
        scored_workspace_validation=records[0][1],
    )
    summary = SkillsBenchTurnTraceSummary()
    summary.merge(first_trace, first_trace["boundary"])
    controller_trace: dict[str, Any] = {}
    summary.apply(controller_trace)
    assert controller_trace["scored_workspace_validation"]["terminal_complete"] is False


def test_stability_sequence_repeats_repairs_then_stops_after_no_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validation_codes = [
        [3, 10, 0],
        [0, 10, 0],
        [0, 1, 0],
    ]
    (
        _plan_instance_ids,
        callback_counts,
        bridge_commands,
        sequence_baseline_paths,
    ) = _install_sequence_runtime(monkeypatch, validation_codes)
    agent_prompts: list[str] = []

    records, sequence = runtime.run_skillsbench_loopx_turn_sequence(
        prompt="original task prompt",
        agent_runner=lambda prompt: agent_prompts.append(prompt) or "done",
        config=runtime.SkillsBenchTurnRuntimeConfig(
            **{
                **_config(tmp_path).__dict__,
                "max_turns": 4,
                "terminal_policy": "stability",
            }
        ),
    )

    assert sequence["status"] == "terminal_complete"
    assert sequence["turn_count"] == 3
    assert callback_counts == {"writeback": 3, "spend": 3}
    assert len(set(sequence_baseline_paths)) == 1
    assert sequence_baseline_paths[0].startswith(
        "/app/.loopx/runtime/benchmark-turn-sequences/"
    )
    assert sequence_baseline_paths[0].endswith(".baseline")
    assert (
        sum(
            f"{runtime.SKILLSBENCH_TURN_BASELINE_ENV}=" in command
            for command in bridge_commands
        )
        == 3
    )
    assert (
        sum(
            f"{runtime.SKILLSBENCH_TURN_SEQUENCE_BASELINE_ENV}=" in command
            for command in bridge_commands
        )
        == 6
    )
    assert agent_prompts[0] == "original task prompt"
    assert all(
        "without manufacturing a change" in prompt for prompt in agent_prompts[1:]
    )
    assert [record[1]["terminal_complete"] for record in records] == [
        False,
        False,
        True,
    ]
    assert [record[1]["stability_progress_detected"] for record in records] == [
        True,
        True,
        False,
    ]
    assert all(
        record[1]["stability_completion_satisfied"] is True for record in records
    )
    assert all(record[1]["sequence_baseline_configured"] is True for record in records)
    sequence_refs = {record[1]["turn_sequence_ref"] for record in records}
    assert sequence_refs == {sequence["turn_sequence_ref"]}
    assert sequence_baseline_paths[0] not in json.dumps(records, sort_keys=True)
    assert all(
        not any(key.startswith("stability_") for key in execution["validation"])
        for execution, _validation in records
    )
    readiness = runtime.build_skillsbench_benchmark_runner_readiness(
        execution=records[-1][0],
        scored_workspace_validation=records[-1][1],
    )
    assert readiness["ready"] is True
    summary = SkillsBenchTurnTraceSummary()
    for execution, validation in records:
        trace = runtime.build_skillsbench_loopx_turn_trace(
            route="loopx-turn-agent-cli",
            benchmark_id="synthetic-benchmark",
            task_id="synthetic-task",
            execution=execution,
            scored_workspace_validation=validation,
        )
        summary.merge(trace, trace["boundary"])
    controller_trace: dict[str, Any] = {}
    summary.apply(controller_trace)
    aggregate = controller_trace["scored_workspace_validation"]
    assert aggregate["terminal_policy"] == "stability"
    assert aggregate["terminal_complete"] is True
    assert aggregate["sequence_baseline_configured"] is True
    assert aggregate["stability_completion_satisfied"] is True
    assert aggregate["stability_progress_detected"] is False
    assert aggregate["stability_repair_turn_count"] == 2
    assert controller_trace["benchmark_runner_readiness"]["ready"] is True


def test_stability_turn_requires_sequence_baseline(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a sequence baseline"):
        runtime.run_skillsbench_loopx_turn(
            prompt="synthetic prompt",
            agent_runner=lambda _prompt: "done",
            config=runtime.SkillsBenchTurnRuntimeConfig(
                **{
                    **_config(tmp_path).__dict__,
                    "terminal_policy": "stability",
                }
            ),
        )


def test_stability_policy_is_projected_and_launchable() -> None:
    prerequisites = skillsbench_loopx_turn_runner_prerequisites(
        "loopx-turn-agent-cli",
        "private-command",
        max_turns=4,
        progress_exit_code=10,
        terminal_policy="stability",
    )
    launch_error = skillsbench_loopx_turn_launch_error(
        SimpleNamespace(
            route="loopx-turn-agent-cli",
            host_local_acp_launch=True,
            loopx_turn_validation_command="private-command",
            loopx_turn_max_turns=4,
            loopx_turn_progress_exit_code=10,
            loopx_turn_terminal_policy="stability",
        )
    )

    assert prerequisites["loopx_turn_terminal_policy"] == "stability"
    assert launch_error is None


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
attempt = len(pathlib.Path(os.environ["FAKE_CODEX_ARGV_LOG"]).read_text().splitlines())
if attempt == 2:
    print(json.dumps({
        "type": "turn.failed",
        "error": {"message": "stream disconnected before completion: codex/responses"},
    }))
    raise SystemExit(1)
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
    assert len(argv_rows) == 3
    assert argv_rows[1][:3] == ["exec", "resume", "--skip-git-repo-check"]
    assert argv_rows[2][:3] == ["exec", "resume", "--skip-git-repo-check"]
    assert "thread-fixture-001" in argv_rows[1]
    assert "thread-fixture-001" in argv_rows[2]
    assert session["_loopx_turn_codex_thread_id"] == "thread-fixture-001"
    failures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in trace_dir.glob("*.compact.json")
        if json.loads(path.read_text(encoding="utf-8")).get("trace_kind")
        == "codex_exec_process_failure"
    ]
    assert len(failures) == 1
    process = failures[0]["codex_exec_process"]
    assert process["failure_category"] == "codex_responses_stream_unavailable"
    assert process["recoverable_turn_failure"] is True
    assert process["transport_retry_index"] == 0
    assert process["retry_scheduled"] is True
    assert process["raw_stdout_recorded"] is False
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


def test_codex_exec_transport_retry_requires_no_task_facing_operation(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "bridge-summary.jsonl"
    assert acp_relay._codex_exec_transport_retry_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )

    summary_path.write_text(
        json.dumps(
            {
                "record_phase": "complete",
                "operation": "read_file",
                "task_facing_operation": True,
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert not acp_relay._codex_exec_transport_retry_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )

    summary_path.write_text(
        json.dumps(
            {
                "record_phase": "complete",
                "operation": "run_command",
                "loopx_state_write": True,
                "loopx_subcommands": ["quota", "spend-slot"],
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert not acp_relay._codex_exec_transport_retry_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )


def test_codex_exec_session_rollover_requires_exhausted_side_effect_free_resume(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "bridge-summary.jsonl"
    assert acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=acp_relay.CODEX_EXEC_TRANSPORT_RETRY_LIMIT,
        rollover_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )
    assert not acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=0,
        rollover_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )

    summary_path.write_text(
        json.dumps(
            {
                "record_phase": "complete",
                "operation": "run_command",
                "loopx_state_write": True,
                "loopx_subcommands": ["refresh-state"],
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert not acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=acp_relay.CODEX_EXEC_TRANSPORT_RETRY_LIMIT,
        rollover_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )
    summary_path.unlink()
    assert not acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=acp_relay.CODEX_EXEC_TRANSPORT_RETRY_LIMIT,
        rollover_count=acp_relay.CODEX_EXEC_SESSION_ROLLOVER_LIMIT,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )
    assert not acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=acp_relay.CODEX_EXEC_TRANSPORT_RETRY_LIMIT,
        rollover_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() - 1,
    )

    summary_path.write_text(
        json.dumps(
            {
                "record_phase": "complete",
                "operation": "write_file",
                "task_facing_operation": True,
                "success": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert not acp_relay._codex_exec_session_rollover_allowed(
        category="codex_responses_stream_unavailable",
        bridge_summary_path=summary_path,
        retry_count=acp_relay.CODEX_EXEC_TRANSPORT_RETRY_LIMIT,
        rollover_count=0,
        final_message_present=False,
        turn_deadline=time.monotonic() + 30,
    )


def test_skillsbench_n_turn_codex_exec_rolls_over_once_after_repeated_resume_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    invocation_log = tmp_path / "invocations.jsonl"
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

log_path = pathlib.Path(os.environ["FAKE_CODEX_INVOCATION_LOG"])
attempt = len(log_path.read_text().splitlines()) + 1 if log_path.exists() else 1
prompt = sys.stdin.read()
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "prompt": prompt}) + "\\n")
if attempt in {2, 3}:
    print(json.dumps({
        "type": "turn.failed",
        "error": {"message": "stream disconnected before completion: codex/responses"},
    }))
    raise SystemExit(1)
output_index = sys.argv.index("--output-last-message") + 1
pathlib.Path(sys.argv[output_index]).write_text("bounded turn complete", encoding="utf-8")
thread_id = "thread-before-rollover" if attempt == 1 else "thread-after-rollover"
print(json.dumps({"type": "thread.started", "thread_id": thread_id}))
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_INVOCATION_LOG", str(invocation_log))
    trace_dir = tmp_path / "public-traces"
    trace_dir.mkdir()
    relay = SkillsBenchLocalAcpRelay(
        CodexExecConfig(
            codex_bin=str(fake_codex),
            loopx_turn_agent_cli=True,
            loopx_turn_max_turns=4,
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
    observed_thread_ids: list[str] = []

    def fake_turn_relay(**kwargs: Any) -> str:
        first = kwargs["agent_runner"](kwargs["prompt"])
        second = kwargs["agent_runner"]("Continue the same task in this session.")
        third = kwargs["agent_runner"]("Continue after the session rollover.")
        assert (
            first.response_text
            == second.response_text
            == third.response_text
            == "bounded turn complete"
        )
        observed_thread_ids.append(session["_loopx_turn_codex_thread_id"])
        return "sequence complete"

    monkeypatch.setattr(acp_relay, "run_skillsbench_loopx_turn_relay", fake_turn_relay)
    private_original_prompt = "private original task prompt fixture"
    assert (
        relay._run_codex(
            private_original_prompt,
            session=session,
            session_id="fixture-session",
            stdout=SimpleNamespace(write=lambda _value: None, flush=lambda: None),
        )
        == "sequence complete"
    )

    invocations = [json.loads(line) for line in invocation_log.read_text().splitlines()]
    assert len(invocations) == 5
    assert invocations[0]["argv"][:2] == ["exec", "--skip-git-repo-check"]
    assert invocations[1]["argv"][:3] == [
        "exec",
        "resume",
        "--skip-git-repo-check",
    ]
    assert invocations[2]["argv"][:3] == [
        "exec",
        "resume",
        "--skip-git-repo-check",
    ]
    assert invocations[3]["argv"][:2] == ["exec", "--skip-git-repo-check"]
    assert "resume" not in invocations[3]["argv"]
    assert "--ephemeral" not in invocations[3]["argv"]
    assert "thread-before-rollover" in invocations[1]["argv"]
    assert "thread-before-rollover" in invocations[2]["argv"]
    assert invocations[4]["argv"][:3] == [
        "exec",
        "resume",
        "--skip-git-repo-check",
    ]
    assert "thread-after-rollover" in invocations[4]["argv"]
    assert private_original_prompt in invocations[3]["prompt"]
    assert "Continue the same task in this session." in invocations[3]["prompt"]
    assert "current durable workspace" in invocations[3]["prompt"]
    assert observed_thread_ids == ["thread-after-rollover"]
    assert "_loopx_turn_codex_thread_id" not in session
    assert "_loopx_turn_codex_rollover_count" not in session
    assert "_loopx_turn_original_prompt" not in session

    traces = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in trace_dir.glob("*.compact.json")
    ]
    failures = sorted(
        (
            trace
            for trace in traces
            if trace.get("trace_kind") == "codex_exec_process_failure"
        ),
        key=lambda trace: trace["codex_exec_process"]["transport_retry_index"],
    )
    assert len(failures) == 2
    assert failures[0]["codex_exec_process"]["retry_scheduled"] is True
    assert (
        failures[0]["codex_exec_process"]["session_rollover_scheduled"] is False
    )
    assert failures[1]["codex_exec_process"]["retry_scheduled"] is False
    assert failures[1]["codex_exec_process"]["session_rollover_scheduled"] is True
    rollover = next(
        trace for trace in traces if trace.get("trace_kind") == "codex_exec_session_rollover"
    )
    assert rollover["codex_exec_session_rollover"] == {
        "schema_version": "skillsbench_codex_exec_session_rollover_v0",
        "stage": "completed",
        "rollover_index": 1,
        "resume_failure_count": 2,
        "previous_thread_present": True,
        "fresh_thread_present": True,
        "shared_sequence_deadline_preserved": True,
        "original_prompt_available_in_private_memory": True,
        "original_prompt_recorded": False,
        "thread_ids_recorded": False,
        "raw_task_text_recorded": False,
    }
    public_trace_text = json.dumps(traces, sort_keys=True)
    assert private_original_prompt not in public_trace_text
    assert "thread-before-rollover" not in public_trace_text
    assert "thread-after-rollover" not in public_trace_text


def test_codex_exec_failure_category_reads_only_typed_jsonl_errors() -> None:
    private_message = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "stream disconnected before completion: codex/responses",
            },
        }
    )
    typed_error = json.dumps(
        {
            "type": "turn.failed",
            "error": {
                "message": "stream disconnected before completion: codex/responses"
            },
        }
    )

    assert (
        acp_relay._codex_exec_failure_category(
            returncode=1,
            stderr_text="",
            stdout_text=private_message,
        )
        == "codex_exec_exit_1"
    )
    assert (
        acp_relay._codex_exec_failure_category(
            returncode=1,
            stderr_text="",
            stdout_text=typed_error,
        )
        == "codex_responses_stream_unavailable"
    )


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


@pytest.mark.parametrize(
    ("terminal_policy", "expected_step_kinds"),
    [
        ("fixed-n", ["progress", "progress", "terminal"]),
        ("stability", ["validator", "validator", "terminal"]),
    ],
)
def test_sequence_reserves_terminal_step_for_configured_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    terminal_policy: str,
    expected_step_kinds: list[str],
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
                "terminal_policy": terminal_policy,
            }
        ),
    )

    assert step_kinds == expected_step_kinds
    assert len(records) == 3
    assert sequence["status"] == "terminal_complete"
    assert sequence["terminal_policy"] == terminal_policy


@pytest.mark.parametrize(
    ("execution_status", "baseline_status", "post_status", "blocker"),
    [
        ("failed", "unsatisfied", "satisfied", "turn_transaction_committed"),
        (
            "committed",
            "already_satisfied",
            "satisfied",
            "pre_agent_postcondition_eligible",
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


@pytest.mark.parametrize(
    ("post_status", "independent", "expected_proven"),
    [
        ("progress_validated", True, True),
        ("satisfied", False, False),
    ],
)
def test_runner_readiness_turn_proof_is_independent_from_causal_readiness(
    post_status: str,
    independent: bool,
    expected_proven: bool,
) -> None:
    receipt = runtime.build_skillsbench_benchmark_runner_readiness(
        execution={"status": "committed"},
        scored_workspace_validation={
            "status": "passed",
            "independent": independent,
            "pre_agent_postcondition_checked": True,
            "pre_agent_postcondition_status": "unsatisfied",
            "post_agent_postcondition_status": post_status,
            "oracle_feedback_used": False,
        },
    )

    assert receipt["turn_proven"] is expected_proven
    assert receipt["ready"] is (expected_proven and post_status == "satisfied")


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
            "turn_sequence_ref": "sequence:aaaaaaaaaaaaaaaa",
            "turn_index": 1,
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
            "turn_sequence_ref": "sequence:aaaaaaaaaaaaaaaa",
            "turn_index": 2,
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
    assert receipt["runner_ready_turn_count"] == 1
    assert receipt["proven_turn_count"] == 2
    assert receipt["committed_turn_count"] == 2
    assert receipt["observed_turn_count"] == 2
    assert receipt["turn_sequence_count"] == 1
    assert receipt["max_observed_turn_count_per_sequence"] == 2
    assert receipt["max_committed_turn_count_per_sequence"] == 2
    assert receipt["multi_turn_sequence_committed"] is True
    assert receipt["unattributed_turn_count"] == 0
    assert receipt["unindexed_sequence_turn_count"] == 0
    assert receipt["blocker_codes"] == []
    assert receipt["raw_task_text_recorded"] is False
    assert (
        compact["scored_workspace_validation"]["raw_validator_output_recorded"] is False
    )
    assert compact["scored_workspace_validation"]["terminal_policy"] == "fixed-n"


def test_runner_readiness_does_not_flatten_commits_across_turn_sequences() -> None:
    summary = SkillsBenchTurnTraceSummary()
    for sequence_ref in (
        "sequence:aaaaaaaaaaaaaaaa",
        "sequence:bbbbbbbbbbbbbbbb",
    ):
        for turn_index, committed in ((1, True), (2, False)):
            trace = runtime.build_skillsbench_loopx_turn_trace(
                route="loopx-turn-agent-cli",
                benchmark_id="synthetic-benchmark",
                task_id="synthetic-task",
                execution={"status": "committed" if committed else "failed"},
                scored_workspace_validation={
                    "status": "passed" if committed else "failed",
                    "validator_kind": "skillsbench_stability_postcondition",
                    "independent": True,
                    "pre_agent_postcondition_checked": True,
                    "pre_agent_postcondition_status": "unsatisfied",
                    "post_agent_postcondition_status": (
                        "progress_validated" if committed else "unsatisfied"
                    ),
                    "baseline_contract": "task_declared_independent_postcondition",
                    "terminal_policy": "stability",
                    "turn_sequence_ref": sequence_ref,
                    "turn_index": turn_index,
                    "oracle_feedback_used": False,
                },
            )
            summary.merge(trace, trace["boundary"])
            summary.merge(trace, trace["boundary"])

    controller_trace: dict[str, Any] = {}
    summary.apply(controller_trace)
    receipt = controller_trace["benchmark_runner_readiness"]

    assert receipt["observed_turn_count"] == 8
    assert receipt["committed_turn_count"] == 4
    assert receipt["turn_sequence_count"] == 2
    assert receipt["max_observed_turn_count_per_sequence"] == 2
    assert receipt["max_committed_turn_count_per_sequence"] == 1
    assert receipt["multi_turn_sequence_committed"] is False
    assert receipt["unattributed_turn_count"] == 0
    assert receipt["unindexed_sequence_turn_count"] == 0
