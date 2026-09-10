"""Public update invariants: a partial edit must not invalidate an armed wait."""
import pytest

from loopx.todos import add_goal_todo, update_goal_todo
from loopx.control_plane.testing.canary_harness import run_json_cli_result
from tests.control_plane.test_monitor_followthrough_contract import (
    AGENT_ID, GOAL_ID, _add_monitor, _write_fixture,
)


def waiting_goal(tmp_path):
    registry, runtime, state = _write_fixture(tmp_path)
    monitor = _add_monitor(registry, text="Observe fixture", target_key="fixture")
    update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
        todo_id=monitor["todo_id"], agent_id=AGENT_ID,
        monitor_metadata={"material_change_generation": "3"})
    def add(text):
        return add_goal_todo(registry_path=registry, goal_id=GOAL_ID,
            role="agent", task_class="advancement_task", text=text, claimed_by=AGENT_ID)
    waiting, successor = add("Await observation"), add("Independent work")
    update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
        todo_id=waiting["todo_id"], agent_id=AGENT_ID,
        resume_when=f"monitor_changed:{monitor['todo_id']}",
        successor_todo_ids=[successor["todo_id"]])
    return registry, runtime, state, waiting, successor


@pytest.mark.parametrize("edit", [{"successor_todo_ids": []}, {"status": "blocked"},
                                    {"task_class": "continuous_monitor"}])
def test_partial_edit_cannot_invalidate_retained_monitor_wait(tmp_path, edit):
    registry, _, state, waiting, _ = waiting_goal(tmp_path)
    before = state.read_bytes()
    with pytest.raises(ValueError, match="external-wait"):
        update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
            todo_id=waiting["todo_id"], agent_id=AGENT_ID, **edit)
    assert state.read_bytes() == before


def test_clear_condition_and_successors_together_is_valid(tmp_path):
    registry, _, state, waiting, _ = waiting_goal(tmp_path)
    result = update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
        todo_id=waiting["todo_id"], agent_id=AGENT_ID,
        clear_resume_when=True, successor_todo_ids=[])
    assert result["resume_when"] is None
    assert result["resume_monitor_generation"] is None
    assert result["successor_todo_ids"] == []


def test_copy_edit_preserves_existing_wait_fence(tmp_path):
    registry, _, _, waiting, _ = waiting_goal(tmp_path)
    result = update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
        todo_id=waiting["todo_id"], agent_id=AGENT_ID, note="Clarify context")
    assert result["resume_when"].startswith("monitor_changed:")
    assert result["resume_monitor_generation"] == 3
    assert "external_wait_transition" not in result


def test_real_cli_rejects_partial_wait_edit_and_supports_explicit_repair(tmp_path):
    registry, runtime, state, waiting, _ = waiting_goal(tmp_path)
    common = ("todo", "update", "--goal-id", GOAL_ID, "--todo-id", waiting["todo_id"],
              "--agent-id", AGENT_ID, "--status", "blocked")
    before = state.read_bytes()
    code, rejected = run_json_cli_result(*common, registry_path=registry, runtime_root=runtime)
    assert code != 0, rejected
    assert state.read_bytes() == before
    code, accepted = run_json_cli_result(*common, "--clear-resume-when", "--dry-run",
        registry_path=registry, runtime_root=runtime)
    assert code == 0, accepted
    assert state.read_bytes() == before


def test_public_update_uses_one_scope_wait_field_crossing(tmp_path, monkeypatch):
    from loopx.control_plane.todos import line_update, authoring_scope, resume_condition
    registry, _, _, waiting, successor = waiting_goal(tmp_path)
    actual = line_update.effect_runtime_result
    calls = []
    def traced(method, params):
        calls.append(method)
        return actual(method, params)
    for module in (line_update, authoring_scope, resume_condition):
        monkeypatch.setattr(module, "effect_runtime_result", traced)
    result = update_goal_todo(registry_path=registry, goal_id=GOAL_ID,
        todo_id=waiting["todo_id"], agent_id=AGENT_ID,
        successor_todo_ids=[successor["todo_id"]])
    assert result["resume_monitor_generation"] == 3
    assert calls == ["todo.public_update.plan"]
