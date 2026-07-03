#!/usr/bin/env python3
"""Smoke-test the local state write correctness protocol example."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "docs" / "reference" / "protocols" / "local-state-write-correctness-v0.md"
README = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"


def extract_example_packet(text: str) -> dict[str, Any]:
    marker = "## Example Packet"
    start = text.index(marker)
    match = re.search(r"```json\n(.*?)\n```", text[start:], re.DOTALL)
    assert match, "Example Packet must include a JSON code block"
    return json.loads(match.group(1))


def require_path(packet: dict[str, Any], path: str) -> Any:
    current: Any = packet
    for part in path.split("."):
        assert isinstance(current, dict) and part in current, f"missing {path}"
        current = current[part]
    return current


def main() -> int:
    text = PROTOCOL.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    packet = extract_example_packet(text)

    assert packet["schema_version"] == "local_state_write_correctness_v0", packet
    assert "local_state_write_correctness_v0" in readme, "README must list the protocol"

    intent = require_path(packet, "write_intent")
    for field in (
        "write_id",
        "goal_id",
        "writer_id",
        "write_class",
        "target_refs",
        "idempotency_key",
        "expected_revision",
        "lease_ref",
    ):
        assert intent.get(field), f"write_intent missing {field}"

    assert require_path(packet, "lock_boundary.kind") == "per_goal"
    assert require_path(packet, "preview.mode") == "dry_run"
    assert require_path(packet, "preview.non_destructive") is True
    assert require_path(packet, "apply_result.status") in {
        "applied",
        "already_applied",
        "skipped_duplicate",
        "lock_busy",
        "revision_conflict",
        "lease_conflict",
        "boundary_rejected",
        "preview_only",
        "failed",
    }

    lease_projection = require_path(packet, "projection.lease_projection")
    assert lease_projection["todo_id"] == intent["target_refs"]["todo_id"]
    assert lease_projection["claimed_by"] == intent["lease_ref"]["claimed_by"]

    boundary = require_path(packet, "projection.public_boundary")
    for field in (
        "raw_logs_copied",
        "private_paths_copied",
        "credentials_copied",
        "production_action_authorized",
    ):
        assert boundary.get(field) is False, f"unsafe boundary flag {field}"

    required_phrases = [
        "idempotency_key",
        "expected_revision",
        "per goal",
        "per-todo lock",
        "lease projection",
        "revision_conflict",
        "boundary_rejected",
    ]
    compact = " ".join(text.split()).lower()
    for phrase in required_phrases:
        assert phrase.lower() in compact, f"protocol missing phrase: {phrase}"

    print("local-state-write-correctness-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
