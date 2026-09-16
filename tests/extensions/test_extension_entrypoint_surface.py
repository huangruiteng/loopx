"""Contract tests for manifest-declared extension entrypoints.

The manifest loader validates the *shape* of every declared reference without
importing provider code. These tests pin the complementary contract: a declared
entrypoint must still resolve to a module file and a top-level symbol, so a
rename or removal cannot pass silently.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from loopx.extensions.entrypoint_surface import (
    EntrypointKind,
    EntrypointStatus,
    resolve_declared_entrypoints,
)


ROOT = Path(__file__).resolve().parents[2]

HOOK_ADAPTER_BLOCK = textwrap.dedent(
    """\
    [[hook_adapters]]
    id = "demo-adapter"
    capability_id = "periodic-report"
    target_hook_id = "periodic_report.request"
    phase = "capability_action"
    factory = "demo_provider.hooks:build_adapter"
    required_permissions = []
    ports = ["periodic_report.request.bind_source"]
    """
).strip()

PRESENTATION_BLOCK = textwrap.dedent(
    """\
    [[presentation_surfaces]]
    id = "demo-surface"
    kind = "decision_research_dashboard"
    title = "Demo Surface"
    view_schema = "demo_surface_v0"
    view_validator = "demo_provider.views:validate_demo_view"
    visibility = "public-safe"
    empty_state_title = "No demo view yet"
    empty_state_detail = "Publish a validated demo projection."
    """
).strip()


def _demo_repo(
    tmp_path: Path,
    *,
    runtime_block: str,
    extra_blocks: tuple[str, ...] = (),
    manifest_dir: str = "loopx/extensions/demo",
) -> Path:
    manifest_path = tmp_path / manifest_dir / "extension.toml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_section = f'[runtime]\nprotocol = "demo_extension_v0"\n{runtime_block}'
    sections = "\n\n".join(block for block in (runtime_section, *extra_blocks))
    manifest_path.write_text(
        textwrap.dedent(
            f"""\
            schema_version = "loopx_extension_manifest_v0"
            id = "demo-extension"
            version = "0.1.0"
            requires_loopx_api = ">=1,<2"
            permissions = []

            {sections}
            """
        ),
        encoding="utf-8",
    )
    return tmp_path


def _write_module(root: Path, module: str, body: str) -> Path:
    path = root.joinpath(*module.split(".")).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_repository_extension_entrypoints_all_resolve() -> None:
    report = resolve_declared_entrypoints(ROOT)

    assert report.manifest_count > 0, "expected bundled extension manifests"
    assert report.entrypoints, "expected declared extension entrypoints"
    assert report.problems == []
    assert report.unresolved == [], [item.as_dict(ROOT) for item in report.unresolved]
    assert report.ok is True
    assert {item.kind for item in report.entrypoints} <= set(EntrypointKind)


def test_removed_hook_factory_is_reported(tmp_path: Path) -> None:
    root = _demo_repo(
        tmp_path,
        runtime_block='python_module = "demo_provider.provider"',
        extra_blocks=(HOOK_ADAPTER_BLOCK,),
    )
    _write_module(root, "demo_provider.provider", "def main() -> None:\n    return None\n")
    _write_module(root, "demo_provider.hooks", "def build_adapter() -> None:\n    return None\n")
    assert resolve_declared_entrypoints(root).ok is True

    _write_module(root, "demo_provider.hooks", "def build_adapter_v2() -> None:\n    return None\n")
    report = resolve_declared_entrypoints(root)

    assert report.ok is False
    unresolved = report.unresolved
    assert len(unresolved) == 1, unresolved
    item = unresolved[0]
    assert item.kind is EntrypointKind.HOOK_FACTORY
    assert item.location == "hook_adapters[0].factory"
    assert item.reference == "demo_provider.hooks:build_adapter"
    assert item.status is EntrypointStatus.UNRESOLVED
    assert "no longer defines" in item.reason
    assert report.as_dict()["unresolved"][0]["manifest"] == "loopx/extensions/demo/extension.toml"


def test_removed_view_validator_is_reported(tmp_path: Path) -> None:
    root = _demo_repo(
        tmp_path,
        runtime_block='python_module = "demo_provider.provider"',
        extra_blocks=(PRESENTATION_BLOCK,),
    )
    _write_module(root, "demo_provider.provider", "def main() -> None:\n    return None\n")
    _write_module(root, "demo_provider.views", "def validate_demo_view() -> None:\n    return None\n")
    assert resolve_declared_entrypoints(root).ok is True

    _write_module(root, "demo_provider.views", "def validate_other_view() -> None:\n    return None\n")
    report = resolve_declared_entrypoints(root)

    assert not report.ok
    item = report.unresolved[0]
    assert item.kind is EntrypointKind.VIEW_VALIDATOR
    assert item.location == "presentation_surfaces[0].view_validator"
    assert "demo_provider.views" in item.reason


def test_missing_python_module_is_reported(tmp_path: Path) -> None:
    root = _demo_repo(tmp_path, runtime_block='python_module = "demo_provider.provider"')

    report = resolve_declared_entrypoints(root)

    assert not report.ok
    item = report.unresolved[0]
    assert item.kind is EntrypointKind.PYTHON_MODULE
    assert item.location == "runtime.python_module"
    assert "no source file" in item.reason


def test_conditional_or_reexported_symbol_counts_as_defined(tmp_path: Path) -> None:
    root = _demo_repo(
        tmp_path,
        runtime_block='python_module = "demo_provider.provider"',
        extra_blocks=(HOOK_ADAPTER_BLOCK,),
    )
    _write_module(root, "demo_provider.provider", "def main() -> None:\n    return None\n")
    _write_module(root, "demo_provider.impl", "def build_adapter() -> None:\n    return None\n")
    _write_module(
        root,
        "demo_provider.hooks",
        """\
        import sys

        if sys.version_info >= (3, 0):
            from demo_provider.impl import build_adapter
        else:  # pragma: no cover - legacy interpreter branch
            build_adapter = None
        """,
    )

    assert resolve_declared_entrypoints(root).ok is True


def test_console_script_without_declaration_is_reported(tmp_path: Path) -> None:
    root = _demo_repo(tmp_path, runtime_block='entrypoint = "demo-entrypoint"')

    report = resolve_declared_entrypoints(root)

    assert not report.ok
    item = report.unresolved[0]
    assert item.kind is EntrypointKind.CONSOLE_SCRIPT
    assert item.reference == "demo-entrypoint"
    assert "not declared in [project.scripts]" in item.reason


def test_console_script_target_symbol_is_resolved(tmp_path: Path) -> None:
    root = _demo_repo(tmp_path, runtime_block='entrypoint = "demo-entrypoint"')
    _write_module(root, "demo_provider.cli", "def main() -> None:\n    return None\n")
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "demo"

            [project.scripts]
            demo-entrypoint = "demo_provider.cli:main"
            """
        ),
        encoding="utf-8",
    )
    assert resolve_declared_entrypoints(root).ok is True

    _write_module(root, "demo_provider.cli", "def entry() -> None:\n    return None\n")
    report = resolve_declared_entrypoints(root)

    assert not report.ok
    item = report.unresolved[0]
    assert item.kind is EntrypointKind.CONSOLE_SCRIPT
    assert item.module == "demo_provider.cli"
    assert item.symbol == "main"
    assert "no longer defines" in item.reason


