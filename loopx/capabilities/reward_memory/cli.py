from __future__ import annotations

import argparse
from collections.abc import Callable

from .architecture import (
    build_reward_memory_architecture_packet,
    build_reward_memory_route_packet,
    pr_3237_regression_observation,
)


def _render(payload: dict[str, object]) -> str:
    lines = ["# Reward Memory", ""]
    for key in ("status", "decision", "case_ref"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    classes = payload.get("memory_classes")
    if isinstance(classes, list):
        lines.append(f"- memory_classes: `{len(classes)}`")
    reasons = payload.get("reason_codes")
    if isinstance(reasons, list):
        lines.append("- reason_codes: `" + ", ".join(map(str, reasons)) + "`")
    return "\n".join(lines) + "\n"


def register_reward_memory_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "reward-memory",
        help="Inspect reward-memory classes and pilot/meta routing boundaries.",
    )
    sub = parser.add_subparsers(dest="reward_memory_command", required=True)
    architecture = sub.add_parser(
        "architecture",
        help="Render the provider-neutral Stage-0 architecture contract.",
    )
    add_subcommand_format(architecture)

    route = sub.add_parser(
        "route-check",
        help="Route a compact issue-fix observation to pilot, meta, or evidence hold.",
    )
    add_subcommand_format(route)
    route.add_argument(
        "--case",
        choices=["pr-3237"],
        help="Use a built-in public regression observation.",
    )
    route.add_argument(
        "--behavior-status",
        choices=["bug_confirmed", "by_design", "uncertain"],
        default="bug_confirmed",
    )
    route.add_argument("--surface-count", type=int, default=1)
    route.add_argument("--semantic-contract-change", action="store_true")
    route.add_argument("--generic-boundary-for-specific-policy", action="store_true")
    route.add_argument("--user-visible-behavior-change", action="store_true")
    route.add_argument("--hot-path-or-storage-change", action="store_true")
    route.add_argument("--retrieval-or-memory-quality-claim", action="store_true")
    route.add_argument(
        "--edge-case-complexity",
        choices=["low", "medium", "high"],
        default="low",
    )
    route.add_argument("--named-reproduction", action="store_true")
    route.add_argument("--named-validation", action="store_true")
    route.add_argument("--effect-evidence", action="store_true")
    route.add_argument("--ux-evidence", action="store_true")
    route.add_argument("--benchmark-evidence", action="store_true")
    route.add_argument("--performance-evidence", action="store_true")


def handle_reward_memory_command(
    args: argparse.Namespace,
    *,
    output_format: Callable[..., str],
    print_payload: Callable[[dict[str, object], str, Callable], None],
) -> int | None:
    if args.command != "reward-memory":
        return None
    try:
        if args.reward_memory_command == "architecture":
            payload = build_reward_memory_architecture_packet()
        else:
            observation = (
                pr_3237_regression_observation()
                if args.case == "pr-3237"
                else {
                    "behavior_status": args.behavior_status,
                    "surface_count": args.surface_count,
                    "semantic_contract_change": args.semantic_contract_change,
                    "generic_boundary_for_specific_policy": (
                        args.generic_boundary_for_specific_policy
                    ),
                    "user_visible_behavior_change": (
                        args.user_visible_behavior_change
                    ),
                    "hot_path_or_storage_change": (
                        args.hot_path_or_storage_change
                    ),
                    "retrieval_or_memory_quality_claim": (
                        args.retrieval_or_memory_quality_claim
                    ),
                    "edge_case_complexity": args.edge_case_complexity,
                    "named_reproduction": args.named_reproduction,
                    "named_validation": args.named_validation,
                    "effect_evidence": args.effect_evidence,
                    "ux_evidence": args.ux_evidence,
                    "benchmark_evidence": args.benchmark_evidence,
                    "performance_evidence": args.performance_evidence,
                }
            )
            payload = build_reward_memory_route_packet(observation)
    except ValueError as exc:
        payload = {
            "ok": False,
            "schema_version": "reward_memory_error_v0",
            "status": "invalid_request",
            "error": str(exc),
        }
        print_payload(payload, output_format(args), _render)
        return 2
    print_payload(payload, output_format(args), _render)
    return 0
