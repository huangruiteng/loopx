#!/usr/bin/env python3
"""Validate Markdown active-state backfill into append-only LoopX events."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    LOCAL_PRIVATE_PRIVACY,
    MARKDOWN_BACKFILL_PRODUCER,
    PUBLIC_BACKFILL_REDACTION,
    PUBLIC_PRIVACY,
    backfill_todo_events_from_markdown,
    build_state_projection,
)


GOAL_ID = "event-sourced-markdown-backfill-fixture"


def fixture_markdown() -> str:
    return "\n".join(
        [
            "# Fixture Active State",
            "",
            "## User Todo / Owner Review Reading Queue",
            "",
            "- [ ] [P0] Approve private launch note https://private.example/doc",
            "  <!-- loopx:todo todo_id=todo_user_gate status=open task_class=user_gate claimed_by=codex-product-capability -->",
            "",
            "## Agent Todo",
            "",
            "- [ ] [P0] First same-priority migration check",
            "  <!-- loopx:todo todo_id=todo_first status=open task_class=advancement_task action_kind=validate claimed_by=codex-product-capability -->",
            "- [ ] [P0] Second same-priority migration check",
            "  <!-- loopx:todo todo_id=todo_second status=open task_class=advancement_task action_kind=validate -->",
            "- [x] [P1] Completed migration proof",
            "  <!-- loopx:todo todo_id=todo_done status=done task_class=advancement_task action_kind=validate evidence=validation_packet -->",
            "",
        ]
    )


def event_blob(events: list[dict]) -> str:
    return json.dumps(events, sort_keys=True, ensure_ascii=False)


def test_public_backfill_redacts_private_state() -> None:
    markdown = fixture_markdown()
    original = str(markdown)
    events = backfill_todo_events_from_markdown(
        markdown,
        goal_id=GOAL_ID,
        source_ref="/Users/example/project/.local/goals/example/ACTIVE_GOAL_STATE.md",
        recorded_at="2026-06-27T00:00:00Z",
        privacy=PUBLIC_PRIVACY,
    )

    assert markdown == original, "backfill must not mutate Markdown workbench"
    assert events, events
    assert all(event["producer"] == MARKDOWN_BACKFILL_PRODUCER for event in events), events
    assert all(event["privacy"] == PUBLIC_PRIVACY for event in events), events
    serialized = event_blob(events)
    assert "private.example" not in serialized, serialized
    assert "/Users/example" not in serialized, serialized
    assert "https://" not in serialized, serialized
    assert PUBLIC_BACKFILL_REDACTION in serialized, serialized
    assert all(event["refs"].get("source_ref") == "ACTIVE_GOAL_STATE.md" for event in events), events

    projection = build_state_projection(events, goal_id=GOAL_ID, generated_at="2026-06-27T00:01:00Z")
    assert [item["todo_id"] for item in projection["agent_todos"]["items"]] == [
        "todo_first",
        "todo_second",
        "todo_done",
    ], projection
    first = projection["agent_todos"]["items"][0]
    assert first["claimed_by"] == "codex-product-capability", projection
    assert projection["agent_todos"]["items"][2]["status"] == "done", projection
    assert projection["agent_todos"]["items"][2]["evidence"] == "validation_packet", projection
    assert projection["user_todos"]["items"][0]["task_class"] == "user_gate", projection
    assert projection["user_todos"]["items"][0]["title"] == PUBLIC_BACKFILL_REDACTION, projection


def test_local_private_backfill_preserves_private_workbench_text() -> None:
    events = backfill_todo_events_from_markdown(
        fixture_markdown(),
        goal_id=GOAL_ID,
        source_ref="ACTIVE_GOAL_STATE.md",
        recorded_at="2026-06-27T00:00:00Z",
        privacy=LOCAL_PRIVATE_PRIVACY,
    )
    serialized = event_blob(events)
    assert "https://private.example/doc" in serialized, serialized
    assert all(event["privacy"] == LOCAL_PRIVATE_PRIVACY for event in events), events


def test_append_many_is_idempotent_for_backfilled_events() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-markdown-backfill-") as tmp:
        store = AppendOnlyStateEventStore(Path(tmp) / "events.jsonl")
        events = backfill_todo_events_from_markdown(
            fixture_markdown(),
            goal_id=GOAL_ID,
            source_ref="ACTIVE_GOAL_STATE.md",
            recorded_at="2026-06-27T00:00:00Z",
            privacy=PUBLIC_PRIVACY,
        )
        store.append_many(events)
        store.append_many(events)
        projection = build_state_projection(store.load(), goal_id=GOAL_ID)
        assert projection["source_event_count"] == len(events), projection
        assert projection["last_append_sequence"] == len(events), projection


def test_backfill_preserves_removed_continuation_diagnostic() -> None:
    for policy in ("review_handoff", "primary_review"):
        events = backfill_todo_events_from_markdown(
            "\n".join(
                [
                    "## Agent Todo",
                    "",
                    "- [ ] [P0] Legacy review handoff must remain blocked",
                    "  <!-- loopx:todo todo_id=todo_legacy_review status=open "
                    "task_class=advancement_task action_kind=review "
                    f"continuation_policy={policy} -->",
                ]
            ),
            goal_id=GOAL_ID,
            source_ref="ACTIVE_GOAL_STATE.md",
            recorded_at="2026-07-11T00:00:00Z",
            privacy=PUBLIC_PRIVACY,
        )
        assert events[0]["payload"]["removed_continuation_policy"] == policy, events
        projection = build_state_projection(events, goal_id=GOAL_ID)
        item = projection["agent_todos"]["items"][0]
        assert item["removed_continuation_policy"] == policy, projection
        assert item.get("continuation_policy") is None, projection


def main() -> int:
    test_public_backfill_redacts_private_state()
    test_local_private_backfill_preserves_private_workbench_text()
    test_append_many_is_idempotent_for_backfilled_events()
    test_backfill_preserves_removed_continuation_diagnostic()
    print("event-sourced-markdown-backfill-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
