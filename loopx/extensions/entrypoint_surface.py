"""Resolve the Python entrypoints that extension manifests declare.

``load_extension_manifest`` is deliberately import-free: it validates the shape
of every declared reference but never proves the referenced object exists. A
renamed or removed ``python_module``, hook ``factory`` or presentation
``view_validator`` therefore passes manifest validation and only fails when the
extension is activated.

This owner resolves those declarations against the repository source tree so a
removal is visible in the same diff that removes it, without importing provider
code. Resolution is structural: it proves the module file and the top-level
symbol exist, not that the symbol behaves correctly at runtime.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .manifest import load_extension_manifest


ENTRYPOINT_SURFACE_SCHEMA_VERSION = "loopx_extension_entrypoint_surface_v0"


class EntrypointKind(str, Enum):
    """The declaration shapes a manifest uses to name Python code."""

    PYTHON_MODULE = "python_module"
    CONSOLE_SCRIPT = "console_script"
    HOOK_FACTORY = "hook_factory"
    VIEW_VALIDATOR = "view_validator"


class EntrypointStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class DeclaredEntrypoint:
    """One declared reference together with its structural resolution."""

    kind: EntrypointKind
    manifest_path: Path
    location: str
    reference: str
    module: str | None = None
    symbol: str | None = None
    source_path: Path | None = None
    status: EntrypointStatus = EntrypointStatus.UNRESOLVED
    reason: str = ""

    def as_dict(self, repo_root: Path) -> dict[str, Any]:
        def relative(path: Path | None) -> str | None:
            return None if path is None else path.relative_to(repo_root).as_posix()

        return {
            "kind": self.kind.value,
            "manifest": relative(self.manifest_path),
            "location": self.location,
            "reference": self.reference,
            "module": self.module,
            "symbol": self.symbol,
            "source_path": relative(self.source_path),
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass
class EntrypointSurfaceReport:
    repo_root: Path
    manifest_count: int = 0
    entrypoints: list[DeclaredEntrypoint] = field(default_factory=list)
    problems: list[dict[str, str]] = field(default_factory=list)

    @property
    def unresolved(self) -> list[DeclaredEntrypoint]:
        return [item for item in self.entrypoints if item.status is EntrypointStatus.UNRESOLVED]

    @property
    def ok(self) -> bool:
        return not self.unresolved and not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ENTRYPOINT_SURFACE_SCHEMA_VERSION,
            "manifest_count": self.manifest_count,
            "entrypoint_count": len(self.entrypoints),
            "unresolved_count": len(self.unresolved),
            "problem_count": len(self.problems),
            "ok": self.ok,
            "problems": list(self.problems),
            "unresolved": [item.as_dict(self.repo_root) for item in self.unresolved],
        }


def bundled_manifest_paths(repo_root: Path) -> list[Path]:
    """Manifests shipped inside the LoopX wheel, plus co-located packages."""

    roots = (repo_root / "loopx" / "extensions", repo_root / "packages")
    manifest_paths: list[Path] = []
    for root in roots:
        manifest_paths.extend(sorted(root.glob("*/extension.toml")))
    return manifest_paths


def _source_roots(repo_root: Path) -> list[Path]:
    roots = [repo_root]
    packages_root = repo_root / "packages"
    if packages_root.is_dir():
        roots.extend(sorted(path for path in packages_root.glob("*/src") if path.is_dir()))
    return roots


def module_source_path(repo_root: Path, module: str) -> Path | None:
    """Return the repository source file for a dotted module name, if any."""

    parts = module.split(".")
    if not module or any(not part.isidentifier() for part in parts):
        return None
    for root in _source_roots(repo_root):
        base = root.joinpath(*parts)
        module_file = base.with_suffix(".py")
        if module_file.is_file():
            return module_file
        package_file = base / "__init__.py"
        if package_file.is_file():
            return package_file
    return None


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in node.elts:
            names |= _target_names(element)
        return names
    return set()


def _import_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    names: set[str] = set()
    for alias in node.names:
        if alias.asname:
            names.add(alias.asname)
        elif isinstance(node, ast.Import):
            names.add(alias.name.split(".")[0])
        elif alias.name != "*":
            names.add(alias.name)
    return names


def _defined_names(body: Sequence[ast.stmt]) -> set[str]:
    """Top-level names a module body defines, including conditional fallbacks."""

    names: set[str] = set()
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names |= _target_names(target)
        elif isinstance(node, ast.AnnAssign):
            names |= _target_names(node.target)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= _import_names(node)
        elif isinstance(node, ast.If):
            names |= _defined_names(node.body)
            names |= _defined_names(node.orelse)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            names |= _defined_names(node.body)
            for handler in node.handlers:
                names |= _defined_names(handler.body)
            names |= _defined_names(node.orelse)
            names |= _defined_names(node.finalbody)
    return names


def symbol_is_defined(source_path: Path, symbol: str) -> bool:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return symbol in _defined_names(tree.body)


def _split_reference(reference: str) -> tuple[str, str]:
    module, _, symbol = reference.partition(":")
    return module.strip(), symbol.strip()


def _owning_pyproject(repo_root: Path, manifest_path: Path) -> Path:
    relative = manifest_path.relative_to(repo_root)
    if relative.parts[0] == "packages" and len(relative.parts) >= 2:
        return repo_root / relative.parts[0] / relative.parts[1] / "pyproject.toml"
    return repo_root / "pyproject.toml"


def project_scripts(pyproject_path: Path) -> dict[str, str]:
    """Declared ``[project.scripts]`` name -> ``module:callable`` targets."""

    if not pyproject_path.is_file():
        return {}
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, Mapping):
        return {}
    scripts = project.get("scripts")
    if not isinstance(scripts, Mapping):
        return {}
    return {str(name): str(target) for name, target in scripts.items()}


def _declare(
    kind: EntrypointKind,
    manifest_path: Path,
    location: str,
    reference: str,
) -> DeclaredEntrypoint:
    module, symbol = _split_reference(reference) if ":" in reference else (reference, "")
    return DeclaredEntrypoint(
        kind=kind,
        manifest_path=manifest_path,
        location=location,
        reference=reference,
        module=module or None,
        symbol=symbol or None,
    )


def _collect_from_manifest(manifest_path: Path, manifest: Mapping[str, Any]) -> Iterator[DeclaredEntrypoint]:
    runtime = manifest.get("runtime")
    if isinstance(runtime, Mapping):
        python_module = runtime.get("python_module")
        if isinstance(python_module, str) and python_module:
            yield _declare(EntrypointKind.PYTHON_MODULE, manifest_path, "runtime.python_module", python_module)
        entrypoint = runtime.get("entrypoint")
        if isinstance(entrypoint, str) and entrypoint:
            yield _declare(EntrypointKind.CONSOLE_SCRIPT, manifest_path, "runtime.entrypoint", entrypoint)

    for index, adapter in enumerate(manifest.get("hook_adapters") or []):
        if not isinstance(adapter, Mapping):
            continue
        factory = adapter.get("factory")
        if isinstance(factory, str) and factory:
            yield _declare(EntrypointKind.HOOK_FACTORY, manifest_path, f"hook_adapters[{index}].factory", factory)

    for index, surface in enumerate(manifest.get("presentation_surfaces") or []):
        if not isinstance(surface, Mapping):
            continue
        validator = surface.get("view_validator")
        if isinstance(validator, str) and validator:
            yield _declare(
                EntrypointKind.VIEW_VALIDATOR,
                manifest_path,
                f"presentation_surfaces[{index}].view_validator",
                validator,
            )


def _resolve(entrypoint: DeclaredEntrypoint, repo_root: Path) -> DeclaredEntrypoint:
    if entrypoint.kind is EntrypointKind.CONSOLE_SCRIPT:
        pyproject = _owning_pyproject(repo_root, entrypoint.manifest_path)
        scripts = project_scripts(pyproject)
        target = scripts.get(entrypoint.reference)
        if target is None:
            return _unresolved(
                entrypoint,
                f"`{entrypoint.reference}` is not declared in [project.scripts] of "
                f"{pyproject.relative_to(repo_root).as_posix()}",
            )
        module, symbol = _split_reference(target)
        entrypoint = replace(entrypoint, module=module or None, symbol=symbol or None)

    if not entrypoint.module:
        return _unresolved(entrypoint, f"`{entrypoint.reference}` names no module")

    source_path = module_source_path(repo_root, entrypoint.module)
    if source_path is None:
        return _unresolved(entrypoint, f"module `{entrypoint.module}` has no source file in this repository")

    entrypoint = replace(entrypoint, source_path=source_path)

    if entrypoint.kind is EntrypointKind.PYTHON_MODULE:
        return _resolved(entrypoint)

    if not entrypoint.symbol:
        return _unresolved(entrypoint, f"`{entrypoint.reference}` names no callable")
    if not symbol_is_defined(source_path, entrypoint.symbol):
        return _unresolved(
            entrypoint,
            f"`{entrypoint.module}` no longer defines `{entrypoint.symbol}`",
        )
    return _resolved(entrypoint)


def _resolved(entrypoint: DeclaredEntrypoint) -> DeclaredEntrypoint:
    return replace(entrypoint, status=EntrypointStatus.RESOLVED, reason="")


def _unresolved(entrypoint: DeclaredEntrypoint, reason: str) -> DeclaredEntrypoint:
    return replace(entrypoint, status=EntrypointStatus.UNRESOLVED, reason=reason)


def resolve_declared_entrypoints(repo_root: Path) -> EntrypointSurfaceReport:
    """Resolve every bundled and co-located extension entrypoint declaration."""

    repo_root = repo_root.resolve()
    report = EntrypointSurfaceReport(repo_root=repo_root)
    for manifest_path in bundled_manifest_paths(repo_root):
        report.manifest_count += 1
        try:
            manifest = load_extension_manifest(manifest_path)
        except ValueError as error:
            report.problems.append(
                {
                    "manifest": manifest_path.relative_to(repo_root).as_posix(),
                    "reason": str(error),
                }
            )
            continue
        for declared in _collect_from_manifest(manifest_path, manifest):
            report.entrypoints.append(_resolve(declared, repo_root))
    return report


def render_report(report: EntrypointSurfaceReport) -> str:
    lines = [
        f"extension entrypoint surface: {'ok' if report.ok else 'FAILED'}",
        f"- manifests: {report.manifest_count}",
        f"- entrypoints: {len(report.entrypoints)}",
        f"- unresolved: {len(report.unresolved)}",
    ]
    for problem in report.problems:
        lines.append(f"- manifest error: {problem['manifest']}: {problem['reason']}")
    for entrypoint in report.unresolved:
        manifest = entrypoint.manifest_path.relative_to(report.repo_root).as_posix()
        lines.append(
            f"- unresolved {entrypoint.kind.value}: {manifest} {entrypoint.location} "
            f"-> {entrypoint.reference}: {entrypoint.reason}"
        )
    return "\n".join(lines)
