from __future__ import annotations

from pathlib import Path

import pytest

from loopx.control_plane.testing.canary_harness import (
    run_json_cli,
    run_json_cli_result,
    write_fixture_registry,
)


GOAL_ID = "decision-scope-cli-validation"
VALID_SCOPE = "direction:action:release_route"
INVALID_SCOPE = "not-a-decision-scope"


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Keep decision-scope writes valid.\n\n"
        "## Next Action\n\n"
        "- Validate the next todo write.\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="decision-scope-cli-validation",
        adapter_kind="generic_project_goal_v0",
    )
    return registry_path, state_file


def _scope_args(flag: str, values: list[str]) -> list[str]:
    return [part for value in values for part in (flag, value)]


@pytest.mark.parametrize(
    ("role", "task_class", "flag", "values", "error_fragment"),
    [
        (
            "user",
            "user_gate",
            "--decision-scope",
            [INVALID_SCOPE],
            "decision_scope must use kind:granularity:scope_key",
        ),
        (
            "agent",
            "advancement_task",
            "--required-decision-scope",
            [VALID_SCOPE, INVALID_SCOPE],
            "required_decision_scopes must contain kind:granularity:scope_key tokens",
        ),
    ],
)
def test_todo_add_rejects_invalid_decision_scope_tokens_without_writing(
    tmp_path: Path,
    role: str,
    task_class: str,
    flag: str,
    values: list[str],
    error_fragment: str,
) -> None:
    registry_path, state_file = _write_fixture(tmp_path)
    original = state_file.read_text(encoding="utf-8")

    returncode, payload = run_json_cli_result(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        role,
        "--task-class",
        task_class,
        "--text",
        f"Validate the {role} decision scope.",
        *_scope_args(flag, values),
        registry_path=registry_path,
    )

    assert returncode != 0, payload
    assert error_fragment in payload["error"], payload
    readback = run_json_cli(
        "todo",
        "list",
        "--goal-id",
        GOAL_ID,
        registry_path=registry_path,
    )
    assert readback["todo_count"] == 0, readback
    assert state_file.read_text(encoding="utf-8") == original


def test_todo_update_rejects_invalid_decision_scope_tokens_without_data_loss(
    tmp_path: Path,
) -> None:
    registry_path, state_file = _write_fixture(tmp_path)
    gate = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "user",
        "--task-class",
        "user_gate",
        "--text",
        "Choose the release route.",
        "--decision-scope",
        VALID_SCOPE,
        registry_path=registry_path,
    )
    agent = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "agent",
        "--task-class",
        "advancement_task",
        "--text",
        "Publish through the approved release route.",
        "--required-decision-scope",
        VALID_SCOPE,
        registry_path=registry_path,
    )
    original = state_file.read_text(encoding="utf-8")

    cases = [
        (
            gate["todo_id"],
            ["--decision-scope", INVALID_SCOPE],
            "decision_scope must use kind:granularity:scope_key",
            "decision_scope",
        ),
        (
            agent["todo_id"],
            _scope_args(
                "--required-decision-scope",
                [VALID_SCOPE, INVALID_SCOPE],
            ),
            "required_decision_scopes must contain kind:granularity:scope_key tokens",
            "required_decision_scopes",
        ),
    ]
    for todo_id, invalid_args, error_fragment, field in cases:
        returncode, payload = run_json_cli_result(
            "todo",
            "update",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            todo_id,
            *invalid_args,
            registry_path=registry_path,
        )

        assert returncode != 0, payload
        assert error_fragment in payload["error"], payload
        readback = run_json_cli(
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            todo_id,
            registry_path=registry_path,
        )
        if field == "decision_scope":
            assert readback["todo"][field]["scope_key"] == "release_route"
        else:
            assert [
                scope["scope_key"] for scope in readback["todo"][field]
            ] == ["release_route"]
        assert state_file.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("decision_outcome", "expected_status", "scope_retained"),
    [
        ("approve", "open", False),
        ("reject", "blocked", True),
        ("cancel", "blocked", True),
    ],
)
def test_todo_complete_cli_applies_explicit_user_gate_outcome(
    tmp_path: Path,
    decision_outcome: str,
    expected_status: str,
    scope_retained: bool,
) -> None:
    registry_path, _state_file = _write_fixture(tmp_path)
    target = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "agent",
        "--task-class",
        "advancement_task",
        "--status",
        "blocked",
        "--text",
        "Read restricted material only after an explicit decision.",
        "--required-decision-scope",
        "private_read:project:restricted_material",
        registry_path=registry_path,
    )
    gate = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "user",
        "--task-class",
        "user_gate",
        "--text",
        "Decide whether this agent may read restricted material.",
        "--decision-scope",
        "private_read:project:restricted_material",
        "--unblocks-todo-id",
        target["todo_id"],
        registry_path=registry_path,
    )

    completed = run_json_cli(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        gate["todo_id"],
        "--role",
        "user",
        "--decision-outcome",
        decision_outcome,
        "--evidence",
        f"owner recorded {decision_outcome}",
        registry_path=registry_path,
    )

    assert completed["decision_outcome"] == decision_outcome
    target_readback = run_json_cli(
        "todo",
        "list",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        target["todo_id"],
        registry_path=registry_path,
    )["todo"]
    assert target_readback["status"] == expected_status
    assert bool(target_readback.get("required_decision_scopes")) is scope_retained
    if decision_outcome == "approve":
        assert target_readback.get("decision_scope_outcomes", []) == []
    else:
        assert target_readback["decision_scope_outcomes"][0]["outcome"] == (
            decision_outcome
        )


def test_todo_complete_cli_rejects_ambiguous_user_gate_completion(
    tmp_path: Path,
) -> None:
    registry_path, state_file = _write_fixture(tmp_path)
    gate = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "user",
        "--task-class",
        "user_gate",
        "--text",
        "Decide whether publication is authorized.",
        "--decision-scope",
        VALID_SCOPE,
        registry_path=registry_path,
    )
    original = state_file.read_text(encoding="utf-8")

    returncode, payload = run_json_cli_result(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        gate["todo_id"],
        "--role",
        "user",
        "--evidence",
        "ambiguous completion",
        registry_path=registry_path,
    )

    assert returncode != 0
    assert "user_gate completion requires decision_outcome" in payload["error"]
    assert state_file.read_text(encoding="utf-8") == original
