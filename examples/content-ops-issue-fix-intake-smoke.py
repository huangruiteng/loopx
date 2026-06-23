#!/usr/bin/env python3
"""Smoke-test the fixture-only repo issue fix intake packet."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.content_ops.surface import (  # noqa: E402
    EXPLORATION_PLAN_SCHEMA_VERSION,
)
from loopx.capabilities.issue_fix.intake_surface import (  # noqa: E402
    CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION,
    ISSUE_FIX_INTAKE_SCHEMA_VERSION,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

FORBIDDEN_VALUES = [
    "raw issue body text",
    "full issue comment text",
    "private repro log",
    "secret-value",
    "credential-value",
    "response payload text",
    "source body text",
]


def assert_public_safe(payload: dict[str, Any] | str) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")
    leaked = [value for value in FORBIDDEN_VALUES if value in text]
    assert not leaked, leaked


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    result = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "issue-fix-intake",
            "--repo",
            "OpenViking/Viking",
            "--issue-ref",
            "issue_123_public_metadata",
        ]
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION
    assert payload["mode"] == "content-ops-issue-fix-intake", payload
    assert payload["exploration_plan_schema_version"] == EXPLORATION_PLAN_SCHEMA_VERSION
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["local_paths_captured"] is False, payload
    assert payload["autopublish_allowed"] is False, payload
    assert payload["automerge_allowed"] is False, payload

    intake = payload["issue_fix_intake"]
    assert intake["schema_version"] == ISSUE_FIX_INTAKE_SCHEMA_VERSION, intake
    first_screen = intake["first_screen"]
    assert first_screen["waiting_on"] == "agent", first_screen
    assert first_screen["user_action_required"] is False, first_screen
    assert first_screen["agent_can_continue"] is True, first_screen
    assert "public issue metadata fixture" in first_screen["next_safe_action"]

    issue_metadata = intake["issue_metadata"]
    assert issue_metadata["source_kind"] == "github_issue_or_pr", issue_metadata
    assert issue_metadata["source_status"] == "public", issue_metadata
    assert issue_metadata["repo"] == "OpenViking/Viking", issue_metadata
    assert issue_metadata["body_captured"] is False, issue_metadata
    assert issue_metadata["comment_bodies_captured"] is False, issue_metadata
    assert issue_metadata["private_repo_state_read"] is False, issue_metadata

    lane = intake["selected_exploration_lane"]
    assert lane["lane_id"] == "repo_issue_public_metadata", lane
    assert lane["requires_user_gate"] is False, lane
    assert lane["source_body_captured"] is False, lane
    assert lane["external_write_allowed"] is False, lane

    routes = intake["code_context_routes"]
    assert {route["route_id"] for route in routes} == {
        "route_reproduction_surface",
        "route_owner_or_component_inference",
    }, routes
    for route in routes:
        assert route["requires_private_repo_state"] is False, route
        assert route["reads_private_material"] is False, route
        for glob in route["candidate_path_globs"]:
            assert not glob.startswith("/"), route

    todos = intake["agent_todo_candidates"]
    assert [todo["role"] for todo in todos] == ["agent", "agent", "agent"], todos
    assert todos[0]["action_kind"] == "issue_fix_repro_smoke", todos
    assert all(todo["validation_surface"] for todo in todos), todos

    gates = intake["gate_projections"]
    assert {gate["gate_id"] for gate in gates} == {
        "owner_triage_gate",
        "private_repro_material_gate",
    }, gates
    assert all(gate["action_required"] is False for gate in gates), gates
    assert any(gate["role"] == "user" for gate in gates), gates

    validation = payload["validation"]
    assert validation["ok"] is True, validation
    assert validation["route_count"] == 2, validation
    assert validation["agent_todo_candidate_count"] == 3, validation
    assert validation["gate_projection_count"] == 2, validation
    assert validation["errors"] == [], validation
    assert_public_safe(payload)

    markdown = run_cli(["content-ops", "issue-fix-intake"]).stdout
    assert "LoopX Repo Issue Fix Intake" in markdown, markdown
    assert "issue_fix_repro_smoke" in markdown, markdown
    assert "private_repro_material_gate" in markdown, markdown
    assert_public_safe(markdown)

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "issue-fix-intake",
            "--repo",
            "https://example.com/not-a-label",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "repo must be a compact public-safe label" in rejected_payload["error"]

    print("content-ops-issue-fix-intake-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
