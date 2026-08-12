from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.work_items import task_lease
from loopx.control_plane.work_items.task_lease import (
    MAX_TASK_LEASE_TTL_SECONDS,
    TaskLeaseError,
    acquire_task_lease,
    assert_expected_version,
    inspect_task_lease,
    normalize_idempotency_key,
    normalize_ttl_seconds,
    release_task_lease,
    renew_task_lease,
    require_task_lease_fence,
    task_lease_fencing_token,
    task_lease_path,
    task_lease_owner_constraint,
    transfer_task_lease,
    write_scopes_overlap,
)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (["docs/**"], ["docs/a.md"], True),
        (["docs/sub/**"], ["docs/sub/a.md"], True),
        (["docs/a*.md"], ["docs/ab.md"], True),
        (["docs/**"], ["docs/sub/**"], True),
        (["**"], ["loopx/cli.py"], True),
        (["docs/a.md"], ["docs/b.md"], False),
        ([], ["docs/a.md"], False),
    ],
)
def test_write_scopes_overlap(
    left: list[str],
    right: list[str],
    expected: bool,
) -> None:
    assert write_scopes_overlap(left, right) is expected


@pytest.mark.parametrize(
    ("todo", "owner", "registered_agents", "reason"),
    [
        (None, "agent-a", ["agent-a"], "todo_not_found"),
        ({"status": "done"}, "agent-a", ["agent-a"], "todo_not_open"),
        ({"status": "open"}, "", ["agent-a"], "invalid_owner"),
        ({"status": "open"}, "agent-b", ["agent-a"], "owner_not_registered"),
        (
            {"status": "open", "excluded_agents": ["agent-a"]},
            "agent-a",
            ["agent-a"],
            "owner_excluded_from_todo",
        ),
        (
            {"status": "open", "claimed_by": "agent-b"},
            "agent-a",
            ["agent-a", "agent-b"],
            "owner_conflicts_with_claim",
        ),
    ],
)
def test_task_lease_owner_constraint_rejects_ineligible_owner(
    todo: dict[str, Any] | None,
    owner: str,
    registered_agents: list[str],
    reason: str,
) -> None:
    constraint = task_lease_owner_constraint(
        todo,
        owner=owner,
        registered_agents=registered_agents,
    )

    assert constraint["effective"] is False
    assert constraint["reason"] == reason


def test_task_lease_owner_constraint_accepts_matching_claim() -> None:
    constraint = task_lease_owner_constraint(
        {
            "status": "open",
            "claimed_by": "agent-a",
            "excluded_agents": ["agent-b"],
        },
        owner="agent-a",
        registered_agents=["agent-a", "agent-b"],
    )

    assert constraint == {"effective": True}


@pytest.mark.parametrize("ttl", [0, -1, MAX_TASK_LEASE_TTL_SECONDS + 1])
def test_normalize_ttl_seconds_rejects_out_of_range(ttl: int) -> None:
    with pytest.raises(TaskLeaseError, match="ttl seconds") as error:
        normalize_ttl_seconds(ttl)

    assert error.value.code == "invalid_ttl"


@pytest.mark.parametrize("key", ["", "contains space", "bad$key"])
def test_normalize_idempotency_key_rejects_non_token(key: str) -> None:
    with pytest.raises(TaskLeaseError) as error:
        normalize_idempotency_key(key)

    assert error.value.code == "invalid_idempotency_key"


def test_expected_version_is_compare_and_swap_guard() -> None:
    with pytest.raises(TaskLeaseError) as error:
        assert_expected_version({"version": 3}, 2)

    assert error.value.code == "version_mismatch"
    assert error.value.payload == {"expected_version": 2, "actual_version": 3}


