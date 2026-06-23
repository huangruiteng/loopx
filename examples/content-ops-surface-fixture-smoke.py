#!/usr/bin/env python3
"""Smoke-test content_ops_surface_v0 fixture, validation, and projection."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.content_ops_surface import (  # noqa: E402
    CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION,
    CONTENT_OPS_SURFACE_SCHEMA_VERSION,
    build_content_ops_surface_fixture,
    project_content_ops_surface,
    validate_content_ops_surface,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

REQUIRED_RECORD_GROUPS = {
    "source_items",
    "angle_candidates",
    "draft_items",
    "feedback_signals",
    "publish_gates",
    "material_memory",
    "connector_trials",
}

REQUIRED_OPERATOR_STATES = {
    "waiting_for_source_review",
    "ready_to_draft",
    "waiting_for_feedback",
    "ready_for_publish_decision",
    "safe_side_work_available",
}


def assert_public_safe(payload: dict[str, object], label: str) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")
    forbidden_values = [
        "full chat transcript",
        "raw platform post body",
        "secret-value",
        "credential-value",
    ]
    leaked = [value for value in forbidden_values if value in text]
    assert not leaked, (label, leaked)


def assert_fixture_contract(surface: dict[str, object]) -> None:
    assert surface["schema_version"] == CONTENT_OPS_SURFACE_SCHEMA_VERSION, surface
    assert surface["mode"] == "compact_state_surface", surface
    for group in REQUIRED_RECORD_GROUPS:
        records = surface[group]
        assert isinstance(records, list) and records, (group, records)
    assert REQUIRED_OPERATOR_STATES.issubset(set(surface["operator_states"])), surface

    boundary = surface["boundary"]
    assert isinstance(boundary, dict), boundary
    assert boundary["public_safe"] is True, boundary
    assert boundary["raw_private_material_recorded"] is False, boundary
    assert boundary["raw_platform_data_recorded"] is False, boundary
    assert boundary["credentials_recorded"] is False, boundary
    assert boundary["autopublish_allowed"] is False, boundary
    assert boundary["publish_requires_user_gate"] is True, boundary

    sources = surface["source_items"]
    assert isinstance(sources, list), sources
    statuses = {item["source_status"] for item in sources}
    assert {"synthetic_public_safe", "private_needs_review"}.issubset(statuses), statuses
    assert all(item["freshness"] for item in sources), sources
    assert all(item["allowed_use"] for item in sources), sources

    drafts = surface["draft_items"]
    assert isinstance(drafts, list), drafts
    for draft in drafts:
        assert draft["source_map"], draft
        assert draft["publish_gate_id"], draft
        assert draft["validation_surface"], draft

    gates = surface["publish_gates"]
    assert isinstance(gates, list), gates
    for gate in gates:
        assert gate["approval_required"] is True, gate
        assert gate["autopublish_allowed"] is False, gate
        assert gate["status"] == "blocked_until_user_approval", gate

    connector_trials = surface["connector_trials"]
    assert isinstance(connector_trials, list) and len(connector_trials) == 2, (
        connector_trials
    )
    surfaces = {trial["surface"] for trial in connector_trials}
    assert {"x_public_feed", "wechat_private_archive"} == surfaces, connector_trials
    access_modes = {trial["access_mode"] for trial in connector_trials}
    assert {"public_metadata_only", "private_metadata_only"} == access_modes, (
        connector_trials
    )
    assert all(trial["external_write_allowed"] is False for trial in connector_trials), (
        connector_trials
    )
    private_trials = [
        trial
        for trial in connector_trials
        if trial["access_mode"] == "private_metadata_only"
    ]
    assert private_trials and private_trials[0]["requires_user_gate"] is True, (
        connector_trials
    )


def assert_projection_contract(projection: dict[str, object]) -> None:
    assert (
        projection["schema_version"]
        == CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION
    ), projection
    assert projection["mode"] == "read_only", projection
    first_screen = projection["first_screen"]
    assert isinstance(first_screen, dict), first_screen
    assert first_screen["waiting_on"] == "user", first_screen
    assert first_screen["user_action_required"] is True, first_screen
    assert first_screen["agent_can_continue"] is True, first_screen
    assert first_screen["safe_side_work_available"] is True, first_screen
    assert first_screen["source_review_required_count"] == 1, first_screen
    assert first_screen["ready_to_draft_count"] == 1, first_screen
    assert first_screen["publish_decision_count"] == 1, first_screen

    truth = projection["truth_contract"]
    assert isinstance(truth, dict), truth
    assert truth["projection_is_writable"] is False, truth
    assert truth["write_authority"] == "none", truth
    assert truth["publish_gate_required"] is True, truth
    assert truth["autopublish_allowed"] is False, truth
    assert truth["raw_private_material_copied"] is False, truth

    validation = projection["validation"]
    assert isinstance(validation, dict), validation
    assert validation["ok"] is True, validation
    assert validation["raw_material_key_names"] == [], validation
    assert set(validation["record_counts"]) == REQUIRED_RECORD_GROUPS, validation

    todo_candidates = projection["todo_candidates"]
    assert isinstance(todo_candidates, list) and len(todo_candidates) >= 3, (
        todo_candidates
    )
    roles = {candidate["role"] for candidate in todo_candidates}
    assert {"agent", "user"}.issubset(roles), todo_candidates
    action_kinds = {candidate["action_kind"] for candidate in todo_candidates}
    assert "content_ops_draft_from_angle" in action_kinds, todo_candidates
    assert "content_ops_source_review" in action_kinds, todo_candidates
    assert "content_ops_publish_gate" in action_kinds, todo_candidates
    assert "content_ops_connector_metadata_trial" in action_kinds, todo_candidates
    assert "content_ops_connector_owner_gate" in action_kinds, todo_candidates

    connector_projection = projection["connector_trials"]
    assert isinstance(connector_projection, dict), connector_projection
    assert connector_projection["count"] == 2, connector_projection
    assert connector_projection["ready_for_metadata_trial_count"] == 1, (
        connector_projection
    )
    assert connector_projection["owner_gate_required_count"] == 1, (
        connector_projection
    )
    assert connector_projection["surfaces"] == {
        "wechat_private_archive": 1,
        "x_public_feed": 1,
    }, connector_projection


def main() -> int:
    surface = build_content_ops_surface_fixture()
    validation = validate_content_ops_surface(surface)
    projection = project_content_ops_surface(surface)

    assert validation["ok"] is True, validation
    assert validation["errors"] == [], validation
    assert_fixture_contract(surface)
    assert_projection_contract(projection)
    assert_public_safe(surface, "surface")
    assert_public_safe(projection, "projection")
    print("content-ops-surface-fixture-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
