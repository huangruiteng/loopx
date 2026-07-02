from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable
from pathlib import Path

from ..canary.planner import (
    build_catalog_canary_coverage_audit,
    build_catalog_canary_plan,
    build_catalog_canary_profiles,
    render_catalog_canary_coverage_audit_markdown,
    render_catalog_canary_plan_markdown,
    render_catalog_canary_profiles_markdown,
)
from ..canary.runner import (
    build_canary_smoke_suite_run,
    build_catalog_canary_run,
    render_canary_smoke_suite_run_markdown,
    render_catalog_canary_run_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _run_git_name_only(repo_root: Path, args: list[str]) -> dict[str, object]:
    command = ["git", "-C", str(repo_root), *args]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    files = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "changed_files": files,
        "stderr_tail": completed.stderr[-800:],
    }


def collect_git_diff_changed_files(
    *,
    repo_root: Path,
    base_ref: str = "origin/main",
) -> dict[str, object]:
    """Collect committed, staged, unstaged, and untracked paths for canary selection."""

    base_ref = (base_ref or "origin/main").strip() or "origin/main"
    sources = {
        "base": _run_git_name_only(repo_root, ["diff", "--name-only", f"{base_ref}...HEAD"]),
        "staged": _run_git_name_only(repo_root, ["diff", "--name-only", "--cached"]),
        "unstaged": _run_git_name_only(repo_root, ["diff", "--name-only"]),
        "untracked": _run_git_name_only(repo_root, ["ls-files", "--others", "--exclude-standard"]),
    }
    changed_files = _dedupe_preserving_order(
        [
            file
            for source in sources.values()
            for file in (source.get("changed_files") or [])
            if isinstance(file, str)
        ]
    )
    successful_sources = [
        name for name, source in sources.items()
        if source.get("ok")
    ]
    warnings = [
        {
            "source": name,
            "returncode": source.get("returncode"),
            "stderr_tail": source.get("stderr_tail"),
        }
        for name, source in sources.items()
        if not source.get("ok")
    ]
    return {
        "ok": bool(successful_sources),
        "base_ref": base_ref,
        "repo_root": str(repo_root),
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "successful_sources": successful_sources,
        "warnings": warnings,
    }


def _resolve_canary_changed_files(args: argparse.Namespace) -> tuple[list[str], dict[str, object] | None]:
    changed_files = list(args.changed_file or [])
    git_diff_selector = None
    if bool(getattr(args, "from_git_diff", False)):
        git_diff_selector = collect_git_diff_changed_files(
            repo_root=Path.cwd(),
            base_ref=str(getattr(args, "git_diff_base", "origin/main") or "origin/main"),
        )
        changed_files.extend(
            file
            for file in (git_diff_selector.get("changed_files") or [])
            if isinstance(file, str)
        )
    return _dedupe_preserving_order(changed_files), git_diff_selector


def _attach_selector_sources(
    payload: dict[str, object],
    *,
    git_diff_selector: dict[str, object] | None,
) -> None:
    if git_diff_selector is None:
        return
    payload["selector_sources"] = {"git_diff": git_diff_selector}


def _add_canary_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Override the interaction-pattern catalog path.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed path or glob-like surface. Repeat for multiple paths.",
    )
    parser.add_argument(
        "--from-git-diff",
        action="store_true",
        help=(
            "Append changed paths from git diff against --git-diff-base plus "
            "staged, unstaged, and untracked working-tree changes."
        ),
    )
    parser.add_argument(
        "--git-diff-base",
        default="origin/main",
        help="Base ref for --from-git-diff committed changes. Defaults to origin/main.",
    )
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Changed control-plane or product surface. Repeat for multiple surfaces.",
    )
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Force-select a catalog family such as 'Work Routing'. Repeat for multiple families.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Force-select a current-repo profile such as 'monitor-scheduler'. Repeat for multiple profiles.",
    )
    parser.add_argument(
        "--include-deep-checks",
        action="store_true",
        help="Include deep/browser/integration checks. Defaults stay bounded and fixture-level.",
    )
    parser.add_argument(
        "--max-checks-per-family",
        type=int,
        default=3,
        help="Maximum candidate checks to include per selected family.",
    )
    parser.add_argument(
        "--max-checks-per-profile",
        type=int,
        default=3,
        help="Maximum candidate checks to include per selected current-repo profile.",
    )


