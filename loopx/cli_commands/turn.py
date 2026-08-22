from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..cli_rollout import append_cli_rollout_event
from ..capabilities.explore.composition_frontier import (
    project_live_explore_composition_frontier,
)
from ..control_plane.quota.live_decision import build_live_quota_should_run_decision
from ..control_plane.quota.heartbeat_receipt import (
    ensure_turn_heartbeat_settlement_receipt,
)
from ..control_plane.quota.settlement import (
    SettlementIdentity,
    SettlementStepKind,
    find_settlement_spend_run,
    find_settlement_step_event,
    find_settlement_writeback,
)
from ..control_plane.quota.turn_envelope import build_turn_envelope
from ..control_plane.runtime.status_projection_cache import (
    resolve_status_projection_cache_runtime_root,
)
from ..control_plane.todos.durable_completion import (
    project_durable_completion_intent,
    project_durable_completion_outcome,
    project_durable_terminal_completion_readback,
    read_persisted_todo_record,
    read_persisted_todo_record_with_source,
)
from ..control_plane.scheduler.execution_context import (
    scheduler_execution_context_for_turn,
)
from ..control_plane.turn_driver import (
    LOOPX_TURN_EXECUTION_SCHEMA_VERSION,
    LOOPX_TURN_JOURNAL_INSPECTION_SCHEMA_VERSION,
    LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
    build_loopx_turn_command_validator,
    build_loopx_turn_plan,
    codex_cli_session_binding,
    inspect_loopx_turn_journal,
    load_loopx_turn_plan_from_journal,
    run_codex_cli_host,
    run_loopx_turn_once,
    selected_turn_todo,
)
from ..paths import default_public_scan_root
from ..quota import spend_quota_slot
from ..state_refresh import refresh_state_run
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status
from ..todos import complete_goal_todo, resolve_todo_state_path, update_goal_todo
from .lark_inbox import build_lark_operator_inbox_urgency_projector

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_turn_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "turn",
        help="Plan, run, or inspect one governed external-host Turn.",
    )
    command_sub = parser.add_subparsers(dest="turn_command", required=True)
    inspect_journal = command_sub.add_parser(
        "inspect-journal",
        help="Inspect one canonical fenced Turn journal without executing effects.",
    )
    add_subcommand_format(inspect_journal)
    inspect_journal.add_argument("--goal-id", required=True)
    inspect_journal.add_argument("--agent-id", required=True)
    inspect_journal.add_argument("--turn-key", required=True)

    plan = command_sub.add_parser(
        "plan",
        help="Build one typed read-only host decision without launching or writing.",
    )
    add_subcommand_format(plan)
    _add_turn_decision_arguments(plan, default_host="codex-cli")
    plan.add_argument(
        "--include-transaction-detail",
        action="store_true",
        help="Include session binding and transaction receipt planning detail.",
    )
    plan.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material.",
    )
    plan.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable.",
    )
    plan.add_argument("--limit", type=int, default=5)

    run_once = command_sub.add_parser(
        "run-once",
        help=(
            "Run one explicit isolated generic host command and commit only a "
            "validated public-safe result."
        ),
        description=(
            "Run one governed Turn: LoopX decides, a host adapter invokes an "
            "agent CLI, an independent validator proves the postcondition, and "
            "LoopX commits only a passing result."
        ),
        epilog=(
            "A Trae, Codex, or other conversational CLI normally needs a thin "
            "adapter: read one typed request from stdin and emit one typed result "
            "to stdout. The validation command receives that normalized result "
            "on stdin and must independently check the real postcondition. Only "
            "eligible interrupted sessions resume; terminal startup or missing-session "
            "failures start a fresh host session on the next Turn."
        ),
    )
    add_subcommand_format(run_once)
    _add_turn_decision_arguments(
        run_once,
        default_host="generic-cli",
        host_choices=["codex-cli", "generic-cli"],
        execution_mode_choices=["isolated-headless"],
        default_execution_mode="isolated-headless",
    )
    run_once.add_argument("--project", required=True)
    run_once.add_argument(
        "--host-command-json",
        "--host-adapter-command-json",
        dest="host_command_json",
        help=(
            "JSON argv array for a typed generic host adapter. The adapter reads "
            "the Turn request from stdin and emits one result JSON object; shell "
            "parsing is never used."
        ),
    )
    run_once.add_argument(
        "--validation-command-json",
        help=(
            "Trusted JSON argv array for independent task/postcondition validation. "
            "The normalized host result is provided on stdin; shell parsing is never used."
        ),
    )
    run_once.add_argument(
        "--validation-timeout-seconds",
        type=float,
        default=30.0,
        help="Timeout for the independent validation command.",
    )
    run_once.add_argument(
        "--validation-failure-kind",
        choices=["repair_required", "replan_required"],
        default="repair_required",
        help="Typed recovery disposition when the independent validator rejects the result.",
    )
    run_once.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable used by the built-in codex-cli host.",
    )
    run_once.add_argument("--codex-model")
    run_once.add_argument(
        "--codex-sandbox",
        choices=["read-only", "workspace-write"],
        default="read-only",
        help="Sandbox for a new Codex CLI session; resume preserves its original session policy.",
    )
    run_once.add_argument("--timeout-seconds", type=float, default=120.0)
    run_once.add_argument(
        "--retry-failed-turn",
        action="store_true",
        help="Retry a failed transaction from its last side-effect-safe phase.",
    )
    run_once.add_argument(
        "--resume-turn-key",
        help="Resume the exact journaled transaction without recomputing its plan.",
    )
    run_once.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Keep disposable fixture writeback out of the shared global registry.",
    )
    run_once.add_argument(
        "--execute",
        action="store_true",
        help="Invoke the host and commit validated writeback/quota effects.",
    )
    run_once.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material.",
    )
    run_once.add_argument("--scan-path", action="append", default=[])
    run_once.add_argument("--limit", type=int, default=5)


