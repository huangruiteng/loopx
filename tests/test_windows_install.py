from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from loopx import windows_install
from loopx.doctor import REQUIRED_INSTALLED_SKILL_PHRASES
from loopx.skill_install_readback import PACKAGED_HOST_SKILL_IDS


def _run_loopx(
    *,
    pwsh: str,
    launcher: Path,
    args: list[str],
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [pwsh, "-NoLogo", "-NoProfile", "-File", str(launcher), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )


@pytest.mark.skipif(os.name != "nt", reason="native Windows installer regression")
def test_windows_installer_promotes_release_and_runs_doctor(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is not installed")
    repo_root = Path(__file__).resolve().parents[1]
    install_root = tmp_path / "share" / "loopx"
    bin_dir = tmp_path / "bin"
    skills_dir = tmp_path / "codex" / "skills"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    install = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(repo_root / "scripts" / "install-windows.ps1"),
            "-Python",
            sys.executable,
            "-InstallRoot",
            str(install_root),
            "-BinDir",
            str(bin_dir),
            "-SkillsDir",
            str(skills_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )

    assert install.returncode == 0, install.stderr
    installed = json.loads(install.stdout)
    pointer_path = install_root / "current-release.json"
    assert installed["pointer"] == str(pointer_path)
    assert (bin_dir / "loopx.ps1").is_file()
    launcher_pointer = bin_dir / windows_install.LAUNCHER_POINTER_FILENAME
    assert installed["launcher_pointer"] == str(launcher_pointer)
    assert launcher_pointer.is_file()
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert json.loads(launcher_pointer.read_text(encoding="utf-8")) == pointer
    release_root = Path(pointer["release_root"])
    assert release_root.is_dir()
    expected_skills = {
        "loopx",
        *PACKAGED_HOST_SKILL_IDS,
        "loopx-deepresearch",
        "loopx-global-summary",
        "loopx-global-gates",
        "loopx-global-todos",
        "loopx-global-risks",
        "loop-global-summary",
        "loop-global-gates",
        "loop-global-todos",
        "loop-global-risks",
    }
    assert expected_skills == {
        path.name for path in skills_dir.iterdir() if (path / "SKILL.md").is_file()
    }

    # A real fresh shell does not inherit the installer's pointer override. The
    # launcher must discover the sidecar next to itself, including when the
    # caller selected a non-default InstallRoot.
    launch_env = dict(env)
    launch_env.pop("LOOPX_CURRENT_RELEASE_FILE", None)
    launcher = bin_dir / "loopx.ps1"
    doctor = _run_loopx(
        pwsh=pwsh,
        launcher=launcher,
        args=[
            "--format",
            "json",
            "doctor",
            "--deep",
        ],
        env=launch_env,
    )

    assert doctor.returncode == 0, doctor.stderr
    payload = json.loads(doctor.stdout)
    assert payload["release_candidate"]["ok"] is True
    assert payload["release_provenance"]["default_release"]["root"] == str(release_root)

    project = tmp_path / "project"
    project.mkdir()
    registry = project / ".loopx" / "registry.json"
    runtime = tmp_path / "runtime"
    common = [
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
    ]
    bootstrap = _run_loopx(
        pwsh=pwsh,
        launcher=launcher,
        args=[
            *common,
            "bootstrap",
            "--project",
            str(project),
            "--goal-id",
            "windows-probe",
            "--objective",
            "Verify the native Windows PowerShell lifecycle",
            "--no-onboarding-scan",
            "--no-global-sync",
            "--codex-app-heartbeat",
            "no",
        ],
        env=launch_env,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    todo = _run_loopx(
        pwsh=pwsh,
        launcher=launcher,
        args=[
            *common,
            "todo",
            "add",
            "--goal-id",
            "windows-probe",
            "--role",
            "agent",
            "--text",
            "[P0] Validate Windows PowerShell state writeback",
            "--task-class",
            "advancement_task",
        ],
        env=launch_env,
    )
    assert todo.returncode == 0, todo.stderr
    state_file = project / ".codex" / "goals" / "windows-probe" / "ACTIVE_GOAL_STATE.md"
    assert "[P0] Validate Windows PowerShell state writeback" in state_file.read_text(
        encoding="utf-8"
    )

    quota = _run_loopx(
        pwsh=pwsh,
        launcher=launcher,
        args=[*common, "quota", "should-run", "--goal-id", "windows-probe"],
        env=launch_env,
    )
    assert quota.returncode == 0, quota.stderr
    quota_payload = json.loads(quota.stdout)
    assert quota_payload["should_run"] is True


@pytest.mark.skipif(os.name != "nt", reason="native Windows installer regression")
def test_windows_installer_preserves_externally_managed_skills(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is not installed")
    repo_root = Path(__file__).resolve().parents[1]
    install_root = tmp_path / "share" / "loopx"
    bin_dir = tmp_path / "bin"
    home = tmp_path / "home"
    codex_skills = home / ".codex" / "skills"
    agents_skills = home / ".agents" / "skills"
    for skill_id in REQUIRED_INSTALLED_SKILL_PHRASES:
        shutil.copytree(repo_root / "skills" / skill_id, agents_skills / skill_id)

    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(home / ".codex"),
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    install = subprocess.run(
        [
            pwsh,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(repo_root / "scripts" / "install-windows.ps1"),
            "-Python",
            sys.executable,
            "-InstallRoot",
            str(install_root),
            "-BinDir",
            str(bin_dir),
            "-SkillsDir",
            str(codex_skills),
            "-SkipSkills",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )

    assert install.returncode == 0, install.stderr
    installed = json.loads(install.stdout)
    assert installed["installed_skill_ids"] == []
    assert not codex_skills.exists()

    launch_env = dict(env)
    launch_env["LOOPX_CURRENT_RELEASE_FILE"] = installed["pointer"]
    doctor = _run_loopx(
        pwsh=pwsh,
        launcher=bin_dir / "loopx.ps1",
        args=["--format", "json", "doctor", "--deep"],
        env=launch_env,
    )

    assert doctor.returncode == 0, doctor.stderr
    payload = json.loads(doctor.stdout)
    assert payload["skill_delivery"]["status"] == "ready"
    assert payload["skill_delivery"]["owner"] == "external_skill_manager"
    assert payload["install_freshness"]["externally_managed_skills"] is True
    assert "-SkipSkills" in payload["install_freshness"]["upgrade_command"]
    assert payload["release_candidate"]["ok"] is True
    assert all(
        Path(skill["path"]).is_relative_to(agents_skills)
        for skill in payload["skills"].values()
    )


@pytest.mark.skipif(os.name != "nt", reason="native Windows installer regression")
def test_windows_installer_keeps_pointer_when_candidate_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_root = tmp_path / "share" / "loopx"
    pointer = install_root / "current-release.json"
    pointer.parent.mkdir(parents=True)
    original_pointer = '{"release_id":"known-good"}\n'
    pointer.write_text(original_pointer, encoding="utf-8")

    monkeypatch.setattr(windows_install, "_copy_release", lambda source, target: None)
    monkeypatch.setattr(windows_install, "write_release_manifest", lambda **kwargs: None)

    def reject_candidate(*args: object, **kwargs: object) -> None:
        raise RuntimeError("candidate rejected")

    monkeypatch.setattr(windows_install, "_validate_candidate", reject_candidate)

    with pytest.raises(RuntimeError, match="candidate rejected"):
        windows_install.install_windows(
            source_root=tmp_path / "source",
            install_root=install_root,
            bin_dir=tmp_path / "bin",
            skills_dir=tmp_path / "codex" / "skills",
            python_requested=sys.executable,
            install_skills=False,
            requested_release_id="rejected",
        )

    assert pointer.read_text(encoding="utf-8") == original_pointer
    assert not (install_root / "releases" / "rejected").exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows installer regression")
def test_windows_installer_rolls_back_late_user_surface_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    install_root = tmp_path / "share" / "loopx"
    bin_dir = tmp_path / "bin"
    skills_dir = tmp_path / "codex" / "skills"
    pointer = install_root / "current-release.json"
    launcher = bin_dir / "loopx.ps1"
    launcher_pointer = bin_dir / windows_install.LAUNCHER_POINTER_FILENAME
    existing_skill = skills_dir / PACKAGED_HOST_SKILL_IDS[0] / "SKILL.md"
    for path, content in (
        (pointer, '{"release_id":"known-good"}\n'),
        (launcher, "# known-good launcher\n"),
        (launcher_pointer, '{"release_id":"known-good"}\n'),
        (existing_skill, "# known-good skill\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def fail_after_skill_write(
        release_root: Path, target_skills_dir: Path, installed_at: str
    ) -> list[str]:
        del release_root, installed_at
        existing_skill_path = target_skills_dir / PACKAGED_HOST_SKILL_IDS[0] / "SKILL.md"
        existing_skill_path.write_text("# partial update\n", encoding="utf-8")
        raise RuntimeError("late skill failure")

    monkeypatch.setattr(windows_install, "_install_skills", fail_after_skill_write)

    with pytest.raises(RuntimeError, match="late skill failure"):
        windows_install.install_windows(
            source_root=repo_root,
            install_root=install_root,
            bin_dir=bin_dir,
            skills_dir=skills_dir,
            python_requested=sys.executable,
            install_skills=True,
            requested_release_id="rejected-late",
        )

    assert pointer.read_text(encoding="utf-8") == '{"release_id":"known-good"}\n'
    assert launcher.read_text(encoding="utf-8") == "# known-good launcher\n"
    assert launcher_pointer.read_text(encoding="utf-8") == (
        '{"release_id":"known-good"}\n'
    )
    assert existing_skill.read_text(encoding="utf-8") == "# known-good skill\n"
    assert not (install_root / "releases" / "rejected-late").exists()
