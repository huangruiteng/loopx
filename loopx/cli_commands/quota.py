from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..control_plane.quota.cli_projection import (
    compact_quota_monitor_poll_cli_payload,
    compact_quota_should_run_cli_payload,
)
from ..control_plane.quota.heartbeat_receipt import (
    fail_heartbeat_receipt,
    find_heartbeat_receipt,
    heartbeat_receipt_view,
)
from ..control_plane.quota.live_decision import build_live_quota_should_run_decision
from ..control_plane.quota.monitor_poll import find_quota_monitor_poll_turn
from ..control_plane.quota.scheduler_ack import (
    record_quota_scheduler_failure_for_decision,
)
from ..control_plane.quota.spend_sources import (
    DEFAULT_SLOT_SPEND_SOURCE,
    VALID_SLOT_SPEND_SOURCES,
)
from ..control_plane.quota.turn_envelope import build_turn_envelope
from ..control_plane.runtime.status_projection_cache import (
    load_status_projection_cache,
    resolve_status_projection_cache_runtime_root,
    write_status_projection_cache,
)
from ..control_plane.scheduler.execution_context import (
    SchedulerExecutionContextResolution,
    SchedulerRuntimeProfile,
    scheduler_execution_context_for_runtime_profile,
)
from ..file_lock import lock_timeout_error_fields
from ..presentation.renderers.quota_event_markdown import (
    render_quota_monitor_poll_markdown,
    render_quota_slot_preview_markdown,
)
from ..presentation.renderers.quota_markdown import (
    render_quota_markdown,
    render_quota_scheduler_ack_markdown,
    render_quota_scheduler_failure_markdown,
    render_quota_should_run_markdown,
)
from ..presentation.renderers.turn_envelope_markdown import (
    render_turn_envelope_markdown,
)
from ..quota import (
    build_quota_plan,
    build_quota_should_run,
    record_quota_monitor_poll,
    record_quota_scheduler_ack,
    spend_quota_slot,
    void_quota_slot,
)
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status
from ..turn_identity import normalize_turn_instance_id
from ..upgrade import resolve_codex_app_automation_rrule
from .lark_inbox import build_lark_operator_inbox_urgency_projector
from .quota_request import (
    QUOTA_DETAIL_SECTIONS,
    QUOTA_MONITOR_POLL_DETAIL_SECTIONS,
    QUOTA_SHOULD_RUN_DETAIL_SECTIONS,
    quota_detail_sections_from_args,
    validate_quota_command_request,
)

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
RolloutEventAppender = Callable[..., dict[str, object]]
QUOTA_EVENT_KINDS = {
    "should-run": "quota_should_run",
    "monitor-poll": "quota_monitor_poll",
    "scheduler-ack": "quota_scheduler_ack",
    "scheduler-ack-current": "quota_scheduler_ack",
    "scheduler-fail-current": "quota_scheduler_failure",
    "spend-slot": "quota_spend",
    "void-slot": "quota_void",
}
QUOTA_SCHEDULER_COMMANDS = frozenset(
    {
        "should-run",
        "monitor-poll",
        "scheduler-ack",
        "scheduler-ack-current",
        "scheduler-fail-current",
    }
)


