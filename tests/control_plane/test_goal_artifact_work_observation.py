"""Lifecycle work precedence through the persisted session-runtime status path."""

from __future__ import annotations

import copy
import json

import pytest

from loopx.session_runtime import build_session_runtime_readonly_projection
from loopx.status import collect_status


@pytest.mark.parametrize("display_limit", [0, 5])
def test_persisted_session_work_prevents_closeout_after_display_trimming(tmp_path, display_limit):
    from loopx.presentation.renderers.status_markdown import render_status_markdown

    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    project.mkdir()
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\nstatus: active\n---\n\n# Goal\n\n## Agent Todo\n\n"
        "- [x] Implement the change\n"
        "  <!-- loopx:todo todo_id=todo_implemented status=done "
        "task_class=advancement_task claimed_by=agent-a -->\n\n## User Todo\n"
    )
    registry = project / "registry.json"
    registry.write_text(json.dumps({
        "schema_version": 1, "common_runtime_root": str(runtime),
        "goals": [{
            "id": "demo", "status": "active", "domain": "software", "repo": str(project),
            "state_file": state.name,
            "adapter": {"kind": "session_runtime", "status": "connected-read-only"},
        }],
    }))
    projection = build_session_runtime_readonly_projection(
        goal_id="demo",
        decision_results=[{"recommended_action": "Verify the remaining evidence"}],
    )
    runs = runtime / "goals" / "demo" / "runs"
    runs.mkdir(parents=True)
    run_path, markdown_path = runs / "run.json", runs / "run.md"
    record = {
        "goal_id": "demo", "generated_at": "2026-09-01T00:00:00+00:00",
        "classification": "session_runtime_projection_recorded",
        "delivery_outcome": "outcome_progress",
        "session_runtime_readonly_projection": projection,
        "json_path": str(run_path), "markdown_path": str(markdown_path),
    }
    run_path.write_text(json.dumps(record))
    markdown_path.write_text("# Compact session-runtime observation\n")
    (runs / "index.jsonl").write_text(json.dumps(record) + "\n")
    before = {path: path.read_bytes() for path in (state, registry, run_path, markdown_path, runs / "index.jsonl")}
    result = collect_status(
        registry_path=registry, runtime_root_override=str(runtime),
        scan_roots=[], limit=display_limit, include_public_boundary_scan=False,
    )
    assert result["ok"] is True
    goal = result["run_history"]["goals"][0]
    item = next(item for item in result["attention_queue"]["items"] if item["goal_id"] == "demo")
    assert item["agent_todos"]["open_count"] == 0
    assert "work_lane_contract" not in item
    assert item["session_runtime_projection"]["work_lane_contract"]["must_attempt_work"] is True
    if display_limit == 0:
        assert goal["latest_runs"] == []
    lifecycle = goal["artifact_lifecycle"]
    assert lifecycle["guards"] == []
    assert all(marker["reached"] for marker in lifecycle["milestones"])
    assert lifecycle["lifecycle_phase"] == "qualifying"
    assert lifecycle["next_transitions"] == [{
        "target_phase": "qualifying", "precondition": "Verify the remaining evidence",
        "reason_codes": ["work_lane_selected"],
    }]
    assert "Verify the remaining evidence" in render_status_markdown(result)
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("field,value", [
    ("goal_id", "other-goal"), ("goal_id", None), ("schema_version", "unknown_v0"),
])
def test_work_observation_rejects_foreign_or_untyped_projection(field, value):
    from loopx.control_plane.runtime.session_runtime import session_runtime_work_observation

    projection = build_session_runtime_readonly_projection(
        goal_id="demo", decision_results=[{"recommended_action": "Continue verification"}],
    )
    projection[field] = value
    before = copy.deepcopy(projection)
    assert session_runtime_work_observation(projection, goal_id="demo") is None
    assert projection == before


@pytest.mark.parametrize("required", [False, True, "false"])
def test_lane_owner_exposes_facts_without_creating_a_work_requirement(required):
    from loopx.control_plane.work_items.work_lane import observe_work_lane

    contract = {"lane": "continuous_monitor", "must_attempt_work": required,
                "obligation": "Inspect the current monitor receipt"}
    before = copy.deepcopy(contract)
    observation = observe_work_lane(contract, next_action="Fallback description")
    assert observation.lane == "continuous_monitor"
    assert observation.must_attempt is (required is True)
    assert observation.next_action == "Inspect the current monitor receipt"
    assert contract == before


def test_lifecycle_validates_work_observation_text_before_rendering():
    from loopx.control_plane.goals.artifact_lifecycle import build_goal_artifact_lifecycle_projection
    from loopx.control_plane.runtime.public_safety import validate_public_safe_value
    from loopx.control_plane.work_items.work_lane import WorkLaneObservation

    projection = build_goal_artifact_lifecycle_projection(
        goal_id="demo", goal={"status": "active"},
        work_observation=WorkLaneObservation(
            lane="advancement_task", must_attempt=True,
            next_action="x" * 500 + " token=" + "synthetic" * 4,
        ),
    )
    assert projection["lifecycle_phase"] == "qualifying"
    assert projection["next_transitions"][0]["precondition"] == "advance the selected lane"
    validate_public_safe_value(projection)
