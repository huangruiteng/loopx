"""Thin auto-research visible-lane plan built on the generic TUI runner."""

from __future__ import annotations

import shlex
from collections.abc import Iterable
from typing import Any

from .defaults import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    build_auto_research_layer_contract,
)
from .preset import (
    AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
    build_auto_research_preset_role,
    build_auto_research_preset_summary,
    auto_research_lane_specs,
)
from ...visible_multi_agent_launcher import build_visible_multi_agent_payload_from_spec


AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION = "auto_research_demo_supervisor_plan_v0"


def build_visible_worker_turn_command(*, objective: object | None = None) -> str:
    """Return a pane-local worker-turn hook that still obeys visible evidence gates."""

    clean_objective = str(objective or AUTO_RESEARCH_DEFAULT_OBJECTIVE).strip()
    return (
        '"$LOOPX_PANE_LOOPX" --format json auto-research worker-turn '
        '--goal-id "$LOOPX_GOAL_ID" '
        '--agent-id "$LOOPX_AGENT_ID" '
        f"--objective {shlex.quote(clean_objective)} "
        '--lane-count "${LOOPX_VISIBLE_LANE_COUNT:-1}" '
        "--visible-lanes-accepted "
        "--complete-selected-todo "
        "--execute"
    )


def build_auto_research_demo_supervisor_plan(
    *,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    open_question: object | None = None,
    preset_context: dict[str, object] | None = None,
    agent_specs: Iterable[str] | None = None,
    session_name: str = "loopx-auto-research",
    cli_bin: str = "loopx",
    codex_bin: str = "codex",
    tmux_bin: str = "tmux",
    reasoning_effort: str = "high",
    output_language: str = "en",
    configure_visible_worker_turn: bool = False,
) -> dict[str, Any]:
    """Build the auto-research visible TUI plan from a small role spec.

    This is intentionally only a launcher/spec packet. Research truth flows
    through each pane's LoopX quota/frontier/todo/evidence commands. The packet
    keeps presentation-specific reporting out of the auto-research kernel.
    """

    goal = str(goal_id).strip() or AUTO_RESEARCH_DEFAULT_GOAL_ID
    lanes = auto_research_lane_specs(agent_specs)
    worker_turn_command = (
        build_visible_worker_turn_command(objective=open_question)
        if configure_visible_worker_turn
        else ""
    )
    roles = [
        build_auto_research_preset_role(
            lane=lane,
            goal_id=goal,
            reasoning_effort=reasoning_effort,
            output_language=output_language,
            open_question=open_question,
            preset_context=preset_context,
        )
        for lane in lanes
    ]
    if worker_turn_command:
        for role in roles:
            role["worker_turn_command"] = worker_turn_command
            role_profile = role.get("role_profile")
            if isinstance(role_profile, dict):
                role_profile["visible_worker_turn_configured"] = True

    payload = build_visible_multi_agent_payload_from_spec(
        {
            "goal_id": goal,
            "session_name": session_name,
            "reasoning_effort": reasoning_effort,
            "roles": roles,
        },
        tmux_bin=tmux_bin,
        cli_bin=cli_bin,
        codex_bin=codex_bin,
    )
    payload.pop("acceptance", None)
    runner_contract = (
        payload.get("runner_contract")
        if isinstance(payload.get("runner_contract"), dict)
        else {}
    )
    driver_contract = (
        runner_contract.get("decentralized_a2a_driver")
        if isinstance(runner_contract.get("decentralized_a2a_driver"), dict)
        else {}
    )
    payload.update(
        {
            "schema_version": AUTO_RESEARCH_DEMO_SUPERVISOR_SCHEMA_VERSION,
            "mode": "dry_run",
            "layer_minimality_contract": build_auto_research_layer_contract(),
            "preset": build_auto_research_preset_summary(
                role_count=len(roles),
                output_language=output_language,
                role_specs=[
                    f"{lane['agent_id']}:{lane['lane_id']}:{lane['role_id']}"
                    for lane in lanes
                ],
            ),
            "auto_research": {
                "schema_version": AUTO_RESEARCH_PRESET_SCHEMA_VERSION,
                "uses_generic_runner": True,
                "surface_count": len(roles),
                "state_bus": "loopx_registry_runtime_todo_quota_frontier",
                "kernel_driver": "decentralized_a2a_driver",
                "kernel_driver_schema": driver_contract.get("schema_version"),
                "delegated_kernel_mechanics": [
                    "fixed_prompt_wakeup",
                    "pane_local_a2a_status_check",
                    "todo_evidence_status_protocol",
                ],
                "worker_turn_owner": "generic_multi_agent_kernel",
                "visible_worker_turn_configured": bool(worker_turn_command),
                "output_language": output_language,
                "presentation_layers_in_kernel": False,
            },
            "coordination_model": {
                "leader_agent_required": False,
                "source_of_truth": [
                    "quota_should_run",
                    "agent_scoped_frontier",
                    "todo_claims",
                    "rollout_event_log",
                ],
                "pattern": "decentralized_state_a2a",
            },
            "one_click_demo": {
                "schema_version": "auto_research_one_click_demo_v1",
                "mode": "visible_codex_tui_lanes",
                "default_safe": True,
                "expected_visible_result": [
                    "one tmux window with tiled role panes",
                    "each pane starts a real interactive Codex CLI TUI",
                    "each role reads its projected frontier and authors a visible research artifact",
                    "$LOOPX_PANE_A2A_TICK is a guard/status check, not a fake research writer",
                    "successor todos flow through LoopX state only after role-authored evidence exists",
                ],
            },
        }
    )
    return payload
