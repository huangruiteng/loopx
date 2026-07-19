#!/usr/bin/env python3
"""Smoke-test demo-e2e no longer treats worker-loop as research output."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ID = "auto-research-operator"
GOAL_ID = "loopx-auto-research-demo-worker-loop-smoke"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.demo_e2e import (
        _build_collective_round_summary,
        run_auto_research_demo_e2e,
    )
    from loopx.capabilities.auto_research.human_view import render_auto_research_markdown
    from loopx.capabilities.auto_research.preset import default_auto_research_agent_specs

    runtime_scripts_source = (
        REPO_ROOT / "loopx/control_plane/agents/multi_agent/runtime_scripts.py"
    ).read_text(encoding="utf-8")
    preset_source = (
        REPO_ROOT / "loopx/capabilities/auto_research/preset.py"
    ).read_text(encoding="utf-8")
    assert "raw JSON is not printed in visible panes" in runtime_scripts_source
    assert "No automated worker-turn is configured" in runtime_scripts_source
    assert "Do not treat this tick as research completion" in runtime_scripts_source
    assert "auto-research worker-turn" not in preset_source
    assert "AUTO_RESEARCH_DEMO_STAGE_METRICS" not in preset_source
    assert default_auto_research_agent_specs() == [
        "research-curator:research-curator:research_curator",
        "hypothesis-proposer:hypothesis-proposer:hypothesis_proposer",
        "research-executor:research-executor:research_executor",
        "evaluator-promoter:evaluator-promoter:evaluator_promoter",
    ]

    worker_markdown = render_auto_research_markdown(
        {
            "ok": True,
            "schema_version": "auto_research_worker_turn_v0",
            "mode": "manual_research_required",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_ID,
            "selected_todo_id": "todo_worker_smoke",
            "selected_action": "run_dev_eval",
            "executed": False,
            "manual_research_required": True,
            "completion": {"requested": True, "executed": False},
            "frontier": {
                "quota": {"should_run": True, "state": "eligible"},
                "frontier": {
                    "selected": {
                        "todo_id": "todo_worker_smoke",
                        "allowed_action": "run_dev_eval",
                    }
                },
            },
        }
    )
    assert "# LoopX Auto Research Worker Turn" in worker_markdown
    assert "- mode: `manual_research_required`" in worker_markdown
    assert "- selected_action: `run_dev_eval`" in worker_markdown

    with tempfile.TemporaryDirectory(prefix="loopx-visible-worker-loop-smoke.") as tmp:
        root = Path(tmp)
        registry = root / "registry.json"
        runtime_root = root / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        payload = run_auto_research_demo_e2e(
            agent_id=AGENT_ID,
            goal_id=GOAL_ID,
            tracking_goal_id=None,
            objective="Verify demo-e2e does not manufacture auto-research metrics.",
            output_dir="auto_research_lightweight_kernel",
            execute=True,
            run_worker_loop=True,
            worker_loop_rounds=1,
            launch_visible=False,
            keep_workspace=False,
            registry_path=registry,
            runtime_root_arg=str(runtime_root),
            session_name="loopx-visible-worker-loop-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
            output_language="en",
            live_evidence_path=None,
            append_evidence=lambda _packet: {},
        )

    assert payload["ok"] is True, payload
    assert payload["execution_kind"] == "loopx_worker_loop", payload
    worker_loop = payload["worker_loop"]
    assert worker_loop["turn_count"] == 4, worker_loop
    assert worker_loop["executed_turn_count"] == 0, worker_loop
    assert worker_loop["completed_turn_count"] == 0, worker_loop
    assert worker_loop["stop_reason"] == "no_executed_turns", worker_loop
    assert worker_loop["selected_actions"] == ["write_research_contract"], worker_loop
    manual_turns = [
        turn for turn in worker_loop["turns"] if turn.get("mode") == "manual_research_required"
    ]
    assert [turn["agent_id"] for turn in manual_turns] == ["research-curator"], worker_loop
    assert [turn["selected_action"] for turn in manual_turns] == [
        "write_research_contract"
    ], worker_loop
    no_action_turns = [turn for turn in worker_loop["turns"] if turn.get("mode") == "no_action"]
    assert [turn["agent_id"] for turn in no_action_turns] == [
        "hypothesis-proposer",
        "research-executor",
        "evaluator-promoter",
    ], worker_loop
    assert all(turn.get("dev_metric") is None for turn in worker_loop["turns"]), worker_loop
    assert all(turn.get("holdout_metric") is None for turn in worker_loop["turns"]), worker_loop
    assert all("demo_iteration" not in turn for turn in worker_loop["turns"]), worker_loop

    collective = payload["collective_research_rounds"]
    assert collective["multi_round_research_verified"] is False, collective
    assert collective["claim_source"] == "worker_loop_collective_agent_passes", collective
    assert collective["visible_role_participation_verified"] is False, collective
    assert collective["visible_role_participation_basis"] == "headless_worker_loop_summary_only", collective
    assert collective["holdout_improvement_count"] == 0, collective
    assert collective["dev_metric_sequence"] == [], collective
    assert collective["holdout_metric_sequence"] == [], collective
    proof = payload["visible_worker_proof"]
    assert proof["visible_role_participation_verified"] is False, proof
    assert proof["decentralized_a2a_rounds_verified"] is False, proof
    tonight = payload["tonight_experience"]
    assert tonight["positive_result"] is False, tonight
    assert tonight["ready"] is False, tonight
    assert tonight["positive_result_basis"] == "requires_visible_lane_authored_evidence", tonight
    assert tonight["dev_metric"] is None, tonight
    assert tonight["holdout_metric"] is None, tonight
    assert_public_safe(payload)

    headless_with_metrics = _build_collective_round_summary(
        source="worker_loop_collective_agent_passes",
        agent_count=4,
        collective_round_count=4,
        dev_metric=4.8,
        holdout_metric=5.2,
        dev_metric_sequence=[4.0, 4.8],
        holdout_metric_sequence=[4.5, 5.2],
        holdout_improvement_count=2,
        expected_lanes=[
            {"agent_id": "research-curator"},
            {"agent_id": "hypothesis-proposer"},
            {"agent_id": "research-executor"},
            {"agent_id": "evaluator-promoter"},
        ],
        lane_outcomes=[
            {
                "round": round_index,
                "agent_id": agent_id,
                "selected_todo_id": f"todo_{round_index}_{agent_id}",
                "selected_action": "summarize_evidence",
                "executed": True,
                "completion_status": "done",
            }
            for round_index in range(1, 5)
            for agent_id in (
                "research-curator",
                "hypothesis-proposer",
                "research-executor",
                "evaluator-promoter",
            )
        ],
        visible_role_participation_verified=False,
        visible_role_participation_basis="headless_worker_loop_summary_only",
    )
    assert headless_with_metrics["kernel_ledger"]["collective_research_verification"][
        "verified"
    ] is True, headless_with_metrics
    assert headless_with_metrics["multi_round_research_verified"] is False, (
        headless_with_metrics
    )
    assert headless_with_metrics["claim_boundary"].startswith(
        "worker-loop summaries are control-plane plumbing evidence only"
    ), headless_with_metrics

    print("auto-research-demo-e2e-worker-loop-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
