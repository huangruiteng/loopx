from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from . import (
    AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
    build_auto_research_rollout_events,
    build_live_auto_research_projection,
    build_auto_research_projection,
    load_auto_research_evidence_packet,
    load_auto_research_evidence_packet_inputs,
    load_auto_research_fixture,
    render_auto_research_markdown,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import (
    append_rollout_event,
    load_rollout_events,
    rollout_event_log_path,
)
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

    append_parser = auto_research_sub.add_parser(
        "append-evidence",
        help="Append an auto_research_evidence_packet_v0 into the LoopX rollout event log.",
    )
    add_subcommand_format(append_parser)
    append_parser.add_argument("--packet", required=True, help="Path to auto_research_evidence_packet_v0 JSON.")
    append_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rollout events without appending them.",
    )


def _append_auto_research_rollout_events(
    *,
    packet_path: str,
    registry_path: Path,
    runtime_root_arg: str | None,
    dry_run: bool,
) -> dict[str, object]:
    packet = load_auto_research_evidence_packet(packet_path)
    goal_id = packet["research_contract"]["goal_id"]
    events = build_auto_research_rollout_events(packet)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    log_path = rollout_event_log_path(runtime_root, goal_id)
    existing_ids = {
        str(event.get("event_id"))
        for event in load_rollout_events(log_path)
        if event.get("event_id")
    }
    appended_ids: list[str] = []
    skipped_ids: list[str] = []
    for event in events:
        event_id = str(event["event_id"])
        if event_id in existing_ids:
            skipped_ids.append(event_id)
            continue
        if not dry_run:
            append_rollout_event(log_path, event)
            existing_ids.add(event_id)
        appended_ids.append(event_id)
    counts_by_kind = Counter(str(event.get("event_kind") or "") for event in events)
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
        "goal_id": goal_id,
        "dry_run": dry_run,
        "event_count": len(events),
        "appended_count": 0 if dry_run else len(appended_ids),
        "would_append_count": len(appended_ids),
        "skipped_existing_count": len(skipped_ids),
        "event_ids": [str(event["event_id"]) for event in events],
        "appended_event_ids": [] if dry_run else appended_ids,
        "skipped_existing_event_ids": skipped_ids,
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "packet_summary": packet["summary"],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "loopx_rollout_event_log",
        },
    }


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
                registry = load_registry(registry_path)
                runtime_root = resolve_runtime_root(registry, runtime_root_arg)
                rollout_events = load_rollout_events(
                    rollout_event_log_path(runtime_root, args.goal_id)
                )
                payload = build_live_auto_research_projection(
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    quota_payload=quota_payload,
                    rollout_events=rollout_events,
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
        elif args.auto_research_command == "append-evidence":
            payload = _append_auto_research_rollout_events(
                packet_path=args.packet,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                dry_run=args.dry_run,
            )
        else:
            raise ValueError("auto-research requires the `frontier`, `evidence`, or `append-evidence` subcommand")
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "auto-research",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_auto_research_markdown)
    return 0 if payload.get("ok") else 1
