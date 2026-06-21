#!/usr/bin/env python3
"""Smoke-test the long-task cadence policy contract."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "docs/long-task-cadence-policy.md"
DOCS_INDEX = REPO_ROOT / "docs/README.md"
GETTING_STARTED = REPO_ROOT / "docs/guides/getting-started.md"
INTERACTION_PATTERN = REPO_ROOT / "docs/interaction-pattern-catalog.md"

PRESETS = ["ultra-long", "long", "medium", "short"]
GRANULARITIES = [
    "status_only",
    "single_surface",
    "multi_surface",
    "implementation_plus_validation",
    "milestone",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def compact(text: str) -> str:
    return " ".join(text.split())


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def extract_json_block(text: str) -> dict:
    start = text.index("```json", text.index("## Public Fields"))
    body_start = text.index("\n", start) + 1
    end = text.index("```", body_start)
    return json.loads(text[body_start:end])


def main() -> int:
    policy = read(POLICY_PATH)
    policy_compact = compact(policy)
    docs_index = read(DOCS_INDEX)
    getting_started = read(GETTING_STARTED)
    interaction = read(INTERACTION_PATTERN)

    for preset in PRESETS:
        assert_contains(policy, f"`{preset}`", "policy preset table")

    for required in [
        "connected autonomous goals default to `long`",
        "visible TUI sessions default to `medium`",
        "`ultra-long` requires an explicit user/controller opt-in",
        "compact turn duration",
        "progress granularity",
        "Too-Small Batch Detection",
        "too_small_heartbeat_batch=true",
        "implementation_plus_validation_writeback",
        "validated_artifact",
        "state_writeback",
        "blocked_priority_fallback_visible",
        "They do not grant permissions",
    ]:
        assert_contains(policy, required, "policy")

    for granularity in GRANULARITIES:
        assert_contains(policy, granularity, "progress granularity")

    projection = extract_json_block(policy)
    cadence = projection["long_task_cadence"]
    assert cadence["schema_version"] == "long_task_cadence_policy_v0", cadence
    assert cadence["cadence_preset"] == "long", cadence
    assert cadence["preset_source"] == "connected_autonomous_default", cadence
    assert isinstance(cadence["turn_duration_minutes"], int), cadence
    assert cadence["progress_granularity"] in GRANULARITIES, cadence
    assert cadence["small_step_streak"] >= 2, cadence
    assert cadence["too_small_heartbeat_batch"] is True, cadence
    assert cadence["widen_next_turn"] is True, cadence

    for forbidden in [
        "conversation transcript",
        "raw local logs",
        "credentials",
        "production actions",
        "still stop or ask",
    ]:
        assert_contains(policy_compact, forbidden, "safety boundary")

    assert_contains(docs_index, "Long-task cadence policy", "docs index")
    assert_contains(getting_started, "Long-task cadence policy", "getting started")
    assert_contains(interaction, "IP-010 Cadence Widening", "interaction pattern")
    assert_contains(interaction, "small-step streak", "interaction pattern")

    print("long-task-cadence-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
