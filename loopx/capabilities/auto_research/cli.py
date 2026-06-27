from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from . import (
    build_live_auto_research_projection,
    build_auto_research_projection,
    load_auto_research_evidence_packet_inputs,
    load_auto_research_fixture,
    render_auto_research_markdown,
)
from ...quota import build_quota_should_run
from ...status import collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_auto_research_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    auto_research_parser = subparsers.add_parser(
        "auto-research",
        help="Project public-safe decentralized auto-research frontiers.",
    )
    auto_research_sub = auto_research_parser.add_subparsers(
        dest="auto_research_command",
        required=True,
    )
    frontier_parser = auto_research_sub.add_parser(
        "frontier",
        help="Render a per-agent decentralized research frontier from a public fixture or live LoopX state.",
    )
    add_subcommand_format(frontier_parser)
    frontier_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    frontier_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    frontier_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose runnable frontier should be projected.",
    )

    evidence_parser = auto_research_sub.add_parser(
        "evidence",
        help="Build public-safe research hypothesis/evidence records from protected eval outputs.",
    )
    add_subcommand_format(evidence_parser)
    evidence_parser.add_argument("--contract", required=True, help="Path to research_contract_v0 JSON.")
    evidence_parser.add_argument(
        "--eval-result",
        action="append",
        required=True,
        help="Path to a protected evaluator JSON result. Repeat for dev/holdout or retry evidence.",
    )
    evidence_parser.add_argument("--hypothesis-id", required=True)
    evidence_parser.add_argument("--todo-id", required=True)
    evidence_parser.add_argument("--agent-id", required=True)
    evidence_parser.add_argument("--claimed-by", required=True)
    evidence_parser.add_argument("--mechanism-family", required=True)
    evidence_parser.add_argument("--hypothesis", required=True)
    evidence_parser.add_argument("--parent-hypothesis-id")
    evidence_parser.add_argument("--grounding-ref", action="append", default=[])
    evidence_parser.add_argument("--novelty-audit-ref")
    evidence_parser.add_argument("--branch-ref")
    evidence_parser.add_argument("--attempt-start", type=int, default=1)


def handle_auto_research_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.auto_research_command == "frontier":
            if bool(args.fixture) == bool(args.goal_id):
                raise ValueError("auto-research frontier requires exactly one of --fixture or --goal-id")
            if args.fixture:
                fixture = load_auto_research_fixture(args.fixture)
                payload = build_auto_research_projection(
                    fixture,
                    agent_id=args.agent_id,
                )
            else:
                status_payload = collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=[Path.cwd()],
                    limit=5,
                )
                quota_payload = build_quota_should_run(
                    status_payload,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                )
                payload = build_live_auto_research_projection(
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    quota_payload=quota_payload,
                )
        elif args.auto_research_command == "evidence":
            payload = load_auto_research_evidence_packet_inputs(
                contract_path=args.contract,
                eval_result_paths=args.eval_result,
                hypothesis_id=args.hypothesis_id,
                todo_id=args.todo_id,
                agent_id=args.agent_id,
                claimed_by=args.claimed_by,
                mechanism_family=args.mechanism_family,
                hypothesis=args.hypothesis,
                parent_hypothesis_id=args.parent_hypothesis_id,
                grounding_refs=args.grounding_ref,
                novelty_audit_ref=args.novelty_audit_ref,
                branch_ref=args.branch_ref,
                attempt_start=args.attempt_start,
            )
        else:
            raise ValueError("auto-research requires the `frontier` or `evidence` subcommand")
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "auto-research",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_auto_research_markdown)
    return 0 if payload.get("ok") else 1