def register_canary_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    canary_parser = subparsers.add_parser(
        "canary",
        help="Plan or run catalog-informed canary profiles and smoke suites.",
    )
    canary_sub = canary_parser.add_subparsers(dest="canary_command", required=True)

    profiles_parser = canary_sub.add_parser(
        "profiles",
        help="List canary profiles derived from the interaction-pattern catalog matrix.",
    )
    add_subcommand_format(profiles_parser)
    profiles_parser.add_argument(
        "--catalog",
        type=Path,
        help="Override the interaction-pattern catalog path.",
    )

    plan_parser = canary_sub.add_parser(
        "plan",
        help="Select the smallest useful canary profiles for changed surfaces.",
    )
    add_subcommand_format(plan_parser)
    _add_canary_selector_args(plan_parser)

    run_parser = canary_sub.add_parser(
        "run",
        help="Execute selected fixture-level canary checks from a catalog plan.",
    )
    add_subcommand_format(run_parser)
    _add_canary_selector_args(run_parser)
    run_parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Preview normalized canary commands without running checks.",
    )
    run_parser.add_argument(
        "--check-limit",
        type=int,
        default=3,
        help="Maximum selected checks to execute or preview.",
    )
    run_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-check timeout for executed canaries.",
    )

    smoke_parser = canary_sub.add_parser(
        "smoke-suite",
        help="Run or preview public smoke scripts as a full suite, module subset, or catalog profile.",
    )
    add_subcommand_format(smoke_parser)
    _add_canary_selector_args(smoke_parser)
    smoke_parser.add_argument(
        "--suite",
        choices=["default-public", "full-public", "catalog-plan"],
        default="default-public",
        help=(
            "Smoke selection mode. default-public excludes explicit grouped checks; "
            "full-public includes every tracked examples/*-smoke.py; catalog-plan "
            "runs only checks selected by catalog/profile inputs."
        ),
    )
    smoke_parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Filter suite scripts by module token, such as quota, status, or canary. Repeatable.",
    )
    smoke_parser.add_argument(
        "--script",
        action="append",
        default=[],
        help="Run a specific examples/*-smoke.py script. Repeatable.",
    )
    smoke_parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Preview normalized smoke commands without running checks.",
    )
    smoke_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum selected checks to execute or preview. Defaults to all selected checks.",
    )
    smoke_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-check timeout for executed smoke scripts.",
    )
    smoke_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop execution at the first failed or timed-out smoke.",
    )

    coverage_parser = canary_sub.add_parser(
        "coverage-audit",
        help="Report P0/P1 catalog patterns missing canary profile coverage or explicit exception rationale.",
    )
    add_subcommand_format(coverage_parser)
    coverage_parser.add_argument(
        "--catalog",
        type=Path,
        help="Override the interaction-pattern catalog path.",
    )
    coverage_parser.add_argument(
        "--priority",
        action="append",
        choices=["P0", "P1", "P2"],
        default=[],
        help="Pattern priority to audit. Defaults to P0 and P1; repeat for multiple priorities.",
    )


def handle_canary_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "canary":
        return None
    if args.canary_command == "profiles":
        payload = build_catalog_canary_profiles(catalog_path=args.catalog)
        renderer = render_catalog_canary_profiles_markdown
    elif args.canary_command == "plan":
        changed_files, git_diff_selector = _resolve_canary_changed_files(args)
        payload = build_catalog_canary_plan(
            catalog_path=args.catalog,
            changed_files=changed_files,
            surfaces=list(args.surface or []),
            families=list(args.family or []),
            profiles=list(args.profile or []),
            include_deep_checks=bool(args.include_deep_checks),
            max_checks_per_family=int(args.max_checks_per_family or 3),
            max_checks_per_profile=int(args.max_checks_per_profile or 3),
        )
        _attach_selector_sources(payload, git_diff_selector=git_diff_selector)
        renderer = render_catalog_canary_plan_markdown
    elif args.canary_command == "run":
        changed_files, git_diff_selector = _resolve_canary_changed_files(args)
        payload = build_catalog_canary_run(
            catalog_path=args.catalog,
            changed_files=changed_files,
            surfaces=list(args.surface or []),
            families=list(args.family or []),
            profiles=list(args.profile or []),
            include_deep_checks=bool(args.include_deep_checks),
            max_checks_per_family=int(args.max_checks_per_family or 3),
            max_checks_per_profile=int(args.max_checks_per_profile or 3),
            check_limit=int(args.check_limit or 3),
            execute=not bool(args.no_execute),
            timeout_seconds=float(args.timeout_seconds or 120.0),
        )
        _attach_selector_sources(payload, git_diff_selector=git_diff_selector)
        renderer = render_catalog_canary_run_markdown
    elif args.canary_command == "smoke-suite":
        changed_files, git_diff_selector = _resolve_canary_changed_files(args)
        payload = build_canary_smoke_suite_run(
            suite=str(args.suite or "default-public"),
            modules=list(args.module or []),
            scripts=list(args.script or []),
            catalog_path=args.catalog,
            changed_files=changed_files,
            surfaces=list(args.surface or []),
            families=list(args.family or []),
            profiles=list(args.profile or []),
            include_deep_checks=bool(args.include_deep_checks),
            max_checks_per_family=int(args.max_checks_per_family or 3),
            max_checks_per_profile=int(args.max_checks_per_profile or 3),
            limit=int(args.limit or 0),
            execute=not bool(args.no_execute),
            timeout_seconds=float(args.timeout_seconds or 120.0),
            fail_fast=bool(args.fail_fast),
        )
        _attach_selector_sources(payload, git_diff_selector=git_diff_selector)
        renderer = render_canary_smoke_suite_run_markdown
    elif args.canary_command == "coverage-audit":
        payload = build_catalog_canary_coverage_audit(
            catalog_path=args.catalog,
            priorities=list(args.priority or []) or None,
        )
        renderer = render_catalog_canary_coverage_audit_markdown
    else:
        raise ValueError("canary requires `profiles`, `plan`, `run`, `smoke-suite`, or `coverage-audit`")
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