@dataclass(frozen=True, slots=True)
class _QuotaCommandContext:
    runtime_root: Path
    scan_roots: list[Path]
    status_limit: int
    status_goal_id: str | None
    status_payload: dict[str, object]
    cache_metadata: dict[str, object] | None
    scheduler_context: Mapping[str, object] | SchedulerExecutionContextResolution | None
    operator_inbox_urgency_projector: Callable[..., dict[str, object]]
    detail_sections: frozenset[str]
    heartbeat_turn_id: str | None


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _scheduler_execution_context_from_args(
    args: argparse.Namespace,
) -> Mapping[str, object] | SchedulerExecutionContextResolution | None:
    explicit_scheduler_fields = (
        args.host_surface,
        args.scheduler_owner,
        args.execution_mode,
    )
    if args.codex_app and (args.runtime_profile or any(explicit_scheduler_fields)):
        raise ValueError(
            "--codex-app cannot be combined with --runtime-profile, "
            "--host-surface, --scheduler-owner, or --execution-mode"
        )
    if args.runtime_profile and any(explicit_scheduler_fields):
        raise ValueError(
            "--runtime-profile cannot be combined with --host-surface, "
            "--scheduler-owner, or --execution-mode"
        )
    runtime_profile = (
        SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT.value
        if args.codex_app
        else args.runtime_profile
    )
    if runtime_profile:
        return scheduler_execution_context_for_runtime_profile(runtime_profile)
    if any(explicit_scheduler_fields):
        return {
            "host_surface": args.host_surface,
            "scheduler_owner": args.scheduler_owner,
            "execution_mode": args.execution_mode,
            "source": "quota_cli_invocation",
        }
    return None


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
            "scheduler-fail-current",
            "spend-slot",
            "void-slot",
        ],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, monitor-poll for no-spend quiet poll evidence, scheduler-ack for successful Codex App RRULE state, scheduler-fail-current to suppress a repeated failed host update pair, spend-slot for accounting, or void-slot for a non-destructive accounting correction.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for one-goal quota commands, including should-run, scheduler ACK/failure, spend, and void.")
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
            "For `quota should-run`, `quota monitor-poll`, `quota scheduler-ack`, "
            "`quota scheduler-ack-current`, and `quota spend-slot`, declare a "
            "capability available in this current agent environment. Repeat the "
            "same declarations for commands that recompute should-run; basic local "
            "shell/filesystem capabilities are assumed."
        ),
    )
    quota_parser.add_argument(
        "--include-detail",
        dest="include_details",
        action="append",
        choices=[*QUOTA_DETAIL_SECTIONS, "all"],
        help=(
            "Include one command-specific cold-path detail section. For `quota "
            "should-run`: scheduler, agent-todos, user-todos, goal-boundary, or "
            "vision. For `quota monitor-poll`: decisions. Repeat for multiple "
            "sections or use `all`."
        ),
    )
    quota_parser.add_argument(
        "--include-scheduler-detail",
        action="store_true",
        # Deprecated compatibility alias. Remove in the next breaking release.
        help=argparse.SUPPRESS,
    )
    quota_parser.add_argument(
        "--codex-app-current-rrule",
        help=(
            "Current RRULE observed from the active Codex App heartbeat. For "
            "`quota should-run`, this reconciles host reality with LoopX's last "
            "scheduler ACK so a stale ACK cannot suppress a required update."
        ),
    )
    quota_parser.add_argument(
        "--runtime-profile",
        choices=[profile.value for profile in SchedulerRuntimeProfile],
        help=(
            "Explicit scheduler runtime shortcut for a known host boundary. "
            "Cannot be combined with --host-surface, --scheduler-owner, or "
            "--execution-mode."
        ),
    )
    quota_parser.add_argument(
        "-A",
        "--codex-app",
        action="store_true",
        help=(
            "Compact explicit alias for --runtime-profile "
            "codex_app_heartbeat. Cannot be combined with another scheduler "
            "runtime or execution context."
        ),
    )
    quota_parser.add_argument(
        "-H",
        "--host-surface",
        choices=[
            "ark_managed_agent",
            "codex_app",
            "codex_app_ssh",
            "codex_cli",
            "generic_cli",
            "claude_code",
            "kunluncode",
            "local_scheduler",
        ],
        help="Host surface that will consume this scheduler projection.",
    )
    quota_parser.add_argument(
        "-O",
        "--scheduler-owner",
        choices=[
            "host_automation",
            "agent_cli_loop",
            "goal_runtime",
            "outer_controller",
            "none",
        ],
        help="Runtime that owns the next cadence decision.",
    )
    quota_parser.add_argument(
        "-M",
        "--execution-mode",
        choices=["interactive", "isolated_headless", "hosted_automation"],
        help="Execution mode paired with --host-surface and --scheduler-owner.",
    )
    quota_parser.add_argument(
        "--turn-envelope",
        action="store_true",
        help=(
            "For `quota should-run`, return the additive bounded TurnEnvelope view. "
            "The default full decision remains unchanged."
        ),
    )
    quota_parser.add_argument(
        "--turn-instance-id",
        help=(
            "Stable heartbeat trigger id for `quota should-run`. The command "
            "persists one idempotent receipt and, for a quiet no-progress "
            "decision, its stall observation. Reuse the same id on retries."
        ),
    )
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument(
        "--source",
        choices=sorted(VALID_SLOT_SPEND_SOURCES),
        default=DEFAULT_SLOT_SPEND_SOURCE,
        help="Source label for `quota spend-slot`.",
    )
    quota_parser.add_argument("--void-generated-at", help="generated_at timestamp of the quota_slot_spent run to void.")
    quota_parser.add_argument("--reason-summary", help="Public-safe reason for `quota void-slot`.")
    quota_parser.add_argument("--todo-id", help="Monitor todo id for `quota monitor-poll` metadata writeback.")
    quota_parser.add_argument("--target-key", help="Stable monitor target key for `quota monitor-poll` metadata writeback.")
    quota_parser.add_argument("--result-hash", help="Public-safe result hash observed by `quota monitor-poll`.")
    quota_parser.add_argument("--material-change", action="store_true", help="Mark a monitor poll as a material transition instead of unchanged evidence.")
    quota_parser.add_argument("--cadence", help="Monitor cadence used to compute the next due timestamp, e.g. 30m, 2h, or 1d.")
    quota_parser.add_argument("--next-due-at", help="Explicit ISO timestamp for the next monitor poll.")
    quota_parser.add_argument("--next-agent-todo", help="Agent follow-up todo to add when `--material-change` is set.")
    quota_parser.add_argument("--next-user-todo", help="User follow-up todo to add when `--material-change` is set.")
    quota_parser.add_argument(
        "--next-user-task-class",
        choices=["user_gate", "user_action"],
        help=(
            "Required with monitor-poll `--next-user-todo`: user_gate for a "
            "blocking owner decision or user_action for a visible reminder "
            "that must not block the bound agent lane."
        ),
    )
    quota_parser.add_argument("--next-claimed-by", help="Registered agent id to claim the `--next-agent-todo` follow-up.")
    quota_parser.add_argument("--surface", default="codex_app", help="Scheduler surface for scheduler ACK/failure commands; defaults to codex_app.")
    quota_parser.add_argument("--state-key", default="scheduler_hint.codex_app.stateful_backoff", help="Scheduler state key for scheduler ACK/failure commands.")
    quota_parser.add_argument("--applied-rrule", help="RRULE successfully applied by the host before `quota scheduler-ack --execute`.")
    quota_parser.add_argument("--failed-rrule", help="RRULE whose host update failed before `quota scheduler-fail-current --execute`.")
    quota_parser.add_argument(
        "--failure-kind",
        choices=["host_tool_failure", "timeout", "rejected", "unavailable"],
        default="host_tool_failure",
        help="Bounded public-safe failure category for scheduler-fail-current.",
    )
    quota_parser.add_argument("--reset-token", help="Optional reset token to validate before scheduler ack.")
    quota_parser.add_argument("--identity-signature", help="Optional identity signature to validate before scheduler ack.")
    quota_parser.add_argument(
        "--host-match-observed",
        action="store_true",
        help=(
            "A bound scheduler hint has authoritative host proof from a successful "
            "update or matching readback, so persist its exact reset-token/identity "
            "binding."
        ),
    )
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


