from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

import loopx.control_plane.todos.completion_validation as completion_validation_module
import loopx.control_plane.todos.completion_transaction as completion_transaction_module
from loopx.control_plane.todos.completion_validation_projection import (
    project_completion_validation_authority,
)
from loopx.event_sourced_state import (
    TODO_ADDED,
    TODO_COMPLETED,
    TODO_DEFERRED,
    TODO_UPDATED,
    AppendOnlyStateEventStore,
    build_state_projection,
    make_state_event,
    render_todo_markdown,
)
from loopx.status import parse_active_state_todos
from loopx.todos import add_goal_todo, complete_goal_todo, update_goal_todo

GOAL_ID = "todo-completion-validation"
AGENT = "codex-author"

_PASS_COMMAND = f'{shlex.quote(sys.executable)} -c "raise SystemExit(0)"'
_FAIL_COMMAND = f'{shlex.quote(sys.executable)} -c "raise SystemExit(1)"'
_SLEEP_COMMAND = f'{shlex.quote(sys.executable)} -c "import time; time.sleep(30)"'


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "\n".join(
            [
                "---",
                f"goal_id: {GOAL_ID}",
                "updated_at: 2026-08-12T00:00:00+00:00",
                "---",
                "",
                "## Agent Todo",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry = tmp_path / "registry.global.json"
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(tmp_path / "runtime"),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "harness_self_improvement",
                        "status": "active",
                        "repo": str(repo),
                        "state_file": state.name,
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry, state


def _agent_todo(state: Path, todo_id: str) -> dict:
    todos = parse_active_state_todos(state.read_text(encoding="utf-8"))
    return next(
        item
        for item in todos["agent_todos"]["items"]
        if item["todo_id"] == todo_id
    )


def _add_todo(
    registry: Path,
    *,
    validation_command: str | None = None,
    validation_command_json: str | None = None,
    validation_label: str | None = None,
    validation_timeout_seconds: int | None = None,
) -> dict:
    return add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Deliver one bounded change.",
        task_class="advancement_task",
        claimed_by=AGENT,
        validation_command=validation_command,
        validation_command_json=validation_command_json,
        validation_label=validation_label,
        validation_timeout_seconds=validation_timeout_seconds,
    )


def test_validation_command_declared_and_passing_commits_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(
        registry,
        validation_command=_PASS_COMMAND,
        validation_label="caller-declared smoke",
    )
    # Spy on the executor so the test fails if the gate is silently skipped.
    original_runner = completion_validation_module.run_caller_validation
    calls = {"count": 0}

    def counting_runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return original_runner(*args, **kwargs)

    monkeypatch.setattr(completion_validation_module, "run_caller_validation", counting_runner)
    original_effect_call = completion_transaction_module.effect_runtime_result
    transaction_calls: list[str] = []

    def counting_effect_call(method, params):  # type: ignore[no-untyped-def]
        if method == "todo.completion.reduce":
            transaction_calls.append(method)
        return original_effect_call(method, params)

    monkeypatch.setattr(
        completion_transaction_module,
        "effect_runtime_result",
        counting_effect_call,
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="validated completion",
    )
    assert calls["count"] == 1  # the gate actually ran the declared command
    assert transaction_calls == [
        "todo.completion.reduce",
        "todo.completion.reduce",
    ]
    assert result["ok"] is True
    assert result["changed"] is True
    assert "validation_blocked_completion" not in result
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "done"


def test_missing_validation_executable_returns_typed_receipt(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(registry, validation_command="nonexistent-binary-xyz-12345")
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["status"] == "command_not_run"
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_malformed_validation_command_returns_typed_receipt(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    # Unbalanced quote -> shlex.split raises ValueError -> typed receipt.
    todo = _add_todo(registry, validation_command="echo 'unbalanced")
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["status"] == "command_malformed"
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_validation_command_declared_and_failing_blocks_completion(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(
        registry,
        validation_command=_FAIL_COMMAND,
        validation_label="caller-declared smoke",
    )
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    # Completion is blocked: nothing committed, evidence stays only a claim.
    assert result["ok"] is False
    assert result["completed"] is False
    assert result["changed"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["exit_code"] == 1
    assert receipt["command_label"] == "caller-declared smoke"
    # Privacy invariant preserved.
    assert receipt["stdout_captured"] is False
    assert receipt["stderr_captured"] is False
    assert receipt["local_path_captured"] is False
    # State is unchanged: the todo is still open.
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_no_validation_command_keeps_fast_path_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(registry)  # no validation_command declared
    original_effect_call = completion_transaction_module.effect_runtime_result
    transaction_calls: list[str] = []

    def counting_effect_call(method, params):  # type: ignore[no-untyped-def]
        if method == "todo.completion.reduce":
            transaction_calls.append(method)
        return original_effect_call(method, params)

    monkeypatch.setattr(
        completion_transaction_module,
        "effect_runtime_result",
        counting_effect_call,
    )
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="plain completion",
    )
    assert result["ok"] is True
    assert result["changed"] is True
    assert transaction_calls == ["todo.completion.reduce"]
    assert "validation_blocked_completion" not in result
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "done"


def test_validation_receipt_cannot_commit_a_changed_completion_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(
        registry,
        validation_command=_PASS_COMMAND,
        validation_label="caller-declared smoke",
    )
    original_validation = (
        completion_validation_module._run_declared_completion_validation
    )

    def validate_then_drift(**kwargs):  # type: ignore[no-untyped-def]
        receipt = original_validation(**kwargs)
        source = state.read_text(encoding="utf-8")
        state.write_text(
            source.replace(
                "validation_label=caller-declared%20smoke",
                "validation_label=drifted%20smoke",
            ),
            encoding="utf-8",
        )
        return receipt

    monkeypatch.setattr(
        completion_validation_module,
        "_run_declared_completion_validation",
        validate_then_drift,
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="stale validation receipt",
    )

    assert result["ok"] is False
    assert result["completion_source_drift"] is True
    assert result["changed"] is False
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_validation_receipt_cannot_commit_changed_completion_policy_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(
        registry,
        validation_command=_PASS_COMMAND,
        validation_label="caller-declared smoke",
    )
    original_validation = (
        completion_validation_module._run_declared_completion_validation
    )

    def validate_then_change_registry(**kwargs):  # type: ignore[no-untyped-def]
        receipt = original_validation(**kwargs)
        payload = json.loads(registry.read_text(encoding="utf-8"))
        payload["goals"][0]["coordination"]["registered_agents"].append(
            "codex-new-peer"
        )
        registry.write_text(json.dumps(payload), encoding="utf-8")
        return receipt

    monkeypatch.setattr(
        completion_validation_module,
        "_run_declared_completion_validation",
        validate_then_change_registry,
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="stale registry projection",
    )

    assert result["ok"] is False
    assert result["completion_source_drift"] is True
    assert result["changed"] is False
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_validation_timeout_blocks_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        completion_validation_module, "_COMPLETION_VALIDATION_TIMEOUT_SECONDS", 0.5
    )
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(registry, validation_command=_SLEEP_COMMAND)
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["status"] == "timeout"
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_terminal_replay_short_circuits_before_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(registry, validation_command=_PASS_COMMAND)

    original_runner = completion_validation_module.run_caller_validation
    calls = {"count": 0}

    def counting_runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return original_runner(*args, **kwargs)

    monkeypatch.setattr(completion_validation_module, "run_caller_validation", counting_runner)

    first = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="validated completion",
    )
    assert first["ok"] is True
    assert calls["count"] == 1  # validation ran once on the real completion

    replay = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="duplicate completion",
    )
    # Replay short-circuits before the validation gate; the command is not re-run.
    assert calls["count"] == 1
    assert replay["ok"] is True


def test_per_todo_validation_timeout_overrides_default(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    # A 1s per-todo timeout cuts the sleeping command off long before the 20s
    # module default, and the typed receipt reports the declared value.
    todo = _add_todo(
        registry,
        validation_command=_SLEEP_COMMAND,
        validation_timeout_seconds=1,
    )
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["status"] == "timeout"
    assert "timed out after 1s" in receipt["summary"]
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_validation_timeout_out_of_range_rejected(tmp_path: Path) -> None:
    registry, _state = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="1 and 29"):
        _add_todo(
            registry,
            validation_command=_PASS_COMMAND,
            validation_timeout_seconds=30,
        )


def test_validation_timeout_requires_validation_command(tmp_path: Path) -> None:
    registry, _state = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="requires --validation-command"):
        _add_todo(registry, validation_timeout_seconds=5)


