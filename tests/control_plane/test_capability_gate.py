from __future__ import annotations

from typing import Any

import pytest

from loopx.control_plane.agents.capability_gate import build_capability_gate


AGENT_ID = "codex-capability-test"


def _todo(
    todo_id: str,
    *,
    index: int,
    required: list[str] | None = None,
    targets: list[str] | None = None,
    task_class: str = "advancement_task",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "todo_id": todo_id,
        "text": f"fixture {todo_id}",
        "status": "open",
        "done": False,
        "index": index,
        "priority": "P1",
        "task_class": task_class,
        "claimed_by": AGENT_ID,
    }
    if required is not None:
        item["required_capabilities"] = required
    if targets is not None:
        item["target_capabilities"] = targets
    return item


def _gate(
    summary: dict[str, Any],
    *,
    available: list[str] | None = None,
) -> dict[str, Any] | None:
    return build_capability_gate(
        summary,
        available_capabilities=available or [],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )


@pytest.mark.parametrize(
    (
        "required",
        "expected_action",
        "expected_owner",
        "expected_missing_field",
    ),
    [
        (["shell"], "run", "agent", None),
        (["network"], "repair_bridge", "agent", "repair_missing"),
        (["credentials"], "ask_owner", "user", "owner_missing"),
        (["gpu_runner"], "skip", "capability_gate", "unsupported_missing"),
    ],
)
def test_missing_capability_decision_table(
    required: list[str],
    expected_action: str,
    expected_owner: str,
    expected_missing_field: str | None,
) -> None:
    gate = _gate(
        {
            "executable_backlog_items": [
                _todo("todo_primary", index=1, required=required)
            ]
        }
    )

    assert gate is not None
    assert gate["action"] == expected_action
    assert gate["decision_owner"] == expected_owner
    if expected_missing_field is None:
        assert gate["missing"] == []
    else:
        assert gate[expected_missing_field] == required
        assert gate["blocks_delivery"] is True


@pytest.mark.parametrize(
    ("summary_field", "expected_source"),
    [
        (
            "active_next_action_executable_items",
            "agent_todo_summary.active_next_action_executable_items",
        ),
        (
            "executable_backlog_items",
            "agent_todo_summary.executable_backlog_items",
        ),
        (
            "first_executable_items",
            "agent_todo_summary.first_executable_items",
        ),
    ],
)
def test_candidate_source_fallback_table(
    summary_field: str,
    expected_source: str,
) -> None:
    item = _todo("todo_source", index=1, required=["shell"])

    gate = _gate({summary_field: [item]})

    assert gate is not None
    assert gate["source"] == expected_source
    assert [candidate["todo_id"] for candidate in gate["runnable_candidates"]] == [
        "todo_source"
    ]


def test_active_next_source_adds_backlog_and_deduplicates_candidates() -> None:
    active = _todo("todo_active", index=1, required=["network"])
    fallback = _todo("todo_fallback", index=2, required=["shell"])

    gate = _gate(
        {
            "active_next_action_executable_items": [active, active],
            "executable_backlog_items": [active, fallback],
        }
    )

    assert gate is not None
    assert gate["action"] == "run"
    assert [item["todo_id"] for item in gate["runnable_candidates"]] == [
        "todo_fallback"
    ]
    assert [item["todo_id"] for item in gate["blocked_candidates"]] == ["todo_active"]
    assert gate["repair_missing"] == ["network"]


def test_due_monitor_candidates_join_advancement_without_becoming_global_gate() -> None:
    advancement = _todo("todo_local", index=1, required=["shell"])
    monitor = _todo(
        "todo_monitor",
        index=2,
        required=["network"],
        task_class="continuous_monitor",
    )

    gate = _gate(
        {
            "executable_backlog_items": [advancement],
            "monitor_due_items": [monitor],
        }
    )

    assert gate is not None
    assert gate["action"] == "run"
    assert gate["source"] == (
        "agent_todo_summary.executable_backlog_items+"
        "agent_todo_summary.monitor_due_items"
    )
    assert [item["todo_id"] for item in gate["runnable_candidates"]] == ["todo_local"]
    assert [item["todo_id"] for item in gate["blocked_candidates"]] == ["todo_monitor"]


def test_target_capability_is_repair_output_instead_of_prerequisite() -> None:
    repair = _todo(
        "todo_bridge_repair",
        index=1,
        required=["network"],
        targets=["network"],
    )

    gate = _gate({"executable_backlog_items": [repair]})

    assert gate is not None
    assert gate["action"] == "run"
    assert gate["repair_missing"] == ["network"]
    assert gate["repair_candidate_count"] == 1
    assert gate["runnable_candidates"][0]["capability_repair_mode"] is True


def test_requirement_free_candidate_does_not_invent_capability_gate() -> None:
    assert _gate({"executable_backlog_items": [_todo("todo_plain", index=1)]}) is None
