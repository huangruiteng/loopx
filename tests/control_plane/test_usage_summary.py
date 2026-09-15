from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from loopx.control_plane.quota.usage_collector import (
    RUN_USAGE_SCHEMA_VERSION,
    UsageRowError,
    UsageSample,
    build_compact_usage_row,
    collect_usage_for_run,
    ingest_usage_into_run_record,
)
from loopx.control_plane.quota.usage_summary import (
    _accumulate_usage,
    blank_usage_goal,
    build_usage_summary,
)
from loopx.quota import goal_quota_with_spend_ledger


def _usage(
    *,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_tokens: int | None = 20,
    cost_usd: float | None = 0.2,
    duration_ms: int | None = 5000,
    provider: str = "codex",
    model: str = "codex-1",
    source_snapshot_id: str = "snap-1",
    measurement_kind: str = "absolute",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": RUN_USAGE_SCHEMA_VERSION,
        "measurement_kind": measurement_kind,
        "source_snapshot_id": source_snapshot_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "provider": provider,
        "model": model,
    }
    if cache_tokens is not None:
        row["cache_tokens"] = cache_tokens
    if cost_usd is not None:
        row["cost_usd"] = cost_usd
    if duration_ms is not None:
        row["duration_ms"] = duration_ms
    return row


def _run(
    goal_id: str,
    *,
    generated_at: datetime,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run: dict[str, Any] = {"goal_id": goal_id, "generated_at": generated_at}
    if usage is not None:
        run["usage"] = usage
    return run


def _slot_run(
    goal_id: str,
    *,
    generated_at: datetime,
    classification: str,
    slots: int = 1,
    voided_run_generated_at: str | None = None,
) -> dict[str, Any]:
    quota_event: dict[str, Any] = {"event_type": classification, "slots": slots}
    if voided_run_generated_at is not None:
        quota_event["voided_run_generated_at"] = voided_run_generated_at
    return {
        "goal_id": goal_id,
        "generated_at": generated_at,
        "classification": classification,
        "quota_event": quota_event,
    }


def _identity_parse(value: Any) -> Any:
    return value


def test_blank_usage_goal_has_usage_fields() -> None:
    goal = blank_usage_goal("g1")
    for suffix in ("24h", "7d"):
        assert goal[f"input_tokens_{suffix}"] == 0
        assert goal[f"output_tokens_{suffix}"] == 0
        assert goal[f"cache_tokens_{suffix}"] == 0
        assert goal[f"cost_usd_{suffix}"] == 0.0
        assert goal[f"duration_ms_{suffix}"] == 0


def test_collect_usage_for_run_returns_none_without_usage_block() -> None:
    assert collect_usage_for_run({"goal_id": "g1"}) is None


def test_collect_usage_for_run_fails_closed_on_non_mapping_usage() -> None:
    with pytest.raises(UsageRowError, match="usage must be a mapping"):
        collect_usage_for_run({"goal_id": "g1", "usage": "not-a-dict"})


def test_collect_usage_for_run_fails_closed_without_schema_version() -> None:
    with pytest.raises(UsageRowError, match="schema_version"):
        collect_usage_for_run(
            {"usage": {"input_tokens": 1, "output_tokens": 1, "provider": "x", "model": "y"}}
        )


def test_collect_usage_for_run_fails_closed_on_non_finite_cost() -> None:
    with pytest.raises(UsageRowError, match="cost_usd must be finite"):
        collect_usage_for_run({"usage": _usage(cost_usd=float("nan"))})


def test_build_usage_summary_fails_closed_on_non_finite_persisted_cost() -> None:
    # A non-finite value that somehow reached a persisted row must abort
    # aggregation, never propagate into summary totals.
    run = _run(
        "g1",
        generated_at=datetime.now(timezone.utc),
        usage=_usage(cost_usd=float("inf")),
    )
    with pytest.raises(UsageRowError, match="cost_usd must be finite"):
        build_usage_summary({"runs": [run]}, parse_timestamp=_identity_parse)


def test_collect_usage_for_run_normalizes_fields() -> None:
    sample = collect_usage_for_run({"usage": _usage()})
    assert sample == UsageSample(
        100,
        50,
        20,
        0.2,
        5000,
        "codex",
        "codex-1",
        "snap-1",
        "absolute",
    )


def test_collect_usage_for_run_keeps_unmeasured_fields_unknown() -> None:
    sample = collect_usage_for_run(
        {
            "usage": _usage(
                cache_tokens=None,
                cost_usd=None,
                duration_ms=None,
            )
        }
    )
    assert sample is not None
    assert sample.cache_tokens is None
    assert sample.cost_usd is None
    assert sample.duration_ms is None


def test_build_usage_summary_aggregates_usage_within_windows() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=100,
                    output_tokens=50,
                    cache_tokens=20,
                    cost_usd=0.1,
                    duration_ms=1000,
                    source_snapshot_id="a",
                ),
            ),
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=200,
                    output_tokens=60,
                    cache_tokens=None,
                    cost_usd=0.2,
                    duration_ms=2000,
                    source_snapshot_id="b",
                ),
            ),
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    totals = summary["totals"]
    assert totals["input_tokens_24h"] == 300
    assert totals["output_tokens_24h"] == 110
    assert totals["cache_tokens_24h"] == 20
    assert totals["cost_usd_24h"] == round(0.1 + 0.2, 6)
    assert totals["duration_ms_24h"] == 3000
    goal = summary["goals"][0]
    assert goal["goal_id"] == "g1"
    assert goal["input_tokens_24h"] == 300


