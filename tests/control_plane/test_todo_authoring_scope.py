"""Explicit authoring scope outranks actor-based defaults, never authority."""
from pathlib import Path

import pytest

from loopx.control_plane.testing.canary_harness import run_json_cli_result, write_fixture_registry
from loopx.control_plane.todos.active_state_editing import find_todo_block
from loopx.todos import add_goal_todo, update_goal_todo

GOAL = "authoring-scope"


@pytest.fixture
def authored_goal(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text("# Goal\n\n## Agent Todo\n\n## User Todo\n", encoding="utf-8")
    registry = tmp_path / "registry.json"
    write_fixture_registry(project=project, runtime_root=tmp_path / "runtime",
        registry_path=registry, goal_id=GOAL, domain="scope-test",
        adapter_kind="generic_project_goal_v0", registered_agents=["agent-a", "agent-b"],
        quota_allowed_slots=None)
    return registry, state


def add(registry, state, **intent):
    return add_goal_todo(registry_path=registry, goal_id=GOAL, state_file=state,
        role="user", text="Decide the next step", **intent)


def stored(state: Path, todo_id):
    return find_todo_block(state.read_text(encoding="utf-8").splitlines(), todo_id=todo_id)[4]


@pytest.mark.parametrize("intent, bound, goal, blocks, global_", [
    ({"task_class": "user_action", "agent_id": "agent-a"}, "agent-a", False, None, False),
    ({"task_class": "user_action", "agent_id": "agent-a", "goal_bound": True}, None, True, None, False),
    ({"task_class": "user_gate", "agent_id": "agent-a"}, "agent-a", False, "agent-a", False),
    ({"task_class": "user_gate", "agent_id": "agent-a", "blocks_agent": "agent-b"}, "agent-b", False, "agent-b", False),
    ({"task_class": "user_gate", "agent_id": "agent-a", "global_gate": True}, None, True, None, True),
])
def test_add_persists_declared_scope_not_the_author_identity(authored_goal, intent, bound, goal, blocks, global_):
    registry, state = authored_goal
    result = add(registry, state, **intent)
    todo = stored(state, result["todo_id"])
    assert todo.get("bound_agent") == bound
    assert bool(todo.get("goal_bound")) == goal
    assert todo.get("blocks_agent") == blocks
    assert bool(todo.get("global_gate")) == global_


@pytest.mark.parametrize("intent", [
    {"global_gate": True, "bound_agent": "agent-a"},
    {"blocks_agent": "agent-a", "bound_agent": "agent-b"},
    {"blocks_agent": "agent-a", "goal_bound": True},
])
def test_update_rejects_explicit_scope_conflicts_without_writing(authored_goal, intent):
    registry, state = authored_goal
    result = add(registry, state, task_class="user_gate", global_gate=True, goal_bound=True)
    before = state.read_bytes()
    with pytest.raises(ValueError):
        update_goal_todo(registry_path=registry, goal_id=GOAL, state_file=state,
            todo_id=result["todo_id"], agent_id="agent-a", role="user",
            clear_global_gate=not intent.get("global_gate", False), **intent)
    assert state.read_bytes() == before


def test_real_cli_requires_explicit_global_flag_and_preserves_dry_run(authored_goal):
    registry, state = authored_goal
    common = ("todo", "add", "--goal-id", GOAL, "--role", "user", "--task-class", "user_gate",
        "--text", "Decide whole-goal policy", "--state-file", str(state))
    before = state.read_bytes()
    code, payload = run_json_cli_result(*common, "--goal-bound", registry_path=registry)
    assert code != 0
    assert state.read_bytes() == before
    code, preview = run_json_cli_result(*common, "--global-gate", "--agent-id", "agent-a", "--dry-run", registry_path=registry)
    assert code == 0, preview
    assert state.read_bytes() == before
    code, written = run_json_cli_result(*common, "--global-gate", "--agent-id", "agent-a", registry_path=registry)
    assert code == 0, written
    todo_id = written["todo_id"]
    assert stored(state, todo_id)["global_gate"] is True
    code, edited = run_json_cli_result("todo", "update", "--goal-id", GOAL, "--todo-id", todo_id,
        "--role", "user", "--agent-id", "agent-a", "--clear-global-gate", "--blocks-agent", "agent-b",
        "--state-file", str(state), registry_path=registry)
    assert code == 0, edited
    assert stored(state, todo_id)["bound_agent"] == "agent-b"
    assert not stored(state, todo_id).get("global_gate")


def test_missing_scope_never_creates_global_gate(authored_goal):
    registry, state = authored_goal
    before = state.read_bytes()
    for intent in ({}, {"goal_bound": True}):
        with pytest.raises(ValueError, match="scope|binding"):
            add(registry, state, task_class="user_gate", **intent)
        assert state.read_bytes() == before
