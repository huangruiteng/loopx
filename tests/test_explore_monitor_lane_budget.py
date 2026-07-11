from __future__ import annotations

from loopx.capabilities.explore.todo_branch_plan import build_explore_todo_branch_plan
from loopx.capabilities.explore.worker_branch_plan import build_explore_worker_branch_plan


ANALYSIS_ONLY = {"explore_harness": {"enabled": True}}


def _todo(
    todo_id: str,
    *,
    index: int,
    priority: str,
    task_class: str,
    capability: str,
    write_scope: str | None = None,
    shared_dependency: str | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "todo_id": todo_id,
        "index": index,
        "status": "open",
        "priority": priority,
        "text": f"[{priority}] Inspect the synthetic {capability.replace('_', ' ')}",
        "task_class": task_class,
        "required_capabilities": [capability],
    }
    if write_scope:
        item["required_write_scopes"] = [write_scope]
    if shared_dependency:
        item["required_capabilities"] = [shared_dependency, capability]
    if task_class == "continuous_monitor":
        item.update(
            {
                "monitor_cadence_seconds": 60,
                "next_due_at": "2020-01-01T00:00:00Z",
            }
        )
    return item


TODOS = [
    _todo(
        "todo_observation_monitor",
        index=1,
        priority="P0",
        task_class="continuous_monitor",
        capability="observation_lane",
    ),
    _todo(
        "todo_long_lane",
        index=2,
        priority="P4",
        task_class="advancement_task",
        capability="resource_lane:long",
        write_scope="variants/long/**",
        shared_dependency="shared_artifact:synthetic_build",
    ),
    _todo(
        "todo_short_lane",
        index=3,
        priority="P4",
        task_class="advancement_task",
        capability="resource_lane:short",
        write_scope="variants/short/**",
        shared_dependency="shared_artifact:synthetic_build",
    ),
]


def _assert_monitor_is_diagnostic_only(rejected: list[dict[str, object]]) -> None:
    monitor = next(item for item in rejected if item.get("todo_id") == "todo_observation_monitor")
    assert monitor["selection_status"] == "excluded_non_exploration_lane"
    assert monitor["exclusion_reason"] == (
        "continuous_monitor_does_not_consume_exploration_budget"
    )


def test_todo_branch_plan_does_not_spend_width_on_monitor_lane() -> None:
    plan = build_explore_todo_branch_plan(
        goal_id="synthetic-portfolio",
        todos=TODOS,
        orchestration=ANALYSIS_ONLY,
        width=2,
    )

    assert plan["orchestration_gate"]["state"] == "analysis_only"
    assert plan["verification_budget"] == 2
    assert plan["exploration_candidate_count"] == 2
    assert [item["todo_id"] for item in plan["selected_branches"]] == [
        "todo_long_lane",
        "todo_short_lane",
    ]
    assert all(
        item["shared_dependency_capabilities"] == ["shared_artifact:synthetic_build"]
        for item in plan["selected_branches"]
    )
    assert all(not item["suggested_commands"] for item in plan["selected_branches"])
    _assert_monitor_is_diagnostic_only(plan["rejected_candidates"])


def test_worker_branch_plan_keeps_monitor_out_of_worker_slots_and_bundles() -> None:
    plan = build_explore_worker_branch_plan(
        goal_id="synthetic-portfolio",
        todos=TODOS,
        orchestration=ANALYSIS_ONLY,
        worker_width=2,
        max_todos_per_branch=1,
    )

    assert plan["orchestration_gate"]["state"] == "analysis_only"
    assert plan["verification_budget"] == 2
    assert plan["excluded_monitor_todo_count"] == 1
    assert {item["affinity_key"] for item in plan["selected_worker_branches"]} == {
        "scope:variants/long",
        "scope:variants/short",
    }
    assert all(
        item["shared_dependency_capabilities"] == ["shared_artifact:synthetic_build"]
        for item in plan["selected_worker_branches"]
    )
    selected_todo_ids = {
        todo_id
        for branch in plan["selected_worker_branches"]
        for todo_id in branch["todo_ids"]
    }
    assert selected_todo_ids == {"todo_long_lane", "todo_short_lane"}
    assert all(not item["suggested_commands"] for item in plan["selected_worker_branches"])
    _assert_monitor_is_diagnostic_only(plan["rejected_worker_branches"])


def test_mutable_shared_build_scope_still_serializes_worker_lanes() -> None:
    todos = [
        _todo(
            "todo_long_build",
            index=1,
            priority="P1",
            task_class="advancement_task",
            capability="resource_lane:long",
            write_scope="artifacts/shared_build/**",
        ),
        _todo(
            "todo_short_build",
            index=2,
            priority="P1",
            task_class="advancement_task",
            capability="resource_lane:short",
            write_scope="artifacts/shared_build/**",
        ),
    ]

    plan = build_explore_worker_branch_plan(
        goal_id="synthetic-shared-build",
        todos=todos,
        orchestration=ANALYSIS_ONLY,
        worker_width=2,
        max_todos_per_branch=1,
    )

    assert plan["selected_worker_branch_count"] == 1
    conflict = next(
        item
        for item in plan["rejected_worker_branches"]
        if item.get("selection_status") == "rejected_hazard"
    )
    assert any(
        str(hazard).startswith("worker_branch_conflict:")
        for hazard in conflict["hazards"]
    )