def _prepare_quota_command_context(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
) -> _QuotaCommandContext:
    command = args.quota_command
    if bool(getattr(args, "turn_envelope", False)) and command != "should-run":
        raise ValueError("--turn-envelope is only valid with `quota should-run`")
    requested_details = set(getattr(args, "include_details", None) or ())
    if requested_details and command not in {"should-run", "monitor-poll"}:
        raise ValueError(
            "--include-detail is only valid with `quota should-run` or "
            "`quota monitor-poll`"
        )
    if requested_details and "all" not in requested_details:
        allowed_details = set(
            QUOTA_MONITOR_POLL_DETAIL_SECTIONS
            if command == "monitor-poll"
            else QUOTA_SHOULD_RUN_DETAIL_SECTIONS
        )
        unsupported_details = sorted(requested_details - allowed_details)
        if unsupported_details:
            raise ValueError(
                f"`quota {command}` does not accept --include-detail "
                f"{', '.join(unsupported_details)}"
            )
    if (
        bool(getattr(args, "include_scheduler_detail", False))
        and command != "should-run"
    ):
        raise ValueError(
            "--include-scheduler-detail is only valid with `quota should-run`"
        )

    heartbeat_turn_id = normalize_turn_instance_id(
        getattr(args, "turn_instance_id", None)
    )
    if heartbeat_turn_id and command != "should-run":
        raise ValueError("--turn-instance-id is only valid with `quota should-run`")
    if heartbeat_turn_id and not args.agent_id:
        raise ValueError("turn-scoped `quota should-run` requires --agent-id")
    if heartbeat_turn_id and bool(args.dry_run):
        raise ValueError("turn-scoped `quota should-run` cannot use --dry-run")

    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    if not scan_roots:
        scan_roots = [Path(args.scan_root).expanduser()]
    status_limit = max(0, args.limit)
    if command in QUOTA_SCHEDULER_COMMANDS:
        status_limit = max(status_limit, AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK)
    runtime_root = resolve_status_projection_cache_runtime_root(
        registry_path=registry_path,
        runtime_root_override=runtime_root_arg,
    )
    operator_inbox_urgency_projector = build_lark_operator_inbox_urgency_projector(
        runtime_root_arg=runtime_root,
    )
    status_goal_id = args.goal_id if command not in {"status", "plan"} else None
    projection_cache_ttl_seconds = int(
        getattr(args, "projection_cache_ttl_seconds", 120)
    )
    status_payload = None
    cache_metadata = None
    if bool(getattr(args, "use_projection_cache", False)):
        status_payload, cache_metadata = load_status_projection_cache(
            registry_path=registry_path,
            runtime_root=runtime_root,
            scan_roots=scan_roots,
            limit=status_limit,
            include_task_graph=False,
            goal_id=status_goal_id,
            max_age_seconds=projection_cache_ttl_seconds,
            available_capabilities=args.available_capabilities,
        )
    if status_payload is None:
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=scan_roots,
            limit=status_limit,
            goal_id=status_goal_id,
            available_capabilities=args.available_capabilities,
        )
        if bool(getattr(args, "write_projection_cache", False)):
            cache_metadata = write_status_projection_cache(
                registry_path=registry_path,
                runtime_root=runtime_root,
                scan_roots=scan_roots,
                limit=status_limit,
                include_task_graph=False,
                goal_id=status_goal_id,
                payload=status_payload,
                max_age_seconds=projection_cache_ttl_seconds,
                available_capabilities=args.available_capabilities,
            )
    elif isinstance(status_payload.get("projection_cache"), dict):
        cache_metadata = dict(status_payload["projection_cache"])

    scheduler_context = (
        _scheduler_execution_context_from_args(args)
        if command in QUOTA_SCHEDULER_COMMANDS
        else None
    )
    validate_quota_command_request(args)
    return _QuotaCommandContext(
        runtime_root=runtime_root,
        scan_roots=scan_roots,
        status_limit=status_limit,
        status_goal_id=status_goal_id,
        status_payload=status_payload,
        cache_metadata=cache_metadata,
        scheduler_context=scheduler_context,
        operator_inbox_urgency_projector=operator_inbox_urgency_projector,
        detail_sections=quota_detail_sections_from_args(args),
        heartbeat_turn_id=heartbeat_turn_id,
    )


