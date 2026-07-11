from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "loopx"
CONTROL_PLANE_ROOT = PACKAGE_ROOT / "control_plane"
FORBIDDEN_DEPENDENCY_PREFIXES = (
    "loopx.benchmark_adapters",
    "loopx.capabilities",
    "loopx.cli",
    "loopx.cli_commands",
    "loopx.presentation",
)
ALLOWED_DEPENDENCY_DEBT = {
    (
        "loopx.control_plane.quota.markdown",
        "loopx.presentation.markdown",
    ),
}


def _module_name(path: Path) -> str:
    relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(("loopx", *parts))


def _resolved_imports(path: Path) -> set[str]:
    module_name = _module_name(path)
    package_name = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package_name)
            imports.add(module)
    return imports


def test_control_plane_does_not_gain_outward_dependencies() -> None:
    outward_dependencies = {
        (_module_name(path), dependency)
        for path in CONTROL_PLANE_ROOT.rglob("*.py")
        for dependency in _resolved_imports(path)
        if any(
            dependency == prefix or dependency.startswith(prefix + ".")
            for prefix in FORBIDDEN_DEPENDENCY_PREFIXES
        )
    }

    unexpected = outward_dependencies - ALLOWED_DEPENDENCY_DEBT
    assert not unexpected, (
        "control-plane code must not depend on presentation, CLI, capability, or "
        f"benchmark-adapter layers; unexpected edges: {sorted(unexpected)}"
    )
