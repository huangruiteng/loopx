from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from ..capabilities.explore.result_log import (
    DEFAULT_FINDING_LIMIT,
    DEFAULT_MERMAID_NODE_LIMIT,
    EDGE_TYPES,
    FINDING_STATUSES,
    NODE_KINDS,
    NODE_STATUSES,
    append_explore_result_event,
    build_explore_edge_event,
    build_explore_finding_event,
    build_explore_node_event,
    build_explore_result_projection,
    explore_result_log_path,
    load_explore_result_events,
)
from ..capabilities.lark.explore_results import (
    DEFAULT_EXPLORE_BASE_NAME,
    EXPLORE_TABLE_KEYS,
    LarkExploreConfig,
    build_explore_result_card,
    default_lark_explore_config_path,
    lark_explore_config_from_payload,
    lark_explore_schema_payload,
    read_lark_explore_local_config,
    setup_lark_explore_board,
    sync_explore_results_to_lark,
    write_lark_explore_local_config,
)
from ..capabilities.lark.kanban import DEFAULT_CLI_BIN
from ..history import load_registry
from ..paths import resolve_runtime_root


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]


def register_explore_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "explore",
        help="Record the exploration topology and project it into a Feishu/Lark result board.",
    )
    sub = parser.add_subparsers(dest="explore_command", required=True)

    schema = sub.add_parser("schema", help="Print the result-board schema and LoopX mapping.")
    add_subcommand_format(schema)

    node = sub.add_parser(
        "node",
        help="Add or update one exploration node (question, area, hypothesis, experiment, artifact).",
    )
    add_subcommand_format(node)
    node.add_argument("--goal-id", required=True)
    node.add_argument("--title", required=True, help="Compact public-safe node statement.")
    node.add_argument("--node-id", help="Stable node id; reuse it to update the same node.")
    node.add_argument("--kind", dest="node_kind", choices=sorted(NODE_KINDS))
    node.add_argument("--status", choices=sorted(NODE_STATUSES))
    node.add_argument("--summary", help="Optional compact public-safe detail.")
    node.add_argument("--blocked-reason", help="Required when --status blocked: why the loop is stuck.")
    node.add_argument("--parent", dest="parent_id", help="Parent node id for the topology tree.")
    _add_common_record_args(node)

    edge = sub.add_parser("edge", help="Link two exploration nodes with a typed edge.")
    add_subcommand_format(edge)
    edge.add_argument("--goal-id", required=True)
    edge.add_argument("--from", dest="from_node", required=True, help="Source node id.")
    edge.add_argument("--to", dest="to_node", required=True, help="Target node id.")
    edge.add_argument("--type", dest="edge_type", required=True, choices=sorted(EDGE_TYPES))
    edge.add_argument("--summary", help="Optional compact edge label detail.")
    edge.add_argument("--confidence", type=float, help="0..1 confidence.")
    edge.add_argument("--agent-id")
    edge.add_argument("--run-id")

    finding = sub.add_parser(
        "finding",
        help="Record one finding, optionally attached to a node; reuse --finding-id to update it.",
    )
    add_subcommand_format(finding)
    finding.add_argument("--goal-id", required=True)
    finding.add_argument("--title", required=True, help="Compact public-safe finding statement.")
    finding.add_argument("--finding-id", help="Stable finding id; reuse it to update the same finding.")
    finding.add_argument("--node", dest="node_id", help="Node id this finding belongs to.")
    finding.add_argument("--status", choices=sorted(FINDING_STATUSES))
    finding.add_argument("--summary", help="Optional compact public-safe detail.")
    finding.add_argument("--confidence", type=float, help="0..1 confidence.")
    _add_common_record_args(finding)

    summary = sub.add_parser(
        "summary",
        help="Build the bounded result projection that display sinks render.",
    )
    add_subcommand_format(summary)
    summary.add_argument("--goal-id", required=True)
    _add_projection_limit_args(summary)

    graph = sub.add_parser(
        "graph",
        help="Export the exploration topology as Mermaid flowchart source or graph JSON.",
    )
    add_subcommand_format(graph)
    graph.add_argument("--goal-id", required=True)
    _add_projection_limit_args(graph)
    graph.add_argument(
        "--graph-format",
        choices=["mermaid", "json"],
        default="mermaid",
    )
    graph.add_argument("--out", help="Also write the graph to this local file.")

    setup = sub.add_parser(
        "feishu-setup",
        help="Create the Nodes/Edges/Findings Lark Base tables. Dry-run unless --execute.",
    )
    add_subcommand_format(setup)
    _add_config_path_arg(setup)
    setup.add_argument("--base-name", default=DEFAULT_EXPLORE_BASE_NAME)
    setup.add_argument("--base-url", help="Reuse an existing shared Base URL.")
    setup.add_argument("--base-token", help="Reuse an existing Base token.")
    setup.add_argument("--cli-bin", default=DEFAULT_CLI_BIN)
    setup.add_argument("--as", dest="identity", default="user", choices=["bot", "user", "auto"])
    setup.add_argument("--execute", action="store_true", help="Actually run lark-cli write commands.")

    sync = sub.add_parser(
        "feishu-sync",
        help="Upsert the goal's result projection into the Lark board. Dry-run unless --execute.",
    )
    add_subcommand_format(sync)
    _add_config_path_arg(sync)
    sync.add_argument("--goal-id", required=True)
    _add_projection_limit_args(sync)
    sync.add_argument("--base-token")
    for table_key in EXPLORE_TABLE_KEYS:
        sync.add_argument(f"--table-id-{table_key}", dest=f"table_id_{table_key}")
    sync.add_argument("--cli-bin")
    sync.add_argument("--as", dest="identity", default="user", choices=["bot", "user", "auto"])
    sync.add_argument(
        "--sink-visibility",
        choices=["owner-only", "shared"],
        default="owner-only",
        help="Use shared to redact private links and external ids before writing rows.",
    )
    sync.add_argument("--execute", action="store_true", help="Actually upsert records and remember record ids.")

    card = sub.add_parser(
        "feishu-card",
        help="Build the result-card content for a gateway to send or update.",
    )
    add_subcommand_format(card)
    _add_config_path_arg(card)
    card.add_argument("--goal-id", required=True)
    _add_projection_limit_args(card)
    card.add_argument("--title")
    card.add_argument("--template", default="blue")
    card.add_argument("--message-id", help="Existing card message id (om_...) for updates.")
    card.add_argument(
        "--remember-message-id",
        action="store_true",
        help="Persist --message-id in the local board config.",
    )
    card.add_argument("--card-file", help="Also write the card JSON to this local file.")


