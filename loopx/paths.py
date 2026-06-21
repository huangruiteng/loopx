from __future__ import annotations

import os
from pathlib import Path


DEFAULT_RUNTIME_ROOT = Path.home() / ".codex" / "loopx"
DEFAULT_PROJECT_REGISTRY = Path(".loopx") / "registry.json"
GLOBAL_REGISTRY_FILENAME = "registry.global.json"


def default_registry_path() -> Path:
    value = os.environ.get("LOOPX_REGISTRY")
    if value:
        return Path(value).expanduser()
    return DEFAULT_PROJECT_REGISTRY


def global_registry_path(runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> Path:
    return runtime_root / GLOBAL_REGISTRY_FILENAME


def resolve_runtime_root(registry: dict[str, object], override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser()
    value = registry.get("common_runtime_root") if isinstance(registry, dict) else None
    return Path(str(value)).expanduser() if value else DEFAULT_RUNTIME_ROOT


def rel_or_abs(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
