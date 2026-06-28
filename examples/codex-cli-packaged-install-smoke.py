#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def add_tree(tar: tarfile.TarFile, root: Path, name: str) -> None:
    path = root / name
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if ".git" in child.parts or "__pycache__" in child.parts:
                continue
            tar.add(child, arcname=str(Path("loopx-main") / child.relative_to(root)))
    else:
        tar.add(path, arcname=str(Path("loopx-main") / name))


def main() -> None:
    script = REPO_ROOT / "scripts" / "install-from-github.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        archive = tmp / "loopx.tar.gz"
        home = tmp / "home"
        home.mkdir()

        with tarfile.open(archive, "w:gz") as tar:
            for name in (
                "loopx",
                "scripts",
                "skills",
                "docs",
                "examples",
                "README.md",
                "pyproject.toml",
                "LICENSE",
            ):
                add_tree(tar, REPO_ROOT, name)

        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "LOOPX_BIN_DIR": str(home / ".local" / "bin"),
                "LOOPX_RELEASES_DIR": str(home / ".local" / "share" / "loopx" / "releases"),
                "LOOPX_SHELL_PROFILE": str(home / ".profile"),
                "LOOPX_ARCHIVE_URL": f"file://{archive}",
                "LOOPX_INSTALL_CANARY": "0",
            }
        )
        subprocess.run(["bash", str(script)], check=True, env=env, cwd=tmp)

        installed = home / ".local" / "bin" / "loopx"
        assert installed.exists(), installed
        assert not (home / ".local" / "bin" / "goal-harness").exists()
        doctor = subprocess.run(
            [str(installed), "doctor"],
            check=True,
            env={**env, "PATH": f"{home / '.local' / 'bin'}:{env.get('PATH', '')}"},
            text=True,
            capture_output=True,
        )
        assert "ok: `True`" in doctor.stdout, doctor.stdout
        assert "## Install Freshness" in doctor.stdout, doctor.stdout
        assert "install-from-github.sh" in doctor.stdout, doctor.stdout

        for skill in (
            "loopx-project",
            "loopx-pr-review",
            "loopx-doc-registry",
            "loopx-self-repair",
        ):
            assert (home / ".codex" / "skills" / skill / "SKILL.md").exists(), skill

        assert not (home / ".local" / "bin" / "loopx-canary").exists()
        assert not (home / ".local" / "bin" / "goal-harness-canary").exists()


if __name__ == "__main__":
    main()
