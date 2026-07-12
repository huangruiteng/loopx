from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path


CODEX_EXECUTABLE_RESOLUTION_SCHEMA_VERSION = "visible_codex_executable_resolution_v0"
_VERSION_PATTERN = re.compile(
    r"(?<!\d)(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
)


def _candidate_version(path: Path) -> tuple[str | None, tuple[object, ...] | None]:
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    match = _VERSION_PATTERN.search(output)
    if not match:
        return None, None
    version = match.group(0)
    prerelease = match.group("prerelease")
    prerelease_key = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in (prerelease or "").split(".")
        if part
    )
    key: tuple[object, ...] = (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        1 if prerelease is None else 0,
        prerelease_key,
    )
    return version, key


def _append_candidate(
    candidates: list[dict[str, object]],
    seen: set[str],
    *,
    path: Path,
    source: str,
    public_ref: str,
) -> None:
    expanded = path.expanduser()
    if not expanded.is_file() or not os.access(expanded, os.X_OK):
        return
    identity = str(expanded.resolve())
    if identity in seen:
        return
    seen.add(identity)
    version, version_key = _candidate_version(expanded)
    candidates.append(
        {
            "path": str(expanded.absolute()),
            "source": source,
            "public_ref": public_ref,
            "version": version,
            "version_key": version_key,
        }
    )


def _default_codex_candidates(env: Mapping[str, str]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, directory in enumerate(str(env.get("PATH") or "").split(os.pathsep), start=1):
        if directory:
            _append_candidate(
                candidates,
                seen,
                path=Path(directory) / "codex",
                source="path",
                public_ref=f"PATH candidate #{index}",
            )

    home = Path(env.get("HOME") or str(Path.home()))
    _append_candidate(
        candidates,
        seen,
        path=home / ".npm-global" / "bin" / "codex",
        source="user_npm_global",
        public_ref="~/.npm-global/bin/codex",
    )
    npm_prefix = str(env.get("NPM_CONFIG_PREFIX") or "").strip()
    if npm_prefix:
        _append_candidate(
            candidates,
            seen,
            path=Path(npm_prefix) / "bin" / "codex",
            source="npm_config_prefix",
            public_ref="$NPM_CONFIG_PREFIX/bin/codex",
        )
    npm = shutil.which("npm", path=env.get("PATH"))
    if npm:
        try:
            prefix = subprocess.run(
                [npm, "prefix", "-g"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
                env=dict(env),
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            prefix = ""
        if prefix:
            _append_candidate(
                candidates,
                seen,
                path=Path(prefix) / "bin" / "codex",
                source="npm_global_prefix",
                public_ref="$(npm prefix -g)/bin/codex",
            )

    _append_candidate(
        candidates,
        seen,
        path=Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
        source="chatgpt_app_bundle",
        public_ref="ChatGPT.app bundled codex",
    )
    return candidates


def resolve_codex_executable(
    requested: str,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, dict[str, object]]:
    effective_env = dict(os.environ if env is None else env)
    requested_value = str(requested or "codex").strip() or "codex"
    if requested_value != "codex":
        resolved = shutil.which(requested_value, path=effective_env.get("PATH"))
        if not resolved:
            raise ValueError(f"codex_bin executable not found: {requested_value}")
        path = Path(resolved).absolute()
        version, _version_key = _candidate_version(path)
        return str(path), {
            "schema_version": CODEX_EXECUTABLE_RESOLUTION_SCHEMA_VERSION,
            "requested": "explicit",
            "selection_policy": "explicit_authoritative",
            "selected_source": "explicit_codex_bin",
            "selected_public_ref": "explicit codex_bin",
            "selected_version": version,
            "path_frozen": True,
            "candidate_count": 1,
        }

    candidates = _default_codex_candidates(effective_env)
    if not candidates:
        raise ValueError("codex_bin executable not found in PATH or known host locations")
    versioned = [item for item in candidates if item.get("version_key") is not None]
    selected = (
        max(versioned, key=lambda item: item["version_key"])
        if versioned
        else candidates[0]
    )
    path_default = next(
        (item for item in candidates if item.get("source") == "path"), None
    )
    return str(selected["path"]), {
        "schema_version": CODEX_EXECUTABLE_RESOLUTION_SCHEMA_VERSION,
        "requested": "default_codex",
        "selection_policy": "newest_version_across_host_candidates",
        "selected_source": selected["source"],
        "selected_public_ref": selected["public_ref"],
        "selected_version": selected["version"],
        "path_default_version": path_default.get("version") if path_default else None,
        "path_default_bypassed": bool(
            path_default and selected["path"] != path_default["path"]
        ),
        "path_frozen": True,
        "candidate_count": len(candidates),
        "candidate_versions": [
            {
                "source": item["source"],
                "version": item["version"],
            }
            for item in candidates
        ],
    }


def write_codex_compatibility_shim(*, directory: Path, executable: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    shim = directory / "codex"
    shim.write_text(
        "#!/bin/sh\n" f"exec {shlex.quote(executable)} \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o700)
    return shim
