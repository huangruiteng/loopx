#!/usr/bin/env python3
"""Smoke-test that derived state projections stay bounded and reconstructable."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import (  # noqa: E402
    MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS,
    MAX_PROJECT_ASSET_TODO_ITEMS,
    MAX_STATUS_TODOS_PER_ROLE,
    MAX_TODO_VISIBILITY_LANE_ITEMS,
    TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
    TODO_PROJECTION_VIEW_SCHEMA_VERSION,
    parse_active_state_todos,
    project_asset_todo_summary,
)
from loopx.control_plane.todos.completed_archive import (  # noqa: E402
    completed_todo_archive_warning,
)


def build_active_state() -> str:
    open_lines: list[str] = []
    claimants = ("codex-main-control", "codex-side-bypass", "codex-review")
    for index in range(1, 31):
        claimant = claimants[index % len(claimants)] if index <= 24 else ""
        metadata = (
            f"  <!-- loopx:todo todo_id=todo_derived_{index:02d} "
            "status=open task_class=advancement_task "
            f"action_kind=derived_state_fixture_{index:02d}"
        )
        if claimant:
            metadata += f" claimed_by={claimant}"
        metadata += " -->"
        open_lines.append(f"- [ ] [P1] Derived projection candidate {index:02d}.")
        open_lines.append(metadata)

    done_lines = [
        (
            f"- [x] [P2] Completed derived projection history {index:02d}.\n"
            f"  <!-- loopx:todo todo_id=todo_done_{index:02d} "
            "status=done task_class=advancement_task -->"
        )
        for index in range(1, 21)
    ]
    return (
        "## Agent Todo\n\n"
        + "\n".join(open_lines)
        + "\n"
        + "\n".join(done_lines)
        + "\n"
    )


def main() -> int:
    agent_todos = parse_active_state_todos(build_active_state())["agent_todos"]
    assert agent_todos["total_count"] == 50, agent_todos
    assert agent_todos["open_count"] == 30, agent_todos
    assert agent_todos["done_count"] == 20, agent_todos

    assert len(agent_todos["items"]) == MAX_STATUS_TODOS_PER_ROLE, agent_todos
    assert len(agent_todos["backlog_items"]) == MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS, agent_todos
    assert len(agent_todos["executable_backlog_items"]) == (
        MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS
    ), agent_todos
    assert len(agent_todos["claimed_open_items"]) == MAX_TODO_VISIBILITY_LANE_ITEMS, agent_todos
    assert len(agent_todos["claimed_advancement_open_items"]) == (
        MAX_TODO_VISIBILITY_LANE_ITEMS
    ), agent_todos
    assert agent_todos["claimed_open_count"] == 24, agent_todos
    assert agent_todos["claimed_advancement_open_count"] == 24, agent_todos
    assert agent_todos["claimed_open_items"][0]["todo_id"].startswith("todo_derived_"), (
        agent_todos
    )
    assert agent_todos["claimed_open_items"][0]["source_section"] == "Agent Todo", agent_todos

    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    assert asset_summary["projection_view"] == {
        "schema_version": TODO_PROJECTION_VIEW_SCHEMA_VERSION,
        "view": "project_asset_overview",
        "truth": "derived",
        "canonical_source": "attention_queue.items[].agent_todos",
        "item_limit": MAX_PROJECT_ASSET_TODO_ITEMS,
        "deferred_item_limit": MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    }, asset_summary
    assert asset_summary["detail_pointer"] == {
        "schema_version": TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
        "cold_path": "loopx status --format json",
        "active_state_source": "registry goal state_file",
        "full_list_included": False,
    }, asset_summary
    assert len(asset_summary["items"]) == MAX_PROJECT_ASSET_TODO_ITEMS, asset_summary
    assert asset_summary["claimed_open_count"] == 24, asset_summary
    assert asset_summary["unclaimed_open_count"] == 6, asset_summary
    assert len(asset_summary["first_executable_items"]) == MAX_PROJECT_ASSET_TODO_ITEMS, (
        asset_summary
    )
    assert asset_summary["first_executable_items"][0]["todo_id"] == "todo_derived_01", (
        asset_summary
    )
    assert asset_summary["claimed_advancement_open_count"] == 24, asset_summary
    assert asset_summary["claimed_monitor_open_count"] == 0, asset_summary
    assert "backlog_items" not in asset_summary, asset_summary
    assert "claimed_open_items" not in asset_summary, asset_summary

    archive_warning = completed_todo_archive_warning(agent_todos)
    assert archive_warning is not None, agent_todos
    assert archive_warning["kind"] == "completed_agent_todo_archive_required", archive_warning
    assert archive_warning["active_done_count"] == 20, archive_warning
    assert archive_warning["max_active_done_count"] == MAX_STATUS_TODOS_PER_ROLE, (
        archive_warning
    )

    docs = (REPO_ROOT / "docs" / "field-derived-patterns.md").read_text(encoding="utf-8")
    for required in (
        "## 3. Bounded Derived State Inheritance",
        "canonical source",
        "inheritance rule",
        "item limits",
        "archive/prune rule",
        "projection semantics",
        "Model-created state must not become a second source of truth",
    ):
        assert required in docs, required

    print("derived-state-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
