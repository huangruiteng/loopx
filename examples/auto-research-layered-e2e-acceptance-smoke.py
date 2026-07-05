#!/usr/bin/env python3
"""Acceptance smoke for the real visible auto-research boundary."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-demo-layered-acceptance"
AGENT_ID = "auto-research-operator"


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
        "deterministic_" + "protected_eval_kernel",
        "raw transcript",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_three_layer_minimality() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.demo_supervisor import (
        build_auto_research_demo_supervisor_plan,
    )
    from loopx.capabilities.auto_research.preset import AUTO_RESEARCH_PRESET_SCHEMA_VERSION

    supervisor = build_auto_research_demo_supervisor_plan(goal_id=GOAL_ID)
    layering = supervisor["layer_minimality_contract"]
    assert layering["principle"] == "user_and_preset_stay_thin_kernel_owns_reusable_mechanics"
    assert layering["preset_layer"]["owns"] == [
        "research_roles",
        "handoff_hints",
        "metric_contract_hints",
        "domain_defaults",
    ], layering
    for mechanic in [
        "multi_agent_runner",
        "real_codex_tui_panes",
        "workspace_and_trust_safe_launch",
        "decentralized_a2a_driver",
        "pane_local_a2a_tick",
        "todo_evidence_status_protocol",
        "compact_human_status",
    ]:
        assert mechanic in layering["preset_layer"]["forbidden"], layering
        assert mechanic in layering["kernel_layer"]["owns"], layering

    preset = supervisor["preset"]
    assert preset["schema_version"] == AUTO_RESEARCH_PRESET_SCHEMA_VERSION, preset
    assert preset["minimal_a2a_recipe"]["user_plus_preset_line_count"] == 5, preset
    assert preset["owns"] == layering["preset_layer"]["owns"], preset
    assert preset["worker_skill_scope"] == "role_specific_semantics_and_successor_todos_only", preset

    driver = supervisor["runner_contract"]["decentralized_a2a_driver"]
    assert driver["broadcaster"]["decides_work"] is False, driver
    assert driver["broadcaster"]["runs_worker_turn"] is False, driver
    assert driver["pane"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", driver
    assert driver["layer_budget"]["preset_layer"] == [
        "domain_roles",
        "handoff_hints",
        "optional_worker_hook",
    ], driver

    for lane in supervisor["lanes"]:
        assert lane["pane_local_a2a"]["auto_start"] is True, lane
        assert lane["pane_local_a2a"]["worker_turn_configured"] is False, lane
        assert lane["pane_local_a2a"]["tick_rounds"] == 1, lane
        command = lane["visible_launch_command"]
        assert "LOOPX_PANE_A2A_TICK" in command, lane
        assert "auto-research worker-turn" not in command, lane
        assert "--complete-selected-todo" not in command, lane
        assert "LOOPX_PANE_TICK_ROUNDS=" not in command, lane
        assert "LOOPX_PANE_TICK_SLEEP_SECONDS=" not in command, lane
    assert_public_safe(supervisor)


def assert_headless_worker_loop_is_not_research_uplift() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e
    from loopx.capabilities.auto_research.human_view import render_auto_research_markdown

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        payload = run_auto_research_demo_e2e(
            agent_id=AGENT_ID,
            goal_id=GOAL_ID,
            tracking_goal_id=None,
            objective="Verify headless worker loop cannot claim research uplift.",
            output_dir="auto_research_lightweight_kernel",
            execute=True,
            run_worker_loop=True,
            worker_loop_rounds=1,
            launch_visible=False,
            keep_workspace=False,
            registry_path=registry,
            runtime_root_arg=str(runtime_root),
            session_name="loopx-ar-layered-acceptance",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
            output_language="en",
            live_evidence_path=None,
            append_evidence=lambda _packet: {},
        )

    worker_loop = payload["worker_loop"]
    assert worker_loop["turn_count"] == 4, worker_loop
    assert worker_loop["executed_turn_count"] == 0, worker_loop
    assert worker_loop["completed_turn_count"] == 0, worker_loop
    assert all(turn.get("dev_metric") is None for turn in worker_loop["turns"]), worker_loop
    assert all(turn.get("holdout_metric") is None for turn in worker_loop["turns"]), worker_loop

    collective = payload["collective_research_rounds"]
    assert collective["multi_round_research_verified"] is False, collective
    assert collective["visible_role_participation_verified"] is False, collective
    assert collective["visible_role_participation_basis"] == "headless_worker_loop_summary_only", collective
    assert collective["holdout_improvement_count"] == 0, collective
    assert collective["dev_metric_sequence"] == [], collective
    assert collective["holdout_metric_sequence"] == [], collective
    tonight = payload["tonight_experience"]
    assert tonight["positive_result"] is False, tonight
    assert tonight["ready"] is False, tonight
    assert tonight["positive_result_basis"] == "requires_visible_lane_authored_evidence", tonight
    assert tonight["dev_metric"] is None, tonight
    assert tonight["holdout_metric"] is None, tonight

    markdown = render_auto_research_markdown(payload)
    assert "claim_source: `worker_loop_collective_agent_passes`" in markdown, markdown
    assert "visible_role_participation_verified: `False`" in markdown, markdown
    assert "dev_metric_sequence: `none`" in markdown, markdown
    assert "holdout_metric_sequence: `none`" in markdown, markdown
    assert "holdout_improvement_count: `0`" in markdown, markdown
    assert "holdout=5.2" not in markdown, markdown
    assert_public_safe(payload)
    assert_public_safe(markdown)


def main() -> int:
    assert_three_layer_minimality()
    assert_headless_worker_loop_is_not_research_uplift()
    print("auto-research-layered-e2e-acceptance-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