def test_build_usage_summary_degrades_when_runs_report_no_usage() -> None:
    now = datetime.now(timezone.utc)
    history = {"runs": [_run("g1", generated_at=now)]}
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    for bucket in (summary["totals"], summary["goals"][0]):
        assert "input_tokens_24h" not in bucket
        assert "cost_usd_24h" not in bucket
        assert "duration_ms_24h" not in bucket
        assert "input_tokens_7d" not in bucket
        assert "cost_usd_7d" not in bucket
        assert "duration_ms_7d" not in bucket
    assert summary["totals"]["runs_24h"] == 1


def test_build_usage_summary_omits_unknown_optional_metrics() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now,
                usage=_usage(cache_tokens=None, cost_usd=None, duration_ms=None),
            )
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    totals = summary["totals"]
    assert totals["input_tokens_24h"] == 100
    assert totals["output_tokens_24h"] == 50
    assert "cache_tokens_24h" not in totals
    assert "cost_usd_24h" not in totals
    assert "duration_ms_24h" not in totals


def test_build_usage_summary_only_emits_windows_with_usage_samples() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now - timedelta(days=2),
                usage=_usage(
                    input_tokens=25,
                    output_tokens=5,
                    cache_tokens=None,
                    cost_usd=None,
                    duration_ms=None,
                ),
            )
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    for bucket in (summary["totals"], summary["goals"][0]):
        assert "input_tokens_24h" not in bucket
        assert bucket["input_tokens_7d"] == 25
        assert bucket["output_tokens_7d"] == 5


def test_build_usage_summary_keeps_old_runs_out_of_usage_windows() -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=10)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now,
                usage=_usage(input_tokens=100, output_tokens=1, source_snapshot_id="new"),
            ),
            _run(
                "g1",
                generated_at=old,
                usage=_usage(input_tokens=999, output_tokens=1, source_snapshot_id="old"),
            ),
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    assert summary["totals"]["input_tokens_7d"] == 100
    assert summary["totals"]["input_tokens_24h"] == 100


def test_aged_out_void_does_not_reduce_a_later_window() -> None:
    now = datetime.now(timezone.utc)
    spent = _slot_run(
        "g1",
        generated_at=now - timedelta(days=2),
        classification="quota_slot_spent",
    )
    history = {
        "runs": [
            spent,
            _slot_run(
                "g1",
                generated_at=now,
                classification="quota_slot_voided",
                voided_run_generated_at=str(spent["generated_at"]),
            ),
        ]
    }

    summary = build_usage_summary(history, parse_timestamp=_identity_parse)

    # The voided spend is outside the 24h window, so the void must not drive
    # that window negative; the spend ledger clamps the same input to zero.
    assert summary["totals"]["quota_spend_slots_24h"] == 0
    assert summary["goals"][0]["quota_spend_slots_24h"] == 0
    # Both runs are inside the 7d window, so the void cancels its spend.
    assert summary["totals"]["quota_spend_slots_7d"] == 0


def test_spend_run_without_resolvable_quota_event_counts_no_slot() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            {
                "goal_id": "g1",
                "generated_at": now - timedelta(minutes=30),
                "classification": "quota_slot_spent",
            },
            _slot_run(
                "g1",
                generated_at=now - timedelta(minutes=20),
                classification="quota_slot_spent",
                slots=2,
            ),
        ]
    }

    summary = build_usage_summary(history, parse_timestamp=_identity_parse)

    # The ledger records no slot for a spend whose event it cannot read, so the
    # summary must not invent one either. The run still appears as an accounting
    # event in the event ledger, so the spend is not hidden, only unquantified.
    assert summary["totals"]["quota_spend_slots_24h"] == 2
    assert summary["goals"][0]["quota_spend_slots_24h"] == 2


