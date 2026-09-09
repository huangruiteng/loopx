"""Monitor routing errors must be rejected before any observation writeback."""
import pytest

from test_monitor_followthrough_contract import _write_fixture, _add_monitor, GOAL_ID, AGENT_ID
from loopx.control_plane.scheduler.monitor_poll_writeback import write_monitor_poll_todo_state
from loopx.control_plane.testing.canary_harness import run_json_cli


@pytest.mark.parametrize("invalid", [
    {"next_required_capabilities": ["filesystem-write", "not/a/capability"]},
    {"next_claimed_by": "invalid/actor"},
    {"material_change": False},
])
def test_invalid_successor_intent_does_not_partially_update_monitor(tmp_path, invalid):
    registry, runtime, state = _write_fixture(tmp_path)
    monitor = _add_monitor(registry, text="Watch a public target.", target_key="public-target")
    before = state.read_bytes()
    with pytest.raises(ValueError):
        write_monitor_poll_todo_state(registry_path=registry, runtime_root=runtime,
            goal_id=GOAL_ID, todo_id=monitor["todo_id"], execute=True,
            generated_at="2026-09-09T12:00:00Z", result_hash="revision-a", agent_id=AGENT_ID,
            next_agent_todo="Validate the material change.", next_action_kind="validate",
            **{"material_change": True, **invalid})
    assert state.read_bytes() == before


def test_public_monitor_poll_accepts_repository_and_action_aliases(tmp_path):
    registry, runtime, _state = _write_fixture(tmp_path)
    monitor = _add_monitor(registry, text="Watch a public target.", target_key="public-target",
        next_due_at="2000-01-01T00:00:00Z")
    result = run_json_cli("quota", "monitor-poll", "--goal-id", GOAL_ID,
        "--agent-id", AGENT_ID, "--runtime-profile", "generic_cli",
        "--todo-id", monitor["todo_id"], "--result-hash", "revision-a", "--material-change",
        "--next-agent-todo", "Validate the transition.", "--next-action-kind", "VALIDATE",
        "--next-task-repository", "https://github.com/example/repo.git",
        "--next-required-capability", "file--write", "--execute",
        registry_path=registry, runtime_root=runtime)
    successor = result["todo_writeback"]["next_todos"][0]
    assert successor["action_kind"] == "validate"
    assert successor["task_repository"] == "git:github.com/example/repo"
    assert successor["required_capabilities"] == ["file__write"]
    assert successor["task_class"] == "advancement_task"
    assert successor["unblocks_todo_id"] == monitor["todo_id"]
