"""End-to-end host contract for the Gemini CLI and cursor-agent surfaces.

Installing discoverable files is not the same as being a usable LoopX host. The
generated `/loopx` facade tells the agent to run `start-goal ... --host-surface
<exact-current-host>`, so these tests execute that path for real: if either host
is missing from the CLI choices, the selection gate or the activation dispatch,
the facade dead-ends at argparse and the surface is decorative.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.agent_onboarding import _start_instruction, _surface_install_command
from loopx.host_loop_activation import (
    build_agent_type_catalog,
    build_host_loop_activation_packet,
    normalize_agent_type,
    scheduler_command_binding_for_agent_type,
)

NEW_HOSTS = ("gemini-cli", "cursor-agent")


def _run_cli(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def _connected_project(root: Path, goal_id: str = "surface-goal") -> Path:
    project = root / "project"
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": goal_id,
                        "domain": "test",
                        "status": "active",
                        "repo": str(project),
                        "adapter": {
                            "kind": "generic_project_goal_v0",
                            "status": "connected",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return project


@pytest.mark.parametrize("host_surface", NEW_HOSTS)
def test_start_goal_accepts_the_new_host_surface(tmp_path: Path, host_surface: str) -> None:
    """The exact command the installed facade generates must run, not exit 2."""
    project = _connected_project(tmp_path)
    result = _run_cli(
        "start-goal",
        "--guided",
        "--project",
        str(project),
        "--goal-id",
        "surface-goal",
        "--host-surface",
        host_surface,
        "--goal-text",
        "verify the host contract for this surface",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["host_surface"] == host_surface
    activation = payload["command_pack"]["host_loop_activation"]
    assert activation["agent_type"] == host_surface
    assert activation["host_surface"] == {
        "gemini-cli": "gemini_cli_agent_loop",
        "cursor-agent": "cursor_agent_loop",
    }[host_surface]


def test_host_selection_gate_offers_the_new_surfaces_and_its_rerun_command_works(
    tmp_path: Path,
) -> None:
    """The facade falls back to the selection gate when the host is unclear, so
    a host missing from the gate is unreachable even though it exists."""
    project = _connected_project(tmp_path)
    gate_result = _run_cli(
        "start-goal",
        "--guided",
        "--project",
        str(project),
        "--goal-id",
        "surface-goal",
        "--goal-text",
        "verify the host selection gate",
        cwd=tmp_path,
    )
    assert gate_result.returncode == 0, gate_result.stderr
    gate = json.loads(gate_result.stdout)["host_surface_selection_gate"]
    choices = {item["host_surface"]: item for item in gate["choices"]}
    for host_surface in NEW_HOSTS:
        assert host_surface in choices, sorted(choices)

    # Run one offered choice exactly as printed: the gate is only useful if its
    # rerun_command is executable as-is.
    tokens = shlex.split(choices["cursor-agent"]["rerun_command"])
    assert tokens[0] == "loopx"
    rerun = _run_cli(*tokens[1:], cwd=tmp_path)
    assert rerun.returncode == 0, rerun.stderr
    assert json.loads(rerun.stdout)["host_surface"] == "cursor-agent"


@pytest.mark.parametrize("agent_type", NEW_HOSTS)
def test_agent_onboarding_setup_command_installs_that_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent_type: str,
) -> None:
    """agent-onboard hands back a setup command; executing it must provision the
    host it named, from any cwd."""
    monkeypatch.delenv("LOOPX_SKILLS_DIR", raising=False)
    project = _connected_project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "GEMINI_HOME": str(tmp_path / "gemini"),
        "CURSOR_HOME": str(tmp_path / "cursor"),
    }

    onboard = _run_cli(
        "agent-onboard",
        "--agent-type",
        agent_type,
        "--project",
        str(project),
        "--goal-id",
        "surface-goal",
        cwd=outside,
        env=env,
    )
    assert onboard.returncode == 0, onboard.stderr
    payload = json.loads(onboard.stdout)
    assert payload["agent_type"] == agent_type
    # These hosts get their skills from the LoopX installer, not from a host
    # that manages skills itself.
    assert payload["skill_delivery"]["mode"] == "surface_managed"

    facade = payload["commands"]["install_command_facade"]
    assert facade is not None
    tokens = shlex.split(facade)
    assert tokens[0] == "loopx"
    install = _run_cli(*tokens[1:], cwd=outside, env=env)
    assert install.returncode == 0, install.stderr
    assert json.loads(install.stdout)["ok"] is True

    home = tmp_path / ("gemini" if agent_type == "gemini-cli" else "cursor")
    assert (home / "skills" / "loopx" / "SKILL.md").is_file()


@pytest.mark.parametrize("agent_type", NEW_HOSTS)
def test_agent_type_catalog_and_scheduler_binding(agent_type: str) -> None:
    """A host with no scheduler binding falls through to the generic default and
    the loop it actually runs stops being visible to the control plane."""
    catalog = build_agent_type_catalog()
    entry = next(
        item
        for item in catalog["canonical_agent_types"]
        if item["agent_type"] == agent_type
    )
    assert entry["display_name"]
    assert entry["host_loop"]
    # The bare product name is what a user types.
    assert agent_type.split("-")[0] in entry["accepted_inputs"]
    assert normalize_agent_type(agent_type.split("-")[0]) == agent_type
    assert scheduler_command_binding_for_agent_type(agent_type) == {
        "runtime_profile": "generic_cli"
    }


@pytest.mark.parametrize("agent_type", NEW_HOSTS)
def test_activation_claims_no_host_loop_these_clis_do_not_have(agent_type: str) -> None:
    """Neither CLI owns a goal primitive or an automation scheduler. The packet
    has to say so: an overstated capability here is what makes an agent claim
    autonomous setup it cannot deliver."""
    packet = build_host_loop_activation_packet(
        agent_type=agent_type,
        goal_id="surface-goal",
        agent_id="probe-agent",
        registered_agents=["probe-agent"],
    )
    assert packet["activation_method"] == "run_agent_cli_loop_gated_by_quota"
    assert packet["host_mutation"]["cli_can_mutate_directly"] is False
    assert packet["host_mutation"]["host_loop_primitive"] is None
    assert packet["host_mutation"]["loop_driver"] == "agent_cli_turn_loop"
    assert packet["setup_command"] == _surface_install_command(agent_type, "loopx", ".")
    assert "quota should-run" in " ".join(packet["activation_steps"])
    assert "quota should-run" in _start_instruction(agent_type)


def test_cursor_activation_names_the_registered_mcp_server() -> None:
    """cursor-agent is the one new host that also gets the LoopX MCP server, so
    its activation must point at it rather than leave the agent shelling out."""
    packet = build_host_loop_activation_packet(
        agent_type="cursor-agent",
        goal_id="surface-goal",
        agent_id="probe-agent",
        registered_agents=["probe-agent"],
    )
    mutation = packet["host_mutation"]
    assert mutation["host_mcp_server"] == "loopx"
    assert mutation["host_mcp_config"] == "CURSOR_HOME/mcp.json"
