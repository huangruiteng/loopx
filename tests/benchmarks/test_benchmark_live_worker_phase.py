from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.benchmark_adapters.terminal_bench import (
    summarize_terminal_bench_post_launch_materialization,
)
from loopx.benchmark_core import (
    build_benchmark_live_worker_phase,
    compact_benchmark_live_worker_phase,
)


def test_live_worker_phase_closes_sparse_higher_phase_evidence() -> None:
    phase = build_benchmark_live_worker_phase(agent_active=True)

    assert phase["current_phase"] == "agent_active"
    assert all(phase["phase_ready"].values())
    assert phase["worker_live"] is True
    assert phase["agent_active_observed"] is True
    assert phase["terminal"] is False
    assert phase["terminal_disposition"] == "open"
    assert phase["next_required_phase"] == ""


def test_live_worker_phase_terminal_state_is_orthogonal_to_progress() -> None:
    phase = build_benchmark_live_worker_phase(
        worker_running=True,
        terminal_disposition="ended_unresolved",
    )

    assert phase["current_phase"] == "worker_running"
    assert phase["worker_live"] is False
    assert phase["terminal"] is True
    assert phase["terminal_disposition"] == "ended_unresolved"
    assert phase["next_required_phase"] == ""
    assert (
        compact_benchmark_live_worker_phase(
            {**phase, "private_detail": "not projected"}
        )
        == phase
    )

    with pytest.raises(ValueError, match="terminal_disposition"):
        build_benchmark_live_worker_phase(terminal_disposition="unknown")


def test_terminal_bench_public_fixture_projects_running_worker_phase(
    tmp_path: Path,
) -> None:
    jobs_dir = tmp_path / "jobs"
    job_root = jobs_dir / "terminal_bench_public_live_worker"
    job_root.mkdir(parents=True)
    (job_root / "lock.json").write_text("{}\n", encoding="utf-8")
    (job_root / "result.json").write_text(
        json.dumps(
            {
                "started_at": "2026-07-23T00:00:00Z",
                "updated_at": "2026-07-23T00:00:01Z",
                "finished_at": None,
                "stats": {
                    "n_running_trials": 1,
                    "n_pending_trials": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_terminal_bench_post_launch_materialization(
        jobs_dir,
        job_name=job_root.name,
        detached_process_state="running",
    )

    phase = summary["benchmark_live_worker_phase"]
    assert phase["current_phase"] == "worker_running"
    assert phase["worker_live"] is True
    assert phase["agent_active_observed"] is False
    assert phase["terminal_disposition"] == "open"
    assert phase["public_evidence_only"] is True
    assert summary["raw_logs_read"] is False
    assert summary["raw_task_text_read"] is False
    assert str(tmp_path) not in json.dumps(summary, sort_keys=True)
