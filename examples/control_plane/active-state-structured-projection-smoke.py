#!/usr/bin/env python3
"""Smoke-test active-state structured projection diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.state_projection import (  # noqa: E402
    ACTIVE_STATE_STRUCTURED_PROJECTION_SCHEMA_VERSION,
    build_active_state_structured_projection,
)


GOAL_ID = "active-state-structured-projection-fixture"


def active_state_text() -> str:
    return (
        "---\n"
        "status: active\n"
        "updated_at: 2026-06-28T00:00:00+08:00\n"
        "---\n\n"
        "# Structured Projection Fixture\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        "- [ ] [P0] Approve the public release packet.\n"
        "  <!-- loopx:todo todo_id=todo_user_gate status=open task_class=user_gate blocks_agent=codex-product-capability -->\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Add active-state structured projection parity smoke.\n"
        "  <!-- loopx:todo todo_id=todo_agent_projection status=open task_class=advancement_task claimed_by=codex-product-capability target_capability=active_state_schema_migration -->\n"
        "- [ ] [P1] Watch external launch evidence.\n"
        "  <!-- loopx:todo todo_id=todo_monitor status=open task_class=continuous_monitor target_key=launch cadence=30m next_due_at=2026-06-28T01:00:00+08:00 -->\n\n"
        "## Next Action\n\n"
        "- todo_agent_projection: add the projection smoke and validate it.\n"
    )


def test_projection_shape() -> None:
    projection = build_active_state_structured_projection(
        active_state_text(),
        goal_id=GOAL_ID,
    )
    assert projection["schema_version"] == ACTIVE_STATE_STRUCTURED_PROJECTION_SCHEMA_VERSION
    assert projection["goal_id"] == GOAL_ID
    assert projection["frontmatter"]["status"] == "active"
    assert projection["next_action"]["first"].startswith("todo_agent_projection"), projection

    user = projection["todos"]["user"]
    agent = projection["todos"]["agent"]
    assert user["open_count"] == 1, user
    assert agent["open_count"] == 2, agent
    assert user["items"][0]["task_class"] == "user_gate", user
    assert user["items"][0]["blocks_agent"] == "codex-product-capability", user
    assert agent["items"][0]["claimed_by"] == "codex-product-capability", agent
    assert agent["items"][0]["target_capabilities"] == ["active_state_schema_migration"], agent
    assert agent["items"][1]["task_class"] == "continuous_monitor", agent
    assert agent["items"][1]["next_due_at"] == "2026-06-28T01:00:00+08:00", agent

    diagnostics = projection["diagnostics"]
    assert diagnostics["parseable"] is True, diagnostics
    assert diagnostics["migration_ready"] is True, diagnostics
    assert diagnostics["warning_count"] == 0, diagnostics
    assert diagnostics["error_count"] == 0, diagnostics


def test_migration_diagnostics() -> None:
    projection = build_active_state_structured_projection(
        "## Agent Todo\n\n"
        "- [ ] [P0] Implement a small parser fixture.\n\n"
        "## Next Action\n\n"
        "- Implement a small parser fixture.\n"
    )
    diagnostics = projection["diagnostics"]
    warning_kinds = {warning["kind"] for warning in diagnostics["warnings"]}
    assert diagnostics["parseable"] is True, diagnostics
    assert diagnostics["migration_ready"] is False, diagnostics
    assert "missing_frontmatter" in warning_kinds, diagnostics
    assert "implicit_todo_ids" in warning_kinds, diagnostics
    assert projection["todos"]["agent"]["implicit_todo_id_count"] == 1, projection

    duplicate = build_active_state_structured_projection(
        "## Agent Todo\n\n"
        "- [ ] First duplicated id.\n"
        "  <!-- loopx:todo todo_id=todo_duplicate status=open -->\n"
        "- [ ] Second duplicated id.\n"
        "  <!-- loopx:todo todo_id=todo_duplicate status=open -->\n"
    )
    duplicate_diagnostics = duplicate["diagnostics"]
    error_kinds = {error["kind"] for error in duplicate_diagnostics["errors"]}
    assert duplicate_diagnostics["parseable"] is False, duplicate_diagnostics
    assert "duplicate_todo_ids" in error_kinds, duplicate_diagnostics


def main() -> None:
    test_projection_shape()
    test_migration_diagnostics()
    print("active-state-structured-projection-smoke ok")


if __name__ == "__main__":
    main()
