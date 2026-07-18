from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from typing import Any


REPRESENTATIVE_CLI_IMPORTS = (
    "loopx.cli",
    "loopx.history",
    "loopx.quota",
    "loopx.status",
)
REPRESENTATIVE_CLI_COMMANDS = (
    ("version", ("--version",)),
    ("commands", ("commands", "--format", "json")),
    ("status_help", ("status", "--help")),
    ("quota_help", ("quota", "--help")),
)
REPRESENTATIVE_PACKAGE_PATHS = (
    "loopx/cli.py",
    "loopx/doctor.py",
    "loopx/history.py",
    "loopx/quota.py",
    "loopx/release_candidate.py",
    "loopx/status.py",
    "loopx/cli_commands/doctor.py",
    "loopx/cli_commands/quota.py",
    "loopx/cli_commands/status.py",
    "scripts/loopx",
    "scripts/install-pi-package.sh",
    "integrations/pi/package.json",
    "integrations/pi/extensions/loopx.ts",
    "integrations/pi/skills/loopx-pi/SKILL.md",
)


def _import_summary() -> dict[str, Any]:
    results: dict[str, str] = {}
    for module_name in REPRESENTATIVE_CLI_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - partial-package errors vary
            results[module_name] = f"{type(exc).__name__}: {exc}"
        else:
            results[module_name] = "ok"
    failed = sorted(name for name, result in results.items() if result != "ok")
    return {
        "ok": not failed,
        "results": results,
        "failed": failed,
    }


def _command_summary(command_path: Path | None) -> dict[str, Any]:
    if command_path is None:
        return {"ok": False, "results": {}, "failed": ["command_missing"]}

    results: dict[str, dict[str, Any]] = {}
    for probe_name, args in REPRESENTATIVE_CLI_COMMANDS:
        try:
            result = subprocess.run(
                [str(command_path), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            results[probe_name] = {
                "ok": False,
                "detail": f"{type(exc).__name__}: {exc}",
            }
            continue
        results[probe_name] = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
        }
    failed = sorted(name for name, result in results.items() if not result.get("ok"))
    return {
        "ok": not failed,
        "results": results,
        "failed": failed,
    }


def _package_path_summary(package_root: Path) -> dict[str, Any]:
    missing = [
        relative
        for relative in REPRESENTATIVE_PACKAGE_PATHS
        if not (package_root / relative).is_file()
    ]
    return {
        "ok": not missing,
        "required": list(REPRESENTATIVE_PACKAGE_PATHS),
        "missing": missing,
    }


def collect_release_candidate_checks(
    *,
    command_path: Path | None,
    package_root: Path,
    invocation_root: Path | None,
) -> dict[str, Any]:
    """Run the slower checks used only before promoting a release candidate."""

    imports = _import_summary()
    commands = _command_summary(command_path)
    package_paths = _package_path_summary(package_root)
    command_package_same_root = bool(
        invocation_root and package_root.resolve() == invocation_root.resolve()
    )
    checks = [
        {
            "id": "command_package_same_root",
            "required": True,
            "ok": command_package_same_root,
            "detail": (
                f"invocation_root={invocation_root}; package_root={package_root}"
            ),
        },
        {
            "id": "representative_cli_imports",
            "required": True,
            "ok": bool(imports.get("ok")),
            "detail": ",".join(imports.get("failed") or []) or "ok",
        },
        {
            "id": "representative_cli_commands",
            "required": True,
            "ok": bool(commands.get("ok")),
            "detail": ",".join(commands.get("failed") or []) or "ok",
        },
        {
            "id": "representative_package_paths",
            "required": True,
            "ok": bool(package_paths.get("ok")),
            "detail": ",".join(package_paths.get("missing") or []) or "ok",
        },
    ]
    return {
        "schema_version": "loopx_release_candidate_checks_v0",
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "representative_cli": {
            "imports": imports,
            "commands": commands,
            "package_paths": package_paths,
        },
    }
