#!/usr/bin/env python3
"""Smoke-test the public session-runtime read-only projection contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.session_runtime import (  # noqa: E402
    SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION,
    build_session_runtime_readonly_projection,
)
from loopx.status import build_attention_queue, build_run_history, render_status_markdown  # noqa: E402


LOCAL_PATH_FIXTURE = "/" + "private" + "/tmp/raw-run.log"


def assert_no_raw_values(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden_values = (
        LOCAL_PATH_FIXTURE,
        "full transcript body",
        "credential-value",
        "secret-value",
    )
    leaked = [value for value in forbidden_values if value in text]
    assert not leaked, leaked


def test_operator_gate_first_screen() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="demo-goal",
        sessions=[
            {
                "session_id": "session-1",
                "created_at": "2026-01-01T00:00:00Z",
                "summary": "runtime finished preflight",
            }
        ],
        gates=[
            {
                "gate_id": "gate-1",
                "status": "pending",
                "actor": "operator",
                "question": "Approve read-only evidence import?",
                "blocking": True,
            }
        ],
        decision_results=[
            {
                "artifact_id": "decision-1",
                "recommended_action": "continue only after compact gate approval",
            }
        ],
    )
    assert (
        payload["schema_version"]
        == SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION
    ), payload
    assert payload["mode"] == "read_only", payload
    assert payload["boundary"]["runtime_writeback_allowed"] is False, payload
    assert payload["first_screen"]["waiting_on"] == "operator", payload
    assert payload["first_screen"]["user_action_required"] is True, payload
    assert payload["first_screen"]["agent_can_continue"] is False, payload
    assert (
        payload["first_screen"]["first_user_todo"]
        == "Approve read-only evidence import?"
    ), payload
    assert payload["first_screen"]["first_agent_todo"] is None, payload
    assert payload["work_lane_contract"]["lane"] == "user_gate", payload
    assert payload["attention_item"]["priority"] == "P0", payload
    assert_no_raw_values(payload)


def test_agent_advancement_first_screen() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="demo-goal",
        sessions=[
            {
                "session_id": "session-2",
                "created_at": "2026-01-01T00:01:00Z",
                "next_action": "write compact adapter fixture",
            }
        ],
        events=[
            {
                "event_id": "event-1",
                "kind": "validation",
                "status": "passed",
                "event_at": "2026-01-01T00:02:00Z",
                "validation_summary": "contract smoke passed",
            }
        ],
        outcomes=[
            {
                "outcome_id": "outcome-1",
                "kind": "outcome",
                "status": "validated",
                "created_at": "2026-01-01T00:03:00Z",
                "validation_summary": "projection is public-safe",
            }
        ],
        decision_results=[
            {
                "artifact_id": "decision-2",
                "recommended_action": "wire adapter into status projection",
            }
        ],
    )
    assert payload["first_screen"]["waiting_on"] == "agent", payload
    assert payload["first_screen"]["user_action_required"] is False, payload
    assert payload["first_screen"]["agent_can_continue"] is True, payload
    assert (
        payload["first_screen"]["first_agent_todo"]
        == "wire adapter into status projection"
    ), payload
    assert payload["first_screen"]["latest_validation"] == (
        "projection is public-safe"
    ), payload
    assert payload["work_lane_contract"]["lane"] == "advancement_task", payload
    assert payload["work_lane_contract"]["must_attempt_work"] is True, payload
    assert_no_raw_values(payload)


def test_raw_material_is_flagged_not_copied() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="demo-goal",
        sessions=[
            {
                "session_id": "session-3",
                "created_at": "2026-01-01T00:03:00Z",
                "next_action": "continue compact projection",
                "raw_transcript": "full transcript body",
                "credential_hint": "credential-value",
            }
        ],
        events=[
            {
                "event_id": "event-raw",
                "kind": "blocker",
                "status": "blocked",
                "summary": "source summary contained raw fields",
                "local_path": LOCAL_PATH_FIXTURE,
                "secret": "secret-value",
            }
        ],
    )
    assert payload["boundary"]["raw_transcript_copied"] is False, payload
    assert payload["boundary"]["raw_logs_copied"] is False, payload
    assert payload["boundary"]["credentials_copied"] is False, payload
    assert payload["boundary"]["raw_material_detected"] is True, payload
    assert payload["first_screen"]["agent_can_continue"] is False, payload
    assert payload["first_screen"]["recommended_action"] == (
        "provide compact summaries without raw material before projection"
    ), payload
    assert "raw_transcript" in payload["boundary"]["raw_material_key_names"], payload
    assert "local_path" in payload["boundary"]["raw_material_key_names"], payload
    assert_no_raw_values(payload)


def test_status_ingests_projection_first_screen() -> None:
    payload = build_session_runtime_readonly_projection(
        goal_id="demo-goal",
        sessions=[
            {
                "session_id": "session-status-1",
                "created_at": "2026-01-01T00:04:00Z",
                "next_action": "continue compact projection",
            }
        ],
        events=[
            {
                "event_id": "event-status-1",
                "kind": "validation",
                "status": "passed",
                "event_at": "2026-01-01T00:05:00Z",
                "validation_summary": "status ingest smoke passed",
            }
        ],
        decision_results=[
            {
                "artifact_id": "decision-status-1",
                "recommended_action": "show session projection in status",
            }
        ],
    )
    run = {
        "generated_at": "2026-01-01T00:06:00Z",
        "goal_id": "demo-goal",
        "classification": "session_runtime_projection_recorded",
        "json_exists": True,
        "markdown_exists": True,
        "session_runtime_readonly_projection": payload,
    }
    history = {
        "goal_count": 1,
        "run_count": 1,
        "goals": [
            {
                "id": "demo-goal",
                "status": "active",
                "registry_member": True,
                "adapter_kind": "session_runtime",
                "adapter_status": "connected-read-only",
                "latest_runs": [run],
            }
        ],
        "runs": [run],
    }
    queue = build_attention_queue(
        contract={"ok": True},
        history=history,
        global_registry={"ok": True, "findings": []},
    )
    item = queue["items"][0]
    assert item["source"] == "session_runtime_projection", item
    assert item["waiting_on"] == "codex", item
    assert item["recommended_action"] == "show session projection in status", item
    projection = item["project_asset"]["session_runtime_projection"]
    assert projection["first_screen"]["first_agent_todo"] == (
        "show session projection in status"
    ), projection
    assert projection["boundary"]["runtime_writeback_allowed"] is False, projection
    assert "source_refs" not in projection.get("source", {}), projection
    assert projection["source"]["source_ref_counts"]["sessions"] == 1, projection

    run_history = build_run_history(history)
    compact_run = run_history["goals"][0]["latest_runs"][0]
    assert compact_run["session_runtime_projection"]["mode"] == "read_only", compact_run
    markdown = render_status_markdown(
        {
            "ok": True,
            "registry": "fixture",
            "runtime_root": "fixture",
            "goal_count": 1,
            "run_count": 1,
            "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
            "global_registry": {"available": True, "ok": True, "summary": {"findings": 0, "high": 0, "action": 0, "info": 0}},
            "attention_queue": queue,
            "run_history": run_history,
        }
    )
    assert "session_runtime_projection" in markdown, markdown
    assert "session_runtime_agent_todo" in markdown, markdown
    assert_no_raw_values(item)
    assert_no_raw_values(run_history)


def main() -> int:
    test_operator_gate_first_screen()
    test_agent_advancement_first_screen()
    test_raw_material_is_flagged_not_copied()
    test_status_ingests_projection_first_screen()
    print("session-runtime-readonly-projection-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