def test_validation_command_json_passing_commits_completion(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    pass_argv = json.dumps([sys.executable, "-c", "raise SystemExit(0)"])
    todo = _add_todo(
        registry,
        validation_command_json=pass_argv,
        validation_label="argv-form smoke",
    )
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="validated completion",
    )
    assert result["ok"] is True
    assert "validation_blocked_completion" not in result
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "done"


def test_validation_command_json_failing_blocks_completion(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    fail_argv = json.dumps([sys.executable, "-c", "raise SystemExit(1)"])
    todo = _add_todo(registry, validation_command_json=fail_argv)
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["exit_code"] == 1
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_validation_command_forms_mutually_exclusive(tmp_path: Path) -> None:
    registry, _state = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="mutually exclusive"):
        _add_todo(
            registry,
            validation_command=_PASS_COMMAND,
            validation_command_json=json.dumps([sys.executable, "-c", "pass"]),
        )


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        '{"not":"a list"}',
        "[]",
        json.dumps([sys.executable, 123]),
        json.dumps([sys.executable, ""]),
    ],
)
def test_validation_command_json_must_be_nonempty_string_array(
    tmp_path: Path, payload: str
) -> None:
    registry, _state = _write_fixture(tmp_path)
    with pytest.raises(ValueError, match="must be a JSON string array"):
        _add_todo(registry, validation_command_json=payload)


