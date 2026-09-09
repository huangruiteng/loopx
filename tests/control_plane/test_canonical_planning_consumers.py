"""Planning consumers must use provider state, not its stale display copy."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from canonical_authority_fixture import initialize_canonical_authority

from loopx.control_plane.coordination.local_authority import (
    LocalCoordinationAuthorityUnavailable,
    canonical_todo_summary_fields,
    read_canonical_todos_if_promoted,
)
from loopx.control_plane.coordination.runtime_shadow import (
    build_todo_runtime_shadow_projection,
)
from loopx.control_plane.goals.start_goal_todo_delta import (
    existing_runnable_agent_frontier,
)
from loopx.control_plane.todos.active_state_todo_parser import parse_active_state_todos
from loopx.control_plane.todos.completion_validation_accountability import (
    require_accountable_completion_validation,
)
from loopx.control_plane.work_items.refresh_recommendation import (
    resolve_refresh_recommendation,
)
from loopx.control_plane.work_items.semantic_replan_writeback import (
    qualify_replan_writeback,
)
from loopx.state_refresh import refresh_state_run


def _refresh(registry: Path, **overrides: object) -> dict:
    return refresh_state_run(
        **{
            "registry_path": registry,
            "runtime_root_override": str(registry.parent / "runtime"),
            "goal_id": "goal-a",
            "project": registry.parent,
            "state_file": None,
            "classification": "state_refreshed",
            "recommended_action": None,
            "delivery_batch_scale": "single_surface",
            "delivery_outcome": "surface_only",
            "agent_id": "agent-a",
            "dry_run": True,
            "sync_global": False,
            **overrides,
        }
    )


def _state(*, done: bool = False, text: str = "Canonical work") -> str:
    return (
        "# Goal\n\n## Agent Todo\n\n"
        f"- [{'x' if done else ' '}] {text}\n"
        "  <!-- loopx:todo todo_id=todo_selected task_class=advancement_task "
        f"status={'done' if done else 'open'} claimed_by=agent-a -->\n"
    )


def _fixture(root: Path, *, state: str | None = None) -> tuple[Path, Path, dict]:
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "ACTIVE_GOAL_STATE.md"
    state_path.write_text(state if state is not None else _state(), encoding="utf-8")
    goal = {
        "id": "goal-a",
        "repo": str(root),
        "state_file": str(state_path),
        "coordination": {"registered_agents": ["agent-a", "agent-b"]},
    }
    runtime = root / "runtime"
    registry = root / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [goal],
            }
        ),
        encoding="utf-8",
    )
    return registry, state_path, goal


def _promote(registry: Path, path: Path, goal: dict) -> dict:
    fields = parse_active_state_todos(path.read_text(), goal=goal, item_limit=None)
    todos = [
        item
        for key in ("user_todos", "agent_todos")
        for item in fields.get(key, {}).get("items", [])
    ]
    runtime = registry.parent / "runtime"
    initialize_canonical_authority(
        runtime,
        "goal-a",
        build_todo_runtime_shadow_projection(
            goal_id="goal-a",
            todos=todos,
            handoff_mode="soft_claim",
        ),
        state_path=path,
    )
    loaded = read_canonical_todos_if_promoted(runtime_root=runtime, goal_id="goal-a")
    assert loaded is not None
    return canonical_todo_summary_fields(loaded["todos"])


@pytest.mark.parametrize("display", ["stale", "missing", "empty"])
def test_start_frontier_uses_real_provider_and_never_repairs_display(
    tmp_path: Path, display: str
) -> None:
    registry, path, goal = _fixture(tmp_path)
    _promote(registry, path, goal)
    if display == "missing":
        path.unlink()
    else:
        path.write_text(_state(done=True, text="Stale display") if display == "stale" else "")
    before = path.read_bytes() if path.exists() else None
    frontier = existing_runnable_agent_frontier(
        {
            "connection_state": "connected",
            "registry": str(registry),
            "project": str(tmp_path),
        },
        resolved_goal_id="goal-a",
        effective_agent_id="agent-a",
    )
    assert frontier is not None
    assert [(item["todo_id"], item["text"]) for item in frontier] == [
        ("todo_selected", "Canonical work")
    ]
    assert (path.read_bytes() if path.exists() else None) == before


def test_empty_canonical_frontier_does_not_resurrect_markdown(tmp_path: Path) -> None:
    registry, path, goal = _fixture(tmp_path, state="# Goal\n")
    _promote(registry, path, goal)
    path.write_text(_state())
    assert (
        existing_runnable_agent_frontier(
            {
                "connection_state": "connected",
                "registry": str(registry),
                "project": str(tmp_path),
            },
            resolved_goal_id="goal-a",
            effective_agent_id="agent-a",
        )
        is None
    )


def test_provider_failure_is_not_permission_to_plan_again(tmp_path: Path) -> None:
    registry, path, goal = _fixture(tmp_path)
    _promote(registry, path, goal)
    # Preserve the cutover fence but remove only this disposable provider head.
    head = next((tmp_path / "runtime/authority/file-v0").glob("authority-store-*.json"), None)
    assert head is not None
    head.rename(head.with_suffix(".unavailable"))
    with pytest.raises(LocalCoordinationAuthorityUnavailable):
        existing_runnable_agent_frontier(
            {
                "connection_state": "connected",
                "registry": str(registry),
                "project": str(tmp_path),
            },
            resolved_goal_id="goal-a",
            effective_agent_id="agent-a",
        )
    with pytest.raises(LocalCoordinationAuthorityUnavailable):
        _refresh(registry, recommended_action="An explicit action is not a provider fallback")


def test_recommendation_uses_canonical_claim_and_receipt_binding(
    tmp_path: Path,
) -> None:
    registry, path, goal = _fixture(tmp_path)
    fields = _promote(registry, path, goal)
    identity = {
        "goal_id": "goal-a",
        "agent_id": "agent-a",
        "todo_id": "todo_selected",
        "turn_instance_id": "turn-a",
        "effect_id": "goal-a:agent-a:todo_selected:turn-a",
    }
    result = resolve_refresh_recommendation(
        _state(done=True, text="Stale copy"),
        agent_id="agent-a",
        registry_goal=goal,
        settlement_identity=identity,
        todo_fields=fields,
    )
    assert result["recommended_action"] == "Canonical work"
    assert result["recommended_action_source"] == "settlement_bound_todo"
    assert result["settlement_alignment"] == "exact"
    empty = resolve_refresh_recommendation(_state(), agent_id="agent-a", todo_fields={})
    assert empty["recommended_action_source"] == "default_refresh_action"


def test_completion_fence_uses_canonical_validation_not_display(tmp_path: Path) -> None:
    state = _state().replace("status=open", "status=open validation_command=pytest")
    registry, path, goal = _fixture(tmp_path, state=state)
    fields = _promote(registry, path, goal)
    with pytest.raises(ValueError, match="completion validation"):
        require_accountable_completion_validation(
            "",
            todo_id="todo_selected",
            agent_id="agent-a",
            todo_fields=fields,
        )
    require_accountable_completion_validation(
        state,
        todo_id="todo_selected",
        agent_id="agent-a",
        todo_fields={},
    )


def _completed_chain() -> str:
    state = "## Agent Todo\n"
    for index in range(3):
        state += (
            f"- [x] [P1] Completed slice {index}\n"
            f"  <!-- loopx:todo todo_id=todo_slice_{index} status=done task_class=advancement_task "
            f"claimed_by=agent-a successor_todo_ids=todo_slice_{index + 1} "
            f"completed_at=2026-08-13T11%3A{30 + index}%3A00%2B08%3A00 -->\n"
        )
    state += "- [x] [P1] Lineage anchor\n  <!-- loopx:todo todo_id=todo_slice_3 status=done claimed_by=agent-a task_class=continuous_monitor -->\n"
    return state


def test_replan_completion_cadence_cannot_be_hidden_by_stale_display(
    tmp_path: Path,
) -> None:
    state = _completed_chain()
    registry, path, goal = _fixture(tmp_path, state=state)
    goal["execution_profile"] = {"replan_after_completed_todos": 3}
    fields = _promote(registry, path, goal)
    arguments = {
        "newest_first_runs": [],
        "agent_id": "agent-a",
        "goal_id": "goal-a",
        "registry_goal": goal,
    }
    obligation, _ = qualify_replan_writeback(state_text="", todo_fields=fields, **arguments)
    assert obligation is not None
    assert any(
        trigger["kind"] == "vision_outcome_checkpoint_required"
        for trigger in obligation["triggers"]
    )
    empty, _ = qualify_replan_writeback(state_text=state, todo_fields={}, **arguments)
    assert empty is None


def test_todo_add_replan_guard_binds_canonical_obligation_without_display(
    tmp_path: Path,
) -> None:
    from argparse import Namespace
    from loopx.cli_commands.todo import _validated_replan_successor_obligation

    registry, path, goal = _fixture(tmp_path, state=_completed_chain())
    goal["execution_profile"] = {"replan_after_completed_todos": 3}
    payload = json.loads(registry.read_text())
    payload["goals"] = [goal]
    registry.write_text(json.dumps(payload))
    fields = _promote(registry, path, goal)
    obligation, _ = qualify_replan_writeback(
        state_text="",
        newest_first_runs=[],
        agent_id="agent-a",
        goal_id="goal-a",
        registry_goal=goal,
        todo_fields=fields,
    )
    assert obligation is not None
    args = Namespace(
        replan_obligation_id=obligation["obligation_id"],
        role="agent",
        task_class="advancement_task",
        claimed_by="agent-a",
        action_kind="implementation",
        monitor_target_key="feature-a",
        explore_result_node_refs=[],
        goal_id="goal-a",
    )
    path.unlink()
    assert (
        _validated_replan_successor_obligation(args, registry_path=registry, runtime_root_arg=None)
        == obligation["obligation_id"]
    )
    args.replan_obligation_id = "obsolete-obligation"
    with pytest.raises(ValueError, match="does not match"):
        _validated_replan_successor_obligation(args, registry_path=registry, runtime_root_arg=None)
    assert not path.exists()


@pytest.mark.parametrize("promoted", [False, True])
def test_public_refresh_retains_legacy_parity_and_uses_one_provider_read(
    tmp_path: Path, monkeypatch, promoted: bool
) -> None:
    from loopx.control_plane.coordination import local_authority

    registry, path, goal = _fixture(tmp_path)
    if promoted:
        _promote(registry, path, goal)
        path.write_text(_state(done=True, text="Stale work"))
    original = local_authority.read_canonical_todos_if_promoted
    reads = []

    def read(**kwargs):
        result = original(**kwargs)
        reads.append(result)
        return result

    monkeypatch.setattr(local_authority, "read_canonical_todos_if_promoted", read)
    result = _refresh(registry)
    assert "Canonical work" in json.dumps(result)
    assert len(reads) == 1
    assert (reads[0] is not None) == promoted


@pytest.mark.parametrize("promoted", [False, True])
def test_refresh_todo_text_is_record_content_not_an_artifact_path(
    tmp_path: Path, promoted: bool,
) -> None:
    text = "../../escape.json"
    registry, path, goal = _fixture(tmp_path, state=_state(text=text))
    if promoted:
        _promote(registry, path, goal)
    before = path.read_bytes()
    result = _refresh(registry, dry_run=False)
    runs = tmp_path / "runtime/goals/goal-a/runs"
    for key in ("json_path", "markdown_path", "index_path"):
        artifact = Path(result[key])
        assert artifact.parent == runs
        assert artifact.is_file()
    record = json.loads(Path(result["json_path"]).read_text())
    assert text in json.dumps(record)
    assert not list(tmp_path.rglob("escape.json"))
    assert path.read_bytes() == before


@pytest.mark.parametrize("promoted", [False, True])
def test_public_refresh_missing_projection_is_readable_not_implicitly_rebuilt(
    tmp_path: Path, promoted: bool,
) -> None:
    registry, path, goal = _fixture(tmp_path)
    if promoted:
        _promote(registry, path, goal)
    path.unlink()
    if promoted:
        result = _refresh(registry)
        assert "Canonical work" in json.dumps(result)
    else:
        with pytest.raises(FileNotFoundError):
            _refresh(registry)
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        _refresh(registry, next_action="Replace the missing narrative", progress_scope="goal")
    assert not path.exists()


def test_committed_refresh_records_canonical_recommendation_without_rewriting_display(
    tmp_path: Path,
) -> None:
    registry, path, goal = _fixture(tmp_path)
    _promote(registry, path, goal)
    path.write_text(_state(done=True, text="Stale display"))
    before = read_canonical_todos_if_promoted(runtime_root=tmp_path / "runtime", goal_id="goal-a")
    display = path.read_bytes()
    _refresh(registry, dry_run=False)
    runs = (tmp_path / "runtime/goals/goal-a/runs/index.jsonl").read_text()
    assert "Canonical work" in runs
    assert path.read_bytes() == display
    assert (
        read_canonical_todos_if_promoted(runtime_root=tmp_path / "runtime", goal_id="goal-a")
        == before
    )


def test_public_refresh_keeps_validation_gate_even_with_explicit_recommendation(
    tmp_path: Path,
) -> None:
    state = _state().replace("status=open", "status=open validation_command=pytest")
    registry, path, goal = _fixture(tmp_path, state=state)
    _promote(registry, path, goal)
    path.write_text(_state(done=True))
    with pytest.raises(ValueError, match="completion validation"):
        _refresh(
            registry,
            recommended_action="Explicit recommendation",
            delivery_outcome="outcome_progress",
        )


def test_production_scale_snapshot_reaches_all_planning_consumers(
    tmp_path: Path,
) -> None:
    generated = subprocess.run(
        [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            "import {productionScaleCoordinationFixture} from './tests/control_plane_ts/production_scale_coordination_fixture.ts';"
            "process.stdout.write(JSON.stringify(productionScaleCoordinationFixture('goal-a')));",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    fixture = json.loads(generated.stdout)
    registry, path, goal = _fixture(tmp_path)
    initialize_canonical_authority(
        tmp_path / "runtime", "goal-a", fixture["projection"], state_path=path
    )
    before = read_canonical_todos_if_promoted(runtime_root=tmp_path / "runtime", goal_id="goal-a")
    assert before is not None
    fields = canonical_todo_summary_fields(before["todos"])
    assert len(fields["agent_todos"]["items"]) == 256
    assert len(fields["user_todos"]["items"]) == 208
    path.unlink()
    for agent, selected_id in [
        ("agent-a", fixture["completion_todo_id"]),
        ("agent-b", fixture["supersede_todo_id"]),
    ]:
        identity = {
            "goal_id": "goal-a",
            "agent_id": agent,
            "todo_id": selected_id,
            "turn_instance_id": "turn-a",
            "effect_id": f"goal-a:{agent}:{selected_id}:turn-a",
        }
        result = resolve_refresh_recommendation(
            "", agent_id=agent, settlement_identity=identity, todo_fields=fields
        )
        assert result["todo_id"] == selected_id
        assert result["settlement_alignment"] == "exact"
        frontier = existing_runnable_agent_frontier(
            {
                "connection_state": "connected",
                "registry": str(registry),
                "project": str(tmp_path),
            },
            resolved_goal_id="goal-a",
            effective_agent_id=agent,
        )
        assert frontier
        assert selected_id in {item["todo_id"] for item in frontier}
        assert all(
            item.get("claimed_by") in (None, agent)
            and item["status"] == "open"
            and item["task_class"] == "advancement_task"
            for item in frontier
        )
        # Replan consumes the complete same snapshot, including terminal records
        # and standing user decisions. Arbitrary display Todo edits have no say.
        baseline = qualify_replan_writeback(
            state_text="",
            newest_first_runs=[],
            agent_id=agent,
            goal_id="goal-a",
            registry_goal=goal,
            todo_fields=fields,
        )
        assert (
            qualify_replan_writeback(
                state_text=_state(),
                newest_first_runs=[],
                agent_id=agent,
                goal_id="goal-a",
                registry_goal=goal,
                todo_fields=fields,
            )
            == baseline
        )
    with pytest.raises(ValueError, match="completion validation"):
        require_accountable_completion_validation(
            "",
            todo_id=fixture["completion_todo_id"],
            agent_id="agent-a",
            todo_fields=fields,
        )
    assert (
        read_canonical_todos_if_promoted(runtime_root=tmp_path / "runtime", goal_id="goal-a")
        == before
    )
    assert not path.exists()


def test_start_goal_packet_honors_runtime_override_and_canonical_frontier(
    tmp_path: Path,
) -> None:
    from loopx.bootstrap_command_pack import build_start_goal_guided_packet

    registry, path, goal = _fixture(tmp_path)
    _promote(registry, path, goal)
    project_registry = tmp_path / ".loopx/registry.json"
    project_registry.parent.mkdir()
    contents = json.loads(registry.read_text())
    contents["common_runtime_root"] = str(tmp_path / "unused-runtime")
    project_registry.write_text(json.dumps(contents))
    path.write_text(_state(done=True, text="Stale copy"))
    result = build_start_goal_guided_packet(
        project=tmp_path,
        goal_id="goal-a",
        agent_id="agent-a",
        cli_bin="loopx",
        host_surface="codex-app",
        goal_text="Continue bounded work",
        available_capabilities=["network"],
        runtime_root_arg=str(tmp_path / "runtime"),
    )
    steps = result["guided_transaction"]["ordered_steps"]
    delta = next(step for step in steps if step["id"] == "apply_todo_delta")
    assert "Canonical work" in json.dumps(delta)
    assert "Stale copy" not in json.dumps(delta)
