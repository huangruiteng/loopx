from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ..control_plane.quota.cli_projection import (
    compact_quota_monitor_poll_cli_payload,
    compact_quota_should_run_cli_payload,
)
from ..control_plane.quota.error_codes import quota_error_code
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
from ..control_plane.quota.settlement_cli import (
    attach_spend_settlement_result,
    quota_rollout_details,
    quota_rollout_todo_id,
    render_existing_heartbeat_receipt_payload,
    reconcile_existing_heartbeat_receipt_for_turn,
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
    QUOTA_MONITOR_POLL_DETAIL_SECTIONS,
    QUOTA_SHOULD_RUN_DETAIL_SECTIONS,
    quota_detail_sections_from_args,
    validate_quota_command_request,
)
from .quota_registration import register_quota_command as register_quota_command
from .task_lease import (
    hold_cli_turn_effect_fence,
    turn_effect_fence_requested,
    turn_effect_key_from_args,
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
    if heartbeat_turn_id and command not in {"should-run", "spend-slot"}:
        raise ValueError(
            "--turn-instance-id is only valid with `quota should-run` or "
            "`quota spend-slot`"
        )
    if heartbeat_turn_id and not args.agent_id:
        raise ValueError("turn-scoped quota settlement requires --agent-id")
    if heartbeat_turn_id and command == "should-run" and bool(args.dry_run):
        raise ValueError("turn-scoped `quota should-run` cannot use --dry-run")
    if turn_effect_fence_requested(args) and command != "spend-slot":
        raise ValueError(
            "Turn effect fencing is only valid with `quota spend-slot`"
        )

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
    scheduler_context = (
        _scheduler_execution_context_from_args(args)
        if command in QUOTA_SCHEDULER_COMMANDS
        else None
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
            "error_code": quota_error_code(error),
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
        "error_code": quota_error_code(error),
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
    heartbeat_receipt_existing_status = "replayed"
    heartbeat_receipt_existing_appended = False
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
                    (
                        heartbeat_receipt_existing,
                        heartbeat_receipt_existing_status,
                        heartbeat_receipt_existing_appended,
                        heartbeat_stall_observation,
                        heartbeat_receipt_ready,
                    ) = reconcile_existing_heartbeat_receipt_for_turn(
                        payload,
                        args,
                        runtime_root=runtime_root,
                        turn_instance_id=heartbeat_turn_id,
                        existing=heartbeat_receipt_existing,
                    )
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
                next_action_kind=args.next_action_kind,
                next_task_repository=args.next_task_repository,
                next_required_capabilities=args.next_required_capabilities,
                next_continuation_policy=args.next_continuation_policy,
                next_target_key=args.next_target_key,
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
            with hold_cli_turn_effect_fence(
                args,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                owner=args.agent_id,
            ):
                spend_status = (
                    collect_status(
                        registry_path=registry_path,
                        runtime_root_override=runtime_root_arg,
                        scan_roots=scan_roots,
                        limit=status_limit,
                        goal_id=status_goal_id,
                        available_capabilities=args.available_capabilities,
                    )
                    if turn_effect_fence_requested(args)
                    else status_payload
                )
                payload = spend_quota_slot(
                    spend_status,
                    goal_id=args.goal_id,
                    slots=args.slots,
                    execute=bool(args.execute),
                    source=args.source,
                    agent_id=args.agent_id,
                    available_capabilities=args.available_capabilities,
                    operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                    todo_id=args.todo_id,
                    turn_instance_id=heartbeat_turn_id,
                    turn_effect_key=turn_effect_key_from_args(args),
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
    except Exception as exc:  # noqa: BLE001 - CLI fail-safe boundary; error_code is typed below.
        payload = _quota_failure_payload(
            args,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            error=exc,
        )
    should_log_quota = args.quota_command in QUOTA_EVENT_KINDS and (
        args.quota_command == "should-run"
        or (
            payload.get("ok")
            and (
                bool(payload.get("appended"))
                or bool(payload.get("receipt_repair_required"))
            )
        )
    )
    if should_log_quota:
        rollout_todo_id = quota_rollout_todo_id(payload, args)
        rollout_details = quota_rollout_details(
            payload,
            args,
            todo_id=rollout_todo_id,
        )
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
                render_existing_heartbeat_receipt_payload(
                    payload,
                    receipt=heartbeat_receipt_existing,
                    turn_instance_id=heartbeat_turn_id,
                    status=heartbeat_receipt_existing_status,
                    appended=heartbeat_receipt_existing_appended,
                )
            else:
                rollout_details.update(
                    {
                        "turn_instance_id": heartbeat_turn_id,
                        "stall_observation": heartbeat_stall_observation,
                        "settlement_effect_id": (
                            f"{args.goal_id}:{args.agent_id}:{rollout_todo_id}:"
                            f"{heartbeat_turn_id}"
                            if rollout_todo_id
                            else ""
                        ),
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
                    rollout_event_value = payload.get("rollout_event")
                    rollout_event: Mapping[str, object] = (
                        rollout_event_value
                        if isinstance(rollout_event_value, Mapping)
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
                todo_id=rollout_todo_id,
                run_id=(
                    heartbeat_turn_id
                    if args.quota_command == "spend-slot"
                    else None
                ),
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
            if args.quota_command == "spend-slot" and heartbeat_turn_id:
                attach_spend_settlement_result(
                    payload,
                    runtime_root=runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    todo_id=rollout_todo_id,
                    turn_instance_id=heartbeat_turn_id,
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
