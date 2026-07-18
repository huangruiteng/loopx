from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "loopx"
CONTROL_PLANE_ROOT = PACKAGE_ROOT / "control_plane"
STATUS_MODULE = PACKAGE_ROOT / "status.py"
QUOTA_MODULE = PACKAGE_ROOT / "quota.py"
LARK_INBOX_CLI_MODULE = PACKAGE_ROOT / "cli_commands" / "lark_inbox.py"
LEGACY_LARK_CAPABILITY_ROOT = PACKAGE_ROOT / "capabilities" / "lark"
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
        "loopx.benchmark_adapters.skillsbench_verifier_bootstrap",
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


def test_quota_operator_inbox_dependency_points_inward() -> None:
    imports = _resolved_imports(QUOTA_MODULE)

    assert "loopx.capabilities.lark.event_inbox" not in imports
    assert "loopx.control_plane.work_items.operator_inbox" in imports


def test_lark_inbox_provider_is_owned_by_the_extension_layer() -> None:
    legacy_provider_modules = {
        "event_collector.py",
        "event_collector_runtime.py",
        "event_inbox.py",
        "inbox_reply.py",
    }
    assert not any(
        (LEGACY_LARK_CAPABILITY_ROOT / name).exists()
        for name in legacy_provider_modules
    )
    legacy_imports = {
        f"loopx.capabilities.lark.{Path(name).stem}"
        for name in legacy_provider_modules
    }
    remaining_legacy_imports = {
        (_module_name(path), dependency)
        for path in PACKAGE_ROOT.rglob("*.py")
        for dependency in _resolved_imports(path)
        if dependency in legacy_imports
    }
    assert not remaining_legacy_imports

    imports = _resolved_imports(LARK_INBOX_CLI_MODULE)
    assert {
        "loopx.extensions.lark.event_collector",
        "loopx.extensions.lark.event_collector_runtime",
        "loopx.extensions.lark.event_inbox",
        "loopx.extensions.lark.inbox_reply",
    } <= imports