def test_window_slot_spend_matches_the_enforcement_ledger() -> None:
    """The reported 24h spend must equal the spend the ledger enforces."""

    now = datetime.now(timezone.utc)
    spent = _slot_run(
        "g1",
        generated_at=now - timedelta(hours=2),
        classification="quota_slot_spent",
        slots=2,
    )
    aged_out = _slot_run(
        "g1",
        generated_at=now - timedelta(days=2),
        classification="quota_slot_spent",
    )
    mismatch = _slot_run(
        "g1",
        generated_at=now - timedelta(hours=3),
        classification="quota_slot_spent",
    )
    mismatch["classification"] = "quota_slot_voided"
    scenarios = {
        "spend": [spent],
        "spend_and_void": [
            spent,
            _slot_run(
                "g1",
                generated_at=now - timedelta(hours=1),
                classification="quota_slot_voided",
                voided_run_generated_at=str(spent["generated_at"]),
            ),
        ],
        "void_of_an_aged_out_spend": [
            aged_out,
            _slot_run(
                "g1",
                generated_at=now,
                classification="quota_slot_voided",
                voided_run_generated_at=str(aged_out["generated_at"]),
            ),
        ],
        "void_of_another_run": [
            spent,
            _slot_run(
                "g1",
                generated_at=now - timedelta(hours=1),
                classification="quota_slot_voided",
                voided_run_generated_at="some-other-run",
            ),
        ],
        "no_resolvable_event": [
            {
                "goal_id": "g1",
                "generated_at": now - timedelta(hours=4),
                "classification": "quota_slot_spent",
            }
        ],
        "non_positive_slots": [
            _slot_run(
                "g1",
                generated_at=now - timedelta(hours=5),
                classification="quota_slot_spent",
                slots=0,
            )
        ],
        "classification_disagrees_with_event_type": [mismatch],
    }

    for name, runs in scenarios.items():
        summary = build_usage_summary({"runs": runs}, parse_timestamp=_identity_parse)
        ledger = goal_quota_with_spend_ledger({"id": "g1"}, runs, now=now)

        assert summary["totals"]["quota_spend_slots_24h"] == ledger["spent_slots"], name
        assert summary["goals"][0]["quota_spend_slots_24h"] == ledger["spent_slots"], name


def test_void_only_cancels_the_spend_it_targets() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _slot_run(
                "g1",
                generated_at=now - timedelta(hours=2),
                classification="quota_slot_spent",
            ),
            _slot_run(
                "g1",
                generated_at=now - timedelta(hours=1),
                classification="quota_slot_voided",
                voided_run_generated_at="some-other-run",
            ),
        ]
    }

    summary = build_usage_summary(history, parse_timestamp=_identity_parse)

    assert summary["totals"]["quota_spend_slots_24h"] == 1
    assert summary["goals"][0]["quota_spend_slots_24h"] == 1


def test_build_usage_summary_is_provider_neutral() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=10,
                    output_tokens=1,
                    provider="codex",
                    model="codex",
                    source_snapshot_id="c1",
                ),
            ),
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=40,
                    output_tokens=1,
                    provider="claude",
                    model="claude-x",
                    source_snapshot_id="c2",
                ),
            ),
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    assert summary["totals"]["input_tokens_24h"] == 50


def test_build_usage_summary_rounds_cost_to_avoid_float_drift() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=1,
                    output_tokens=1,
                    cost_usd=0.1,
                    source_snapshot_id="r1",
                    provider="x",
                    model="y",
                ),
            ),
            _run(
                "g1",
                generated_at=now,
                usage=_usage(
                    input_tokens=1,
                    output_tokens=1,
                    cost_usd=0.2,
                    source_snapshot_id="r2",
                    provider="x",
                    model="y",
                ),
            ),
        ]
    }
    summary = build_usage_summary(history, parse_timestamp=_identity_parse)
    assert summary["totals"]["cost_usd_24h"] == 0.3


