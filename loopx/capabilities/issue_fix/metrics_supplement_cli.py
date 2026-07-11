from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...domain_packs.issue_fix import (
    default_issue_fix_domain_state_ledger_path,
    default_issue_fix_feasibility_ledger_path,
)
from ...history import load_index, load_registry
from ...paths import resolve_runtime_root
from .metrics_supplement import build_issue_fix_metrics_supplement


def register_issue_fix_metrics_supplement_command(
    issue_fix_sub: argparse._SubParsersAction,
    *,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
    add_generated_at_arg: Callable[..., None],
) -> None:
    parser = issue_fix_sub.add_parser(
        "metrics-supplement",
        help=(
            "Compose public-safe supplemental counts from existing issue-fix "
            "domain state and explicit bounded event or memory evidence."
        ),
    )
    add_subcommand_format(parser)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--project", default=".")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--period-start", required=True)
    parser.add_argument("--period-end", required=True)
    parser.add_argument(
        "--event-json",
        default=None,
        help="Optional issue_fix_metrics_event_batch_v0 file, inline object, or stdin.",
    )
    parser.add_argument(
        "--human-intervention-coverage-start",
        default=None,
        help=(
            "Earliest ISO-8601 time from which the compact LoopX run index is "
            "known to cover explicit operator gates and correction rewards. "
            "Without it, observed history is partial and the count remains unavailable."
        ),
    )
    parser.add_argument(
        "--repository-memory-json",
        action="append",
        default=[],
        help=(
            "Optional issue_fix_repository_memory_read_result_v0 file or inline "
            "object. Repeat for multiple issue-scoped reads."
        ),
    )
    add_generated_at_arg(parser, artifact="the metrics supplement")


def build_issue_fix_metrics_supplement_from_args(
    args: argparse.Namespace,
    *,
    registry_path: Path | None,
    runtime_root_arg: str | None,
    generated_at: str,
    load_json_object: Callable[[str], dict[str, Any]],
    load_jsonl_rows: Callable[[Path], list[dict[str, Any]]],
) -> dict[str, Any]:
    stdin_input_count = sum(
        value == "-"
        for value in [args.event_json, *args.repository_memory_json]
        if value is not None
    )
    if stdin_input_count > 1:
        raise ValueError("only one metrics supplement input may read from stdin")

    run_history_rows: list[dict[str, Any]] = []
    if registry_path is not None:
        registry = load_registry(registry_path)
        runtime_root = resolve_runtime_root(registry, runtime_root_arg)
        run_history_rows, _ = load_index(
            runtime_root / "goals" / args.goal_id / "runs" / "index.jsonl"
        )
    project = Path(args.project).expanduser()
    return build_issue_fix_metrics_supplement(
        repo=args.repo,
        period_start=args.period_start,
        period_end=args.period_end,
        feasibility_rows=load_jsonl_rows(
            default_issue_fix_feasibility_ledger_path(
                project=project, goal_id=args.goal_id
            )
        ),
        pr_lifecycle_rows=load_jsonl_rows(
            default_issue_fix_domain_state_ledger_path(
                project=project, goal_id=args.goal_id
            )
        ),
        event_batch=load_json_object(args.event_json) if args.event_json else None,
        run_history_rows=run_history_rows,
        human_intervention_coverage_start=args.human_intervention_coverage_start,
        repository_memory_results=[
            load_json_object(value) for value in args.repository_memory_json
        ],
        generated_at=generated_at,
    )
