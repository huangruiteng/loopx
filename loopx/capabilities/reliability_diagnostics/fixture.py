"""Deterministic DSH-shaped observer fixture and its conformance run.

The fixture is a fixed envelope stream shaped like the `dsh-session-events`
provider output. It deliberately exercises: a sequence gap (event loss), an
event with declared clock uncertainty above the degraded threshold, a
raw-material-bearing record that must be rejected, and a burst that overflows
the bounded buffer so backpressure drops are counted. Outbound endpoints stay
empty because the intake cannot express any.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .envelope import (
    CAPABILITY_ID,
    DSH_PROVIDER_ID,
    OBSERVER_ENVELOPE_SCHEMA_VERSION,
    ClockSource,
    ObserverEventKind,
)
from .intake import ObserverRunIdentity, ShadowObserverIntake
from .projection import build_diagnostic_projection
from .receipt import build_integrity_receipt, read_ledger

FIXTURE_GOAL_ID = "goal-dsh-fixture"
FIXTURE_SESSION_ID = "dsh-session-fixture"
FIXTURE_AGENT_ID = "agent-dsh-fixture"
FIXTURE_OBSERVER_ID = "dsh-session-events-fixture"
FIXTURE_BUFFER_BOUND = 20
FIXTURE_UNCERTAIN_CLOCK_MS = 1500
FIXTURE_START = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXTURE_RUN_IDENTITY = ObserverRunIdentity(
    worker_id="dsh-worker-fixture",
    model_id="model-fixture",
    task_id="task-fixture",
    environment_id="environment-fixture",
    tools_id="tools-fixture",
    budget_id="budget-fixture",
    adapter_revision="dsh-adapter-fixture",
    observer_revision="observer-fixture",
)


def _envelope(
    sequence: int,
    kind: ObserverEventKind,
    *,
    seconds: int,
    summary: dict[str, Any] | None = None,
    source_refs: dict[str, str] | None = None,
    clock_source: ClockSource = ClockSource.HARNESS_EVENT_TIME,
    uncertainty_ms: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": OBSERVER_ENVELOPE_SCHEMA_VERSION,
        "capability_id": CAPABILITY_ID,
        "provider_id": DSH_PROVIDER_ID,
        "observer_id": FIXTURE_OBSERVER_ID,
        "goal_id": FIXTURE_GOAL_ID,
        "session_id": FIXTURE_SESSION_ID,
        "agent_id": FIXTURE_AGENT_ID,
        "sequence": sequence,
        "observed_at": (FIXTURE_START + timedelta(seconds=seconds)).isoformat(),
        "clock": {"source": clock_source.value, "uncertainty_ms": uncertainty_ms},
        "event_kind": kind.value,
        "summary": summary or {},
        "source_refs": {"event_seq": str(sequence), **(source_refs or {})},
    }


def dsh_fixture_records() -> list[dict[str, Any]]:
    """The fixed DSH-shaped stream as the provider would hand it to the intake."""

    k = ObserverEventKind
    records = [
        _envelope(0, k.SESSION_STARTED, seconds=0),
        _envelope(1, k.AGENT_STATUS, seconds=1, summary={"status": "running"}, clock_source=ClockSource.OBSERVER_WALL_CLOCK, uncertainty_ms=50),
        _envelope(2, k.TURN_STARTED, seconds=1, summary={"turn": 1}),
        _envelope(3, k.USER_MESSAGE, seconds=1, summary={"turn": 1, "message_source_kind": "user"}, source_refs={"message_id": "msg-1"}),
        _envelope(4, k.STEP_STARTED, seconds=2, summary={"turn": 1, "step": 1}),
        _envelope(5, k.TOOL_CALLED, seconds=3, summary={"turn": 1, "step": 1, "tool_name": "bash"}, source_refs={"tool_call_id": "call-1"}),
        _envelope(6, k.TOOL_COMPLETED, seconds=8, summary={"turn": 1, "step": 1, "status": "ok"}, source_refs={"tool_call_id": "call-1"}),
        _envelope(7, k.STEP_ENDED, seconds=9, summary={"turn": 1, "step": 1}),
        _envelope(8, k.TURN_ENDED, seconds=9, summary={"turn": 1, "reason": "completed"}),
        _envelope(9, k.AGENT_STATUS, seconds=9, summary={"status": "idle"}, clock_source=ClockSource.OBSERVER_WALL_CLOCK, uncertainty_ms=50),
        # sequence 10 is intentionally missing: event loss before the observer.
        _envelope(11, k.TURN_STARTED, seconds=60, summary={"turn": 2}, clock_source=ClockSource.OBSERVER_WALL_CLOCK, uncertainty_ms=FIXTURE_UNCERTAIN_CLOCK_MS),
        _envelope(12, k.STEP_STARTED, seconds=61, summary={"turn": 2, "step": 1}),
        _envelope(13, k.TOOL_CALLED, seconds=62, summary={"turn": 2, "step": 1, "tool_name": "read"}, source_refs={"tool_call_id": "call-2"}),
        _envelope(14, k.TOOL_CALLED, seconds=63, summary={"turn": 2, "step": 1, "tool_name": "read"}, source_refs={"tool_call_id": "call-3"}),
        _envelope(15, k.TOOL_CALLED, seconds=64, summary={"turn": 2, "step": 1, "tool_name": "read"}, source_refs={"tool_call_id": "call-4"}),
        _envelope(16, k.AGENT_ERROR, seconds=70, summary={"turn": 2, "error_class": "ToolTimeout"}),
        _envelope(17, k.STEP_ENDED, seconds=71, summary={"turn": 2, "step": 1}),
        _envelope(18, k.TURN_ENDED, seconds=72, summary={"turn": 2, "reason": "completed"}),
    ]
    raw_material_record = _envelope(19, k.USER_MESSAGE, seconds=73, summary={"turn": 3})
    raw_material_record["transcript"] = "protected task content that must never be persisted"
    records.append(raw_material_record)
    # Burst arriving while the bounded buffer fills: sequences 20..23. The
    # later disposal is also dropped, so trailing loss is visible only through
    # the stats record, not through sequence gaps.
    records.extend(
        _envelope(sequence, k.AGENT_PRE_STEP, seconds=74, summary={"turn": 3})
        for sequence in range(20, 24)
    )
    records.append(_envelope(24, k.SESSION_DISPOSED, seconds=90))
    return records


def run_dsh_fixture() -> dict[str, Any]:
    """Feed the fixture through the reference intake without flushing mid-burst.

    Returns the persisted ledger records, the intake stats, the receipt, and
    the projection so callers can assert contract semantics.
    """

    intake = ShadowObserverIntake(
        provider_id=DSH_PROVIDER_ID,
        observer_id=FIXTURE_OBSERVER_ID,
        goal_id=FIXTURE_GOAL_ID,
        clock_source=ClockSource.FIXTURE,
        run_identity=FIXTURE_RUN_IDENTITY,
        event_sources=("session/created", "session/disposed", "session/event"),
        source_fields_consumed=(
            "event.data.callId",
            "event.data.error.code",
            "event.data.id",
            "event.data.message.source.callId",
            "event.data.name",
            "event.data.reason.kind",
            "event.data.source.kind",
            "event.data.step",
            "event.data.turn",
            "event.seq",
            "event.time",
            "event.type",
            "session.id",
        ),
        buffer_bound=FIXTURE_BUFFER_BOUND,
    )
    accepted = [intake.observe(record) for record in dsh_fixture_records()]
    ledger: list[dict[str, Any]] = []
    emitted_at = (FIXTURE_START + timedelta(seconds=95)).isoformat()
    intake.flush(ledger.extend, emitted_at=emitted_at)
    reading = read_ledger(ledger, goal_id=FIXTURE_GOAL_ID)
    return {
        "accepted_flags": accepted,
        "ledger_records": ledger,
        "stats": intake.stats(emitted_at=emitted_at).as_dict(),
        "receipt": build_integrity_receipt(reading),
        "projection": build_diagnostic_projection(reading),
    }
