"""Private context consumption; never creates or reprioritizes Todos."""

import json
from ..agent_registry import registered_agent_ids_for_goal
from ..history import load_registry
from ..capabilities.manager_context import (
    acknowledge,
    pending,
    configure_evidence_scope,
)


def register_manager_inbox(subparsers, add_format):
    parser = subparsers.add_parser(
        "manager-inbox",
        help="Read context handed to an Agent and record its replan decision.",
    )
    add_format(parser)
    parser.add_argument(
        "manager_inbox_action", choices=("read", "acknowledge", "configure-read-scope")
    )
    parser.add_argument("--goal-id")
    parser.add_argument("--agent-id")
    parser.add_argument("--channel-id")
    parser.add_argument("--read-goal-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--request-id")
    parser.add_argument("--decision", choices=("adopt", "defer", "reject", "no_change"))
    parser.add_argument("--reason")


def handle_manager_inbox(args, registry_path, runtime_root):
    try:
        if args.manager_inbox_action == "configure-read-scope":
            result = configure_evidence_scope(
                runtime_root,
                registry_path,
                channel=args.channel_id or "",
                goal_ids=args.read_goal_id,
                execute=args.execute,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        registry = load_registry(registry_path)
        goal = next(
            (g for g in registry.get("goals", []) if g.get("id") == args.goal_id), None
        )
        if not goal or args.agent_id not in registered_agent_ids_for_goal(goal):
            raise ValueError("recipient is not registered")
        if args.manager_inbox_action == "read":
            result = pending(runtime_root, args.goal_id, args.agent_id)
        else:
            result = acknowledge(
                runtime_root,
                args.goal_id,
                args.agent_id,
                args.request_id or "",
                args.decision or "",
                args.reason or "",
            )
    except (OSError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1
