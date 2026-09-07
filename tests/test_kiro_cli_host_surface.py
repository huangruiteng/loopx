"""End-to-end host contract for the Kiro CLI surface.

Installing discoverable files is not the same as being a usable LoopX host. The
generated `/loopx` facade tells the agent to run `start-goal ... --host-surface
<exact-current-host>`, so these tests execute that path for real: if kiro-cli
is missing from the CLI choices, the selection gate or the activation dispatch,
the facade dead-ends at argparse and the surface is decorative.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest
import yaml
from host_surface_cli_probes import (
    onboarding_setup_command_installs,
    selection_gate_offers_surface,
    start_goal_accepts_surface,
)

from loopx.agent_onboarding import _start_instruction, _surface_install_command
from loopx.capabilities.project_skill_delivery import (
    PROJECT_SKILL_SURFACE_ROOTS,
    PROJECT_SKILL_SURFACES,
)
from loopx.chat_actions import ChatActionService
from loopx.chat_endpoints import RESERVED_AGENT_IDS, AgentEndpointRegistry
from loopx.chat_runtime import ChatRuntimeController
from loopx.chat_store import ChatSessionStore
from loopx.cli_commands._host_thread import (
    HOST_THREAD_ID_ENV,
    current_host_thread_id,
)
from loopx.host_loop_activation import (
    _heartbeat_commands,
    build_agent_type_catalog,
    build_host_loop_activation_packet,
    normalize_agent_type,
    scheduler_command_binding_for_agent_type,
)
from loopx.kiro_cli_goal_mode import (
    KIRO_CLI_CHAT_AGENT_ID,
    KIRO_CLI_GOAL_AGENT_FLAG,
    KIRO_CLI_GOAL_CLEAR_COMMAND,
    KIRO_CLI_GOAL_COMMAND,
    KIRO_CLI_GOAL_COMPLETION_TOOL,
    KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS,
    KIRO_CLI_GOAL_MAX_ITERATION_CEILING,
    KIRO_CLI_GOAL_STATUS_COMMAND,
    KIRO_CLI_GOAL_VALIDATE_FLAG,
    KIRO_CLI_HOOK_TRIGGERS,
    KIRO_CLI_NATIVE_GOAL_FACTS,
    KIRO_CLI_SESSION_ID_ENV,
    kiro_cli_chat_command,
    kiro_home,
)
from loopx.slash_command_install import install_slash_commands

HOST_SURFACE = "kiro-cli"


def _executable_stub(path: Path) -> Path:
    """A file that only has to satisfy the runtime's PATH availability probe."""
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_start_goal_accepts_the_kiro_cli_host_surface(tmp_path: Path) -> None:
    payload = start_goal_accepts_surface(HOST_SURFACE, tmp_path)
    activation = payload["command_pack"]["host_loop_activation"]
    assert activation["host_surface"] == "kiro_cli_agent_loop"


def test_host_selection_gate_offers_kiro_cli_and_its_rerun_command_works(
    tmp_path: Path,
) -> None:
    selection_gate_offers_surface(HOST_SURFACE, tmp_path)


def test_agent_onboarding_setup_command_installs_the_kiro_cli_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOOPX_SKILLS_DIR", raising=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
    }
    if "PYTHONPATH" in os.environ:  # keep hermetic when run from a worktree
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]

    # Kiro CLI reads global skills from ~/.kiro/skills/<name>/SKILL.md, the
    # per-skill directory layout, not one flat file per skill.
    onboarding_setup_command_installs(
        HOST_SURFACE,
        outside,
        env,
        expected_skill=(tmp_path / "home" / ".kiro" / "skills" / "loopx" / "SKILL.md"),
    )


def test_kiro_home_is_the_documented_fixed_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The host documents no home override for the skills root
    # (KIRO_AGENT_CONFIG_DIR relocates agent configs only), so LoopX exposes
    # none: only HOME itself (tests stay hermetic) and the internal injection
    # parameter move the root.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("KIRO_AGENT_CONFIG_DIR", str(tmp_path / "elsewhere"))
    assert kiro_home() == tmp_path / "home" / ".kiro"
    assert kiro_home(str(tmp_path / "explicit")) == tmp_path / "explicit"


