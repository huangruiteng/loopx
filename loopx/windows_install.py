from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Sequence

from .file_lock import exclusive_file_lock
from .release_manifest import write_release_manifest
from .skill_install_readback import (
    PACKAGED_HOST_SKILL_IDS,
    write_skill_install_readback,
)
from .slash_command_install import install_slash_commands, materialize_loopx_entry_skill


POINTER_SCHEMA_VERSION = "loopx_windows_release_pointer_v0"
COPY_DIRECTORIES = ("loopx", "scripts", "skills", "docs", "man", "examples", "apps", ".github")
COPY_FILES = ("README.md", "README.zh-CN.md", "CONTRIBUTOR_TASKS.md", "LICENSE", "pyproject.toml")
REQUIRED_DEEP_CHECKS = {
    "command_package_same_root",
    "representative_cli_commands",
    "representative_cli_imports",
    "representative_package_paths",
}


def _resolve_python(requested: str) -> Path:
    result = subprocess.run(
        [requested, "-c", "import sys; print(sys.executable); raise SystemExit(sys.version_info < (3, 11))"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Python 3.11+ is required; selected runtime failed validation: {requested}"
        )
    return Path(result.stdout.strip()).resolve()


def _release_id(requested: str | None, releases_dir: Path) -> str:
    base = requested or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = base
    suffix = 2
    while (releases_dir / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _copy_release(source_root: Path, target: Path) -> None:
    ignored = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "node_modules", ".next", "dist", "build", "coverage"
    )
    for name in COPY_DIRECTORIES:
        source = source_root / name
        if source.exists():
            shutil.copytree(source, target / name, ignore=ignored)
    for name in COPY_FILES:
        source = source_root / name
        if source.exists():
            shutil.copy2(source, target / name)


def _entry_command(release_root: Path, python: Path, args: Sequence[str]) -> list[str]:
    return [str(python), "-I", str(release_root / "scripts" / "loopx_entry.py"), *args]


def _validate_candidate(
    release_root: Path,
    *,
    python: Path,
    skills_dir: Path,
) -> None:
    env = dict(os.environ)
    env["LOOPX_RELEASE_ROOT"] = str(release_root)
    env["CODEX_HOME"] = str(skills_dir.parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    candidate_pointer = release_root / ".candidate-current-release.json"
    _atomic_json(
        candidate_pointer,
        {
            "schema_version": POINTER_SCHEMA_VERSION,
            "release_id": release_root.name,
            "release_root": str(release_root),
            "python": str(python),
        },
    )
    env["LOOPX_COMMAND_PATH"] = str(release_root / "scripts" / "loopx.ps1")
    env["LOOPX_CURRENT_RELEASE_FILE"] = str(candidate_pointer)
    try:
        result = subprocess.run(
            _entry_command(release_root, python, ["--format", "json", "doctor", "--deep"]),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=120,
        )
    finally:
        candidate_pointer.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(
            "release candidate doctor failed: "
            f"stdout={result.stdout[-2000:]!r}, stderr={result.stderr[-2000:]!r}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("release candidate doctor did not return JSON") from exc
    checks = {
        str(item.get("id")): item
        for item in payload.get("checks", [])
        if isinstance(item, dict)
    }
    missing = sorted(REQUIRED_DEEP_CHECKS - checks.keys())
    failed = sorted(
        check_id
        for check_id in REQUIRED_DEEP_CHECKS
        if not checks.get(check_id, {}).get("ok")
    )
    if missing or failed:
        raise RuntimeError(
            f"release candidate validation incomplete: missing={missing}, failed={failed}"
        )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _install_skills(release_root: Path, skills_dir: Path, installed_at: str) -> list[str]:
    skills_dir.mkdir(parents=True, exist_ok=True)
    installed_ids: list[str] = []
    for skill_id in PACKAGED_HOST_SKILL_IDS:
        source = release_root / "skills" / skill_id
        target = skills_dir / skill_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        installed_ids.append(skill_id)
    entry = materialize_loopx_entry_skill(
        skills_dir=skills_dir,
        execute=True,
        cli_bin="loopx",
    )
    if entry.get("status") in {"created", "updated", "unchanged", "upgraded_legacy_managed"}:
        installed_ids.append("loopx")
    install_slash_commands(
        execute=True,
        surfaces=["codex"],
        cli_bin="loopx",
        codex_home=str(skills_dir.parent),
    )
    write_skill_install_readback(
        skills_dir=skills_dir,
        skill_ids=installed_ids,
        source_root=release_root,
        installed_at=installed_at,
    )
    return installed_ids


def install_windows(
    *,
    source_root: Path,
    install_root: Path,
    bin_dir: Path,
    skills_dir: Path,
    python_requested: str,
    install_skills: bool,
    requested_release_id: str | None = None,
) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("the PowerShell 7 installer is supported only on native Windows")
    source_root = source_root.expanduser().resolve()
    install_root = install_root.expanduser().resolve()
    bin_dir = bin_dir.expanduser().resolve()
    skills_dir = skills_dir.expanduser().resolve()
    python = _resolve_python(python_requested)
    releases_dir = install_root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    installed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with exclusive_file_lock(install_root / ".install-guard"):
        release_id = _release_id(requested_release_id, releases_dir)
        release_root = releases_dir / release_id
        temporary = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=releases_dir))
        try:
            _copy_release(source_root, temporary)
            (temporary / ".loopx-python").write_text(str(python) + "\n", encoding="utf-8")
            manifest_env = dict(os.environ)
            manifest_env["LOOPX_PROMOTION_MODE"] = "windows_local_checkout"
            write_release_manifest(
                release_root=temporary,
                release_id=release_id,
                source_root=source_root,
                installed_at=installed_at,
                env=manifest_env,
            )
            _validate_candidate(temporary, python=python, skills_dir=skills_dir)
            os.replace(temporary, release_root)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        installed_skill_ids = (
            _install_skills(release_root, skills_dir, installed_at) if install_skills else []
        )
        launcher = bin_dir / "loopx.ps1"
        _atomic_copy(release_root / "scripts" / "loopx.ps1", launcher)
        pointer = install_root / "current-release.json"
        _atomic_json(
            pointer,
            {
                "schema_version": POINTER_SCHEMA_VERSION,
                "release_id": release_id,
                "release_root": str(release_root),
                "python": str(python),
                "installed_at": installed_at,
            },
        )

    return {
        "ok": True,
        "release_id": release_id,
        "release_root": str(release_root),
        "launcher": str(launcher),
        "pointer": str(pointer),
        "skills_dir": str(skills_dir),
        "installed_skill_ids": installed_skill_ids,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install LoopX for native Windows PowerShell 7.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--bin-dir", required=True)
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--python", default="python")
    parser.add_argument("--release-id")
    parser.add_argument("--skip-skills", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = install_windows(
            source_root=Path(args.source_root),
            install_root=Path(args.install_root),
            bin_dir=Path(args.bin_dir),
            skills_dir=Path(args.skills_dir),
            python_requested=args.python,
            install_skills=not args.skip_skills,
            requested_release_id=args.release_id,
        )
    except Exception as exc:
        print(f"loopx Windows installer error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
