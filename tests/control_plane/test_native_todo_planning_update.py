"""Real CLI and canonical FileAuthorityStore; no production registry or promotion."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from canonical_authority_fixture import initialize_canonical_authority

from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.control_plane.todos.contract import format_todo_metadata_line
from loopx.todos import list_goal_todos, update_goal_todo


def fixture(tmp_path: Path, promoted: bool) -> tuple[Path, Path]:
    project = tmp_path / "project"
    state = project / ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    rows = "\n".join(
        "- [ ] " + text + "\n" + format_todo_metadata_line(
            todo_id=todo_id, status="open", task_class="advancement_task",
            claimed_by=owner, note="Preserved note",
        ) for todo_id, text, owner in [
            ("todo_target", "Synthetic task", "agent-a"),
            ("todo_other", "Independent task", "agent-b"),
        ]
    )
    state.write_text("# Goal\n\n## User Todo / Owner Review Reading Queue\n\n"
                     "## Agent Todo\n\n" + rows + "\n\n## Completed Work Archive\n", encoding="utf-8")
    registry = tmp_path / "registry.json"
    runtime = tmp_path / "runtime"
    registry.write_text(json.dumps({"schema_version": 1, "common_runtime_root": str(runtime), "goals": [{
        "id": "goal-a", "status": "active", "repo": str(project),
        "state_file": ".codex/goals/goal-a/ACTIVE_GOAL_STATE.md",
        "coordination": {"registered_agents": ["agent-a", "agent-b"]},
    }]}), encoding="utf-8")
    if promoted:
        todos = list_goal_todos(registry_path=registry, goal_id="goal-a")["todos"]
        projection = build_todo_runtime_shadow_projection(goal_id="goal-a", todos=todos, handoff_mode="soft_claim")
        initialize_canonical_authority(runtime, "goal-a", projection, state_path=state)
        state.unlink()  # The update must neither require nor import a Markdown authority source.
    return registry, state


def update(registry: Path, *args: str, ok: bool = True) -> dict:
    process = subprocess.run([
        sys.executable, "-m", "loopx.cli", "--format", "json", "--registry", str(registry),
        "todo", "update", "--goal-id", "goal-a", "--todo-id", "todo_target", "--agent-id", "agent-a", *args,
    ], capture_output=True, text=True, timeout=45)
    result = json.loads(process.stdout)
    assert (process.returncode == 0) is ok, (result, process.stderr)
    return result


def records(registry: Path) -> dict[str, dict]:
    return {item["todo_id"]: item for item in list_goal_todos(registry_path=registry, goal_id="goal-a")["todos"]}


@pytest.mark.parametrize("promoted", [False, True])
def test_work_requirements_update_preserves_authority_and_supports_explicit_empty(tmp_path: Path, promoted: bool) -> None:
    registry, _state = fixture(tmp_path, promoted)
    before = records(registry)
    result = update_goal_todo(
        registry_path=registry, goal_id="goal-a", todo_id="todo_target", agent_id="agent-a",
        action_kind="IMPLEMENT", task_domain="Code.Review",
        task_repository="git@github.com:example/project.git",
        required_capabilities=["Code-Review", "code_review"],
        target_capabilities=["Delivery"], required_write_scopes=["src/**", "tests/**"],
        explore_result_node_refs=["Node:alpha"],
    )
    assert result["ok"] is True
    todo = records(registry)["todo_target"]
    assert todo["action_kind"] == "implement"
    assert todo["task_domain"] == "code.review"
    assert todo["task_repository"] == "git:github.com/example/project"
    assert todo["required_capabilities"] == ["code_review"]
    assert todo["target_capabilities"] == ["delivery"]
    assert todo["required_write_scopes"] == ["src/**", "tests/**"]
    assert todo["explore_result_node_refs"] == ["Node:alpha"]
    assert todo["claimed_by"] == "agent-a"
    assert records(registry)["todo_other"] == before["todo_other"]
    update_goal_todo(registry_path=registry, goal_id="goal-a", todo_id="todo_target",
                     agent_id="agent-a", required_capabilities=[], required_write_scopes=[],
                     target_capabilities=[], explore_result_node_refs=[])
    cleared = records(registry)["todo_target"]
    for field in ("required_capabilities", "target_capabilities", "required_write_scopes", "explore_result_node_refs"):
        assert not cleared.get(field)
    assert cleared["task_repository"] == todo["task_repository"]


@pytest.mark.parametrize("promoted", [False, True])
@pytest.mark.parametrize("intent", [
    {"required_capabilities": ["code_review", "bad/token"]},
    {"required_write_scopes": ["src/**", "../escape"]},
    {"task_repository": "https://user:password@example.com/project"},
    {"task_repository": "user:password@example.com:project"},
    {"explore_result_node_refs": ["Node:alpha", "bad/ref"]},
])
def test_invalid_work_requirement_is_not_silently_dropped(tmp_path: Path, promoted: bool, intent: dict) -> None:
    registry, state = fixture(tmp_path, promoted)
    before = records(registry)
    with pytest.raises((ValueError, RuntimeError)):
        update_goal_todo(registry_path=registry, goal_id="goal-a", todo_id="todo_target",
                         agent_id="agent-a", text="Must not partially commit", **intent)
    assert records(registry) == before
    if promoted:
        assert not state.exists()


@pytest.mark.parametrize("promoted", [False, True])
def test_cli_routes_work_requirements_without_display_dependency(tmp_path: Path, promoted: bool) -> None:
    registry, state = fixture(tmp_path, promoted)
    args = ["--action-kind", "IMPLEMENT", "--task-domain", "code",
            "--task-repository", "https://github.com/example/project",
            "--required-capability", "Code-Review", "--target-capability", "Delivery",
            "--required-write-scope", "src/**", "--explore-result-node-ref", "Node:alpha"]
    if promoted:
        args += ["--update-operation-id", "requirements-cli"]
    update(registry, *args, "--dry-run")
    if promoted:
        assert not state.exists()
    update(registry, *args)
    assert records(registry)["todo_target"]["required_capabilities"] == ["code_review"]
    if promoted:
        assert update(registry, *args)["status"] == "replayed"
    update(registry, "--clear-explore-result-node-refs")
    assert not records(registry)["todo_target"].get("explore_result_node_refs")
    before = records(registry)
    update(registry, "--required-capability", "valid", "--required-capability", "bad/token", ok=False)
    assert records(registry) == before


@pytest.mark.parametrize("promoted", [False, True])
@pytest.mark.parametrize("surface", ["cli", "python_api"])
@pytest.mark.parametrize(("label", "note", "expected_note"), [
    ("omitted", None, "Preserved note"),
    ("empty", "", "Preserved note"),
    ("unicode_whitespace", " \t\u2003\n", "Preserved note"),
    ("nonempty", "  Updated\u2003note  ", "Updated note"),
])
def test_note_input_semantics_match_before_and_after_promotion(
    tmp_path: Path, promoted: bool, surface: str, label: str,
    note: str | None, expected_note: str,
) -> None:
    registry, _state = fixture(tmp_path, promoted)
    operation_id = f"note-{surface}-{label}" if promoted else None
    if surface == "cli":
        args = ["--text", "Corrected task"]
        if note is not None:
            args += ["--note", note]
        if operation_id is not None:
            args += ["--update-operation-id", operation_id]
        update(registry, *args)
    else:
        result = update_goal_todo(
            registry_path=registry, goal_id="goal-a", todo_id="todo_target",
            role="agent", agent_id="agent-a", text="Corrected task", note=note,
            update_operation_id=operation_id,
        )
        assert result["ok"] is True
    persisted = records(registry)["todo_target"]
    assert persisted["text"] == "Corrected task"
    assert persisted["note"] == expected_note


def test_promoted_v0_replay_uses_normalized_empty_note_identity(tmp_path: Path) -> None:
    registry, _state = fixture(tmp_path, True)
    base = ["--text", "Corrected task", "--update-operation-id", "note-v0-replay"]
    assert update(registry, *base)["status"] == "applied"
    assert update(registry, *base, "--note", "")["status"] == "replayed"
    assert update(registry, *base, "--note", " \t\u2003\n")["status"] == "replayed"
    update(registry, *base, "--note", "Different note", ok=False)
    assert records(registry)["todo_target"]["note"] == "Preserved note"


@pytest.mark.parametrize("promoted", [False, True])
def test_public_cli_nonterminal_wait_update_and_clear(tmp_path: Path, promoted: bool) -> None:
    registry, state = fixture(tmp_path, promoted)
    before = records(registry)
    args = ["--status", "deferred", "--resume-when", "pr_merged:#123", "--reason", "Await upstream",
            "--evidence", "Synthetic evidence", "--text", "  Corrected\u2003task  "]
    if promoted:
        args += ["--update-operation-id", "planning-attempt"]
    update(registry, *args, "--dry-run")
    assert records(registry) == before
    if promoted:
        assert not state.exists()
    update(registry, *args)
    waiting = records(registry)
    todo = waiting["todo_target"]
    assert todo["status"] == "deferred" and todo["done"] is True
    assert todo["resume_when"] == "pr_merged:#123"
    assert todo["reason"] == "Await upstream"
    assert todo["text"] == "Corrected task"
    assert todo["note"] == "Preserved note"
    assert todo["claimed_by"] == "agent-a"
    assert waiting["todo_other"] == before["todo_other"]
    if promoted:
        assert update(registry, *args)["status"] == "replayed"
        update(registry, *args, "--note", "Changed retry", ok=False)
        assert records(registry) == waiting
        assert state.exists(), "accepted commit should drain its independent display projection"
    update(registry, "--status", "open", "--clear-resume-when")
    resumed = records(registry)["todo_target"]
    assert resumed["status"] == "open" and resumed["done"] is False
    assert not resumed.get("resume_when")
    assert not resumed.get("resume_monitor_generation")


@pytest.mark.parametrize("args", [
    ["--status", "done"], ["--status", "deferred"], ["--claimed-by", "agent-b"],
    ["--task-class", "continuous_monitor"], ["--status", "blocked", "--agent-id", "agent-b"],
])
def test_promoted_unsupported_or_unauthorized_update_never_falls_back(tmp_path: Path, args: list[str]) -> None:
    registry, state = fixture(tmp_path, True)
    before = records(registry)
    update(registry, *args, ok=False)
    assert records(registry) == before
    assert not state.exists()


@pytest.mark.parametrize("todo_id,role,reason", [
    ("todo_missing", "agent", "Todo is missing from canonical authority"),
    ("todo_target", "user", "Todo does not have the requested role"),
])
def test_native_target_lookup_keeps_public_value_error(tmp_path: Path, todo_id: str, role: str, reason: str) -> None:
    registry, state = fixture(tmp_path, True)
    before = records(registry)
    with pytest.raises(ValueError, match=reason):
        update_goal_todo(registry_path=registry, goal_id="goal-a", todo_id=todo_id,
                         role=role, agent_id="agent-a", text="Correction")
    assert records(registry) == before
    assert not state.exists()
