from __future__ import annotations

import copy
import json
from pathlib import Path

from loopx.control_plane.goals.artifact_lifecycle import build_goal_artifact_lifecycle
from loopx.control_plane.runtime.public_safety import validate_public_safe_value
from loopx.status import collect_status


def vision_run(
    agent: str = "agent-a",
    *,
    state: str = "active",
    acceptance: str = "Independent verification report",
) -> dict:
    return {
        "run_id": "run-evidence-1",
        "goal_id": "acceptance-demo",
        "generated_at": "2026-09-01T00:00:00+00:00",
        "classification": "state_refreshed",
        "lifecycle_flags": ["refreshed", "operator_approved"],
        "agent_id": agent,
        "agent_vision": {
            "schema_version": "agent_vision_v0",
            "agent_id": agent,
            "state": state,
            "vision_patch": {
                "acceptance_summary": acceptance,
                "replan_trigger_summary": "Verification evidence is still missing",
            },
        },
    }


def test_completed_tasks_and_historical_approval_do_not_certify_acceptance():
    goal = {"id": "acceptance-demo", "latest_runs": [vision_run()]}
    item = {
        "goal_id": goal["id"],
        "agent_todos": {"done_count": 10, "open_count": 0},
        "user_todos": {
            "items": [
                {
                    "todo_id": "todo_approval",
                    "task_class": "user_gate",
                    "done": False,
                    "status": "open",
                    "text": "Review the verification report",
                    "blocks_agent": "agent-a",
                    "claimed_by": "agent-a",
                    "decision_scope": {
                        "kind": "public_claim",
                        "granularity": "goal",
                        "scope_key": "acceptance-demo",
                    },
                }
            ]
        },
    }
    before = copy.deepcopy((goal, item))
    result = build_goal_artifact_lifecycle(goal, item)
    assert result["acceptance_assessed"] is False
    assert (
        result["acceptance_gaps"][0]["evidence_required"]
        == "Independent verification report"
    )
    assert result["guards"][0]["blocks_agent"] == "agent-a"
    assert result["guards"][0]["decision_scope"] == "public_claim:goal:acceptance-demo"
    assert result["guards"][0]["owner"] is None  # routing is not human authority
    assert result["milestones"][0]["evidence_refs"] == ["run-evidence-1"]
    assert (goal, item) == before


def test_latest_vision_is_per_agent_and_closed_lane_does_not_hide_other_lane():
    goal = {
        "id": "acceptance-demo",
        "latest_runs": [
            vision_run("agent-a", state="closed"),
            vision_run("agent-b"),
            vision_run("agent-a"),
        ],
    }
    result = build_goal_artifact_lifecycle(goal, {})
    assert [gap["owner"] for gap in result["acceptance_gaps"]] == ["agent-b"]


def test_missing_and_compacted_sources_are_never_complete():
    result = build_goal_artifact_lifecycle(
        {"id": "acceptance-demo", "lifecycle_flags": [{}, "connected"]}, None
    )
    assert result["coverage"] == "unavailable"
    assert result["acceptance_assessed"] is False
    compact = build_goal_artifact_lifecycle(
        {"id": "acceptance-demo"},
        {
            "goal_frontier_projection": {
                "agent_id": "agent-a",
                "acceptance_gaps": [],
                "acceptance_gap_count": 5,
                "payload_compaction": {},
            }
        },
    )
    assert compact["coverage"] == "partial"
    assert compact["acceptance_assessed"] is False


def test_deferred_and_completed_gates_are_not_current_pending_gates():
    gates = [
        {
            "task_class": "user_gate",
            "todo_id": f"todo_{state}",
            "status": state,
            "done": state == "done",
            "blocks_agent": "agent-a",
        }
        for state in ["open", "blocked", "deferred", "done", "superseded"]
    ]
    result = build_goal_artifact_lifecycle(
        {"id": "acceptance-demo"}, {"user_todos": {"items": gates}}
    )
    assert [gate["todo_id"] for gate in result["guards"]] == [
        "todo_open",
        "todo_blocked",
    ]


