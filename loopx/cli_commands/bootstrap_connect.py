from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from ..execution_profile import DEFAULT_EXECUTION_PROFILE


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_bootstrap_connect_command(subparsers: argparse._SubParsersAction) -> None:
    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument(
        "--fork-goal",
        help="Create a new forked goal id instead of reusing an existing global goal route.",
    )
    bootstrap_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE, help="Initial goal objective.")
    bootstrap_parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Goal domain label.")
    bootstrap_parser.add_argument("--role", choices=["controller", "subagent"], default="controller")
    bootstrap_parser.add_argument("--parent-goal-id", help="Parent goal id when --role subagent.")
    bootstrap_parser.add_argument("--state-file", help="Active goal state path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--goal-doc", help="Primary goal document path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--adapter-kind", default="generic_project_goal_v0")
    bootstrap_parser.add_argument("--adapter-status", default="connected")
    bootstrap_parser.add_argument("--next-probe", help="Optional project-specific pre-tick command.")
    bootstrap_parser.add_argument(
        "--spawn-allowed",
        action="store_true",
        help="Declare that this controller may spawn child agents.",
    )
    bootstrap_parser.add_argument("--max-children", type=int, default=3)
    bootstrap_parser.add_argument(
        "--allowed-domain",
        action="append",
        default=[],
        help="Allowed child work domain. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--write-scope",
        action="append",
        default=[],
        help="Allowed write scope such as docs/**. Repeatable.",
    )
    bootstrap_parser.add_argument("--claim-ttl-minutes", type=int, default=30)
    bootstrap_parser.add_argument(
        "--execution-minimum-scale",
        default=str(DEFAULT_EXECUTION_PROFILE["minimum_scale"]),
        help="Minimum delivery scale after repeated small follow-through.",
    )
    bootstrap_parser.add_argument(
        "--execution-must-include",
        action="append",
        default=[],
        help="Required delivery component. Repeatable; defaults to artifact, validation, and state writeback.",
    )
    bootstrap_parser.add_argument(
        "--execution-small-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["degradation_policy"]["small_scale_streak_threshold"]),
        help="Repeated small-scale streak that triggers the delivery contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-marker",
        action="append",
        default=[],
        help="Classification substring that counts as primary outcome/evidence progress. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-only-hint",
        action="append",
        default=[],
        help="Classification substring that counts as surface-only progress unless an outcome marker is present. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["outcome_floor"]["surface_streak_threshold"]),
        help="Surface-progress streak that triggers the outcome-floor contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-must-advance",
        action="append",
        default=[],
        help="Outcome/evidence floor label that future delivery must advance. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--no-onboarding-scan",
        action="store_true",
        help="Skip the fast first-connect repository scan and todo candidate proposal.",
    )
    bootstrap_parser.add_argument(
        "--accept-onboarding-agent-todos",
        action="store_true",
        help="Write all proposed onboarding agent todos into the initial active state.",
    )
    bootstrap_parser.add_argument(
        "--begin-autonomous-advance",
        action="store_true",
        help="Record that Codex may begin from accepted onboarding agent todos after the quota guard permits work.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-commits",
        type=int,
        default=5,
        help="Maximum recent commits sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-status-paths",
        type=int,
        default=12,
        help="Maximum git status lines sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-top-level-files",
        type=int,
        default=24,
        help="Maximum top-level names sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument(
        "--replace-state",
        action="store_true",
        help=(
            "Allow replacing an existing global route for the same goal id. "
            "Writes a global registry backup before changing the route."
        ),
    )
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    bootstrap_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not merge this project registry into the shared global registry.",
    )


def handle_bootstrap_connect_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
) -> int | None:
    if args.command not in {"bootstrap", "connect"}:
        return None
    try:
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
        state_file = Path(args.state_file).expanduser() if args.state_file else None
        goal_doc = Path(args.goal_doc).expanduser() if args.goal_doc else None
        if args.fork_goal and args.goal_id and args.fork_goal != args.goal_id:
            raise ValueError("--fork-goal cannot be combined with a different --goal-id")
        goal_id = args.fork_goal or args.goal_id
        payload = bootstrap_project(
            project=Path(args.project),
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id=goal_id,
            objective=args.objective,
            domain=args.domain,
            role=args.role,
            parent_goal_id=args.parent_goal_id,
            state_file=state_file,
            goal_doc=goal_doc,
            adapter_kind=args.adapter_kind,
            adapter_status=args.adapter_status,
            next_probe=args.next_probe,
            spawn_allowed=args.spawn_allowed,
            max_children=args.max_children,
            allowed_domains=args.allowed_domain,
            write_scope=args.write_scope,
            claim_ttl_minutes=args.claim_ttl_minutes,
            execution_minimum_scale=args.execution_minimum_scale,
            execution_must_include=args.execution_must_include or None,
            execution_small_streak_threshold=args.execution_small_streak_threshold,
            execution_outcome_markers=args.execution_outcome_marker or None,
            execution_surface_only_hints=args.execution_surface_only_hint or None,
            execution_surface_streak_threshold=args.execution_surface_streak_threshold,
            execution_outcome_must_advance=args.execution_outcome_must_advance or None,
            onboarding_scan_enabled=not bool(args.no_onboarding_scan),
            accept_onboarding_agent_todos=bool(args.accept_onboarding_agent_todos),
            begin_autonomous_advance=bool(args.begin_autonomous_advance),
            onboarding_max_commits=args.onboarding_max_commits,
            onboarding_max_status_paths=args.onboarding_max_status_paths,
            onboarding_max_top_level_files=args.onboarding_max_top_level_files,
            force=args.force,
            dry_run=args.dry_run,
            sync_global=not bool(args.no_global_sync),
            allow_global_route_replacement=bool(args.replace_state),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "registry": str(registry_path),
            "error": str(exc),
        }
    print_payload(payload, args.format, render_bootstrap_markdown)
    return 0 if payload.get("ok") else 1
