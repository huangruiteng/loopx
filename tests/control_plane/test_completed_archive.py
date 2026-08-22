from __future__ import annotations

from loopx.control_plane.todos.completed_archive import (
    archive_completed_todo_lines,
    completed_todo_archive_warning,
)
from loopx.status import parse_active_state_todos


def _fixture_text() -> str:
    return (
        "# Goal\n\n"
        "## Agent Todo\n\n"
        "- [x] Completed work.\n"
        "  <!-- loopx:todo todo_id=todo_done status=done -->\n"
        "- [-] Deferred work.\n"
        "  <!-- loopx:todo todo_id=todo_deferred status=deferred "
        "resume_when=todo_done:todo_done -->\n\n"
        "## Completed Work Archive\n"
    )


def test_completed_archive_keeps_deferred_todo_active() -> None:
    original = _fixture_text()
    parsed = parse_active_state_todos(original)["agent_todos"]

    assert parsed["done_count"] == 2
    assert parsed["deferred_count"] == 1
    warning = completed_todo_archive_warning(parsed, max_active_done_todos=0)
    assert warning is not None
    assert warning["active_done_count"] == 1

    result = archive_completed_todo_lines(original.splitlines(), max_active_done=0)
    updated = "\n".join(result["lines"])

    assert result["moved_count"] == 1
    assert updated.index("Deferred work.") < updated.index("## Completed Work Archive")
    assert updated.index("## Completed Work Archive") < updated.index("Completed work.")
    projected = parse_active_state_todos(updated)["agent_todos"]
    deferred = next(
        item for item in projected["items"] if item["todo_id"] == "todo_deferred"
    )
    assert deferred["status"] == "deferred"
    assert deferred["archive_state"] == "active"
