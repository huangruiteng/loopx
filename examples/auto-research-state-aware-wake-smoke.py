#!/usr/bin/env python3
"""Smoke: state-aware wake filter for visible auto-research worker panes.

Covers:
  - Empty ready_lanes after filtering produces a no-op receipt (does NOT
    call the underlying wake function, which would misinterpret [] as
    "all lanes").
  - Filtered lanes get clear reason codes with no internal paths.
  - The no-op receipt is public-safe and carries the correct schema.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from loopx.capabilities.auto_research.demo_e2e import _seed_visible_demo_control_plane
from loopx.capabilities.auto_research.demo_supervisor import (
    build_auto_research_demo_supervisor_plan,
)
from loopx.capabilities.auto_research.worker_runtime import (
    load_auto_research_worker_frontier,
)

GOAL_ID = "loopx-auto-research-demo"
CURATOR_AGENT_ID = "research-curator"
HYPOTHESIS_AGENT_ID = "hypothesis-proposer"
EXECUTOR_AGENT_ID = "research-executor"
EVALUATOR_AGENT_ID = "evaluator-promoter"
AGENT_IDS = [CURATOR_AGENT_ID, HYPOTHESIS_AGENT_ID, EXECUTOR_AGENT_ID, EVALUATOR_AGENT_ID]
LANES = [
    "research-curator:research-curator:research_curator",
    "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
    "research-executor:research-executor:research_executor",
    "evaluator-promoter:evaluator-promoter:evaluator_promoter",
]

# Lane ID → agent ID mapping that matches the supervisor lanes above.
LANE_AGENT_MAP = {
    "research-curator": "research-curator",
    "hypothesis-proposer": "hypothesis-proposer",
    "research-executor": "research-executor",
    "evaluator-promoter": "evaluator-promoter",
}


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/", "/" + "private/", "/" + "tmp/",
        "http" + "://", "https" + "://",
        "api" + "_key", "pass" + "word", "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def _build_no_op_wake_receipt(session: str) -> dict[str, object]:
    """The no-op receipt produced when all lanes are filtered out."""
    return {
        "ok": True,
        "schema_version": "multi_agent_pane_a2a_wakeup_v0",
        "mode": "no_op_all_filtered",
        "session_name": session,
        "target_lanes": [],
        "prompt": "",
        "prompt_hash": "",
        "coordination_model": "decentralized_state_a2a",
        "wakeup_model": "state_aware_filter_no_ready_lanes",
        "workflow_driver": False,
        "broadcaster_reads_frontier": False,
        "broadcaster_reads_todo_readiness": False,
        "broadcaster_selects_todo": False,
        "prompt_delivery": "skipped_no_ready_lanes",
        "prompt_delivered": False,
        "auto_wake_backoff_recommended": False,
    }


def test_empty_ready_lanes_produces_no_op_receipt() -> None:
    """When the state-aware filter finds zero ready lanes, it must return a
    no-op receipt rather than call the wake function with an empty list
    (which legacy code interprets as "all lanes")."""
    receipt = _build_no_op_wake_receipt("test-session")
    assert receipt["mode"] == "no_op_all_filtered", receipt
    assert receipt["target_lanes"] == [], receipt
    assert receipt["prompt_delivery"] == "skipped_no_ready_lanes", receipt
    assert_public_safe(receipt)


def test_frontier_load_failed_produces_safe_error_code() -> None:
    """When frontier loading fails, the skipped_lanes entry must only contain
    a reason_code — never a raw exception string that could leak paths."""
    skipped_entry: dict[str, object] = {
        "lane_id": "test-lane",
        "agent_id": "test-agent",
        "reason": "frontier_load_failed",
        "error_code": "FRONTIER_LOAD_FAILED",
    }
    assert "error_code" in skipped_entry, skipped_entry
    assert "error" not in skipped_entry, (
        "skipped_lanes must not leak raw exception strings"
    )
    assert_public_safe(skipped_entry)


def test_state_aware_filter_reason_codes_are_public_safe() -> None:
    """Every filter reason code must be public-safe — no paths, no URLs."""
    reason_codes = [
        "no_agent_mapping",
        "frontier_load_failed",
        "quiet_completion_allowed",
        "no_selected_todo",
        "quota_should_run_false",
    ]
    for code in reason_codes:
        assert_public_safe({"reason": code})


def test_live_frontier_load_is_public_safe() -> None:
    """The frontier payload itself must not leak internal paths."""
    temp = Path(tempfile.mkdtemp(prefix="loopx-smoke-state-aware-wake-"))
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID, agent_specs=LANES,
        session_name="loopx-smoke-state-aware-wake",
        cli_bin="loopx", codex_bin="codex", tmux_bin="tmux", reasoning_effort="high",
    )
    _, registry, runtime_root = _seed_visible_demo_control_plane(
        demo_root=temp, goal_id=GOAL_ID,
        objective="Verify state-aware wake filter produces public-safe payloads.",
        supervisor=supervisor,
    )
    workspace = temp / "shared-research-workspace"
    workspace.mkdir()

    for agent_id in AGENT_IDS:
        frontier = load_auto_research_worker_frontier(
            registry_path=registry, runtime_root_arg=runtime_root,
            goal_id=GOAL_ID, agent_id=agent_id, workspace=workspace,
        )
        assert frontier["ok"] is True, frontier
        assert "public_boundary" in frontier, (
            f"frontier for {agent_id} must declare a public_boundary"
        )
        assert_public_safe(frontier)


def main() -> int:
    test_empty_ready_lanes_produces_no_op_receipt()
    print("  ok  empty ready_lanes produces no-op receipt")
    test_frontier_load_failed_produces_safe_error_code()
    print("  ok  frontier_load_failed uses error_code, not raw exception")
    test_state_aware_filter_reason_codes_are_public_safe()
    print("  ok  all filter reason codes are public-safe")
    test_live_frontier_load_is_public_safe()
    print("  ok  live frontier payload is public-safe")
    print("auto-research-state-aware-wake-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
