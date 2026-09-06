"""End-to-end producer regression for the GH-C95 cost ledger.

Proves that a shipped host measurement source (a Codex session rollout) lands
as a typed ``run_usage_v0`` row on the real ``refresh-state`` run-write path,
that the goal's ``usage_summary`` becomes non-zero, that replaying the same
cumulative snapshot never double-counts, and that a grown rollout books only
the non-negative increment.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

import loopx.state_refresh as state_refresh_module
from loopx.control_plane.quota.codex_session_usage import (
    CodexSessionUsageError,
    book_codex_session_usage,
    read_codex_session_usage,
    session_usage_baseline,
)
from loopx.control_plane.quota.usage_collector import UsageRowError
from loopx.control_plane.quota.usage_summary import build_usage_summary
from loopx.control_plane.runtime.time import parse_timestamp
from loopx.state_refresh import refresh_state_run

GOAL_ID = "codex-usage-fixture"
SESSION_ID = "019f0000-aaaa-bbbb-cccc-000000000001"
OTHER_SESSION_ID = "019f0000-aaaa-bbbb-cccc-000000000002"
MODEL = "gpt-fixture-1"


def _rollout_event(
    timestamp: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> str:
    totals = {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_input_tokens": 0,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": 0,
        "total_tokens": input_tokens + output_tokens,
    }
    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": totals,
                    "last_token_usage": totals,
                    "model_context_window": 400000,
                },
            },
        }
    )


def _rollout_header(session_id: str = SESSION_ID) -> list[str]:
    return [
        json.dumps(
            {
                "timestamp": "2026-08-26T01:00:00.000Z",
                "type": "session_meta",
                "payload": {
                    "session_id": session_id,
                    "timestamp": "2026-08-26T01:00:00.000Z",
                    "cwd": "/tmp/fixture-project",
                },
            }
        ),
        json.dumps(
            {
                "timestamp": "2026-08-26T01:00:01.000Z",
                "type": "turn_context",
                "payload": {"turn_id": "turn-1", "model": MODEL},
            }
        ),
    ]


def _rollout_model_context(model: str, *, turn_id: str = "turn-2") -> str:
    return json.dumps(
        {
            "timestamp": "2026-08-26T01:06:00.000Z",
            "type": "turn_context",
            "payload": {"turn_id": turn_id, "model": model},
        }
    )


def _write_rollout(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fixture_rollout(tmp_path: Path) -> Path:
    lines = [
        *_rollout_header(),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=1200,
            cached_input_tokens=200,
            output_tokens=300,
        ),
    ]
    return _write_rollout(tmp_path / "rollout-fixture.jsonl", lines)


def test_read_codex_session_usage_extracts_cumulative_totals(tmp_path: Path) -> None:
    observation = read_codex_session_usage(_fixture_rollout(tmp_path))
    assert observation["input_tokens"] == 1200
    assert observation["output_tokens"] == 300
    assert observation["cache_tokens"] == 200
    assert observation["provider"] == "codex"
    assert observation["model"] == MODEL
    assert observation["session_id"] == SESSION_ID
    assert observation["source_snapshot_id"] == (
        f"codex:{SESSION_ID}:2026-08-26T01:05:00.000Z"
    )
    assert observation["measurement_kind"] == "absolute"
    assert observation["duration_ms"] == 300_000
    assert "cost_usd" not in observation  # unmeasured stays unknown, not zero


def test_read_codex_session_usage_binds_model_when_token_snapshot_is_observed(
    tmp_path: Path,
) -> None:
    lines = [
        *_rollout_header(),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=1200,
            cached_input_tokens=200,
            output_tokens=300,
        ),
        _rollout_model_context("gpt-fixture-2"),
    ]
    rollout = _write_rollout(tmp_path / "rollout-model-switch.jsonl", lines)

    first = read_codex_session_usage(rollout)
    second = read_codex_session_usage(rollout)

    assert first["model"] == MODEL
    assert second == first


def test_read_codex_session_usage_updates_model_with_new_token_snapshot(
    tmp_path: Path,
) -> None:
    lines = [
        *_rollout_header(),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=1200,
            cached_input_tokens=200,
            output_tokens=300,
        ),
        _rollout_model_context("gpt-fixture-2"),
        _rollout_event(
            "2026-08-26T01:10:00.000Z",
            input_tokens=2000,
            cached_input_tokens=350,
            output_tokens=450,
        ),
    ]
    rollout = _write_rollout(
        tmp_path / "rollout-model-switch-new-usage.jsonl", lines
    )

    observation = read_codex_session_usage(rollout)

    assert observation["model"] == "gpt-fixture-2"
    assert observation["input_tokens"] == 2000


def test_read_codex_session_usage_requires_model_before_token_snapshot(
    tmp_path: Path,
) -> None:
    lines = [
        json.dumps(
            {
                "timestamp": "2026-08-26T01:00:00.000Z",
                "type": "session_meta",
                "payload": {"session_id": SESSION_ID},
            }
        ),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=1200,
            cached_input_tokens=200,
            output_tokens=300,
        ),
        _rollout_model_context("gpt-fixture-2"),
    ]
    rollout = _write_rollout(tmp_path / "rollout-late-model.jsonl", lines)

    with pytest.raises(CodexSessionUsageError, match="no turn_context model"):
        read_codex_session_usage(rollout)


def test_read_codex_session_usage_tolerates_torn_trailing_line(tmp_path: Path) -> None:
    lines = [
        *_rollout_header(),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
        ),
        '{"timestamp":"2026-08-26T01:06:00.000Z","type":"event_msg","payl',
    ]
    observation = read_codex_session_usage(
        _write_rollout(tmp_path / "rollout-torn.jsonl", lines)
    )
    assert observation["input_tokens"] == 10


def test_read_codex_session_usage_fails_closed_on_corrupt_middle_line(
    tmp_path: Path,
) -> None:
    # A malformed line followed by valid events is file damage, not a torn
    # tail: parsing on could silently accept a stale cumulative snapshot.
    lines = [
        *_rollout_header(),
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=100,
            cached_input_tokens=0,
            output_tokens=10,
        ),
        '{"timestamp":"2026-08-26T01:06:00.000Z","type":"event_msg","payl',
        _rollout_event(
            "2026-08-26T01:07:00.000Z",
            input_tokens=200,
            cached_input_tokens=0,
            output_tokens=20,
        ),
    ]
    path = _write_rollout(tmp_path / "rollout-corrupt-middle.jsonl", lines)
    with pytest.raises(CodexSessionUsageError, match="line 4 is corrupt"):
        read_codex_session_usage(path)


def test_read_codex_session_usage_fails_closed_without_token_counts(
    tmp_path: Path,
) -> None:
    path = _write_rollout(tmp_path / "rollout-empty.jsonl", _rollout_header())
    with pytest.raises(CodexSessionUsageError, match="no token_count"):
        read_codex_session_usage(path)


def test_read_codex_session_usage_fails_closed_without_session_meta(
    tmp_path: Path,
) -> None:
    lines = [
        _rollout_event(
            "2026-08-26T01:05:00.000Z",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
        )
    ]
    path = _write_rollout(tmp_path / "rollout-no-meta.jsonl", lines)
    with pytest.raises(CodexSessionUsageError, match="session_meta"):
        read_codex_session_usage(path)


def test_read_codex_session_usage_fails_closed_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CodexSessionUsageError, match="cannot read"):
        read_codex_session_usage(tmp_path / "missing.jsonl")


def _index_row(
    *,
    generated_at: str,
    source_snapshot_id: str,
    input_tokens: int,
    output_tokens: int,
    measurement_kind: str,
    cache_tokens: int | None = None,
    duration_ms: int | None = None,
) -> str:
    usage: dict[str, Any] = {
        "schema_version": "run_usage_v0",
        "measurement_kind": measurement_kind,
        "source_snapshot_id": source_snapshot_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "provider": "codex",
        "model": MODEL,
    }
    if cache_tokens is not None:
        usage["cache_tokens"] = cache_tokens
    if duration_ms is not None:
        usage["duration_ms"] = duration_ms
    return json.dumps(
        {
            "generated_at": generated_at,
            "classification": "state_refreshed",
            "json_path": f"runs/{generated_at}.json",
            "markdown_path": f"runs/{generated_at}.md",
            "usage": usage,
        }
    )


def test_session_usage_baseline_missing_index_means_first_observation(
    tmp_path: Path,
) -> None:
    assert session_usage_baseline(tmp_path / "index.jsonl", SESSION_ID) is None


def test_session_usage_baseline_telescopes_only_its_own_session_rows(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "index.jsonl"
    index_path.write_text(
        "\n".join(
            [
                _index_row(
                    generated_at="2026-08-26T01:05:00",
                    source_snapshot_id=f"codex:{SESSION_ID}:t1",
                    measurement_kind="absolute",
                    input_tokens=100,
                    output_tokens=10,
                    cache_tokens=20,
                    duration_ms=1000,
                ),
                _index_row(
                    generated_at="2026-08-26T01:06:00",
                    source_snapshot_id=f"codex:{OTHER_SESSION_ID}:t1",
                    measurement_kind="absolute",
                    input_tokens=50,
                    output_tokens=5,
                ),
                _index_row(
                    generated_at="2026-08-26T01:07:00",
                    source_snapshot_id=f"codex:{SESSION_ID}:t2",
                    measurement_kind="delta",
                    input_tokens=40,
                    output_tokens=4,
                    cache_tokens=10,
                    duration_ms=500,
                ),
                json.dumps({"generated_at": "2026-08-26T01:08:00"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    basis = session_usage_baseline(index_path, SESSION_ID)
    assert basis is not None
    assert basis["input_tokens"] == 140
    assert basis["output_tokens"] == 14
    assert basis["cache_tokens"] == 30
    assert basis["duration_ms"] == 1500
    assert basis["cost_usd"] is None
    assert basis["source_snapshot_id"] == f"codex:{SESSION_ID}:t2"
    assert basis["provider"] == "codex"
    assert basis["model"] == MODEL

    other = session_usage_baseline(index_path, OTHER_SESSION_ID)
    assert other is not None
    assert other["input_tokens"] == 50


def test_session_usage_baseline_fails_closed_on_corrupt_index_row(
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "index.jsonl"
    index_path.write_text('{"generated_at": "2026-08-26T01:05:00"\n', encoding="utf-8")
    with pytest.raises(CodexSessionUsageError, match="row 1 is corrupt"):
        session_usage_baseline(index_path, SESSION_ID)


@pytest.mark.parametrize(
    ("mutation", "error_match"),
    [
        ({"input_tokens": 1200.5}, "input_tokens must be a whole number"),
        ({"duration_ms": 300_000.5}, "duration_ms must be a whole number"),
        ({"schema_version": None}, "schema_version"),
        ({"measurement_kind": "estimate"}, "measurement_kind"),
        ({"provider": "other-provider"}, "provider must be codex"),
    ],
    ids=[
        "fractional-token",
        "fractional-duration",
        "missing-schema",
        "illegal-measurement-kind",
        "wrong-provider",
    ],
)
def test_book_codex_session_usage_fails_closed_on_invalid_baseline_without_appending(
    tmp_path: Path,
    mutation: dict[str, Any],
    error_match: str,
) -> None:
    rollout = _fixture_rollout(tmp_path)
    index_path = tmp_path / "index.jsonl"
    persisted_row = json.loads(
        _index_row(
            generated_at="2026-08-26T01:05:00",
            source_snapshot_id=f"codex:{SESSION_ID}:2026-08-26T01:05:00.000Z",
            measurement_kind="absolute",
            input_tokens=1200,
            output_tokens=300,
            cache_tokens=200,
            duration_ms=300_000,
        )
    )
    persisted_row["usage"].update(mutation)
    if "schema_version" in mutation and mutation["schema_version"] is None:
        persisted_row["usage"].pop("schema_version", None)
    index_path.write_text(json.dumps(persisted_row) + "\n", encoding="utf-8")
    index_before_retry = index_path.read_bytes()
    record: dict[str, Any] = {}
    index_record: dict[str, Any] = {}

    with pytest.raises(CodexSessionUsageError, match=error_match):
        book_codex_session_usage(
            record,
            rollout,
            index_path,
            index_record=index_record,
        )

    assert index_path.read_bytes() == index_before_retry
    assert "usage" not in record
    assert "usage" not in index_record


def _goal_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text("# Active Goal State\n", encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runtime_root = tmp_path / "runtime"
    return registry_path, project, runtime_root


def _refresh(
    *,
    registry_path: Path,
    runtime_root: Path,
    project: Path,
    usage_codex_session: Path | None = None,
    usage_measurement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        project=project,
        state_file=None,
        classification="state_refreshed",
        recommended_action="Observe the usage fixture.",
        usage_codex_session=usage_codex_session,
        usage_measurement=usage_measurement,
        dry_run=False,
        sync_global=False,
    )


def _index_runs(runtime_root: Path) -> list[dict[str, Any]]:
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    return [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _summary_totals(runtime_root: Path) -> dict[str, Any]:
    runs = _index_runs(runtime_root)
    for run in runs:
        run.setdefault("goal_id", GOAL_ID)
    summary = build_usage_summary({"runs": runs}, parse_timestamp=parse_timestamp)
    return summary["totals"]


def test_refresh_state_codex_session_produces_non_zero_usage_summary(
    tmp_path: Path,
) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout = _fixture_rollout(tmp_path)

    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )
    assert payload["ok"] is True
    assert payload["usage"]["schema_version"] == "run_usage_v0"

    runs = _index_runs(runtime_root)
    assert len(runs) == 1
    usage = runs[0]["usage"]
    assert usage["input_tokens"] == 1200
    assert usage["output_tokens"] == 300
    assert usage["cache_tokens"] == 200
    assert usage["provider"] == "codex"
    assert usage["model"] == MODEL

    totals = _summary_totals(runtime_root)
    assert totals["input_tokens_24h"] == 1200
    assert totals["output_tokens_24h"] == 300
    assert totals["cache_tokens_24h"] == 200
    assert totals["duration_ms_24h"] == 300_000


def test_refresh_state_replaying_same_snapshot_does_not_double_count(
    tmp_path: Path,
) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout = _fixture_rollout(tmp_path)

    for _ in range(2):
        payload = _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_codex_session=rollout,
        )
        assert payload["ok"] is True

    runs = _index_runs(runtime_root)
    assert len(runs) == 2
    replay_usage = runs[1]["usage"]
    assert replay_usage["measurement_kind"] == "delta"
    assert replay_usage["input_tokens"] == 0
    assert replay_usage["output_tokens"] == 0

    totals = _summary_totals(runtime_root)
    assert totals["input_tokens_24h"] == 1200
    assert totals["output_tokens_24h"] == 300
    # The appended index row is the basis advancement itself: there is no
    # second snapshot state file that a crash between writes could leave stale.
    runs_dir = runtime_root / "goals" / GOAL_ID / "runs"
    assert not (runs_dir / "usage_snapshot.json").exists()


def test_refresh_state_replays_snapshot_after_model_context_change(
    tmp_path: Path,
) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout = _fixture_rollout(tmp_path)
    _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )
    with rollout.open("a", encoding="utf-8") as handle:
        handle.write(_rollout_model_context("gpt-fixture-2") + "\n")

    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )

    assert payload["usage"]["model"] == MODEL
    runs = _index_runs(runtime_root)
    assert runs[1]["usage"]["measurement_kind"] == "delta"
    assert runs[1]["usage"]["input_tokens"] == 0
    assert runs[1]["usage"]["model"] == MODEL

    with rollout.open("a", encoding="utf-8") as handle:
        handle.write(
            _rollout_event(
                "2026-08-26T01:10:00.000Z",
                input_tokens=2000,
                cached_input_tokens=350,
                output_tokens=450,
            )
            + "\n"
        )
    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )

    assert payload["usage"]["model"] == "gpt-fixture-2"
    runs = _index_runs(runtime_root)
    increment = runs[2]["usage"]
    assert increment["measurement_kind"] == "delta"
    assert increment["input_tokens"] == 800
    assert increment["output_tokens"] == 150
    assert increment["cache_tokens"] == 150
    assert increment["model"] == "gpt-fixture-2"

    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )

    assert payload["usage"]["model"] == "gpt-fixture-2"
    runs = _index_runs(runtime_root)
    replay = runs[3]["usage"]
    assert replay["measurement_kind"] == "delta"
    assert replay["input_tokens"] == 0
    assert replay["output_tokens"] == 0
    assert replay["model"] == "gpt-fixture-2"


def test_refresh_state_books_only_the_cumulative_increment(tmp_path: Path) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout = _fixture_rollout(tmp_path)
    _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )

    with rollout.open("a", encoding="utf-8") as handle:
        handle.write(
            _rollout_event(
                "2026-08-26T01:10:00.000Z",
                input_tokens=2000,
                cached_input_tokens=350,
                output_tokens=450,
            )
            + "\n"
        )
    _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout,
    )

    runs = _index_runs(runtime_root)
    increment = runs[1]["usage"]
    assert increment["measurement_kind"] == "delta"
    assert increment["input_tokens"] == 800
    assert increment["output_tokens"] == 150
    assert increment["cache_tokens"] == 150
    assert increment["duration_ms"] == 300_000

    totals = _summary_totals(runtime_root)
    assert totals["input_tokens_24h"] == 2000
    assert totals["output_tokens_24h"] == 450


def test_refresh_state_interleaved_sessions_do_not_double_count(
    tmp_path: Path,
) -> None:
    """A returning session must rebase against its own baseline (A, B, A)."""
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout_a = _write_rollout(
        tmp_path / "rollout-a.jsonl",
        [
            *_rollout_header(),
            _rollout_event(
                "2026-08-26T01:05:00.000Z",
                input_tokens=100,
                cached_input_tokens=0,
                output_tokens=10,
            ),
        ],
    )
    rollout_b = _write_rollout(
        tmp_path / "rollout-b.jsonl",
        [
            *_rollout_header(session_id=OTHER_SESSION_ID),
            _rollout_event(
                "2026-08-26T01:06:00.000Z",
                input_tokens=50,
                cached_input_tokens=0,
                output_tokens=5,
            ),
        ],
    )

    for rollout in (rollout_a, rollout_b):
        _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_codex_session=rollout,
        )
    with rollout_a.open("a", encoding="utf-8") as handle:
        handle.write(
            _rollout_event(
                "2026-08-26T01:10:00.000Z",
                input_tokens=150,
                cached_input_tokens=0,
                output_tokens=15,
            )
            + "\n"
        )
    _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_codex_session=rollout_a,
    )

    runs = _index_runs(runtime_root)
    assert len(runs) == 3
    returning = runs[2]["usage"]
    assert returning["measurement_kind"] == "delta"
    assert returning["input_tokens"] == 50  # 150 cumulative - 100 own baseline
    assert returning["output_tokens"] == 5

    totals = _summary_totals(runtime_root)
    assert totals["input_tokens_24h"] == 200  # 150 (A) + 50 (B), never 300
    assert totals["output_tokens_24h"] == 20


def test_refresh_state_concurrent_same_session_bookings_do_not_double_count(
    tmp_path: Path,
) -> None:
    """The booking lock serializes basis read + append: exactly one non-zero booking."""
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    rollout = _fixture_rollout(tmp_path)
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _book() -> None:
        try:
            barrier.wait(timeout=10)
            _refresh(
                registry_path=registry_path,
                runtime_root=runtime_root,
                project=project,
                usage_codex_session=rollout,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced via assertion below
            errors.append(exc)

    workers = [threading.Thread(target=_book) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
    assert errors == []

    runs = _index_runs(runtime_root)
    assert len(runs) == 2
    booked_inputs = sorted(run["usage"]["input_tokens"] for run in runs)
    assert booked_inputs == [0, 1200]  # one absolute intake, one zero-delta replay

    totals = _summary_totals(runtime_root)
    assert totals["input_tokens_24h"] == 1200
    assert totals["output_tokens_24h"] == 300


def test_refresh_state_never_persists_non_finite_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Durable run rows are strict JSON even if a future producer bug slips NaN through."""
    registry_path, project, runtime_root = _goal_fixture(tmp_path)

    def _inject_nan(
        record: dict[str, Any],
        measurement: dict[str, Any] | None = None,
        *,
        previous_snapshot: Any = None,
        index_record: dict[str, Any] | None = None,
    ) -> None:
        poisoned = {
            "schema_version": "run_usage_v0",
            "measurement_kind": "absolute",
            "source_snapshot_id": "poisoned",
            "input_tokens": 1,
            "output_tokens": 1,
            "provider": "codex",
            "model": MODEL,
            "cost_usd": float("nan"),
        }
        record["usage"] = poisoned
        if index_record is not None:
            index_record["usage"] = dict(poisoned)

    monkeypatch.setattr(
        state_refresh_module, "ingest_usage_into_run_record", _inject_nan
    )
    with pytest.raises(ValueError, match="JSON compliant"):
        _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_measurement={"input_tokens": 1, "output_tokens": 1},
        )
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    assert not index_path.exists()