def _add_common_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent-id")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="Public relative ref or opaque id, never a local absolute path. Repeatable.",
    )
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--supersedes", help="Result id this event supersedes.")


def _add_config_path_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config-path", help="Local board config path. Defaults beside the LoopX registry.")


def _add_projection_limit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--finding-limit", type=int, default=DEFAULT_FINDING_LIMIT)
    parser.add_argument("--mermaid-node-limit", type=int, default=DEFAULT_MERMAID_NODE_LIMIT)


def _target_config(args: argparse.Namespace, *, config_path: Path) -> LarkExploreConfig:
    stored = lark_explore_config_from_payload(read_lark_explore_local_config(config_path))
    base_token = args.base_token or (stored.base_token if stored else None)
    table_ids = dict(stored.table_ids) if stored else {}
    for table_key in EXPLORE_TABLE_KEYS:
        override = getattr(args, f"table_id_{table_key}", None)
        if override:
            table_ids[table_key] = override
    if not base_token or not all(table_ids.get(key) for key in EXPLORE_TABLE_KEYS):
        raise ValueError(
            "explore feishu target requires --base-token/--table-id-* or local config from feishu-setup"
        )
    return LarkExploreConfig(
        **{"base_" + "token": base_token},
        table_ids=table_ids,
        cli_bin=args.cli_bin or (stored.cli_bin if stored else DEFAULT_CLI_BIN),
        identity=args.identity or (stored.identity if stored else "user"),
    )


