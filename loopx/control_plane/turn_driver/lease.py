"""Turn-scoped ownership adapter over the canonical task lease."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..work_items.task_lease import (
    DEFAULT_TASK_LEASE_TTL_SECONDS,
    acquire_task_lease,
    hold_task_lease_fence,
    release_task_lease,
    renew_task_lease,
    require_task_lease_fence,
    task_lease_fencing_generation,
    task_lease_fencing_token,
)


@dataclass(frozen=True, slots=True)
class TurnFence:
    goal_id: str
    todo_id: str
    owner: str
    idempotency_key: str
    token: str
    generation: int
    version: int


class TurnLeaseAuthority(Protocol):
    """Ownership interface shared by local and remote Turn lease adapters."""

    def acquire(self) -> TurnFence: ...

    def renew(self, fence: TurnFence) -> TurnFence: ...

    def require_current(self, fence: TurnFence) -> None: ...

    def release(self, fence: TurnFence) -> None: ...

    def heartbeat(
        self,
        fence: TurnFence,
    ) -> AbstractContextManager[Callable[[], TurnFence]]: ...

    def effect_guard(self, fence: TurnFence) -> AbstractContextManager[None]: ...


def _turn_fence(lease: dict[str, Any]) -> TurnFence:
    fencing_token = task_lease_fencing_token(lease)
    return TurnFence(
        goal_id=str(lease["goal_id"]),
        todo_id=str(lease["todo_id"]),
        owner=str(lease["owner"]),
        idempotency_key=str(lease["idempotency_key"]),
        generation=task_lease_fencing_generation(lease),
        version=int(lease["version"]),
        **{"token": fencing_token},
    )


@contextmanager
def hold_turn_lease_heartbeat(
    fence: TurnFence,
    *,
    renew: Callable[[TurnFence], TurnFence],
    interval_seconds: float,
) -> Iterator[Callable[[], TurnFence]]:
    """Renew one lease and expose the latest fence to either adapter."""

    current = fence
    renewal_error: BaseException | None = None
    state_lock = threading.Lock()
    stop = threading.Event()

    def latest() -> TurnFence:
        with state_lock:
            if renewal_error is not None:
                raise renewal_error
            return current

    def renew_until_stopped() -> None:
        nonlocal current, renewal_error
        while not stop.wait(interval_seconds):
            try:
                renewed = renew(latest())
            except BaseException as exc:  # noqa: BLE001 - propagated by latest()
                with state_lock:
                    renewal_error = exc
                stop.set()
                return
            with state_lock:
                current = renewed

    worker = threading.Thread(
        target=renew_until_stopped,
        name=f"loopx-turn-heartbeat-{fence.generation}",
        daemon=True,
    )
    worker.start()
    try:
        yield latest
    finally:
        stop.set()
        worker.join(timeout=max(1.0, interval_seconds + 0.1))


class TurnLeaseController:
    """Own one task lease for a bounded Turn execution."""

    def __init__(
        self,
        *,
        registry_path: Path,
        runtime_root: Path,
        goal_id: str,
        todo_id: str,
        owner: str,
        idempotency_key: str,
        write_scopes: list[str] | None = None,
        ttl_seconds: int | None = None,
        heartbeat_interval_seconds: float | None = None,
        terminal_replay_key: str | None = None,
    ) -> None:
        self._registry_path = registry_path
        self._runtime_root = runtime_root
        self._goal_id = goal_id
        self._todo_id = todo_id
        self._owner = owner
        self._idempotency_key = idempotency_key
        self._write_scopes = list(write_scopes or [])
        self._ttl_seconds = ttl_seconds
        self._terminal_replay_key = terminal_replay_key
        ttl = ttl_seconds or DEFAULT_TASK_LEASE_TTL_SECONDS
        self._heartbeat_interval_seconds = (
            max(0.001, heartbeat_interval_seconds)
            if heartbeat_interval_seconds is not None
            else ttl / 3
        )

    def acquire(self) -> TurnFence:
        outcome = acquire_task_lease(
            registry_path=self._registry_path,
            runtime_root=self._runtime_root,
            goal_id=self._goal_id,
            todo_id=self._todo_id,
            owner=self._owner,
            idempotency_key=self._idempotency_key,
            write_scopes=self._write_scopes,
            ttl_seconds=self._ttl_seconds,
            terminal_replay_key=self._terminal_replay_key,
        )
        return _turn_fence(dict(outcome["lease"]))

    def renew(self, fence: TurnFence) -> TurnFence:
        outcome = renew_task_lease(
            registry_path=self._registry_path,
            runtime_root=self._runtime_root,
            goal_id=fence.goal_id,
            todo_id=fence.todo_id,
            owner=fence.owner,
            idempotency_key=fence.idempotency_key,
            ttl_seconds=self._ttl_seconds,
            expected_version=fence.version,
            terminal_replay_key=self._terminal_replay_key,
        )
        return _turn_fence(dict(outcome["lease"]))

    def require_current(self, fence: TurnFence) -> None:
        require_task_lease_fence(
            runtime_root=self._runtime_root,
            goal_id=fence.goal_id,
            todo_id=fence.todo_id,
            owner=fence.owner,
            idempotency_key=fence.idempotency_key,
            fencing_token=fence.token,
        )

    def release(self, fence: TurnFence) -> None:
        release_task_lease(
            runtime_root=self._runtime_root,
            goal_id=fence.goal_id,
            todo_id=fence.todo_id,
            owner=fence.owner,
            idempotency_key=fence.idempotency_key,
            expected_version=fence.version,
        )

    @contextmanager
    def heartbeat(
        self,
        fence: TurnFence,
    ) -> Iterator[Callable[[], TurnFence]]:
        with hold_turn_lease_heartbeat(
            fence,
            renew=self.renew,
            interval_seconds=self._heartbeat_interval_seconds,
        ) as latest:
            yield latest

    @contextmanager
    def effect_guard(self, fence: TurnFence) -> Iterator[None]:
        with hold_task_lease_fence(
            runtime_root=self._runtime_root,
            goal_id=fence.goal_id,
            todo_id=fence.todo_id,
            owner=fence.owner,
            idempotency_key=fence.idempotency_key,
            fencing_token=fence.token,
            operation="turn_effect_guard",
        ):
            yield
