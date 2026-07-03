#!/usr/bin/env python3
"""Smoke-test the local state write correctness runtime promotion gate."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "docs" / "reference" / "protocols" / "local-state-write-correctness-v0.md"


def extract_gate_packet(text: str) -> dict[str, Any]:
    marker = "## Runtime Promotion Gate"
    start = text.index(marker)
    match = re.search(r"```json\n(.*?)\n```", text[start:], re.DOTALL)
    assert match, "Runtime Promotion Gate must include a JSON code block"
    return json.loads(match.group(1))


def main() -> int:
    text = PROTOCOL.read_text(encoding="utf-8")
    packet = extract_gate_packet(text)

    assert packet["schema_version"] == "local_state_write_correctness_rollout_gate_v0", packet
    assert packet["current_mode"] == "dry_run_preview", packet
    assert packet["promotion_target"] == "shadow_validate", packet
    assert packet["allowed_to_change_write_behavior"] is False, packet

    required = packet["required_evidence"]
    for field in (
        "dry_run_packet_smoke",
        "idempotency_key_stability",
        "expected_revision_fixture",
        "revision_conflict_fixture",
        "lease_projection_fixture",
        "public_boundary_scan",
    ):
        assert required.get(field), f"promotion gate missing evidence: {field}"

    exit_criteria = " ".join(packet["exit_criteria"])
    for phrase in (
        "dry-run JSON and markdown",
        "duplicate retries",
        "revision and lease conflicts",
        "compact public-safe write refs",
    ):
        assert phrase in exit_criteria, f"promotion gate missing exit criterion: {phrase}"

    compact = " ".join(text.split())
    assert "must not reject or rewrite a previously accepted real write" in compact
    assert "separate validated step" in compact

    print("local-state-write-correctness-rollout-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
