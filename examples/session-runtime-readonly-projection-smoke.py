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


def assert_no_raw_values(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden_values = (
        "/private/tmp/raw-run.log",
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
                "local_path": "/private/tmp/raw-run.log",
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


def main() -> int:
    test_operator_gate_first_screen()
    test_agent_advancement_first_screen()
    test_raw_material_is_flagged_not_copied()
    print("session-runtime-readonly-projection-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
