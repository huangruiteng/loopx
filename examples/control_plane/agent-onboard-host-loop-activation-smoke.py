#!/usr/bin/env python3
"""Smoke-test agent onboarding and host-loop activation routing."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.bootstrap_command_pack import build_loopx_bootstrap_command_pack  # noqa: E402
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
    assert {"codex-app", "codex-cli", "claude-code", "manual", "other-agent"} <= agent_types
    ambiguous = {item["input"]: item["use_one_of"] for item in catalog["ambiguous_inputs"]}
    assert ambiguous["codex"] == ["codex-app", "codex-cli"], ambiguous

    assert agent_type_for_host_surface("chat-box") == "codex-app"
    assert agent_type_for_host_surface("codex-cli-tui") == "codex-cli"

    codex_app = build_host_loop_activation_packet(agent_type="codex-app", goal_id="demo")
    codex_cli = build_host_loop_activation_packet(agent_type="codex-cli", goal_id="demo")
    claude_code = build_host_loop_activation_packet(agent_type="claude-code", goal_id="demo")
    assert codex_app["activation_method"] == "create_or_update_codex_app_automation", codex_app
    assert codex_cli["host_mutation"]["host_command"] == "/goal <task_body>", codex_cli
    assert claude_code["host_mutation"]["host_command"] == "/loop", claude_code

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
    assert ambiguous_payload["suggestions"] == ["codex-app", "codex-cli"], ambiguous_payload

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