def test_task_lease_lifecycle_preserves_idempotency_and_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(task_lease, "now_utc", lambda: now)
    monkeypatch.setattr(task_lease, "require_task_lease_owner_allowed", lambda **_: {})
    monkeypatch.setattr(
        task_lease,
        "require_registered_task_lease_owner",
        lambda **kwargs: kwargs["owner"],
    )
    monkeypatch.setattr(
        task_lease,
        "task_lease_owner_constraint",
        lambda *_args, **_kwargs: {"effective": True},
    )
    monkeypatch.setattr(task_lease, "active_conflicts", lambda **_: [])
    registry_path = tmp_path / "registry.json"
    runtime_root = tmp_path / "runtime"
    arguments = {
        "registry_path": registry_path,
        "runtime_root": runtime_root,
        "goal_id": "goal-a",
        "todo_id": "todo_leasea",
        "owner": "agent-a",
        "idempotency_key": "turn-1",
        "ttl_seconds": 120,
        "write_scopes": ["loopx/**"],
    }

    acquired = acquire_task_lease(**arguments)
    assert acquired["acquired"] is True
    assert acquired["lease"]["version"] == 1
    assert acquired["lease"]["fencing_generation"] == 1
    assert acquired["lease"]["expires_at"] == (
        now + timedelta(seconds=120)
    ).isoformat().replace("+00:00", "Z")
    acquired_fence = task_lease_fencing_token(acquired["lease"])

    repeated = acquire_task_lease(**arguments)
    assert repeated["idempotent"] is True
    assert repeated["lease"]["version"] == 1

    with pytest.raises(TaskLeaseError) as reuse_error:
        acquire_task_lease(**{**arguments, "ttl_seconds": 600})
    assert reuse_error.value.code == "idempotency_key_reuse"

    renewed = renew_task_lease(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-a",
        idempotency_key="turn-1",
        expected_version=1,
    )
    assert renewed["lease"]["version"] == 2
    assert renewed["lease"]["fencing_generation"] == 1
    assert task_lease_fencing_token(renewed["lease"]) == acquired_fence

    transferred = transfer_task_lease(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-a",
        idempotency_key="turn-1",
        new_owner="agent-b",
        new_idempotency_key="turn-2",
        expected_version=2,
    )
    assert transferred["lease"]["owner"] == "agent-b"
    assert transferred["lease"]["version"] == 3
    assert transferred["lease"]["fencing_generation"] == 2
    assert task_lease_fencing_token(transferred["lease"]) != acquired_fence

    released = release_task_lease(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-b",
        idempotency_key="turn-2",
        expected_version=3,
    )
    assert released["released"] is True
    assert released["lease"]["status"] == "released"
    assert released["lease"]["released_at"] == now.isoformat().replace("+00:00", "Z")
    assert released["lease"]["updated_at"] == released["lease"]["released_at"]
    assert released["lease"]["version"] == 4
    assert released["lease"]["fencing_generation"] == 2
    assert task_lease.lease_is_active(released["lease"], at=now) is False
    assert Path(str(released["lease_path"])).exists()
    assert task_lease.read_lease(Path(str(released["lease_path"]))) == released["lease"]
    repeated_release = release_task_lease(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-b",
        idempotency_key="turn-2",
        expected_version=4,
    )
    assert repeated_release["idempotent"] is True
    assert repeated_release["lease"] == released["lease"]
    inspected = inspect_task_lease(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
    )
    assert inspected["active"] is False
    assert inspected["lease"] == released["lease"]


def test_stale_task_lease_fence_is_rejected_after_reacquire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(task_lease, "now_utc", lambda: now)
    monkeypatch.setattr(task_lease, "require_task_lease_owner_allowed", lambda **_: {})
    monkeypatch.setattr(task_lease, "active_conflicts", lambda **_: [])
    registry_path = tmp_path / "registry.json"
    runtime_root = tmp_path / "runtime"
    arguments = {
        "registry_path": registry_path,
        "runtime_root": runtime_root,
        "goal_id": "goal-a",
        "todo_id": "todo_leasea",
        "owner": "agent-a",
        "idempotency_key": "turn-1",
        "ttl_seconds": 30,
        "write_scopes": ["loopx/**"],
    }

    acquired = acquire_task_lease(**arguments)
    stale_token = task_lease_fencing_token(acquired["lease"])
    now += timedelta(seconds=31)
    reacquired = acquire_task_lease(
        **arguments,
        expected_version=acquired["lease"]["version"],
    )

    assert reacquired["lease"]["fencing_generation"] == 2
    with pytest.raises(TaskLeaseError) as error:
        require_task_lease_fence(
            runtime_root=runtime_root,
            goal_id="goal-a",
            todo_id="todo_leasea",
            owner="agent-a",
            idempotency_key="turn-1",
            fencing_token=stale_token,
        )

    assert error.value.code == "stale_fencing_token"


