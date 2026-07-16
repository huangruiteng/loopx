from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

from loopx.control_plane.runtime.run_artifacts import write_unique_run_artifacts


def _write_same_timestamp_monitor_artifact(runs_dir: str, worker_id: int) -> None:
    record = {
        "generated_at": "2026-07-17T00:00:00+08:00",
        "goal_id": "fixture-goal",
        "classification": "quota_monitor_poll",
        "monitor_event": {
            "todo_id": f"todo-{worker_id}",
            "target_key": f"monitor:fixture:{worker_id}",
        },
    }
    index_record = {
        "generated_at": record["generated_at"],
        "goal_id": record["goal_id"],
        "classification": record["classification"],
        "todo_id": record["monitor_event"]["todo_id"],
        "target_key": record["monitor_event"]["target_key"],
    }
    write_unique_run_artifacts(
        runs_dir=Path(runs_dir),
        stem="2026-07-17T00-00-00-08-00",
        suffix="quota-monitor-poll",
        record=record,
        markdown=f"# Monitor {worker_id}",
        index_record=index_record,
    )


def test_same_timestamp_multi_process_monitor_artifacts_keep_distinct_identity(
    tmp_path: Path,
) -> None:
    runs_dir = tmp_path / "runs"
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(
            target=_write_same_timestamp_monitor_artifact,
            args=(str(runs_dir), worker_id),
        )
        for worker_id in range(6)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    rows = [
        json.loads(line)
        for line in (runs_dir / "index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 6
    assert len({row["json_path"] for row in rows}) == 6
    assert len({row["markdown_path"] for row in rows}) == 6
    assert {row["todo_id"] for row in rows} == {
        f"todo-{worker_id}" for worker_id in range(6)
    }
    for row in rows:
        json_payload = json.loads(Path(row["json_path"]).read_text(encoding="utf-8"))
        assert json_payload["monitor_event"]["todo_id"] == row["todo_id"]
        assert Path(row["markdown_path"]).exists()
