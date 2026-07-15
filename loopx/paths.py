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


def registry_project_root(registry_path: Path) -> Path:
    """Return the project root that owns a registry path.

    Project registries conventionally live at ``<project>/.loopx/registry.json``.
    Standalone fixtures and global registries live directly under their owning
    root.  Keeping this rule here prevents relative runtime paths from silently
    depending on the caller's current working directory.
    """

    expanded = registry_path.expanduser().resolve()
    parent = expanded.parent
    return parent.parent if parent.name == ".loopx" else parent


def resolve_runtime_root(
    registry: dict[str, object],
    override: str | None = None,
    *,
    registry_path: Path | None = None,
) -> Path:
    value = override
    if not value:
        value = registry.get("common_runtime_root") if isinstance(registry, dict) else None
    if not value:
        return DEFAULT_RUNTIME_ROOT

    runtime_root = Path(str(value)).expanduser()
    if runtime_root.is_absolute() or registry_path is None:
        return runtime_root
    return registry_project_root(registry_path) / runtime_root


def rel_or_abs(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
