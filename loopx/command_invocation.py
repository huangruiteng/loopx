from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Mapping, Sequence


def resolve_command_path(
    name: str,
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    """Resolve executables plus PowerShell scripts discoverable by PowerShell 7."""

    source_env = os.environ if env is None else env
    explicit = source_env.get("LOOPX_COMMAND_PATH") if name == "loopx" else None
    if os.name == "nt" and explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.is_file():
            return explicit_path
    resolved = shutil.which(name, path=source_env.get("PATH"))
    if resolved:
        return Path(resolved).expanduser()
    if os.name != "nt":
        return None

    candidates: list[Path] = []
    for entry in source_env.get("PATH", "").split(os.pathsep):
        if entry.strip():
            candidates.append(Path(entry).expanduser() / f"{name}.ps1")
    candidates.append((home or Path.home()) / ".local" / "bin" / f"{name}.ps1")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def command_argv(
    command_path: Path,
    args: Sequence[str],
    *,
    pwsh: str | None = None,
) -> list[str]:
    """Build a subprocess argv for native executables or PowerShell scripts."""

    if command_path.suffix.lower() != ".ps1":
        return [str(command_path), *args]
    powershell = pwsh or shutil.which("pwsh")
    if not powershell:
        raise FileNotFoundError("PowerShell 7 executable `pwsh` was not found on PATH")
    return [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-File",
        str(command_path),
        *args,
    ]
