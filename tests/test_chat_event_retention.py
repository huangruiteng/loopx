from __future__ import annotations

from datetime import datetime, timedelta, timezone
import gc
import json
from pathlib import Path

import pytest

import loopx.chat_store as chat_store
from loopx.chat_store import CHAT_TURN_SCHEMA_VERSION, ChatSessionStore


def _write_completed_turn(root: Path, *, with_events: bool = True) -> tuple[Path, Path]:
    turn_path = root / "chat" / "sessions" / "session" / "turns" / "turn.json"
    turn_path.parent.mkdir(parents=True)
    turn_path.write_text(
        json.dumps(
            {
                "schema_version": CHAT_TURN_SCHEMA_VERSION,
                "session_id": "session",
                "turn_id": "turn",
                "status": "completed",
                "completed_at": (
                    datetime.now(timezone.utc) - timedelta(days=2)
                ).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    event_path = turn_path.with_name("turn.events.jsonl")
    if with_events:
        rows = [
            {"kind": "answer.delta", "sequence": 1, "event_id": "1"},
            {"kind": "turn.completed", "sequence": 2, "event_id": "2"},
        ]
        event_path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
    return turn_path, event_path


def test_completed_replay_reuses_log_until_an_external_append(tmp_path: Path, monkeypatch) -> None:
    store = ChatSessionStore(tmp_path)
    key = ("session", "turn")
    store.append_event(*key, kind="assistant.delta", payload={"text": "visible"}, buffered=True)
    store.append_event(*key, kind="turn.completed", payload={})
    assert key not in store._event_cache._entries
    reads = []
    read = chat_store._read_jsonl

    def counted(path):
        reads.append(path)
        return read(path)

    monkeypatch.setattr(chat_store, "_read_jsonl", counted)
    for _ in range(5):
        assert [row["sequence"] for row in store.events_after(*key, "0")] == [1, 2]
    assert len(reads) == 1
    other = ChatSessionStore(tmp_path)
    other.append_event(*key, kind="turn.completed", payload={"recovered": True})
    assert [row["sequence"] for row in store.events_after(*key, "2")] == [3]
    assert len(reads) == 3  # independent writer plus invalidated reader


def test_completed_replay_evicts_least_recently_used_log(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    for i in range(8):
        store.append_event("session", str(i), kind="turn.completed", payload={})
        store.events_after("session", str(i), None)
    store.events_after("session", "0", None)
    store.append_event("session", "8", kind="turn.completed", payload={})
    store.events_after("session", "8", None)
    assert ("session", "0") in store._event_cache._entries
    assert ("session", "1") not in store._event_cache._entries
    assert len(store._event_cache._finished) == 8


@pytest.mark.parametrize("row_count,text_size", [(1, 2 * 1024 * 1024), (4096, 1)])
def test_oversized_completed_log_is_replayable_but_not_retained(
    tmp_path: Path, row_count: int, text_size: int,
) -> None:
    store = ChatSessionStore(tmp_path)
    key = ("session", "large")
    for _ in range(row_count):
        store.append_event(*key, kind="assistant.delta", payload={"text": "x" * text_size}, buffered=True)
    store.append_event(*key, kind="turn.completed", payload={})
    assert len(store.events_after(*key, None)) == row_count + 1
    assert key not in store._event_cache._entries
    assert key not in store._event_cache._finished


def test_completed_replay_budget_is_aggregate(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    for turn in ("a", "b", "c"):
        store.append_event("session", turn, kind="assistant.delta", payload={"text": "x" * 800_000}, buffered=True)
        store.append_event("session", turn, kind="turn.completed", payload={})
        store.events_after("session", turn, None)
    assert ("session", "a") not in store._event_cache._entries
    assert set(store._event_cache._finished) == {("session", "b"), ("session", "c")}


def test_old_replay_cannot_retain_a_replaced_snapshot(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    key = ("session", "turn")
    store.append_event(*key, kind="turn.completed", payload={})
    store.events_after(*key, None)
    old = store._event_cache._entries[key][1]
    store.append_event(*key, kind="assistant.delta", payload={"text": "continued"})
    store._event_cache.retain_terminal(key, old)
    assert key not in store._event_cache._finished
    assert store.events_after(*key, "1")[0]["kind"] == "assistant.delta"


def test_keyed_locks_are_released_after_callers_drop_them(tmp_path: Path) -> None:
    store = ChatSessionStore(tmp_path)
    session_lock = store._session_lock("session")
    event_lock = store._event_flush_lock(("session", "turn"))

    assert store._session_lock("session") is session_lock
    assert store._event_flush_lock(("session", "turn")) is event_lock

    del session_lock, event_lock
    gc.collect()

    assert "session" not in store._session_locks
    assert ("session", "turn") not in store._event_flush_locks


def test_completed_event_compaction_is_skipped_until_the_file_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    turn_path, event_path = _write_completed_turn(tmp_path)
    first = ChatSessionStore(tmp_path)
    turn = json.loads(turn_path.read_text(encoding="utf-8"))

    assert turn["event_compaction_revision"] == list(
        first._event_revision(event_path) or ()
    )
    assert ("session", "turn") not in first._event_cache._entries

    original_read_jsonl = chat_store._read_jsonl

    def reject_redundant_event_read(path: Path):
        if path == event_path:
            raise AssertionError("an unchanged compacted event stream was read again")
        return original_read_jsonl(path)

    monkeypatch.setattr(chat_store, "_read_jsonl", reject_redundant_event_read)
    restarted = ChatSessionStore(tmp_path)

    assert not restarted._event_cache._entries
    assert not restarted._event_flush_locks


def test_completed_event_compaction_marker_is_invalidated_by_a_new_event(
    tmp_path: Path,
) -> None:
    turn_path, event_path = _write_completed_turn(tmp_path)
    ChatSessionStore(tmp_path)
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps({"kind": "answer.delta", "sequence": 3, "event_id": "3"})
        )
        handle.write("\n")

    restarted = ChatSessionStore(tmp_path)
    rows = chat_store._read_jsonl(event_path)
    turn = json.loads(turn_path.read_text(encoding="utf-8"))

    assert [row["kind"] for row in rows] == ["turn.completed"]
    assert turn["event_compaction_revision"] == list(
        restarted._event_revision(event_path) or ()
    )
    assert ("session", "turn") not in restarted._event_cache._entries


def test_missing_event_stream_is_marked_without_retaining_empty_state(
    tmp_path: Path,
) -> None:
    turn_path, _event_path = _write_completed_turn(tmp_path, with_events=False)

    store = ChatSessionStore(tmp_path)
    turn = json.loads(turn_path.read_text(encoding="utf-8"))

    assert turn["event_compaction_revision"] == []
    assert not store._event_cache._entries
    assert not store._event_flush_locks


def test_compaction_marker_does_not_make_legacy_terminal_turns_unreadable(
    tmp_path: Path,
) -> None:
    turn_path, event_path = _write_completed_turn(tmp_path)
    turn = json.loads(turn_path.read_text(encoding="utf-8"))
    turn.pop("schema_version")
    turn_path.write_text(json.dumps(turn), encoding="utf-8")

    store = ChatSessionStore(tmp_path)
    persisted = json.loads(turn_path.read_text(encoding="utf-8"))

    assert persisted["event_compaction_revision"] == list(
        store._event_revision(event_path) or ()
    )
