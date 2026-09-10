import json
from contextlib import contextmanager
from pathlib import Path

import pytest

import loopx.event_sourced_state as event_sourced_state
from loopx.event_sourced_state import (
    TODO_ADDED,
    AppendOnlyStateEventStore,
    StateEventError,
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

    assert appended["append_sequence"] == 1
    assert reader.load() == [appended]


def test_append_many_loads_once_and_preserves_idempotent_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = AppendOnlyStateEventStore(tmp_path / "events.jsonl")
    events = [
        make_state_event(
            event_id=f"event-{index}",
            goal_id="goal-a",
            event_type=TODO_ADDED,
            refs={"todo_id": f"todo_event_{index}"},
            payload={"role": "agent", "title": f"Event {index}"},
            recorded_at="2026-09-08T00:00:00Z",
        )
        for index in range(3)
    ]
    first = store.append(events[0])
    load = store.load
    load_count = 0

    def counted_load() -> list[dict[str, object]]:
        nonlocal load_count
        load_count += 1
        return load()

    monkeypatch.setattr(store, "load", counted_load)
    appended = store.append_many([events[1], events[1], events[0], events[2]])

    assert load_count == 1
    assert [event["append_sequence"] for event in appended] == [2, 2, 1, 3]
    assert [event["event_id"] for event in load()] == [
        "event-0",
        "event-1",
        "event-2",
    ]
    assert appended[2] == first


def test_append_many_preserves_lazy_iterable_visibility_and_reentrancy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = AppendOnlyStateEventStore(tmp_path / "events.jsonl")
    events = [
        make_state_event(
            event_id=f"lazy-event-{index}",
            goal_id="goal-a",
            event_type=TODO_ADDED,
            refs={"todo_id": f"todo_lazy_event_{index}"},
            payload={"role": "agent", "title": f"Lazy event {index}"},
            recorded_at="2026-09-09T00:00:00Z",
        )
        for index in range(3)
    ]
    lock_held = False

    @contextmanager
    def non_reentrant_lock(_path: Path):
        nonlocal lock_held
        assert not lock_held
        lock_held = True
        try:
            yield
        finally:
            lock_held = False

    monkeypatch.setattr(
        event_sourced_state,
        "exclusive_file_lock",
        non_reentrant_lock,
    )
    observed_prefix: list[str] = []

    def lazy_events():
        yield events[0]
        observed_prefix.extend(event["event_id"] for event in store.load())
        store.append(events[1])
        yield events[2]

    appended = store.append_many(lazy_events())

    assert observed_prefix == ["lazy-event-0"]
    assert [event["event_id"] for event in appended] == [
        "lazy-event-0",
        "lazy-event-2",
    ]
    assert [event["event_id"] for event in store.load()] == [
        "lazy-event-0",
        "lazy-event-1",
        "lazy-event-2",
    ]


def test_append_many_does_not_iterate_list_subclasses_under_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = AppendOnlyStateEventStore(tmp_path / "events.jsonl")
    events = [
        make_state_event(
            event_id=f"subclass-event-{index}",
            goal_id="goal-a",
            event_type=TODO_ADDED,
            refs={"todo_id": f"todo_subclass_event_{index}"},
            payload={"role": "agent", "title": f"Subclass event {index}"},
            recorded_at="2026-09-10T00:00:00Z",
        )
        for index in range(2)
    ]
    lock_held = False

    @contextmanager
    def non_reentrant_lock(_path: Path):
        nonlocal lock_held
        assert not lock_held
        lock_held = True
        try:
            yield
        finally:
            lock_held = False

    monkeypatch.setattr(event_sourced_state, "exclusive_file_lock", non_reentrant_lock)

    class ReentrantList(list):
        def __iter__(self):
            store.append(events[1])
            return super().__iter__()

    appended = store.append_many(ReentrantList([events[0]]))

    assert [event["event_id"] for event in appended] == ["subclass-event-0"]
    assert [event["event_id"] for event in store.load()] == [
        "subclass-event-1",
        "subclass-event-0",
    ]


def test_append_many_flushes_each_event_before_processing_the_next(
    tmp_path: Path,
) -> None:
    event_log = tmp_path / "events.jsonl"
    store = AppendOnlyStateEventStore(event_log)
    first = make_state_event(
        event_id="flush-event-0",
        goal_id="goal-a",
        event_type=TODO_ADDED,
        refs={"todo_id": "todo_flush_event_0"},
        payload={"role": "agent", "title": "First event"},
        recorded_at="2026-09-10T00:00:00Z",
    )
    observed_prefix: list[str] = []

    class ObservingEvent(dict):
        def get(self, key, default=None):
            if not observed_prefix:
                observed_prefix.append(event_log.read_text(encoding="utf-8"))
            return super().get(key, default)

    second = ObservingEvent(
        make_state_event(
            event_id="flush-event-1",
            goal_id="goal-a",
            event_type=TODO_ADDED,
            refs={"todo_id": "todo_flush_event_1"},
            payload={"role": "agent", "title": "Second event"},
            recorded_at="2026-09-10T00:00:00Z",
        )
    )

    store.append_many([first, second])

    assert '"event_id": "flush-event-0"' in observed_prefix[0]


@pytest.mark.parametrize("sequence", [True, False, 1.5, "2"])
def test_load_rejects_non_integer_append_sequence(tmp_path: Path, sequence: object) -> None:
    event_log = tmp_path / "events.jsonl"
    event = make_state_event(
        event_id="evt-bool-sequence",
        goal_id="goal-a",
        event_type=TODO_ADDED,
        refs={"todo_id": "todo_bool_sequence"},
        payload={"role": "agent", "title": "Reject corrupt sequence."},
        recorded_at="2026-09-07T00:00:00Z",
    )
    event["append_sequence"] = sequence
    event_log.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(StateEventError, match="append_sequence must be an integer"):
        AppendOnlyStateEventStore(event_log).load()
