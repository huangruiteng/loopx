#!/usr/bin/env python3
"""Smoke-test the fixture-only content-ops exploration plan packet."""

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

from loopx.content_ops_surface import (  # noqa: E402
    CONTENT_OPS_EXPLORATION_PLAN_PACKET_SCHEMA_VERSION,
    EXPLORATION_PLAN_SCHEMA_VERSION,
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
    "full chat transcript",
    "raw platform post body",
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
    result = run_cli(["--format", "json", "content-ops", "exploration-plan"])
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == CONTENT_OPS_EXPLORATION_PLAN_PACKET_SCHEMA_VERSION
    assert payload["mode"] == "content-ops-exploration-plan", payload
    assert payload["external_reads_performed"] is False, payload
    assert payload["external_writes_performed"] is False, payload
    assert payload["private_source_bodies_read"] is False, payload
    assert payload["private_source_content_read"] is False, payload
    assert payload["local_paths_captured"] is False, payload
    assert payload["autopublish_allowed"] is False, payload

    plan = payload["exploration_plan"]
    assert plan["schema_version"] == EXPLORATION_PLAN_SCHEMA_VERSION, plan
    assert plan["lane_counts"]["total"] == 4, plan["lane_counts"]
    assert plan["lane_counts"]["user_gate_required"] == 2, plan["lane_counts"]
    assert plan["first_screen"]["waiting_on"] == "user", plan["first_screen"]
    assert plan["first_screen"]["agent_can_continue"] is True, plan["first_screen"]
    assert plan["truth_contract"]["private_boundary_crossing_requires_user_gate"] is True

    lanes = plan["selected_source_lanes"]
    lane_ids = {lane["lane_id"] for lane in lanes}
    assert lane_ids == {
        "repo_issue_public_metadata",
        "public_social_signal_metadata",
        "private_chat_metadata_gate",
        "experiment_compact_result_metadata",
    }, lane_ids
    for lane in lanes:
        assert lane["source_body_captured"] is False, lane
        assert lane["response_payload_captured"] is False, lane
        assert lane["local_path_captured"] is False, lane
        assert lane["external_write_allowed"] is False, lane
        assert lane["route"], lane
        assert lane["fallback"], lane
        assert lane["promotion_target"], lane
        if lane["requires_user_gate"]:
            assert lane.get("user_gate", {}).get("question"), lane

    validation = payload["validation"]
    assert validation["ok"] is True, validation
    assert validation["lane_count"] == 4, validation
    assert validation["errors"] == [], validation
    assert_public_safe(payload)

    markdown = run_cli(["content-ops", "exploration-plan"]).stdout
    assert "LoopX Content-Ops Exploration Plan" in markdown, markdown
    assert "private_chat_metadata_gate" in markdown, markdown
    assert "experiment_compact_result_metadata" in markdown, markdown
    assert_public_safe(markdown)

    rejected = run_cli(
        [
            "--format",
            "json",
            "content-ops",
            "exploration-plan",
            "--scenario",
            "https://example.com/not-a-label",
        ],
        check=False,
    )
    assert rejected.returncode == 1, rejected
    rejected_payload = json.loads(rejected.stdout)
    assert rejected_payload["ok"] is False, rejected_payload
    assert "scenario must be a compact public-safe label" in rejected_payload["error"]

    print("content-ops-exploration-plan-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
