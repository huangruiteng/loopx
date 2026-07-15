from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..control_plane.turn_driver import (
    LOOPX_TURN_EXECUTION_SCHEMA_VERSION,
    LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
    build_loopx_turn_command_validator,
    build_loopx_turn_plan,
    codex_cli_session_binding,
    load_loopx_turn_plan_from_journal,
    run_codex_cli_host,
    run_loopx_turn_once,
)
from ..control_plane.quota.live_decision import build_live_quota_should_run_decision
from ..control_plane.quota.turn_envelope import build_turn_envelope
from ..control_plane.runtime.status_projection_cache import (
    resolve_status_projection_cache_runtime_root,
)
from ..quota import spend_quota_slot
from ..state_refresh import refresh_state_run
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status
from ..todos import update_goal_todo


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def register_turn_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "turn",
        help="Plan or run one governed external-host turn from a live LoopX decision.",
    )
    command_sub = parser.add_subparsers(dest="turn_command", required=True)
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
        default=_default_public_scan_root(),
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
            "on stdin and must independently check the real postcondition."
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
        default=_default_public_scan_root(),
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
        payload.get("validation")
        if isinstance(payload.get("validation"), dict)
        else {}
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
    try:
        scan_roots = [Path(item).expanduser() for item in args.scan_path]
        if not scan_roots:
            scan_roots = [Path(args.scan_root).expanduser()]
        runtime_root = resolve_status_projection_cache_runtime_root(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
        )
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=scan_roots,
            limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
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
        turn_envelope = build_turn_envelope(decision)
        if args.turn_command == "run-once" and args.host == "codex-cli" and not supplied_resume_fields:
            session_binding = codex_cli_session_binding(runtime_root, turn_envelope)
        payload = build_loopx_turn_plan(
            turn_envelope,
            host=args.host,
            execution_mode=args.execution_mode,
            session_binding=session_binding,
        )
        if args.turn_command == "plan":
            if not args.include_transaction_detail:
                payload.pop("session", None)
                payload.pop("transaction", None)
                boundary = payload.get("boundary")
                if isinstance(boundary, dict):
                    boundary.pop("opaque_session_handle_omitted", None)
        elif args.turn_command == "run-once":
            if args.resume_turn_key:
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
            planned_host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
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
            envelope = payload.get("turn_envelope") if isinstance(payload.get("turn_envelope"), dict) else {}
            action = envelope.get("action") if isinstance(envelope.get("action"), dict) else {}
            selected_todo = action.get("selected_todo") if isinstance(action.get("selected_todo"), dict) else {}

            def writeback(result: dict[str, object]) -> dict[str, object]:
                # The host workspace is execution context, not state authority.
                state_project = None
                result_kind = str(result.get("result_kind") or "")
                if result_kind in {"repair_required", "replan_required"}:
                    todo_id = str(selected_todo.get("todo_id") or "")
                    if not todo_id:
                        raise ValueError(f"{result_kind} requires one selected todo for typed writeback")
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
                return refresh_state_run(
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
                    agent_id=args.agent_id,
                    progress_scope="goal",
                    autonomous_replan_recorded=result_kind == "replan_required",
                    vision_unchanged_reason=str(result["vision_unchanged_reason"]),
                    dry_run=False,
                    sync_global=not bool(args.no_global_sync),
                )

            def current_status() -> dict[str, object]:
                return collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=scan_roots,
                    limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
                )

            def spend() -> dict[str, object]:
                return spend_quota_slot(
                    current_status(),
                    goal_id=args.goal_id,
                    slots=1,
                    execute=True,
                    source="adapter",
                    agent_id=args.agent_id,
                    available_capabilities=args.available_capabilities,
                )

            def scheduler(_spend_payload: dict[str, object]) -> dict[str, object]:
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
                )
                hint = latest.get("scheduler_hint") if isinstance(latest.get("scheduler_hint"), dict) else {}
                codex_app = hint.get("codex_app") if isinstance(hint.get("codex_app"), dict) else {}
                backoff = codex_app.get("stateful_backoff") if isinstance(codex_app.get("stateful_backoff"), dict) else {}
                apply_needed = backoff.get("apply_needed") is True
                return {
                    "disposition": "host_action_required" if apply_needed else "not_required",
                    "completed": not apply_needed,
                    "acknowledged": False,
                    "apply_needed": apply_needed,
                    **(
                        {
                            "recommended_interval_minutes": codex_app.get(
                                "recommended_interval_minutes"
                            ),
                            "ack_hint": codex_app.get("ack_hint"),
                        }
                        if apply_needed
                        else {}
                    ),
                }

            host_runner = None
            if args.host == "codex-cli":
                def run_built_in_host(request: dict[str, object]) -> dict[str, object]:
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

            payload = run_loopx_turn_once(
                payload,
                host_argv=raw_argv,
                host_runner=host_runner,
                project=project,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                timeout_seconds=args.timeout_seconds,
                execute=bool(args.execute),
                retry_failed=bool(args.retry_failed_turn),
                task_validator=task_validator,
                writeback=writeback if args.execute else None,
                spend=spend if args.execute else None,
                scheduler=scheduler if args.execute else None,
            )
        else:
            raise ValueError("turn requires the `plan` or `run-once` subcommand")
    except Exception as exc:
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