def _add_turn_decision_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_host: str,
    host_choices: list[str] | None = None,
    execution_mode_choices: list[str] | None = None,
    default_execution_mode: str = "interactive-visible",
) -> None:
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--host",
        choices=host_choices or ["codex-cli", "claude-code", "generic-cli"],
        default=default_host,
    )
    parser.add_argument(
        "--execution-mode",
        choices=execution_mode_choices or ["interactive-visible", "isolated-headless"],
        default=default_execution_mode,
    )
    parser.add_argument(
        "--scheduler-owner",
        choices=["host_automation", "agent_cli_loop", "outer_controller", "none"],
        help=(
            "Cadence owner; defaults to outer_controller for generic-cli and "
            "agent_cli_loop otherwise."
        ),
    )
    parser.add_argument(
        "--turn-instance-id",
        help=(
            "Caller-stable public-safe identity for one logical Turn. Reusing the "
            "same id replays idempotently; use a new id for a new Turn with the "
            "same semantic action."
        ),
    )
    parser.add_argument(
        "--resume-goal-id",
        help="Goal identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--resume-agent-id",
        help="Agent identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--resume-todo-id",
        help="Todo identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
    )


def _render_loopx_turn_plan_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        error = payload.get("error") or "invalid TurnEnvelope contract"
        return f"LoopX Turn plan failed: {error}"
    host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    return "\n".join(
        [
            "# LoopX Turn Plan",
            f"- host: {host.get('kind')}",
            f"- execution_mode: {host.get('execution_mode')}",
            f"- route: {route.get('kind')}",
            f"- would_invoke_host: {route.get('would_invoke_host')}",
            "- side_effects: none",
        ]
    )


def _render_loopx_turn_execution_markdown(payload: dict[str, object]) -> str:
    effects = payload.get("effects") if isinstance(payload.get("effects"), dict) else {}
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    validation = (
        payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    )
    return "\n".join(
        [
            "# LoopX Turn Run Once",
            f"- status: {payload.get('status')}",
            f"- result_kind: {payload.get('result_kind')}",
            f"- validation: {validation.get('status')}",
            f"- recovery_kind: {validation.get('recovery_kind')}",
            f"- next_phase: {receipt.get('next_phase')}",
            f"- host_invoked: {effects.get('host_invoked')}",
            f"- state_written: {effects.get('state_written')}",
            f"- quota_spent: {effects.get('quota_spent')}",
        ]
    )


