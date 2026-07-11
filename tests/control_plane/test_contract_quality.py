from __future__ import annotations

from datetime import datetime
from typing import get_type_hints

import pytest

from loopx.control_plane import compact_control_plane_policy
from loopx.control_plane.scheduler.time import parse_scheduler_timestamp
from loopx.control_plane.todos.contract import format_todo_metadata_line
from loopx.control_plane.work_items.lifecycle import ordered_lifecycle_flags
from loopx.presentation.sinks.lark import kanban, sync_receipt


def test_scheduler_timestamp_return_annotation_resolves() -> None:
    hints = get_type_hints(parse_scheduler_timestamp)

    assert hints["return"] == datetime | None


def test_control_plane_policy_ignores_non_mapping_self_repair() -> None:
    assert compact_control_plane_policy({"self_repair": None}) == {}


def test_lifecycle_flags_are_deduplicated_before_priority_sort() -> None:
    assert ordered_lifecycle_flags(
        ["unknown", "waiting", "running", "waiting", "", "unknown"],
        lifecycle_priority=("running", "waiting"),
    ) == ["running", "waiting", "unknown"]


def test_invalid_removed_continuation_policy_reports_allowed_values() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "removed_continuation_policy must be one of: primary_review, review_handoff"
        ),
    ):
        format_todo_metadata_line(
            todo_id="todo_contract_quality",
            removed_continuation_policy="invalid_policy",
        )


def test_lark_kanban_preserves_sync_receipt_compatibility_exports() -> None:
    assert (
        kanban.compact_lark_kanban_sync_receipt
        is sync_receipt.compact_lark_kanban_sync_receipt
    )
    assert (
        kanban.render_lark_kanban_markdown is sync_receipt.render_lark_kanban_markdown
    )
