#!/usr/bin/env python3
"""Smoke-test agent onboarding and host-loop activation routing."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.agent_onboarding import build_agent_onboarding_packet  # noqa: E402
from loopx.bootstrap_command_pack import (  # noqa: E402
    build_loopx_bootstrap_command_pack,
    build_start_goal_guided_packet,
)
from loopx.host_loop_activation import (  # noqa: E402
    agent_type_for_host_surface,
    build_agent_type_catalog,
    build_host_loop_activation_packet,
)


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def main() -> int:
    catalog = build_agent_type_catalog()
    agent_types = {item["agent_type"] for item in catalog["canonical_agent_types"]}
    assert {
        "codex-app",
        "codex-ide-plugin",
        "codex-cli",
        "claude-code",
        "opencode",
        "manual",
        "other-agent",
    } <= agent_types
    ambiguous = {item["input"]: item["use_one_of"] for item in catalog["ambiguous_inputs"]}
    assert ambiguous["codex"] == ["codex-app", "codex-ide-plugin", "codex-cli"], ambiguous

    assert agent_type_for_host_surface("chat-box") == "codex-app"
    assert agent_type_for_host_surface("codex-ide-plugin") == "codex-ide-plugin"
    assert agent_type_for_host_surface("codex-ide") == "codex-ide-plugin"
    assert agent_type_for_host_surface("codex-cli-tui") == "codex-cli"
    assert agent_type_for_host_surface("opencode") == "opencode"

    codex_app = build_host_loop_activation_packet(agent_type="codex-app", goal_id="demo")
    codex_ide = build_host_loop_activation_packet(agent_type="codex-ide-plugin", goal_id="demo")
    codex_cli = build_host_loop_activation_packet(agent_type="codex-cli", goal_id="demo")
    claude_code = build_host_loop_activation_packet(agent_type="claude-code", goal_id="demo")
    opencode = build_host_loop_activation_packet(agent_type="opencode", goal_id="demo")
    assert codex_app["activation_method"] == "create_or_update_codex_app_automation", codex_app
    assert codex_ide["activation_method"] == "set_visible_goal", codex_ide
    assert codex_ide["host_mutation"]["host_command"] == "/goal <task_body>", codex_ide
    assert codex_cli["host_mutation"]["host_command"] == "/goal <task_body>", codex_cli
    assert claude_code["host_mutation"]["host_command"] == "/loop", claude_code
    assert opencode["activation_method"] == "activate_loopx_opencode_goal_bridge", opencode
    assert opencode["host_mutation"]["host_tool"] == "loopx_goal_activate", opencode
    assert "--runtime-profile generic_cli" in opencode["commands"]["heartbeat_prompt"], opencode
    gated_activation = build_host_loop_activation_packet(
        agent_type="codex-app",
        goal_id="multi-agent-demo",
        registered_agents=["codex-main-control", "codex-product-capability"],
    )
    assert gated_activation["activation_state"] == "selection_required", gated_activation
    assert gated_activation["activation_allowed"] is False, gated_activation
    assert gated_activation["activation_input_command"] is None, gated_activation
    assert len(gated_activation["identity_selection_gate"]["choices"]) == 2, gated_activation
    peer_activation = build_host_loop_activation_packet(
        agent_type="codex-app",
        goal_id="peer-agent-demo",
        registered_agents=["codex-alpha", "codex-beta"],
    )
    assert peer_activation["agent_model"] == "peer_v1", peer_activation
    assert "primary_agent" not in peer_activation["identity_contract"], peer_activation
    assert all(
        "role" not in choice
        for choice in peer_activation["identity_selection_gate"]["choices"]
    ), peer_activation
    single_agent_activation = build_host_loop_activation_packet(
        agent_type="codex-app",
        goal_id="single-agent-demo",
        registered_agents=["codex-main-control"],
    )
    assert single_agent_activation["activation_state"] == "single_registered_agent_selected"
    assert single_agent_activation["agent_id"] == "codex-main-control"
    assert single_agent_activation["activation_allowed"] is True
    assert "--agent-id codex-main-control" in single_agent_activation["activation_input_command"]

    list_result = run_cli("agent-onboard", "--list-agent-types")
    list_payload = json.loads(list_result.stdout)
    assert list_payload["schema_version"] == "loopx_agent_type_catalog_v0", list_payload

    ambiguous_result = run_cli(
        "agent-onboard",
        "--agent-type",
        "codex",
        "--project",
        ".",
        check=False,
    )
    assert ambiguous_result.returncode == 2, ambiguous_result.stdout
    ambiguous_payload = json.loads(ambiguous_result.stdout)
    assert ambiguous_payload["ok"] is False, ambiguous_payload
    assert ambiguous_payload["suggestions"] == [
        "codex-app",
        "codex-ide-plugin",
        "codex-cli",
    ], ambiguous_payload

    with tempfile.TemporaryDirectory(prefix="loopx-agent-onboard-smoke-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        payload = build_loopx_bootstrap_command_pack(
            project=project,
            goal_id="demo-goal",
            agent_id="codex-value-explorer",
            cli_bin="loopx",
            host_surface="codex-cli-tui",
            goal_text="build a deterministic onboarding path",
        )
    assert payload["agent_type"] == "codex-cli", payload
    activation = payload["host_loop_activation"]
    assert activation["host_surface"] == "codex_cli_visible_goal_mode", activation
    contract = payload["goal_start_contract"]
    assert contract["activation"]["host_loop_required_after_todo_writeback"] is True, contract
    assert payload["safety_contract"]["explicit_goal_start_must_activate_host_loop"] is True, payload
    message = payload["message"]
    assert "/goal <task_body>" in message, message
    assert "agent-onboard" in message, message

    with tempfile.TemporaryDirectory(prefix="loopx-agent-onboard-identity-") as tmp:
        root = Path(tmp)
        project = root / "project"
        home = root / "home"
        state_file = project / ".codex" / "goals" / "multi-agent-goal" / "ACTIVE_GOAL_STATE.md"
        project_registry = project / ".loopx" / "registry.json"
        global_registry = home / ".codex" / "loopx" / "registry.global.json"
        state_file.parent.mkdir(parents=True)
        project_registry.parent.mkdir(parents=True)
        global_registry.parent.mkdir(parents=True)
        state_file.write_text("# Active State\n", encoding="utf-8")
        registry = {
            "goals": [
                {
                    "id": "multi-agent-goal",
                    "domain": "smoke",
                    "status": "active",
                    "repo": str(project),
                    "state_file": ".codex/goals/multi-agent-goal/ACTIVE_GOAL_STATE.md",
                    "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                    "coordination": {
                        "agent_model": "peer_v1",
                        "registered_agents": [
                            "codex-main-control",
                            "codex-product-capability",
                        ],
                    },
                }
            ]
        }
        serialized_registry = json.dumps(registry)
        project_registry.write_text(serialized_registry, encoding="utf-8")
        global_registry.write_text(serialized_registry, encoding="utf-8")
        cli_bin = str(REPO_ROOT / "scripts" / "loopx")

        onboarding_gate = build_agent_onboarding_packet(
            project=project,
            agent_type="codex-app",
            goal_id="multi-agent-goal",
            cli_bin=cli_bin,
        )
        gate = onboarding_gate["identity_selection_gate"]
        assert onboarding_gate["host_loop_activation"]["activation_allowed"] is False
        assert onboarding_gate["commands"]["quota_guard"] is None
        assert onboarding_gate["host_loop_activation"]["activation_input_command"] is None
        assert len(gate["choices"]) == 2, onboarding_gate
        selected_choice = next(
            choice
            for choice in gate["choices"]
            if choice["agent_id"] == "codex-product-capability"
        )
        assert "--agent-id codex-product-capability" in selected_choice["heartbeat_prompt_json"]
        assert "--agent-scope" in selected_choice["heartbeat_prompt_json"]

        choice_run = subprocess.run(
            shlex.split(selected_choice["heartbeat_prompt_json"]),
            cwd=REPO_ROOT,
            env={**os.environ, "HOME": str(home)},
            check=True,
            text=True,
            capture_output=True,
        )
        choice_payload = json.loads(choice_run.stdout)
        assert choice_payload["ok"] is True, choice_payload
        assert choice_payload["agent_id"] == "codex-product-capability", choice_payload
        assert choice_payload["task_body"], choice_payload

        command_pack_gate = build_loopx_bootstrap_command_pack(
            project=project,
            goal_id="multi-agent-goal",
            agent_id=None,
            cli_bin=cli_bin,
            host_surface="codex-app",
            goal_text="fix a public issue",
        )
        assert command_pack_gate["recommended_next_step"]["kind"] == "select_agent_identity"
        assert command_pack_gate["commands"]["heartbeat_prompt_json"] is None
        assert command_pack_gate["commands"]["goal_start_quota_should_run"] is None
        assert "No unscoped heartbeat or quota command" in command_pack_gate["message"]

        guided_gate = build_start_goal_guided_packet(
            project=project,
            goal_id="multi-agent-goal",
            agent_id=None,
            cli_bin=cli_bin,
            host_surface="codex-app",
            goal_text="fix a public issue",
        )
        transaction = guided_gate["guided_transaction"]
        assert transaction["blocked_by"] == "agent_identity_selection", transaction
        assert transaction["ordered_steps"][1]["id"] == "select_agent_identity", transaction

        selected_pack = build_loopx_bootstrap_command_pack(
            project=project,
            goal_id="multi-agent-goal",
            agent_id="codex-product-capability",
            cli_bin=cli_bin,
            host_surface="codex-app",
            goal_text="fix a public issue",
            available_capabilities=["network", "external_evidence_poll"],
        )
        assert selected_pack["host_loop_activation"]["activation_allowed"] is True
        for key in (
            "heartbeat_prompt_json",
            "quota_guard",
            "goal_start_agent_onboard_recheck",
            "goal_start_quota_should_run",
        ):
            assert "--agent-id codex-product-capability" in selected_pack["commands"][key], (
                key,
                selected_pack["commands"],
            )
            assert "--available-capability network" in selected_pack["commands"][key], (
                key,
                selected_pack["commands"],
            )
            assert "--available-capability external_evidence_poll" in selected_pack["commands"][key], (
                key,
                selected_pack["commands"],
            )

        ide_onboarding = build_agent_onboarding_packet(
            project=project,
            agent_type="codex-ide-plugin",
            goal_id="multi-agent-goal",
            agent_id="codex-product-capability",
            cli_bin=cli_bin,
        )
        ide_bootstrap = ide_onboarding["commands"]["bootstrap_command_pack"]
        assert "--host-surface codex-ide-plugin" in ide_bootstrap, ide_onboarding
        assert "worker-bridge" not in ide_bootstrap, ide_onboarding
        assert "visible IDE plugin" in ide_onboarding["recommended_start"], ide_onboarding

        opencode_onboarding = build_agent_onboarding_packet(
            project=project,
            agent_type="opencode",
            goal_id="multi-agent-goal",
            agent_id="codex-product-capability",
            cli_bin=cli_bin,
        )
        assert "--host-surface opencode" in opencode_onboarding["commands"]["bootstrap_command_pack"]
        assert opencode_onboarding["commands"]["install_command_facade"].endswith(
            "--surface opencode --with-goal-bridge"
        )
        assert opencode_onboarding["host_loop_activation"]["host_mutation"]["host_tool"] == (
            "loopx_goal_activate"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
