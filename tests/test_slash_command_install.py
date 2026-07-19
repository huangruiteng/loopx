from pathlib import Path

from loopx.slash_command_install import install_slash_commands


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
    assert "`codex-ide-plugin` only for the IDE plugin" in skill_text
    assert "Codex IDE plugin or CLI visible `/goal <task_body>`" in skill_text
    assert "use `codex-ide` for the IDE" not in skill_text
    assert "do not return merely after setup, planning, or claim" in skill_text
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
    assert '"opencode-goal-plugin": "0.6.5"' in package_text
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
