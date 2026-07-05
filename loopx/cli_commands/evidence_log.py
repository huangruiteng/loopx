from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..control_plane.runtime.agent_scoped_evidence_log import build_agent_scoped_evidence_log
from ..history import collect_history, load_registry
from ..paths import resolve_runtime_root
from ..rollout_event_log import load_rollout_events, rollout_event_log_path


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def register_evidence_log_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "evidence-log",
        help="Read a public-safe, agent-scoped evidence ledger for replan and handoff.",
    )
    add_subcommand_format(parser)
    parser.add_argument("--goal-id", required=True, help="Goal id whose evidence should be read.")
    parser.add_argument(
        "--agent-id",
        required=True,
        help="Registered agent id. The ledger expands only this agent's event stream.",
    )
    parser.add_argument("--todo-id", help="Optional todo id filter for the current replan/work slice.")
    parser.add_argument("--since", help="Optional ISO timestamp lower bound.")
    parser.add_argument(
        "--event-kind",
        action="append",
        default=[],
        help="Optional rollout event kind filter. Repeatable.",
    )
    parser.add_argument("--limit", type=int, default=24, help="Maximum merged ledger rows to return.")
    parser.add_argument(
        "--history-limit",
        type=int,
        default=80,
        help="Maximum compact run-history rows to scan before agent/todo filtering.",
    )
    parser.add_argument(
        "--rollout-limit",
        type=int,
        default=400,
        help="Maximum rollout-event rows to scan from the tail before filtering.",
    )
    parser.add_argument(
        "--thin",
        action="store_true",
        help="Return the thin public-safe shape. This is the only current mode and is accepted for clarity.",
    )


def _goal_runs(history_payload: dict[str, Any], goal_id: str) -> list[dict[str, Any]]:
    goals = history_payload.get("goals") if isinstance(history_payload.get("goals"), list) else []
    for goal in goals:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            latest_runs = goal.get("latest_runs")
            return [dict(item) for item in latest_runs if isinstance(item, dict)] if isinstance(latest_runs, list) else []
    runs = history_payload.get("runs") if isinstance(history_payload.get("runs"), list) else []
    return [dict(item) for item in runs if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id]


def render_evidence_log_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return "\n".join(
            [
                "# LoopX Evidence Log",
                "",
                f"- ok: `{payload.get('ok')}`",
                f"- error: `{payload.get('error')}`",
                "",
            ]
        )
    lines = [
        "# LoopX Evidence Log",
        "",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- todo_id: `{payload.get('todo_id') or ''}`",
        f"- mode: `{payload.get('mode')}`",
        f"- rollout_events: `{payload.get('rollout_event_count')}`",
        f"- run_history_refs: `{payload.get('run_history_ref_count')}`",
        "",
        "## Ledger",
        "",
    ]
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), list) else []
    if not ledger:
        lines.append("- No matching public-safe evidence rows.")
    for row in ledger:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "unknown")
        when = str(row.get("recorded_at") or "")
        if source == "rollout_event_log":
            title = str(row.get("event_kind") or "event")
            suffix = str(row.get("status") or row.get("classification") or "")
        else:
            title = str(row.get("classification") or "run")
            suffix = str(row.get("delivery_outcome") or row.get("progress_scope") or "")
        summary = str(row.get("summary") or row.get("recommended_action") or row.get("health_check") or "")
        line = f"- `{when}` `{source}` {title}"
        if suffix:
            line += f" ({suffix})"
        if summary:
            line += f": {summary}"
        lines.append(line)
    frontier = payload.get("other_agent_frontier") if isinstance(payload.get("other_agent_frontier"), dict) else {}
    items = frontier.get("items") if isinstance(frontier.get("items"), list) else []
    if items:
        lines.extend(["", "## Other Agent Frontier", ""])
        for item in items:
            if not isinstance(item, dict):
                continue
            agent = str(item.get("agent_id") or "")
            classification = str(item.get("classification") or "latest run")
            lines.append(f"- `{agent}`: {classification}")
    lines.append("")
    return "\n".join(lines)


def handle_evidence_log_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "evidence-log":
        return None
    try:
        registry = load_registry(registry_path)
        runtime_root = resolve_runtime_root(registry, runtime_root_arg)
        rollout_events = load_rollout_events(
            rollout_event_log_path(runtime_root, args.goal_id),
            limit=max(0, int(args.rollout_limit)),
        )
        history_payload = collect_history(
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id=args.goal_id,
            limit=max(0, int(args.history_limit)),
        )
        payload = build_agent_scoped_evidence_log(
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            todo_id=args.todo_id,
            since=args.since,
            event_kinds=args.event_kind,
            limit=max(0, int(args.limit)),
            rollout_events=rollout_events,
            history_runs=_goal_runs(history_payload, args.goal_id),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "agent_scoped_evidence_log_v0",
            "goal_id": getattr(args, "goal_id", None),
            "agent_id": getattr(args, "agent_id", None),
            "error": str(exc),
        }
    selected_format = output_format(args)
    print_payload(payload, selected_format, render_evidence_log_markdown)
    return 0 if payload.get("ok") else 1