def test_import_error_fallback_counts_as_defined(tmp_path: Path) -> None:
    root = _demo_repo(
        tmp_path,
        runtime_block='python_module = "demo_provider.provider"',
        extra_blocks=(HOOK_ADAPTER_BLOCK,),
    )
    _write_module(root, "demo_provider.provider", "def main() -> None:\n    return None\n")
    _write_module(root, "demo_provider.compat", "def build_adapter() -> None:\n    return None\n")
    _write_module(
        root,
        "demo_provider.hooks",
        """\
        try:
            from demo_provider.fast import build_adapter
        except ImportError:
            from demo_provider.compat import build_adapter
        """,
    )

    assert resolve_declared_entrypoints(root).ok is True


def test_colocated_package_resolves_through_src_and_own_pyproject(tmp_path: Path) -> None:
    root = _demo_repo(
        tmp_path,
        runtime_block='entrypoint = "demo-entrypoint"',
        extra_blocks=(HOOK_ADAPTER_BLOCK,),
        manifest_dir="packages/demo-pkg",
    )
    src = root / "packages" / "demo-pkg" / "src"
    _write_module(src, "demo_provider.cli", "def main() -> None:\n    return None\n")
    _write_module(src, "demo_provider.hooks", "def build_adapter() -> None:\n    return None\n")
    (root / "packages" / "demo-pkg" / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "demo-pkg"

            [project.scripts]
            demo-entrypoint = "demo_provider.cli:main"
            """
        ),
        encoding="utf-8",
    )

    report = resolve_declared_entrypoints(root)

    assert report.problems == []
    assert report.ok is True, [item.as_dict(root) for item in report.unresolved]
    resolved_kinds = {item.kind for item in report.entrypoints}
    assert EntrypointKind.CONSOLE_SCRIPT in resolved_kinds
    assert EntrypointKind.HOOK_FACTORY in resolved_kinds

    _write_module(src, "demo_provider.hooks", "def build_adapter_v2() -> None:\n    return None\n")
    report = resolve_declared_entrypoints(root)

    assert not report.ok
    assert report.unresolved[0].kind is EntrypointKind.HOOK_FACTORY
