#!/usr/bin/env python3
"""Smoke-test `loopx todo list` event projection with Markdown late-todo overlay."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    run_json_cli,
    write_fixture_registry,
)
from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    TODO_ADDED,
    TODO_COMPLETED,
    make_state_event,
)


GOAL_ID = "todo-list-event-projection-fixture"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-side-bypass"
GATE_TODO_ID = "todo_markdown_gate_done"
DEPENDENT_TODO_ID = "todo_event_dependent"
EVENT_GATE_TODO_ID = "todo_event_non_delivery_gate"
EVENT_SUCCESSOR_TODO_ID = "todo_event_same_agent_successor"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    event_log = state_file.with_name("events.jsonl")
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## User Todo\n\n"
        "- [x] [P0] Completed Markdown gate\n"
        f"  <!-- loopx:todo todo_id={GATE_TODO_ID} status=done task_class=user_gate -->\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Markdown fallback todo\n"
        "  <!-- loopx:todo todo_id=todo_markdown status=open task_class=advancement_task -->\n"
        "- [-] [P1] Continue after the Markdown gate\n"
        f"  <!-- loopx:todo todo_id={DEPENDENT_TODO_ID} status=deferred "
        f"task_class=advancement_task resume_when=todo_done:{GATE_TODO_ID} -->\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="todo-list-fixture",
        adapter_kind="generic_project_goal_v0",
        state_event_log=f".codex/goals/{GOAL_ID}/events.jsonl",
        registered_agents=(PRIMARY_AGENT, SIDE_AGENT),
        quota_allowed_slots=None,
        extra_goal_fields={
            "coordination": {
                "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                "agent_model": "peer_v1",
                "side_agent_handoff_agent": SIDE_AGENT,
            }
        },
    )
    return registry_path, state_file, event_log


def event(event_id: str, event_type: str, todo_id: str, payload: dict) -> dict:
    return make_state_event(
        event_id=event_id,
        goal_id=GOAL_ID,
        event_type=event_type,
        refs={"todo_id": todo_id},
        payload=payload,
        recorded_at=f"2026-06-27T00:00:{len(event_id):02d}Z",
        producer="todo-list-event-projection-smoke",
    )


def run_cli(registry_path: Path, *args: str) -> dict:
    return run_json_cli(
        *args,
        registry_path=registry_path,
        include_returncode=False,
    )


def write_events(event_log: Path) -> None:
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        event(
            "evt-open",
            TODO_ADDED,
            "todo_event_open",
            {
                "role": "agent",
                "priority": "P0",
                "title": "Projected open todo",
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "implement",
                "continuation_policy": "independent_handoff",
            },
        )
    )
    store.append(
        event(
            "evt-done",
            TODO_ADDED,
            "todo_event_done",
            {
                "role": "agent",
                "priority": "P1",
                "title": "Projected completed todo",
                "planner_order": 2,
                "task_class": "advancement_task",
            },
        )
    )
    store.append(
        event(
            "evt-complete",
            TODO_COMPLETED,
            "todo_event_done",
            {"evidence": "projection smoke"},
        )
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-list-projection-") as tmp:
        registry_path, _, event_log = write_fixture(Path(tmp))
        write_events(event_log)

        projected = run_cli(registry_path, "todo", "list", "--goal-id", GOAL_ID, "--role", "agent")
        assert projected["ok"] is True, projected
        assert projected["read_only"] is True, projected
        assert projected["source"] == "event_projection_with_markdown_overlay", projected
        assert projected["todo_count"] == 4, projected
        assert [item["todo_id"] for item in projected["todos"]] == [
            "todo_event_open",
            "todo_markdown",
            DEPENDENT_TODO_ID,
            "todo_event_done",
        ], projected
        dependent = next(
            item for item in projected["todos"] if item["todo_id"] == DEPENDENT_TODO_ID
        )
        assert dependent["resume_ready"] is True, dependent
        assert dependent["resume_condition"]["target_status"] == "done", dependent
        projected_open = next(
            item for item in projected["todos"] if item["todo_id"] == "todo_event_open"
        )
        assert projected_open["continuation_policy"] == "independent_handoff", projected_open
        assert projected["projection_overlay"]["markdown_only_todo_ids"] == [
            GATE_TODO_ID,
            DEPENDENT_TODO_ID,
            "todo_markdown",
        ], projected
        assert projected["projection_overlay"]["event_only_todo_ids"] == [
            "todo_event_open",
            "todo_event_done",
        ], projected
        assert projected["state_event_projection"]["source_event_count"] == 3, projected

        dependent_only = run_cli(
            registry_path,
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            DEPENDENT_TODO_ID,
        )
        assert dependent_only["todo_count"] == 1, dependent_only
        assert dependent_only["relations"]["resume_ready"] is True, dependent_only
        assert (
            dependent_only["relations"]["resume_condition"]["target_status"] == "done"
        ), dependent_only

        done_only = run_cli(
            registry_path,
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--status",
            "done",
        )
        assert done_only["source"] == "event_projection_with_markdown_overlay", done_only
        assert done_only["todo_count"] == 1, done_only
        assert done_only["todos"][0]["todo_id"] == "todo_event_done", done_only

        store = AppendOnlyStateEventStore(event_log)
        store.append(
            event(
                "evt-non-delivery-gate",
                TODO_ADDED,
                EVENT_GATE_TODO_ID,
                {
                    "role": "agent",
                    "priority": "P1",
                    "title": "Complete an event-projected readiness gate",
                    "task_class": "advancement_task",
                    "action_kind": "readiness_check",
                    "continuation_policy": "same_agent_non_delivery",
                    "claimed_by": SIDE_AGENT,
                    "blocks_agent": PRIMARY_AGENT,
                },
            )
        )
        store.append(
            event(
                "evt-same-agent-successor",
                TODO_ADDED,
                EVENT_SUCCESSOR_TODO_ID,
                {
                    "role": "agent",
                    "priority": "P1",
                    "title": "Continue the event-projected lane",
                    "task_class": "advancement_task",
                    "action_kind": "continue_lane",
                    "continuation_policy": "independent_handoff",
                    "claimed_by": SIDE_AGENT,
                },
            )
        )
        completed = run_cli(
            registry_path,
            "todo",
            "complete",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--todo-id",
            EVENT_GATE_TODO_ID,
            "--agent-id",
            SIDE_AGENT,
            "--claimed-by",
            SIDE_AGENT,
            "--evidence",
            "public-safe event-projected readiness evidence",
            "--successor-todo-id",
            EVENT_SUCCESSOR_TODO_ID,
        )
        assert completed["linked_successor_id"] == EVENT_SUCCESSOR_TODO_ID, completed
        assert completed["self_merged"] is False, completed

        event_log.unlink()
        fallback = run_cli(registry_path, "todo", "list", "--goal-id", GOAL_ID, "--role", "agent")
        assert fallback["source"] == "markdown_active_state", fallback
        assert fallback["todo_count"] == 2, fallback
        assert [item["todo_id"] for item in fallback["todos"]] == [
            "todo_markdown",
            DEPENDENT_TODO_ID,
        ], fallback
        fallback_dependent = run_cli(
            registry_path,
            "todo",
            "list",
            "--goal-id",
            GOAL_ID,
            "--todo-id",
            DEPENDENT_TODO_ID,
        )
        assert fallback_dependent["relations"]["resume_ready"] is True, fallback_dependent
        assert (
            fallback_dependent["relations"]["resume_condition"]["target_status"] == "done"
        ), fallback_dependent

    print("todo-list-event-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
