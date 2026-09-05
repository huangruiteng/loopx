"""Bounded, crash-isolated observer intake and its stats record.

The intake is the provider-neutral reference for the L1 observer runtime
contract: a bounded buffer whose overflow is counted rather than blocking, an
``observe`` call that never raises into the caller, and a stats record that
carries the receipt inputs (buffer bound, drops, failures, outbound endpoints)
next to the envelopes it accepted. The DSH TypeScript observer implements the
same shape and writes the same stats record.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .envelope import (
    CAPABILITY_ID,
    IDENTITY_TOKEN_PATTERN,
    OBSERVER_STATS_SCHEMA_VERSION,
    ClockSource,
    EnvelopeRejection,
    ObserverEnvelope,
    ObserverEnvelopeError,
    normalize_observer_envelope,
)

DEFAULT_BUFFER_BOUND = 256
MAX_BUFFER_BOUND = 65_536
_ENDPOINT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,200}$")

RUN_IDENTITY_FIELDS = frozenset(
    {
        "worker_id",
        "model_id",
        "task_id",
        "environment_id",
        "tools_id",
        "budget_id",
        "adapter_revision",
        "observer_revision",
    }
)

STATS_FIELDS = frozenset(
    {
        "schema_version",
        "capability_id",
        "provider_id",
        "observer_id",
        "goal_id",
        "run_identity",
        "event_sources",
        "source_fields_consumed",
        "emitted_at",
        "observed_event_count",
        "accepted_event_count",
        "rejected_event_count",
        "rejected_by_reason",
        "buffer_bound",
        "backpressure_drop_count",
        "observer_failure_count",
        "peak_buffered_event_count",
        "flush_attempt_count",
        "outbound_endpoints",
        "observation_entered_worker_context",
        "observation_entered_scheduler_inputs",
        "clock_source",
    }
)


@dataclass(frozen=True)
class ObserverRunIdentity:
    worker_id: str
    model_id: str
    task_id: str
    environment_id: str
    tools_id: str
    budget_id: str
    adapter_revision: str
    observer_revision: str

    def as_dict(self) -> dict[str, str]:
        return {
            field_name: str(getattr(self, field_name))
            for field_name in RUN_IDENTITY_FIELDS
        }


@dataclass(frozen=True)
class ObserverStats:
    provider_id: str
    observer_id: str
    goal_id: str
    run_identity: ObserverRunIdentity
    event_sources: tuple[str, ...]
    source_fields_consumed: tuple[str, ...]
    emitted_at: str
    observed_event_count: int
    accepted_event_count: int
    rejected_event_count: int
    rejected_by_reason: Mapping[str, int]
    buffer_bound: int
    backpressure_drop_count: int
    observer_failure_count: int
    peak_buffered_event_count: int
    flush_attempt_count: int
    outbound_endpoints: tuple[str, ...]
    observation_entered_worker_context: bool
    observation_entered_scheduler_inputs: bool
    clock_source: ClockSource

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OBSERVER_STATS_SCHEMA_VERSION,
            "capability_id": CAPABILITY_ID,
            "provider_id": self.provider_id,
            "observer_id": self.observer_id,
            "goal_id": self.goal_id,
            "run_identity": self.run_identity.as_dict(),
            "event_sources": list(self.event_sources),
            "source_fields_consumed": list(self.source_fields_consumed),
            "emitted_at": self.emitted_at,
            "observed_event_count": self.observed_event_count,
            "accepted_event_count": self.accepted_event_count,
            "rejected_event_count": self.rejected_event_count,
            "rejected_by_reason": dict(self.rejected_by_reason),
            "buffer_bound": self.buffer_bound,
            "backpressure_drop_count": self.backpressure_drop_count,
            "observer_failure_count": self.observer_failure_count,
            "peak_buffered_event_count": self.peak_buffered_event_count,
            "flush_attempt_count": self.flush_attempt_count,
            "outbound_endpoints": list(self.outbound_endpoints),
            "observation_entered_worker_context": self.observation_entered_worker_context,
            "observation_entered_scheduler_inputs": self.observation_entered_scheduler_inputs,
            "clock_source": self.clock_source.value,
        }


def _count(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"observer stats {name} must be a non-negative integer")
    return value


def _identity_token(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not IDENTITY_TOKEN_PATTERN.match(value):
        raise ValueError(f"observer stats {name} must be an identity token")
    return value


def _token_list(value: Any, *, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(item, str) or not _ENDPOINT_PATTERN.match(item)
            for item in value
        )
    ):
        raise ValueError(
            f"observer stats {name} must be a non-empty list of compact tokens"
        )
    if len(set(value)) != len(value):
        raise ValueError(f"observer stats {name} must not contain duplicates")
    return tuple(value)


@dataclass(frozen=True)
class _ValidatedStatsCounts:
    observed: int
    accepted: int
    rejected: int
    dropped: int
    buffer_bound: int
    peak_buffered: int


def _stats_identity(record: Mapping[str, Any]) -> tuple[str, str, str]:
    if not isinstance(record, Mapping):
        raise ValueError("observer stats must be an object")
    unknown = sorted(str(key) for key in record if str(key) not in STATS_FIELDS)
    if unknown:
        raise ValueError(f"observer stats carry unsupported fields: {unknown}")
    if record.get("schema_version") != OBSERVER_STATS_SCHEMA_VERSION:
        raise ValueError(
            f"observer stats schema must be {OBSERVER_STATS_SCHEMA_VERSION}"
        )
    if record.get("capability_id") != CAPABILITY_ID:
        raise ValueError(f"observer stats capability must be {CAPABILITY_ID}")
    return (
        _identity_token(record.get("provider_id"), name="provider_id"),
        _identity_token(record.get("observer_id"), name="observer_id"),
        _identity_token(record.get("goal_id"), name="goal_id"),
    )


def _stats_emitted_at(record: Mapping[str, Any]) -> str:
    emitted_at = record.get("emitted_at")
    if not isinstance(emitted_at, str):
        raise ValueError(
            "observer stats emitted_at must be timezone-aware ISO-8601 text"
        )
    try:
        parsed_emitted_at = datetime.fromisoformat(emitted_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "observer stats emitted_at must be timezone-aware ISO-8601 text"
        ) from exc
    if parsed_emitted_at.tzinfo is None:
        raise ValueError("observer stats emitted_at must carry a timezone")
    return emitted_at


def _stats_rejection_counts(record: Mapping[str, Any]) -> dict[str, int]:
    reasons = record.get("rejected_by_reason") or {}
    if not isinstance(reasons, Mapping):
        raise ValueError("observer stats rejected_by_reason must be an object")
    return {
        EnvelopeRejection(str(key)).value: _count(
            value, name=f"rejected_by_reason.{key}"
        )
        for key, value in reasons.items()
    }


def _stats_endpoints(record: Mapping[str, Any]) -> tuple[str, ...]:
    endpoints = record.get("outbound_endpoints")
    if not isinstance(endpoints, list) or any(
        not isinstance(item, str) or not _ENDPOINT_PATTERN.match(item)
        for item in endpoints
    ):
        raise ValueError(
            "observer stats outbound_endpoints must be a list of endpoint ids"
        )
    return tuple(endpoints)


def _stats_boolean(record: Mapping[str, Any], name: str) -> bool:
    value = record.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"observer stats {name} must be boolean")
    return value


def _stats_counts(
    record: Mapping[str, Any],
    rejected_by_reason: Mapping[str, int],
) -> _ValidatedStatsCounts:
    buffer_bound = _count(record.get("buffer_bound"), name="buffer_bound")
    if not 1 <= buffer_bound <= MAX_BUFFER_BOUND:
        raise ValueError(
            f"observer stats buffer_bound must be within 1..{MAX_BUFFER_BOUND}"
        )
    counts = _ValidatedStatsCounts(
        observed=_count(
            record.get("observed_event_count"), name="observed_event_count"
        ),
        accepted=_count(
            record.get("accepted_event_count"), name="accepted_event_count"
        ),
        rejected=_count(
            record.get("rejected_event_count"), name="rejected_event_count"
        ),
        dropped=_count(
            record.get("backpressure_drop_count"), name="backpressure_drop_count"
        ),
        buffer_bound=buffer_bound,
        peak_buffered=_count(
            record.get("peak_buffered_event_count"), name="peak_buffered_event_count"
        ),
    )
    if counts.rejected != sum(rejected_by_reason.values()):
        raise ValueError(
            "observer stats rejected_event_count must equal rejected_by_reason"
        )
    if counts.observed != counts.accepted + counts.rejected + counts.dropped:
        raise ValueError(
            "observer stats observed_event_count must equal accepted + rejected + dropped"
        )
    if counts.peak_buffered > counts.buffer_bound:
        raise ValueError(
            "observer stats peak_buffered_event_count exceeds buffer_bound"
        )
    return counts


def normalize_observer_run_identity(value: Any) -> ObserverRunIdentity:
    if not isinstance(value, Mapping) or set(value) != RUN_IDENTITY_FIELDS:
        raise ValueError(
            "observer stats run_identity must contain exactly the pinned identity fields"
        )
    return ObserverRunIdentity(
        **{
            field_name: _identity_token(
                value.get(field_name), name=f"run_identity.{field_name}"
            )
            for field_name in RUN_IDENTITY_FIELDS
        }
    )


def normalize_observer_stats(record: Mapping[str, Any]) -> ObserverStats:
    """Validate one stats record written by any observer implementation."""

    provider_id, observer_id, goal_id = _stats_identity(record)
    emitted_at = _stats_emitted_at(record)
    normalized_reasons = _stats_rejection_counts(record)
    endpoints = _stats_endpoints(record)
    entered = _stats_boolean(record, "observation_entered_worker_context")
    entered_scheduler = _stats_boolean(record, "observation_entered_scheduler_inputs")
    counts = _stats_counts(record, normalized_reasons)
    return ObserverStats(
        provider_id=provider_id,
        observer_id=observer_id,
        goal_id=goal_id,
        run_identity=normalize_observer_run_identity(record.get("run_identity")),
        event_sources=_token_list(record.get("event_sources"), name="event_sources"),
        source_fields_consumed=_token_list(
            record.get("source_fields_consumed"), name="source_fields_consumed"
        ),
        emitted_at=emitted_at,
        observed_event_count=counts.observed,
        accepted_event_count=counts.accepted,
        rejected_event_count=counts.rejected,
        rejected_by_reason=normalized_reasons,
        buffer_bound=counts.buffer_bound,
        backpressure_drop_count=counts.dropped,
        observer_failure_count=_count(
            record.get("observer_failure_count"), name="observer_failure_count"
        ),
        peak_buffered_event_count=counts.peak_buffered,
        flush_attempt_count=_count(
            record.get("flush_attempt_count"), name="flush_attempt_count"
        ),
        outbound_endpoints=tuple(endpoints),
        observation_entered_worker_context=entered,
        observation_entered_scheduler_inputs=entered_scheduler,
        clock_source=ClockSource(str(record.get("clock_source"))),
    )


@dataclass
class ShadowObserverIntake:
    """Reference intake: bounded buffer, counted drops, isolated failures."""

    provider_id: str
    observer_id: str
    goal_id: str
    clock_source: ClockSource
    run_identity: ObserverRunIdentity
    event_sources: tuple[str, ...]
    source_fields_consumed: tuple[str, ...]
    buffer_bound: int = DEFAULT_BUFFER_BOUND
    observed_event_count: int = 0
    accepted_event_count: int = 0
    rejected_event_count: int = 0
    backpressure_drop_count: int = 0
    observer_failure_count: int = 0
    peak_buffered_event_count: int = 0
    flush_attempt_count: int = 0
    rejected_by_reason: dict[str, int] = field(default_factory=dict)
    _buffer: deque[ObserverEnvelope] = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        if not 1 <= self.buffer_bound <= MAX_BUFFER_BOUND:
            raise ValueError(f"buffer_bound must be within 1..{MAX_BUFFER_BOUND}")
        for key in ("provider_id", "observer_id", "goal_id"):
            if not IDENTITY_TOKEN_PATTERN.match(getattr(self, key)):
                raise ValueError(f"{key} must be an identity token")
        if not isinstance(self.run_identity, ObserverRunIdentity):
            raise ValueError("run_identity must be an ObserverRunIdentity")
        normalize_observer_run_identity(self.run_identity.as_dict())
        _token_list(list(self.event_sources), name="event_sources")
        _token_list(list(self.source_fields_consumed), name="source_fields_consumed")

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    def observe(self, record: Any) -> bool:
        """Accept or refuse one record; never raise into the event source."""

        self.observed_event_count += 1
        try:
            envelope = normalize_observer_envelope(record)
        except ObserverEnvelopeError as exc:
            self.rejected_event_count += 1
            reason = exc.reason.value
            self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
            return False
        except Exception:  # noqa: BLE001 - crash isolation is the contract
            self.observer_failure_count += 1
            self.rejected_event_count += 1
            reason = EnvelopeRejection.OBSERVER_INTERNAL_FAILURE.value
            self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
            return False
        if (
            envelope.provider_id != self.provider_id
            or envelope.observer_id != self.observer_id
            or envelope.goal_id != self.goal_id
        ):
            self.rejected_event_count += 1
            reason = EnvelopeRejection.IDENTITY_INVALID.value
            self.rejected_by_reason[reason] = self.rejected_by_reason.get(reason, 0) + 1
            return False
        if len(self._buffer) >= self.buffer_bound:
            self.backpressure_drop_count += 1
            return False
        self._buffer.append(envelope)
        self.accepted_event_count += 1
        self.peak_buffered_event_count = max(
            self.peak_buffered_event_count, len(self._buffer)
        )
        return True

    def drain(self) -> list[ObserverEnvelope]:
        drained = list(self._buffer)
        self._buffer.clear()
        return drained

    def stats(self, *, emitted_at: str) -> ObserverStats:
        return ObserverStats(
            provider_id=self.provider_id,
            observer_id=self.observer_id,
            goal_id=self.goal_id,
            run_identity=self.run_identity,
            event_sources=self.event_sources,
            source_fields_consumed=self.source_fields_consumed,
            emitted_at=emitted_at,
            observed_event_count=self.observed_event_count,
            accepted_event_count=self.accepted_event_count,
            rejected_event_count=self.rejected_event_count,
            rejected_by_reason=dict(self.rejected_by_reason),
            buffer_bound=self.buffer_bound,
            backpressure_drop_count=self.backpressure_drop_count,
            observer_failure_count=self.observer_failure_count,
            peak_buffered_event_count=self.peak_buffered_event_count,
            flush_attempt_count=self.flush_attempt_count,
            outbound_endpoints=(),
            observation_entered_worker_context=False,
            observation_entered_scheduler_inputs=False,
            clock_source=self.clock_source,
        )

    def flush(
        self,
        sink: Callable[[list[dict[str, Any]]], None],
        *,
        emitted_at: str,
    ) -> list[dict[str, Any]]:
        """Hand drained envelopes plus a stats record to ``sink``.

        A failing sink is counted as an observer failure and its envelopes are
        counted as backpressure drops; the failure never propagates.
        """

        envelopes = self.drain()
        records = [envelope.as_dict() for envelope in envelopes]
        self.flush_attempt_count += 1
        try:
            sink([*records, self.stats(emitted_at=emitted_at).as_dict()])
        except Exception:  # noqa: BLE001 - crash isolation is the contract
            self.observer_failure_count += 1
            self.accepted_event_count -= len(records)
            self.backpressure_drop_count += len(records)
            return []
        return records
