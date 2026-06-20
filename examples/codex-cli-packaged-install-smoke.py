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
            tar.add(child, arcname=str(Path("goal-harness-main") / child.relative_to(root)))
    else:
        tar.add(path, arcname=str(Path("goal-harness-main") / name))


def main() -> None:
    script = REPO_ROOT / "scripts" / "install-from-github.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        archive = tmp / "goal-harness.tar.gz"
        home = tmp / "home"
        home.mkdir()

        with tarfile.open(archive, "w:gz") as tar:
            for name in (
                "goal_harness",
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
                "GOAL_HARNESS_BIN_DIR": str(home / ".local" / "bin"),
                "GOAL_HARNESS_RELEASES_DIR": str(home / ".local" / "share" / "goal-harness" / "releases"),
                "GOAL_HARNESS_SHELL_PROFILE": str(home / ".profile"),
                "GOAL_HARNESS_ARCHIVE_URL": f"file://{archive}",
                "GOAL_HARNESS_INSTALL_CANARY": "0",
            }
        )
        subprocess.run(["bash", str(script)], check=True, env=env, cwd=tmp)

        installed = home / ".local" / "bin" / "goal-harness"
        assert installed.exists(), installed
        doctor = subprocess.run(
            [str(installed), "doctor"],
            check=True,
            env={**env, "PATH": f"{home / '.local' / 'bin'}:{env.get('PATH', '')}"},
            text=True,
            capture_output=True,
        )
        assert "ok: `True`" in doctor.stdout, doctor.stdout

        for skill in (
            "goal-harness-project",
            "goal-harness-doc-registry",
            "goal-harness-self-repair",
        ):
            assert (home / ".codex" / "skills" / skill / "SKILL.md").exists(), skill

        assert not (home / ".local" / "bin" / "goal-harness-canary").exists()


if __name__ == "__main__":
    main()
