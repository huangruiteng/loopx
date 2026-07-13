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
    normalize_idempotency_key,
    normalize_ttl_seconds,
    release_task_lease,
    renew_task_lease,
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
    assert acquired["lease"]["expires_at"] == (
        now + timedelta(seconds=120)
    ).isoformat().replace("+00:00", "Z")

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

    released = release_task_lease(
        runtime_root=runtime_root,
        goal_id="goal-a",
        todo_id="todo_leasea",
        owner="agent-b",
        idempotency_key="turn-2",
        expected_version=3,
    )
    assert released["released"] is True
