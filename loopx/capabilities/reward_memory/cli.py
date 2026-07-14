from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .architecture import (
    build_reward_memory_architecture_packet,
    build_reward_memory_route_packet,
    pr_3237_regression_observation,
)
from .candidate_review import (
    issue_fix_verified_contributor_candidate_fixture,
    review_reward_memory_candidate,
)
from .health import (
    build_reward_memory_corpus_health_packet,
    reward_memory_health_case,
)
from .evaluation import run_reward_memory_evaluation
from .dogfood import (
    build_reward_memory_dogfood_batch,
    build_reward_memory_dogfood_receipt,
    build_reward_memory_operator_control,
)
from .registry import build_reward_memory_corpus_registry_packet


def _render(payload: dict[str, object]) -> str:
    lines = ["# Reward Memory", ""]
    for key in (
        "status",
        "decision",
        "effective_decision",
        "health_state",
        "case_ref",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    classes = payload.get("memory_classes")
    if isinstance(classes, list):
        lines.append(f"- memory_classes: `{len(classes)}`")
    if "corpus_count" in payload:
        lines.append(f"- corpus_count: `{payload['corpus_count']}`")
    reasons = payload.get("reason_codes")
    if isinstance(reasons, list):
        lines.append("- reason_codes: `" + ", ".join(map(str, reasons)) + "`")
    return "\n".join(lines) + "\n"


def _load_json_object(path_value: str) -> dict[str, object]:
    path = Path(path_value).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("input JSON must contain one object")
    return payload


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

    registry = sub.add_parser(
        "corpus-registry",
        help="Render the Stage-1 corpus ownership and maintenance registry.",
    )
    add_subcommand_format(registry)

    health = sub.add_parser(
        "health-check",
        help="Exercise a Stage-1 scope, freshness, retrieval, and readback state.",
    )
    add_subcommand_format(health)
    health.add_argument(
        "--case",
        choices=[
            "unavailable",
            "empty",
            "stale",
            "wrong-project",
            "wrong-surface",
            "index-unavailable",
            "retrieval-failed",
            "readback-unverified",
            "retrieval-verified",
            "applied-verified",
        ],
        default="retrieval-verified",
        help="Use a compact public health fixture.",
    )

    candidate = sub.add_parser(
        "candidate-review",
        help="Exercise the stateless Stage-2 candidate and review seam.",
    )
    add_subcommand_format(candidate)
    candidate.add_argument(
        "--case",
        choices=["issue-fix-verified-contributor"],
        default="issue-fix-verified-contributor",
        help="Use a compact public Issue Fix adapter fixture.",
    )
    candidate.add_argument(
        "--decision",
        choices=["accept", "edit", "reject", "retire", "no_write"],
        default="accept",
        help="Apply one review decision without persisting provider state.",
    )

    evaluate = sub.add_parser(
        "evaluate",
        help="Run the bounded Stage-4 core-contract suite and release gate.",
    )
    add_subcommand_format(evaluate)

    dogfood = sub.add_parser(
        "dogfood-evaluate",
        help="Evaluate compact Stage-5 module outcomes after the Stage-4 gate.",
    )
    add_subcommand_format(dogfood)
    dogfood.add_argument(
        "--input",
        required=True,
        help=(
            "JSON object containing observations and operator_controls; no raw "
            "provider content is accepted."
        ),
    )

    control = sub.add_parser(
        "operator-control",
        help="Prepare an authorized Stage-5 edit or retire decision without writing.",
    )
    add_subcommand_format(control)
    control.add_argument("--input", required=True)
    control.add_argument("--action", choices=["edit", "retire"], required=True)
    control.add_argument("--control-ref", required=True)
    control.add_argument("--reasoning-summary", required=True)
    control.add_argument("--edited-content-summary")

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
        elif args.reward_memory_command == "corpus-registry":
            payload = build_reward_memory_corpus_registry_packet()
        elif args.reward_memory_command == "health-check":
            corpus, observation = reward_memory_health_case(args.case)
            payload = build_reward_memory_corpus_health_packet(corpus, observation)
        elif args.reward_memory_command == "candidate-review":
            adapter = issue_fix_verified_contributor_candidate_fixture()
            candidate = adapter["shared_candidate"]
            review = {
                "decision": args.decision,
                "reviewer_ref": "github:user:maintainer",
                "review_ref": f"review:fixture:{args.decision}",
                "reasoning_summary": "The compact evidence and scope were reviewed.",
            }
            if args.decision == "edit":
                review["edited_content_summary"] = (
                    "Keep focused fixes within the affected module unless "
                    "current evidence requires a broader surface."
                )
            if args.decision == "retire":
                candidate = review_reward_memory_candidate(
                    candidate,
                    review
                    | {
                        "decision": "accept",
                        "review_ref": "review:fixture:accept-before-retire",
                    },
                )
            payload = review_reward_memory_candidate(candidate, review)
            payload["adapter"] = adapter
        elif args.reward_memory_command == "evaluate":
            payload = run_reward_memory_evaluation()
        elif args.reward_memory_command == "dogfood-evaluate":
            source = _load_json_object(args.input)
            observations = source.get("observations")
            controls = source.get("operator_controls")
            if not isinstance(observations, Sequence) or isinstance(
                observations, (str, bytes)
            ):
                raise ValueError("observations must be a list")
            if not isinstance(controls, Sequence) or isinstance(controls, (str, bytes)):
                raise ValueError("operator_controls must be a list")
            if any(not isinstance(item, Mapping) for item in observations):
                raise ValueError("each observation must be an object")
            if any(not isinstance(item, Mapping) for item in controls):
                raise ValueError("each operator control must be an object")
            payload = build_reward_memory_dogfood_batch(
                [build_reward_memory_dogfood_receipt(item) for item in observations],
                [dict(item) for item in controls],
                evaluation=run_reward_memory_evaluation(),
            )
        elif args.reward_memory_command == "operator-control":
            source = _load_json_object(args.input)
            reviewed_record = source.get("reviewed_record")
            corpus = source.get("corpus")
            checkpoint = source.get("operator_checkpoint")
            if not isinstance(reviewed_record, Mapping):
                raise ValueError("reviewed_record must be an object")
            if not isinstance(corpus, Mapping):
                raise ValueError("corpus must be an object")
            if not isinstance(checkpoint, Mapping):
                raise ValueError("operator_checkpoint must be an object")
            payload = build_reward_memory_operator_control(
                reviewed_record,
                corpus,
                action=args.action,
                operator_checkpoint=checkpoint,
                control_ref=args.control_ref,
                reasoning_summary=args.reasoning_summary,
                edited_content_summary=args.edited_content_summary,
            )
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
                    "user_visible_behavior_change": (args.user_visible_behavior_change),
                    "hot_path_or_storage_change": (args.hot_path_or_storage_change),
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
    if args.reward_memory_command in {"evaluate", "dogfood-evaluate"} and (
        payload.get("ok") is not True
    ):
        return 2
    return 0
