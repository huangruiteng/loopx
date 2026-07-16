from __future__ import annotations

import pytest

from loopx.control_plane.todos.decision_scope import (
    build_required_decision_scope_consistency,
    build_required_decision_scope_repair_hint,
)


AGENT_ID = "codex-quality-qualification"
SCOPE = {
    "schema_version": "decision_scope_v0",
    "kind": "direction",
    "granularity": "action",
    "scope_key": "publish_quality_contract",
}


def _agent_summary() -> dict:
    return {
        "first_open_items": [
            {
                "todo_id": "todo_agent_delivery",
                "status": "open",
                "task_class": "advancement_task",
                "claimed_by": AGENT_ID,
                "required_decision_scopes": [SCOPE],
            }
        ]
    }


def _user_summary(*items: dict) -> dict:
    return {
        "first_open_items": list(items),
        "backlog_items": list(items),
    }


@pytest.mark.parametrize(
    "gate",
    [
        {
            "todo_id": "todo_current_gate",
            "status": "open",
            "task_class": "user_gate",
            "blocks_agent": AGENT_ID,
            "decision_scope": SCOPE,
        },
        {
            "todo_id": "todo_global_gate",
            "status": "open",
            "task_class": "user_gate",
            "global_gate": True,
            "decision_scope": SCOPE,
        },
    ],
)
def test_required_scope_resolves_only_to_compatible_blocking_gate(gate: dict) -> None:
    result = build_required_decision_scope_consistency(
        _agent_summary(),
        _user_summary(gate),
        agent_id=AGENT_ID,
    )

    assert result["ok"] is True
    assert result["checked_required_scope_count"] == 1
    assert result["errors"] == []


@pytest.mark.parametrize(
    ("user_item", "reason_code"),
    [
        (
            {
                "todo_id": "todo_nonblocking_action",
                "status": "open",
                "task_class": "user_action",
                "decision_scope": SCOPE,
            },
            "non_blocking_user_action_scope_collision",
        ),
        (
            {
                "todo_id": "todo_other_agent_gate",
                "status": "open",
                "task_class": "user_gate",
                "blocks_agent": "codex-other-agent",
                "decision_scope": SCOPE,
            },
            "required_decision_scope_gate_owner_mismatch",
        ),
        (None, "dangling_required_decision_scope"),
    ],
)
def test_invalid_required_scope_projects_bounded_repair(
    user_item: dict | None,
    reason_code: str,
) -> None:
    result = build_required_decision_scope_consistency(
        _agent_summary(),
        _user_summary(*([user_item] if user_item else [])),
        agent_id=AGENT_ID,
    )
    repair = build_required_decision_scope_repair_hint(result)

    assert result["ok"] is False
    assert result["errors"][0]["reason_code"] == reason_code
    assert repair is not None
    assert repair["effective_action"] == "todo_decision_scope_projection_repair"
    assert repair["allowed"] is True


def test_unrelated_gate_has_no_authority_over_independent_agent_todo() -> None:
    agent_summary = _agent_summary()
    agent_summary["first_open_items"][0]["required_decision_scopes"] = []
    unrelated_gate = {
        "todo_id": "todo_other_agent_gate",
        "status": "open",
        "task_class": "user_gate",
        "blocks_agent": "codex-other-agent",
        "decision_scope": SCOPE,
    }

    result = build_required_decision_scope_consistency(
        agent_summary,
        _user_summary(unrelated_gate),
        agent_id=AGENT_ID,
    )

    assert result["ok"] is True
    assert result["checked_required_scope_count"] == 0