def _projection_for(args: argparse.Namespace, *, runtime_root: Path) -> dict[str, object]:
    log_path = explore_result_log_path(runtime_root, args.goal_id)
    events = load_explore_result_events(log_path, goal_id=args.goal_id)
    projection = build_explore_result_projection(
        events,
        goal_id=args.goal_id,
        finding_limit=max(0, int(args.finding_limit)),
        mermaid_node_limit=max(1, int(args.mermaid_node_limit)),
    )
    projection["log_path"] = str(log_path)
    return projection


def _append_event_payload(
    event: dict[str, object], *, runtime_root: Path, goal_id: str
) -> dict[str, object]:
    payload = append_explore_result_event(
        explore_result_log_path(runtime_root, goal_id), event
    )
    payload["goal_id"] = goal_id
    payload["event"] = event
    return payload


def _tree_lines(tree: object, *, indent: int = 0) -> list[str]:
    lines: list[str] = []
    if not isinstance(tree, list):
        return lines
    for branch in tree:
        if not isinstance(branch, dict):
            continue
        lines.append(f"{'  ' * indent}- [{branch.get('status')}] {branch.get('title')}")
        lines.extend(_tree_lines(branch.get("children"), indent=indent + 1))
    return lines


def render_explore_markdown(payload: dict[str, object]) -> str:
    lines = ["# LoopX Explore", ""]
    if not payload.get("ok"):
        lines.extend([f"- ok: `{payload.get('ok')}`", f"- error: `{payload.get('error')}`", ""])
        return "\n".join(lines)
    for key in (
        "schema_version",
        "goal_id",
        "execute",
        "event_kind",
        "result_id",
        "event_id",
        "sink_visibility",
        "message_id",
        "card_file",
        "out",
    ):
        if payload.get(key) not in (None, ""):
            lines.append(f"- {key}: `{payload.get(key)}`")
    counts = payload.get("counts")
    if isinstance(counts, dict):
        lines.append(
            f"- map: `{counts.get('node_count')} nodes, {counts.get('edge_count')} edges, "
            f"{counts.get('finding_count')} findings`"
        )
    row_counts = payload.get("row_counts")
    if isinstance(row_counts, dict):
        joined = ", ".join(f"{key}={value}" for key, value in row_counts.items())
        lines.append(f"- rows: `{joined}`")
    tree_lines = _tree_lines(payload.get("tree"))
    if tree_lines:
        lines.extend(["", "## Topology", "", *tree_lines])
    stuck = payload.get("stuck")
    if isinstance(stuck, list) and stuck:
        lines.extend(["", "## Blocked", ""])
        for item in stuck:
            if isinstance(item, dict):
                reason = str(item.get("blocked_reason") or "").strip()
                lines.append(f"- {item.get('title')}" + (f" - {reason}" if reason else ""))
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        lines.extend(["", "## Findings", ""])
        for item in findings:
            if isinstance(item, dict):
                lines.append(f"- [{item.get('status')}] {item.get('finding')}")
    mermaid = payload.get("mermaid")
    if isinstance(mermaid, str) and mermaid and payload.get("graph_format") != "json":
        lines.extend(["", "## Mermaid", "", "```mermaid", mermaid, "```"])
    card_markdown = payload.get("card_markdown")
    if isinstance(card_markdown, str) and card_markdown:
        lines.extend(["", "## Card", "", card_markdown])
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    return "\n".join(lines)