def test_task_lease_file_is_private_and_release_tombstone_reacquires_higher_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(task_lease, "now_utc", lambda: now)
    monkeypatch.setattr(task_lease, "require_task_lease_owner_allowed", lambda **_: {})
    monkeypatch.setattr(task_lease, "active_conflicts", lambda **_: [])
    registry_path = tmp_path / "registry.json"
    runtime_root = tmp_path / "runtime"
    arguments = {
        "registry_path": registry_path,
        "runtime_root": runtime_root,
        "goal_id": "goal-a",
        "todo_id": "todo_leasea",
        "owner": "agent-a",
        "idempotency_key": "turn-1",
        "ttl_seconds": 120,
        "write_scopes": ["loopx/**"],
    }
    path = task_lease_path(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
    )

    acquired = acquire_task_lease(**arguments)
    assert path.stat().st_mode & 0o777 == 0o600
    released = release_task_lease(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-a",
        idempotency_key="turn-1",
        expected_version=acquired["lease"]["version"],
    )
    reacquired = acquire_task_lease(
        **{**arguments, "idempotency_key": "turn-2"},
        expected_version=released["lease"]["version"],
    )

    assert reacquired["lease"]["fencing_generation"] == 2
    assert reacquired["lease"]["version"] == released["lease"]["version"] + 1


def test_legacy_active_lease_uses_current_version_as_stable_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(task_lease, "now_utc", lambda: now)
    monkeypatch.setattr(task_lease, "require_task_lease_owner_allowed", lambda **_: {})
    runtime_root = tmp_path / "runtime"
    path = task_lease_path(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
    )
    legacy = {
        "schema_version": "task_lease_v0",
        "goal_id": "goal-a",
        "todo_id": "todo_leasea",
        "owner": "agent-a",
        "idempotency_key": "turn-1",
        "write_scopes": ["loopx/**"],
        "acquire_ttl_seconds": 120,
        "version": 7,
        "acquired_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=120)).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "active",
    }
    task_lease.write_lease(path, legacy)
    token = task_lease_fencing_token(legacy)

    renewed = renew_task_lease(
        registry_path=tmp_path / "registry.json",
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-a",
        idempotency_key="turn-1",
        expected_version=7,
    )

    assert renewed["lease"]["version"] == 8
    assert renewed["lease"]["fencing_generation"] == 7
    assert task_lease_fencing_token(renewed["lease"]) == token


def test_write_lease_failure_before_replace_preserves_complete_old_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "lease.json"
    old = {"schema_version": "task_lease_v0", "version": 1}
    new = {"schema_version": "task_lease_v0", "version": 2}
    task_lease.write_lease(path, old)

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("injected before replace")

    monkeypatch.setattr(task_lease.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected before replace"):
        task_lease.write_lease(path, new)

    assert task_lease.read_lease(path) == old
    assert list(tmp_path.glob(".lease.json.*.tmp")) == []


def test_write_lease_directory_fsync_failure_leaves_complete_new_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "lease.json"
    old = {"schema_version": "task_lease_v0", "version": 1}
    new = {"schema_version": "task_lease_v0", "version": 2}
    task_lease.write_lease(path, old)
    real_fsync = task_lease.os.fsync
    calls = 0

    def fail_directory_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected directory fsync")
        real_fsync(descriptor)

    monkeypatch.setattr(task_lease.os, "fsync", fail_directory_fsync)
    with pytest.raises(OSError, match="injected directory fsync"):
        task_lease.write_lease(path, new)

    assert task_lease.read_lease(path) == new
    assert list(tmp_path.glob(".lease.json.*.tmp")) == []
