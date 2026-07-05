#!/usr/bin/env python3
"""Smoke-test the read-only agent-scoped evidence-log CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


GOAL_ID = "agent-evidence-fixture"
AGENT_ID = "agent-a"
TODO_ID = "todo_target"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n")


def write_fixture(root: Path) -> Path:
    runtime = root / "runtime"
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "fixture",
                        "status": "active-read-only",
                        "adapter": {"kind": "fixture", "status": "connected-read-only"},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl(
        runtime / "goals" / GOAL_ID / "rollout-event-log.jsonl",
        [
            {
                "schema_version": "loopx_rollout_event_v0",
                "goal_id": GOAL_ID,
                "event_id": "evt-agent-a",
                "event_kind": "todo_update",
                "recorded_at": "2026-07-05T00:00:01Z",
                "agent_id": AGENT_ID,
                "todo_id": TODO_ID,
                "status": "open",
                "summary": "authorization token label is safe as prose",
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "raw_session_transcript_recorded": False,
                    "credential_values_recorded": False,
                    "absolute_paths_recorded": False,
                },
            },
            {
                "schema_version": "loopx_rollout_event_v0",
                "goal_id": GOAL_ID,
                "event_id": "evt-aksk",
                "event_kind": "todo_update",
                "recorded_at": "2026-07-05T00:00:02Z",
                "agent_id": AGENT_ID,
                "todo_id": TODO_ID,
                "status": "open",
                "summary": "sk=should-not-surface",
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "raw_session_transcript_recorded": False,
                    "credential_values_recorded": False,
                    "absolute_paths_recorded": False,
                },
            },
            {
                "schema_version": "loopx_rollout_event_v0",
                "goal_id": GOAL_ID,
                "event_id": "evt-access-secret",
                "event_kind": "todo_update",
                "recorded_at": "2026-07-05T00:00:03Z",
                "agent_id": AGENT_ID,
                "todo_id": TODO_ID,
                "status": "open",
                "summary": "access_key=should-not-surface",
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "raw_session_transcript_recorded": False,
                    "credential_values_recorded": False,
                    "absolute_paths_recorded": False,
                },
            },
            {
                "schema_version": "loopx_rollout_event_v0",
                "goal_id": GOAL_ID,
                "event_id": "evt-other-agent",
                "event_kind": "todo_update",
                "recorded_at": "2026-07-05T00:00:04Z",
                "agent_id": "agent-b",
                "todo_id": TODO_ID,
                "status": "open",
                "summary": "other agent private stream should not expand",
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "raw_session_transcript_recorded": False,
                    "credential_values_recorded": False,
                    "absolute_paths_recorded": False,
                },
            },
        ],
    )
    write_jsonl(
        runtime / "goals" / GOAL_ID / "runs" / "index.jsonl",
        [
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:04+00:00",
                "agent_id": AGENT_ID,
                "classification": "agent_a_progress",
                "recommended_action": f"continue {TODO_ID}",
                "health_check": "compact only",
            },
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:05+00:00",
                "agent_id": "agent-b",
                "classification": "agent_b_old_frontier_should_not_surface",
                "recommended_action": "old other-agent run should not surface",
                "health_check": "compact only",
            },
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:06+00:00",
                "agent_id": "agent-e",
                "classification": "agent_e_frontier",
                "recommended_action": "fourth other-agent run exceeds frontier cap",
                "health_check": "compact only",
            },
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:07+00:00",
                "agent_id": "agent-d",
                "classification": "agent_d_frontier",
                "recommended_action": "other agent d top todo only",
                "health_check": "compact only",
            },
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:08+00:00",
                "agent_id": "agent-c",
                "classification": "agent_c_frontier",
                "recommended_action": "other agent c top todo only",
                "health_check": "compact only",
            },
            {
                "goal_id": GOAL_ID,
                "generated_at": "2026-07-05T00:00:09+00:00",
                "agent_id": "agent-b",
                "classification": "agent_b_frontier",
                "recommended_action": "other agent top todo only",
                "health_check": "compact only",
            },
        ],
    )
    return registry_path


def run_cli(registry_path: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            "evidence-log",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            TODO_ID,
            "--thin",
            "--limit",
            "10",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = run_cli(write_fixture(Path(tmp)))
    assert payload["ok"] is True
    assert payload["schema_version"] == "agent_scoped_evidence_log_v0"
    assert payload["goal_id"] == GOAL_ID
    assert payload["agent_id"] == AGENT_ID
    assert payload["todo_id"] == TODO_ID
    assert payload["rollout_event_count"] == 3
    assert payload["run_history_ref_count"] == 1
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "authorization token label is safe as prose" in rendered
    assert "sk=should-not-surface" not in rendered
    assert "access_key=should-not-surface" not in rendered
    assert "other agent private stream should not expand" not in rendered
    assert "agent_b_old_frontier_should_not_surface" not in rendered
    assert "agent_e_frontier" not in rendered
    assert payload["other_agent_frontier"]["item_count"] == 3
    assert [item["agent_id"] for item in payload["other_agent_frontier"]["items"]] == [
        "agent-b",
        "agent-c",
        "agent-d",
    ]
    assert payload["boundary"]["other_agent_event_stream_expanded"] is False
    assert payload["boundary"]["credential_values_recorded"] is False


if __name__ == "__main__":
    main()