def test_refresh_state_rejects_non_finite_measurement(tmp_path: Path) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    with pytest.raises(UsageRowError, match="finite"):
        _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_measurement={
                "input_tokens": 1,
                "output_tokens": 1,
                "provider": "fixture-host",
                "model": "fixture-model",
                "source_snapshot_id": "host-measured-nan",
                "cost_usd": float("nan"),
            },
        )
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    assert not index_path.exists()


def test_refresh_state_without_usage_flags_keeps_usage_unknown(
    tmp_path: Path,
) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
    )
    assert payload["ok"] is True
    assert "usage" not in payload
    runs = _index_runs(runtime_root)
    assert "usage" not in runs[0]


def test_refresh_state_accepts_typed_host_measurement(tmp_path: Path) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    payload = _refresh(
        registry_path=registry_path,
        runtime_root=runtime_root,
        project=project,
        usage_measurement={
            "input_tokens": 42,
            "output_tokens": 7,
            "provider": "fixture-host",
            "model": "fixture-model",
            "source_snapshot_id": "host-measured-1",
        },
    )
    assert payload["ok"] is True
    runs = _index_runs(runtime_root)
    assert runs[0]["usage"]["input_tokens"] == 42
    assert runs[0]["usage"]["provider"] == "fixture-host"


def test_refresh_state_rejects_combined_usage_inputs(tmp_path: Path) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    with pytest.raises(ValueError, match="cannot be combined"):
        _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_codex_session=_fixture_rollout(tmp_path),
            usage_measurement={"input_tokens": 1, "output_tokens": 1},
        )


def test_refresh_state_fails_closed_on_malformed_rollout_without_appending(
    tmp_path: Path,
) -> None:
    registry_path, project, runtime_root = _goal_fixture(tmp_path)
    bad_rollout = _write_rollout(
        tmp_path / "rollout-bad.jsonl", _rollout_header()
    )
    with pytest.raises(CodexSessionUsageError, match="no token_count"):
        _refresh(
            registry_path=registry_path,
            runtime_root=runtime_root,
            project=project,
            usage_codex_session=bad_rollout,
        )
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    assert not index_path.exists()
