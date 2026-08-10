from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver.journal import (
    TurnJournalError,
    append_turn_event,
    load_turn_events,
    rebuild_turn_projection,
    turn_journal_path,
    turn_projection_path,
)
from loopx.control_plane.turn_driver import journal
from loopx.control_plane.work_items import task_lease
from loopx.control_plane.work_items.task_lease import (
    TaskLeaseError,
    acquire_task_lease,
    task_lease_fencing_token,
)


TURN_KEY = "sha256:" + "a" * 64


@pytest.fixture
def active_fence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(task_lease, "now_utc", lambda: now)
    monkeypatch.setattr(task_lease, "require_task_lease_owner_allowed", lambda **_: {})
    monkeypatch.setattr(task_lease, "active_conflicts", lambda **_: [])
    acquired = acquire_task_lease(
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path,
        goal_id="fixture-goal",
        todo_id="todo_fixture",
        owner="codex-a",
        idempotency_key="turn:fixture:a",
        ttl_seconds=120,
        write_scopes=["src/**"],
    )["lease"]
    return {
        "todo_id": acquired["todo_id"],
        "owner": acquired["owner"],
        "idempotency_key": acquired["idempotency_key"],
        "token": task_lease_fencing_token(acquired),
    }


def append_fixture_event(
    tmp_path: Path,
    fence: dict[str, object],
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return append_turn_event(
        runtime_root=tmp_path,
        goal_id="fixture-goal",
        turn_key=TURN_KEY,
        event_type="phase_completed",
        phase_key=f"{TURN_KEY}:validation:completed",
        fencing=fence,
        payload=payload or {"phase": "validation", "receipt_ref": "receipt:fixture"},
    )


def test_append_is_idempotent_for_same_phase_key(
    tmp_path: Path,
    active_fence: dict[str, object],
) -> None:
    first = append_fixture_event(tmp_path, active_fence)
    replay = append_fixture_event(tmp_path, active_fence)

    assert replay == first
    assert len(load_turn_events(tmp_path, "fixture-goal", TURN_KEY)) == 1


def test_phase_key_conflict_fails_closed(
    tmp_path: Path,
    active_fence: dict[str, object],
) -> None:
    append_fixture_event(tmp_path, active_fence)

    with pytest.raises(TurnJournalError, match="phase key conflict"):
        append_fixture_event(
            tmp_path,
            active_fence,
            payload={"phase": "quota_spend", "receipt_ref": "receipt:other"},
        )


def test_stale_fence_cannot_append(
    tmp_path: Path,
    active_fence: dict[str, object],
) -> None:
    stale = {**active_fence, "token": "fence:" + "0" * 64}

    with pytest.raises(TaskLeaseError) as error:
        append_fixture_event(tmp_path, stale)

    assert error.value.code == "stale_fencing_token"
    assert not turn_journal_path(tmp_path, "fixture-goal", TURN_KEY).exists()


def test_projection_rebuilds_from_jsonl_after_projection_loss(
    tmp_path: Path,
    active_fence: dict[str, object],
) -> None:
    append_fixture_event(tmp_path, active_fence)
    turn_projection_path(tmp_path, "fixture-goal", TURN_KEY).unlink()

    projection = rebuild_turn_projection(tmp_path, "fixture-goal", TURN_KEY)

    assert projection["last_phase"] == "validation"
    assert projection["event_count"] == 1
    assert projection["last_event_hash"]


def test_idempotent_replay_restores_a_missing_projection(
    tmp_path: Path,
    active_fence: dict[str, object],
) -> None:
    first = append_fixture_event(tmp_path, active_fence)
    projection_path = turn_projection_path(tmp_path, "fixture-goal", TURN_KEY)
    projection_path.unlink()

    assert append_fixture_event(tmp_path, active_fence) == first
    assert projection_path.exists()


def test_append_obeys_lease_then_journal_lock_order(
    tmp_path: Path,
    active_fence: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered: list[str] = []
    active: list[str] = []

    @contextmanager
    def record_lock(_path: Path, **kwargs: object):
        operation = str(kwargs.get("operation") or "")
        entered.append(operation)
        active.append(operation)
        if operation == "turn_journal_append":
            assert active == ["turn_journal_lease_fence", "turn_journal_append"]
        try:
            yield _path
        finally:
            active.pop()

    monkeypatch.setattr(journal, "exclusive_file_lock", record_lock)

    append_fixture_event(tmp_path, active_fence)

    assert entered == ["turn_journal_lease_fence", "turn_journal_append"]


@pytest.mark.parametrize("corruption", ["truncated", "hash", "schema"])
def test_corrupt_journal_fails_closed(
    tmp_path: Path,
    active_fence: dict[str, object],
    corruption: str,
) -> None:
    event = append_fixture_event(tmp_path, active_fence)
    path = turn_journal_path(tmp_path, "fixture-goal", TURN_KEY)
    if corruption == "truncated":
        path.write_bytes(path.read_bytes().rstrip(b"\n")[:-1])
    else:
        changed = dict(event)
        if corruption == "hash":
            changed["payload"] = {"phase": "tampered"}
        else:
            changed["schema_version"] = "unsupported"
        path.write_text(json.dumps(changed) + "\n", encoding="utf-8")

    with pytest.raises(TurnJournalError):
        load_turn_events(tmp_path, "fixture-goal", TURN_KEY)
