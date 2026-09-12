from __future__ import annotations

import json
from pathlib import Path

from loopx.control_plane.todos.todo_semantics import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    todo_item_claimed_by_agent_or_unclaimed,
    todo_item_is_due_monitor,
    todo_item_task_class,
    todo_presentation_metadata,
    todo_presentation_sort_key,
)
from loopx.control_plane.todos.todo_summary import todo_item_task_class as summary_task_class


FIXTURE = Path(__file__).parents[1] / "fixtures/control_plane/coordination_production_scale_v0.json"


def test_summary_and_projection_share_title_aware_task_classification() -> None:
    item = {"title": "Observe dependency health", "text": "", "status": "open"}
    assert todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    assert summary_task_class(item) == TODO_TASK_CLASS_MONITOR
    assert todo_item_is_due_monitor(
        {**item, "next_due_at": "2025-01-01T00:00:00Z"},
        now=__import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )


def test_exclusion_is_part_of_selectability_not_claim_ownership() -> None:
    item = {"task_class": TODO_TASK_CLASS_ADVANCEMENT, "status": "open", "excluded_agents": ["agent-a"]}
    assert not todo_item_claimed_by_agent_or_unclaimed(item, agent_id="agent-a")
    assert todo_item_claimed_by_agent_or_unclaimed(item, agent_id="agent-b")


def test_complex_fixture_declares_cross_rfc_semantic_edges() -> None:
    cases = json.loads(FIXTURE.read_text())["semantic_cases"]
    assert cases["global_gate_without_goal_binding"]["global_gate"] is True
    assert cases["global_gate_without_goal_binding"]["goal_bound"] is False
    assert cases["expired_lease"]["lease_epoch"] == 7
    assert cases["excluded_unclaimed_advancement"]["claimed_by"] is None


def test_presentation_metadata_keeps_wire_address_out_of_native_ordering() -> None:
    legacy = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_legacy",
        "role": "agent",
        "status": "open",
        "archive_state": "active",
        "source_section": "Agent Todo",
        "index": 4,
    }
    native = {
        "schema_version": "todo_domain_record_v0",
        "todo_id": "todo_native",
        "role": "agent",
        "status": "open",
        "archive_state": "active",
        "updated_at": "2025-01-02T00:00:00Z",
    }
    assert todo_presentation_metadata(legacy)["order_source"] == "source_index"
    assert todo_presentation_metadata(native) == {
        "schema_version": "loopx_todo_presentation_metadata_v0",
        "todo_id": "todo_native",
        "display_section": "Agent Todo",
        "display_order": None,
        "order_source": "todo_id",
    }
    assert todo_presentation_sort_key(native)[1:] == (
        999999,
        "2025-01-02T00:00:00Z",
        "todo_native",
    )


def test_unknown_presentation_schema_fails_closed() -> None:
    try:
        todo_presentation_metadata({"schema_version": "future_todo_v1"})
    except ValueError as error:
        assert "unsupported Todo presentation schema" in str(error)
    else:  # pragma: no cover - assertion is the contract
        raise AssertionError("unknown Todo presentation schema was accepted")


def test_fixture_display_cases_match_the_python_presentation_owner() -> None:
    cases = json.loads(FIXTURE.read_text())["presentation_cases"]
    assert todo_presentation_metadata(cases["legacy_display"])["display_order"] == 7
    native = todo_presentation_metadata(cases["native_display"])
    assert native["display_section"] == "Completed Work Archive"
    assert native["display_order"] is None
