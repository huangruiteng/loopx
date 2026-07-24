from __future__ import annotations

from pathlib import Path

import pytest

from loopx.control_plane.scheduler.monitor_poll_writeback import (
    resolve_monitor_todo_item,
)
from loopx.control_plane.scheduler.monitor_todo import (
    monitor_todo_is_actionable_open,
)
from loopx.control_plane.testing.canary_harness import (
    run_json_cli,
    run_json_cli_result,
    write_fixture_registry,
)
from loopx.control_plane.todos.contract import resolve_next_user_task_class
from loopx.quota import record_quota_monitor_poll
from loopx.status import collect_status
from loopx.todos import add_goal_todo, list_goal_todos, update_goal_todo


GOAL_ID = "monitor-followthrough-fixture"
AGENT_ID = "codex-quality-qualification"


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry = project / ".loopx" / "registry.json"
    state.parent.mkdir(parents=True)
    state.write_text(
        "---\nstatus: active\n---\n\n# Active Goal State\n\n## Agent Todo\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry,
        goal_id=GOAL_ID,
        domain="loopx-platform",
        adapter_kind="harness_self_improvement",
        registered_agents=[AGENT_ID, "codex-main-control"],
        quota_allowed_slots=None,
    )
    return registry, runtime, state


def _add_monitor(
    registry: Path,
    *,
    text: str,
    target_key: str,
    next_due_at: str = "2099-01-01T00:00:00+00:00",
) -> dict:
    return add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text=text,
        task_class="continuous_monitor",
        claimed_by=AGENT_ID,
        monitor_metadata={
            "target_key": target_key,
            "cadence": "1h",
            "next_due_at": next_due_at,
        },
    )


def test_exact_todo_id_precedes_ambiguous_target_key(tmp_path: Path) -> None:
    registry, _runtime, _state = _write_fixture(tmp_path)
    first = _add_monitor(registry, text="Poll the first target.", target_key="shared")
    second = _add_monitor(registry, text="Poll the second target.", target_key="shared")

    resolved = resolve_monitor_todo_item(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=second["todo_id"],
        target_key="shared",
    )

    assert resolved["todo_id"] == second["todo_id"]
    with pytest.raises(ValueError, match="matched multiple todos"):
        resolve_monitor_todo_item(
            registry_path=registry,
            goal_id=GOAL_ID,
            target_key="shared",
        )
    assert first["todo_id"] != second["todo_id"]


def test_monitor_resume_when_is_rejected_without_legacy_bypass(
    tmp_path: Path,
) -> None:
    registry, _runtime, _state = _write_fixture(tmp_path)

    with pytest.raises(ValueError, match="continuous_monitor todos cannot use resume_when"):
        add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Poll a merge target.",
            task_class="continuous_monitor",
            claimed_by=AGENT_ID,
            resume_when="pr_merged:owner/repo#42",
            monitor_metadata={"target_key": "public-pr:42", "cadence": "1h"},
        )

    monitor = _add_monitor(
        registry,
        text="Poll a legacy merge target.",
        target_key="legacy-pr:42",
    )
    with pytest.raises(ValueError, match="continuous_monitor todos cannot use resume_when"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=monitor["todo_id"],
            agent_id=AGENT_ID,
            resume_when="pr_merged:owner/repo#42",
        )

    assert monitor_todo_is_actionable_open(
        {
            "status": "open",
            "task_class": "continuous_monitor",
            "resume_when": "pr_merged:owner/repo#42",
            "resume_ready": False,
        }
    ) is False


def test_material_poll_reloads_status_and_projects_declared_successor(
    tmp_path: Path,
) -> None:
    registry, runtime, state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a public release target.",
        target_key="public-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )

    result = run_json_cli(
        "quota",
        "monitor-poll",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--runtime-profile",
        "generic_cli",
        "--todo-id",
        monitor["todo_id"],
        "--target-key",
        "public-release:42",
        "--result-hash",
        "merged-42",
        "--material-change",
        "--next-agent-todo",
        "Validate the exact merged release head.",
        "--next-claimed-by",
        AGENT_ID,
        "--execute",
        registry_path=registry,
        runtime_root=runtime,
    )

    successor = result["todo_writeback"]["next_todos"][0]
    assert successor["status"] == "open"
    assert result["after"]["selected_todo"]["todo_id"] == successor["todo_id"]
    assert result["after"]["effective_action"] == "normal_run"
    assert "Validate the exact merged release head." in state.read_text(encoding="utf-8")


def test_material_poll_user_action_does_not_block_existing_advancement(
    tmp_path: Path,
) -> None:
    registry, runtime, _state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a public release target.",
        target_key="public-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )
    advancement = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Continue the independent quality task.",
        task_class="advancement_task",
        claimed_by=AGENT_ID,
    )

    result = run_json_cli(
        "quota",
        "monitor-poll",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--runtime-profile",
        "generic_cli",
        "--todo-id",
        monitor["todo_id"],
        "--result-hash",
        "review-ready-42",
        "--material-change",
        "--next-user-todo",
        "Review the validated release when convenient.",
        "--next-user-task-class",
        "user_action",
        "--execute",
        registry_path=registry,
        runtime_root=runtime,
    )

    reminder = result["todo_writeback"]["next_todos"][0]
    assert reminder["task_class"] == "user_action"
    assert reminder["bound_agent"] == AGENT_ID
    assert reminder["blocks_agent"] is None
    assert reminder["unblocks_todo_id"] is None
    assert result["after"]["effective_action"] == "normal_run"
    assert result["after"]["selected_todo"]["todo_id"] == advancement["todo_id"]