def _quota_failure_payload(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    error: Exception,
) -> dict[str, object]:
    command = args.quota_command
    lock_timeout_fields = lock_timeout_error_fields(error)
    if command not in QUOTA_EVENT_KINDS:
        return {
            "ok": False,
            "mode": command,
            "registry": str(registry_path),
            "runtime_root": runtime_root_arg,
            "error": str(error),
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
                    "recommended_action": str(error),
                    "source": "quota",
                }
            ],
            **lock_timeout_fields,
        }

    payload: dict[str, object] = {
        "ok": False,
        "mode": command,
        "goal_id": args.goal_id,
        "decision": "skip",
        "should_run": False,
        "reason": str(error),
        "state": "blocked_health",
        "waiting_on": "codex",
        "status": "quota_collection_failed",
        "source": "quota",
        "recommended_action": (
            "fix quota/status collection before spending automatic compute"
        ),
        **lock_timeout_fields,
    }
    if lock_timeout_fields:
        payload["recommended_action"] = "inspect the lock holder before retrying"
    if command == "monitor-poll":
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
    elif command in {"scheduler-ack", "scheduler-ack-current"}:
        payload.update(
            {
                "agent_id": args.agent_id,
                "surface": args.surface,
                "state_key": args.state_key,
                "applied_rrule": args.applied_rrule,
            }
        )
    elif command == "scheduler-fail-current":
        payload.update(
            {
                "agent_id": args.agent_id,
                "surface": args.surface,
                "state_key": args.state_key,
                "failed_rrule": args.failed_rrule,
                "failure_kind": args.failure_kind,
            }
        )
    return payload