def test_validation_timeout_works_with_command_json(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    sleep_argv = json.dumps([sys.executable, "-c", "import time; time.sleep(30)"])
    todo = _add_todo(
        registry,
        validation_command_json=sleep_argv,
        validation_timeout_seconds=1,
    )
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    receipt = result["validation"]
    assert receipt["status"] == "timeout"
    assert "timed out after 1s" in receipt["summary"]
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_corrupted_argv_declaration_fails_closed(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(
        registry,
        validation_command_json=json.dumps(
            [sys.executable, "-c", "raise SystemExit(0)"]
        ),
    )
    # Corrupt the persisted argv declaration in place; completion must run the
    # gate and fail closed as a malformed command, never silently skip it.
    text = state.read_text(encoding="utf-8")
    corrupted, substitutions = re.subn(
        r"validation_command_argv=\S+",
        "validation_command_argv=%5Bbroken",
        text,
    )
    assert substitutions == 1
    state.write_text(corrupted, encoding="utf-8")
    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        agent_id=AGENT,
        evidence="claim of completion",
    )
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["status"] == "declaration_invalid"
    assert "validation_command_argv" in receipt["summary"]
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_empty_argv_declaration_reports_neutral_message(
    tmp_path: Path,
) -> None:
    # An argv declaration collapsing to [] (e.g. corrupted on disk) surfaces
    # the form-neutral empty-command error inside the malformed receipt.
    registry, _state = _write_fixture(tmp_path)
    receipt = completion_validation_module._run_declared_completion_validation(
        validation_command=None,
        validation_argv=[],
        validation_label=None,
        validation_timeout_seconds=None,
        registry_path=registry,
        goal_id=GOAL_ID,
    )
    assert receipt is not None
    assert receipt["status"] == "command_malformed"
    assert "validation command must not be empty" in receipt["summary"]


def _user_todo(state: Path, todo_id: str) -> dict:
    todos = parse_active_state_todos(state.read_text(encoding="utf-8"))
    return next(
        item
        for item in todos["user_todos"]["items"]
        if item["todo_id"] == todo_id
    )


def _spy_validation_runner(monkeypatch: pytest.MonkeyPatch) -> dict:
    original_runner = completion_validation_module.run_caller_validation
    calls = {"count": 0}

    def counting_runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return original_runner(*args, **kwargs)

    monkeypatch.setattr(
        completion_validation_module, "run_caller_validation", counting_runner
    )
    return calls


def test_user_todo_update_done_runs_declared_validation_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="user",
        text="Operator-recorded outcome.",
        task_class="user_action",
        validation_command=_FAIL_COMMAND,
        validation_label="caller-declared smoke",
    )
    calls = _spy_validation_runner(monkeypatch)
    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        status="done",
        evidence="claim of completion",
    )
    # The declared command ran once and blocked the update: nothing committed.
    assert calls["count"] == 1
    assert result["ok"] is False
    assert result["changed"] is False
    assert result["validation_blocked_completion"] is True
    receipt = result["validation"]
    assert receipt["passed"] is False
    assert receipt["exit_code"] == 1
    assert receipt["stdout_captured"] is False
    assert _user_todo(state, str(todo["todo_id"]))["status"] == "open"


