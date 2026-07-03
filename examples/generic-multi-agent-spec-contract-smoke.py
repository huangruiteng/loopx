#!/usr/bin/env python3
"""Smoke-test the thin generic multi-agent spec contract.

This intentionally avoids tmux/Codex execution. It checks that the user-facing
role spec is enough to materialize interactive TUI lanes while machine JSON
stays routed to public artifact files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.visible_multi_agent_launcher import (  # noqa: E402
    INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION,
    TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
    build_visible_multi_agent_payload_from_spec,
)
from loopx.capabilities.multi_agent.contract import (  # noqa: E402
    DECENTRALIZED_A2A_DRIVER_CONTRACT_SCHEMA_VERSION,
    GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION,
    GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
    build_tui_multi_agent_runner_contract,
)


PRIVATE_MARKERS = [
    "byte" + "dance",
    "lark" + "office",
    "fei" + "shu.cn",
    "/" + "Users" + "/",
    "/" + "private" + "/",
    "/" + "tmp" + "/",
    "api" + "_key",
    "pass" + "word",
    "sec" + "ret",
]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    leaked = [marker for marker in PRIVATE_MARKERS if marker.lower() in text]
    assert not leaked, leaked


def lane_by_id(payload: dict[str, Any], lane_id: str) -> dict[str, Any]:
    for lane in payload["lanes"]:
        if lane["lane_id"] == lane_id:
            return lane
    raise AssertionError(f"missing lane {lane_id}")


def main() -> int:
    payload = build_visible_multi_agent_payload_from_spec(
        {
            "schema_version": "generic_multi_agent_launch_spec_v0",
            "goal_id": "loopx-meta",
            "session_name": "loopx-generic-spec-smoke",
            "default_reasoning_effort": "medium",
            "roles": [
                {
                    "lane_id": "planner",
                    "agent_id": "codex-main-control",
                    "role_id": "research-planner",
                    "scope": "Plan the next bounded research handoff.",
                    "skill": {
                        "name": "loopx-planner-worker",
                        "source": "skills/planner/SKILL.md",
                    },
                    "handoff_hints": [
                        "Write a LoopX todo for builder when the plan is ready."
                    ],
                    "worker_turn_command": "loopx auto-research worker-turn --dry-run",
                    "tick_rounds": 2,
                    "tick_sleep_seconds": 1,
                },
                {
                    "lane_id": "builder",
                    "agent_id": "codex-side-bypass",
                    "role_id": "research-builder",
                    "scope": "Implement the claimed todo and write compact evidence.",
                    "skill": {
                        "name": "loopx-builder-worker",
                        "source": "skills/builder/SKILL.md",
                    },
                    "handoff_hints": [
                        "Complete the todo or hand a focused review todo back."
                    ],
                    "worker_turn_command": "loopx auto-research worker-turn --execute",
                    "reasoning_effort": "high",
                },
            ],
        },
        tmux_bin="tmux",
        cli_bin="loopx",
        codex_bin="codex",
    )

    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "multi_agent_visible_launcher_v0", payload
    assert payload["mode"] == "dry_run", payload
    assert payload["goal_id"] == "loopx-meta", payload
    assert payload["product_spec"] == {
        "schema_version": "generic_multi_agent_launch_spec_v0",
        "input_shape": ["goal_id", "session_name", "roles"],
        "role_fields": [
            "agent_id",
            "role_id",
            "scope",
            "skill",
            "handoff_hints",
            "reasoning_effort",
            "worker_turn_command",
            "worker_loop_command",
        ],
        "role_count": 2,
        "role_profile_schema_version": GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
        "uses_generic_runner": True,
        "domain_specific": False,
    }, payload

    runner = payload["runner_contract"]
    assert runner["schema_version"] == TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION, runner
    assert runner["runner_surface"] == "tmux_codex_cli_tui", runner
    assert runner["coordination_model"]["leader_required"] is False, runner
    assert runner["coordination_model"]["state_bus"] == "loopx_registry_runtime_todo_quota_frontier", runner
    assert runner["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK", runner
    assert runner["pane_local_a2a"]["machine_json_policy"] == "file_or_explicit_machine_channel_only", runner
    assert runner["pane_local_a2a"]["machine_json_destination"] == "$LOOPX_PANE_ARTIFACT_DIR/*.public.json", runner
    driver = runner["decentralized_a2a_driver"]
    assert driver["schema_version"] == DECENTRALIZED_A2A_DRIVER_CONTRACT_SCHEMA_VERSION, driver
    assert driver["owner_layer"] == "generic_multi_agent_kernel", driver
    assert driver["coordination_pattern"] == "decentralized_state_a2a", driver
    assert driver["broadcaster"]["model"] == "fixed_prompt_broadcast", driver
    assert driver["broadcaster"]["decides_work"] is False, driver
    assert driver["pane"]["decision_owner"] == "codex_tui_agent_via_loopx_state", driver
    assert driver["acceptance"]["user_and_preset_do_not_own_tick_driver"] is True, driver
    assert runner["role_prompt_and_skill"]["worker_local_skill_only"] is True, runner
    assert runner["boundaries"]["domain_specific_research_logic"] is False, runner
    direct_runner = build_tui_multi_agent_runner_contract(
        session_name="loopx-direct-kernel-smoke",
        lane_count=2,
        attach_command="tmux attach -t loopx-direct-kernel-smoke",
        stop_command="tmux kill-session -t loopx-direct-kernel-smoke",
        retry_command="rerun after state refresh",
        all_lane_workspace_isolation=False,
    )
    assert direct_runner["schema_version"] == TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION
    assert direct_runner["pane_local_a2a"]["tick_command"] == "$LOOPX_PANE_A2A_TICK"
    assert direct_runner["decentralized_a2a_driver"]["schema_version"] == (
        DECENTRALIZED_A2A_DRIVER_CONTRACT_SCHEMA_VERSION
    )
    assert direct_runner["boundaries"]["domain_specific_research_logic"] is False

    tui = payload["interactive_tui_contract"]
    assert tui["schema_version"] == INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION, tui
    assert tui["codex_surface"] == "interactive_cli_tui", tui
    assert tui["machine_json_policy"] == "file_or_explicit_machine_channel_only", tui
    assert "raw_role_profile_json" in tui["forbidden_visible_content"], tui
    assert "pre_codex_character_stream" in tui["forbidden_visible_content"], tui

    shared = payload["shared_goal_surface"]
    assert shared["shared_state_route"] == "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT", shared
    assert shared["lane_identity_source"] == "role_profile_plus_agent_scoped_quota", shared
    assert shared["all_lane_workspace_isolation"] is False, shared

    planner = lane_by_id(payload, "planner")
    builder = lane_by_id(payload, "builder")
    assert planner["role_profile"]["agent_scope"] == "Plan the next bounded research handoff.", planner
    assert builder["role_profile"]["agent_scope"] == "Implement the claimed todo and write compact evidence.", builder
    assert planner["role_profile"]["required_skill"] == "loopx-planner-worker", planner
    assert builder["role_profile"]["required_skill"] == "loopx-builder-worker", builder
    assert planner["pane_local_a2a"]["worker_turn_configured"] is True, planner
    assert planner["pane_local_a2a"]["tick_rounds"] == 2, planner
    assert builder["reasoning_effort"] == "high", builder
    assert planner["reasoning_effort"] == "medium", planner

    for lane in (planner, builder):
        command = lane["visible_launch_command"]
        assert "LOOPX_CODEX_TUI_MODE=interactive" in command, lane
        assert "LOOPX_PANE_A2A_TICK" in command, lane
        assert "LOOPX_PANE_WORKER_TURN" in command, lane
        assert "LOOPX_PANE_LOOPX_JSON" in command, lane
        assert "LOOPX_PANE_ARTIFACT_DIR" in command, lane
        assert "pane-a2a-tick.output.txt" in command, lane
        assert "exec python3 -c" in command, lane
        assert "codex exec" not in command, lane
        assert "codex_stream_filter" not in command, lane
        assert "raw_frontier_json" not in command, lane
        assert "$LOOPX_PANE_LOOPX_JSON quota should-run" in lane["quota_guard"], lane
        assert "> \"$LOOPX_PANE_ARTIFACT_DIR/quota.public.json\"" in lane["quota_guard"], lane
        assert "auto_start_pane_local_a2a_tick" in lane["lane_timeline"], lane

    assert payload["cli_contract"]["machine_json_policy"] == "artifact_only_in_visible_panes", payload
    compact = payload["compact_human_status"]
    assert compact["schema_version"] == GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION, compact
    assert compact["role_count"] == 2, compact
    assert compact["first_action"] == "$LOOPX_PANE_A2A_TICK", compact
    assert compact["driver_model"] == "fixed_prompt_broadcast_plus_pane_local_state_tick", compact
    assert compact["coordination_pattern"] == "decentralized_state_a2a", compact
    assert compact["machine_json_policy"] == "artifact_only_in_visible_panes", compact
    assert [role["lane_id"] for role in compact["roles"]] == ["planner", "builder"], compact
    assert payload["boundary"]["starts_visible_processes"] is False, payload
    assert payload["boundary"]["writes_loopx_state"] is False, payload
    assert payload["boundary"]["spends_loopx_quota"] is False, payload
    assert_public_safe(payload)

    print("generic-multi-agent-spec-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
