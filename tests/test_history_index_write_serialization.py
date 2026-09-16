"""Refs GH-C07: per-goal history index writers share one lock.

`write_reserved_run_artifacts` appends to `<runs>/index.jsonl` while
`repair_index_duplicates` rewrites that same file from a snapshot. If only one
side locks, an append that lands after the repair reads the index is still lost,
so the durable invariant is that **both** sides take the lock for the **same**
path. These cases pin that, plus the rule that a dry-run repair stays read-only
and does not block writers.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest

from loopx import history

GOAL_ID = "goal-history-lock"


@pytest.fixture
def record_lock_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Capture every lock path taken through the history module."""
    taken: list[Path] = []
    real_lock = history.exclusive_file_lock

    @contextmanager
    def recording_lock(path: Path, **_kwargs: Any) -> Iterator[Path]:
        taken.append(path)
        with real_lock(path) as locked:
            yield locked

    monkeypatch.setattr(history, "exclusive_file_lock", recording_lock)
    return taken


def _write_artifacts(runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-09-16T00:00:00+00:00"
    history.write_reserved_run_artifacts(
        runs_dir=runs_dir,
        generated_at=generated_at,
        record={"goal_id": GOAL_ID, "generated_at": generated_at},
        index_record={"goal_id": GOAL_ID, "generated_at": generated_at},
        payload={"goal_id": GOAL_ID, "generated_at": generated_at},
        render_markdown=lambda payload: "# record\n",
    )
    return runs_dir / "index.jsonl"


def test_append_takes_the_goal_index_lock(tmp_path: Path, record_lock_calls: list[Path]) -> None:
    index_path = _write_artifacts(tmp_path / "runs")

    assert record_lock_calls == [index_path], record_lock_calls
    assert index_path.exists()


def test_append_is_visible_after_the_lock_released(
    tmp_path: Path, record_lock_calls: list[Path]
) -> None:
    index_path = _write_artifacts(tmp_path / "runs")

    rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["goal_id"] for row in rows] == [GOAL_ID]


def _history_fixture(root: Path) -> tuple[Path, Path]:
    runtime_root = root / "runtime"
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"goal_id": GOAL_ID, "generated_at": "2026-09-16T00:00:00+00:00", "kind": "run"}
    index_path.write_text(
        "".join(json.dumps(row) + "\n" for _ in range(2)), encoding="utf-8"
    )
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime_root),
                "projects": [],
                "goals": [],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, runtime_root


def test_repair_locks_the_same_index_path_on_execute(
    tmp_path: Path, record_lock_calls: list[Path]
) -> None:
    registry_path, runtime_root = _history_fixture(tmp_path)
    index_path = runtime_root / "goals" / GOAL_ID / "runs" / "index.jsonl"

    history.repair_index_duplicates(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        limit=10,
        execute=True,
    )

    assert record_lock_calls == [index_path], record_lock_calls


def test_repair_dry_run_does_not_take_the_write_lock(
    tmp_path: Path, record_lock_calls: list[Path]
) -> None:
    registry_path, runtime_root = _history_fixture(tmp_path)

    result = history.repair_index_duplicates(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        limit=10,
        execute=False,
    )

    assert result["dry_run"] is True
    assert record_lock_calls == [], "a read-only repair must not block writers"