def _quota_renderer(
    args: argparse.Namespace,
) -> Callable[[dict[str, object]], str]:
    command = args.quota_command
    if bool(getattr(args, "turn_envelope", False)):
        return render_turn_envelope_markdown
    return {
        "should-run": render_quota_should_run_markdown,
        "monitor-poll": render_quota_monitor_poll_markdown,
        "scheduler-ack": render_quota_scheduler_ack_markdown,
        "scheduler-ack-current": render_quota_scheduler_ack_markdown,
        "scheduler-fail-current": render_quota_scheduler_failure_markdown,
        "spend-slot": render_quota_slot_preview_markdown,
        "void-slot": render_quota_slot_preview_markdown,
    }.get(command, render_quota_markdown)


def handle_quota_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    append_cli_rollout_event: RolloutEventAppender,
) -> int:
    heartbeat_turn_id: str | None = None
    heartbeat_receipt_existing: dict[str, object] | None = None
    heartbeat_receipt_ready = False
    heartbeat_stall_observation = "not_evaluated"
    detail_sections: frozenset[str] = frozenset()
    try:
        context = _prepare_quota_command_context(
            args,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
        )
        heartbeat_turn_id = context.heartbeat_turn_id
        detail_sections = context.detail_sections
        runtime_root = context.runtime_root
        scan_roots = context.scan_roots
        status_limit = context.status_limit
        status_goal_id = context.status_goal_id
        status_payload = context.status_payload
        cache_metadata = context.cache_metadata
        scheduler_context = context.scheduler_context
        operator_inbox_urgency_projector = context.operator_inbox_urgency_projector
        if args.quota_command == "should-run":
            payload = build_live_quota_should_run_decision(
                status_payload,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                include_scheduler_detail="scheduler" in detail_sections,
                codex_app_current_rrule=args.codex_app_current_rrule,
                registry_path=registry_path,
                runtime_root=runtime_root,
                host_observation_resolver=resolve_codex_app_automation_rrule,
                scheduler_execution_context=scheduler_context,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            )
            if heartbeat_turn_id:
                heartbeat_receipt_existing = find_heartbeat_receipt(
                    runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    turn_instance_id=heartbeat_turn_id,
                )
                if heartbeat_receipt_existing:
                    details = (
                        heartbeat_receipt_existing.get("details")
                        if isinstance(heartbeat_receipt_existing.get("details"), Mapping)
                        else {}
                    )
                    heartbeat_stall_observation = str(
                        details.get("stall_observation") or "not_applicable"
                    )
                    heartbeat_receipt_ready = True
                else:
                    existing_stall = find_quota_monitor_poll_turn(
                        runtime_root,
                        goal_id=args.goal_id,
                        agent_id=args.agent_id,
                        turn_instance_id=heartbeat_turn_id,
                    )
                    if (
                        payload.get("effective_action") == "monitor_quiet_skip"
                        or existing_stall is not None
                    ):
                        poll = record_quota_monitor_poll(
                            status_payload,
                            goal_id=args.goal_id,
                            registry_path=registry_path,
                            execute=True,
                            source="heartbeat",
                            agent_id=args.agent_id,
                            available_capabilities=args.available_capabilities,
                            turn_instance_id=heartbeat_turn_id,
                            scheduler_execution_context=scheduler_context,
                            operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                        )
                        if not poll.get("ok"):
                            raise RuntimeError(
                                "heartbeat stall observation writeback failed: "
                                f"{poll.get('reason') or 'missing follow-up quota decision'}"
                            )
                        status_payload = collect_status(
                            registry_path=registry_path,
                            runtime_root_override=runtime_root_arg,
                            scan_roots=scan_roots,
                            limit=status_limit,
                            goal_id=status_goal_id,
                            available_capabilities=args.available_capabilities,
                        )
                        payload = build_live_quota_should_run_decision(
                            status_payload,
                            goal_id=args.goal_id,
                            agent_id=args.agent_id,
                            available_capabilities=args.available_capabilities,
                            include_scheduler_detail="scheduler" in detail_sections,
                            codex_app_current_rrule=args.codex_app_current_rrule,
                            registry_path=registry_path,
                            runtime_root=runtime_root,
                            host_observation_resolver=resolve_codex_app_automation_rrule,
                            scheduler_execution_context=scheduler_context,
                            operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                        )
                        cache_metadata = None
                        heartbeat_stall_observation = (
                            "replayed" if poll.get("replayed") else "appended"
                        )
                        payload["heartbeat_stall_writeback"] = {
                            "turn_instance_id": heartbeat_turn_id,
                            "status": heartbeat_stall_observation,
                            "generated_at": poll.get("generated_at"),
                        }
                    else:
                        heartbeat_stall_observation = "not_applicable"
                    heartbeat_receipt_ready = True
        elif args.quota_command == "monitor-poll":
            payload = record_quota_monitor_poll(
                status_payload,
                goal_id=args.goal_id,
                registry_path=registry_path,
                execute=bool(args.execute),
                source=args.source,
                reason_summary=args.reason_summary,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                todo_id=args.todo_id,
                target_key=args.target_key,
                result_hash=args.result_hash,
                material_change=bool(args.material_change),
                cadence=args.cadence,
                next_due_at=args.next_due_at,
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_user_task_class=args.next_user_task_class,
                next_claimed_by=args.next_claimed_by,
                scheduler_execution_context=scheduler_context,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                status_reloader=lambda: collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=scan_roots,
                    limit=status_limit,
                    goal_id=status_goal_id,
                    available_capabilities=args.available_capabilities,
                ),
            )
        elif args.quota_command in {"scheduler-ack", "scheduler-ack-current"}:
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
                host_match_observed=bool(getattr(args, "host_match_observed", False)),
                scheduler_execution_context=scheduler_context,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            )
        elif args.quota_command == "scheduler-fail-current":
            observed_rrule = str(args.codex_app_current_rrule or "").strip()
            if not observed_rrule:
                host_observation = resolve_codex_app_automation_rrule(
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                )
                if host_observation.get("available") is True:
                    observed_rrule = str(host_observation.get("rrule") or "")
            failure_decision = build_quota_should_run(
                status_payload,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                codex_app_current_rrule=observed_rrule,
                scheduler_execution_context=scheduler_context,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            )
            payload = record_quota_scheduler_failure_for_decision(
                failure_decision,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                execute=bool(args.execute),
                surface=args.surface,
                state_key=args.state_key,
                failed_rrule=args.failed_rrule,
                observed_host_rrule=observed_rrule,
                failure_kind=args.failure_kind,
            )
        elif args.quota_command == "spend-slot":
            payload = spend_quota_slot(
                status_payload,
                goal_id=args.goal_id,
                slots=args.slots,
                execute=bool(args.execute),
                source=args.source,
                agent_id=args.agent_id,
                available_capabilities=args.available_capabilities,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            )
        elif args.quota_command == "void-slot":
            payload = void_quota_slot(
                status_payload,
                goal_id=args.goal_id,
                voided_run_generated_at=args.void_generated_at,
                execute=bool(args.execute),
                source=args.source,
                reason_summary=args.reason_summary,
                agent_id=args.agent_id,
                operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            )
        else:
            payload = build_quota_plan(status_payload, mode=args.quota_command)
        if cache_metadata:
            payload["status_projection_cache"] = cache_metadata
    except Exception as exc:
        payload = _quota_failure_payload(
            args,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            error=exc,
        )
    should_log_quota = args.quota_command in QUOTA_EVENT_KINDS and (
        args.quota_command == "should-run"
        or (payload.get("ok") and bool(payload.get("appended")))
    )
    if should_log_quota:
        rollout_details = {
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
        }
        if heartbeat_turn_id and args.quota_command == "should-run":
            if not heartbeat_receipt_ready:
                prior_reason = str(payload.get("reason") or "").strip()
                fail_heartbeat_receipt(
                    payload,
                    turn_instance_id=heartbeat_turn_id,
                    stall_observation=heartbeat_stall_observation,
                    reason=(
                        "heartbeat receipt was not committed because quota or stall "
                        "writeback did not complete"
                        + (f": {prior_reason}" if prior_reason else "")
                    ),
                )
            elif heartbeat_receipt_existing:
                payload["heartbeat_receipt"] = heartbeat_receipt_view(
                    heartbeat_receipt_existing,
                    turn_instance_id=heartbeat_turn_id,
                    status="replayed",
                )
                payload["rollout_event"] = {
                    "schema_version": heartbeat_receipt_existing.get("schema_version"),
                    "event_id": heartbeat_receipt_existing.get("event_id"),
                    "event_kind": heartbeat_receipt_existing.get("event_kind"),
                    "recorded_at": heartbeat_receipt_existing.get("recorded_at"),
                    "status": heartbeat_receipt_existing.get("status"),
                    "appended": False,
                }
            else:
                rollout_details.update(
                    {
                        "turn_instance_id": heartbeat_turn_id,
                        "stall_observation": heartbeat_stall_observation,
                    }
                )
                append_cli_rollout_event(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    event_kind="quota_should_run",
                    agent_id=args.agent_id,
                    run_id=heartbeat_turn_id,
                    status=str(
                        payload.get("effective_action")
                        or payload.get("decision")
                        or "should-run"
                    ),
                    summary=(
                        "heartbeat quota receipt committed for "
                        f"turn={heartbeat_turn_id} stall={heartbeat_stall_observation}"
                    ),
                    details=rollout_details,
                    allow_failed=True,
                    idempotency_fields=["goal_id", "event_kind", "agent_id", "run_id"],
                )
                receipt = find_heartbeat_receipt(
                    runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    turn_instance_id=heartbeat_turn_id,
                )
                if receipt:
                    rollout_event = (
                        payload.get("rollout_event")
                        if isinstance(payload.get("rollout_event"), Mapping)
                        else {}
                    )
                    payload["heartbeat_receipt"] = heartbeat_receipt_view(
                        receipt,
                        turn_instance_id=heartbeat_turn_id,
                        status="committed" if rollout_event.get("appended") else "replayed",
                    )
                else:
                    fail_heartbeat_receipt(
                        payload,
                        turn_instance_id=heartbeat_turn_id,
                        stall_observation=heartbeat_stall_observation,
                        reason=(
                            "heartbeat receipt append could not be read back; retry "
                            "quota should-run with the same --turn-instance-id"
                        ),
                    )
        else:
            append_cli_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                event_kind=QUOTA_EVENT_KINDS[args.quota_command],
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
                details=rollout_details,
                allow_failed=args.quota_command == "should-run",
            )
    if bool(getattr(args, "turn_envelope", False)):
        payload = build_turn_envelope(
            payload,
            scheduler_execution_context=scheduler_context,
        )
    elif args.quota_command == "should-run":
        payload = compact_quota_should_run_cli_payload(
            payload,
            include_todo_summary_detail="agent-todos" in detail_sections,
            include_user_todo_summary_detail="user-todos" in detail_sections,
            include_goal_boundary_detail="goal-boundary" in detail_sections,
            include_vision_detail="vision" in detail_sections,
        )
    elif args.quota_command == "monitor-poll":
        payload = compact_quota_monitor_poll_cli_payload(
            payload,
            include_decision_detail="decisions" in detail_sections,
        )
    print_payload(payload, args.format, _quota_renderer(args))
    return 0 if payload.get("ok") else 1
