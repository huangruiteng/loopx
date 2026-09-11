"""Transaction capture evidence, receipt-proven drain, and operator readback.

The independent compatibility observation path lives in
local_authority_shadow_observation; this owner only delivers durable entries.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...file_lock import (
    LockAcquireTimeoutError,
    exclusive_cross_runtime_file_lock,
    try_exclusive_file_lock,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...registry import find_registry_goal
from ..effect_runtime import effect_runtime_result
from . import local_authority_shadow_outbox as outbox
from .coordination_state_contract_generated import (
    LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_REQUEST_SCHEMA,
    LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_RESULT_SCHEMA,
    LOCAL_AUTHORITY_SHADOW_READ_REQUEST_SCHEMA,
    LOCAL_AUTHORITY_SHADOW_READ_RESULT_SCHEMA,
    LOCAL_AUTHORITY_SHADOW_TRANSACTION_EVIDENCE_SCHEMA,
)
from .local_authority_shadow_projection import (
    LEASE_PARTITION,
    PARTITIONS,
    TODO_PARTITION,
    canonical_value,
    head_digest,
    partition_digest,
    todo_partition_projection,
)
from .runtime_shadow import resolve_coordination_runtime_shadow_config, capture_todo_archive_dependencies
from .shadow_management import read_shadow_capture_binding


from .local_authority_shadow_observation import local_authority_shadow_summary


def effective_runtime_root(
    registry_path: Path,
    runtime_root_override: str | Path | None,
) -> Path:
    """Resolve the one runtime root every writer hook of a CLI call must share.

    ``--runtime-root`` wins when given; otherwise the registry's
    ``common_runtime_root`` applies, and a relative value resolves against the
    registry's project root rather than the caller's working directory. Todo,
    follow-up, handoff-mode, and task-lease hooks all consume this value so one
    goal never splits into two candidate lineages.
    """

    registry = load_registry(registry_path)
    override = str(runtime_root_override) if runtime_root_override is not None else None
    return resolve_runtime_root(registry, override, registry_path=registry_path)


# ---------------------------------------------------------------------------
# Transaction-bound outbox drain (Stage 2C second half plumbing).
#
# Writers record per-partition outbox entries inside the primary lock (see
# ``local_authority_shadow_outbox``). The drain below runs after that lock is
# released and turns each committed entry into exactly one candidate
# transaction. It is bounded, never blocks a writer, and reports what it left
# behind instead of guessing.
# ---------------------------------------------------------------------------

LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA_V1 = (
    LOCAL_AUTHORITY_SHADOW_TRANSACTION_EVIDENCE_SCHEMA
)
INLINE_DRAIN_MAX_ENTRIES = 16
INLINE_DRAIN_BUDGET_SECONDS = 2.0
INLINE_DRAIN_LOCK_TIMEOUT_SECONDS = 0.25
CLI_DRAIN_LOCK_TIMEOUT_SECONDS = 5.0
RETENTION_PRESSURE_BYTES = 8 * 1024 * 1024
_COMMIT_ENTRY_OUTCOMES = {
    "delivered",
    "replayed",
    "ambiguous_reconciled",
    "ambiguous_unproved",
    "unavailable",
    "failed",
    "protocol_mismatch",
    "conflict_retry_required",
}
_SETTLED_OUTCOMES = {"delivered", "replayed", "ambiguous_reconciled"}
_SEED_WRITE_CLASSES = {"seed", "reseed_after_crash_gap"}
_ENTRY_SOURCE_FIELDS = (
    "kind",
    "previous_bytes_digest",
    "previous_partition_digest",
    "bytes_digest",
    "lease",
    "event_id",
)
_EVIDENCE_V1_OUTCOMES = {
    "delivered",
    "replayed",
    "ambiguous_reconciled",
    "pending",
    "drain_deferred",
    "no_transaction",
    "capture_failed",
    "ambiguous_unproved",
    "unavailable",
    "failed",
    "protocol_mismatch",
    "conflict_retry_required",
}


@dataclass
class DrainResult:
    """Typed outcome of one bounded drain pass."""

    goal_id: str
    outcome: str = "nothing_pending"
    config_enabled: bool = False
    delivered: int = 0
    replayed: int = 0
    reconciled: int = 0
    no_op: int = 0
    reseeded: int = 0
    reclaimed_residue: int = 0
    pending_after: int = 0
    prepared_only_after: int = 0
    in_flight_partitions: list[str] = field(default_factory=list)
    budget_exhausted: bool = False
    stopped_at: dict[str, Any] | None = None
    reason_code: str | None = None
    store_identity: str | None = None
    provider_revision: str | None = None
    last_cursor: str | None = None
    cursor_before: str | None = None
    cursor_after: str | None = None
    head_digest: str | None = None
    candidate_readback_verified: bool | None = None
    entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.outcome in {"drained", "nothing_pending"} and self.stopped_at is None
        )

    @property
    def drained_count(self) -> int:
        return self.delivered + self.replayed + self.reconciled

    def entry_outcome(self, entry_id: str | None) -> dict[str, Any] | None:
        if entry_id is None:
            return None
        for item in self.entries:
            if item.get("entry_id") == entry_id:
                return item
        return None

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        payload["drained_count"] = self.drained_count
        return payload


def todo_partition_projector(
    goal: Mapping[str, Any] | None,
    *,
    state_path: Path,
    rollout_events: list[dict[str, Any]] | None = None,
) -> outbox.TodoPartitionProjector:
    """Production projector: parse active-state text into the todos partition."""

    from ...control_plane.todos.handoff_mode import goal_handoff_mode
    from ..todos.goal_todo_projection import project_goal_todo_items

    goal_record = dict(goal) if isinstance(goal, Mapping) else None
    events = list(rollout_events or [])

    def project(state_text: str) -> dict[str, Any]:
        return todo_partition_projection(
            handoff_mode=goal_handoff_mode(state_text),
            todos=capture_todo_archive_dependencies(project_goal_todo_items(
                goal_record,
                state_text=state_text,
                state_path=state_path,
                rollout_events=events,
            ), state_text),
        )

    return project


def primary_lock_is_free(target: Path) -> bool:
    """Probe a partition's Python primary lock once without waiting."""

    try:
        with try_exclusive_file_lock(
            target, operation="local_authority_shadow_drain_probe"
        ) as held:
            return held is not None
    except OSError:
        return False


