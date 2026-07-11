from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "loopx"
CONTROL_PLANE_ROOT = PACKAGE_ROOT / "control_plane"
STATUS_MODULE = PACKAGE_ROOT / "status.py"
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
STATUS_FORBIDDEN_DEPENDENCY_PREFIXES = (
    "loopx.benchmark_adapters",
    "loopx.presentation",
)
STATUS_OUTWARD_DEPENDENCY_DEBT = {
    (
        "loopx.status",
        "loopx.benchmark_adapters.skillsbench_signals",
    ),
    (
        "loopx.status",
        "loopx.benchmark_adapters.skillsbench_verifier_bootstrap",
    ),
    (
        "loopx.status",
        "loopx.presentation.renderers.status_markdown",
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


def test_status_outward_dependency_debt_only_shrinks() -> None:
    outward_dependencies = {
        (_module_name(STATUS_MODULE), dependency)
        for dependency in _resolved_imports(STATUS_MODULE)
        if any(
            dependency == prefix or dependency.startswith(prefix + ".")
            for prefix in STATUS_FORBIDDEN_DEPENDENCY_PREFIXES
        )
    }

    unexpected = outward_dependencies - STATUS_OUTWARD_DEPENDENCY_DEBT
    stale_debt = STATUS_OUTWARD_DEPENDENCY_DEBT - outward_dependencies
    assert not unexpected, (
        "loopx.status must not gain new benchmark-adapter or presentation dependencies; "
        f"unexpected edges: {sorted(unexpected)}"
    )
    assert not stale_debt, (
        "remove resolved loopx.status edges from STATUS_OUTWARD_DEPENDENCY_DEBT; "
        f"stale entries: {sorted(stale_debt)}"
    )