def test_installed_skills_are_invocable_as_kiro_slash_commands(
    tmp_path: Path,
) -> None:
    """Kiro exposes every discovered skill as `/<skill-name>`, so the reported
    invocation must be the slash form the user actually types — a bare skill id
    would send them looking for a menu the host does not have."""
    payload = install_slash_commands(
        execute=True,
        surfaces=["kiro"],  # the bare product name must resolve to the surface
        kiro_home=str(tmp_path / "kiro-home"),
    )
    assert payload["ok"] is True
    assert payload["effective_surfaces"] == [HOST_SURFACE]
    rows = {
        item["command"]: item
        for item in payload["installed"]
        if item["surface"] == HOST_SURFACE
    }
    assert rows["/loopx"]["invoke_as"] == ["/loopx"]
    assert rows["/loopx"]["mechanism"] == "kiro_cli_skills"
    assert (
        payload["summary"]["kiro_cli_skill_dir"]
        == str(tmp_path / "kiro-home" / "skills")
    )
    assert (tmp_path / "kiro-home" / "skills" / "loopx" / "SKILL.md").is_file()


def test_installed_skill_front_matter_keeps_names_unquoted(tmp_path: Path) -> None:
    """Kiro derives the slash command from the front-matter `name`, and its
    reader keeps quote characters verbatim: `name: "loopx"` becomes the command
    `/"loopx"`. So the name must be a plain YAML scalar. Values YAML genuinely
    needs quoted (a leading `[`, an embedded `": "`) must stay quoted, or a
    strict reader rejects the whole front matter."""
    install_slash_commands(
        execute=True,
        surfaces=[HOST_SURFACE],
        kiro_home=str(tmp_path / "kiro-home"),
    )
    skills = sorted((tmp_path / "kiro-home" / "skills").glob("*/SKILL.md"))
    assert skills, "installer wrote no skills"
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        front_matter = text.split("---", 2)[1]
        fields = yaml.safe_load(front_matter)
        assert fields["name"] == skill.parent.name
        assert '"' not in fields["name"]
        assert f"name: {skill.parent.name}\n" in text

    # The values that must stay quoted, proven on the shipped specs rather than
    # asserted in the abstract.
    entry = (tmp_path / "kiro-home" / "skills" / "loopx" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert 'argument-hint: "[' in entry  # a bare [ would parse as a flow sequence
    research = (
        tmp_path / "kiro-home" / "skills" / "loopx-deepresearch" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert 'description: "' in research  # contains ": ", illegal unquoted


def test_installer_preserves_user_owned_kiro_skill(tmp_path: Path) -> None:
    """The skills root is shared with the user's own skills; an unmarked file
    must never be overwritten, and a rerun over a managed file is a no-op."""
    skills_dir = tmp_path / "kiro-home" / "skills"
    skill_path = skills_dir / "loopx" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("user-owned skill body\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        surfaces=[HOST_SURFACE],
        kiro_home=str(tmp_path / "kiro-home"),
    )
    statuses = {
        (item["surface"], item["command"]): item["status"]
        for item in payload["installed"]
    }
    assert statuses[(HOST_SURFACE, "/loopx")] == "skipped_user_file"
    assert skill_path.read_text(encoding="utf-8") == "user-owned skill body\n"

    skill_path.write_text(
        "<!-- loopx-managed-slash-command:v1 command=/loopx surface=claude-skills -->\nold\n",
        encoding="utf-8",
    )
    payload = install_slash_commands(
        execute=True,
        surfaces=[HOST_SURFACE],
        kiro_home=str(tmp_path / "kiro-home"),
    )
    statuses = {
        (item["surface"], item["command"]): item["status"]
        for item in payload["installed"]
    }
    assert statuses[(HOST_SURFACE, "/loopx")] == "updated"
    assert "user-owned skill body" not in skill_path.read_text(encoding="utf-8")

    retire = install_slash_commands(
        execute=True,
        uninstall=True,
        surfaces=[HOST_SURFACE],
        kiro_home=str(tmp_path / "kiro-home"),
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
    assert entry["display_name"] == "Kiro CLI"
    assert entry["host_loop"]
    assert "gated" not in entry["host_loop"].lower()
    assert "advisory" in entry["host_loop"].lower()
    # The bare product name is what a user types.
    assert "kiro" in entry["accepted_inputs"]
    assert normalize_agent_type("kiro") == HOST_SURFACE
    assert normalize_agent_type("kiro-cli") == HOST_SURFACE
    assert normalize_agent_type("Kiro CLI") == HOST_SURFACE
    assert scheduler_command_binding_for_agent_type(HOST_SURFACE) == {
        "runtime_profile": "generic_cli"
    }


def test_activation_binds_native_goal_with_advisory_quota_entry() -> None:
    """Kiro CLI owns a native goal primitive (`/goal <task> [--max N]`, whose
    host-side loop re-dispatches turns until the `goal` tool proves completion)
    and a host-enforced iteration budget. The packet has to state exactly that
    capability envelope: bind the objective via `/goal`, bound it by quota and
    the host ceiling, state advisory quota pacing without claiming a host hook
    intercepts iterations, and admit the loop dies with the session — an
    overstated capability here is what makes an agent claim autonomous setup it
    cannot deliver."""
    packet = build_host_loop_activation_packet(
        agent_type=HOST_SURFACE,
        goal_id="surface-goal",
        agent_id="probe-agent",
        registered_agents=["probe-agent"],
    )
    assert packet["activation_method"] == "bind_native_goal_with_advisory_quota_entry"
    mutation = packet["host_mutation"]
    assert mutation["cli_can_mutate_directly"] is False
    # The native primitive is real and must be named, not denied.
    assert mutation["host_loop_primitive"] == "kiro-cli-/goal-iteration-loop"
    assert mutation["loop_driver"] == "kiro_cli_native_goal_loop"
    # The quota claim must be honest: advisory guidance, no installed hook.
    assert mutation["quota_gate_enforcement"] == "advisory_only"
    assert mutation["native_goal_command"] == KIRO_CLI_GOAL_COMMAND
    assert mutation["native_goal_cancel_command"] == KIRO_CLI_GOAL_CLEAR_COMMAND
    assert mutation["native_goal_status_command"] == KIRO_CLI_GOAL_STATUS_COMMAND
    assert mutation["native_goal_validate_flag"] == KIRO_CLI_GOAL_VALIDATE_FLAG
    assert (
        mutation["native_goal_max_iteration_ceiling"]
        == KIRO_CLI_GOAL_MAX_ITERATION_CEILING
    )
    assert (
        mutation["native_goal_default_max_iterations"]
        == KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS
    )
    assert mutation["native_goal_completion_tool"] == KIRO_CLI_GOAL_COMPLETION_TOOL
    assert mutation["host_session_id_env"] == KIRO_CLI_SESSION_ID_ENV
    # The hook seam exists but LoopX installs none; recording the triggers must
    # not be read as a claim of enforcement.
    assert "preToolUse" in mutation["host_hook_triggers"]
    # The loop dies with the CLI session; the gate text must say so instead of
    # promising unattended heartbeat support.
    gate = mutation["missing_host_tool_gate"]
    assert "only" in gate
    assert "alive" in gate
    assert "daemon" in gate
    assert "advisory" in gate
    assert "installs no Kiro hook" in gate

    steps = " ".join(packet["activation_steps"])
    assert "`/goal <task_body> --max <N>`" in steps
    assert str(KIRO_CLI_GOAL_MAX_ITERATION_CEILING) in steps
    assert "quota should-run" in steps
    assert KIRO_CLI_GOAL_COMPLETION_TOOL in steps
    assert "no host scheduler to fall back on" not in steps
    # The host judges each iteration against --validate criteria; binding the
    # goal without them leaves the host checking nothing LoopX will accept.
    assert KIRO_CLI_GOAL_VALIDATE_FLAG in steps
    assert KIRO_CLI_GOAL_STATUS_COMMAND in steps

    assert packet["setup_command"] == _surface_install_command(
        HOST_SURFACE, "loopx", "."
    )
    assert "quota should-run" in _start_instruction(HOST_SURFACE)
    assert "/goal" in _start_instruction(HOST_SURFACE)
    assert (
        packet["entry_command_hint"] == "the LoopX skill installed in ~/.kiro/skills"
    )
    # Rendered heartbeat commands and scope must carry no machine-gate semantics.
    assert "gated" not in packet["activation_input_command"].lower()
    assert "advisory" in packet["activation_input_command"].lower()
    hb = _heartbeat_commands(
        goal_id="surface-goal",
        agent_type=HOST_SURFACE,
        cli_bin="loopx",
        agent_id="probe-agent",
    )
    assert "gated" not in hb["heartbeat_prompt"].lower()
    assert "gated" not in hb["heartbeat_prompt_json"].lower()
    assert "advisory" in hb["heartbeat_prompt"].lower()
    assert "advisory" in hb["heartbeat_prompt_json"].lower()


def test_dashboard_lists_kiro_cli_as_a_builtin_chat_agent(tmp_path: Path) -> None:
    """`loopx dashboard` renders its Agent picker from the running process's
    capability rows, so a host is only reachable there if it appears as a row
    with an adapter the runtime can actually start. Kiro CLI ships an ACP agent,
    so the row must be built-in, ACP-shaped, and read-only — and its id must be
    reserved, or an owner-local endpoint could shadow the built-in adapter."""
    controller = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "runtime"),
        codex_bin="loopx-missing-codex-for-test",
        kiro_cli_bin=str(_executable_stub(tmp_path / "kiro-cli")),
    )
    try:
        rows = controller.capabilities()
        row = next(
            item for item in rows if item["agent_id"] == KIRO_CLI_CHAT_AGENT_ID
        )
        assert row["source"] == "builtin"
        assert row["adapter_kind"] == "acp"
        assert row["display_name"] == "Kiro CLI"
        assert row["trust_scope"] == "read_only"
        assert row["available"] is True
    finally:
        controller.close()

    # The launch argv must not auto-approve tools: LoopX Chat cancels every ACP
    # permission request, and a trust flag here would bypass that decision.
    command = kiro_cli_chat_command("kiro-cli")
    assert command == ("kiro-cli", "acp")
    assert not any("trust" in argument for argument in command)

    assert KIRO_CLI_CHAT_AGENT_ID in RESERVED_AGENT_IDS
    with pytest.raises(ValueError, match="reserved"):
        AgentEndpointRegistry(tmp_path / "endpoints").upsert(
            {
                "agent_id": KIRO_CLI_CHAT_AGENT_ID,
                "display_name": "Shadow Kiro",
                "command": ["kiro-cli", "acp"],
            }
        )


def test_missing_kiro_cli_renders_as_needing_configuration(tmp_path: Path) -> None:
    """An uninstalled host must render as unavailable rather than failing when a
    session opens; `available` is a live probe, not a static claim."""
    controller = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "runtime"),
        codex_bin="loopx-missing-codex-for-test",
        kiro_cli_bin="loopx-missing-kiro-cli-for-test",
    )
    try:
        row = next(
            item
            for item in controller.capabilities()
            if item["agent_id"] == KIRO_CLI_CHAT_AGENT_ID
        )
        assert row["available"] is False
    finally:
        controller.close()