def test_redaction_precedes_truncation_and_bounded_output():
    run = vision_run(acceptance="x" * 500 + " /Users/private/evidence.json")
    run["raw_log"] = "private payload"
    run["agent_vision"]["vision_patch"].pop("replan_trigger_summary")
    result = build_goal_artifact_lifecycle(
        {"id": "acceptance-demo", "latest_runs": [run]},
        {"recommended_action": "=".join(("token", "synthetic" * 4))},
    )
    assert result["acceptance_gaps"][0]["evidence_required"] is None
    assert result["next_action"] is None
    assert "raw_log" not in json.dumps(result)
    validate_public_safe_value(result)
    many = build_goal_artifact_lifecycle(
        {
            "id": "acceptance-demo",
            "latest_runs": [vision_run(f"agent-{n}") for n in range(15)],
        },
        {},
    )
    assert many["truncated"] and len(many["acceptance_gaps"]) == 12


def collect_fixture(root: Path) -> dict:
    project, runtime = root / "project", root / "runtime"
    project.mkdir(parents=True)
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\nstatus: active\n---\n\n# Acceptance\n\n## Agent Todo\n\n- [x] Implement the change\n  <!-- loopx:todo todo_id=todo_implemented status=done task_class=advancement_task claimed_by=agent-a -->\n\n## User Todo\n\n- [ ] Review verification\n  <!-- loopx:todo todo_id=todo_review status=open task_class=user_gate blocks_agent=agent-a -->\n"
    )
    registry = project / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": "acceptance-demo",
                        "status": "active",
                        "domain": "software",
                        "repo": str(project),
                        "state_file": state.name,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                    }
                ],
            }
        )
    )
    runs = runtime / "goals" / "acceptance-demo" / "runs"
    runs.mkdir(parents=True)
    (runs / "index.jsonl").write_text(json.dumps(vision_run()) + "\n")
    return collect_status(
        registry_path=registry,
        runtime_root_override=str(runtime),
        scan_roots=[],
        limit=0,
        include_public_boundary_scan=False,
    )


def test_real_collection_preserves_acceptance_before_display_run_trimming(tmp_path):
    result = collect_fixture(tmp_path)
    goal = result["run_history"]["goals"][0]
    assert goal["latest_runs"] == []
    projection = goal["artifact_lifecycle"]
    assert (
        projection["acceptance_gaps"][0]["evidence_required"]
        == "Independent verification report"
    )
    assert projection["acceptance_gaps"][0]["owner"] == "agent-a"
    assert projection["guards"][0]["blocks_agent"] == "agent-a"
    validate_public_safe_value(projection)


def test_closed_stage_retains_canonical_successor_requirement():
    result = build_goal_artifact_lifecycle(
        {
            "id": "acceptance-demo",
            "status": "active",
            "latest_runs": [vision_run(state="vision_closed")],
        },
        {},
    )
    gap = result["acceptance_gaps"][0]
    assert gap["kind"] == "vision_successor_required"
    assert "establish a successor vision" in gap["reason"]
    assert gap["reason"] != "Verification evidence is still missing"
    assert "next bounded agent vision" in gap["evidence_required"]


def test_other_goal_run_cannot_supply_acceptance_or_milestones():
    result = build_goal_artifact_lifecycle(
        {"id": "other-goal", "latest_runs": [vision_run()]}, {}
    )
    assert result["acceptance_gaps"] == []
    assert result["milestones"] == []


def test_status_markdown_surfaces_gap_and_unknown_owner_without_completion_claim():
    from loopx.presentation.renderers.status_markdown import append_run_history_markdown

    goal = {"id": "acceptance-demo", "latest_runs": [vision_run("")]}
    goal["artifact_lifecycle"] = build_goal_artifact_lifecycle(goal, {})
    lines = []
    append_run_history_markdown(lines, {"goals": [goal]})
    rendered = "\n".join(lines)
    assert "acceptance observations (partial; not completion proof)" in rendered
    assert "owner=unknown: Independent verification report" in rendered
    assert "gaps=1" in rendered
