#!/usr/bin/env python3
"""Validate the public long-horizon self-iteration rollout fixture."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT
    / "examples"
    / "fixtures"
    / "long-horizon-self-iteration-rollout.public.json"
)

PRIVATE_PATTERNS = [
    re.compile(r"/" + r"Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/" + "private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b" + "depart" + "ment" + r"\b", re.IGNORECASE),
    re.compile("\u90e8\u95e8"),
    re.compile("\u6c47\u62a5"),
]

REQUIRED_BOUNDARY_FALSE = {
    "raw_task_text_recorded",
    "raw_logs_recorded",
    "raw_trajectory_recorded",
    "raw_session_transcript_recorded",
    "credential_values_recorded",
    "absolute_paths_recorded",
}

ALLOWED_CONFIDENCE = {
    "observed",
    "inferred_high",
    "inferred_medium",
    "synthetic_bridge",
}


def assert_public_safe(text: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"fixture matched private pattern {pattern.pattern!r}")


def assert_boundary(payload: dict, label: str) -> None:
    boundary = payload.get("boundary")
    assert isinstance(boundary, dict), (label, boundary)
    for key in REQUIRED_BOUNDARY_FALSE:
        assert boundary.get(key) is False, (label, key, boundary)


def main() -> int:
    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
    assert_public_safe(fixture_text)
    payload = json.loads(fixture_text)

    assert payload["schema_version"] == "long_horizon_self_iteration_fixture_v0", payload
    assert payload["goal_id"] == "public-long-horizon-loop", payload
    assert payload["truth_contract"]["event_ledger_is_source_of_truth"] is True, payload
    assert payload["truth_contract"]["fixture_is_writable"] is False, payload
    assert payload["truth_contract"]["projection_is_writable"] is False, payload
    assert payload["truth_contract"]["write_authority"] == "none", payload

    state_partitioning = payload["state_partitioning"]
    assert state_partitioning["schema_version"] == "long_horizon_state_partitioning_v0", state_partitioning
    canonical_stream = state_partitioning["canonical_stream"]
    assert canonical_stream["goal_id"] == payload["goal_id"], state_partitioning
    assert canonical_stream["event_stream_count"] == 1, state_partitioning
    assert "rollout_event_log" in canonical_stream["source_surfaces"], state_partitioning
    derived_contract = state_partitioning["derived_view_contract"]
    assert derived_contract["views_are_writable"] is False, state_partitioning
    assert derived_contract["must_reference_canonical_events"] is True, state_partitioning

    public_boundary = payload["public_boundary"]
    for key in REQUIRED_BOUNDARY_FALSE:
        assert public_boundary.get(key) is False, (key, public_boundary)
    assert public_boundary.get("private_material_body_recorded") is False, public_boundary

    lanes = {lane["lane_id"]: lane for lane in payload["lanes"]}
    assert {"release_validation", "product_capability", "implementation_lane"} <= set(
        lanes
    ), lanes
    assert lanes["implementation_lane"]["agent_id"] == "codex-side-bypass", lanes

    rollout_events = payload["rollout_events"]
    assert len(rollout_events) >= 7, rollout_events
    event_ids = [event["event_id"] for event in rollout_events]
    assert len(event_ids) == len(set(event_ids)), event_ids
    events_by_id = {event["event_id"]: event for event in rollout_events}
    event_lanes = {event.get("lane", {}).get("lane_id") for event in rollout_events}
    assert {"implementation_lane", "product_capability"} <= event_lanes, event_lanes

    derived_views = payload["derived_views"]
    assert {view["view_kind"] for view in derived_views} == {
        "per_agent",
        "per_todo",
        "per_case",
        "per_run",
    }, derived_views
    for view in derived_views:
        assert view["projection_is_writable"] is False, view
        source_event_ids = view["source_event_ids"]
        assert source_event_ids, view
        for event_id in source_event_ids:
            assert event_id in events_by_id, (view, event_id)
        filter_keys = view["filter_keys"]
        if view["view_kind"] == "per_agent":
            assert any(
                event.get("agent_id") == filter_keys["agent_id"]
                or event.get("lane", {}).get("lane_id") == filter_keys["lane_id"]
                for event in (events_by_id[event_id] for event_id in source_event_ids)
            ), view
        if view["view_kind"] == "per_todo":
            assert all(
                events_by_id[event_id].get("todo_id") == filter_keys["todo_id"]
                for event_id in source_event_ids
            ), view
        if view["view_kind"] == "per_case":
            assert all(
                events_by_id[event_id].get("case_id") == filter_keys["case_id"]
                for event_id in source_event_ids
            ), view
        if view["view_kind"] == "per_run":
            assert all(
                events_by_id[event_id].get("run_id") == filter_keys["run_id"]
                for event_id in source_event_ids
            ), view

    saw_gate = False
    saw_handoff = False
    saw_validation = False
    saw_pr_ref = False
    saw_deferred_resume = False

    for event in rollout_events:
        assert event["schema_version"] == "loopx_rollout_event_v0", event
        assert event["goal_id"] == "public-long-horizon-loop", event
        assert_boundary(event, event["event_id"])
        assert event.get("summary"), event
        assert not any(str(ref).startswith("/") for ref in event.get("artifact_refs", [])), event
        causality = event.get("causality", {})
        if causality.get("gate_id") == "gate_minimal_rollout_fixture":
            saw_gate = True
        if event.get("handoff", {}).get("to_agent_id") == "codex-side-bypass":
            saw_handoff = True
        if event["event_kind"] == "validation":
            saw_validation = True
        if event.get("code_refs", {}).get("pr_ref"):
            saw_pr_ref = True
        transition = event.get("state_transition", {})
        if transition.get("from_state", "").startswith("deferred"):
            saw_deferred_resume = True

    assert saw_gate, "human/fixture gate missing"
    assert saw_handoff, "peer handoff missing"
    assert saw_validation, "validation event missing"
    assert saw_pr_ref, "PR evidence missing"
    assert saw_deferred_resume, "deferred-to-ready transition missing"

    animation_events = payload["animation_events"]
    assert len(animation_events) >= 6, animation_events
    animation_ids = [event["animation_event_id"] for event in animation_events]
    assert len(animation_ids) == len(set(animation_ids)), animation_ids
    assert any(event["kind"] == "human_gate" for event in animation_events), animation_events
    assert any(event["display_hint"] == "dashed_edge" for event in animation_events), animation_events
    assert any(event["confidence"] == "synthetic_bridge" for event in animation_events), animation_events
    for event in animation_events:
        assert event["confidence"] in ALLOWED_CONFIDENCE, event
        assert event["lane_id"] in lanes, event
        assert event.get("source_event_ids"), event

    must_render = set(payload["frontend_acceptance"]["must_render"])
    assert "three agent lanes" in must_render, must_render
    assert "one human gate node" in must_render, must_render
    assert "one dashed inferred bridge" in must_render, must_render

    print("long-horizon-self-iteration-rollout-fixture smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