def test_user_todo_update_done_without_declaration_keeps_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="user",
        text="Operator-recorded outcome.",
        task_class="user_action",
    )
    calls = _spy_validation_runner(monkeypatch)
    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        status="done",
    )
    assert calls["count"] == 0
    assert result["ok"] is True
    assert "validation_blocked_completion" not in result
    assert _user_todo(state, str(todo["todo_id"]))["status"] == "done"


def test_repeated_done_update_does_not_rerun_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="user",
        text="Operator-recorded outcome.",
        task_class="user_action",
        validation_command=_PASS_COMMAND,
    )
    calls = _spy_validation_runner(monkeypatch)
    first = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        status="done",
        evidence="validated completion",
    )
    assert first["ok"] is True
    assert calls["count"] == 1  # the passing command ran once via the update gate
    assert _user_todo(state, str(todo["todo_id"]))["status"] == "done"

    second = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=str(todo["todo_id"]),
        status="done",
        note="re-acknowledged",
    )
    # Already-completed short-circuit: the command is not re-run.
    assert second["ok"] is True
    assert calls["count"] == 1
    assert _user_todo(state, str(todo["todo_id"]))["status"] == "done"


def test_agent_todo_update_done_keeps_guard_error_without_running_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_todo(registry, validation_command=_FAIL_COMMAND)
    calls = _spy_validation_runner(monkeypatch)
    with pytest.raises(ValueError, match="must use complete_goal_todo"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=str(todo["todo_id"]),
            status="done",
        )
    # The gate never runs for agent sections; the pre-existing guard fires.
    assert calls["count"] == 0
    assert _agent_todo(state, str(todo["todo_id"]))["status"] == "open"


def _add_event_only_todo(
    state: Path,
    *,
    todo_id: str = "todo_event_validation",
    validation_command: Any = None,
    validation_command_argv: Any = None,
    validation_label: Any = None,
    validation_timeout_seconds: Any = None,
    event_log: Path | None = None,
) -> str:
    store = AppendOnlyStateEventStore(event_log or state.with_name("events.jsonl"))
    payload: dict[str, Any] = {
        "role": "agent",
        "title": "Deliver one event-projected change.",
        "task_class": "advancement_task",
        "claimed_by": AGENT,
    }
    if validation_command is not None:
        payload["validation_command"] = validation_command
    if validation_command_argv is not None:
        payload["validation_command_argv"] = validation_command_argv
    if validation_label is not None:
        payload["validation_label"] = validation_label
    if validation_timeout_seconds is not None:
        payload["validation_timeout_seconds"] = validation_timeout_seconds
    store.append(
        make_state_event(
            event_id=f"evt-{todo_id}-add",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": todo_id},
            payload=payload,
            recorded_at="2026-08-22T00:00:00+00:00",
        )
    )
    return todo_id


