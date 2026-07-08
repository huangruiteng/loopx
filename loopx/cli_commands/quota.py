from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..quota import (
    build_quota_plan,
    build_quota_should_run,
    record_quota_monitor_poll,
    record_quota_scheduler_ack,
    render_quota_markdown,
    render_quota_monitor_poll_markdown,
    render_quota_scheduler_ack_markdown,
    render_quota_should_run_markdown,
    render_quota_slot_preview_markdown,
    spend_quota_slot,
    void_quota_slot,
)
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status
from ..control_plane.runtime.status_projection_cache import (
    load_status_projection_cache,
    resolve_status_projection_cache_runtime_root,
    write_status_projection_cache,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
RolloutEventAppender = Callable[..., dict[str, object]]


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def register_quota_command(subparsers: argparse._SubParsersAction) -> None:
    quota_parser = subparsers.add_parser(
        "quota",
        help="Show agent-facing compute quota status or next-turn plan.",
    )
    quota_parser.add_argument(
        "quota_command",
        nargs="?",
        choices=[
            "status",
            "plan",
            "should-run",
            "monitor-poll",
            "scheduler-ack",
            "scheduler-ack-current",
            "spend-slot",
            "void-slot",
        ],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, monitor-poll for no-spend quiet poll evidence, scheduler-ack for no-spend Codex App RRULE state, scheduler-ack-current to ack from the latest scheduler hint, spend-slot for accounting, or void-slot for a non-destructive accounting correction.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for `quota should-run`, `quota monitor-poll`, `quota scheduler-ack`, `quota scheduler-ack-current`, `quota spend-slot`, and `quota void-slot`.")
    quota_parser.add_argument(
        "--agent-id",
        help=(
            "Registered agent id for `quota should-run` and scoped quota accounting "
            "commands; suppresses identity-upgrade warnings and records the identity "
            "on appended monitor/scheduler/spend/void events."
        ),
    )
    quota_parser.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
        help=(
            "For `quota should-run` and `quota spend-slot`, declare a capability "
            "available in this current agent environment. Repeat for multiple "
            "capabilities; basic local shell/filesystem capabilities are assumed."
        ),
    )
    quota_parser.add_argument(
        "--include-scheduler-detail",
        action="store_true",
        help=(
            "Include cold-path scheduler detail for local scheduler, Codex CLI, "
            "and Claude loop runtimes in `quota should-run` JSON."
        ),
    )
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument("--source", choices=["heartbeat", "controller", "adapter"], default="heartbeat", help="Source label for `quota spend-slot`.")
    quota_parser.add_argument("--void-generated-at", help="generated_at timestamp of the quota_slot_spent run to void.")
    quota_parser.add_argument("--reason-summary", help="Public-safe reason for `quota void-slot`.")
    quota_parser.add_argument("--todo-id", help="Monitor todo id for `quota monitor-poll` metadata writeback.")
    quota_parser.add_argument("--target-key", help="Stable monitor target key for `quota monitor-poll` metadata writeback.")
    quota_parser.add_argument("--result-hash", help="Public-safe result hash observed by `quota monitor-poll`.")
    quota_parser.add_argument("--material-change", action="store_true", help="Mark a monitor poll as a material transition instead of unchanged evidence.")
    quota_parser.add_argument("--cadence", help="Monitor cadence used to compute the next due timestamp, e.g. 30m, 2h, or 1d.")
    quota_parser.add_argument("--next-due-at", help="Explicit ISO timestamp for the next monitor poll.")
    quota_parser.add_argument("--next-agent-todo", help="Agent follow-up todo to add when `--material-change` is set.")
    quota_parser.add_argument("--next-user-todo", help="User gate todo to add when `--material-change` is set.")
    quota_parser.add_argument("--next-claimed-by", help="Registered agent id to claim the `--next-agent-todo` follow-up.")
    quota_parser.add_argument("--surface", default="codex_app", help="Scheduler surface for `quota scheduler-ack`; defaults to codex_app.")
    quota_parser.add_argument("--state-key", default="scheduler_hint.codex_app.stateful_backoff", help="Scheduler state key for `quota scheduler-ack`.")
    quota_parser.add_argument("--applied-rrule", help="RRULE successfully applied by the host before `quota scheduler-ack --execute`.")
    quota_parser.add_argument("--reset-token", help="Optional reset token to validate before scheduler ack.")
    quota_parser.add_argument("--identity-signature", help="Optional identity signature to validate before scheduler ack.")
    quota_parser.add_argument(
        "--use-current-hint",
        action="store_true",
        help=(
            "For `quota scheduler-ack`, resolve reset token and identity signature "
            "from the latest quota should-run scheduler hint; `scheduler-ack-current` "
            "sets this automatically."
        ),
    )
    quota_parser.add_argument("--dry-run", action="store_true", help="Keep quota accounting or scheduler-state writes as preview-only. This is the default.")
    quota_parser.add_argument("--execute", action="store_true", help="Execute the quota accounting write or no-spend scheduler-state ack.")
    quota_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    quota_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    quota_parser.add_argument(
        "--use-projection-cache",
        action="store_true",
        help=(
            "Read a fresh status_projection_cache_v0 snapshot before building "
            "quota decisions. Misses and expired snapshots fall back to full "
            "status collection."
        ),
    )
    quota_parser.add_argument(
        "--write-projection-cache",
        action="store_true",
        help="Write the status projection cache after a full quota status collection.",
    )
    quota_parser.add_argument(
        "--projection-cache-ttl-seconds",
        type=int,
        default=120,
        help="Freshness window for --use-projection-cache. Defaults to 120 seconds.",
    )
    quota_parser.add_argument("--limit", type=int, default=5)


def handle_quota_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    append_cli_rollout_event: RolloutEventAppender,
) -> int:
    try:
        scan_roots = [Path(item).expanduser() for item in args.scan_path]
        if not scan_roots:
            scan_roots = [Path(args.scan_root).expanduser()]
        status_limit = max(0, args.limit)
        if args.quota_command in {"should-run", "monitor-poll", "scheduler-ack", "scheduler-ack-current"}:
            status_limit = max(status_limit, AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK)
        runtime_root = resolve_status_projection_cache_runtime_root(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
        )
        status_payload = None
        cache_metadata = None
        use_projection_cache = bool(getattr(args, "use_projection_cache", False))
        write_projection_cache_enabled = bool(getattr(args, "write_projection_cache", False))
        projection_cache_ttl_seconds = int(getattr(args, "projection_cache_ttl_seconds", 120))
        if use_projection_cache:
            status_payload, cache_metadata = load_status_projection_cache(
                registry_path=registry_path,
                runtime_root=runtime_root,
                scan_roots=scan_roots,
                limit=status_limit,
                include_task_graph=False,
                goal_id=None,
                max_age_seconds=projection_cache_ttl_seconds,
            )
        if status_payload is None:
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
                scan_roots=scan_roots,
                limit=status_limit,
            )
            if write_projection_cache_enabled:
                cache_metadata = write_status_projection_cache(
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    scan_roots=scan_roots,
                    limit=status_limit,
                    include_task_graph=False,
                    goal_id=None,
                    payload=status_payload,
                    max_age_seconds=projection_cache_ttl_seconds,
                )
        elif isinstance(status_payload.get("projection_cache"), dict):
            cache_metadata = dict(status_payload["projection_cache"])
        if args.quota_command == "should-run":
            if not args.goal_id:
                raise ValueError("`loopx quota should-run` requires --goal-id")
            payload = build_quota_should_run(
                status_payload,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                include_scheduler_detail=bool(args.include_scheduler_detail),
            )
        elif args.quota_command == "monitor-poll":
            if not args.goal_id:
                raise ValueError("`loopx quota monitor-poll` requires --goal-id")
            if args.dry_run and args.execute:
                raise ValueError("`loopx quota monitor-poll` accepts only one of --dry-run or --execute")
            payload = record_quota_monitor_poll(
                status_payload,
                goal_id=args.goal_id,
                registry_path=registry_path,
                execute=bool(args.execute),
                source=args.source,
                reason_summary=args.reason_summary,
                agent_id=args.agent_id,
                todo_id=args.todo_id,
                target_key=args.target_key,
                result_hash=args.result_hash,
                material_change=bool(args.material_change),
                cadence=args.cadence,
                next_due_at=args.next_due_at,
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_claimed_by=args.next_claimed_by,
            )
        elif args.quota_command in {"scheduler-ack", "scheduler-ack-current"}:
            if not args.goal_id:
                raise ValueError(f"`loopx quota {args.quota_command}` requires --goal-id")
            if not args.agent_id:
                raise ValueError(f"`loopx quota {args.quota_command}` requires --agent-id")
            if args.dry_run and args.execute:
                raise ValueError(f"`loopx quota {args.quota_command}` accepts only one of --dry-run or --execute")
            payload = record_quota_scheduler_ack(
                status_payload,
                goal_id=args.goal_id,
                execute=bool(args.execute),
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                surface=args.surface,
                state_key=args.state_key,
                applied_rrule=args.applied_rrule,
                reset_token=args.reset_token,
                identity_signature=args.identity_signature,
                reason_summary=args.reason_summary,
                use_current_hint=bool(args.use_current_hint or args.quota_command == "scheduler-ack-current"),
            )
        elif args.quota_command == "spend-slot":
            if not args.goal_id:
                raise ValueError("`loopx quota spend-slot` requires --goal-id")
            if args.dry_run and args.execute:
                raise ValueError("`loopx quota spend-slot` accepts only one of --dry-run or --execute")
            payload = spend_quota_slot(
                status_payload,
                goal_id=args.goal_id,
                slots=args.slots,
                execute=bool(args.execute),
                source=args.source,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
            )
        elif args.quota_command == "void-slot":
            if not args.goal_id:
                raise ValueError("`loopx quota void-slot` requires --goal-id")
            if not args.void_generated_at:
                raise ValueError("`loopx quota void-slot` requires --void-generated-at")
            if args.dry_run and args.execute:
                raise ValueError("`loopx quota void-slot` accepts only one of --dry-run or --execute")
            payload = void_quota_slot(
                status_payload,
                goal_id=args.goal_id,
                voided_run_generated_at=args.void_generated_at,
                execute=bool(args.execute),
                source=args.source,
                reason_summary=args.reason_summary,
                agent_id=args.agent_id,
            )
        else:
            payload = build_quota_plan(status_payload, mode=args.quota_command)
        if cache_metadata:
            payload["status_projection_cache"] = cache_metadata
    except Exception as exc:
        if args.quota_command in {"should-run", "monitor-poll", "scheduler-ack", "scheduler-ack-current", "spend-slot", "void-slot"}:
            payload = {
                "ok": False,
                "mode": args.quota_command,
                "goal_id": args.goal_id,
                "decision": "skip",
                "should_run": False,
                "reason": str(exc),
                "state": "blocked_health",
                "waiting_on": "codex",
                "status": "quota_collection_failed",
                "source": "quota",
                "recommended_action": "fix quota/status collection before spending automatic compute",
            }
            if args.quota_command == "monitor-poll":
                payload.update(
                    {
                        "source": args.source,
                        "agent_id": args.agent_id,
                        "todo_id": args.todo_id,
                        "target_key": args.target_key,
                        "result_hash": args.result_hash,
                        "material_change": bool(args.material_change),
                    }
                )
            if args.quota_command in {"scheduler-ack", "scheduler-ack-current"}:
                payload.update(
                    {
                        "agent_id": args.agent_id,
                        "surface": args.surface,
                        "state_key": args.state_key,
                        "applied_rrule": args.applied_rrule,
                    }
                )
        else:
            payload = {
                "ok": False,
                "mode": args.quota_command,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
                "error": str(exc),
                "summary": {
                    "registered_goals": 0,
                    "health_blockers": 1,
                    "next_automatic_turn": None,
                    "states": {},
                },
                "groups": {},
                "health_items": [
                    {
                        "goal_id": "loopx-quota",
                        "status": "quota_collection_failed",
                        "waiting_on": "codex",
                        "severity": "high",
                        "recommended_action": str(exc),
                        "source": "quota",
                    }
                ],
            }
    quota_event_kinds = {
        "should-run": "quota_should_run",
        "monitor-poll": "quota_monitor_poll",
        "scheduler-ack": "quota_scheduler_ack",
        "scheduler-ack-current": "quota_scheduler_ack",
        "spend-slot": "quota_spend",
        "void-slot": "quota_void",
    }
    should_log_quota = (
        args.quota_command in quota_event_kinds
        and (
            args.quota_command == "should-run"
            or (payload.get("ok") and bool(payload.get("appended")))
        )
    )
    if should_log_quota:
        append_cli_rollout_event(
            payload,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            event_kind=quota_event_kinds[args.quota_command],
            agent_id=args.agent_id,
            status=str(
                payload.get("effective_action")
                or payload.get("decision")
                or payload.get("mode")
                or args.quota_command
            ),
            summary=(
                f"quota {args.quota_command} decision="
                f"{payload.get('decision') or payload.get('mode')} "
                f"state={payload.get('state') or ''}"
            ),
            details={
                "command": "quota",
                "quota_command": args.quota_command,
                "ok": bool(payload.get("ok")),
                "should_run": bool(payload.get("should_run")),
                "appended": bool(payload.get("appended")),
                "slots": payload.get("slots") or "",
                "source": payload.get("source") or "",
                "todo_id": payload.get("todo_id") or "",
                "target_key": payload.get("target_key") or "",
                "applied_rrule": payload.get("applied_rrule") or "",
            },
            allow_failed=args.quota_command == "should-run",
        )
    renderer = (
        render_quota_should_run_markdown
        if args.quota_command == "should-run"
        else render_quota_monitor_poll_markdown
        if args.quota_command == "monitor-poll"
        else render_quota_scheduler_ack_markdown
        if args.quota_command in {"scheduler-ack", "scheduler-ack-current"}
        else render_quota_slot_preview_markdown
        if args.quota_command in {"spend-slot", "void-slot"}
        else render_quota_markdown
    )
    print_payload(payload, args.format, renderer)
    return 0 if payload.get("ok") else 1
