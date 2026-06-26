#!/usr/bin/env python3
"""Smoke-test the public global_manager_command_v0 contract and fixture."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "global-manager-command-v0.md"
INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
LONG_HORIZON_PATH = (
    REPO_ROOT / "docs" / "reference" / "protocols" / "long-horizon-agent-state-protocol-v0.md"
)
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "global-manager-command.public.json"

REQUIRED_COMMANDS = {
    "/loopx-global-summary",
    "/loopx-global-gates",
    "/loopx-global-todos",
    "/loopx-global-risks",
    "/loop-goal-summary",
}
LEGACY_COMMAND_ALIASES = {
    "/loop-global-summary",
    "/loop-global-gates",
    "/loop-global-todos",
    "/loop-global-risks",
}
REJECTED_COMMAND_ALIASES = {
    "/loopx-summary-all",
}

REQUIRED_BOUNDARY_FALSE = {
    "raw_logs_recorded",
    "raw_transcripts_recorded",
    "raw_connector_payloads_recorded",
    "credential_values_recorded",
    "absolute_paths_recorded",
    "private_source_bodies_recorded",
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


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


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

    assert_contains(index, "global_manager_command_v0", "protocol index")
    assert_contains(long_horizon, "global_manager_command_v0", "long horizon protocol")
    for command in REQUIRED_COMMANDS:
        assert_contains(contract, command, "command set")
    for command in LEGACY_COMMAND_ALIASES:
        assert_contains(contract, command, "legacy alias note")
    for command in REJECTED_COMMAND_ALIASES:
        if command in contract:
            raise AssertionError(f"command set should not include superseded alias {command!r}")
    for needle in [
        "read-only by default",
        "Action Ladder",
        "Privacy Boundary",
        "global_manager_command_response_v0",
        "python3 examples/global-manager-command-protocol-smoke.py",
    ]:
        assert_contains(contract, needle, "global manager command contract")

    payload = json.loads(fixture_text)
    assert payload["schema_version"] == "global_manager_command_response_v0", payload
    request = payload["request"]
    assert request["schema_version"] == "global_manager_command_request_v0", request
    assert request["command"] in REQUIRED_COMMANDS, request
    assert "/loop-global-summary" in request.get("legacy_aliases", []), request
    assert request["privacy_mode"] == "public_safe_summary", request
    assert request["dry_run"] is True, request

    summary = payload["summary"]
    for key in ("headline", "progress_count", "open_gate_count", "runnable_todo_count", "risk_count"):
        assert key in summary, summary

    lanes = payload["lanes"]
    assert lanes and all(item.get("goal_id") and item.get("agent_id") for item in lanes), lanes
    assert all(item.get("next_safe_action") for item in lanes), lanes

    actions = payload["actions"]
    assert actions, actions
    assert any(action["kind"] == "promote_todo" and action["requires_user_approval"] for action in actions)
    assert any(action["kind"] == "review" and action["requires_primary_agent"] for action in actions)

    boundary = payload["boundary"]
    for key in REQUIRED_BOUNDARY_FALSE:
        assert boundary.get(key) is False, (key, boundary)

    omissions = " ".join(payload.get("omissions") or [])
    assert "Raw logs" in omissions and "private source bodies" in omissions, omissions

    print("global-manager-command-protocol-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