def _defer_event_todo(state: Path, *, todo_id: str) -> None:
    AppendOnlyStateEventStore(state.with_name("events.jsonl")).append(
        make_state_event(
            event_id=f"evt-{todo_id}-defer",
            goal_id=GOAL_ID,
            event_type=TODO_DEFERRED,
            refs={"todo_id": todo_id},
            payload={
                "reason": "waiting for owner signal",
                "resume_when": "manual",
            },
            recorded_at="2026-08-22T00:01:00+00:00",
        )
    )


def _event_todo_completed_count(event_log: Path) -> int:
    events = AppendOnlyStateEventStore(event_log).load()
    return sum(event["event_type"] == TODO_COMPLETED for event in events)


def _set_registry_event_log(registry: Path, event_log: Path) -> None:
    data = json.loads(registry.read_text(encoding="utf-8"))
    data["goals"][0]["event_log"] = str(event_log)
    registry.write_text(json.dumps(data), encoding="utf-8")


def test_event_projection_preserves_private_validation_and_public_marker() -> None:
    todo_id = "todo_event_projected_validation"
    events = [
        make_state_event(
            event_id=f"evt-{todo_id}-add",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": todo_id},
            payload={
                "role": "agent",
                "title": "Deliver one event-projected change.",
                "task_class": "advancement_task",
                "claimed_by": AGENT,
                "validation_command_argv": [sys.executable, "-c", "pass"],
                "validation_label": "event argv smoke",
                "validation_timeout_seconds": 5,
            },
            recorded_at="2026-08-22T00:00:00+00:00",
        )
    ]

    projection = build_state_projection(events, goal_id=GOAL_ID)
    item = projection["agent_todos"]["items"][0]

    assert item["validation_command_argv"] == [sys.executable, "-c", "pass"]
    assert item["validation_label"] == "event argv smoke"
    assert item["validation_timeout_seconds"] == 5
    rendered = "\n".join(render_todo_markdown(item))
    assert "validation_command_argv=" in rendered
    public = project_completion_validation_authority(item)
    assert public["completion_validation_required"] is True
    assert "validation_command" not in public
    assert "validation_command_argv" not in public
    assert "validation_label" not in public
    assert "validation_timeout_seconds" not in public


def test_event_projected_failing_validation_blocks_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        validation_command=_FAIL_COMMAND,
        validation_label="event-projected smoke",
    )
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="claim of completion",
        no_followup=True,
    )

    assert calls["count"] == 1
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    assert result["validation"]["passed"] is False
    assert _event_todo_completed_count(state.with_name("events.jsonl")) == 0


def test_event_projected_deferred_validation_replays_without_running_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        todo_id="todo_event_deferred_validation",
        validation_command=_FAIL_COMMAND,
    )
    _defer_event_todo(state, todo_id=todo_id)
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="terminal replay request",
        no_followup=True,
    )

    assert calls["count"] == 0
    assert result["ok"] is True
    assert result["idempotent_replay"] is True
    assert result["changed"] is False
    assert "validation_blocked_completion" not in result
    assert _event_todo_completed_count(state.with_name("events.jsonl")) == 0


