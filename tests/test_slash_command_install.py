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


def test_codex_install_retires_managed_loopx_facade(tmp_path: Path) -> None:
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

    assert not skill.exists()
    assert not metadata.exists()
    assert _row(payload, "retired_codex_project_command_facade")["status"] == (
        "retired_managed_file"
    )
    assert _row(payload, "retired_codex_project_command_metadata")["status"] == (
        "retired_managed_file"
    )
    fallback = next(
        item["fallback"]
        for item in payload["installed"]
        if item.get("mechanism") == "unsupported_native_slash_registry"
        and item.get("command") == "/loopx"
    )
    assert "$loopx" not in fallback
    assert "`LoopX` workflow skill in `/skills`" in fallback


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
    assert _row(payload, "retired_codex_project_command_facade")["status"] == (
        "skipped_user_file"
    )
    assert _row(payload, "retired_codex_project_command_metadata")["status"] == (
        "skipped_user_file"
    )