def _render_loopx_turn_journal_inspection_markdown(
    payload: dict[str, object],
) -> str:
    if not payload.get("ok"):
        error = payload.get("error") or "Turn journal inspection failed"
        return f"LoopX Turn journal inspection failed: {error}"
    completed_phases = payload.get("completed_phases")
    violations = payload.get("violations")
    return "\n".join(
        [
            "# LoopX Turn Journal Inspection",
            f"- decision: {payload.get('decision')}",
            f"- journal_status: {payload.get('journal_status')}",
            f"- replay_legal: {payload.get('replay_legal')}",
            f"- goal_matches: {payload.get('goal_matches')}",
            f"- owner_matches: {payload.get('owner_matches')}",
            f"- turn_key_matches: {payload.get('turn_key_matches')}",
            (
                "- phases_form_ordered_prefix: "
                f"{payload.get('phases_form_ordered_prefix')}"
            ),
            "- completed_phases: "
            + (
                ", ".join(str(value) for value in completed_phases)
                if isinstance(completed_phases, list) and completed_phases
                else "none"
            ),
            f"- tombstone_retained: {payload.get('tombstone_retained')}",
            "- violations: "
            + (
                ", ".join(str(value) for value in violations)
                if isinstance(violations, list) and violations
                else "none"
            ),
            "- effects: none",
        ]
    )


