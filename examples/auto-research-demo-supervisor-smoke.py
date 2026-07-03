#!/usr/bin/env python3
"""Smoke-test the thin auto-research visible TUI supervisor packet."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research.demo_supervisor import (  # noqa: E402
    AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
    build_auto_research_demo_supervisor_plan,
)
from loopx.capabilities.auto_research.preset import (  # noqa: E402
    AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
)


GOAL_ID = "loopx-auto-research-demo"
LANES = [
    "codex-product-capability:research-curator:research_curator",
    "codex-side-bypass:hypothesis-mapper:hypothesis_mapper",
    "codex-main-control:evidence-runner:evidence_runner",
    "codex-value-explorer:evidence-verifier:evidence_verifier",
]


def assert_no_private_surface(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http" + "://",
        "https" + "://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_supervisor_contract(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION, payload
    assert payload["mode"] == "dry_run", payload
    assert payload["goal_id"] == GOAL_ID, payload

    layering = payload["layer_minimality_contract"]
    assert (
        layering["schema_version"] == "multi_agent_three_layer_minimality_contract_v0"
    ), layering
    assert layering["product_id"] == "auto-research", layering
    assert layering["preset_id"] == "auto_research_thin_preset", layering
    assert layering["principle"] == (
        "user_and_preset_stay_thin_kernel_owns_reusable_mechanics"
    ), layering
    assert layering["user_layer"]["fields"] == [
        "topic_or_objective",
        "rounds",
        "role_overrides",
        "data_or_eval_entrypoint",
    ], layering
    assert "research_roles" in layering["preset_layer"]["owns"], layering
    assert "metric_evidence_loop" in layering["preset_layer"]["owns"], layering
    assert "multi_agent_runner" in layering["preset_layer"]["forbidden"], layering
    assert "decentralized_a2a_driver" in layering["preset_layer"]["forbidden"], layering
    assert "pane_local_a2a_tick" in layering["preset_layer"]["forbidden"], layering
    assert "decentralized_a2a_driver" in layering["kernel_layer"]["owns"], layering
    assert "compact_human_status" in layering["kernel_layer"]["owns"], layering
    assert layering["acceptance"]["preset_has_no_runner_process_logic"] is True, layering

    preset = payload["preset"]
    assert preset["schema_version"] == AUTO_RESEARCH_PRESET_SCHEMA_VERSION, preset
    assert preset["role_count"] == 4, preset
    assert preset["owns"] == [
        "research_roles",
        "handoff_hints",
        "metric_evidence_loop",
        "domain_defaults",
    ], preset
    assert "multi_agent_runner" in preset["forbidden"], preset
    assert "decentralized_a2a_driver" in preset["forbidden"], preset
    assert "pane_local_a2a_tick" in preset["forbidden"], preset

    kernel = payload["auto_research"]
    assert kernel["schema_version"] == AUTO_RESEARCH_PRESET_SCHEMA_VERSION, payload
    assert kernel["uses_generic_runner"] is True, payload
    assert kernel["surface_count"] == 4, payload
    assert kernel["state_bus"] == "loopx_registry_runtime_todo_quota_frontier", payload
    assert kernel["kernel_driver"] == "decentralized_a2a_driver", payload
    assert kernel["kernel_driver_schema"] == "multi_agent_decentralized_a2a_driver_contract_v0", payload
    assert kernel["worker_turn_owner"] == "generic_multi_agent_kernel", payload
    assert "pane_local_a2a_tick" in kernel["delegated_kernel_mechanics"], payload
    assert kernel["presentation_layers_in_kernel"] is False, payload

    coordination = payload["coordination_model"]
    assert coordination["leader_agent_required"] is False, payload
    assert coordination["pattern"] == "decentralized_state_a2a", payload
    assert "quota_should_run" in coordination["source_of_truth"], payload
    assert "agent_scoped_frontier" in coordination["source_of_truth"], payload

    shared = payload["shared_goal_surface"]
    assert shared["shared_goal_id"] == GOAL_ID, shared
    assert shared["shared_state_route"] == "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT", shared
    assert shared["shared_frontier"] is True, shared
    assert shared["all_lane_workspace_isolation"] is False, shared
    assert "agent-scoped todo/frontier" in shared["mutation_isolation_policy"], shared

    runner = payload["runner_contract"]
    assert runner["runner_surface"] == "tmux_codex_cli_tui", runner
    assert runner["coordination_model"]["leader_required"] is False, runner
    assert runner["coordination_model"]["state_bus"] == "loopx_registry_runtime_todo_quota_frontier", runner
    assert runner["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", runner
    assert runner["pane_local_a2a"]["human_default"] == "markdown_status_inside_codex_tui", runner
    driver = runner["decentralized_a2a_driver"]
    assert driver["owner_layer"] == "generic_multi_agent_kernel", driver
    assert driver["broadcaster"]["decides_work"] is False, driver
    assert driver["acceptance"]["user_and_preset_do_not_own_tick_driver"] is True, driver
    assert runner["role_prompt_and_skill"]["worker_local_skill_only"] is True, runner

    tui = payload["interactive_tui_contract"]
    assert tui["codex_surface"] == "interactive_cli_tui", tui
    assert tui["visible_json_policy"] == "not_printed_before_tui", tui
    assert "pre_codex_character_stream" in tui["forbidden_visible_content"], tui
    assert "raw_frontier_json" in tui["forbidden_visible_content"], tui

    lanes = payload["lanes"]
    assert [lane["lane_id"] for lane in lanes] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
        "evidence-verifier",
    ], payload
    assert [lane["role_id"] for lane in lanes] == [
        "research_curator",
        "hypothesis_mapper",
        "evidence_runner",
        "evidence_verifier",
    ], payload
    expected_action_hints = {
        "research_curator": "write_research_contract",
        "hypothesis_mapper": "propose_hypothesis",
        "evidence_runner": "run_dev_eval",
        "evidence_verifier": "summarize_evidence",
    }
    for lane in lanes:
        profile = lane["role_profile"]
        assert profile["schema_version"] == "auto_research_role_profile_v0", profile
        assert profile["goal_id"] == GOAL_ID, profile
        assert profile["agent_id"] == lane["agent_id"], profile
        assert profile["role_id"] == lane["role_id"], profile
        assert profile["required_skill"] == "loopx-auto-research", profile
        assert profile["skill_distribution"] == "worker_local", profile
        assert profile["worker_skill_source"].endswith("auto_research/worker_skill/SKILL.md"), profile
        assert expected_action_hints[lane["role_id"]] in profile["allowed_actions"], profile
        assert profile["write_scope"], profile
        assert profile["stop_conditions"], profile

        assert "quota should-run" in lane["quota_guard"], lane
        assert f"--agent-id {lane['agent_id']}" in lane["quota_guard"], lane
        assert lane["frontier"] == "agent-scoped LoopX todo/quota/frontier projection", lane
        assert lane["bootstrap_message"] == "role_prompt_inside_codex_tui", lane
        assert lane["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", lane
        assert lane["pane_local_a2a"]["worker_turn_configured"] is True, lane
        assert lane["pane_local_a2a"]["auto_start"] is True, lane
        assert lane["pane_local_a2a"]["tick_rounds"] == 3, lane
        assert lane["pane_local_a2a"]["tick_sleep_seconds"] == 3, lane
        assert lane["lane_timeline"] == [
            "role_profile",
            "auto_start_pane_local_a2a_tick",
            "codex_tui",
            "frontier",
        ], lane

        command = lane["visible_launch_command"]
        assert "LOOPX_PANE_A2A_TICK" in command, lane
        assert "LOOPX_PANE_WORKER_TURN" in command, lane
        assert "LOOPX_PANE_TICK_ROUNDS=3" in command, lane
        assert "LOOPX_PANE_TICK_SLEEP_SECONDS=3" in command, lane
        assert "pane-a2a-tick.output.txt" in command, lane
        assert "auto-research worker-turn" in command, lane
        assert "--visible-lanes-accepted" in command, lane
        assert "LOOPX_VISIBLE_LANE_COUNT" in command, lane
        assert "live-codex-e2e-evidence.public.json" in command, lane
        assert "--complete-selected-todo" in command, lane
        assert "LOOPX_VISIBLE_TUI_SILENT_BOOTSTRAP=1" in command, lane
        assert "LOOPX_CODEX_TUI_MODE=interactive" in command, lane
        assert "LOOPX_CODEX_TUI_PROMPT_ARTIFACT" in command, lane
        assert "LOOPX_CODEX_BIN=codex" in command, lane
        assert "LOOPX_CODEX_REASONING_EFFORT=high" in command, lane
        assert "exec python3 -c" in command, lane
        assert "codex exec" not in command, lane
        assert "codex_stream_filter" not in command, lane
        assert "[LoopX auto-research frontier]" not in command, lane
        assert "BOOTSTRAP_ARTIFACT" in command, lane
        assert "bootstrap-or-stop" not in command, lane

    start_script = "\n".join(payload["commands"]["start_script"])
    assert "tmux new-session" in start_script, start_script
    assert "tmux new-window" in start_script, start_script
    assert "LOOPX_PROJECT" in start_script, start_script
    assert "LOOPX_CODEX_TUI_MODE=interactive" in start_script, start_script
    assert "LOOPX_CODEX_BIN=codex" in start_script, start_script
    assert "LOOPX_CODEX_REASONING_EFFORT=high" in start_script, start_script
    assert "exec python3 -c" in start_script, start_script
    assert "[Codex bootstrap]" not in start_script, start_script
    assert "[Codex bootstrap prompt]" not in start_script, start_script
    assert payload["commands"]["attach"] == "tmux attach -t loopx-auto-research", payload

    one_click = payload["one_click_demo"]
    assert one_click["schema_version"] == "auto_research_one_click_demo_v1", payload
    assert one_click["mode"] == "visible_codex_tui_lanes", payload
    assert one_click["default_safe"] is True, payload
    assert "each window starts a real interactive Codex CLI TUI" in " ".join(
        one_click["expected_visible_result"]
    ), one_click
    assert "starts by running $LOOPX_PANE_A2A_TICK" in " ".join(
        one_click["expected_visible_result"]
    ), one_click

    boundary = payload["boundary"]
    assert boundary["starts_visible_processes"] is False, payload
    assert boundary["runs_agent_processes"] is False, payload
    assert boundary["writes_loopx_state"] is False, payload
    assert boundary["spends_loopx_quota"] is False, payload
    assert boundary["reads_raw_transcripts"] is False, payload
    assert boundary["reads_session_files"] is False, payload
    assert boundary["reads_credentials"] is False, payload
    assert boundary["shared_goal_surface"] is True, payload
    assert boundary["public_safe_redaction"] is True, payload

    for removed_key in [
        "acceptance",
        "demo_acceptance",
        "launch_checks",
        "board",
        "showcase_projection",
        "artifact_packet",
        "public_claim_boundary",
    ]:
        assert removed_key not in payload, payload
    assert_no_private_surface(payload)


def run_cli_json() -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "demo-supervisor",
            "--goal-id",
            GOAL_ID,
            "--agent",
            LANES[0],
            "--agent",
            LANES[1],
            "--agent",
            LANES[2],
            "--agent",
            LANES[3],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    default_payload = build_auto_research_demo_supervisor_plan(goal_id=GOAL_ID)
    assert [lane["agent_id"] for lane in default_payload["lanes"]] == [
        "codex-product-capability",
        "codex-side-bypass",
        "codex-main-control",
        "codex-value-explorer",
    ], default_payload
    assert [lane["lane_id"] for lane in default_payload["lanes"]] == [
        "research-curator",
        "hypothesis-mapper",
        "evidence-runner",
        "evidence-verifier",
    ], default_payload
    assert default_payload["auto_research"]["surface_count"] == 4, default_payload
    assert default_payload["shared_goal_surface"]["shared_goal_id"] == GOAL_ID, default_payload

    payload = build_auto_research_demo_supervisor_plan(
        goal_id=GOAL_ID,
        agent_specs=LANES,
    )
    assert_supervisor_contract(payload)

    try:
        build_auto_research_demo_supervisor_plan(
            goal_id=GOAL_ID,
            agent_specs=["codex-main-control:evidence-runner:not_a_role"],
        )
    except ValueError as exc:
        assert "unknown auto-research role_id" in str(exc), exc
    else:
        raise AssertionError("explicit invalid role_id must not silently fallback")

    cli_payload = run_cli_json()
    assert_supervisor_contract(cli_payload)

    markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "auto-research",
            "demo-supervisor",
            "--goal-id",
            GOAL_ID,
            "--agent",
            LANES[0],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "# LoopX Auto Research Demo Supervisor" in markdown, markdown
    assert "leader_agent_required: `False`" in markdown, markdown
    assert "## Role Profiles" in markdown, markdown
    assert "loopx-auto-research" in markdown, markdown
    assert "## Lane Timeline" in markdown, markdown
    assert "required_worker_playbook: `loopx-auto-research`" in markdown, markdown
    assert "skill_distribution: `worker_local`" in markdown, markdown
    assert "worker_skill_source: `loopx/capabilities/auto_research/worker_skill/SKILL.md`" in markdown, markdown
    assert "## One-Click Dry Run" in markdown, markdown
    assert "visible_codex_tui_lanes" in markdown, markdown
    assert "## Demo Acceptance" not in markdown, markdown
    assert "accept when:" not in markdown, markdown
    assert "tmux attach -t loopx-auto-research" in markdown, markdown
    assert "start_script: `machine_json_only`" in markdown, markdown
    assert "loopx auto-research demo-e2e --execute" in markdown, markdown
    assert "tmux new-session" not in markdown, markdown
    assert "LOOPX_ROLE_PROFILE_JSON" not in markdown, markdown

    print("auto-research-demo-supervisor-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
