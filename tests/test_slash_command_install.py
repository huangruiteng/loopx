import json
from pathlib import Path

import pytest

from loopx import slash_command_install
from loopx.slash_command_install import (
    install_slash_commands,
    materialize_loopx_entry_skill,
)

MANAGED_SKILL = "<!-- loopx-managed-slash-command:v1 command=/loopx surface=codex-skills -->\n"
MANAGED_METADATA = (
    "# <!-- loopx-managed-slash-command:v1 command=/loopx "
    "surface=codex-skill-metadata -->\n"
)


def _row(payload: dict[str, object], mechanism: str) -> dict[str, object]:
    installed = payload["installed"]
    assert isinstance(installed, list)
    return next(item for item in installed if item.get("mechanism") == mechanism)


def _loopx_paths(codex_home: Path) -> tuple[Path, Path]:
    skill = codex_home / "skills" / "loopx" / "SKILL.md"
    return skill, skill.parent / "agents" / "openai.yaml"


def test_host_materialization_installs_generated_loopx_entry_skill(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"

    created = materialize_loopx_entry_skill(
        skills_dir=skills_dir,
        execute=True,
    )

    skill = skills_dir / "loopx" / "SKILL.md"
    skill_text = skill.read_text(encoding="utf-8")
    assert created == {
        "skill_id": "loopx",
        "path": str(skill),
        "status": "created",
    }
    # A plain scalar, not `name: "loopx"`: hosts such as Kiro CLI keep the quote
    # characters verbatim and would expose the skill as `/"loopx"`.
    assert "name: loopx\n" in skill_text
    assert 'name: "loopx"' not in skill_text
    assert "ark-managed-agent" in skill_text
    assert "--slash-command-arguments" in skill_text
    assert "The CLI, not the model, owns parsing" in skill_text
    assert "Never split or recompose" in skill_text
    assert "never infer a route from issue/PR wording or URLs" in skill_text
    assert "verified active LoopX Goal/Agent binding" in skill_text
    assert "Do not call `start-goal` for an ordinary phase" in skill_text
    assert "typed Todo/writeback path for the bound agent" in skill_text
    assert "explicit new-Goal request" in skill_text
    assert "`ordered_steps` and `goal_start_contract` as authoritative" in skill_text
    assert "surface the exact pasteable gate" in skill_text
    assert "follow its exact CLI `interaction_contract` or quota command first" in skill_text
    assert "reuse the packet's verified thread binding" not in skill_text
    assert "capability show <capability-id> --format json" not in skill_text
    assert "Chat/model summaries are not durable state" not in skill_text
    assert materialize_loopx_entry_skill(
        skills_dir=skills_dir,
        execute=True,
    )["status"] == "unchanged"


def test_host_materialization_can_bind_exact_managed_agent_surface(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"

    materialize_loopx_entry_skill(
        skills_dir=skills_dir,
        execute=True,
        host_surface="ark-managed-agent",
    )

    skill_text = (skills_dir / "loopx" / "SKILL.md").read_text(encoding="utf-8")
    assert "exact current host `ark-managed-agent`" in skill_text
    assert "--host-surface ark-managed-agent" in skill_text
    assert "--host-surface <exact-current-host>" not in skill_text
    assert "--slash-command-arguments" in skill_text
    assert "The CLI, not the model, owns parsing" in skill_text
    assert "`ordered_steps` and `goal_start_contract` as authoritative" in skill_text
    assert "never infer a route" in skill_text
    assert "verified active LoopX Goal/Agent binding" in skill_text
    assert "Do not call `start-goal` for an ordinary phase" in skill_text
    assert "follow its exact CLI `interaction_contract` or quota command first" in skill_text
    assert "current Todo evidence and the next executable Todo" not in skill_text
    assert "generic Todos remain scheduling records" not in skill_text


def test_host_materialization_can_bind_dsh_native_surface(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"

    materialize_loopx_entry_skill(
        skills_dir=skills_dir,
        execute=True,
        host_surface="deepseek-harness-native",
    )

    skill_text = (skills_dir / "loopx" / "SKILL.md").read_text(encoding="utf-8")
    assert "exact current host `deepseek-harness-native`" in skill_text
    assert "--host-surface deepseek-harness-native" in skill_text
    assert '--thread-id "$DSH_SESSION_ID"' in skill_text
    assert "complete original visible user task as `goalText`" in skill_text
    assert "--goal-text='<shell-escaped complete original visible user task>'" in skill_text
    assert "no task text becomes shell syntax" in skill_text
    assert "embedded single quote with the exact sequence `'\"'\"'`" in skill_text
    assert "does not substitute a `$ARGUMENTS`" in skill_text
    assert "plugin-provided LoopX model tools" in skill_text
    assert "resolve-agent-thread" in skill_text
    assert "never guess or fuzzy-match a Goal or Agent id" in skill_text
    assert "Visible command arguments: `$ARGUMENTS`." not in skill_text
    assert "On native Windows" not in skill_text
    assert "surface=dsh-skills" in skill_text
    assert "# LoopX CLI Workflow" in skill_text
    assert "DSH workflow skill" in skill_text
    assert 'argument-hint: "[task text]"' in skill_text
    assert "/loopx" not in skill_text


def test_host_materialization_rejects_unknown_fixed_surface(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported fixed LoopX entry host surface"):
        materialize_loopx_entry_skill(
            skills_dir=tmp_path / "skills",
            execute=True,
            host_surface="guessed-host",
        )


def test_codex_install_upgrades_managed_loopx_facade(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex"
    skill, metadata = _loopx_paths(codex_home)
    skill.parent.mkdir(parents=True)
    skill.write_text(MANAGED_SKILL, encoding="utf-8")
    metadata.parent.mkdir(parents=True)
    metadata.write_text(MANAGED_METADATA, encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        surfaces=["codex"],
        codex_home=str(codex_home),
        claude_home=str(tmp_path / "claude"),
    )

    skill_text = skill.read_text(encoding="utf-8")
    assert "Treat this as the LoopX `/loopx` explicit LoopX command skill." in skill_text
    assert "--host-surface <exact-current-host>" in skill_text
    assert "Identify the exact current host surface" in skill_text
    assert "ark-managed-agent" in skill_text
    assert "`ordered_steps` and `goal_start_contract` as authoritative" in skill_text
    assert "use `codex-ide` for the IDE" not in skill_text
    assert "surface the exact pasteable gate" in skill_text
    assert "follow its exact CLI `interaction_contract` or quota command first" in skill_text
    assert "treat `--action-kind` as the documented extensible public-safe token" in skill_text
    assert "do not search the LoopX source for an allowlist" in skill_text
    assert "never pipe it through `head` or `tail`" in skill_text
    assert "never rerun the turn-start call to recover hidden fields" in skill_text
    # A skill facade is installed for every host, so it must not present a
    # Codex-only flag as the universal turn-start mechanism.
    assert "never pipe a `--begin-turn` call" not in skill_text
    assert "passes its own `--turn-instance-id`" in skill_text
    assert "interaction_contract.cli_channel.selection_command" in skill_text
    assert "do not return merely after setup, planning, or claim" not in skill_text
    metadata_text = metadata.read_text(encoding="utf-8")
    assert 'display_name: "LoopX"' in metadata_text
    assert 'display_name: "LoopX /loopx"' not in metadata_text
    assert "allow_implicit_invocation: false" in metadata_text
    assert _row(payload, "codex_explicit_skills")["status"] == "updated"
    assert _row(payload, "codex_skill_openai_metadata")["status"] == "updated"
    fallback = next(
        item["fallback"]
        for item in payload["installed"]
        if item.get("mechanism") == "unsupported_native_slash_registry"
        and item.get("command") == "/loopx"
    )
    assert "$loopx" in fallback


def test_codex_install_preserves_user_owned_loopx_facade(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex"
    skill, metadata = _loopx_paths(codex_home)
    skill.parent.mkdir(parents=True)
    skill.write_text("# user-owned loopx skill\n", encoding="utf-8")
    metadata.parent.mkdir(parents=True)
    metadata.write_text("# user-owned metadata\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        surfaces=["codex"],
        codex_home=str(codex_home),
        claude_home=str(tmp_path / "claude"),
    )

    assert skill.read_text(encoding="utf-8") == "# user-owned loopx skill\n"
    assert metadata.read_text(encoding="utf-8") == "# user-owned metadata\n"
    assert _row(payload, "codex_explicit_skills")["status"] == "skipped_user_file"
    assert _row(payload, "retired_codex_command_metadata")["status"] == "skipped_user_file"


def test_codex_install_retires_managed_metadata_beside_user_owned_skill(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "codex"
    skill, metadata = _loopx_paths(codex_home)
    skill.parent.mkdir(parents=True)
    skill.write_text("# user-owned loopx skill\n", encoding="utf-8")
    metadata.parent.mkdir(parents=True)
    metadata.write_text(MANAGED_METADATA, encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        surfaces=["codex"],
        codex_home=str(codex_home),
        claude_home=str(tmp_path / "claude"),
    )

    assert skill.read_text(encoding="utf-8") == "# user-owned loopx skill\n"
    assert not metadata.exists()
    assert _row(payload, "codex_explicit_skills")["status"] == "skipped_user_file"
    assert _row(payload, "retired_codex_command_metadata")["status"] == (
        "retired_managed_file"
    )


def test_opencode_install_writes_commands_bridge_and_pinned_dependencies(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is True
    command = opencode_home / "commands" / "loopx.md"
    plugin = opencode_home / "plugins" / "loopx-goal.js"
    runtime = opencode_home / "loopx" / "goal-bridge-runtime.mjs"
    package = opencode_home / "package.json"
    assert "--host-surface opencode" in command.read_text(encoding="utf-8")
    assert "createLoopxGoalPlugin" in plugin.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")
    assert "quota" in runtime_text
    assert "terminal_no_followup" in runtime_text
    package_text = package.read_text(encoding="utf-8")
    assert '"opencode-goal-plugin": "0.7.0"' in package_text
    assert '"@opencode-ai/plugin": ">=1.17.15 <2"' in package_text
    assert _row(payload, "opencode_goal_bridge")["status"] == "created"


def test_default_and_all_surfaces_install_only_static_opencode_commands(
    tmp_path: Path,
) -> None:
    for surfaces in (None, ["all"]):
        opencode_home = tmp_path / ("default" if surfaces is None else "all")
        payload = install_slash_commands(
            execute=True,
            surfaces=surfaces,
            codex_home=str(tmp_path / "codex"),
            claude_home=str(tmp_path / "claude"),
            opencode_home=str(opencode_home),
        )

        assert payload["effective_surfaces"] == ["codex", "claude-code", "opencode"]
        assert payload["with_goal_bridge"] is False
        assert (opencode_home / "commands" / "loopx.md").exists()
        assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
        assert not (opencode_home / "loopx" / "goal-bridge-runtime.mjs").exists()
        assert not (opencode_home / "package.json").exists()


def test_claude_install_routes_global_risks_to_focused_cli(tmp_path: Path) -> None:
    claude_home = tmp_path / "claude"
    install_slash_commands(
        execute=True,
        surfaces=["claude-code"],
        claude_home=str(claude_home),
    )

    expected = (
        "Run `loopx global-risks` first and summarize structured stale runs, "
        "boundary warnings, failing checks, and whether a formally evidenced "
        "rollback candidate source is available, without mutating state."
    )
    for name_skill in ("loopx-global-risks", "loop-global-risks"):
        skill = claude_home / "skills" / name_skill / "SKILL.md"
        skill_text = skill.read_text(encoding="utf-8")
        assert expected in skill_text
        assert "This command is read-only" in skill_text
        assert "global-summary" not in skill_text


def test_opencode_static_uninstall_preserves_installed_bridge(tmp_path: Path) -> None:
    opencode_home = tmp_path / "opencode"
    install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    payload = install_slash_commands(
        execute=True,
        uninstall=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is True
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert (opencode_home / "loopx" / "goal-bridge-runtime.mjs").exists()
    assert (opencode_home / "package.json").exists()


def test_opencode_bridge_uninstall_retires_managed_files_and_keeps_package(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    payload = install_slash_commands(
        execute=True,
        uninstall=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is True
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert not (opencode_home / "loopx" / "goal-bridge-runtime.mjs").exists()
    assert (opencode_home / "package.json").exists()
    assert _row(payload, "opencode_goal_dependencies")["status"] == (
        "preserved_shared_dependencies"
    )


def test_opencode_install_fails_closed_for_direct_goal_plugin_registration(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    opencode_home.mkdir()
    (opencode_home / "opencode.jsonc").write_text(
        '{"plugin": ["opencode-goal-plugin"]}\n',
        encoding="utf-8",
    )

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is False
    assert _row(payload, "opencode_goal_bridge")["status"] == (
        "blocked_conflicting_direct_plugin"
    )
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert not (opencode_home / "package.json").exists()


def test_opencode_install_fails_closed_for_tuple_goal_plugin_registration(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    opencode_home.mkdir()
    (opencode_home / "opencode.json").write_text(
        '{"plugin": [["opencode-goal-plugin", {"maxTurns": 20}]]}\n',
        encoding="utf-8",
    )

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is False
    assert _row(payload, "opencode_goal_bridge")["status"] == (
        "blocked_conflicting_direct_plugin"
    )
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert not (opencode_home / "package.json").exists()


@pytest.mark.parametrize(
    "relative_path",
    ["plugins/loopx-goal.js", "loopx/goal-bridge-runtime.mjs"],
)
def test_opencode_bridge_preflight_blocks_user_owned_bridge_without_partial_writes(
    tmp_path: Path,
    relative_path: str,
) -> None:
    opencode_home = tmp_path / "opencode"
    user_file = opencode_home / relative_path
    user_file.parent.mkdir(parents=True)
    user_file.write_text("// user-owned bridge file\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is False
    bridge = _row(payload, "opencode_goal_bridge")
    assert bridge["status"] == "blocked_user_owned_bridge_file"
    assert bridge["conflicts"] == [str(user_file)]
    assert user_file.read_text(encoding="utf-8") == "// user-owned bridge file\n"
    assert not (opencode_home / "commands" / "loopx.md").exists()
    other_bridge = (
        opencode_home / "loopx" / "goal-bridge-runtime.mjs"
        if relative_path == "plugins/loopx-goal.js"
        else opencode_home / "plugins" / "loopx-goal.js"
    )
    assert not other_bridge.exists()
    assert not (opencode_home / "package.json").exists()


def test_opencode_bridge_preflight_blocks_all_writes_for_invalid_config(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    opencode_home.mkdir()
    (opencode_home / "opencode.jsonc").write_text("{ invalid\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is False
    assert _row(payload, "opencode_goal_bridge")["status"] == (
        "blocked_invalid_opencode_config"
    )
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert not (opencode_home / "package.json").exists()


def test_goal_bridge_requires_an_effective_opencode_surface(tmp_path: Path) -> None:
    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["codex"],
        codex_home=str(tmp_path / "codex"),
        opencode_home=str(tmp_path / "opencode"),
    )

    assert payload["ok"] is False
    assert _row(payload, "opencode_goal_bridge")["status"] == (
        "blocked_goal_bridge_requires_opencode_surface"
    )
    assert not (tmp_path / "opencode").exists()


def test_opencode_bridge_preflight_blocks_all_writes_for_invalid_package(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    opencode_home.mkdir()
    package = opencode_home / "package.json"
    package.write_text("[]\n", encoding="utf-8")

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is False
    assert _row(payload, "opencode_goal_dependencies")["status"] == (
        "blocked_invalid_user_package_json"
    )
    assert not (opencode_home / "commands" / "loopx.md").exists()
    assert not (opencode_home / "plugins" / "loopx-goal.js").exists()
    assert package.read_text(encoding="utf-8") == "[]\n"


def test_opencode_install_ignores_commented_jsonc_goal_plugin(
    tmp_path: Path,
) -> None:
    opencode_home = tmp_path / "opencode"
    opencode_home.mkdir()
    (opencode_home / "opencode.jsonc").write_text(
        """{
  // \"plugin\": [\"opencode-goal-plugin\"],
  \"plugin\": [],
}
""",
        encoding="utf-8",
    )

    payload = install_slash_commands(
        execute=True,
        with_goal_bridge=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )

    assert payload["ok"] is True
    assert (opencode_home / "plugins" / "loopx-goal.js").exists()


def test_pi_install_writes_self_contained_extension_into_project(
    tmp_path: Path,
) -> None:
    payload = install_slash_commands(
        execute=True,
        surfaces=["pi"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        pi_project=str(tmp_path),
    )

    assert payload["ok"] is True
    assert payload["effective_surfaces"] == ["pi"]
    extension = tmp_path / ".pi" / "extensions" / "loopx-goal.ts"
    runtime = tmp_path / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs"
    assert payload["summary"]["pi_extension_path"] == str(extension)
    assert payload["summary"]["pi_runtime_path"] == str(runtime)
    assert _row(payload, "pi_goal_extension")["status"] == "created"
    assert _row(payload, "pi_goal_extension_runtime")["status"] == "created"
    text = extension.read_text(encoding="utf-8")
    assert "loopx-managed-slash-command:v1 command=/loopx surface=pi-extension" in text
    assert 'pi.registerCommand("loopx"' in text
    assert "loopx_goal_activate" in text
    assert "agent_settled" in text
    assert 'pi.on("agent_end"' in text
    assert "hasAbortedAssistantMessage" in text
    assert "pi.on(\"session_shutdown\"" in text
    assert "loop.dispose()" in text
    # The quota/wait/store loop core lives in the sibling runtime module so it
    # is directly executable by node:test.
    runtime_text = runtime.read_text(encoding="utf-8")
    assert "surface=pi-extension-runtime" in runtime_text
    assert "quota" in runtime_text
    assert "should-run" in runtime_text
    assert "--runtime-profile" in runtime_text
    assert "terminal_no_followup" in runtime_text
    # The extension is self-contained: no package.json or node_modules needed.
    assert not (tmp_path / ".pi" / "extensions" / "package.json").exists()


def test_pi_install_does_not_touch_default_all_surfaces(tmp_path: Path) -> None:
    payload = install_slash_commands(
        execute=True,
        surfaces=["all"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        pi_project=str(tmp_path),
    )

    assert payload["effective_surfaces"] == ["codex", "claude-code", "opencode"]
    assert payload["summary"]["pi_extension_path"] is None
    assert payload["summary"]["pi_runtime_path"] is None
    assert not (tmp_path / ".pi" / "extensions" / "loopx-goal.ts").exists()
    assert not (tmp_path / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs").exists()


def test_pi_install_blocks_atomically_on_user_owned_extension(tmp_path: Path) -> None:
    extension = tmp_path / ".pi" / "extensions" / "loopx-goal.ts"
    extension.parent.mkdir(parents=True)
    extension.write_text("// user-owned extension\n", encoding="utf-8")
    runtime = tmp_path / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs"

    payload = install_slash_commands(
        execute=True,
        surfaces=["pi"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        pi_project=str(tmp_path),
    )

    # The adapter and its loop runtime are one atomic unit: a user-owned
    # target fails closed with ok=false and zero writes.
    assert payload["ok"] is False
    assert extension.read_text(encoding="utf-8") == "// user-owned extension\n"
    assert not runtime.exists()
    row = _row(payload, "pi_goal_extension")
    assert row["status"] == "blocked_user_owned_pi_file"
    assert str(extension) in row["conflicts"]


def test_pi_install_blocks_atomically_on_user_owned_runtime(tmp_path: Path) -> None:
    runtime = tmp_path / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("// user-owned runtime\n", encoding="utf-8")
    extension = tmp_path / ".pi" / "extensions" / "loopx-goal.ts"

    payload = install_slash_commands(
        execute=True,
        surfaces=["pi"],
        codex_home=str(tmp_path / "codex"),
        claude_home=str(tmp_path / "claude"),
        pi_project=str(tmp_path),
    )

    assert payload["ok"] is False
    assert runtime.read_text(encoding="utf-8") == "// user-owned runtime\n"
    assert not extension.exists()
    row = _row(payload, "pi_goal_extension")
    assert row["status"] == "blocked_user_owned_pi_file"
    assert str(runtime) in row["conflicts"]
    # No partial unit: neither managed file was written.
    assert _row_if_present(payload, "pi_goal_extension_runtime") is None


def _row_if_present(
    payload: dict[str, object], mechanism: str
) -> dict[str, object] | None:
    installed = payload["installed"]
    assert isinstance(installed, list)
    for item in installed:
        if item.get("mechanism") == mechanism:
            return item
    return None


def test_pi_install_retires_managed_extension_on_uninstall(tmp_path: Path) -> None:
    install_slash_commands(
        execute=True,
        surfaces=["pi"],
        pi_project=str(tmp_path),
    )
    extension = tmp_path / ".pi" / "extensions" / "loopx-goal.ts"
    runtime = tmp_path / ".pi" / "extensions" / "pi-goal-loop-runtime.mjs"
    assert extension.exists()
    assert runtime.exists()

    payload = install_slash_commands(
        execute=True,
        uninstall=True,
        surfaces=["pi"],
        pi_project=str(tmp_path),
    )

    assert payload["ok"] is True
    assert not extension.exists()
    assert not runtime.exists()
    assert _row(payload, "pi_goal_extension")["status"] == "retired_managed_file"
    assert _row(payload, "pi_goal_extension_runtime")["status"] == "retired_managed_file"


def test_gemini_surface_writes_skill_files_gemini_cli_can_discover(tmp_path: Path) -> None:
    """Gemini CLI reads user skills from GEMINI_HOME/skills with the same
    SKILL.md front matter as Claude Code, so the facade must land there."""
    gemini_home = tmp_path / "gemini"
    payload = install_slash_commands(
        execute=True,
        surfaces=["gemini"],
        gemini_home=str(gemini_home),
    )
    assert payload["ok"] is True
    assert payload["effective_surfaces"] == ["gemini"]

    skill = gemini_home / "skills" / "loopx" / "SKILL.md"
    assert skill.exists()
    body = skill.read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "name: loopx\n" in body

    row = _row(payload, "gemini_cli_skills")
    assert row["surface"] == "gemini"
    assert row["host_surfaces"] == ["gemini-cli"]


def test_gemini_uninstall_keeps_user_files(tmp_path: Path) -> None:
    """Uninstall removes only what LoopX manages — a skill the user wrote
    under the same name must survive."""
    gemini_home = tmp_path / "gemini"
    install_slash_commands(execute=True, surfaces=["gemini"], gemini_home=str(gemini_home))

    mine = gemini_home / "skills" / "my-own-skill" / "SKILL.md"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text("---\nname: my-own-skill\n---\nhand written\n", encoding="utf-8")

    install_slash_commands(
        execute=True, uninstall=True, surfaces=["gemini"], gemini_home=str(gemini_home)
    )
    assert not (gemini_home / "skills" / "loopx" / "SKILL.md").exists()
    assert mine.exists(), "user-owned skill must not be removed"


def test_cursor_surface_installs_skills(tmp_path: Path) -> None:
    """Cursor discovers SKILL.md from CURSOR_HOME/skills — the same format the
    other hosts use — so the facade lands there too, not only as MCP."""
    cursor_home = tmp_path / "cursor"
    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    skill = cursor_home / "skills" / "loopx" / "SKILL.md"
    assert skill.exists()
    assert "name: loopx\n" in skill.read_text(encoding="utf-8")
    assert _row(payload, "cursor_skills")["host_surfaces"] == ["cursor-agent"]


def test_opencode_surface_installs_skills_next_to_commands(tmp_path: Path) -> None:
    """OpenCode reads global skills from OPENCODE_CONFIG_DIR/skills. The typed
    command facade must stay — the two are different invocation paths."""
    opencode_home = tmp_path / "opencode"
    install_slash_commands(
        execute=True,
        surfaces=["opencode"],
        opencode_home=str(opencode_home),
    )
    assert (opencode_home / "skills" / "loopx" / "SKILL.md").exists()
    assert (opencode_home / "commands" / "loopx.md").exists()


def test_cursor_surface_merges_mcp_and_leaves_other_servers(tmp_path: Path) -> None:
    """The mcp.json usually already holds the user's own servers — we may
    touch nothing but our own key."""
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "somebin", "args": []}}}),
        encoding="utf-8",
    )

    payload = install_slash_commands(
        execute=False, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    row = _row(payload, "cursor_mcp_server")
    assert row["status"] == "would_write"
    # Dry run must not touch the file at all.
    after = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    assert after == {"mcpServers": {"other": {"command": "somebin", "args": []}}}


def test_cursor_surface_reports_unreadable_config_instead_of_overwriting(
    tmp_path: Path,
) -> None:
    """A broken mcp.json is the user's file — overwriting it would silently
    drop their servers, so we report and stop."""
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text("{ this is not json", encoding="utf-8")

    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    row = _row(payload, "cursor_mcp_server")
    assert row["status"] == "blocked_invalid_cursor_mcp_json"
    assert payload["ok"] is False
    assert (cursor_home / "mcp.json").read_text(encoding="utf-8") == "{ this is not json"


def test_gemini_and_cursor_are_opt_in_not_part_of_all(tmp_path: Path) -> None:
    """`all` must not start writing into homes of CLIs the user may not have —
    the two new surfaces are opt-in, the same way `pi` is."""
    payload = install_slash_commands(
        execute=False,
        surfaces=["all"],
        gemini_home=str(tmp_path / "g"),
        cursor_home=str(tmp_path / "c"),
    )
    assert "gemini" not in payload["effective_surfaces"]
    assert "cursor" not in payload["effective_surfaces"]
    assert not (tmp_path / "g").exists()
    assert not (tmp_path / "c").exists()


def _stub_mcp_command(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Pretend `mcp` is provisioned: these tests are about file ownership, not
    about building a venv."""
    entry = {"command": "/opt/loopx/bin/python", "args": ["/opt/loopx/mcp/loopx_mcp.py"]}
    monkeypatch.setattr(
        slash_command_install,
        "_loopx_mcp_command",
        lambda: (str(entry["command"]), str(entry["args"][0])),
    )
    return entry


def test_cursor_mcp_refuses_to_replace_a_user_owned_loopx_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server the user named `loopx` is theirs. LoopX did not write it, cannot
    prove it did, and must not take the name — silently replacing a working
    server is the one failure the user cannot see happening."""
    _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    mine = {
        "mcpServers": {
            "loopx": {"command": "my-own-loopx", "args": ["--mine"]},
            "other": {"command": "somebin", "args": []},
        }
    }
    (cursor_home / "mcp.json").write_text(json.dumps(mine), encoding="utf-8")

    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8")) == mine

    # And uninstall may not delete it either — removing a server we never wrote
    # is the same violation in the other direction.
    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8")) == mine


def test_cursor_mcp_dry_run_reports_the_foreign_entry_before_execute(
    tmp_path: Path,
) -> None:
    """The dry run is where a user finds out; reporting `would_write` here and
    skipping at execute time would make the preview a lie."""
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"loopx": {"command": "my-own-loopx"}}}),
        encoding="utf-8",
    )
    payload = install_slash_commands(
        execute=False, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"


def test_cursor_mcp_fails_closed_on_an_unexpected_servers_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A list-valued `mcpServers` is either a shape LoopX does not understand or
    a damaged file. Normalizing it to `{}` would discard whatever it held."""
    _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    raw = json.dumps({"mcpServers": [{"name": "other"}]})
    (cursor_home / "mcp.json").write_text(raw, encoding="utf-8")

    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "blocked_invalid_cursor_mcp_json"
    assert (cursor_home / "mcp.json").read_text(encoding="utf-8") == raw


def test_cursor_mcp_writes_then_retires_only_its_own_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of the provenance marker: what LoopX wrote, LoopX may
    take back — and nothing else moves."""
    entry = _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    cursor_home.mkdir()
    (cursor_home / "mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "somebin", "args": []}}}),
        encoding="utf-8",
    )

    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "written"
    written = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    assert written["mcpServers"]["loopx"] == entry
    assert written["mcpServers"]["other"] == {"command": "somebin", "args": []}

    # Reinstalling the same entry is not a change.
    payload = install_slash_commands(
        execute=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "unchanged"

    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "retired"
    after = json.loads((cursor_home / "mcp.json").read_text(encoding="utf-8"))
    assert after["mcpServers"] == {"other": {"command": "somebin", "args": []}}
    assert not (cursor_home / slash_command_install.CURSOR_MCP_MARKER_NAME).exists()


def test_cursor_mcp_hand_edited_entry_becomes_the_users(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provenance is the recorded entry, not the key name. Once a user edits the
    entry LoopX wrote, it is theirs and LoopX stops touching it."""
    _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    install_slash_commands(execute=True, surfaces=["cursor"], cursor_home=str(cursor_home))

    config = cursor_home / "mcp.json"
    edited = json.loads(config.read_text(encoding="utf-8"))
    edited["mcpServers"]["loopx"]["args"].append("--my-flag")
    config.write_text(json.dumps(edited), encoding="utf-8")

    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert json.loads(config.read_text(encoding="utf-8")) == edited


# Provenance is a lifecycle, not a single check: what the marker claims has to
# stop being true the moment the entry it describes is gone or changed. The two
# chains below are the ones that bite — a stale marker would let a later
# same-name entry be deleted as if LoopX had written it.
def test_marker_retires_after_user_deletes_the_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    install_slash_commands(execute=True, surfaces=["cursor"], cursor_home=str(cursor_home))
    marker = cursor_home / slash_command_install.CURSOR_MCP_MARKER_NAME
    assert marker.exists()

    # The user removes our server by hand and keeps their own file.
    config = cursor_home / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "somebin"}}}), encoding="utf-8")

    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "absent"
    assert not marker.exists(), "ownership must expire with the entry it described"

    # Later the user writes their own server under the same name — byte for byte
    # what LoopX used to write. Without retiring the marker we would delete it.
    config.write_text(json.dumps({"mcpServers": {"loopx": entry}}), encoding="utf-8")
    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["loopx"] == entry


def test_marker_retires_after_user_edits_the_entry_and_dry_run_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _stub_mcp_command(monkeypatch)
    cursor_home = tmp_path / "cursor"
    install_slash_commands(execute=True, surfaces=["cursor"], cursor_home=str(cursor_home))
    marker = cursor_home / slash_command_install.CURSOR_MCP_MARKER_NAME
    config = cursor_home / "mcp.json"

    edited = json.loads(config.read_text(encoding="utf-8"))
    edited["mcpServers"]["loopx"]["args"].append("--my-flag")
    config.write_text(json.dumps(edited), encoding="utf-8")

    # A dry run reports and touches nothing — including the marker.
    payload = install_slash_commands(
        execute=False, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert marker.exists(), "dry run must stay read-only"

    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert not marker.exists()

    # The user reverts their edit back to the original value. That value is no
    # longer ours to claim — the marker is gone, so the entry stays.
    config.write_text(json.dumps({"mcpServers": {"loopx": entry}}), encoding="utf-8")
    payload = install_slash_commands(
        execute=True, uninstall=True, surfaces=["cursor"], cursor_home=str(cursor_home)
    )
    assert _row(payload, "cursor_mcp_server")["status"] == "skipped_user_owned_mcp_entry"
    assert json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["loopx"] == entry
