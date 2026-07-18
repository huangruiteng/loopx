"""AST-backed control-plane debt reporting with reviewed exception lifecycle."""

from __future__ import annotations

import ast
from collections import Counter
from importlib.util import resolve_name
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence


MAINTAINABILITY_REPORT_SCHEMA_VERSION = "control_plane_maintainability_report_v0"
DECISION_STATEMENT_LIMIT = 90
DECISION_POINT_LIMIT = 60

CONTROL_PLANE_FORBIDDEN_DEPENDENCY_PREFIXES = (
    "loopx.benchmark_adapters",
    "loopx.capabilities",
    "loopx.cli",
    "loopx.cli_commands",
    "loopx.presentation",
)
STATUS_FORBIDDEN_DEPENDENCY_PREFIXES = (
    "loopx.benchmark_adapters",
    "loopx.presentation",
)
COMPATIBILITY_FACADE_PATHS = {
    "loopx.quota": "loopx/quota.py",
    "loopx.status": "loopx/status.py",
}


def _exception(reason: str, retirement_plan: str) -> dict[str, str]:
    return {
        "reason": reason,
        "retirement_plan": retirement_plan,
    }


_EXISTING_DECISION_DEBT_REASON = (
    "Existing multi-branch control-plane decision owner predates the ratchet."
)
_OVERSIZED_DECISION_RETIREMENT_PLANS = {
    "loopx.control_plane.agents.agent_scope:_agent_scope_no_candidate_frontier": (
        "Extract the distinct no-candidate frontier policies into ordered rule helpers."
    ),
    "loopx.control_plane.agents.capability_gate:build_capability_gate": (
        "Separate capability matching, fallback selection, and projection rendering."
    ),
    "loopx.control_plane.quota.goal_boundary:goal_boundary": (
        "Split registry boundary resolution from capability and write-scope projection."
    ),
    "loopx.control_plane.quota.heartbeat_recommendation:build_heartbeat_recommendation": (
        "Move recommendation modes into ordered policy rules with one projection assembler."
    ),
    "loopx.control_plane.runtime.benchmark_comparison:benchmark_comparison_decision_note": (
        "Extract comparison evidence rules from decision-note presentation assembly."
    ),
    "loopx.control_plane.runtime.benchmark_experiment_report:compact_benchmark_experiment_report": (
        "Split experiment evidence normalization from compact report projection."
    ),
    "loopx.control_plane.runtime.goal_start_control_score:build_goal_start_product_mode_control_score": (
        "Extract score dimensions into independently testable rule evaluators."
    ),
    "loopx.control_plane.runtime.skillsbench_post_run_debug:build_skillsbench_post_run_debug_gate": (
        "Separate debug evidence classification from the final gate projection."
    ),
    "loopx.control_plane.scheduler.scheduler_hint:build_scheduler_hint.hint": (
        "Promote the nested hint assembler into smaller scheduler policy projections."
    ),
    "loopx.control_plane.todos.contract:parse_todo_metadata_line": (
        "Replace branch-heavy field parsing with the canonical todo field schema."
    ),
    "loopx.control_plane.todos.contract:format_todo_metadata_line": (
        "Replace branch-heavy field formatting with the canonical todo field schema."
    ),
    "loopx.control_plane.turn_driver.executor:run_loopx_turn_once": (
        "Split host execution, receipt validation, and transaction closeout stages."
    ),
    "loopx.status:compact_benchmark_run": (
        "Move benchmark run compaction into bounded runtime read-model modules."
    ),
    "loopx.status:compact_active_user_assisted_pilot": (
        "Move assisted-pilot compaction into a bounded runtime read model."
    ),
    "loopx.quota:build_quota_plan": (
        "Move quota-plan policy selection behind focused control-plane rule helpers."
    ),
    "loopx.quota:build_quota_should_run": (
        "Continue decomposing the public quota facade into bounded decision stages."
    ),
}

REVIEWED_MAINTAINABILITY_EXCEPTIONS: dict[str, dict[str, str]] = {
    "dependency_debt:loopx.status->loopx.benchmark_adapters.skillsbench_verifier_bootstrap": _exception(
        "Status still applies one benchmark bootstrap compatibility projection.",
        "Move the bootstrap attribution into the benchmark runtime projection and delete the edge.",
    ),
    "compatibility_facade:loopx.quota": _exception(
        "The public loopx.quota import surface remains a supported compatibility contract.",
        "Keep internal consumers on canonical modules and shrink exports as callers migrate.",
    ),
    "compatibility_facade:loopx.status": _exception(
        "The public loopx.status import surface remains a supported compatibility contract.",
        "Keep internal consumers on canonical modules and shrink exports as callers migrate.",
    ),
    **{
        f"oversized_decision_function:{symbol}": _exception(
            _EXISTING_DECISION_DEBT_REASON,
            retirement_plan,
        )
        for symbol, retirement_plan in _OVERSIZED_DECISION_RETIREMENT_PLANS.items()
    },
}


