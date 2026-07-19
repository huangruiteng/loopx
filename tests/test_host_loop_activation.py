from __future__ import annotations

import pytest

from loopx.heartbeat_prompt import build_heartbeat_prompt
from loopx.host_loop_activation import (
    AgentTypeError,
    agent_type_for_host_surface,
    build_host_loop_activation_packet,
    normalize_agent_type,
    scheduler_command_binding_for_agent_type,
)


def test_codex_ide_plugin_is_an_exact_host_type_with_visible_goal_activation() -> None:
    assert normalize_agent_type("codex-ide-plugin") == "codex-ide-plugin"
    assert normalize_agent_type("VSCode Codex") == "codex-ide-plugin"
    assert normalize_agent_type("codex-ide") == "codex-ide-plugin"
    assert agent_type_for_host_surface("codex-ide-plugin") == "codex-ide-plugin"
    assert agent_type_for_host_surface("codex-ide") == "codex-ide-plugin"
    assert agent_type_for_host_surface("codex-app") == "codex-app"
    assert agent_type_for_host_surface("codex-cli-tui") == "codex-cli"
    assert normalize_agent_type("Open Code") == "opencode"
    assert agent_type_for_host_surface("opencode") == "opencode"

    packet = build_host_loop_activation_packet(
        agent_type="codex-ide-plugin",
        goal_id="fixture-goal",
        agent_id="codex-fixture",
        registered_agents=["codex-fixture"],
    )

    assert packet["host_surface"] == "codex_ide_visible_goal_mode"
    assert packet["activation_method"] == "set_visible_goal"
    assert packet["host_mutation"]["owner"] == "Codex IDE plugin composer"
    assert packet["host_mutation"]["host_command"] == "/goal <task_body>"
    assert "automation_update" not in str(packet)
    assert (
        "--runtime-profile codex_cli"
        in packet["commands"]["heartbeat_prompt"]
    )
    assert " -H " not in packet["commands"]["heartbeat_prompt"]
    assert " -O " not in packet["commands"]["heartbeat_prompt"]
    assert " -M " not in packet["commands"]["heartbeat_prompt"]


@pytest.mark.parametrize(
    ("agent_type", "runtime_profile"),
    (
        ("codex-app", "codex_app_heartbeat"),
        ("codex-cli", "codex_cli"),
        ("codex-ide-plugin", "codex_cli"),
        ("claude-code", "claude_code"),
        ("opencode", "generic_cli"),
    ),
)
def test_first_class_hosts_bind_one_runtime_profile(
    agent_type: str,
    runtime_profile: str,
) -> None:
    assert scheduler_command_binding_for_agent_type(agent_type) == {
        "runtime_profile": runtime_profile
    }


def test_codex_app_activation_uses_narrow_runtime_profile() -> None:
    packet = build_host_loop_activation_packet(
        agent_type="codex-app",
        goal_id="fixture-goal",
        agent_id="codex-fixture",
        registered_agents=["codex-fixture"],
    )

    command = packet["commands"]["heartbeat_prompt"]
    assert "--codex-app" in command
    assert "--runtime-profile" not in command
    assert "--host-surface" not in command
    assert "--scheduler-owner" not in command
    assert "--execution-mode" not in command


def test_codex_app_thin_prompt_embeds_profile_only_in_quota_command() -> None:
    prompt = build_heartbeat_prompt(
        goal_id="fixture-goal",
        thin=True,
        runtime_profile="codex_app_heartbeat",
    )

    assert "--codex-app" in prompt["quota_guard_command"]
    assert "--codex-app" in prompt["task_body"]
    assert "host_surface" not in prompt["task_body"]
    assert "scheduler_owner" not in prompt["task_body"]
    assert "compact_prompt_command" not in prompt
    assert "brief_prompt_command" not in prompt
    assert prompt["interface_budget"]["within_budget"] is True


def test_opencode_activation_uses_bridge_tool_and_generic_cli_quota() -> None:
    packet = build_host_loop_activation_packet(
        agent_type="opencode",
        goal_id="fixture-goal",
        agent_id="opencode-fixture",
        registered_agents=["opencode-fixture"],
    )

    assert packet["host_surface"] == "opencode_visible_goal_mode"
    assert packet["activation_method"] == "activate_loopx_opencode_goal_bridge"
    assert packet["host_mutation"]["host_tool"] == "loopx_goal_activate"
    assert packet["setup_command"].endswith(
        "--surface opencode --with-goal-bridge"
    )
    assert "--runtime-profile generic_cli" in packet["commands"]["heartbeat_prompt"]


def test_ambiguous_codex_requires_app_ide_or_cli_selection() -> None:
    with pytest.raises(AgentTypeError) as caught:
        normalize_agent_type("codex")

    assert caught.value.suggestions == ["codex-app", "codex-ide-plugin", "codex-cli"]
