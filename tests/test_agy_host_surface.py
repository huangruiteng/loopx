"""End-to-end host contract for the Antigravity CLI (agy) surface.

Installing discoverable files is not the same as being a usable LoopX host. The
generated `/loopx` facade tells the agent to run `start-goal ... --host-surface
<exact-current-host>`, so these tests execute that path for real: if agy is
missing from the CLI choices, the selection gate or the activation dispatch,
the facade dead-ends at argparse and the surface is decorative.
"""

from __future__ import annotations

import json
import os
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
from loopx.slash_command_install import install_slash_commands
from loopx.agy_goal_mode import (
    AGY_GOAL_CANCELLED_TOKEN,
    AGY_GOAL_COMMAND,
    AGY_GOAL_COMMAND_DESCRIPTION,
    AGY_GOAL_COMPLETE_TOKEN,
    AGY_NATIVE_WAKE_FACTS,
    AGY_NATIVE_WAKE_TOOLS,
    agy_home,
)

HOST_SURFACE = "agy"


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


def test_start_goal_accepts_the_agy_host_surface(tmp_path: Path) -> None:
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
        HOST_SURFACE,
        "--goal-text",
        "verify the host contract for this surface",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["host_surface"] == HOST_SURFACE
    activation = payload["command_pack"]["host_loop_activation"]
    assert activation["agent_type"] == HOST_SURFACE
    assert activation["host_surface"] == "agy_agent_loop"