def test_kiro_cli_is_recognized_across_the_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serving an Agent row is not the same as being reachable. Three separate
    surfaces resolve a host by identity, and each one silently degraded for Kiro
    CLI: the Endpoint could not bind to a registered Goal agent, the session id
    the adapter documents was never read, and project skills had no delivery
    root. All three are table lookups; a host that owns a built-in Endpoint must
    appear in every table."""
    # A durable Goal agent id is operator-chosen, so the Endpoint must resolve
    # through its host family, exactly as `codex` resolves `codex-main-control`.
    assert ChatActionService._agent_family("kiro-cli") == KIRO_CLI_CHAT_AGENT_ID
    assert ChatActionService._agent_family("kiro-worker-1") == KIRO_CLI_CHAT_AGENT_ID
    assert ChatActionService._agent_family("Kiro_CLI") == KIRO_CLI_CHAT_AGENT_ID
    # Existing families keep their behavior, and an unknown host still resolves
    # to its own id rather than being absorbed into a neighbour.
    assert ChatActionService._agent_family("codex-main-control") == "codex"
    assert ChatActionService._agent_family("claude-impl") == "claude-code"
    assert ChatActionService._agent_family("trae-cli-1") == "trae-cli-1"

    # The adapter records KIRO_SESSION_ID as the stable thread key; reading it is
    # what makes that a binding instead of a note.
    assert HOST_THREAD_ID_ENV[HOST_SURFACE] == KIRO_CLI_SESSION_ID_ENV
    monkeypatch.setenv(KIRO_CLI_SESSION_ID_ENV, "kiro-session-1")
    args = argparse.Namespace(host_surface=HOST_SURFACE, thread_id=None)
    assert current_host_thread_id(args) == "kiro-session-1"
    # An explicit flag still wins, and a host that exports no id stays unbound
    # instead of inheriting another host's variable.
    assert current_host_thread_id(
        argparse.Namespace(host_surface=HOST_SURFACE, thread_id="explicit")
    ) == "explicit"
    assert current_host_thread_id(
        argparse.Namespace(host_surface="agy", thread_id=None)
    ) is None

    # Kiro reads workspace skills from .kiro/skills, so project-level delivery
    # has a real target root.
    assert HOST_SURFACE in PROJECT_SKILL_SURFACES
    assert PROJECT_SKILL_SURFACE_ROOTS[HOST_SURFACE] == Path(".kiro") / "skills"


def test_native_goal_facts_match_the_probed_host() -> None:
    """The host-facts constants are the single source the activation packet,
    README and PR narrative cite; they must stay pinned to what the host
    actually documents and what the probed binary exposes."""
    assert KIRO_CLI_GOAL_COMMAND == "/goal"
    assert KIRO_CLI_GOAL_CLEAR_COMMAND == "/goal clear"
    assert KIRO_CLI_GOAL_STATUS_COMMAND == "/goal status"
    assert KIRO_CLI_GOAL_VALIDATE_FLAG == "--validate"
    assert KIRO_CLI_GOAL_AGENT_FLAG == "--agent"
    assert KIRO_CLI_GOAL_DEFAULT_MAX_ITERATIONS == 5
    assert KIRO_CLI_GOAL_MAX_ITERATION_CEILING == 50
    assert KIRO_CLI_GOAL_COMPLETION_TOOL == "goal"
    assert KIRO_CLI_SESSION_ID_ENV == "KIRO_SESSION_ID"
    assert set(KIRO_CLI_HOOK_TRIGGERS) == {
        "agentSpawn",
        "userPromptSubmit",
        "preToolUse",
        "postToolUse",
        "stop",
    }
    facts = " ".join(KIRO_CLI_NATIVE_GOAL_FACTS)
    assert "--max" in facts
    assert "ceiling 50" in facts
    assert "completion contract" in facts
    assert "exit code 2" in facts
    # The host's own hint names --validate and --agent; an adapter that only
    # documents --max understates the primitive it binds.
    assert KIRO_CLI_GOAL_VALIDATE_FLAG in facts
    assert KIRO_CLI_GOAL_AGENT_FLAG in facts
    assert KIRO_CLI_GOAL_STATUS_COMMAND in facts
