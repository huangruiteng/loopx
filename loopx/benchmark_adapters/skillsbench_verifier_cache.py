from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any


VERIFIER_DEPENDENCY_CACHE_TARGET = "/opt/loopx/skillsbench-verifier-cache"
VERIFIER_DEPENDENCY_CACHE_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_VERIFIER_DEPENDENCY_CACHE"
)
VERIFIER_DEPENDENCY_CACHE_END = (
    "# END LOOPX_SKILLSBENCH_VERIFIER_DEPENDENCY_CACHE"
)
DEFAULT_VERIFIER_DEPENDENCY_CACHE_ROOT = (
    "~/.cache/loopx/benchmarks/skillsbench/verifier-dependencies"
)
VERIFIER_DEPENDENCY_CACHE_ENV = {
    "NPM_CONFIG_CACHE": f"{VERIFIER_DEPENDENCY_CACHE_TARGET}/npm",
    "PIP_CACHE_DIR": f"{VERIFIER_DEPENDENCY_CACHE_TARGET}/pip",
    "PLAYWRIGHT_BROWSERS_PATH": f"{VERIFIER_DEPENDENCY_CACHE_TARGET}/playwright",
    "UV_CACHE_DIR": f"{VERIFIER_DEPENDENCY_CACHE_TARGET}/uv",
    "npm_config_cache": f"{VERIFIER_DEPENDENCY_CACHE_TARGET}/npm",
}


def dependency_cache_enabled(*, sandbox: str, mode: str) -> bool:
    return sandbox == "docker" and mode == "shared"


def prepare_dependency_cache(
    root: str | Path,
    *,
    requested: bool,
    sandbox_user: str,
) -> tuple[Path | None, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "verifier_dependency_cache_requested": requested,
        "verifier_dependency_cache_ready": False,
        "verifier_dependency_cache_mount_injected": False,
        "verifier_dependency_cache_raw_path_recorded": False,
        "verifier_dependency_cache_env_key_count": len(
            VERIFIER_DEPENDENCY_CACHE_ENV
        ),
        "verifier_dependency_cache_solver_write_access": sandbox_user in {"0", "root"},
        "verifier_dependency_cache_scoring_material_cached": False,
    }
    if not requested:
        return None, metadata
    if metadata["verifier_dependency_cache_solver_write_access"]:
        raise ValueError(
            "shared verifier dependency cache requires a non-root sandbox user"
        )

    cache_root = Path(root).expanduser().resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_root.chmod(0o755)
    for path in VERIFIER_DEPENDENCY_CACHE_ENV.values():
        relative = Path(path).relative_to(VERIFIER_DEPENDENCY_CACHE_TARGET)
        target = cache_root / relative
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o755)
    metadata["verifier_dependency_cache_ready"] = True
    return cache_root, metadata


def dependency_cache_mount(root: Path | None) -> list[dict[str, Any]]:
    if root is None:
        return []
    return [
        {
            "type": "bind",
            "source": str(root),
            "target": VERIFIER_DEPENDENCY_CACHE_TARGET,
            "read_only": False,
        }
    ]


def _strip_marker_block(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == VERIFIER_DEPENDENCY_CACHE_BEGIN:
            skipping = True
            continue
        if line.strip() == VERIFIER_DEPENDENCY_CACHE_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def patch_verifier_dependency_cache_env(
    verifier: Path,
    *,
    enabled: bool,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "verifier_dependency_cache_required": bool(enabled and verifier.is_file()),
        "verifier_dependency_cache_env_patch_applied": False,
        "verifier_dependency_cache_env_key_count": (
            len(VERIFIER_DEPENDENCY_CACHE_ENV) if enabled else 0
        ),
        "verifier_dependency_cache_raw_path_recorded": False,
    }
    if not metadata["verifier_dependency_cache_required"]:
        return metadata

    original = verifier.read_text(encoding="utf-8", errors="replace")
    original_mode = stat.S_IMODE(verifier.stat().st_mode)
    text = _strip_marker_block(original)
    block_lines = [
        VERIFIER_DEPENDENCY_CACHE_BEGIN,
        "# Reuse package-manager artifacts; official verifier outputs are not cached.",
    ]
    for key, value in sorted(VERIFIER_DEPENDENCY_CACHE_ENV.items()):
        block_lines.append(f"export {key}={value}")
    unique_paths = sorted(set(VERIFIER_DEPENDENCY_CACHE_ENV.values()))
    block_lines.append("mkdir -p " + " ".join(unique_paths))
    block_lines.append(VERIFIER_DEPENDENCY_CACHE_END)

    lines = text.splitlines()
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    patched_lines = [*lines[:insert_at], *block_lines, *lines[insert_at:]]
    patched = "\n".join(patched_lines).rstrip() + "\n"
    temporary = verifier.with_name(f".{verifier.name}.loopx-cache.tmp")
    try:
        temporary.write_text(patched, encoding="utf-8")
        temporary.chmod(original_mode)
        os.replace(temporary, verifier)
    finally:
        temporary.unlink(missing_ok=True)
    metadata["verifier_dependency_cache_env_patch_applied"] = True
    return metadata
