#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.control_plane.goals import active_state_metadata as active_state_metadata_read_model  # noqa: E402
from loopx.control_plane.goals import global_registry_health as global_registry_health_read_model  # noqa: E402
from loopx.control_plane.work_items import attention_item as attention_item_read_model  # noqa: E402
from loopx.control_plane.work_items import autonomous_candidates as autonomous_read_model  # noqa: E402
from loopx.control_plane.work_items import autonomous_replan_ack as replan_ack_read_model  # noqa: E402
from loopx.control_plane.goals import global_registry_shadow as global_registry_shadow_read_model  # noqa: E402
from loopx.control_plane.runtime import event_ledger as event_ledger_read_model  # noqa: E402
from loopx.control_plane.runtime import run_compaction as run_compaction_read_model  # noqa: E402
from loopx.control_plane.runtime import session_runtime as session_runtime_read_model  # noqa: E402
from loopx.control_plane.runtime import time as runtime_time_read_model  # noqa: E402
from loopx.control_plane.quota import usage_summary as usage_summary_read_model  # noqa: E402
from loopx.control_plane.todos import active_state_todo_parser as active_state_todo_parser_read_model  # noqa: E402
from loopx.control_plane.todos import active_state_todos as active_state_todos_read_model  # noqa: E402
from loopx.control_plane.todos import monitor_metadata as monitor_metadata_read_model  # noqa: E402
from loopx.control_plane.todos import projection as todo_projection_read_model  # noqa: E402
from loopx.control_plane.todos import todo_summary as todo_read_model  # noqa: E402


