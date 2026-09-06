"""Codex session rollout usage producer for the ``run_usage_v0`` ledger seam.

This is the first shipped measurement source behind
``ingest_usage_into_run_record``: it reads one locally stored Codex CLI
session rollout (JSONL) and returns the session-cumulative token usage as a
provider-neutral observation. Only aggregate ``token_count`` totals, the model
id, the session id, and event timestamps are read; prompts, completions, tool
output, and any other conversational content never enter the measurement.

The rollout must be bound explicitly by the caller. This module performs no
session discovery under ``CODEX_HOME``: guessing the session (for example by
cwd and mtime) risks attributing one concurrent session's spend to another
run, and a wrong attribution is worse than an unknown one. Automatic
discovery, if ever added, needs its own explicitly reviewed contract.

Cumulative-to-delta conversion happens at the run-write boundary. The delta
basis is not a second state file: :func:`session_usage_baseline` reconstructs
each session's last accepted cumulative observation from the run index itself
(telescoping absolute + delta sums per session id), so the durable row append
is the single commit point that also advances the basis. A crash or retry can
never leave the basis behind the ledger — replaying the same rollout books an
idempotent zero delta, a grown rollout books only the non-negative increment,
and interleaved sessions (A, then B, then A again) each rebase against their
own baseline. Callers must hold the per-goal usage booking lock (see
:func:`usage_booking_lock_target`) across basis read + row append so two
concurrent bookings cannot fund two deltas from one stale basis. Missing
optional metrics stay unknown, never zero.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping, cast

from ..runtime.run_index_duplicates import index_identity
from .usage_collector import (
    UsageRowError,
    ingest_usage_into_run_record,
    normalize_compact_usage_row,
)

CODEX_USAGE_PROVIDER = "codex"
USAGE_BOOKING_LOCK_TARGET = "usage_booking"
_BASELINE_INT_FIELDS = ("input_tokens", "output_tokens", "cache_tokens", "duration_ms")


class CodexSessionUsageError(UsageRowError):
    """Fail-closed diagnostic for unreadable or unusable Codex rollouts."""


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def read_codex_session_usage(rollout_path: Path) -> dict[str, Any]:
    """Return one cumulative usage observation from a Codex session rollout.

    Counters are the session-cumulative totals from the newest ``token_count``
    event. ``source_snapshot_id`` binds the observation to the session id plus
    that event's timestamp, so replaying an unchanged rollout keeps the same
    identity (idempotent zero delta) while a grown rollout produces a new
    identity whose delta is taken against the stored previous observation.
    """
    path = Path(rollout_path).expanduser()
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CodexSessionUsageError(
            f"cannot read codex session rollout: {exc}"
        ) from exc

    session_id = ""
    session_started_at: datetime | None = None
    model = ""
    last_totals: Mapping[str, Any] | None = None
    last_totals_at = ""
    last_totals_model = ""
    lines = [
        (number, text)
        for number, text in enumerate(raw_text.splitlines(), start=1)
        if text.strip()
    ]
    for position, (line_number, line) in enumerate(lines):
        try:
            item = json.loads(line.strip())
        except json.JSONDecodeError as exc:
            if position == len(lines) - 1:
                # The Codex CLI appends to the rollout while sessions run; only
                # a torn final line is concurrent-write noise. A malformed line
                # with valid events after it means the file itself is damaged,
                # and parsing on could book a stale cumulative snapshot.
                continue
            raise CodexSessionUsageError(
                f"codex session rollout line {line_number} is corrupt: {path}"
            ) from exc
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        raw_payload = item.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        if kind == "session_meta":
            session_id = str(
                payload.get("session_id") or payload.get("id") or ""
            ).strip()
            session_started_at = _parse_timestamp(
                payload.get("timestamp") or item.get("timestamp")
            )
        elif kind == "turn_context":
            model_text = str(payload.get("model") or "").strip()
            if model_text:
                model = model_text
        elif kind == "event_msg" and str(payload.get("type") or "") == "token_count":
            raw_info = payload.get("info")
            info = raw_info if isinstance(raw_info, dict) else {}
            totals = info.get("total_token_usage")
            if isinstance(totals, Mapping):
                last_totals = totals
                last_totals_at = str(item.get("timestamp") or "").strip()
                # The model labels this cumulative snapshot only if it was
                # observed before the token_count event. A later turn_context
                # must not relabel an unchanged snapshot on replay.
                last_totals_model = model

    if not session_id:
        raise CodexSessionUsageError(
            f"codex session rollout has no session_meta id: {path}"
        )
    if last_totals is None:
        raise CodexSessionUsageError(
            f"codex session rollout has no token_count usage events: {path}"
        )
    if not last_totals_model:
        raise CodexSessionUsageError(
            f"codex session rollout has no turn_context model id: {path}"
        )

    duration_ms: int | None = None
    observed_at = _parse_timestamp(last_totals_at)
    if session_started_at is not None and observed_at is not None:
        elapsed_seconds = (observed_at - session_started_at).total_seconds()
        if elapsed_seconds >= 0:
            duration_ms = int(elapsed_seconds * 1000)

    observation: dict[str, Any] = {
        "input_tokens": last_totals.get("input_tokens"),
        "output_tokens": last_totals.get("output_tokens"),
        "cache_tokens": last_totals.get("cached_input_tokens"),
        "provider": CODEX_USAGE_PROVIDER,
        "model": last_totals_model,
        "session_id": session_id,
        "source_snapshot_id": f"codex:{session_id}:{last_totals_at or 'unanchored'}",
        "measurement_kind": "absolute",
    }
    if duration_ms is not None:
        observation["duration_ms"] = duration_ms
    return observation


def usage_booking_lock_target(runs_dir: Path) -> Path:
    """Return the per-goal lock target serializing usage basis read + append."""
    return Path(runs_dir) / USAGE_BOOKING_LOCK_TARGET


def book_codex_session_usage(
    record: MutableMapping[str, Any],
    rollout_path: Path,
    index_path: Path,
    *,
    index_record: MutableMapping[str, Any] | None = None,
) -> None:
    """Read the rollout and ingest its typed usage row onto the run record.

    The delta basis is the session's ledger baseline from ``index_path``.
    Callers must hold the usage booking lock across this call and the run row
    append it funds, so concurrent bookings serialize on one basis.
    """
    observation = read_codex_session_usage(rollout_path)
    ingest_usage_into_run_record(
        record,
        {key: value for key, value in observation.items() if key != "session_id"},
        previous_snapshot=session_usage_baseline(
            index_path, str(observation.get("session_id") or "")
        ),
        index_record=index_record,
    )


def session_usage_baseline(
    index_path: Path, session_id: str
) -> dict[str, Any] | None:
    """Reconstruct the session's last accepted cumulative observation.

    The run index append is the ledger's single commit point: a usage booking
    exists exactly when its row is durable. Summing the session's absolute and
    delta rows telescopes back to the last accepted cumulative observation, so
    there is no second basis state that a crash between writes could leave
    stale. ``None`` means the session has never been booked (absolute intake).
    Corrupt index rows fail closed: skipping a booked row would shrink the
    basis and double-book real spend. Callers must hold the usage booking lock
    while reading the basis and appending the row it funds.
    """
    sid = str(session_id or "").strip()
    if not sid:
        raise CodexSessionUsageError("usage observation has no session id")
    prefix = f"{CODEX_USAGE_PROVIDER}:{sid}:"
    try:
        raw = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CodexSessionUsageError(
            f"cannot read run index for the usage basis: {exc}"
        ) from exc

    int_totals: dict[str, int | None] = {field: None for field in _BASELINE_INT_FIELDS}
    cost_total: float | None = None
    last_usage: Mapping[str, Any] | None = None
    seen_rows: set[tuple[str, str, str]] = set()
    for line_number, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexSessionUsageError(
                f"run index row {line_number} is corrupt: {index_path}"
            ) from exc
        if not isinstance(row, dict):
            continue
        raw_usage = row.get("usage")
        if not isinstance(raw_usage, dict):
            continue
        if not str(raw_usage.get("source_snapshot_id") or "").startswith(prefix):
            continue
        try:
            usage = normalize_compact_usage_row(raw_usage)
        except UsageRowError as exc:
            raise CodexSessionUsageError(
                f"run index row {line_number} has invalid usage: {index_path}: {exc}"
            ) from exc
        if usage["provider"] != CODEX_USAGE_PROVIDER:
            raise CodexSessionUsageError(
                f"run index row {line_number} usage.provider must be codex: {index_path}"
            )
        if not str(usage["source_snapshot_id"]).startswith(prefix):
            raise CodexSessionUsageError(
                f"run index row {line_number} usage source does not match session: {index_path}"
            )
        identity = index_identity(row)
        if identity in seen_rows:
            continue
        seen_rows.add(identity)
        for field in _BASELINE_INT_FIELDS:
            value = usage.get(field)
            if value is None:
                continue
            int_totals[field] = (int_totals[field] or 0) + cast(int, value)
        cost = usage.get("cost_usd")
        if cost is not None:
            cost_total = (cost_total or 0.0) + cast(float, cost)
        last_usage = usage
    if last_usage is None:
        return None
    return {
        "session_id": sid,
        "source_snapshot_id": str(last_usage.get("source_snapshot_id") or ""),
        "input_tokens": int_totals["input_tokens"],
        "output_tokens": int_totals["output_tokens"],
        "cache_tokens": int_totals["cache_tokens"],
        "cost_usd": cost_total,
        "duration_ms": int_totals["duration_ms"],
        "provider": last_usage.get("provider"),
        "model": last_usage.get("model"),
    }