def test_material_poll_user_followup_requires_explicit_class_without_writeback(
    tmp_path: Path,
) -> None:
    registry, runtime, state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a protected release target.",
        target_key="protected-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )
    before_state = state.read_text(encoding="utf-8")
    before_todos = list_goal_todos(
        registry_path=registry,
        goal_id=GOAL_ID,
    )

    returncode, result = run_json_cli_result(
        "quota",
        "monitor-poll",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--runtime-profile",
        "generic_cli",
        "--todo-id",
        monitor["todo_id"],
        "--result-hash",
        "approval-required-42",
        "--material-change",
        "--next-user-todo",
        "Approve the protected release.",
        "--execute",
        registry_path=registry,
        runtime_root=runtime,
    )

    assert returncode == 1
    assert result["ok"] is False
    assert result["reason"] == (
        "--next-user-todo requires explicit --next-user-task-class "
        "user_action|user_gate"
    )
    assert "todo_writeback" not in result
    assert state.read_text(encoding="utf-8") == before_state
    assert (
        list_goal_todos(
            registry_path=registry,
            goal_id=GOAL_ID,
        )
        == before_todos
    )


def test_material_poll_explicit_user_gate_blocks_bound_agent(
    tmp_path: Path,
) -> None:
    registry, runtime, _state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a protected release target.",
        target_key="protected-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )

    result = run_json_cli(
        "quota",
        "monitor-poll",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--runtime-profile",
        "generic_cli",
        "--todo-id",
        monitor["todo_id"],
        "--result-hash",
        "approval-required-42",
        "--material-change",
        "--next-user-todo",
        "Approve the protected release.",
        "--next-user-task-class",
        "user_gate",
        "--execute",
        registry_path=registry,
        runtime_root=runtime,
    )

    gate = result["todo_writeback"]["next_todos"][0]
    assert gate["task_class"] == "user_gate"
    assert gate["bound_agent"] == AGENT_ID
    assert gate["blocks_agent"] == AGENT_ID
    assert gate["unblocks_todo_id"] == monitor["todo_id"]
    assert result["after"]["effective_action"] == "operator_gate_notify"


def test_next_user_task_class_contract_requires_explicit_semantics() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "--next-user-todo requires explicit --next-user-task-class "
            r"user_action\|user_gate"
        ),
    ):
        resolve_next_user_task_class("Review the release.", None)

    assert (
        resolve_next_user_task_class("Review the release.", "user_action")
        == "user_action"
    )
    assert (
        resolve_next_user_task_class("Approve the release.", "user_gate")
        == "user_gate"
    )


def test_monitor_poll_user_task_class_requires_user_followup(
    tmp_path: Path,
) -> None:
    registry, runtime, _state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a public release target.",
        target_key="public-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )

    returncode, result = run_json_cli_result(
        "quota",
        "monitor-poll",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--runtime-profile",
        "generic_cli",
        "--todo-id",
        monitor["todo_id"],
        "--result-hash",
        "review-ready-42",
        "--material-change",
        "--next-user-task-class",
        "user_action",
        "--execute",
        registry_path=registry,
        runtime_root=runtime,
    )

    assert returncode == 1
    assert result["ok"] is False
    assert result["reason"] == "--next-user-task-class requires --next-user-todo"


def test_material_poll_reload_failure_reports_persisted_writeback(
    tmp_path: Path,
) -> None:
    registry, runtime, state = _write_fixture(tmp_path)
    monitor = _add_monitor(
        registry,
        text="Poll a public release target.",
        target_key="public-release:42",
        next_due_at="2000-01-01T00:00:00+00:00",
    )
    status_payload = collect_status(
        registry_path=registry,
        runtime_root_override=str(runtime),
        scan_roots=[Path(__file__).resolve()],
        limit=20,
    )

    def fail_status_reload() -> dict:
        raise RuntimeError("synthetic status reload failure")

    result = record_quota_monitor_poll(
        status_payload,
        goal_id=GOAL_ID,
        registry_path=registry,
        execute=True,
        source="heartbeat",
        agent_id=AGENT_ID,
        todo_id=monitor["todo_id"],
        result_hash="merged-42",
        material_change=True,
        next_agent_todo="Validate the persisted material transition successor.",
        status_reloader=fail_status_reload,
    )

    assert result["ok"] is True
    warning = result["status_reload_warning"]
    assert warning["schema_version"] == "monitor_poll_status_reload_warning_v0"
    assert warning["error_type"] == "RuntimeError"
    assert warning["persisted_writeback"] is True
    assert warning["after_projection_fresh"] is False
    assert "rerun quota should-run" in warning["recommended_action"]
    assert result["monitor_event"]["status_reload_warning"] == warning
    assert result["todo_writeback"]["next_todos"]
    assert "Validate the persisted material transition successor." in state.read_text(
        encoding="utf-8"
    )


def test_todo_help_distinguishes_assignment_from_lifecycle_actor() -> None:
    from loopx.cli import build_parser

    parser = build_parser()
    todo_action = next(
        action
        for action in parser._actions
        if getattr(action, "dest", None) == "command"
    )
    todo_parser = todo_action.choices["todo"]
    claimed_by = next(
        action for action in todo_parser._actions if action.dest == "claimed_by"
    )
    agent_id = next(
        action for action in todo_parser._actions if action.dest == "agent_id"
    )

    assert "assignment target" in claimed_by.help
    assert "not the lifecycle actor" in claimed_by.help
    assert "attribute the lifecycle actor" in agent_id.help
