from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

DOCKER_UV_BINARY_CACHE_CONTEXT_DIR = "loopx_uv_cache"
DOCKER_UV_BINARY_CACHE_BEGIN = "# BEGIN LOOPX_SKILLSBENCH_UV_BINARY_CACHE"
DOCKER_UV_BINARY_CACHE_END = "# END LOOPX_SKILLSBENCH_UV_BINARY_CACHE"
UV_BINARY_CACHE_KEYS = (
    "dockerfile_uv_binary_cache_context_created",
    "dockerfile_uv_binary_cache_available",
    "dockerfile_uv_binary_cache_binary_count",
    "dockerfile_uv_binary_cache_has_uv",
    "dockerfile_uv_binary_cache_has_uvx",
    "dockerfile_uv_binary_cache_dockerfile_patch_applied",
    "dockerfile_uv_binary_cache_raw_path_recorded",
)


def empty_uv_binary_cache_metadata() -> dict[str, Any]:
    return {
        "dockerfile_uv_binary_cache_context_created": False,
        "dockerfile_uv_binary_cache_available": False,
        "dockerfile_uv_binary_cache_binary_count": 0,
        "dockerfile_uv_binary_cache_has_uv": False,
        "dockerfile_uv_binary_cache_has_uvx": False,
        "dockerfile_uv_binary_cache_dockerfile_patch_applied": False,
        "dockerfile_uv_binary_cache_raw_path_recorded": False,
    }


def dockerfile_uv_binary_cache_prelude() -> str:
    return (
        f"COPY {DOCKER_UV_BINARY_CACHE_CONTEXT_DIR}/ /opt/loopx_uv_cache/\n"
        "RUN set -eux; \\\n"
        f"    : \"{DOCKER_UV_BINARY_CACHE_BEGIN}\"; \\\n"
        "    if [ -x /opt/loopx_uv_cache/uv ]; then install -m 0755 /opt/loopx_uv_cache/uv /usr/local/bin/uv; fi; \\\n"
        "    if [ -x /opt/loopx_uv_cache/uvx ]; then install -m 0755 /opt/loopx_uv_cache/uvx /usr/local/bin/uvx; fi; \\\n"
        "    if command -v uv >/dev/null 2>&1 && command -v uvx >/dev/null 2>&1 && uv --version >/dev/null 2>&1 && uvx --version >/dev/null 2>&1; then exit 0; fi; \\\n"
        "    rm -f /usr/local/bin/uv /usr/local/bin/uvx; \\\n"
        f"    : \"{DOCKER_UV_BINARY_CACHE_END}\"; \\\n"
    )


def host_uv_binary_cache_candidates() -> dict[str, Path]:
    """Return host uv binaries that are safe to copy into Linux Docker images."""

    if not sys.platform.startswith("linux"):
        return {}
    machine = os.uname().machine.lower()
    if machine not in {"x86_64", "amd64"}:
        return {}
    candidates: dict[str, Path] = {}
    for name in ("uv", "uvx"):
        raw = shutil.which(name)
        if not raw:
            continue
        path = Path(raw)
        if path.is_file() and os.access(path, os.X_OK):
            candidates[name] = path
    return candidates


def stage_uv_binary_cache_context(environment_dir: Path) -> dict[str, Any]:
    """Stage optional host uv/uvx binaries into the Docker build context."""

    cache_dir = environment_dir / DOCKER_UV_BINARY_CACHE_CONTEXT_DIR
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / ".loopx_keep").write_text(
        "Optional LoopX uv binary cache for SkillsBench Docker bootstrap.\n",
        encoding="utf-8",
    )
    copied: list[str] = []
    for name, source in host_uv_binary_cache_candidates().items():
        target = cache_dir / name
        shutil.copy2(source, target)
        target.chmod(0o755)
        copied.append(name)
    return {
        "dockerfile_uv_binary_cache_context_created": True,
        "dockerfile_uv_binary_cache_available": bool(copied),
        "dockerfile_uv_binary_cache_binary_count": len(copied),
        "dockerfile_uv_binary_cache_has_uv": "uv" in copied,
        "dockerfile_uv_binary_cache_has_uvx": "uvx" in copied,
        "dockerfile_uv_binary_cache_raw_path_recorded": False,
    }


def discover_uv_binary_cache_metadata(
    prepared_task: Path,
    dockerfile_text: str,
) -> dict[str, Any]:
    cache_dir = prepared_task / "environment" / DOCKER_UV_BINARY_CACHE_CONTEXT_DIR
    has_uv = (cache_dir / "uv").exists()
    has_uvx = (cache_dir / "uvx").exists()
    return {
        "dockerfile_uv_binary_cache_context_created": cache_dir.exists(),
        "dockerfile_uv_binary_cache_available": has_uv or has_uvx,
        "dockerfile_uv_binary_cache_binary_count": int(has_uv) + int(has_uvx),
        "dockerfile_uv_binary_cache_has_uv": has_uv,
        "dockerfile_uv_binary_cache_has_uvx": has_uvx,
        "dockerfile_uv_binary_cache_dockerfile_patch_applied": (
            DOCKER_UV_BINARY_CACHE_BEGIN in dockerfile_text
        ),
        "dockerfile_uv_binary_cache_raw_path_recorded": False,
    }
