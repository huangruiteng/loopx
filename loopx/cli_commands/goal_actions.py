from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..control_plane.goals.operator_actions import (
    GOAL_ACTION_CATALOG_SCHEMA_VERSION,
    build_goal_action_catalog,
    render_goal_action_catalog_markdown,
)
from ..review_packet import find_goal, find_queue_item, infer_action_kind
from ..status import collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_goal_actions_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "goal-actions",
        help="List fresh typed owner actions for one Goal.",
    )
    parser.add_argument(
        "--goal-id", required=True, help="Goal id present in the active registry."
    )


def handle_goal_actions_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
) -> int:
    try:
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=args.runtime_root,
            scan_roots=[],
            limit=5,
            goal_id=args.goal_id,
            include_public_boundary_scan=False,
            activation_state_filter=None,
        )
        queue_item = find_queue_item(status_payload, args.goal_id)
        status_goal = find_goal(status_payload, args.goal_id)
        operator_gate_required = (
            infer_action_kind(queue_item, status_goal) == "controller"
        )
        payload = build_goal_action_catalog(
            registry_path=registry_path,
            goal_id=args.goal_id,
            operator_gate_required=operator_gate_required,
            runtime_root_override=args.runtime_root,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": GOAL_ACTION_CATALOG_SCHEMA_VERSION,
            "goal_id": args.goal_id,
            "actions": [],
            "error": str(exc),
        }
    print_payload(payload, args.format, render_goal_action_catalog_markdown)
    return 0 if payload.get("ok") else 1
