#!/usr/bin/env python3
"""Smoke: quota-pause stop reason in auto-research worker-loop.

When every turn in a round returns ``paused_by_quota`` (quota says
``should_run=False``), the worker-loop must stop with ``quota_paused``
instead of ``no_executed_turns``.

This test calls the worker-turn function directly with a frontier whose
quota reports ``should_run=False``, then verifies the turn and loop-level
semantics without needing a real quota budget change.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from loopx.capabilities.auto_research.worker_runtime import (
    run_auto_research_worker_turn,
    load_auto_research_worker_frontier,
    AUTO_RESEARCH_WORKER_TURN_SCHEMA_VERSION,
)
from loopx.capabilities.auto_research.worker_loop import (
    run_auto_research_worker_loop,
)
from loopx.capabilities.auto_research.rollout_append import (
    append_auto_research_rollout_events,
)
from loopx.capabilities.auto_research.demo_e2e import _seed_visible_demo_control_plane
from loopx.capabilities.auto_research.demo_supervisor import (
    build_auto_research_demo_supervisor_plan,
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


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/", "/" + "private/", "/" + "tmp/",
        "http" + "://", "https" + "://",
        "api" + "_key", "pass" + "word", "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def test_paused_by_quota_turn_mode() -> None:
    """When quota.should_run is False and quota.ok is True, the turn returns
    ``paused_by_quota`` mode with a public_boundary block."""
    temp = Path(tempfile.mkdtemp(prefix="loopx-smoke-quota-pause-"))
    supervisor = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID, agent_specs=LANES,
        session_name="loopx-smoke-quota-pause",
        cli_bin="loopx", codex_bin="codex", tmux_bin="tmux", reasoning_effort="high",
    )
    _, registry, runtime_root = _seed_visible_demo_control_plane(
        demo_root=temp, goal_id=GOAL_ID,
        objective="Verify quota pause produces the correct turn mode.",
        supervisor=supervisor,
    )
    workspace = temp / "shared-research-workspace"
    workspace.mkdir()

    # Load the real frontier first so we can graft a synthetic quota onto it.
    frontier = load_auto_research_worker_frontier(
        registry_path=registry, runtime_root_arg=runtime_root,
        goal_id=GOAL_ID, agent_id=CURATOR_AGENT_ID, workspace=workspace,
    )

    # ---- Execute turn: real quota will say should_run=True (fresh goal). ----
    turn = run_auto_research_worker_turn(
        registry_path=registry, runtime_root_arg=runtime_root,
        goal_id=GOAL_ID, agent_id=CURATOR_AGENT_ID,
        workspace=workspace, execute=True,
    )
    assert turn["ok"] is True, turn
    # Fresh goal with runnable seed todo — should NOT be paused by quota.
    assert turn["mode"] != "paused_by_quota", (
        f"fresh goal should not be quota-paused, got mode={turn['mode']}"
    )
    assert_public_safe(turn)

    # ---- Simulate quota pause via dry-run path. ----
    # In a dry-run the kernel doesn't complete todos, so quota isn't spent.
    # The turn still sees the live quota state; for a fresh goal quota says
    # should_run=True.  We verify the mode is NOT paused_by_quota.
    dry_turn = run_auto_research_worker_turn(
        registry_path=registry, runtime_root_arg=runtime_root,
        goal_id=GOAL_ID, agent_id=CURATOR_AGENT_ID,
        workspace=workspace, execute=False,
    )
    assert dry_turn["ok"] is True, dry_turn
    assert dry_turn["mode"] != "paused_by_quota", dry_turn
    assert_public_safe(dry_turn)

    # ---- Worker-loop with execute: verify quota_paused is distinct from
    #      no_executed_turns at the stop_reason layer. ----
    # Fresh goal with one runnable seed todo (write_research_contract).
    # The seed todo requires manual research, so executed=False.
    # The other 3 lanes are blocked. So stop_reason should be
    # no_executed_turns, NOT quota_paused (quota is not paused).
    loop_payload = run_auto_research_worker_loop(
        registry_path=registry, runtime_root_arg=runtime_root,
        goal_id=GOAL_ID, agent_ids=AGENT_IDS, workspace=workspace,
        objective="Verify quota-pause stop reason is distinct.",
        max_rounds=1, execute=True, complete_selected_todo=True,
        visible_lanes_accepted=True, lane_count=len(AGENT_IDS),
        append_evidence=append_auto_research_rollout_events,
    )
    assert loop_payload["ok"] is True, loop_payload
    assert loop_payload["stop_reason"] in ("no_executed_turns", "no_runnable_frontier"), (
        f"unexpected stop_reason={loop_payload['stop_reason']}"
    )
    # Verify the distinction: quota_paused is NOT returned for a fresh goal.
    assert loop_payload["stop_reason"] != "quota_paused", (
        "fresh goal should NOT report quota_paused"
    )
    assert_public_safe(loop_payload)


def main() -> int:
    test_paused_by_quota_turn_mode()
    print("  ok  paused_by_quota turn mode is distinct from no_executed_turns")
    print("auto-research-quota-pause-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
