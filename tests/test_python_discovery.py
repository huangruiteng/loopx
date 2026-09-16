"""Interpreter discovery must not depend on a maintained minor-version list."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX launcher discovery")


def _selector(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    scripts = tmp_path / "project" / "scripts"
    scripts.mkdir(parents=True)
    helper = scripts / "loopx-python.sh"
    shutil.copyfile(Path(__file__).parents[1] / "scripts/loopx-python.sh", helper)
    binaries = tmp_path / "bin with spaces"
    binaries.mkdir()
    env = {**os.environ, "PATH": f"{binaries}:/usr/bin:/bin", "HOME": str(tmp_path)}
    env.pop("LOOPX_PYTHON", None)
    return helper, env, binaries


def _python(path: Path, *, compatible: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"exec {shlex.quote(sys.executable)} \"$@\"" if compatible else "exit 1"
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


def test_discovers_unlisted_minor_and_runs_the_selected_interpreter(tmp_path: Path):
    helper, env, binaries = _selector(tmp_path)
    expected = binaries / "python3.97"
    _python(expected)
    _python(binaries / "python3.98", compatible=False)
    _python(binaries / "python3.999-config")
    result = subprocess.run(["bash", str(helper)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(expected)
    executed = subprocess.run(
        ["bash", str(helper), "--exec", "-c", "print('selected interpreter ran')"],
        env=env, text=True, capture_output=True,
    )
    assert executed.returncode == 0, executed.stderr
    assert executed.stdout.strip() == "selected interpreter ran"


@pytest.mark.parametrize("selection", ["explicit", "recorded", "project_environment"])
def test_declared_or_project_interpreter_precedes_discovery(tmp_path: Path, selection: str):
    helper, env, binaries = _selector(tmp_path)
    project = helper.parent.parent
    chosen = project / ".venv" / "bin" / "python"
    _python(chosen)
    _python(binaries / "python3.97")
    if selection == "explicit":
        env["LOOPX_PYTHON"] = str(chosen)
    elif selection == "recorded":
        (project / ".loopx-python").write_text(str(chosen) + "\n")
    result = subprocess.run(["bash", str(helper)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(chosen)


def test_invalid_explicit_interpreter_does_not_fall_back(tmp_path: Path):
    helper, env, binaries = _selector(tmp_path)
    _python(binaries / "python3.97")
    env["LOOPX_PYTHON"] = str(binaries / "missing-python")
    result = subprocess.run(["bash", str(helper)], env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert not result.stdout.strip()


def test_equal_minor_preserves_path_precedence(tmp_path: Path):
    helper, env, binaries = _selector(tmp_path)
    later = tmp_path / "later-bin"
    _python(binaries / "python3.97")
    _python(later / "python3.97")
    env["PATH"] = f"{binaries}:{later}:/usr/bin:/bin"
    result = subprocess.run(["bash", str(helper)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(binaries / "python3.97")


def test_discovers_unlisted_minor_in_user_install_directory(tmp_path: Path):
    helper, env, binaries = _selector(tmp_path)
    for name in ("dirname", "sort", "uniq"):
        (binaries / name).symlink_to(shutil.which(name))
    _python(binaries / "python3", compatible=False)
    expected = tmp_path / ".local" / "bin" / "python3.97"
    _python(expected)
    env["PATH"] = str(binaries)
    result = subprocess.run(["/bin/bash", str(helper)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(expected)
