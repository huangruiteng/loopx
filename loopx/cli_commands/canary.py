from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..canary.planner import (
    build_catalog_canary_plan,
    build_catalog_canary_profiles,
    render_catalog_canary_plan_markdown,
    render_catalog_canary_profiles_markdown,
)
from ..canary.runner import (
    build_catalog_canary_run,
    render_catalog_canary_run_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


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
        help="Plan or run catalog-informed canary profiles.",
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
        payload = build_catalog_canary_plan(
            catalog_path=args.catalog,
            changed_files=list(args.changed_file or []),
            surfaces=list(args.surface or []),
            families=list(args.family or []),
            profiles=list(args.profile or []),
            include_deep_checks=bool(args.include_deep_checks),
            max_checks_per_family=int(args.max_checks_per_family or 3),
            max_checks_per_profile=int(args.max_checks_per_profile or 3),
        )
        renderer = render_catalog_canary_plan_markdown
    elif args.canary_command == "run":
        payload = build_catalog_canary_run(
            catalog_path=args.catalog,
            changed_files=list(args.changed_file or []),
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
        renderer = render_catalog_canary_run_markdown
    else:
        raise ValueError("canary requires `profiles`, `plan`, or `run`")
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