def test_host_selection_gate_offers_agy_and_its_rerun_command_works(
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
    assert HOST_SURFACE in choices, sorted(choices)

    # Run the offered choice exactly as printed: the gate is only useful if its
    # rerun_command is executable as-is.
    tokens = shlex.split(choices[HOST_SURFACE]["rerun_command"])
    assert tokens[0] == "loopx"
    rerun = _run_cli(*tokens[1:], cwd=tmp_path)
    assert rerun.returncode == 0, rerun.stderr
    assert json.loads(rerun.stdout)["host_surface"] == HOST_SURFACE


def test_agent_onboarding_setup_command_installs_the_agy_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent-onboard hands back a setup command; executing it must provision
    the host it named, from any cwd."""
    monkeypatch.delenv("LOOPX_SKILLS_DIR", raising=False)
    project = _connected_project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
    }
    if "PYTHONPATH" in os.environ:  # keep hermetic when run from a worktree
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]

    onboard = _run_cli(
        "agent-onboard",
        "--agent-type",
        HOST_SURFACE,
        "--project",
        str(project),
        "--goal-id",
        "surface-goal",
        cwd=outside,
        env=env,
    )
    assert onboard.returncode == 0, onboard.stderr
    payload = json.loads(onboard.stdout)
    assert payload["agent_type"] == HOST_SURFACE
    # Antigravity CLI gets its skills from the LoopX installer, not from a host
    # that manages skills itself.
    assert payload["skill_delivery"]["mode"] == "surface_managed"

    facade = payload["commands"]["install_command_facade"]
    assert facade is not None
    tokens = shlex.split(facade)
    assert tokens[0] == "loopx"
    install = _run_cli(*tokens[1:], cwd=outside, env=env)
    assert install.returncode == 0, install.stderr
    assert json.loads(install.stdout)["ok"] is True

    skills_root = tmp_path / "home" / ".gemini" / "antigravity-cli" / "skills"
    assert (skills_root / "loopx.md").is_file()


def test_agy_home_is_the_documented_fixed_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The official CLI documents no home override, so LoopX exposes none:
    # only HOME itself (tests stay hermetic) and the internal injection
    # parameter move the root.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert agy_home() == tmp_path / "home" / ".gemini" / "antigravity-cli"
    assert agy_home(str(tmp_path / "explicit")) == tmp_path / "explicit"


def test_installer_preserves_user_owned_agy_skill(tmp_path: Path) -> None:
    """The skills root is shared with the user's own skills; an unmarked file
    must never be overwritten, and a rerun over a managed file is a no-op."""
    skills_dir = tmp_path / "agy-home" / "skills"
    skill_path = skills_dir / "loopx.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("user-owned skill body\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        surfaces=["agy"],
        agy_home=str(tmp_path / "agy-home"),
    )
    statuses = {
        (item["surface"], item["command"]): item["status"] for item in payload["installed"]
    }
    assert statuses[("agy", "/loopx")] == "skipped_user_file"
    assert skill_path.read_text(encoding="utf-8") == "user-owned skill body\n"

    skill_path.write_text(
        "<!-- loopx-managed-slash-command:v1 command=/loopx surface=claude-skills -->\nold\n",
        encoding="utf-8",
    )
    payload = install_slash_commands(
        execute=True,
        surfaces=["agy"],
        agy_home=str(tmp_path / "agy-home"),
    )
    statuses = {
        (item["surface"], item["command"]): item["status"] for item in payload["installed"]
    }
    assert statuses[("agy", "/loopx")] == "updated"
    assert "user-owned skill body" not in skill_path.read_text(encoding="utf-8")

    retire = install_slash_commands(
        execute=True,
        uninstall=True,
        surfaces=["agy"],
        agy_home=str(tmp_path / "agy-home"),
    )
    assert not skill_path.exists()
    assert retire["ok"] is True


def test_agent_type_catalog_and_scheduler_binding() -> None:
    """A host with no scheduler binding falls through to the generic default and
    the loop it actually runs stops being visible to the control plane."""
    catalog = build_agent_type_catalog()
    entry = next(
        item
        for item in catalog["canonical_agent_types"]
        if item["agent_type"] == HOST_SURFACE
    )
    assert entry["display_name"] == "Antigravity CLI"
    assert entry["host_loop"]
    # The bare product name is what a user types.
    assert HOST_SURFACE in entry["accepted_inputs"]
    assert normalize_agent_type("agy") == HOST_SURFACE
    assert normalize_agent_type("antigravity") == HOST_SURFACE
    assert normalize_agent_type("antigravity-cli") == HOST_SURFACE
    assert scheduler_command_binding_for_agent_type(HOST_SURFACE) == {
        "runtime_profile": "generic_cli"
    }


def test_activation_binds_native_goal_and_wake_and_keeps_the_quota_gate() -> None:
    """Antigravity CLI owns both a native goal primitive (the `/goal` command
    with host-side forced continuation until `<!-- GOAL_COMPLETE -->`,
    live-verified in the TUI and headless `-p`) and a native in-session
    scheduler (the `schedule` tool plus background-task/subagent wakes).
    The packet has to state exactly that capability envelope: bind the
    objective via `/goal`, arm self-wakes with `schedule`, keep every turn,
    wake and audit-continuation gated through quota, and admit the loop dies
    with the session — an overstated capability here is what makes an agent
    claim autonomous setup it cannot deliver."""
    packet = build_host_loop_activation_packet(
        agent_type=HOST_SURFACE,
        goal_id="surface-goal",
        agent_id="probe-agent",
        registered_agents=["probe-agent"],
    )
    assert (
        packet["activation_method"] == "bind_native_goal_with_advisory_quota_entry"
    )
    assert packet["host_mutation"]["cli_can_mutate_directly"] is False
    # Both native primitives are real and must be named, not denied.
    assert (
        packet["host_mutation"]["host_loop_primitive"] == "agy-/goal-and-schedule-tool"
    )
    assert (
        packet["host_mutation"]["loop_driver"]
        == "agy_native_goal_loop_with_schedule_wakes"
    )
    # The quota claim must be honest: advisory guidance, no host hook.
    assert (
        packet["host_mutation"]["quota_gate_enforcement"] == "advisory_only"
    )
    assert packet["host_mutation"]["native_goal_command"] == "/goal"
    assert packet["host_mutation"]["goal_complete_token"] == AGY_GOAL_COMPLETE_TOKEN
    assert packet["host_mutation"]["goal_cancelled_token"] == AGY_GOAL_CANCELLED_TOKEN
    assert "schedule" in packet["host_mutation"]["native_wake_tools"]
    assert "manage_task" in packet["host_mutation"]["native_wake_tools"]
    # The loop dies with the CLI session; the gate text must say so instead of
    # promising unattended heartbeat support.
    gate = packet["host_mutation"]["missing_host_tool_gate"]
    assert "only" in gate and "alive" in gate
    assert "daemon" in gate
    steps = " ".join(packet["activation_steps"])
    assert "`/goal <task_body>`" in steps
    assert AGY_GOAL_COMPLETE_TOKEN in steps
    assert "`schedule` tool" in steps
    assert "MaxIterations" in steps
    assert "quota should-run" in steps
    assert "no host scheduler to fall back on" not in steps
    assert packet["setup_command"] == _surface_install_command(HOST_SURFACE, "loopx", ".")
    assert "quota should-run" in _start_instruction(HOST_SURFACE)
    assert "/goal" in _start_instruction(HOST_SURFACE)
    assert (
        packet["entry_command_hint"]
        == "the LoopX skill installed in ~/.gemini/antigravity-cli/skills"
    )


def test_native_goal_and_wake_facts_match_the_live_probes() -> None:
    """The host-facts constants are the single source the activation packet,
    README and PR narrative cite; they must stay pinned to what the live
    agy 1.1.18 probes actually demonstrated."""
    assert AGY_GOAL_COMMAND == "/goal"
    assert "completely finished" in AGY_GOAL_COMMAND_DESCRIPTION
    assert AGY_GOAL_COMPLETE_TOKEN == "<!-- GOAL_COMPLETE -->"
    assert AGY_GOAL_CANCELLED_TOKEN == "<!-- GOAL_CANCELLED -->"
    facts = " ".join(AGY_NATIVE_WAKE_FACTS)
    assert "DurationSeconds" in facts and "Prompt" in facts
    assert "MaxIterations" in facts
    assert "hooks.json" in facts
    assert set(AGY_NATIVE_WAKE_TOOLS) >= {
        "schedule",
        "manage_task",
        "invoke_subagent",
        "send_message",
        "manage_inbox",
    }