def handle_explore_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.command != "explore":
        return None
    fmt = output_format(args)
    try:
        runtime_root = resolve_runtime_root(load_registry(registry_path), runtime_root_arg)
        config_path = (
            Path(args.config_path).expanduser()
            if getattr(args, "config_path", None)
            else default_lark_explore_config_path(registry_path)
        )
        if args.explore_command == "schema":
            payload = lark_explore_schema_payload()
        elif args.explore_command == "node":
            event = build_explore_node_event(
                goal_id=args.goal_id,
                title=args.title,
                node_id=args.node_id,
                node_kind=args.node_kind,
                status=args.status,
                summary=args.summary,
                blocked_reason=args.blocked_reason,
                parent_id=args.parent_id,
                agent_id=args.agent_id,
                run_id=args.run_id,
                evidence_refs=args.evidence_ref,
                tags=args.tag,
                supersedes=args.supersedes,
            )
            payload = _append_event_payload(event, runtime_root=runtime_root, goal_id=args.goal_id)
        elif args.explore_command == "edge":
            event = build_explore_edge_event(
                goal_id=args.goal_id,
                from_node=args.from_node,
                to_node=args.to_node,
                edge_type=args.edge_type,
                summary=args.summary,
                confidence=args.confidence,
                agent_id=args.agent_id,
                run_id=args.run_id,
            )
            payload = _append_event_payload(event, runtime_root=runtime_root, goal_id=args.goal_id)
        elif args.explore_command == "finding":
            event = build_explore_finding_event(
                goal_id=args.goal_id,
                title=args.title,
                finding_id=args.finding_id,
                node_id=args.node_id,
                status=args.status,
                summary=args.summary,
                confidence=args.confidence,
                agent_id=args.agent_id,
                run_id=args.run_id,
                evidence_refs=args.evidence_ref,
                tags=args.tag,
                supersedes=args.supersedes,
            )
            payload = _append_event_payload(event, runtime_root=runtime_root, goal_id=args.goal_id)
        elif args.explore_command == "summary":
            payload = _projection_for(args, runtime_root=runtime_root)
        elif args.explore_command == "graph":
            projection = _projection_for(args, runtime_root=runtime_root)
            payload = {
                "ok": True,
                "schema_version": "loopx_explore_graph_v0",
                "goal_id": args.goal_id,
                "graph_format": args.graph_format,
                "counts": projection.get("counts"),
                "nodes": projection.get("nodes"),
                "edges": projection.get("edges"),
                "mermaid": projection.get("mermaid"),
            }
            if args.out:
                out_path = Path(args.out).expanduser()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if args.graph_format == "mermaid":
                    out_path.write_text(str(projection.get("mermaid") or "") + "\n", encoding="utf-8")
                else:
                    graph_json = {
                        "goal_id": args.goal_id,
                        "nodes": projection.get("nodes"),
                        "edges": projection.get("edges"),
                    }
                    out_path.write_text(
                        json.dumps(graph_json, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                payload["out"] = str(out_path)
        elif args.explore_command == "feishu-setup":
            payload = setup_lark_explore_board(
                config_path=config_path,
                base_name=args.base_name,
                base_url=args.base_url,
                **{"base_" + "token": args.base_token},
                cli_bin=args.cli_bin,
                identity=args.identity,
                execute=bool(args.execute),
            )
        elif args.explore_command == "feishu-sync":
            projection = _projection_for(args, runtime_root=runtime_root)
            payload = sync_explore_results_to_lark(
                _target_config(args, config_path=config_path),
                projection=projection,
                config_path=config_path,
                sink_visibility=args.sink_visibility,
                execute=bool(args.execute),
            )
        elif args.explore_command == "feishu-card":
            projection = _projection_for(args, runtime_root=runtime_root)
            local = read_lark_explore_local_config(config_path)
            stored_card = local.get("card") if isinstance(local.get("card"), dict) else {}
            message_id = args.message_id or str(stored_card.get("message_id") or "") or None
            payload = build_explore_result_card(
                projection,
                title=args.title,
                template=args.template,
                message_id=message_id,
            )
            if args.remember_message_id and args.message_id:
                write_lark_explore_local_config(
                    config_path,
                    {
                        **{
                            key: value
                            for key, value in local.items()
                            if key not in {"ok", "exists", "path"}
                        },
                        "card": {**stored_card, "message_id": args.message_id},
                    },
                )
                payload["message_id_remembered"] = True
            if args.card_file:
                card_file = Path(args.card_file).expanduser()
                card_file.parent.mkdir(parents=True, exist_ok=True)
                card_file.write_text(
                    json.dumps(payload["card"], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                payload["card_file"] = str(card_file)
        else:
            raise ValueError(f"unknown explore command: {args.explore_command}")
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_explore_error_v0",
            "error": str(exc),
        }
    print_payload(payload, fmt, render_explore_markdown)
    return 0 if payload.get("ok") else 1