def test_noncanonical_sidecar_cannot_inject_validation_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = "todo_event_two_logs"
    canonical = state.with_name("canonical-events.jsonl")
    _add_event_only_todo(state, todo_id=todo_id, event_log=canonical)
    _add_event_only_todo(
        state,
        todo_id=todo_id,
        validation_command=_FAIL_COMMAND,
    )
    _set_registry_event_log(registry, canonical)
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="canonical source has no declaration",
        no_followup=True,
    )

    assert calls["count"] == 0
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["source"] == "event_log"
    assert _event_todo_completed_count(canonical) == 1
    assert _event_todo_completed_count(state.with_name("events.jsonl")) == 0


def test_empty_earlier_candidate_does_not_replace_canonical_validation_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        todo_id="todo_event_after_empty_candidate",
        validation_command=_FAIL_COMMAND,
    )
    empty_candidate = state.with_name("empty-events.jsonl")
    empty_candidate.touch()
    _set_registry_event_log(registry, empty_candidate)
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="canonical fallback validation must run",
        no_followup=True,
    )

    assert calls["count"] == 1
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    assert _event_todo_completed_count(state.with_name("events.jsonl")) == 0
    assert empty_candidate.read_text(encoding="utf-8") == ""


def test_corrupted_earlier_candidate_does_not_block_canonical_completion_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        todo_id="todo_event_after_corrupted_candidate",
        validation_command=_PASS_COMMAND,
    )
    canonical = state.with_name("events.jsonl")
    corrupted_candidate = state.with_name("corrupted-events.jsonl")
    corrupted_candidate.write_text("{not-json\n", encoding="utf-8")
    _set_registry_event_log(registry, corrupted_candidate)
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="canonical source remains usable",
        no_followup=True,
    )

    assert calls["count"] == 1
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["source"] == "event_log"
    assert _event_todo_completed_count(canonical) == 1
    assert corrupted_candidate.read_text(encoding="utf-8") == "{not-json\n"


@pytest.mark.parametrize("timeout_value", [0, 30, "not-int", {"seconds": 5}])
def test_event_projected_invalid_timeout_rejects_without_running_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    timeout_value: Any,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        todo_id="todo_event_invalid_timeout",
        validation_command=_PASS_COMMAND,
        validation_timeout_seconds=timeout_value,
    )
    calls = _spy_validation_runner(monkeypatch)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="invalid persisted timeout must fail closed",
        no_followup=True,
    )

    assert calls["count"] == 0
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    assert result["validation"]["status"] == "declaration_invalid"
    assert "validation_timeout_seconds" in result["validation"]["summary"]
    assert _event_todo_completed_count(state.with_name("events.jsonl")) == 0


def test_event_projected_source_drift_after_validation_blocks_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo_id = _add_event_only_todo(
        state,
        todo_id="todo_event_source_drift",
        validation_command=_PASS_COMMAND,
    )
    event_log = state.with_name("events.jsonl")
    calls = {"count": 0}

    def drifting_runner(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls["count"] += 1
        AppendOnlyStateEventStore(event_log).append(
            make_state_event(
                event_id=f"evt-{todo_id}-drift",
                goal_id=GOAL_ID,
                event_type=TODO_UPDATED,
                refs={"todo_id": todo_id},
                payload={"title": "Changed after validation."},
                recorded_at="2026-08-22T00:02:00+00:00",
            )
        )
        return {
            "schema_version": completion_validation_module.CALLER_VALIDATION_RECEIPT_SCHEMA_VERSION,
            "command_label": "todo completion validation",
            "exit_code": 0,
            "passed": True,
            "status": "passed",
            "summary": "validation passed before source drift",
            "stdout_captured": False,
            "stderr_captured": False,
            "local_path_captured": False,
        }

    monkeypatch.setattr(
        completion_validation_module,
        "run_caller_validation",
        drifting_runner,
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo_id,
        agent_id=AGENT,
        evidence="validated stale source",
        no_followup=True,
    )

    assert calls["count"] == 1
    assert result["ok"] is False
    assert result["validation_blocked_completion"] is True
    assert result["validation"]["status"] == "source_drift"
    assert _event_todo_completed_count(event_log) == 0
