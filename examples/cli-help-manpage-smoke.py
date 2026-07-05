#!/usr/bin/env python3
from __future__ import annotations

import gzip
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LONG_TAIL_COMMAND = "codex-cli-visible-first-response-capture-plan"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def assert_concise_default_help(output: str) -> None:
    assert "LoopX keeps long-running agent work moving" in output, output
    assert "Start here:" in output, output
    assert "/loopx <goal text>" in output, output
    assert "Run the loop:" in output, output
    assert "Codex App" in output, output
    assert "Claude Code" in output, output
    assert "loopx commands" in output, output
    assert "evidence-log --goal-id ID --agent-id AGENT --thin" in output, output
    assert "man loopx" in output, output
    assert LONG_TAIL_COMMAND not in output, output
    assert len(output.splitlines()) <= 36, output


def assert_default_help_surface() -> None:
    bare = run_cli()
    assert bare.returncode == 0, (bare.returncode, bare.stdout, bare.stderr)
    assert_concise_default_help(bare.stdout)
    assert bare.stderr == "", bare.stderr

    top_help = run_cli("--help")
    assert top_help.returncode == 0, (top_help.returncode, top_help.stdout, top_help.stderr)
    assert_concise_default_help(top_help.stdout)
    assert top_help.stderr == "", top_help.stderr


def assert_command_reference_surface() -> None:
    result = run_cli("commands")
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "LoopX command reference" in result.stdout, result.stdout
    assert "Daily operator commands" in result.stdout, result.stdout
    assert "required evidence-log reads" in result.stdout, result.stdout
    assert "before replan or handoff" in result.stdout, result.stdout
    assert "Loop driver hints" in result.stdout, result.stdout
    assert "Claude Code /loop" in result.stdout, result.stdout
    assert "Maintainer and adapter commands" in result.stdout, result.stdout
    assert "loopx <command> --help" in result.stdout, result.stdout
    assert "codex-cli-bootstrap-message" in result.stdout, result.stdout
    assert result.stderr == "", result.stderr


def assert_installer_manpage_surface() -> None:
    script = REPO_ROOT / "scripts" / "install-local.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)

    with tempfile.TemporaryDirectory(prefix="loopx-help-manpage-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        home = tmp / "home"
        bin_dir = home / ".local" / "bin"
        man_root = home / ".local" / "share" / "man"
        profile = home / ".zshrc"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "LOOPX_BIN_DIR": str(bin_dir),
            "LOOPX_RELEASES_DIR": str(home / ".local" / "share" / "loopx" / "releases"),
            "LOOPX_SHELL_PROFILE": str(profile),
            "LOOPX_INSTALL_SKILL": "0",
            "LOOPX_INSTALL_CANARY": "0",
            "LOOPX_RELEASE_ID": "help-manpage-smoke-release",
            "PATH": os.environ.get("PATH", ""),
            "SHELL": "/bin/zsh",
        }

        install = subprocess.run(
            [str(script)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        assert f"- manpage: {man_root / 'man1' / 'loopx.1.gz'}" in install.stdout, install.stdout

        installed_help = subprocess.run(
            [str(bin_dir / "loopx")],
            cwd=tmp,
            env=env,
            text=True,
            capture_output=True,
        )
        assert installed_help.returncode == 0, (
            installed_help.returncode,
            installed_help.stdout,
            installed_help.stderr,
        )
        assert_concise_default_help(installed_help.stdout)
        assert installed_help.stderr == "", installed_help.stderr

        manpage = man_root / "man1" / "loopx.1.gz"
        assert manpage.is_file(), manpage
        with gzip.open(manpage, "rt", encoding="utf-8") as handle:
            man_text = handle.read()
        compact_man_text = " ".join(man_text.split())
        assert ".TH LOOPX 1" in man_text, man_text
        assert ".SH LOOP DRIVERS" in man_text, man_text
        assert "Codex App automation" in man_text, man_text
        assert "loopx commands" in man_text, man_text
        assert "loopx evidence-log --goal-id" in man_text, man_text
        assert "before replan or handoff" in compact_man_text, man_text
        assert "loopx COMMAND --help" in man_text, man_text

        profile_text = profile.read_text(encoding="utf-8")
        assert 'export MANPATH="$HOME/.local/share/man:${MANPATH:-}"' in profile_text, profile_text

        man = subprocess.run(
            ["man", "-M", str(man_root), "loopx"],
            cwd=tmp,
            env={**env, "MANPAGER": "cat", "PAGER": "cat"},
            text=True,
            capture_output=True,
        )
        assert man.returncode == 0, (man.returncode, man.stdout, man.stderr)
        assert "LOOPX(1)" in man.stdout, man.stdout
        assert "LoopX keeps long-running agent work moving" in man.stdout, man.stdout
        assert "heartbeat automation" in man.stdout, man.stdout


def main() -> int:
    assert_default_help_surface()
    assert_command_reference_surface()
    assert_installer_manpage_surface()
    print("cli-help-manpage-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