def test_build_usage_summary_fails_closed_when_total_cost_overflows() -> None:
    now = datetime.now(timezone.utc)
    history = {
        "runs": [
            _run(
                goal_id,
                generated_at=now,
                usage=_usage(
                    input_tokens=1,
                    output_tokens=1,
                    cost_usd=1e308,
                    source_snapshot_id=f"overflow-{goal_id}",
                ),
            )
            for goal_id in ("g1", "g2")
        ]
    }

    with pytest.raises(UsageRowError, match="cost_usd_7d must be finite"):
        build_usage_summary(history, parse_timestamp=_identity_parse)


def test_accumulate_usage_fails_closed_when_goal_cost_overflows() -> None:
    bucket = blank_usage_goal("g1")
    sample = UsageSample(
        input_tokens=1,
        output_tokens=1,
        cache_tokens=None,
        cost_usd=1e308,
        duration_ms=None,
        provider="codex",
        model="codex-1",
        source_snapshot_id="overflow-goal",
        measurement_kind="delta",
    )
    observed_metrics: set[str] = set()
    _accumulate_usage(bucket, sample, "24h", observed_metrics)

    with pytest.raises(UsageRowError, match="cost_usd_24h must be finite"):
        _accumulate_usage(bucket, sample, "24h", observed_metrics)


def test_collect_usage_for_run_rejects_bool_tokens() -> None:
    with pytest.raises(UsageRowError, match="input_tokens"):
        collect_usage_for_run(
            {"usage": _usage(input_tokens=True)}  # type: ignore[arg-type]
        )


def test_collect_usage_for_run_rejects_negative_tokens() -> None:
    with pytest.raises(UsageRowError, match="non-negative"):
        collect_usage_for_run({"usage": _usage(input_tokens=-100)})


def test_collect_usage_for_run_rejects_non_numeric_tokens() -> None:
    with pytest.raises(UsageRowError, match="input_tokens"):
        collect_usage_for_run(
            {
                "usage": {
                    **_usage(),
                    "input_tokens": "100",
                }
            }
        )


def test_collect_usage_for_run_rejects_negative_cost() -> None:
    with pytest.raises(UsageRowError, match="cost_usd"):
        collect_usage_for_run({"usage": _usage(cost_usd=-0.5)})


def test_build_compact_usage_row_from_cumulative_delta() -> None:
    previous = {
        "source_snapshot_id": "snap-1",
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_tokens": 10,
        "cost_usd": 0.1,
        "duration_ms": 1000,
    }
    row = build_compact_usage_row(
        input_tokens=150,
        output_tokens=55,
        cache_tokens=12,
        cost_usd=0.15,
        duration_ms=1600,
        provider="codex",
        model="codex-1",
        source_snapshot_id="snap-2",
        previous_snapshot=previous,
    )
    assert row["schema_version"] == RUN_USAGE_SCHEMA_VERSION
    assert row["measurement_kind"] == "delta"
    assert row["input_tokens"] == 50
    assert row["output_tokens"] == 15
    assert row["cache_tokens"] == 2
    assert row["cost_usd"] == pytest.approx(0.05)
    assert row["duration_ms"] == 600
    assert row["source_snapshot_id"] == "snap-2"


def test_build_compact_usage_row_idempotent_replay_same_snapshot() -> None:
    previous = {
        "source_snapshot_id": "snap-9",
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_tokens": 10,
        "cost_usd": 0.1,
        "duration_ms": 1000,
        "provider": "codex",
        "model": "codex-1",
    }
    row = build_compact_usage_row(
        input_tokens=100,
        output_tokens=40,
        cache_tokens=10,
        cost_usd=0.1,
        duration_ms=1000,
        provider="codex",
        model="codex-1",
        source_snapshot_id="snap-9",
        previous_snapshot=previous,
    )
    assert row["measurement_kind"] == "delta"
    assert row["input_tokens"] == 0
    assert row["output_tokens"] == 0
    assert row["cache_tokens"] == 0
    assert row["cost_usd"] == 0.0
    assert row["duration_ms"] == 0


def test_build_compact_usage_row_same_snapshot_id_different_counters_fails_closed() -> None:
    previous = {
        "source_snapshot_id": "snap-9",
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_tokens": 10,
        "cost_usd": 0.1,
        "duration_ms": 1000,
        "provider": "codex",
        "model": "codex-1",
    }
    with pytest.raises(UsageRowError, match="different cumulative observation.*input_tokens"):
        build_compact_usage_row(
            input_tokens=150,
            output_tokens=40,
            cache_tokens=10,
            cost_usd=0.1,
            duration_ms=1000,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-9",
            previous_snapshot=previous,
        )


