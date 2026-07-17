from __future__ import annotations

import pytest

from loopx.heartbeat_prompt import build_heartbeat_prompt
from loopx.host_loop_activation import (
    AgentTypeError,
    agent_type_for_host_surface,
    build_host_loop_activation_packet,
    normalize_agent_type,
)


def test_codex_ide_is_an_exact_host_type_with_visible_goal_activation() -> None:
    assert normalize_agent_type("VSCode Codex") == "codex-ide"
    assert agent_type_for_host_surface("codex-ide") == "codex-ide"

    packet = build_host_loop_activation_packet(
        agent_type="codex-ide",
        goal_id="fixture-goal",
        agent_id="codex-fixture",
        registered_agents=["codex-fixture"],
    )

    assert packet["host_surface"] == "codex_ide_visible_goal_mode"
    assert packet["activation_method"] == "set_visible_goal"
    assert packet["host_mutation"]["owner"] == "Codex IDE composer"
    assert packet["host_mutation"]["host_command"] == "/goal <task_body>"
    assert "automation_update" not in str(packet)
    assert "--host-surface codex_cli" in packet["commands"]["heartbeat_prompt"]
    assert "--scheduler-owner agent_cli_loop" in packet["commands"]["heartbeat_prompt"]
    assert "--execution-mode interactive" in packet["commands"]["heartbeat_prompt"]


def test_codex_app_activation_uses_narrow_runtime_profile() -> None:
    packet = build_host_loop_activation_packet(
        agent_type="codex-app",
        goal_id="fixture-goal",
        agent_id="codex-fixture",
        registered_agents=["codex-fixture"],
    )

    command = packet["commands"]["heartbeat_prompt"]
    assert "--runtime-profile codex_app_heartbeat" in command
    assert "--host-surface" not in command
    assert "--scheduler-owner" not in command
    assert "--execution-mode" not in command


def test_codex_app_thin_prompt_embeds_profile_only_in_quota_command() -> None:
    prompt = build_heartbeat_prompt(
        goal_id="fixture-goal",
        thin=True,
        runtime_profile="codex_app_heartbeat",
    )

    assert "--runtime-profile codex_app_heartbeat" in prompt["quota_guard_command"]
    assert "--runtime-profile codex_app_heartbeat" in prompt["task_body"]
    assert "host_surface" not in prompt["task_body"]
    assert "scheduler_owner" not in prompt["task_body"]
    assert "compact_prompt_command" not in prompt
    assert "brief_prompt_command" not in prompt
    assert prompt["interface_budget"]["within_budget"] is True


def test_ambiguous_codex_requires_app_ide_or_cli_selection() -> None:
    with pytest.raises(AgentTypeError) as caught:
        normalize_agent_type("codex")

    assert caught.value.suggestions == ["codex-app", "codex-ide", "codex-cli"]