def _module_name(path: Path, package_root: Path) -> str:
    relative = path.relative_to(package_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join((package_root.name, *parts))


def _package_name(path: Path, package_root: Path) -> str:
    module_name = _module_name(path, package_root)
    return module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]


def _resolved_module(node: ast.ImportFrom, *, package_name: str) -> str:
    module = node.module or ""
    if not node.level:
        return module
    if not package_name:
        return ""
    return resolve_name("." * node.level + module, package_name)


def resolved_imports(path: Path, *, package_root: Path) -> set[str]:
    package_name = _package_name(path, package_root)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolved_module(node, package_name=package_name)
            if module:
                imports.add(module)
    return imports


def _resolved_from_imports(
    path: Path,
    *,
    package_root: Path,
) -> dict[str, set[str]]:
    package_name = _package_name(path, package_root) if path.is_relative_to(package_root) else ""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolved_module(node, package_name=package_name)
        if not module:
            continue
        imports.setdefault(module, set()).update(alias.name for alias in node.names)
    return imports


def _top_level_package_imports(
    path: Path,
    *,
    package_root: Path,
) -> dict[str, str]:
    package_name = _package_name(path, package_root)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = _resolved_module(node, package_name=package_name)
            if not module.startswith(package_root.name + "."):
                continue
            for alias in node.names:
                imports[alias.asname or alias.name] = module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(package_root.name + "."):
                    imports[alias.asname or alias.name.split(".")[0]] = alias.name
    return imports


def _matches_prefix(value: str, prefixes: Sequence[str]) -> bool:
    return any(value == prefix or value.startswith(prefix + ".") for prefix in prefixes)


def _finding_id(category: str, identity: str) -> str:
    return f"{category}:{identity}"


