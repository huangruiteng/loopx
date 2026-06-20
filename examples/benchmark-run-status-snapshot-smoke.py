#!/usr/bin/env python3
"""Smoke-test compact benchmark run status snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "benchmark_run_status_snapshot.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gh-benchmark-status-") as tmp:
        root = Path(tmp)
        run = root / "terminal-case-r1"
        work = run / "host-agent-work" / "host-codex-goal-abc"
        work.mkdir(parents=True)
        requests = work / "requests"
        requests.mkdir()
        (requests / "abc.request.json").write_text("{}", encoding="utf-8")
        (requests / "def.response.json").write_text("{}", encoding="utf-8")
        (run / "status.env").write_text("rc=0\n", encoding="utf-8")
        (run / "pid.private").write_text(str(os.getpid()), encoding="utf-8")
        (work / "tmux_capture.txt").write_text(
            "Working\nsecret raw transcript should never be emitted\n",
            encoding="utf-8",
        )
        (run / "result.compact.json").write_text(
            json.dumps(
                {
                    "compact_benchmark_run": {
                        "benchmark_id": "terminal-bench",
                        "case_id": "terminal-case",
                        "official_score_status": "completed",
                        "official_score": 1.0,
                    }
                }
            ),
            encoding="utf-8",
        )
        (work / "app_server_goal_turn.compact.json").write_text(
            json.dumps(
                {
                    "schema_version": "codex_app_server_goal_turn_driver_v0",
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "goal_status": "active",
                    "turn_id_present": True,
                    "raw_transcript_recorded": False,
                    "notifications": ["thread/goal/updated", "thread/started"],
                }
            ),
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--run-root",
                str(root),
                "--label",
                "terminal-case-r1",
                "--pattern",
                "Working",
                "--pretty",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["schema_version"] == "benchmark_run_status_snapshot_v0"
        assert payload["boundary"]["raw_logs_emitted"] is False
        assert payload["boundary"]["local_paths_recorded"] is False
        assert payload["run_root_recorded"] is False
        item = payload["runs"][0]
        assert item["status"] == "rc=0"
        assert item["run_dir_recorded"] is False
        assert item["pid_alive"] is True
        summaries = [result["summary"] for result in item["compact_results"]]
        assert any(summary.get("official_score") == 1.0 for summary in summaries)
        goal_summaries = [
            summary
            for summary in summaries
            if summary.get("schema_version") == "codex_app_server_goal_turn_driver_v0"
        ]
        assert goal_summaries
        assert goal_summaries[0]["goal_get_present"] is True
        assert goal_summaries[0]["goal_status"] == "active"
        assert goal_summaries[0]["turn_id_present"] is True
        assert goal_summaries[0]["raw_transcript_recorded"] is False
        assert item["bridge_request_dirs"][0]["json_count"] == 2
        assert item["bridge_request_dirs"][0]["request_count"] == 1
        assert item["bridge_request_dirs"][0]["response_count"] == 1
        assert item["capture_files"][0]["patterns"]["Working"] is True
        assert "secret raw transcript" not in proc.stdout
        assert str(root) not in proc.stdout

    print("benchmark run status snapshot smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
