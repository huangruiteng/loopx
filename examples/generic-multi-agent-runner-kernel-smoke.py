#!/usr/bin/env python3
"""Smoke-test the generic multi-agent runner kernel module."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.control_plane.agents.multi_agent.contract import (  # noqa: E402
    GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION,
    GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
    THREE_LAYER_MINIMALITY_CONTRACT_SCHEMA_VERSION,
    TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
    build_compact_human_status,
    build_generic_role_profile,
    build_three_layer_minimality_contract,
    build_tui_multi_agent_runner_contract,
    generic_role_prompt,
    role_skill_profile,
)
from loopx.control_plane.agents.multi_agent.runtime_scripts import (  # noqa: E402
    CODEX_TUI_EXEC_PY,
    SCOPED_LOOPX_WRAPPER_PY,
)


def main() -> int:
    skill = role_skill_profile({"name": "planner-skill", "source": "skills/planner/SKILL.md"})
    profile = build_generic_role_profile(
        role_id="planner",
        agent_id="codex-main-control",
        scope="Plan one bounded handoff.",
        responsibility="Turn shared state into the next runnable todo.",
        handoff_hints=["Write a todo for builder when ready."],
        skill_profile=skill,
    )
    assert profile["schema_version"] == GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION, profile
    assert profile["required_skill"] == "planner-skill", profile

    prompt = generic_role_prompt(
        goal_id="loopx-meta",
        agent_id="codex-main-control",
        role_id="planner",
        scope=str(profile["agent_scope"]),
        handoff_hints=["Write a todo for builder when ready."],
        skill_name=str(profile["required_skill"]),
    )
    assert "$LOOPX_PANE_A2A_TICK" in prompt, prompt
    assert "$LOOPX_PANE_LOOPX_JSON" in prompt, prompt
    assert "normal Codex CLI agent" in prompt, prompt

    runner = build_tui_multi_agent_runner_contract(
        session_name="loopx-generic-team",
        lane_count=2,
        attach_command="tmux attach -t loopx-generic-team",
        stop_command="tmux kill-session -t loopx-generic-team",
        retry_command="rerun after quota/frontier refresh",
        all_lane_workspace_isolation=False,
    )
    assert runner["schema_version"] == TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION, runner
    assert runner["coordination_model"]["leader_required"] is False, runner
    assert runner["pane_local_a2a"]["machine_json_policy"] == "file_or_explicit_machine_channel_only", runner
    assert runner["boundaries"]["domain_specific_research_logic"] is False, runner
    role_prompt = runner["role_prompt_and_skill"]
    assert role_prompt["default_kernel_skills"] == ["loopx-project", "loopx-doc-registry"], runner
    assert (
        role_prompt["default_kernel_skill_policy"]["owner_layer"]
        == "generic_multi_agent_kernel"
    ), runner
    assert role_prompt["default_kernel_skill_policy"][
        "preset_should_not_repeat_skill_playbooks"
    ] is True, runner
    assert role_prompt["wake_prompt_owner"] == "generic_multi_agent_kernel", runner
    assert (
        runner["decentralized_a2a_driver"]["prompt"]["owner_layer"]
        == "generic_multi_agent_kernel"
    ), runner

    compact = build_compact_human_status(
        {
            "goal_id": "loopx-meta",
            "mode": "dry_run",
            "session_name": "loopx-generic-team",
            "commands": {
                "attach": "tmux attach -t loopx-generic-team",
                "stop": "tmux kill-session -t loopx-generic-team",
            },
            "lanes": [
                {
                    "lane_id": "planner",
                    "role_id": "planner",
                    "agent_id": "codex-main-control",
                    "agent_scope": "Plan one bounded handoff.",
                    "pane_local_a2a": {"worker_turn_configured": True},
                },
                {
                    "lane_id": "builder",
                    "role_id": "builder",
                    "agent_id": "codex-side-bypass",
                    "agent_scope": "Execute one claimed todo.",
                    "pane_local_a2a": {"worker_loop_configured": True},
                },
            ],
        }
    )
    assert compact["schema_version"] == GENERIC_MULTI_AGENT_COMPACT_STATUS_SCHEMA_VERSION, compact
    assert compact["role_count"] == 2, compact
    assert compact["roles"][0]["tick"] == "$LOOPX_PANE_A2A_TICK", compact
    assert compact["machine_json_policy"] == "artifact_only_in_visible_panes", compact

    layering = build_three_layer_minimality_contract(
        product_id="customer-support",
        preset_id="support_triage_preset",
        user_intent_fields=["inbox", "rounds"],
        preset_responsibilities=["triage_roles", "handoff_hints", "resolution_policy"],
        extension_points=["role_overrides", "ticket_adapter"],
    )
    assert layering["schema_version"] == THREE_LAYER_MINIMALITY_CONTRACT_SCHEMA_VERSION, layering
    assert layering["principle"] == (
        "user_and_preset_stay_thin_kernel_owns_reusable_mechanics"
    ), layering
    assert layering["user_layer"]["fields"] == ["inbox", "rounds"], layering
    assert "multi_agent_runner" in layering["kernel_layer"]["owns"], layering
    assert layering["kernel_layer"]["default_skills"] == [
        "loopx-project",
        "loopx-doc-registry",
    ], layering
    assert layering["kernel_layer"]["fixed_wake_prompt"] == (
        "PANE_LOCAL_A2A_WAKEUP_PROMPT"
    ), layering
    assert "pane_local_a2a_status_check" in layering["preset_layer"]["forbidden"], layering
    assert (
        layering["preset_layer"]["role_skill_limit"]
        == "role_specific_semantics_and_successor_declarations_only"
    ), layering
    assert layering["acceptance"]["other_multi_agent_products_can_reuse_kernel"] is True, layering
    assert "LoopX machine JSON hidden" in SCOPED_LOOPX_WRAPPER_PY
    assert "loopx-pane-a2a-tick" in SCOPED_LOOPX_WRAPPER_PY
    assert "LOOPX_MACHINE_JSON=1 explicitly" in SCOPED_LOOPX_WRAPPER_PY
    assert "LOOPX_CODEX_TRUST_WORKSPACE" in CODEX_TUI_EXEC_PY
    assert "trust_level" in CODEX_TUI_EXEC_PY

    source = (ROOT / "loopx/control_plane/agents/multi_agent/contract.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (
        ROOT / "loopx/control_plane/agents/multi_agent/runtime_scripts.py"
    ).read_text(
        encoding="utf-8"
    )
    assert "auto" + "_research" not in source + runtime_source
    assert "quickstart" not in (source + runtime_source).lower()
    json.dumps(compact, sort_keys=True)
    print("generic-multi-agent-runner-kernel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
