from pathlib import Path

from loopx.event_sourced_state import (
    TODO_ADDED,
    AppendOnlyStateEventStore,
    make_state_event,
)


def test_load_observes_events_appended_by_another_store(tmp_path: Path) -> None:
    event_log = tmp_path / "events.jsonl"
    reader = AppendOnlyStateEventStore(event_log)
    writer = AppendOnlyStateEventStore(event_log)
    assert reader.load() == []

    appended = writer.append(
        make_state_event(
            event_id="evt-concurrent-writer",
            goal_id="goal-a",
            event_type=TODO_ADDED,
            refs={"todo_id": "todo_concurrent_writer"},
            payload={"role": "agent", "title": "Observe the durable event."},
            recorded_at="2026-09-06T00:00:00Z",
        )
    )

    assert reader.load() == [appended]