def tracked_python_paths(repository_root: Path) -> set[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=repository_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return {
        repository_root / relative_path
        for relative_path in completed.stdout.splitlines()
        if relative_path and (repository_root / relative_path).is_file()
    }


def _dependency_finding(
    *,
    source: str,
    target: str,
    path: Path,
    repository_root: Path,
    rule: str,
    imported_name: str | None = None,
) -> dict[str, Any]:
    identity = f"{source}->{target}"
    if imported_name:
        identity += f":{imported_name}"
    return {
        "id": _finding_id("dependency_debt", identity),
        "category": "dependency_debt",
        "rule": rule,
        "path": path.relative_to(repository_root).as_posix(),
        "source": source,
        "target": target,
        **({"imported_name": imported_name} if imported_name else {}),
    }


def collect_dependency_debt(
    repository_root: Path,
    *,
    tracked_paths: set[Path] | None = None,
) -> list[dict[str, Any]]:
    package_root = repository_root / "loopx"
    control_plane_root = package_root / "control_plane"
    findings: list[dict[str, Any]] = []
    control_plane_paths = sorted(control_plane_root.rglob("*.py"))
    if tracked_paths is not None:
        control_plane_paths = [path for path in control_plane_paths if path in tracked_paths]
    for path in control_plane_paths:
        source = _module_name(path, package_root)
        for target in sorted(resolved_imports(path, package_root=package_root)):
            if _matches_prefix(target, CONTROL_PLANE_FORBIDDEN_DEPENDENCY_PREFIXES):
                findings.append(
                    _dependency_finding(
                        source=source,
                        target=target,
                        path=path,
                        repository_root=repository_root,
                        rule="control_plane_outward_dependency",
                    )
                )

    status_path = package_root / "status.py"
    for target in sorted(resolved_imports(status_path, package_root=package_root)):
        if _matches_prefix(target, STATUS_FORBIDDEN_DEPENDENCY_PREFIXES):
            findings.append(
                _dependency_finding(
                    source="loopx.status",
                    target=target,
                    path=status_path,
                    repository_root=repository_root,
                    rule="status_outward_dependency",
                )
            )

    facade_exports = {
        module: set(
            _top_level_package_imports(
                repository_root / relative_path,
                package_root=package_root,
            )
        )
        for module, relative_path in COMPATIBILITY_FACADE_PATHS.items()
    }
    facade_paths = {repository_root / path for path in COMPATIBILITY_FACADE_PATHS.values()}
    internal_paths = [
        path
        for root in (package_root, repository_root / "scripts")
        for path in root.rglob("*.py")
        if path not in facade_paths
        and (tracked_paths is None or path in tracked_paths)
    ]
    for path in sorted(internal_paths):
        source = (
            _module_name(path, package_root)
            if path.is_relative_to(package_root)
            else path.relative_to(repository_root).as_posix()
        )
        for target, imported_names in sorted(
            _resolved_from_imports(path, package_root=package_root).items()
        ):
            if target not in facade_exports:
                continue
            for imported_name in sorted(imported_names & facade_exports[target]):
                findings.append(
                    _dependency_finding(
                        source=source,
                        target=target,
                        path=path,
                        repository_root=repository_root,
                        rule="internal_facade_consumer",
                        imported_name=imported_name,
                    )
                )
    return sorted(findings, key=lambda item: str(item["id"]))


class _FunctionMetrics(ast.NodeVisitor):
    def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.root = root
        self.statement_count = 0
        self.decision_points = 0

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.stmt) and not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            self.statement_count += 1
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            for child in node.body:
                self.visit(child)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            for child in node.body:
                self.visit(child)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_If(self, node: ast.If) -> None:
        self.decision_points += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.decision_points += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.decision_points += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.decision_points += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.decision_points += max(1, len(node.handlers))
        self.generic_visit(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self.decision_points += max(1, len(node.handlers))
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.decision_points += len(node.cases)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.decision_points += max(1, len(node.values) - 1)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.decision_points += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.decision_points += 1 + len(node.ifs)
        self.generic_visit(node)


def _iter_functions(
    body: Sequence[ast.stmt],
    *,
    prefix: str = "",
) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    functions: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified_name = f"{prefix}.{node.name}" if prefix else node.name
            functions.append((qualified_name, node))
            functions.extend(_iter_functions(node.body, prefix=qualified_name))
        elif isinstance(node, ast.ClassDef):
            qualified_name = f"{prefix}.{node.name}" if prefix else node.name
            functions.extend(_iter_functions(node.body, prefix=qualified_name))
    return functions


def collect_oversized_decision_functions(
    repository_root: Path,
    *,
    statement_limit: int = DECISION_STATEMENT_LIMIT,
    decision_point_limit: int = DECISION_POINT_LIMIT,
    tracked_paths: set[Path] | None = None,
) -> list[dict[str, Any]]:
    package_root = repository_root / "loopx"
    paths = [
        *sorted((package_root / "control_plane").rglob("*.py")),
        package_root / "quota.py",
        package_root / "status.py",
    ]
    if tracked_paths is not None:
        paths = [path for path in paths if path in tracked_paths]
    findings: list[dict[str, Any]] = []
    for path in paths:
        module = _module_name(path, package_root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for qualified_name, function in _iter_functions(tree.body):
            metrics = _FunctionMetrics(function)
            metrics.visit(function)
            if (
                metrics.statement_count <= statement_limit
                and metrics.decision_points <= decision_point_limit
            ):
                continue
            identity = f"{module}:{qualified_name}"
            findings.append(
                {
                    "id": _finding_id("oversized_decision_function", identity),
                    "category": "oversized_decision_function",
                    "path": path.relative_to(repository_root).as_posix(),
                    "module": module,
                    "symbol": qualified_name,
                    "line": function.lineno,
                    "metrics": {
                        "statements": metrics.statement_count,
                        "decision_points": metrics.decision_points,
                    },
                    "thresholds": {
                        "max_statements": statement_limit,
                        "max_decision_points": decision_point_limit,
                    },
                }
            )
    return sorted(findings, key=lambda item: str(item["id"]))


def collect_compatibility_facades(repository_root: Path) -> list[dict[str, Any]]:
    package_root = repository_root / "loopx"
    findings: list[dict[str, Any]] = []
    for module, relative_path in sorted(COMPATIBILITY_FACADE_PATHS.items()):
        path = repository_root / relative_path
        imports = _top_level_package_imports(path, package_root=package_root)
        public_exports = sorted(name for name in imports if not name.startswith("_"))
        if not public_exports:
            continue
        findings.append(
            {
                "id": _finding_id("compatibility_facade", module),
                "category": "compatibility_facade",
                "path": relative_path,
                "module": module,
                "metrics": {
                    "package_reexport_count": len(public_exports),
                    "source_module_count": len({imports[name] for name in public_exports}),
                },
                "source_modules": sorted({imports[name] for name in public_exports}),
                "package_reexports": public_exports,
            }
        )
    return findings


def evaluate_maintainability_findings(
    findings: Sequence[Mapping[str, Any]],
    *,
    reviewed_exceptions: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    finding_ids = {str(item.get("id") or "") for item in findings}
    invalid_exceptions = [
        exception_id
        for exception_id, exception in reviewed_exceptions.items()
        if not exception_id
        or not str(exception.get("reason") or "").strip()
        or not str(exception.get("retirement_plan") or "").strip()
    ]
    stale_exception_ids = sorted(set(reviewed_exceptions) - finding_ids)
    evaluated: list[dict[str, Any]] = []
    for finding in findings:
        finding_id = str(finding.get("id") or "")
        exception = reviewed_exceptions.get(finding_id)
        evaluated.append(
            {
                **dict(finding),
                "review_state": "reviewed_exception" if exception else "unreviewed",
                **({"reviewed_exception": dict(exception)} if exception else {}),
            }
        )
    unreviewed = [item for item in evaluated if item["review_state"] == "unreviewed"]
    return {
        "ok": not unreviewed and not stale_exception_ids and not invalid_exceptions,
        "finding_count": len(evaluated),
        "category_counts": dict(
            sorted(Counter(str(item.get("category") or "unknown") for item in evaluated).items())
        ),
        "reviewed_exception_count": len(evaluated) - len(unreviewed),
        "unreviewed_count": len(unreviewed),
        "stale_exception_count": len(stale_exception_ids),
        "invalid_exception_count": len(invalid_exceptions),
        "findings": evaluated,
        "unreviewed_findings": unreviewed,
        "stale_exceptions": [
            {
                "id": exception_id,
                **dict(reviewed_exceptions[exception_id]),
            }
            for exception_id in stale_exception_ids
        ],
        "invalid_exceptions": invalid_exceptions,
    }


def build_control_plane_maintainability_report(
    repository_root: Path,
    *,
    reviewed_exceptions: Mapping[str, Mapping[str, str]] = REVIEWED_MAINTAINABILITY_EXCEPTIONS,
) -> dict[str, Any]:
    tracked_paths = tracked_python_paths(repository_root)
    findings = [
        *collect_dependency_debt(repository_root, tracked_paths=tracked_paths),
        *collect_oversized_decision_functions(
            repository_root,
            tracked_paths=tracked_paths,
        ),
        *collect_compatibility_facades(repository_root),
    ]
    evaluation = evaluate_maintainability_findings(
        sorted(findings, key=lambda item: str(item["id"])),
        reviewed_exceptions=reviewed_exceptions,
    )
    return {
        "schema_version": MAINTAINABILITY_REPORT_SCHEMA_VERSION,
        "repository_root": str(repository_root),
        "policy": {
            "decision_statement_limit": DECISION_STATEMENT_LIMIT,
            "decision_point_limit": DECISION_POINT_LIMIT,
            "exception_contract": (
                "stable finding id plus non-empty reason and retirement_plan; "
                "new debt and stale exceptions fail"
            ),
            "freezes_exact_line_counts": False,
        },
        **evaluation,
    }


def render_control_plane_maintainability_report(payload: Mapping[str, Any]) -> str:
    status = "ok" if payload.get("ok") else "failed"
    category_counts = payload.get("category_counts") or {}
    lines = [
        f"control-plane-maintainability-ratchet: {status}",
        "- debt: "
        + ", ".join(
            f"{category}={count}" for category, count in sorted(category_counts.items())
        ),
        f"- reviewed_exceptions: {payload.get('reviewed_exception_count', 0)}",
        f"- unreviewed: {payload.get('unreviewed_count', 0)}",
        f"- stale_exceptions: {payload.get('stale_exception_count', 0)}",
    ]
    for finding in payload.get("unreviewed_findings") or []:
        lines.append(
            f"- unreviewed finding: {finding.get('id')} path={finding.get('path')}"
        )
    for exception in payload.get("stale_exceptions") or []:
        lines.append(f"- remove stale exception: {exception.get('id')}")
    for exception_id in payload.get("invalid_exceptions") or []:
        lines.append(f"- invalid exception metadata: {exception_id}")
    return "\n".join(lines) + "\n"
