#!/usr/bin/env python3
"""Smoke-test the public rollback_packet_v0 contract and fixture."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "rollback-packet-v0.md"
INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
LONG_HORIZON_PATH = (
    REPO_ROOT / "docs" / "reference" / "protocols" / "long-horizon-agent-state-protocol-v0.md"
)
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "rollback-packet.public.json"

ALLOWED_TRIGGER_KINDS = {
    "validation_regression",
    "public_boundary_leak",
    "operator_request",
    "external_setup_partial_failure",
    "wrong_owner_or_lane",
    "bad_state_projection",
    "release_or_publish_mistake",
}

ALLOWED_STEP_KINDS = {
    "git_revert",
    "fix_forward",
    "history_rewrite",
    "state_compensation",
    "external_cleanup",
    "support_request",
    "todo_supersede",
    "validation",
}

REQUIRED_BOUNDARY_FALSE = {
    "raw_task_text_recorded",
    "raw_logs_recorded",
    "raw_trajectory_recorded",
    "raw_session_transcript_recorded",
    "credential_values_recorded",
    "absolute_paths_recorded",
}

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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def main() -> int:
    contract = read(CONTRACT_PATH)
    index = read(INDEX_PATH)
    long_horizon = read(LONG_HORIZON_PATH)
    fixture_text = read(FIXTURE_PATH)

    for label, text in {
        "contract": contract,
        "protocol index": index,
        "long horizon protocol": long_horizon,
        "fixture": fixture_text,
    }.items():
        assert_public_safe(text, label)

    for needle in [
        "rollback_packet_v0",
        "Commit And Todo Linkage",
        "history_rewrite",
        "explicit user or maintainer approval",
        "support_request",
        "todo_compensation",
        "python3 examples/protocol/rollback-packet-protocol-smoke.py",
    ]:
        assert_contains(contract, needle, "rollback contract")
    assert_contains(index, "rollback_packet_v0", "protocol index")
    assert_contains(long_horizon, "rollback_packet_v0", "long horizon protocol")

    payload = json.loads(fixture_text)
    assert payload["schema_version"] == "rollback_packet_v0", payload
    assert payload["trigger"]["kind"] in ALLOWED_TRIGGER_KINDS, payload
    assert payload["trigger"]["todo_ids"], payload
    assert payload["trigger"]["source_event_ids"], payload
    assert payload["scope"]["repository_refs"]["commit_refs"], payload
    assert payload["scope"]["repository_refs"]["pr_refs"], payload
    assert payload["scope"]["external_resource_refs"], payload
    assert payload["decision"]["required"] is True, payload

    plan = payload["plan"]
    assert isinstance(plan, list) and len(plan) >= 3, plan
    step_ids = [step["step_id"] for step in plan]
    assert len(step_ids) == len(set(step_ids)), step_ids
    for step in plan:
        assert step["kind"] in ALLOWED_STEP_KINDS, step
        for key in ("action", "requires_gate", "destructive", "automatable_by_agent"):
            assert key in step, step
        if step["destructive"] or step["kind"] in {"history_rewrite", "support_request"}:
            assert step["requires_gate"] is True, step
            assert step["automatable_by_agent"] is False, step

    compensation = payload["todo_compensation"]
    assert compensation["complete_todo_ids"], compensation
    assert compensation["add_todos"], compensation
    assert compensation["add_todos"][0]["task_class"] == "continuous_monitor", compensation

    validation = payload["validation"]
    assert validation["commands"], validation
    assert validation["public_boundary_scan_required"] is True, validation
    assert validation["success_criteria"], validation

    boundary = payload["boundary"]
    for key in REQUIRED_BOUNDARY_FALSE:
        assert boundary.get(key) is False, (key, boundary)

    print("rollback-packet-protocol-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
