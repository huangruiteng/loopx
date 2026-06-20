#!/usr/bin/env python3
"""Validate public-safe Goal Harness rollout event logging."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.rollout_event_log import (  # noqa: E402
    build_rollout_event,
    append_rollout_event,
    load_rollout_events,
    rollout_event_log_path,
    summarize_rollout_events,
)


def assert_public_safe_text(text: str) -> None:
    forbidden = (
        "/" + "Users/",
        "/" + "root/",
        "/" + "private/",
        "trajectory" + ".json",
        "Auth" + "orization:",
        "goal-harness-" + "ecs",
        "115." + "190.",
    )
    for marker in forbidden:
        assert marker not in text, marker


def assert_boundary(payload: dict) -> None:
    boundary = payload["boundary"]
    assert boundary["raw_task_text_recorded"] is False, payload
    assert boundary["raw_logs_recorded"] is False, payload
    assert boundary["raw_trajectory_recorded"] is False, payload
    assert boundary["raw_session_transcript_recorded"] is False, payload
    assert boundary["credential_values_recorded"] is False, payload
    assert boundary["absolute_paths_recorded"] is False, payload


def run_script(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "goal_rollout_event_log.py"), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    assert_public_safe_text(result.stdout)
    return json.loads(result.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="goal-harness-rollout-event-log-") as tmp:
        runtime_root = Path(tmp) / "runtime"
        goal_id = "goal-harness-meta"
        log_path = rollout_event_log_path(runtime_root, goal_id)
        event = build_rollout_event(
            goal_id=goal_id,
            event_kind="quota_should_run",
            agent_id="codex-main-control",
            todo_id="todo_406bb256efd8",
            status="eligible",
            summary="Quota allowed one bounded rollout event-log slice.",
            artifact_refs=["docs/benchmark-developer-workflow.md"],
            details={"open_agent_todo_count": 2},
        )
        append_rollout_event(log_path, event)

        result_event = run_script(
            "append",
            "--goal-id",
            goal_id,
            "--runtime-root",
            str(runtime_root),
            "--event-kind",
            "compact_case_result",
            "--agent-id",
            "codex-main-control",
            "--todo-id",
            "todo_406bb256efd8",
            "--benchmark-id",
            "terminal-bench@2.0",
            "--case-id",
            "build-cython-ext",
            "--status",
            "precise_blocker",
            "--summary",
            "Compact case result reduced to public-safe failure attribution.",
            "--artifact-ref",
            "docs/research/long-horizon-agent-benchmarks/benchmark-case-analysis.json",
        )
        assert result_event["event_kind"] == "compact_case_result", result_event
        assert_boundary(result_event)

        session_root = Path(tmp) / "sessions"
        session_root.mkdir()
        (session_root / "rollout.jsonl").write_text(
            '{"raw":"this transcript body must not be read"}\n',
            encoding="utf-8",
        )
        session_event = run_script(
            "observe-codex-sessions",
            "--goal-id",
            goal_id,
            "--runtime-root",
            str(runtime_root),
            "--session-root",
            str(session_root),
            "--agent-id",
            "codex-main-control",
        )
        assert session_event["event_kind"] == "codex_session_observed", session_event
        assert session_event["private_source"] == {
            "kind": "codex_sessions_jsonl",
            "raw_values_recorded": False,
            "count": 1,
        }, session_event
        assert_boundary(session_event)

        events = load_rollout_events(log_path)
        summary = summarize_rollout_events(events, limit=5)
        assert summary["event_count"] == 3, summary
        assert summary["counts_by_kind"]["quota_should_run"] == 1, summary
        assert summary["counts_by_kind"]["compact_case_result"] == 1, summary
        assert summary["counts_by_kind"]["codex_session_observed"] == 1, summary
        assert_boundary(summary)
        rendered_summary = run_script(
            "summarize",
            "--goal-id",
            goal_id,
            "--runtime-root",
            str(runtime_root),
            "--limit",
            "3",
            "--pretty",
        )
        assert rendered_summary["event_count"] == 3, rendered_summary

        try:
            build_rollout_event(
                goal_id=goal_id,
                event_kind="validation",
                artifact_refs=["/" + "Users/bytedance/private-result.json"],
            )
        except ValueError:
            pass
        else:
            raise AssertionError("absolute artifact refs must be rejected")

        try:
            build_rollout_event(
                goal_id=goal_id,
                event_kind="validation",
                details={"raw_" + "trajectory_path": "trajectory" + ".json"},
            )
        except ValueError:
            pass
        else:
            raise AssertionError("raw/private detail keys must be rejected")

        assert_public_safe_text(log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