def handle_turn_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "turn":
        return None
    if args.turn_command == "inspect-journal":
        try:
            runtime_root = resolve_status_projection_cache_runtime_root(
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
            )
            payload = inspect_loopx_turn_journal(
                runtime_root,
                goal_id=args.goal_id,
                agent_id=args.agent_id,
                turn_key=args.turn_key,
            )
        except Exception as exc:  # noqa: BLE001 - typed CLI failure boundary
            payload = {
                "ok": False,
                "schema_version": LOOPX_TURN_JOURNAL_INSPECTION_SCHEMA_VERSION,
                "error": str(exc),
                "effects": [],
            }
        print_payload(
            payload,
            output_format(args),
            _render_loopx_turn_journal_inspection_markdown,
        )
        return 0 if payload.get("ok") else 1
    try:
        scan_roots = [Path(item).expanduser() for item in args.scan_path]
        if not scan_roots:
            scan_roots = [Path(args.scan_root).expanduser()]
        runtime_root = resolve_status_projection_cache_runtime_root(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
        )
        operator_inbox_urgency_projector = build_lark_operator_inbox_urgency_projector(
            runtime_root_arg=runtime_root,
        )
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=scan_roots,
            limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
            goal_id=args.goal_id,
            available_capabilities=args.available_capabilities,
        )
        scheduler_context = scheduler_execution_context_for_turn(
            host=args.host,
            execution_mode=args.execution_mode,
            scheduler_owner=args.scheduler_owner,
        )
        decision = build_live_quota_should_run_decision(
            status_payload,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            available_capabilities=args.available_capabilities,
            include_scheduler_detail=False,
            codex_app_current_rrule=None,
            registry_path=registry_path,
            runtime_root=runtime_root,
            route_source="loopx_turn_plan",
            scheduler_execution_context=scheduler_context,
            operator_inbox_urgency_projector=operator_inbox_urgency_projector,
            bounded_research_frontier_projector=(
                project_live_explore_composition_frontier
            ),
        )
        resume_identity = {
            "goal_id": args.resume_goal_id,
            "agent_id": args.resume_agent_id,
            "todo_id": args.resume_todo_id,
        }
        supplied_resume_fields = [
            field for field, value in resume_identity.items() if value is not None
        ]
        if supplied_resume_fields and len(supplied_resume_fields) != len(
            resume_identity
        ):
            raise ValueError(
                "resume planning requires --resume-goal-id, --resume-agent-id, "
                "and --resume-todo-id together"
            )
        session_binding = None
        if supplied_resume_fields:
            session_binding = {
                "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
                **resume_identity,
            }
        turn_envelope = build_turn_envelope(
            decision,
            scheduler_execution_context=scheduler_context,
        )
        if (
            args.turn_command == "run-once"
            and args.host == "codex-cli"
            and not supplied_resume_fields
        ):
            session_binding = codex_cli_session_binding(runtime_root, turn_envelope)
        payload = build_loopx_turn_plan(
            turn_envelope,
            host=args.host,
            execution_mode=args.execution_mode,
            scheduler_owner=args.scheduler_owner,
            session_binding=session_binding,
            turn_instance_id=args.turn_instance_id,
        )
        if args.turn_command == "plan":
            if not args.include_transaction_detail:
                payload.pop("session", None)
                payload.pop("transaction", None)
                boundary = payload.get("boundary")
                if isinstance(boundary, dict):
                    boundary.pop("opaque_session_handle_omitted", None)
            else:
                # The typed settlement plan is used by validation and
                # execution, but is not part of the agent-facing CLI contract.
                transaction = payload.get("transaction")
                if isinstance(transaction, dict):
                    transaction.pop("settlement_plan", None)
        elif args.turn_command == "run-once":
            if args.resume_turn_key:
                if args.turn_instance_id:
                    raise ValueError(
                        "--resume-turn-key cannot be combined with --turn-instance-id"
                    )
                if supplied_resume_fields:
                    raise ValueError(
                        "--resume-turn-key cannot be combined with host session identity flags"
                    )
                payload = load_loopx_turn_plan_from_journal(
                    runtime_root,
                    goal_id=args.goal_id,
                    turn_key=args.resume_turn_key,
                )
                envelope = (
                    payload.get("turn_envelope")
                    if isinstance(payload.get("turn_envelope"), dict)
                    else {}
                )
                if envelope.get("agent_id") != args.agent_id:
                    raise ValueError(
                        "LoopX Turn resume journal belongs to another agent"
                    )
            project = Path(args.project).expanduser().resolve()
            planned_host = (
                payload.get("host") if isinstance(payload.get("host"), dict) else {}
            )
            if planned_host.get("kind") != args.host:
                raise ValueError("--host must match the journaled LoopX Turn plan")
            if args.host == "generic-cli":
                if not args.host_command_json:
                    raise ValueError(
                        "generic-cli requires --host-adapter-command-json "
                        "(alias --host-command-json)"
                    )
                raw_argv = json.loads(args.host_command_json)
                if not isinstance(raw_argv, list) or not all(
                    isinstance(item, str) for item in raw_argv
                ):
                    raise ValueError(
                        "--host-adapter-command-json must be a JSON string array"
                    )
            else:
                if args.host_command_json:
                    raise ValueError("codex-cli does not accept --host-command-json")
                raw_argv = None
            if args.validation_command_json:
                raw_validation_argv = json.loads(args.validation_command_json)
                if not isinstance(raw_validation_argv, list) or not all(
                    isinstance(item, str) for item in raw_validation_argv
                ):
                    raise ValueError(
                        "--validation-command-json must be a JSON string array"
                    )
                task_validator = build_loopx_turn_command_validator(
                    raw_validation_argv,
                    project=project,
                    timeout_seconds=args.validation_timeout_seconds,
                    failure_recovery_kind=args.validation_failure_kind,
                )
            else:
                task_validator = None
            envelope = (
                payload.get("turn_envelope")
                if isinstance(payload.get("turn_envelope"), dict)
                else {}
            )
            selected_todo = selected_turn_todo(envelope)
            transaction = (
                payload.get("transaction")
                if isinstance(payload.get("transaction"), Mapping)
                else {}
            )
            settlement_plan = (
                transaction.get("settlement_plan")
                if isinstance(transaction.get("settlement_plan"), Mapping)
                else {}
            )
            raw_identity = (
                settlement_plan.get("identity")
                if isinstance(settlement_plan.get("identity"), Mapping)
                else {}
            )
            settlement_identity = SettlementIdentity(
                goal_id=str(raw_identity.get("goal_id") or args.goal_id),
                agent_id=str(raw_identity.get("agent_id") or args.agent_id),
                todo_id=str(
                    raw_identity.get("todo_id") or selected_todo.get("todo_id") or ""
                ),
                turn_instance_id=str(
                    raw_identity.get("turn_instance_id")
                    or transaction.get("turn_instance_id")
                    or transaction.get("turn_key")
                    or ""
                ),
            )
            persisted_effect_id = str(raw_identity.get("effect_id") or "")
            if (
                persisted_effect_id
                and persisted_effect_id != settlement_identity.effect_id
            ):
                raise ValueError("Turn settlement identity effect_id is inconsistent")
            if args.execute:
                ensure_turn_heartbeat_settlement_receipt(
                    runtime_root,
                    settlement_identity,
                )

            def require_effect_ref(
                effect_ref: str,
                step_kind: SettlementStepKind,
            ) -> None:
                expected = f"{settlement_identity.effect_id}#{step_kind.value}"
                if effect_ref != expected:
                    raise ValueError(
                        f"{step_kind.value} effect ref does not match Turn identity"
                    )

            def append_settlement_event(
                effect_payload: Mapping[str, object],
                *,
                event_kind: str,
                status: str,
                details: Mapping[str, object],
            ) -> None:
                event_payload = {
                    **dict(effect_payload),
                    "ok": True,
                    "goal_id": args.goal_id,
                    "runtime_root": str(runtime_root),
                }
                append_cli_rollout_event(
                    event_payload,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    event_kind=event_kind,
                    agent_id=settlement_identity.agent_id,
                    todo_id=settlement_identity.todo_id,
                    run_id=settlement_identity.turn_instance_id,
                    status=status,
                    summary=f"Turn settlement {event_kind} recorded",
                    details={
                        **dict(details),
                        "settlement_effect_id": settlement_identity.effect_id,
                    },
                    idempotency_fields=[
                        "goal_id",
                        "event_kind",
                        "agent_id",
                        "todo_id",
                        "run_id",
                        *(("status",) if event_kind == "todo_complete" else ()),
                    ],
                )
                if event_payload.get("rollout_event_log_error"):
                    raise OSError(f"failed to persist {event_kind} settlement receipt")

            writeback_contract = (
                envelope.get("writeback")
                if isinstance(envelope.get("writeback"), dict)
                else {}
            )
            delivery_workspace_path = (
                project
                if isinstance(
                    writeback_contract.get("delivery_workspace_causality"), dict
                )
                else None
            )

            def writeback(
                result: dict[str, object],
                *,
                completion_todo_id: str | None = None,
                completion_turn_key: str | None = None,
                effect_ref: str,
            ) -> dict[str, object]:
                require_effect_ref(effect_ref, SettlementStepKind.DURABLE_WRITEBACK)
                # The host workspace is execution context, not state authority.
                state_project = None
                result_kind = str(result.get("result_kind") or "")
                if result_kind in {"repair_required", "replan_required"}:
                    todo_id = str(selected_todo.get("todo_id") or "")
                    if not todo_id:
                        raise ValueError(
                            f"{result_kind} requires one selected todo for typed writeback"
                        )
                    update_goal_todo(
                        registry_path=registry_path,
                        goal_id=args.goal_id,
                        todo_id=todo_id,
                        role="agent",
                        note=str(result.get("summary") or result["classification"]),
                        evidence=f"LoopX Turn {result_kind}: {result['next_action']}",
                        agent_id=args.agent_id,
                        project=state_project,
                        dry_run=False,
                    )
                refresh = refresh_state_run(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    project=state_project,
                    state_file=None,
                    classification=str(result["classification"]),
                    recommended_action=str(result["recommended_action"]),
                    next_action=str(result["next_action"]),
                    delivery_batch_scale=str(result["delivery_batch_scale"]),
                    delivery_outcome=str(result["delivery_outcome"]),
                    delivery_workspace_path=delivery_workspace_path,
                    todo_id=settlement_identity.todo_id,
                    turn_instance_id=settlement_identity.turn_instance_id,
                    agent_id=args.agent_id,
                    progress_scope="goal",
                    autonomous_replan_recorded=result_kind == "replan_required",
                    agent_vision_packet=(
                        dict(result["agent_vision"])
                        if isinstance(result.get("agent_vision"), dict)
                        else None
                    ),
                    vision_unchanged_reason=(
                        str(result.get("vision_unchanged_reason") or "") or None
                    ),
                    completion_todo_id=completion_todo_id,
                    completion_turn_key=completion_turn_key,
                    dry_run=False,
                    sync_global=not bool(args.no_global_sync),
                )
                if refresh.get("ok") and (
                    refresh.get("appended")
                    or refresh.get("idempotent_replay")
                    or refresh.get("receipt_repair_required")
                ):
                    append_settlement_event(
                        refresh,
                        event_kind="refresh_state",
                        status="appended",
                        details={"command": "turn run-once"},
                    )
                return refresh

            def completion_intent(_result: dict[str, object]) -> dict[str, object]:
                todo_id = str(selected_todo.get("todo_id") or "")
                if not todo_id:
                    raise ValueError(
                        "validated_completion requires one selected todo for lifecycle writeback"
                    )
                _state_project, state_file = resolve_todo_state_path(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    project=None,
                    state_file=None,
                )
                durable_todo, existing_todo_ids = read_persisted_todo_record(
                    state_file,
                    todo_id=todo_id,
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                )
                return project_durable_completion_intent(
                    todo=durable_todo,
                    expected_todo_id=todo_id,
                    existing_todo_ids=existing_todo_ids,
                )

            def todo_completion(
                result: dict[str, object],
                *,
                effect_ref: str,
            ) -> dict[str, object]:
                todo_id = str(selected_todo.get("todo_id") or "")
                if not todo_id:
                    raise ValueError(
                        "validated_completion requires one selected todo for lifecycle writeback"
                    )
                completion = complete_goal_todo(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    todo_id=todo_id,
                    role="agent",
                    completion_turn_key=settlement_identity.turn_instance_id,
                    evidence=(
                        "LoopX Turn validated completion: "
                        + str(result.get("summary") or result["classification"])
                    ),
                    note=str(result["next_action"]),
                    agent_id=args.agent_id,
                    project=None,
                    dry_run=False,
                )
                # Project the continuation the Todo lifecycle durably recorded,
                # never a host-normalized continuation. Contradictory or
                # dangling durable state fails closed before any further
                # writeback so the typed settlement sees the truthful outcome.
                state_file = completion.get("state_file")
                if not isinstance(state_file, str) or not state_file:
                    return {
                        "ok": False,
                        "appended": False,
                        "reason": (
                            "validated completion lifecycle did not report its "
                            "durable Todo state file"
                        ),
                    }
                try:
                    durable_todo, existing_todo_ids = read_persisted_todo_record(
                        Path(state_file),
                        todo_id=todo_id,
                        registry_path=registry_path,
                        goal_id=args.goal_id,
                    )
                    completion_outcome = project_durable_completion_outcome(
                        todo=durable_todo,
                        expected_todo_id=todo_id,
                        existing_todo_ids=existing_todo_ids,
                    )
                except ValueError as exc:
                    return {
                        "ok": False,
                        "appended": False,
                        "reason": f"durable completion projection failed: {exc}",
                    }
                completion_payload = {
                    "ok": bool(completion.get("ok")),
                    # A completed Todo is idempotent under Turn replay: after an
                    # interrupted journal write, the retry may observe it done.
                    "appended": bool(completion.get("completed"))
                    and bool(
                        completion.get("changed") or completion.get("idempotent_replay")
                    ),
                    "completion": completion_outcome,
                }
                if completion_payload["ok"] and completion_payload["appended"]:
                    append_settlement_event(
                        completion_payload,
                        event_kind="todo_complete",
                        status=(
                            "terminal_no_followup"
                            if completion_outcome.get("continuation") == "no_followup"
                            else "completed"
                        ),
                        details={
                            "command": "turn run-once",
                            "no_followup": (
                                completion_outcome.get("continuation") == "no_followup"
                            ),
                        },
                    )
                return completion_payload

            def completion_writeback(
                result: dict[str, object],
                *,
                effect_ref: str,
            ) -> dict[str, object]:
                completion = todo_completion(result, effect_ref=effect_ref)
                if not completion.get("ok"):
                    return completion
                todo_id = str(selected_todo.get("todo_id") or "")
                refresh = writeback(
                    result,
                    completion_todo_id=todo_id,
                    completion_turn_key=settlement_identity.turn_instance_id,
                    effect_ref=effect_ref,
                )
                return {
                    "ok": bool(refresh.get("ok")),
                    "appended": bool(completion.get("appended"))
                    and bool(refresh.get("appended")),
                    "classification": refresh.get("classification"),
                    "completion": completion["completion"],
                }

            def terminal_closeout(
                result: dict[str, object],
                *,
                effect_ref: str,
            ) -> dict[str, object]:
                require_effect_ref(effect_ref, SettlementStepKind.TERMINAL_CLOSEOUT)
                return todo_completion(result, effect_ref=effect_ref)

            def current_status() -> dict[str, object]:
                return collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=scan_roots,
                    limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
                    goal_id=args.goal_id,
                    available_capabilities=args.available_capabilities,
                )

            def spend(*, effect_ref: str) -> dict[str, object]:
                require_effect_ref(effect_ref, SettlementStepKind.QUOTA_SPEND)
                spent = spend_quota_slot(
                    current_status(),
                    goal_id=args.goal_id,
                    slots=1,
                    execute=True,
                    source="adapter",
                    agent_id=args.agent_id,
                    workspace_path=delivery_workspace_path,
                    available_capabilities=args.available_capabilities,
                    operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                )
                if spent.get("ok") and (
                    spent.get("appended")
                    or spent.get("idempotent_replay")
                    or spent.get("receipt_repair_required")
                ):
                    append_settlement_event(
                        spent,
                        event_kind="quota_spend",
                        status="appended",
                        details={"command": "turn run-once"},
                    )
                return spent

            def completion_readback() -> dict[str, object] | None:
                todo_id = str(selected_todo.get("todo_id") or "")
                if not todo_id:
                    return None
                try:
                    _state_project, state_file = resolve_todo_state_path(
                        registry_path=registry_path,
                        goal_id=args.goal_id,
                        project=None,
                        state_file=None,
                    )
                    durable_todo, existing_todo_ids = read_persisted_todo_record(
                        state_file,
                        todo_id=todo_id,
                        registry_path=registry_path,
                        goal_id=args.goal_id,
                    )
                    return project_durable_completion_outcome(
                        todo=durable_todo,
                        expected_todo_id=todo_id,
                        existing_todo_ids=existing_todo_ids,
                    )
                except (OSError, ValueError):
                    return None

            def terminal_completion_readback() -> dict[str, object] | None:
                todo_id = str(selected_todo.get("todo_id") or "")
                if not todo_id:
                    raise ValueError("terminal completion requires one selected Todo")
                _state_project, state_file = resolve_todo_state_path(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    project=None,
                    state_file=None,
                )
                (
                    durable_todo,
                    existing_todo_ids,
                    projection_source,
                ) = read_persisted_todo_record_with_source(
                    state_file,
                    todo_id=todo_id,
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                )
                readback = project_durable_terminal_completion_readback(
                    todo=durable_todo,
                    expected_todo_id=todo_id,
                    expected_completion_turn_key=(
                        settlement_identity.turn_instance_id
                    ),
                    projection_source=projection_source,
                    existing_todo_ids=existing_todo_ids,
                )
                if readback["kind"] == "absent":
                    return None
                completion = readback.get("completion")
                if not isinstance(completion, dict):
                    raise ValueError(
                        "terminal completion readback is missing its completion"
                    )
                return completion

            def writeback_resolver(effect_ref: str) -> dict[str, object]:
                try:
                    require_effect_ref(
                        effect_ref,
                        SettlementStepKind.DURABLE_WRITEBACK,
                    )
                    run = find_settlement_writeback(runtime_root, settlement_identity)
                    event = find_settlement_step_event(
                        runtime_root,
                        settlement_identity,
                        event_kind="refresh_state",
                    )
                    if run is None and event is None:
                        return {"kind": "absent"}
                    if run is None:
                        return {
                            "kind": "unknown",
                            "reason": "refresh-state receipt has no durable run",
                        }
                    if event is None:
                        append_settlement_event(
                            run,
                            event_kind="refresh_state",
                            status="receipt_repaired",
                            details={"command": "turn recovery probe"},
                        )
                    committed: dict[str, object] = {
                        "ok": True,
                        "appended": True,
                        "effect_ref": effect_ref,
                        "classification": run.get("classification"),
                    }
                    completion = completion_readback()
                    if completion is not None:
                        committed["completion"] = completion
                    return {"kind": "committed", "payload": committed}
                except (OSError, ValueError):
                    return {"kind": "unknown", "reason": "writeback readback failed"}

            def spend_resolver(effect_ref: str) -> dict[str, object]:
                try:
                    require_effect_ref(effect_ref, SettlementStepKind.QUOTA_SPEND)
                    run = find_settlement_spend_run(runtime_root, settlement_identity)
                    event = find_settlement_step_event(
                        runtime_root,
                        settlement_identity,
                        event_kind="quota_spend",
                    )
                    if event is not None:
                        return {
                            "kind": "committed",
                            "payload": {
                                "ok": True,
                                "appended": True,
                                "effect_ref": effect_ref,
                                "mode": "spend-slot",
                            },
                        }
                    return {
                        "kind": "unknown",
                        "reason": (
                            "quota outcome has no identity-bound receipt"
                            if run is None
                            else "quota run cannot be bound to this effect"
                        ),
                    }
                except (OSError, ValueError):
                    return {"kind": "unknown", "reason": "quota readback failed"}

            def terminal_closeout_resolver(effect_ref: str) -> dict[str, object]:
                try:
                    require_effect_ref(
                        effect_ref,
                        SettlementStepKind.TERMINAL_CLOSEOUT,
                    )
                    event = find_settlement_step_event(
                        runtime_root,
                        settlement_identity,
                        event_kind="todo_complete",
                    )
                    completion = terminal_completion_readback()
                    if event is None and completion is None:
                        return {"kind": "absent"}
                    if (
                        completion is None
                        or completion.get("continuation") != "no_followup"
                    ):
                        return {
                            "kind": "unknown",
                            "reason": "Todo state does not prove terminal no-followup",
                        }
                    if event is None:
                        append_settlement_event(
                            {"ok": True, "appended": True},
                            event_kind="todo_complete",
                            status="terminal_no_followup",
                            details={
                                "command": "turn recovery probe",
                                "no_followup": True,
                            },
                        )
                    return {
                        "kind": "committed",
                        "payload": {
                            "ok": True,
                            "appended": True,
                            "effect_ref": effect_ref,
                            "completion": completion,
                        },
                    }
                except (OSError, ValueError):
                    return {"kind": "unknown", "reason": "closeout readback failed"}

            def scheduler(_spend_payload: dict[str, object]) -> dict[str, object]:
                turn_scheduler_context = (
                    payload.get("scheduler_execution_context")
                    if isinstance(payload.get("scheduler_execution_context"), dict)
                    else None
                )
                latest = build_live_quota_should_run_decision(
                    current_status(),
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    available_capabilities=args.available_capabilities,
                    include_scheduler_detail=False,
                    codex_app_current_rrule=None,
                    registry_path=registry_path,
                    runtime_root=runtime_root,
                    route_source="loopx_turn_run_once",
                    scheduler_execution_context=turn_scheduler_context,
                    operator_inbox_urgency_projector=operator_inbox_urgency_projector,
                    bounded_research_frontier_projector=(
                        project_live_explore_composition_frontier
                    ),
                )
                hint = (
                    latest.get("scheduler_hint")
                    if isinstance(latest.get("scheduler_hint"), dict)
                    else {}
                )
                phase = hint.get("execution_phase")
                return (
                    dict(phase)
                    if isinstance(phase, dict)
                    else {
                        "disposition": "contract_error",
                        "completed": False,
                        "acknowledged": False,
                        "apply_needed": False,
                    }
                )

            host_runner = None
            session_binding_resolver = None
            if args.host == "codex-cli":

                def run_built_in_host(
                    request: Mapping[str, Any],
                ) -> dict[str, Any]:
                    return run_codex_cli_host(
                        request,
                        runtime_root=runtime_root,
                        project=project,
                        codex_bin=args.codex_bin,
                        sandbox=args.codex_sandbox,
                        model=args.codex_model,
                        timeout_seconds=max(1.0, args.timeout_seconds - 5.0),
                    )

                host_runner = run_built_in_host

                def resolve_built_in_session_binding(
                    turn_envelope: Mapping[str, Any],
                ) -> dict[str, str] | None:
                    return codex_cli_session_binding(runtime_root, turn_envelope)

                session_binding_resolver = resolve_built_in_session_binding

            payload = run_loopx_turn_once(
                payload,
                host_argv=raw_argv,
                host_runner=host_runner,
                session_binding_resolver=session_binding_resolver,
                project=project,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                timeout_seconds=args.timeout_seconds,
                execute=bool(args.execute),
                retry_failed=bool(args.retry_failed_turn),
                task_validator=task_validator,
                writeback=writeback if args.execute else None,
                completion_writeback=completion_writeback if args.execute else None,
                completion_intent=completion_intent if args.execute else None,
                terminal_closeout=terminal_closeout if args.execute else None,
                spend=spend if args.execute else None,
                writeback_resolver=writeback_resolver if args.execute else None,
                spend_resolver=spend_resolver if args.execute else None,
                terminal_closeout_resolver=(
                    terminal_closeout_resolver if args.execute else None
                ),
                scheduler=scheduler if args.execute else None,
            )
        else:
            raise ValueError("turn requires the `plan` or `run-once` subcommand")
    except Exception as exc:  # noqa: BLE001 - CLI boundary renders typed JSON failure
        payload = {
            "ok": False,
            "schema_version": (
                LOOPX_TURN_EXECUTION_SCHEMA_VERSION
                if args.turn_command == "run-once"
                else "loopx_turn_plan_v0"
            ),
            "mode": "run_once" if args.turn_command == "run-once" else "plan",
            "error": str(exc),
            "effects": {
                "host_invoked": False,
                "state_written": False,
                "scheduler_acknowledged": False,
                "quota_spent": False,
            },
        }
    renderer = (
        _render_loopx_turn_execution_markdown
        if args.turn_command == "run-once"
        else _render_loopx_turn_plan_markdown
    )
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