def fixture_todos() -> dict:
    return {
        "first_open_items": [
            {
                "index": 2,
                "done": False,
                "text": "[P2] Run focused canary smoke",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
            {
                "index": 1,
                "done": False,
                "text": "[P1] Monitor quiet transition",
                "task_class": "continuous_monitor",
                "target_key": "monitor-gap",
            },
        ],
        "items": [
            {
                "index": 2,
                "done": False,
                "text": "[P2] Run focused canary smoke",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
            {
                "index": 3,
                "done": True,
                "text": "[P3] Completed old slice",
            },
            {
                "index": 4,
                "done": False,
                "text": "  [P2]   Refactor todo read model   ",
                "task_class": "advancement_task",
            },
        ],
        "monitor_open_items": [
            {
                "index": 1,
                "done": False,
                "text": "[P1] Monitor quiet transition",
                "task_class": "continuous_monitor",
            }
        ],
    }


def assert_direct_status_aliases() -> None:
    assert status_module.parse_state_frontmatter is active_state_metadata_read_model.parse_state_frontmatter
    assert status_module.todo_role_for_heading is active_state_metadata_read_model.todo_role_for_heading
    assert status_module.parse_active_state_todos is active_state_todo_parser_read_model.parse_active_state_todos
    assert status_module.attach_monitor_writeback_contract is active_state_todos_read_model.attach_monitor_writeback_contract
    assert status_module.redacted_status_todo_fields is active_state_todos_read_model.redacted_status_todo_fields
    assert status_module.todo_item_is_expired_monitor is todo_projection_read_model.todo_item_is_expired_monitor
    assert status_module.open_todo_items is todo_read_model.open_todo_items
    assert status_module.todo_lane_items is todo_read_model.todo_lane_items
    assert status_module.first_open_todo_text is todo_read_model.first_open_todo_text
    assert status_module.first_open_todo_item is todo_read_model.first_open_todo_item
    assert status_module.project_asset_todo_summary is todo_read_model.project_asset_todo_summary
    assert status_module.dependency_blocker_summary is todo_read_model.dependency_blocker_summary
    assert status_module.attach_dependency_blockers is todo_read_model.attach_dependency_blockers
    assert status_module.autonomous_replan_ack_recorded is replan_ack_read_model.autonomous_replan_ack_recorded
    assert status_module.compact_autonomous_replan_ack is replan_ack_read_model.compact_autonomous_replan_ack
    assert status_module.global_registry_finding is global_registry_health_read_model.global_registry_finding
    assert status_module.attach_session_runtime_projection is session_runtime_read_model.attach_session_runtime_projection
    assert status_module.compact_human_reward is run_compaction_read_model.compact_human_reward
    assert status_module.compact_operator_gate is run_compaction_read_model.compact_operator_gate
    assert status_module.compact_operator_gate_resume_contract is run_compaction_read_model.compact_operator_gate_resume_contract
    assert status_module.compact_controller_readiness is run_compaction_read_model.compact_controller_readiness
    assert status_module.parse_timestamp is runtime_time_read_model.parse_timestamp
    assert monitor_metadata_read_model.parse_timestamp is runtime_time_read_model.parse_timestamp
    assert status_module.quota_spend_slots is usage_summary_read_model.quota_spend_slots
    assert status_module.is_automation_run is usage_summary_read_model.is_automation_run
    assert status_module.is_progress_signal_run is usage_summary_read_model.is_progress_signal_run
    assert status_module.blank_usage_goal is usage_summary_read_model.blank_usage_goal
    assert status_module.blank_event_class_counts is event_ledger_read_model.blank_event_class_counts
    assert status_module.blank_event_ledger_goal is event_ledger_read_model.blank_event_ledger_goal


def assert_wrapper_parity() -> None:
    todos = fixture_todos()

    assert status_module.open_todo_items(todos) == todo_read_model.open_todo_items(todos)
    assert status_module.todo_lane_items(todos, "monitor_open_items") == todo_read_model.todo_lane_items(
        todos,
        "monitor_open_items",
    )
    assert status_module.first_open_todo_text(todos) == todo_read_model.first_open_todo_text(todos)
    assert status_module.first_open_todo_item(todos) == todo_read_model.first_open_todo_item(todos)
    assert status_module.project_asset_todo_summary(
        todos,
        role="agent",
    ) == todo_read_model.project_asset_todo_summary(
        todos,
        role="agent",
    )
    parsed = status_module.parse_timestamp("2026-01-01T00:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert status_module.parse_timestamp("not-a-time") is None
    assert monitor_metadata_read_model.normalize_monitor_metadata(
        {"next_due_at": "2026-01-01T00:00:00Z"}
    ) == {"next_due_at": "2026-01-01T00:00:00Z"}


def assert_dependency_blocker_parity() -> None:
    items = [
        {
            "goal_id": "current",
            "status": "active",
            "waiting_on": "codex",
        },
        {
            "goal_id": "dependency",
            "status": "blocked",
            "waiting_on": "controller",
            "severity": "action",
            "user_todos": {
                "items": [
                    {
                        "index": 5,
                        "done": False,
                        "text": "Approve rollout gate",
                    },
                    {
                        "index": 6,
                        "done": True,
                        "text": "Old approval",
                    },
                ]
            },
        },
    ]
    assert status_module.dependency_blocker_summary(
        items,
        current_goal_id="current",
    ) == todo_read_model.dependency_blocker_summary(
        items,
        current_goal_id="current",
    )

    status_items = deepcopy(items)
    direct_items = deepcopy(items)
    status_module.attach_dependency_blockers(status_items)
    todo_read_model.attach_dependency_blockers(direct_items)
    assert status_items == direct_items


def assert_autonomous_candidate_parity() -> None:
    items = [
        {
            "goal_id": "goal-b",
            "status": "active",
            "waiting_on": "codex",
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
        {
            "goal_id": "goal-a",
            "status": "watching",
            "waiting_on": status_module.MONITOR_SIGNAL_WAITING_ON,
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
        {
            "goal_id": "goal-c",
            "status": "blocked",
            "waiting_on": "controller",
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
    ]
    assert status_module.autonomous_backlog_candidates(items) == autonomous_read_model.autonomous_backlog_candidates(
        items,
        open_todo_items=status_module.open_todo_items,
        todo_item_is_actionable_open=status_module.todo_item_is_actionable_open,
        normalize_todo_text=status_module.normalize_todo_text,
        advancement_task_class=status_module.TODO_TASK_CLASS_ADVANCEMENT,
    )
    assert status_module.autonomous_monitor_candidates(items) == autonomous_read_model.autonomous_monitor_candidates(
        items,
        open_todo_items=status_module.open_todo_items,
        todo_item_is_actionable_open=status_module.todo_item_is_actionable_open,
        normalize_todo_text=status_module.normalize_todo_text,
        monitor_task_class=status_module.TODO_TASK_CLASS_MONITOR,
        monitor_signal_waiting_on=status_module.MONITOR_SIGNAL_WAITING_ON,
    )


def assert_global_registry_shadow_parity() -> None:
    finding = {
        "kind": "state_shadow",
        "severity": "warning",
        "message": "registry points at stale projection",
        "recommended_action": "refresh the public-safe state projection",
    }
    assert status_module.compact_global_registry_shadow_finding(
        finding
    ) == global_registry_shadow_read_model.compact_global_registry_shadow_finding(finding)

    status_item = {"project_asset": {"goal_id": "loopx-meta"}}
    direct_item = deepcopy(status_item)
    status_module.attach_global_registry_shadow_finding(status_item, finding)
    global_registry_shadow_read_model.attach_global_registry_shadow_finding(direct_item, finding)
    assert status_item == direct_item


def assert_attention_item_parity() -> None:
    kwargs = {
        "goal_id": "loopx-meta",
        "status": "active_state_agent_todo",
        "waiting_on": "codex",
        "severity": "action",
        "recommended_action": "continue canary-gated read-model cleanup",
        "source": "active_state",
        "operator_question": "Should the controller approve the next gate?",
        "agent_command": "loopx quota should-run --goal-id loopx-meta",
        "controller_stage": "implementation",
        "missing_gates": ["controller_review"],
        "next_handoff_condition": "stop if validation fails",
        "lifecycle_phase": "active",
        "lifecycle_flags": ["connected", "active_state"],
        "user_todos": {"open_count": 0, "items": []},
        "agent_todos": fixture_todos(),
        "todo_state_file": ".codex/goals/loopx-meta/ACTIVE_GOAL_STATE.md",
        "dreaming_proposal": {
            "kind": "dreaming_refactor_warning",
            "recommended_action": "split the projection builder",
        },
    }

    assert status_module.attention_item(**kwargs) == attention_item_read_model.attention_item(
        **kwargs,
        build_project_asset=status_module.build_project_asset,
        compact_dreaming_lane_badge=status_module.compact_dreaming_lane_badge,
    )


def assert_active_state_todo_fields_redacts_review_material_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-redaction-") as tmp:
        project = Path(tmp)
        material = project / "docs" / "notes.md"
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_text("# Notes\n", encoding="utf-8")
        state_path = project / ".codex" / "goals" / "loopx-meta" / "ACTIVE_GOAL_STATE.md"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_text = "\n".join(
            [
                "# Active State",
                "## Agent Todos",
                "- [ ] [P1] Review [notes](docs/notes.md)",
                "",
            ]
        )
        state_path.write_text(state_text, encoding="utf-8")
        goal = {
            "id": "loopx-meta",
            "repo": str(project),
            "state_file": ".codex/goals/loopx-meta/ACTIVE_GOAL_STATE.md",
        }

        raw_fields = status_module.parse_active_state_todos(
            state_text,
            goal=goal,
            state_path=state_path,
        )
        raw_material = raw_fields["agent_todos"]["items"][0]["review_materials"][0]
        assert raw_material["resolved_path"] == str(material.resolve()), raw_material

        fields = status_module.active_state_todo_fields(goal)
        material_projection = fields["agent_todos"]["items"][0]["review_materials"][0]
        assert material_projection["path"] == "docs/notes.md", material_projection
        assert material_projection["exists"] is True, material_projection
        assert "resolved_path" not in material_projection, material_projection


def main() -> None:
    assert_direct_status_aliases()
    assert_wrapper_parity()
    assert_dependency_blocker_parity()
    assert_autonomous_candidate_parity()
    assert_global_registry_shadow_parity()
    assert_attention_item_parity()
    assert_active_state_todo_fields_redacts_review_material_paths()


if __name__ == "__main__":
    main()
