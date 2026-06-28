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


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_canary_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    canary_parser = subparsers.add_parser(
        "canary",
        help="Plan catalog-informed canary profiles without running checks.",
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
    plan_parser.add_argument(
        "--catalog",
        type=Path,
        help="Override the interaction-pattern catalog path.",
    )
    plan_parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed path or glob-like surface. Repeat for multiple paths.",
    )
    plan_parser.add_argument(
        "--surface",
        action="append",
        default=[],
        help="Changed control-plane or product surface. Repeat for multiple surfaces.",
    )
    plan_parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Force-select a catalog family such as 'Work Routing'. Repeat for multiple families.",
    )
    plan_parser.add_argument(
        "--max-checks-per-family",
        type=int,
        default=3,
        help="Maximum candidate checks to include per selected family.",
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
            max_checks_per_family=int(args.max_checks_per_family or 3),
        )
        renderer = render_catalog_canary_plan_markdown
    else:
        raise ValueError("canary requires `profiles` or `plan`")
    print_payload(payload, output_format(args), renderer)
    return 0