@dataclass(frozen=True)
class _GoalSources:
    goal: dict[str, Any] | None
    state_path: Path
    lease_dir: Path


def _goal_sources(
    registry: dict[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
) -> _GoalSources:
    from ...state_refresh import resolve_goal_state

    goal, _project, state_path = resolve_goal_state(
        registry=registry,
        goal_id=goal_id,
        project_override=None,
        state_file_override=None,
    )
    return _GoalSources(
        goal=goal,
        state_path=state_path,
        lease_dir=outbox.lease_directory(runtime_root, goal_id),
    )


def _read_state_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _event_present(sources: _GoalSources, event_id: str) -> bool:
    from ...event_sourced_state import AppendOnlyStateEventStore
    from ..goals.active_state_event_projection import state_event_log_candidates
    from ..goals.path_resolution import resolve_goal_local_path

    if sources.goal is None:
        return False
    for candidate in state_event_log_candidates(
        sources.goal,
        state_path=sources.state_path,
        resolve_goal_local_path=resolve_goal_local_path,
    ):
        if not candidate.exists():
            continue
        for event in AppendOnlyStateEventStore(candidate).load():
            if isinstance(event, dict) and event.get("event_id") == event_id:
                return True
    return False


def _lease_bytes(sources: _GoalSources, todo_id: str) -> bytes | None:
    if not todo_id or "/" in todo_id or "\\" in todo_id or todo_id in {".", ".."}:
        raise outbox.OutboxError("outbox_file_invalid", "invalid lease source identity")
    try:
        return (sources.lease_dir / f"{todo_id}.json").read_bytes()
    except FileNotFoundError:
        return None


@contextmanager
def _primary_lock_if_free(
    partition: str,
    *,
    runtime_root: Path,
    goal_id: str,
    sources: _GoalSources,
) -> Iterator[bool]:
    """Hold the partition's primary lock only if it is free right now."""

    if partition == TODO_PARTITION:
        from .legacy_writer_fence import legacy_coordination_todo_lock_path

        try:
            with (
                exclusive_cross_runtime_file_lock(
                    legacy_coordination_todo_lock_path(
                        runtime_root=runtime_root, goal_id=goal_id
                    ),
                    timeout_seconds=0.0,
                    operation="local_authority_shadow_drain_resolve",
                ),
                exclusive_cross_runtime_file_lock(
                    sources.state_path,
                    timeout_seconds=0.0,
                    operation="local_authority_shadow_drain_resolve",
                ),
            ):
                yield True
        except LockAcquireTimeoutError:
            yield False
        return
    from ..work_items.task_lease import task_lease_lock_path

    target = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
    try:
        with exclusive_cross_runtime_file_lock(
            target,
            timeout_seconds=0.0,
            operation="local_authority_shadow_drain_resolve",
        ):
            yield True
    except LockAcquireTimeoutError:
        yield False


def _entry_projection(
    entry: outbox.OutboxEntry,
    *,
    goal_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Compact projection and digest for a deliverable entry."""

    raw = entry.projection()
    if raw is None:
        return None, None
    if entry.partition == LEASE_PARTITION:
        projection = outbox.compact_lease_projection(raw, goal_id=goal_id)
        return projection, partition_digest(projection)
    projection = dict(canonical_value(raw))
    digest = partition_digest(projection)
    recorded = entry.recorded_partition_digest()
    if recorded is not None and recorded != digest:
        raise outbox.OutboxError(
            "outbox_file_invalid",
            f"entry {entry.entry_id} projection does not match its recorded digest",
        )
    return projection, digest


def _commit_entry_request(
    *,
    runtime_root: Path,
    goal_id: str,
    entry: outbox.OutboxEntry,
    resolution: str,
    projection: dict[str, Any] | None,
    digest: str | None,
) -> dict[str, Any]:
    raw_source = (
        entry.prepared.get("source")
        if isinstance(entry.prepared.get("source"), dict)
        else {}
    )
    writer = (
        entry.prepared.get("writer")
        if isinstance(entry.prepared.get("writer"), dict)
        else {}
    )
    committed_at = entry.committed.get("committed_at") if entry.committed else None
    return {
        "schema_version": LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_REQUEST_SCHEMA,
        "runtime_root": str(runtime_root),
        "goal_id": goal_id,
        "entry": {
            "entry_id": entry.entry_id,
            "partition": entry.partition,
            "seq": entry.seq,
            "writer": {
                "runtime": writer.get("runtime"),
                "write_class": writer.get("write_class"),
                "operation_id": writer.get("operation_id"),
            },
            "source": {key: raw_source.get(key) for key in _ENTRY_SOURCE_FIELDS},
            "source_root_digest": entry.prepared.get("source_root_digest"),
            "capture_lineage_id": entry.prepared.get("capture_lineage_id"),
            "prepared_sha256": outbox.raw_bytes_digest(
                entry.prepared_path.read_bytes()
            ),
            "committed_sha256": outbox.raw_bytes_digest(
                entry.committed_path.read_bytes()
            )
            if entry.committed_path
            else None,
            "prepared_at": entry.prepared.get("prepared_at"),
            "committed_at": committed_at,
            "resolution": resolution,
        },
        "partition_projection": projection,
        "partition_digest": digest,
    }


def _valid_commit_entry_result(result: object, entry: outbox.OutboxEntry) -> bool:
    if not isinstance(result, dict):
        return False
    return (
        result.get("schema_version")
        == LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_RESULT_SCHEMA
        and result.get("outcome") in _COMMIT_ENTRY_OUTCOMES
        and result.get("entry_id") == entry.entry_id
        and result.get("partition") == entry.partition
        and result.get("seq") == entry.seq
        and isinstance(result.get("no_op"), bool)
    )


def read_local_authority_shadow(
    *,
    runtime_root: Path,
    goal_id: str,
    store_kind: str = "runtime_shadow",
    scan_after_cursor: str | None = None,
    scan_limit: int = 0,
    receipt_operation_id: str | None = None,
) -> dict[str, Any]:
    """Read-only candidate view through the TypeScript store boundary."""

    result = effect_runtime_result(
        "coordination.runtime_shadow.outbox_read",
        {
            "schema_version": LOCAL_AUTHORITY_SHADOW_READ_REQUEST_SCHEMA,
            "runtime_root": str(runtime_root),
            "goal_id": goal_id,
            "store_kind": store_kind,
            "scan_after_cursor": scan_after_cursor,
            "scan_limit": scan_limit,
            "receipt_operation_id": receipt_operation_id,
        },
        timeout=15.0,
    )
    if (
        not isinstance(result, dict)
        or result.get("schema_version") != LOCAL_AUTHORITY_SHADOW_READ_RESULT_SCHEMA
        or result.get("goal_id") != goal_id
    ):
        raise RuntimeError("local authority shadow read result is invalid")
    return dict(result)


class _DrainBudget:
    def __init__(self, *, max_entries: int, budget_seconds: float) -> None:
        self._max_entries = max(1, max_entries)
        self._deadline = time.monotonic() + max(0.0, budget_seconds)
        self.consumed = 0

    def exhausted(self) -> bool:
        return self.consumed >= self._max_entries or time.monotonic() >= self._deadline

    @property
    def remaining_entries(self) -> int:
        return max(0, self._max_entries - self.consumed)

    def can_reclaim(self, count: int) -> bool:
        return (
            self.consumed + count <= self._max_entries
            and time.monotonic() < self._deadline
        )


class _PartitionDrainer:
    """Prove under M, release for the TS transaction, then reacquire before cleanup."""

    def __init__(
        self,
        *,
        registry_path: Path,
        runtime_root: Path,
        goal_id: str,
        partition: str,
        sources: _GoalSources,
        result: DrainResult,
        budget: _DrainBudget,
        lock_timeout_seconds: float,
        capture_lineage_id: str,
    ) -> None:
        self._runtime_root = runtime_root
        self._goal_id = goal_id
        self._partition = partition
        self._sources = sources
        self._result = result
        self._budget = budget
        self._lock_timeout = lock_timeout_seconds
        self._directory = outbox.partition_directory(runtime_root, goal_id, partition)
        self._lineage: str | None = capture_lineage_id
        self.last_delivered_digest: str | None = None

    def _lock(self) -> Any:
        return exclusive_cross_runtime_file_lock(
            outbox.drain_lock_target(self._runtime_root, self._goal_id),
            timeout_seconds=self._lock_timeout,
            operation="local_authority_shadow_drain",
        )

    def _binding(self) -> dict[str, Any]:
        view = read_shadow_capture_binding(self._runtime_root, self._goal_id)
        if view["status"] != "active":
            raise outbox.OutboxError(
                str(view.get("reason_code") or "bootstrap_required"),
                "shadow capture has no active binding",
            )
        binding = dict(view["binding"])
        lineage = str(binding["capture_lineage_id"])
        if self._lineage is not None and self._lineage != lineage:
            raise outbox.OutboxError(
                "stale_generation", "drain belongs to an earlier lineage"
            )
        self._lineage = lineage
        return binding

    def _proof(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        binding = self._binding()
        # Parse before consulting the candidate: malformed cursor bytes are evidence.
        outbox.read_cursor(self._directory)
        view = read_local_authority_shadow(
            runtime_root=self._runtime_root,
            goal_id=self._goal_id,
            scan_limit=10_000,
        )
        proof = view.get("proof")
        if view.get("status") != "loaded" or not isinstance(proof, dict):
            raise outbox.OutboxError(
                str(view.get("reason_code") or "outbox_receipt_unproved"),
                "candidate history is not proved",
            )
        transactions = proof.get("transactions")
        if (
            proof.get("capture_lineage_id") != self._lineage
            or view.get("store_identity") != binding["store_identity"]
            or not isinstance(transactions, list)
            or not transactions
            or not all(isinstance(tx, dict) for tx in transactions)
            or transactions[-1].get("cursor") != view.get("cursor")
            or transactions[-1].get("provider_revision")
            != view.get("provider_revision")
        ):
            raise outbox.OutboxError(
                "outbox_receipt_unproved", "incomplete or foreign history proof"
            )
        return view, transactions

    @staticmethod
    def _receipt(transaction: dict[str, Any]) -> dict[str, Any] | None:
        receipts = transaction.get("receipts")
        if (
            isinstance(receipts, list)
            and len(receipts) == 1
            and isinstance(receipts[0], dict)
        ):
            return receipts[0]
        return None

    def _partition_history(
        self, transactions: list[dict[str, Any]]
    ) -> dict[int, dict[str, Any]]:
        history: dict[int, dict[str, Any]] = {}
        for transaction in transactions:
            receipt = self._receipt(transaction)
            if receipt is None or receipt.get("partition") != self._partition:
                continue
            seq = receipt.get("seq")
            if (
                type(seq) is not int
                or seq != len(history) + 1
                or receipt.get("capture_lineage_id") != self._lineage
                or receipt.get("source_root_digest")
                != outbox.runtime_root_digest(self._runtime_root)
                or receipt.get("entry_id") != transaction.get("operation_id")
            ):
                raise outbox.OutboxError(
                    "outbox_receipt_unproved", "partition history is not continuous"
                )
            history[seq] = transaction
        return history

    def _check_file(
        self, entry: outbox.OutboxEntry, transaction: dict[str, Any]
    ) -> list[tuple[Path, str]]:
        receipt = self._receipt(transaction)
        if (
            receipt is None
            or receipt.get("entry_id") != entry.entry_id
            or receipt.get("seq") != entry.seq
            or receipt.get("partition") != entry.partition
            or receipt.get("capture_lineage_id") != self._lineage
        ):
            raise outbox.OutboxError(
                "outbox_receipt_mismatch", "entry does not match its receipt"
            )
        files: list[tuple[Path, str]] = []
        for path, key in (
            (entry.prepared_path, "prepared_sha256"),
            (entry.committed_path, "committed_sha256"),
        ):
            if path is None or not path.exists():
                continue
            expected = receipt.get(key)
            if (
                not isinstance(expected, str)
                or outbox.raw_bytes_digest(path.read_bytes()) != expected
            ):
                raise outbox.OutboxError(
                    "outbox_receipt_mismatch", "outbox bytes differ from the receipt"
                )
            files.append((path, expected))
        return files

    def _reconcile(
        self,
        transactions: list[dict[str, Any]],
        *,
        delivered_entry_id: str | None = None,
    ) -> list[outbox.OutboxEntry] | None:
        history = self._partition_history(transactions)
        cursor = outbox.read_cursor(self._directory)
        if cursor is not None:
            anchor = history.get(cursor["last_seq"])
            if (
                anchor is None
                or anchor.get("operation_id") != cursor["last_entry_id"]
                or anchor.get("cursor") != cursor["last_cursor"]
                or anchor.get("provider_revision") != cursor["last_provider_revision"]
                or self._cursor_digest(anchor) != cursor["last_partition_digest"]
            ):
                raise outbox.OutboxError(
                    "outbox_cursor_unproved", "cursor has no exact history anchor"
                )
        entries = outbox.list_entries(self._directory, allow_committed_only=True)
        verified: dict[str, list[tuple[Path, str]]] = {}
        for entry in entries:
            transaction = history.get(entry.seq)
            if transaction is not None:
                verified[entry.entry_id] = self._check_file(entry, transaction)
            elif not entry.prepared:
                raise outbox.OutboxError(
                    "outbox_file_invalid", "unproved committed-only residue"
                )
            elif entry.prepared.get("capture_lineage_id") != self._lineage:
                raise outbox.OutboxError(
                    "stale_generation", "outbox entry belongs to another lineage"
                )
        recovered = [
            entry
            for entry in entries
            if entry.seq in history and entry.entry_id != delivered_entry_id
        ]
        # Prove every residue first, then reclaim a bounded prefix. Repeated
        # small-budget recovery must make progress without concealing a bad tail.
        if not self._budget.can_reclaim(0):
            self._result.budget_exhausted = True
            return None
        if len(recovered) > self._budget.remaining_entries:
            self._result.budget_exhausted = True
            recovered = recovered[: self._budget.remaining_entries]
        selected_ids = {entry.entry_id for entry in recovered}
        if delivered_entry_id is not None:
            selected_ids.add(delivered_entry_id)
        files = [
            item
            for entry_id, batch in verified.items()
            if entry_id in selected_ids
            for item in batch
        ]
        # No deletion or cursor rewrite until the complete batch has been checked.
        if history:
            last = history[len(history)]
            with _primary_lock_if_free(
                self._partition,
                runtime_root=self._runtime_root,
                goal_id=self._goal_id,
                sources=self._sources,
            ) as held:
                if not held:
                    raise outbox.OutboxError(
                        "primary_writer_busy", "primary writer is in flight"
                    )
                self._binding()
                if (
                    outbox.read_cursor(self._directory) != cursor
                    or outbox.list_entries(self._directory, allow_committed_only=True)
                    != entries
                ):
                    raise outbox.OutboxError(
                        "outbox_file_changed", "outbox changed during proof"
                    )
                digest = self._cursor_digest(last)
                if cursor is None or cursor["last_seq"] != len(history):
                    outbox.write_cursor(
                        self._directory,
                        partition=self._partition,
                        last_seq=len(history),
                        last_entry_id=str(last["operation_id"]),
                        last_partition_digest=digest,
                        last_cursor=str(last["cursor"]),
                        last_provider_revision=str(last["provider_revision"]),
                    )
                self._result.reclaimed_residue += outbox.reclaim_verified_files(files)
                for entry in recovered:
                    transaction = history[entry.seq]
                    receipt = self._receipt(transaction)
                    assert receipt is not None
                    self._result.entries.append(
                        {
                            "entry_id": entry.entry_id,
                            "partition": entry.partition,
                            "seq": entry.seq,
                            "resolution": receipt["resolution"],
                            "outcome": "replayed",
                            "reason_code": "verified_receipt_recovery",
                            "cursor": transaction["cursor"],
                            "provider_revision": transaction["provider_revision"],
                            "partition_digest": receipt["partition_digest"],
                        }
                    )
                    self._result.replayed += 1
                    self._result.no_op += int(receipt["no_op"])
                    self._budget.consumed += 1
        return [entry for entry in entries if entry.seq not in history]

    def _cursor_digest(self, transaction: dict[str, Any]) -> str | None:
        # The native history validator owns this applied-mutation marker.
        # Settled no-ops advance position but never synthesize a baseline digest.
        marker = transaction["projection"]["partitions"][self._partition]
        return None if marker is None else marker["partition_digest"]

    def _resolve(
        self, entry: outbox.OutboxEntry, pending: list[outbox.OutboxEntry]
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        if entry.is_committed:
            projection, digest = _entry_projection(entry, goal_id=self._goal_id)
            if projection is None:
                raise outbox.OutboxError(
                    "outbox_file_invalid", "committed entry has no projection"
                )
            return "committed", projection, digest
        with _primary_lock_if_free(
            self._partition,
            runtime_root=self._runtime_root,
            goal_id=self._goal_id,
            sources=self._sources,
        ) as held:
            if not held:
                raise outbox.OutboxError(
                    "primary_writer_busy", "prepared writer is in flight"
                )
            # Current A cannot prove an earlier A->B was abandoned after B->A.
            if any(other.seq > entry.seq for other in pending):
                raise outbox.OutboxError(
                    "outbox_source_unproved",
                    "later writes make source recovery ambiguous",
                )
            resolution = outbox.resolve_prepared_only_entry(
                entry,
                markdown_text_reader=lambda: _read_state_text(self._sources.state_path),
                lease_bytes_reader=lambda todo_id: _lease_bytes(self._sources, todo_id),
                event_presence_reader=lambda event_id: _event_present(
                    self._sources, event_id
                ),
            )
            if resolution == "abandoned":
                return resolution, None, None
            if resolution != "committed":
                raise outbox.OutboxError(
                    "outbox_source_unproved", "prepared source cannot be proved"
                )
            projection, digest = _entry_projection(entry, goal_id=self._goal_id)
            if projection is None:
                raise outbox.OutboxError(
                    "outbox_source_unproved", "prepared source has no projection"
                )
            return "committed_proven_by_readback", projection, digest

    def _record_view(self, view: dict[str, Any]) -> None:
        self._result.candidate_readback_verified = True
        self._result.store_identity = view.get("store_identity")
        self._result.provider_revision = view.get("provider_revision")
        self._result.last_cursor = view.get("cursor")
        self._result.cursor_after = view.get("cursor")
        self._result.head_digest = view.get("head_digest")

    def run(self) -> None:
        while not self._budget.exhausted():
            with self._lock():
                view, transactions = self._proof()
                if self._result.cursor_before is None:
                    self._result.cursor_before = view.get("cursor")
                self._record_view(view)
                pending = self._reconcile(transactions)
                if not pending:
                    return
                if self._budget.exhausted():
                    self._result.budget_exhausted = True
                    return
                entry = pending[0]
                resolution, projection, digest = self._resolve(entry, pending)
                if entry.seq != len(self._partition_history(transactions)) + 1:
                    raise outbox.OutboxError(
                        "outbox_sequence_gap", "pending sequence is not continuous"
                    )
                request = _commit_entry_request(
                    runtime_root=self._runtime_root,
                    goal_id=self._goal_id,
                    entry=entry,
                    resolution=resolution,
                    projection=projection,
                    digest=digest,
                )
            # TS owns M for every public commit, including retries. Never re-enter M across RPC.
            raw = effect_runtime_result(
                "coordination.runtime_shadow.commit_entry", request, timeout=15.0
            )
            self._budget.consumed += 1
            if not _valid_commit_entry_result(raw, entry):
                raise outbox.OutboxError(
                    "shadow_commit_entry_result_invalid", "invalid commit result"
                )
            if raw["outcome"] not in _SETTLED_OUTCOMES:
                self._result.stopped_at = {
                    "partition": entry.partition,
                    "seq": entry.seq,
                    "entry_id": entry.entry_id,
                    "outcome": raw["outcome"],
                    "reason_code": raw.get("reason_code"),
                }
                return
            with self._lock():
                view, transactions = self._proof()
                history = self._partition_history(transactions)
                transaction = history.get(entry.seq)
                if (
                    transaction is None
                    or transaction.get("operation_id") != entry.entry_id
                    or transaction.get("cursor") != raw.get("cursor")
                    or transaction.get("provider_revision")
                    != raw.get("provider_revision")
                    or view.get("store_identity") != raw.get("store_identity")
                    or self._receipt(transaction).get("no_op") != raw.get("no_op")
                    or self._receipt(transaction).get("partition_digest") != digest
                ):
                    raise outbox.OutboxError(
                        "shadow_commit_entry_result_invalid",
                        "ACK differs from exact receipt",
                    )
                # Preserve verified commit evidence even if local cleanup fails.
                self._record_view(view)
                self._reconcile(transactions, delivered_entry_id=entry.entry_id)
            summary = {
                "entry_id": entry.entry_id,
                "partition": entry.partition,
                "seq": entry.seq,
                "resolution": resolution,
                "outcome": raw["outcome"],
                "reason_code": raw.get("reason_code"),
                "cursor": raw.get("cursor"),
                "provider_revision": raw.get("provider_revision"),
                "partition_digest": digest,
            }
            self._result.entries.append(summary)
            if raw["outcome"] == "delivered":
                self._result.delivered += 1
            elif raw["outcome"] == "replayed":
                self._result.replayed += 1
            else:
                self._result.reconciled += 1
            if raw["no_op"]:
                self._result.no_op += 1
            elif digest is not None:
                self.last_delivered_digest = digest
        if outbox.list_entries(self._directory, allow_committed_only=True):
            self._result.budget_exhausted = True


def _drain_prelude(
    result: DrainResult,
    *,
    registry_path: Path,
    runtime_root: Path | None,
    goal_id: str,
) -> tuple[dict[str, Any], Path] | None:
    """Validate the goal id and resolve the registry and root; typed failure on error."""

    if not goal_id or goal_id in {".", ".."} or "/" in goal_id or "\\" in goal_id:
        result.outcome = "failed"
        result.reason_code = "invalid_shadow_goal_id"
        return None
    try:
        registry = load_registry(registry_path)
        result.config_enabled = (
            resolve_coordination_runtime_shadow_config(
                find_registry_goal(registry, goal_id)
            ).enabled
            or local_authority_shadow_summary(find_registry_goal(registry, goal_id) or {})["enabled"] is True
        )
        resolved = (
            runtime_root
            if runtime_root is not None
            else resolve_runtime_root(registry, None, registry_path=registry_path)
        )
    except Exception:
        result.outcome = "failed"
        result.reason_code = "invalid_shadow_config"
        return None
    return registry, resolved


def _drain_partitions(
    result: DrainResult,
    *,
    registry: dict[str, Any],
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    max_entries: int,
    budget_seconds: float,
    lock_timeout_seconds: float,
) -> None:
    """Drain partitions through the shared management lock and TS commit owner."""

    sources = _goal_sources(registry, runtime_root=runtime_root, goal_id=goal_id)
    binding_view = read_shadow_capture_binding(runtime_root, goal_id)
    if binding_view["status"] != "active":
        raise outbox.OutboxError(
            str(binding_view.get("reason_code") or "bootstrap_required"),
            "drain requires an active capture lineage",
        )
    capture_lineage_id = str(binding_view["binding"]["capture_lineage_id"])
    budget = _DrainBudget(max_entries=max_entries, budget_seconds=budget_seconds)
    for partition in PARTITIONS:
        if result.stopped_at is not None:
            break
        drainer = _PartitionDrainer(
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id=goal_id,
            partition=partition,
            sources=sources,
            result=result,
            budget=budget,
            lock_timeout_seconds=lock_timeout_seconds,
            capture_lineage_id=capture_lineage_id,
        )
        drainer.run()


def _settle_drain_outcome(result: DrainResult) -> None:
    if result.stopped_at is not None:
        result.outcome = "stopped"
        result.reason_code = str(
            result.stopped_at.get("reason_code") or result.stopped_at["outcome"]
        )
    else:
        result.outcome = (
            "drained"
            if result.drained_count or result.budget_exhausted
            else "nothing_pending"
        )


def _count_backlog(result: DrainResult, runtime_root: Path, goal_id: str) -> None:
    summary_after = outbox.outbox_summary(runtime_root, goal_id)
    result.pending_after = sum(
        int(item["committed_pending"]) for item in summary_after.values()
    )
    result.prepared_only_after = sum(
        int(item["prepared_only"]) for item in summary_after.values()
    )


def drain_local_authority_shadow_outbox(
    *,
    registry_path: Path,
    runtime_root: Path | None,
    goal_id: str,
    max_entries: int = INLINE_DRAIN_MAX_ENTRIES,
    budget_seconds: float = INLINE_DRAIN_BUDGET_SECONDS,
    lock_timeout_seconds: float = INLINE_DRAIN_LOCK_TIMEOUT_SECONDS,
) -> DrainResult:
    """Deliver pending outbox entries to the candidate store, one transaction each.

    The drain lock is per goal. A held lock means another drainer is already
    at work, so the caller's write stays ``pending`` instead of waiting on it.
    """

    result = DrainResult(goal_id=goal_id)
    prelude = _drain_prelude(
        result, registry_path=registry_path, runtime_root=runtime_root, goal_id=goal_id
    )
    if prelude is None:
        return result
    registry, resolved_root = prelude
    binding = read_shadow_capture_binding(resolved_root, goal_id)
    if binding["status"] != "active":
        runtime_enabled = resolve_coordination_runtime_shadow_config(find_registry_goal(registry, goal_id)).enabled
        requires_bootstrap = (runtime_enabled or binding["status"] in {"inactive", "hold"}
                              or outbox.outbox_root(resolved_root, goal_id).exists())
        result.outcome = "stopped" if requires_bootstrap else "nothing_pending"
        result.reason_code = (
            str(binding.get("reason_code") or "bootstrap_required")
            if result.outcome == "stopped"
            else None
        )
        return result
    try:
        _drain_partitions(
            result,
            registry=registry,
            registry_path=registry_path,
            runtime_root=resolved_root,
            goal_id=goal_id,
            max_entries=max_entries,
            budget_seconds=budget_seconds,
            lock_timeout_seconds=lock_timeout_seconds,
        )
    except LockAcquireTimeoutError:
        result.outcome = "drain_deferred"
        result.reason_code = "drain_lock_busy"
    except outbox.OutboxError as error:
        result.outcome = "stopped"
        result.reason_code = error.reason_code
    except Exception:
        result.outcome = "stopped"
        result.reason_code = "shadow_drain_failed"
    else:
        _settle_drain_outcome(result)
    try:
        _count_backlog(result, resolved_root, goal_id)
    except Exception:
        result.outcome = "stopped"
        result.reason_code = result.reason_code or "outbox_status_unavailable"
    return result


class _CandidateMissing(Exception):
    """The candidate store directory does not exist yet."""


def _store_bytes(runtime_root: Path, goal_id: str, *, legacy_observation: bool) -> int:
    directory = (
        runtime_root / "authority-shadow" / "file" / goal_id
        if legacy_observation
        else runtime_root / "authority-shadow" / "file-v0"
    )
    if not directory.is_dir():
        return 0
    return sum(path.stat().st_size for path in directory.iterdir() if path.is_file())


def local_authority_shadow_status(
    *,
    registry_path: Path,
    runtime_root: Path | None,
    goal_id: str,
) -> dict[str, Any]:
    """Operator readback: configuration, outbox backlog, and candidate head facts."""

    registry = load_registry(registry_path)
    goal = find_registry_goal(registry, goal_id)
    if not isinstance(goal, dict):
        raise ValueError(f"goal {goal_id!r} is not registered")
    if runtime_root is None:
        runtime_root = resolve_runtime_root(registry, None, registry_path=registry_path)
    config = local_authority_shadow_summary(goal)
    runtime_config = resolve_coordination_runtime_shadow_config(goal)
    management = read_shadow_capture_binding(runtime_root, goal_id)
    legacy_observation = (
        config["enabled"] is True
        and not runtime_config.enabled
        and management["status"] == "missing"
    )
    backlog = outbox.outbox_summary(runtime_root, goal_id)
    candidate: dict[str, Any]
    try:
        directory = (
            runtime_root / "authority-shadow" / "file" / goal_id
            if legacy_observation
            else runtime_root / "authority-shadow" / "file-v0"
        )
        if not directory.is_dir() or not any(directory.glob("authority-store-*.json")):
            # Reading through the store boundary would mint a store identity;
            # a status probe must not create candidate lineage.
            raise _CandidateMissing
        view = read_local_authority_shadow(
            runtime_root=runtime_root,
            goal_id=goal_id,
            store_kind=(
                "legacy_observation" if legacy_observation else "runtime_shadow"
            ),
        )
        head = view.get("head") if isinstance(view.get("head"), dict) else None
        candidate = {
            "status": view.get("status"),
            "reason_code": view.get("reason_code"),
            "store_identity": view.get("store_identity"),
            "provider_revision": view.get("provider_revision"),
            "cursor": view.get("cursor"),
            "head_digest": view.get("head_digest"),
            "head_schema_version": head.get("schema_version") if head else None,
            "partitions": view.get("partitions"),
            "codec_agreement": (head_digest(head) == view.get("head_digest"))
            if head
            else None,
        }
    except _CandidateMissing:
        candidate = {
            "status": "missing",
            "reason_code": None,
            "store_identity": None,
            "provider_revision": None,
            "cursor": None,
            "head_digest": None,
            "head_schema_version": None,
            "partitions": None,
            "codec_agreement": None,
        }
    except Exception:
        candidate = {
            "status": "unavailable",
            "reason_code": "shadow_read_failed",
            "store_identity": None,
            "provider_revision": None,
            "cursor": None,
            "head_digest": None,
            "head_schema_version": None,
            "partitions": None,
            "codec_agreement": None,
        }
    try:
        store_bytes = _store_bytes(
            runtime_root, goal_id, legacy_observation=legacy_observation
        )
        storage_error = None
    except OSError:
        store_bytes = None
        storage_error = "shadow_store_unavailable"
    return {
        "ok": all(item["invalid"] is None for item in backlog.values())
        and storage_error is None
        and management["status"] != "hold",
        "action": "status",
        "goal_id": goal_id,
        "config": config,
        "runtime_config": asdict(runtime_config),
        "management": management,
        "storage_error": storage_error,
        "runtime_root_digest": outbox.runtime_root_digest(runtime_root),
        "outbox": backlog,
        "candidate": candidate,
        "store_bytes": store_bytes,
        "retention_pressure": store_bytes > RETENTION_PRESSURE_BYTES
        if store_bytes is not None
        else None,
    }


def capture_evidence(
    *,
    goal_id: str,
    capture: outbox.CaptureOutcome,
    drain: DrainResult | None,
) -> dict[str, Any]:
    """Evidence v1 attached to a writer payload: capture facts plus drain facts.

    Every flag here is a measured fact of this write. ``source_candidate_compared``
    and ``parity_verdict`` stay negative until the verify step exists.
    """

    if capture.failure is not None:
        outcome = "capture_failed"
        reason_code: str | None = str(capture.failure.get("reason_code"))
    elif capture.entry_id is None:
        outcome = "no_transaction"
        reason_code = capture.skipped_reason
    elif drain is None or drain.outcome == "drain_deferred":
        outcome = "drain_deferred" if drain is not None else "pending"
        reason_code = drain.reason_code if drain is not None else None
    else:
        settled = drain.entry_outcome(capture.entry_id)
        if settled is None:
            outcome = "pending"
            reason_code = drain.reason_code
        else:
            outcome = str(settled["outcome"])
            reason_code = settled.get("reason_code")
    return {
        "schema_version": LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA_V1,
        "outcome": outcome,
        "reason_code": reason_code,
        "goal_id": goal_id,
        "entry": {
            "entry_id": capture.entry_id,
            "partition": capture.partition,
            "seq": capture.seq,
            "partition_digest": capture.partition_digest,
            "source_bytes_digest": capture.source_bytes_digest,
        },
        "drain": None
        if drain is None
        else {
            "outcome": drain.outcome,
            "delivered": drain.delivered,
            "replayed": drain.replayed,
            "reclaimed_residue": drain.reclaimed_residue,
            "pending_after": drain.pending_after,
            "prepared_only_after": drain.prepared_only_after,
            "stopped_at": drain.stopped_at,
            "last_cursor": drain.last_cursor,
            "provider_revision": drain.provider_revision,
            "candidate_readback_verified": drain.candidate_readback_verified,
        },
        "capture_kind": "source_transaction_outbox",
        # Both flags are measured facts of this write: they are true only when
        # a prepared/committed entry was actually recorded for it. A disabled
        # or unchanged capture recorded nothing and claims nothing.
        "source_transaction_correlated": capture.recorded,
        "durable_source_outbox": capture.recorded,
        "source_candidate_compared": False,
        "parity_verdict": "not_evaluated",
        "primary_authority": "legacy_local",
        "candidate_provider": "file",
        "candidate_read_for_decision": False,
        "provider_to_local_writes": False,
        "primary_writeback_preserved": True,
        "store_identity": drain.store_identity if drain is not None else None,
    }


def valid_evidence_v1(result: object, *, goal_id: str) -> bool:
    """Closed-shape check for evidence v1 as attached to writer payloads."""

    if not isinstance(result, dict):
        return False
    entry = result.get("entry")
    return (
        result.get("schema_version") == LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA_V1
        and result.get("outcome") in _EVIDENCE_V1_OUTCOMES
        and result.get("goal_id") == goal_id
        and isinstance(entry, dict)
        and result.get("capture_kind") == "source_transaction_outbox"
        and isinstance(result.get("source_transaction_correlated"), bool)
        and isinstance(result.get("durable_source_outbox"), bool)
        and result.get("source_candidate_compared") is False
        and result.get("parity_verdict") == "not_evaluated"
        and result.get("primary_authority") == "legacy_local"
        and result.get("candidate_provider") == "file"
        and result.get("candidate_read_for_decision") is False
        and result.get("provider_to_local_writes") is False
        and result.get("primary_writeback_preserved") is True
        and (
            result.get("reason_code") is None
            or isinstance(result.get("reason_code"), str)
        )
    )


__all__ = [
    "effective_runtime_root",
    "CLI_DRAIN_LOCK_TIMEOUT_SECONDS",
    "INLINE_DRAIN_BUDGET_SECONDS",
    "INLINE_DRAIN_LOCK_TIMEOUT_SECONDS",
    "INLINE_DRAIN_MAX_ENTRIES",
    "LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_REQUEST_SCHEMA",
    "LOCAL_AUTHORITY_SHADOW_COMMIT_ENTRY_RESULT_SCHEMA",
    "LOCAL_AUTHORITY_SHADOW_EVIDENCE_SCHEMA_V1",
    "LOCAL_AUTHORITY_SHADOW_READ_REQUEST_SCHEMA",
    "LOCAL_AUTHORITY_SHADOW_READ_RESULT_SCHEMA",
    "RETENTION_PRESSURE_BYTES",
    "DrainResult",
    "capture_evidence",
    "primary_lock_is_free",
    "todo_partition_projector",
    "drain_local_authority_shadow_outbox",
    "local_authority_shadow_status",
    "read_local_authority_shadow",
    "valid_evidence_v1",
]
