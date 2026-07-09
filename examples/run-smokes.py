#!/usr/bin/env python3
"""Run public smoke scripts through the LoopX canary smoke-suite runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.runner import (  # noqa: E402
    build_canary_smoke_suite_run,
    render_canary_smoke_suite_run_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=["default-public", "full-public", "catalog-plan"],
        default="default-public",
        help=(
            "Smoke selection mode. default-public excludes explicit grouped checks; "
            "full-public includes every tracked examples/**/*-smoke.py."
        ),
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Filter suite scripts by module token, such as quota, status, or canary.",
    )
    parser.add_argument(
        "--exclude-module",
        action="append",
        default=[],
        help="Exclude suite scripts by module token after positive selection.",
    )
    parser.add_argument(
        "--script",
        action="append",
        default=[],
        help="Run a specific examples/**/*-smoke.py script.",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Run a named smoke-suite profile or catalog profile.",
    )
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Run catalog family checks instead of the default full script set.",
    )
    parser.add_argument(
        "--include-deep-checks",
        action="store_true",
        help="Include catalog deep checks when --profile/--family is used.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum selected checks to execute or preview. Defaults to all selected checks.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip this many matched checks before applying --limit.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-check timeout for executed smoke scripts.",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Preview normalized smoke commands without running checks.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop execution at the first failed or timed-out smoke.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help=(
            "Run up to this many smoke scripts concurrently. Defaults to 1. "
            "--fail-fast keeps execution serial."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of markdown.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_canary_smoke_suite_run(
        suite=args.suite,
        modules=list(args.module or []),
        exclude_modules=list(args.exclude_module or []),
        scripts=list(args.script or []),
        families=list(args.family or []),
        profiles=list(args.profile or []),
        include_deep_checks=bool(args.include_deep_checks),
        offset=int(args.offset or 0),
        limit=int(args.limit or 0),
        execute=not bool(args.no_execute),
        timeout_seconds=float(args.timeout_seconds or 120.0),
        fail_fast=bool(args.fail_fast),
        parallel_jobs=int(args.jobs or 1),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_canary_smoke_suite_run_markdown(payload), end="")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
