#!/usr/bin/env python3
"""Acceptance smoke for the layered auto-research demo contract.

This smoke intentionally does not start tmux. The visible TUI launch contract is
validated through the generic supervisor packet, while the outcome proof runs
the fast demo-local worker loop.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-demo-layered-acceptance"
AGENT_ID = "auto-research-operator"
EXPECTED_ACTIONS = [
    "write_research_contract",
    "propose_hypothesis",
    "run_dev_eval",
    "summarize_evidence",
    "run_holdout_eval",
    "write_evaluation_summary",
    "propose_hypothesis",
    "run_dev_eval",
    "run_holdout_eval",
    "write_evaluation_summary",
]


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


def run_headless_demo() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        workspace.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "auto-research",
                "demo-e2e",
                "--agent-id",
                AGENT_ID,
                "--demo-run-id",
                "layered-acceptance",
                "--execute",
                "--headless",
            ],
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                "layered demo-e2e failed "
                f"rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return json.loads(result.stdout)


def assert_three_layer_minimality() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.demo_supervisor import (
        build_auto_research_demo_supervisor_plan,
    )
    from loopx.capabilities.auto_research.preset import (
        AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
    )
    from loopx.capabilities.auto_research.worker_runtime import (
        AUTO_RESEARCH_DEMO_BASELINE,
    )

    supervisor = build_auto_research_demo_supervisor_plan(goal_id=GOAL_ID)
    layering = supervisor["layer_minimality_contract"]
    assert layering["principle"] == "user_and_preset_stay_thin_kernel_owns_reusable_mechanics"
    assert layering["user_layer"]["fields"] == [
        "topic_or_objective",
        "rounds",
        "role_overrides",
        "data_or_eval_entrypoint",
    ], layering
    assert len(layering["user_layer"]["fields"]) == 4, layering
    assert layering["preset_layer"]["owns"] == [
        "research_roles",
        "handoff_hints",
        "metric_evidence_loop",
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
    assert layering["acceptance"]["preset_has_no_runner_process_logic"] is True, layering

    minimal_recipe = supervisor["minimal_a2a_recipe"]
    assert minimal_recipe["schema_version"] == "auto_research_minimal_a2a_recipe_v0"
    assert minimal_recipe["user_plus_preset_line_count"] == 5, minimal_recipe
    assert minimal_recipe["user_line_count"] == 1, minimal_recipe
    assert minimal_recipe["preset_role_spec_line_count"] == 4, minimal_recipe
    assert minimal_recipe["shared_kernel_counted_as_recipe_lines"] is False, minimal_recipe
    assert minimal_recipe["coordination_model"] == "decentralized_state_a2a", minimal_recipe
    assert minimal_recipe["a2a_proof_contract"] == {
        "broadcaster_selects_todo": False,
        "broadcaster_runs_worker_turn": False,
        "each_pane_reads_own_quota_frontier": True,
        "successor_todos_declared_by_role_profile": True,
        "leader_agent_required": False,
    }, minimal_recipe

    preset = supervisor["preset"]
    assert preset["schema_version"] == AUTO_RESEARCH_PRESET_SCHEMA_VERSION, preset
    assert preset["minimal_a2a_recipe"]["user_plus_preset_line_count"] == 5, preset
    assert preset["owns"] == layering["preset_layer"]["owns"], preset
    assert "multi_agent_runner" in preset["forbidden"], preset
    assert "real_codex_tui_panes" in preset["forbidden"], preset
    assert "decentralized_a2a_driver" in preset["forbidden"], preset
    assert "pane_local_a2a_tick" in preset["forbidden"], preset
    assert "default_loopx_skill_bootstrap" in preset["forbidden"], preset
    assert "fixed_a2a_wake_prompt" in preset["forbidden"], preset
    assert preset["worker_skill_scope"] == "role_specific_semantics_and_successor_todos_only", preset
    assert preset["successor_routing"] == "role_profile_successor_todos_with_target_agent", preset

    auto_research = supervisor["auto_research"]
    assert auto_research["schema_version"] == AUTO_RESEARCH_PRESET_SCHEMA_VERSION, auto_research
    assert auto_research["uses_generic_runner"] is True, auto_research
    assert auto_research["presentation_layers_in_kernel"] is False, auto_research
    assert auto_research["kernel_driver"] == "decentralized_a2a_driver", auto_research
    assert auto_research["worker_turn_owner"] == "generic_multi_agent_kernel", auto_research
    assert "pane_local_a2a_tick" in auto_research["delegated_kernel_mechanics"], auto_research

    runner = supervisor["runner_contract"]
    assert runner["runner_surface"] == "tmux_codex_cli_tui", runner
    assert runner["coordination_model"]["leader_required"] is False, runner
    assert runner["decentralized_a2a_driver"]["owner_layer"] == "generic_multi_agent_kernel", runner
    assert runner["decentralized_a2a_driver"]["broadcaster"]["decides_work"] is False, runner
    assert runner["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", runner
    assert runner["pane_local_a2a"]["human_default"] == "markdown_status_inside_codex_tui", runner
    assert runner["pane_local_a2a"]["machine_json_destination"] == "$LOOPX_PANE_ARTIFACT_DIR/*.public.json", runner
    assert runner["role_prompt_and_skill"]["default_kernel_skills"] == [
        "loopx-project",
        "loopx-doc-registry",
    ], runner
    assert (
        runner["role_prompt_and_skill"]["worker_local_skill_scope"]
        == "role_specific_semantics_only"
    ), runner

    lanes = supervisor["lanes"]
    assert len(lanes) == 4, supervisor
    assert [lane["agent_id"] for lane in lanes] == [
        "research-curator",
        "hypothesis-proposer",
        "research-executor",
        "evaluator-promoter",
    ], supervisor
    assert [lane["role_id"] for lane in lanes] == [
        "research_curator",
        "hypothesis_proposer",
        "research_executor",
        "evaluator_promoter",
    ], supervisor
    for lane in lanes:
        assert lane["pane_local_a2a"]["auto_start"] is True, lane
        assert lane["bootstrap_message"] == "role_prompt_public_artifact_for_fixed_wake", lane
        assert "LOOPX_PANE_A2A_TICK" in lane["visible_launch_command"], lane
        assert "pane-a2a-tick.output.txt" in lane["visible_launch_command"], lane
        assert "--visible-lanes-accepted" in lane["visible_launch_command"], lane
        assert "codex exec" not in lane["visible_launch_command"], lane
        assert "codex_stream_filter" not in lane["visible_launch_command"], lane

    preset_source = (REPO_ROOT / "loopx/capabilities/auto_research/preset.py").read_text(
        encoding="utf-8"
    )
    for forbidden_source in [
        "visible_multi_agent_launcher",
        "build_visible_multi_agent_payload",
        "add_goal_todo",
        "complete_goal_todo",
        "subprocess",
        "tempfile",
        "tmux",
    ]:
        assert forbidden_source not in preset_source, forbidden_source
    assert AUTO_RESEARCH_DEMO_BASELINE == 1.0
    assert_public_safe(supervisor)


def assert_two_round_outcome(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["execution_kind"] == "loopx_worker_loop", payload
    assert payload["result_source"] == "loopx_worker_loop_public_evidence", payload
    assert payload["route_contract"]["goal_surface_mode"] == "fresh_demo_goal", payload

    user_contract = payload["user_contract"]
    assert user_contract["mode"] == "user_contract", user_contract
    assert user_contract["open_question"], user_contract
    assert user_contract["one_click_start"]["uses_generic_kernel"] is True, user_contract
    assert (
        user_contract["one_click_start"]["command_template"]
        == 'loopx auto-research start "<open question>" --execute'
    ), user_contract
    assert payload["contract_acceptance"]["accepted"] is True, payload
    assert payload["contract_acceptance"]["checks"]["one_click_start_present"] is True, payload
    assert "auto-research start" in payload["commands"]["one_question_start"], payload
    assert "--execute" in payload["commands"]["one_question_start"], payload

    supervisor = payload["supervisor"]
    assert supervisor["uses_generic_runner"] is True, supervisor
    assert supervisor["domain_specific_runner_logic"] is False, supervisor
    assert supervisor["machine_json_policy"] == "artifact_only_in_visible_panes", supervisor
    assert supervisor["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", supervisor
    assert supervisor["pane_local_a2a"]["human_default"] == "markdown_status_inside_codex_tui", supervisor
    assert supervisor["kernel_boundary"]["coordination_pattern"] == "decentralized_state_a2a", supervisor
    assert supervisor["kernel_boundary"]["presentation_layers_in_kernel"] is False, supervisor

    worker_loop = payload["worker_loop"]
    assert worker_loop["schema_version"] == "auto_research_worker_loop_v0", worker_loop
    assert worker_loop["mode"] == "execute", worker_loop
    assert worker_loop["selected_actions"] == EXPECTED_ACTIONS, worker_loop
    assert worker_loop["executed_turn_count"] == 10, worker_loop
    assert worker_loop["completed_turn_count"] == 10, worker_loop
    assert worker_loop["stop_reason"] == "max_rounds", worker_loop

    turns = worker_loop["turns"]
    executed = [turn for turn in turns if turn["executed"]]
    assert {turn["round"] for turn in executed} == {1, 2, 3, 4}, executed
    dev_turn = next(
        turn
        for turn in executed
        if turn["selected_action"] == "run_dev_eval" and turn.get("demo_iteration") == 1
    )
    summary_turn = next(turn for turn in executed if turn["selected_action"] == "summarize_evidence")
    refined_dev_turn = next(
        turn
        for turn in executed
        if turn["selected_action"] == "run_dev_eval" and turn.get("demo_iteration") == 2
    )
    holdout_turn = next(
        turn
        for turn in executed
        if turn["selected_action"] == "run_holdout_eval" and turn.get("demo_iteration") == 1
    )
    refined_holdout_turn = next(
        turn
        for turn in executed
        if turn["selected_action"] == "run_holdout_eval" and turn.get("demo_iteration") == 2
    )
    evaluation_turn = next(
        turn for turn in executed if turn["selected_action"] == "write_evaluation_summary"
    )
    assert dev_turn["round"] == 1, dev_turn
    assert dev_turn["dev_metric"] == 4.0, dev_turn
    assert dev_turn["appended_count"] == 2, dev_turn
    assert dev_turn["live_evidence_written"] is True, dev_turn
    assert summary_turn["round"] == 1, summary_turn
    assert summary_turn["completion_status"] == "done", summary_turn
    assert refined_dev_turn["round"] == 3, refined_dev_turn
    assert refined_dev_turn["dev_metric"] == 4.8, refined_dev_turn
    assert refined_dev_turn["live_evidence_written"] is True, refined_dev_turn
    assert holdout_turn["round"] == 2, holdout_turn
    assert holdout_turn["holdout_metric"] == 4.5, holdout_turn
    assert holdout_turn["best_holdout_metric"] == 4.5, holdout_turn
    assert holdout_turn["claim_allowed"] is True, holdout_turn
    assert holdout_turn["appended_count"] == 1, holdout_turn
    assert refined_holdout_turn["round"] == 4, refined_holdout_turn
    assert refined_holdout_turn["holdout_metric"] == 5.2, refined_holdout_turn
    assert refined_holdout_turn["best_holdout_metric"] == 5.2, refined_holdout_turn
    assert refined_holdout_turn["holdout_improvement_count"] == 2, refined_holdout_turn
    assert evaluation_turn["round"] == 2, evaluation_turn
    assert evaluation_turn["completion_status"] == "done", evaluation_turn
    assert sum(int(turn.get("appended_count") or 0) for turn in turns) >= 3, turns
    collective_rounds = payload["collective_research_rounds"]
    assert collective_rounds["round_unit"] == "collective_agent_pass", collective_rounds
    assert collective_rounds["collective_round_count"] == 4, collective_rounds
    assert collective_rounds["multi_round_research_verified"] is True, collective_rounds
    assert collective_rounds["dev_metric_sequence"] == [4.0, 4.8], collective_rounds
    assert collective_rounds["holdout_metric_sequence"] == [4.5, 5.2], collective_rounds
    assert collective_rounds["holdout_improvement_count"] == 2, collective_rounds
    kernel_ledger = collective_rounds["kernel_ledger"]
    assert kernel_ledger["schema_version"] == "multi_agent_collective_round_ledger_v0"
    assert kernel_ledger["owner_layer"] == "generic_multi_agent_kernel", kernel_ledger
    assert kernel_ledger["expected_lane_count"] == 4, kernel_ledger
    assert kernel_ledger["collective_round_count"] == 4, kernel_ledger
    assert kernel_ledger["integrated_evidence"]["dev_metric"] == 4.8, kernel_ledger
    assert kernel_ledger["integrated_evidence"]["holdout_metric"] == 5.2, kernel_ledger
    assert kernel_ledger["integrated_evidence"]["holdout_improvement_count"] == 2, kernel_ledger

    tonight = payload["tonight_experience"]
    assert tonight["ready"] is True, tonight
    assert tonight["positive_result"] is True, tonight
    assert tonight["positive_result_basis"] == "public_safe_dev_and_holdout_evidence", tonight
    assert tonight["workflow_model"] == "state_projected_frontier_not_dynamic_workflow", tonight
    assert tonight["leader_agent_required"] is False, tonight
    assert tonight["dev_metric"] == 4.8, tonight
    assert tonight["holdout_metric"] == 5.2, tonight
    assert tonight["dev_metric_sequence"] == [4.0, 4.8], tonight
    assert tonight["holdout_metric_sequence"] == [4.5, 5.2], tonight
    assert tonight["holdout_improvement_count"] == 2, tonight
    assert tonight["dev_metric"] > 1.0, tonight
    assert tonight["holdout_metric"] > tonight["dev_metric"], tonight
    assert tonight["selected_actions"] == EXPECTED_ACTIONS, tonight
    assert tonight["state_surfaces"] == [
        "demo-local LoopX registry",
        "quota/frontier selection",
        "todo completion",
        "rollout event log",
    ], tonight
    assert "--run-worker-loop" in tonight["one_command"], tonight
    assert "--headless" not in tonight["one_command"], tonight

    visible_proof = payload["visible_worker_proof"]
    assert visible_proof["schema_version"] == "auto_research_visible_worker_proof_v0", visible_proof
    assert visible_proof["visible_lanes_launched"] is False, visible_proof
    assert visible_proof["lane_authored_evidence_loaded"] is False, visible_proof
    assert "visible Codex worker panes" in visible_proof["reason"], visible_proof

    control = payload["visible_control_plane"]
    assert control["seeded_todo_count"] == 4, control
    seeded_actions = [item["action_kind"] for item in control["seeded_todos"]]
    assert seeded_actions == [
        "write_research_contract",
        "propose_hypothesis",
        "run_dev_eval",
        "summarize_evidence",
    ], control
    assert control["workspace_route"]["primary_workspace"] == "visible_codex_tui_workspace", control
    assert control["workspace_guard_policy"] == {
        "side_agent_independent_worktree_required": False,
        "repository_edits_still_require_lane_boundary": True,
    }, control
    assert_public_safe(payload)


def assert_markdown_explains_research_rounds(payload: dict[str, Any]) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.capabilities.auto_research.human_view import render_auto_research_markdown

    markdown = render_auto_research_markdown(payload)
    assert "## Research Roles / 研究角色" in markdown, markdown
    for role in [
        "research-curator / 研究策展",
        "hypothesis-proposer / 假设生成",
        "research-executor / 研究执行",
        "evaluator-promoter / 评估推进",
    ]:
        assert role in markdown, markdown
    assert "## Collective Rounds / 集体研究轮次" in markdown, markdown
    assert "rounds: `4`" in markdown, markdown
    assert "completed_turns: `10/16`" in markdown, markdown
    assert "dev_metric_sequence: `4.0 -> 4.8`" in markdown, markdown
    assert "holdout_metric_sequence: `4.5 -> 5.2`" in markdown, markdown
    assert "holdout_improvement_count: `2` (required `2`)" in markdown, markdown
    assert "Round 4: executed `research-executor:run_holdout_eval holdout=5.2" in markdown, markdown
    assert "round_semantics: one round is one quota/frontier opportunity" in markdown, markdown
    assert_public_safe(markdown)


def main() -> int:
    assert_three_layer_minimality()
    payload = run_headless_demo()
    assert_two_round_outcome(payload)
    assert_markdown_explains_research_rounds(payload)
    print("auto-research-layered-e2e-acceptance-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
