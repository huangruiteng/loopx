from __future__ import annotations

from pathlib import Path

from loopx.chat_store import ChatSessionStore


def test_events_after_does_not_scan_the_cached_prefix(tmp_path: Path) -> None:
    class NonIterableRows(list[dict[str, object]]):
        def __iter__(self):
            raise AssertionError("events_after scanned the cached prefix")

    store = ChatSessionStore(tmp_path)
    session_id = "session"
    turn_id = "turn"
    event_path = store._event_path(session_id, turn_id)
    event_path.parent.mkdir(parents=True)
    event_path.touch()
    key = (session_id, turn_id)
    store._event_cache[key] = NonIterableRows(
        [
            {"sequence": 1, "event_id": "1"},
            {"sequence": 4, "event_id": "4"},
            {"sequence": 7, "event_id": "7"},
        ]
    )
    store._event_cache_revision[key] = store._event_revision(event_path)

    assert store.events_after(session_id, turn_id, "4") == [
        {"sequence": 7, "event_id": "7"}
    ]
