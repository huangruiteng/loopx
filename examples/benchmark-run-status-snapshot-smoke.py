#!/usr/bin/env python3
"""Smoke-test compact benchmark run status snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from loopx.rollout_event_log import (  # noqa: E402
    load_rollout_events,
    rollout_event_log_path,
)


SCRIPT = REPO / "scripts" / "benchmark_run_status_snapshot.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gh-benchmark-status-") as tmp:
        root = Path(tmp)
        run = root / "terminal-case-r1"
        work = run / "host-agent-work" / "host-codex-goal-abc"
        work.mkdir(parents=True)
        running_run = root / "skills-case-running-r1"
        running_run.mkdir()
        (running_run / "status.env").write_text("running\n", encoding="utf-8")
        (running_run / "pid.private").write_text(str(os.getpid()), encoding="utf-8")
        failure_run = root / "swe-case-terminal-failure-r1"
        failure_run.mkdir()
        (failure_run / "status.env").write_text("rc=1\n", encoding="utf-8")
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
        (failure_run / "materialization.compact.json").write_text(
            json.dumps(
                {
                    "compact_benchmark_run": {
                        "benchmark_id": "swe-marathon",
                        "case_id": "swe-case",
                        "ready_for_compact_failure_marker": True,
                        "compact_failure_class": (
                            "detached_worker_ended_without_trial_result"
                        ),
                        "external_handle_terminal": True,
                    }
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
                "--label",
                "skills-case-running-r1",
                "--label",
                "swe-case-terminal-failure-r1",
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
        running_item = payload["runs"][1]
        failure_item = payload["runs"][2]
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
        closeout_policy = item["observable_handle_policy"]
        assert closeout_policy["schema_version"] == (
            "benchmark_observable_handle_policy_v0"
        )
        assert closeout_policy["one_shot_expected"] is True
        assert closeout_policy["keep_alive_allowed"] is False
        assert closeout_policy["duplicate_rerun_allowed"] is False
        assert closeout_policy["terminal_closeout"] is True
        assert closeout_policy["compact_result_closeout"] is True
        assert closeout_policy["cleanup_required"] is True
        assert closeout_policy["disable_scheduler_label_required"] is True
        assert closeout_policy["unload_launchd_label_required"] is True
        assert closeout_policy["monitor_poll_allowed"] is False
        assert closeout_policy["boundary"]["local_paths_recorded"] is False
        running_policy = running_item["observable_handle_policy"]
        assert running_policy["terminal_closeout"] is False
        assert running_policy["cleanup_required"] is False
        assert running_policy["monitor_poll_allowed"] is True
        assert running_policy["next_action"] == "poll_observable_handle"
        failure_policy = failure_item["observable_handle_policy"]
        assert failure_policy["terminal_closeout"] is True
        assert failure_policy["compact_failure_closeout"] is True
        assert failure_policy["cleanup_required"] is True
        assert failure_policy["blocker_required_before_rerun"] is False
        assert "secret raw transcript" not in proc.stdout
        assert str(root) not in proc.stdout

        runtime_root = root / "runtime"
        rollout_proc = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--run-root",
                str(root),
                "--label",
                "terminal-case-r1",
                "--label",
                "skills-case-running-r1",
                "--label",
                "swe-case-terminal-failure-r1",
                "--pattern",
                "Working",
                "--record-rollout-event",
                "--goal-id",
                "rollout-status-smoke",
                "--runtime-root",
                str(runtime_root),
                "--agent-id",
                "codex-main-control",
                "--todo-id",
                "todo_status_smoke",
                "--pretty",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rollout_payload = json.loads(rollout_proc.stdout)
        assert rollout_payload["rollout_event"]["event_kind"] == "benchmark_status"
        assert rollout_payload["rollout_event"]["status"] == "running"
        assert str(root) not in rollout_proc.stdout
        events = load_rollout_events(
            rollout_event_log_path(runtime_root, "rollout-status-smoke")
        )
        assert len(events) == 1, events
        event = events[0]
        assert event["event_kind"] == "benchmark_status", event
        assert event["status"] == "running", event
        assert event["details"]["run_count"] == 3, event
        assert event["details"]["pid_alive_count"] == 2, event
        assert event["details"]["compact_result_count"] == 3, event
        assert event["details"]["terminal_closeout_count"] == 2, event
        assert event["details"]["cleanup_required_count"] == 2, event
        assert event["details"]["monitor_poll_allowed_count"] == 1, event
        assert event["details"]["blocker_required_count"] == 0, event
        assert event["boundary"]["raw_logs_recorded"] is False, event
        assert event["boundary"]["absolute_paths_recorded"] is False, event

    print("benchmark run status snapshot smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