def test_build_compact_usage_row_same_snapshot_id_optional_presence_change_fails_closed() -> None:
    previous = {
        "source_snapshot_id": "snap-9",
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_tokens": 10,
        "provider": "codex",
        "model": "codex-1",
    }
    with pytest.raises(UsageRowError, match="different cumulative observation.*cache_tokens"):
        build_compact_usage_row(
            input_tokens=100,
            output_tokens=40,
            cache_tokens=None,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-9",
            previous_snapshot=previous,
        )


def test_build_compact_usage_row_same_snapshot_id_different_labels_fails_closed() -> None:
    previous = {
        "source_snapshot_id": "snap-9",
        "input_tokens": 100,
        "output_tokens": 40,
        "provider": "codex",
        "model": "codex-1",
    }
    with pytest.raises(UsageRowError, match="different cumulative observation.*model"):
        build_compact_usage_row(
            input_tokens=100,
            output_tokens=40,
            provider="codex",
            model="codex-2",
            source_snapshot_id="snap-9",
            previous_snapshot=previous,
        )


def test_build_compact_usage_row_same_snapshot_id_without_prior_labels_fails_closed() -> None:
    # A same-id basis that never recorded its binding labels cannot prove the
    # replay is identical, so it must not be treated as a zero-delta replay.
    previous = {
        "source_snapshot_id": "snap-9",
        "input_tokens": 100,
        "output_tokens": 40,
    }
    with pytest.raises(UsageRowError, match="different cumulative observation"):
        build_compact_usage_row(
            input_tokens=100,
            output_tokens=40,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-9",
            previous_snapshot=previous,
        )


@pytest.mark.parametrize(
    "bad_cost", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "-inf"]
)
def test_build_compact_usage_row_rejects_non_finite_cost(bad_cost: float) -> None:
    # NaN/Infinity would survive json.dumps as non-standard JSON and poison
    # aggregation, so they must fail closed at intake instead.
    with pytest.raises(UsageRowError, match="cost_usd must be finite"):
        build_compact_usage_row(
            input_tokens=10,
            output_tokens=5,
            cost_usd=bad_cost,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-nonfinite-cost",
        )


@pytest.mark.parametrize(
    "bad_tokens", [float("nan"), float("inf")], ids=["nan", "inf"]
)
def test_build_compact_usage_row_rejects_non_finite_token_counts(
    bad_tokens: float,
) -> None:
    # Must raise the typed UsageRowError, not leak int()'s ValueError/OverflowError.
    with pytest.raises(UsageRowError, match="input_tokens must be finite"):
        build_compact_usage_row(
            input_tokens=bad_tokens,  # type: ignore[arg-type]
            output_tokens=5,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-nonfinite-tokens",
        )


def test_build_compact_usage_row_fails_closed_on_cumulative_reset() -> None:
    previous = {
        "source_snapshot_id": "snap-1",
        "input_tokens": 100,
        "output_tokens": 40,
    }
    with pytest.raises(UsageRowError, match="reset or out-of-order"):
        build_compact_usage_row(
            input_tokens=80,
            output_tokens=40,
            provider="codex",
            model="codex-1",
            source_snapshot_id="snap-2",
            previous_snapshot=previous,
        )


def test_ingest_usage_into_run_record_attaches_typed_row() -> None:
    record: dict[str, Any] = {
        "generated_at": "2026-08-26T00:00:00+00:00",
        "goal_id": "g1",
        "run_id": "run-1",
    }
    index_record: dict[str, Any] = dict(record)
    row = ingest_usage_into_run_record(
        record,
        {
            "input_tokens": 12,
            "output_tokens": 3,
            "provider": "fixture",
            "model": "fixture-1",
            "source_snapshot_id": "host-snap-1",
        },
        index_record=index_record,
    )
    assert row is not None
    assert record["usage"]["schema_version"] == RUN_USAGE_SCHEMA_VERSION
    assert index_record["usage"]["input_tokens"] == 12
    sample = collect_usage_for_run(record)
    assert sample is not None
    assert sample.input_tokens == 12
    assert sample.source_snapshot_id == "host-snap-1"


def test_ingest_usage_into_run_record_fails_closed_on_negative() -> None:
    record: dict[str, Any] = {"generated_at": "2026-08-26T00:00:00+00:00"}
    with pytest.raises(UsageRowError, match="non-negative"):
        ingest_usage_into_run_record(
            record,
            {
                "input_tokens": -1,
                "output_tokens": 1,
                "provider": "fixture",
                "model": "fixture-1",
                "source_snapshot_id": "bad",
            },
        )
    assert "usage" not in record
