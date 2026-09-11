from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..agent_registry import (
    agent_profile_from_registry,
    load_goal_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from ..chat_server import (
    DEFAULT_CHAT_HOST,
    DEFAULT_CHAT_PORT,
    serve_chat,
)
from ..control_plane.scheduler.execution_context import SchedulerRuntimeProfile
from ..dashboard_launcher import launch_dashboard, replace_existing_loopx_chat
from ..execution_profile import execution_profile_turn_granularity
from ..heartbeat_prequota import (
    render_heartbeat_pre_quota_markdown,
    run_heartbeat_pre_quota,
)
from ..heartbeat_prompt import (
    build_heartbeat_prompt,
    build_heartbeat_prompt_error_payload,
    render_heartbeat_prompt_markdown,
)
from ..kiro_cli_goal_mode import KIRO_CLI_BIN
from ..paths import default_public_scan_root
from ..presentation.renderers.status_markdown import render_status_markdown
from ..promotion_gate import (
    build_promotion_gate,
    record_promotion_readiness,
    render_promotion_gate_markdown,
    render_promotion_readiness_record_markdown,
)
from ..registry import (
    inspect_registry,
    inspect_registry_boundary,
    render_registry_boundary_markdown,
    render_registry_markdown,
)
from ..self_update import (
    UpdateAction,
    build_rollback_plan,
    build_update_plan,
    execute_rollback_plan,
    execute_update_plan,
    render_update_plan_markdown,
    resolve_update_action,
)
from ..status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)
from ..upgrade import build_upgrade_plan, render_upgrade_plan_markdown
from .support_control_backup import (
    handle_backup_state_command,
    register_backup_state_command,
)
from .support_control_agent_runtime import register_agent_runtime_arguments
from .support_control_chat_endpoint import (
    handle_chat_endpoint_command,
    register_chat_endpoint_command,
)
from .support_control_heartbeat_registration import (
    register_heartbeat_control_commands,
)
from .support_control_registry import (
    explicit_global_registry,
    resolve_heartbeat_active_state,
)
from .support_control_supervisor import (
    SUPERVISOR_CONTROL_COMMANDS,
    handle_supervisor_control_command,
    register_supervisor_control_commands,
)

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]

SUPPORT_CONTROL_COMMANDS = {
    "automation-prompts",
    "backup-state",
    "chat",
    "chat-endpoint",
    "dashboard",
    "heartbeat-prequota",
    "heartbeat-prompt",
    "promotion-gate",
    "promotion-readiness",
    "upgrade-plan",
    "update",
    "registry",
    "registry-boundary",
    "serve-status",
} | SUPERVISOR_CONTROL_COMMANDS


def register_support_control_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    from .automation_prompts import register_automation_prompts
    register_automation_prompts(subparsers, add_subcommand_format)
    register_backup_state_command(subparsers, add_subcommand_format)
    register_heartbeat_control_commands(subparsers, add_subcommand_format)

    register_supervisor_control_commands(subparsers, add_subcommand_format)

    promotion_gate_parser = subparsers.add_parser(
        "promotion-gate",
        help="Emit a compact machine-readable canary promotion readiness gate result.",
    )
    add_subcommand_format(promotion_gate_parser)

    promotion_readiness_parser = subparsers.add_parser(
        "promotion-readiness",
        help="Record release-scoped canary promotion-readiness evidence.",
    )
    promotion_readiness_subparsers = promotion_readiness_parser.add_subparsers(
        dest="promotion_readiness_command",
        required=True,
    )
    promotion_readiness_record_parser = promotion_readiness_subparsers.add_parser(
        "record",
        help="Append one runtime-level readiness event after the canary checks pass.",
    )
    add_subcommand_format(promotion_readiness_record_parser)
    promotion_readiness_record_parser.add_argument(
        "--dashboard-readiness",
        choices=("passed", "skipped"),
        required=True,
        help="Whether dashboard readiness ran successfully or was explicitly skipped.",
    )
    promotion_readiness_record_parser.add_argument(
        "--execute",
        action="store_true",
        help="Append the evidence event. Without this flag, emit a dry-run plan.",
    )

    upgrade_plan_parser = subparsers.add_parser(
        "upgrade-plan",
        help="Plan local default upgrade propagation for managed heartbeat automations.",
    )
    add_subcommand_format(upgrade_plan_parser)
    upgrade_plan_parser.add_argument(
        "--goal-id",
        action="append",
        default=[],
        help="Only include one goal id. Repeatable.",
    )
    upgrade_plan_parser.add_argument(
        "--installed-manifest",
        help=(
            "Optional JSON manifest of installed automations with goal_id, mode, automation_id, and "
            "prompt_sha256/task_body. If omitted, upgrade-plan auto-discovers Codex App heartbeat "
            "automations from $CODEX_HOME/automations or ~/.codex/automations."
        ),
    )
    upgrade_plan_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="CLI command embedded in generated heartbeat prompts for the promoted default.",
    )
    upgrade_plan_parser.add_argument(
        "--mode",
        action="append",
        choices=["thin", "brief", "compact"],
        default=[],
        help="Prompt mode to compare. Repeatable; defaults to the thin installed heartbeat contract.",
    )

    update_parser = subparsers.add_parser(
        "update",
        help="Inspect or apply an update using the active installation owner.",
        description=(
            "Use `update check` for a read-only freshness probe, `update plan` for the "
            "full no-write plan, or `update apply` for an explicit archive-snapshot "
            "mutation. Bare `update` remains a read-only plan."
        ),
    )
    add_subcommand_format(update_parser)
    update_parser.add_argument(
        "update_action",
        nargs="?",
        choices=tuple(action.value for action in UpdateAction),
        help="Explicit intent: check (read only), plan (read only), or apply (mutating).",
    )
    update_mode = update_parser.add_mutually_exclusive_group()
    update_mode.add_argument(
        "--check",
        action="store_true",
        help="Compatibility alias for `loopx update check`.",
    )
    update_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Compatibility alias for `loopx update plan`.",
    )
    update_mode.add_argument(
        "--execute",
        action="store_true",
        help="Compatibility alias for `loopx update apply`; prefer the explicit action.",
    )
    update_mode.add_argument(
        "--rollback",
        metavar="RELEASE_ID",
        help="Repoint the user-local loopx command to a release id, or use `previous` for the prior snapshot.",
    )
    update_parser.add_argument(
        "--repo",
        help="GitHub repo owner/name used by the installer archive. Defaults to LOOPX_REPO or huangruiteng/loopx.",
    )
    update_parser.add_argument(
        "--ref",
        help="Git ref used by the installer archive. Defaults to LOOPX_REF or stable.",
    )
    update_parser.add_argument(
        "--archive-url",
        help="Explicit tarball URL passed to the installer as LOOPX_ARCHIVE_URL.",
    )
    update_parser.add_argument(
        "--installed-doctor-json",
        help=(
            "Local JSON output from the installed `loopx --format json doctor`; "
            "valid only with --check for source-versus-installed qualification."
        ),
    )
    update_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Timeout for `update apply` installer and post-update doctor commands.",
    )

    subparsers.add_parser(
        "registry", help="Inspect registry goals and adapter declarations."
    )
    registry_boundary_parser = subparsers.add_parser(
        "registry-boundary",
        help="Classify a registry file as local-only, global-local, public projection, or public fixture.",
    )
    registry_boundary_parser.add_argument(
        "--path",
        help="Registry path to classify. Defaults to the active --registry path.",
    )
    registry_boundary_parser.add_argument(
        "--require-not-tracked",
        action="store_true",
        help="Return non-zero if the registry is tracked while publication policy disallows pushing it.",
    )
    registry_boundary_parser.add_argument(
        "--require-gitignored",
        action="store_true",
        help="Return non-zero if the registry should be ignored but is neither ignored nor tracked.",
    )

    serve_status_parser = subparsers.add_parser(
        "serve-status", help="Serve live status JSON for the local dashboard."
    )
    serve_status_parser.add_argument(
        "--host",
        default=DEFAULT_STATUS_HOST,
        help="Bind host. Defaults to localhost only.",
    )
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument(
        "--path", default=DEFAULT_STATUS_PATH, help="Status JSON route."
    )
    serve_status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    serve_status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    serve_status_parser.add_argument("--limit", type=int, default=5)
    serve_status_parser.add_argument(
        "--enable-reward-write-api",
        action="store_true",
        help="Enable POST /reward/append on loopback only so the dashboard can append human_reward overlays.",
    )
    serve_status_parser.add_argument(
        "--enable-control-plane-write-api",
        action="store_true",
        help="Enable POST /control-plane/configure-goal/apply on loopback only so the dashboard can write registry settings.",
    )
    serve_status_parser.add_argument(
        "--enable-goal-subagent-configuration",
        action="store_true",
        help=(
            "Expose the Goal sub-agent status projection. Disabled by default."
        ),
    )
    serve_status_parser.add_argument(
        "--global-registry",
        action="store_true",
        help="Serve the shared global registry view even when invoked from a project directory.",
    )
    serve_status_parser.add_argument(
        "--verbose", action="store_true", help="Print HTTP request logs."
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Open the local Goal Studio and review Agent-proposed LoopX Todos.",
    )
    chat_parser.add_argument(
        "--goal-id", help="Goal to select when the local workspace opens."
    )
    chat_parser.add_argument(
        "--host", default=DEFAULT_CHAT_HOST, help="Loopback bind host."
    )
    chat_parser.add_argument("--port", type=int, default=DEFAULT_CHAT_PORT)
    register_agent_runtime_arguments(chat_parser, kiro_cli_bin=KIRO_CLI_BIN)
    chat_parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=30.0,
        help="Maximum seconds allowed for Codex app-server startup and handshake.",
    )
    chat_parser.add_argument(
        "--idle-timeout-seconds",
        type=float,
        default=180.0,
        help="Maximum seconds without an upstream event before interrupting the active turn.",
    )
    chat_parser.add_argument(
        "--hard-timeout-seconds",
        type=float,
        default=900.0,
        help="Absolute maximum seconds for one Agent turn.",
    )
    chat_parser.add_argument(
        "--assets-dir",
        help="Optional LoopX Chat web bundle directory. Defaults to packaged assets.",
    )
    chat_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files used by the underlying status projection.",
    )
    chat_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable.",
    )
    chat_parser.add_argument("--limit", type=int, default=20)
    chat_parser.add_argument(
        "--global-registry",
        action="store_true",
        help="Use the shared global registry even when the command runs in a project directory.",
    )
    chat_parser.add_argument(
        "--enable-goal-subagent-configuration",
        action="store_true",
        help=(
            "Enable the preview-locked Goal sub-agent configuration API, "
            "status projection, and dashboard controls."
        ),
    )
    chat_parser.add_argument(
        "--no-open",
        action="store_true",
        help="Start the local server without opening a browser.",
    )
    chat_parser.add_argument(
        "--replace-existing-loopx-chat",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    chat_parser.add_argument(
        "--verbose", action="store_true", help="Print HTTP request logs."
    )

    register_chat_endpoint_command(subparsers, add_subcommand_format)

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start the local LoopX dashboard, status service, and Chat service.",
    )
    dashboard_parser.add_argument(
        "--goal-id", help="Goal to select when the local workspace opens."
    )
    dashboard_parser.add_argument(
        "--host", default=DEFAULT_CHAT_HOST, help="Loopback bind host."
    )
    dashboard_parser.add_argument("--port", type=int, default=DEFAULT_CHAT_PORT)
    register_agent_runtime_arguments(dashboard_parser, kiro_cli_bin=KIRO_CLI_BIN)
    dashboard_parser.add_argument(
        "--assets-dir",
        help="Optional LoopX Chat web bundle directory. Defaults to packaged assets.",
    )
    dashboard_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files used by the underlying status projection.",
    )
    dashboard_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable.",
    )
    dashboard_parser.add_argument("--limit", type=int, default=20)
    dashboard_parser.add_argument(
        "--global-registry",
        action="store_true",
        help="Use the shared global registry even when the command runs in a project directory.",
    )
    dashboard_parser.add_argument(
        "--enable-goal-subagent-configuration",
        action="store_true",
        help=(
            "Enable the preview-locked Goal sub-agent configuration API, "
            "status projection, and dashboard controls."
        ),
    )
    dashboard_parser.add_argument(
        "--no-open",
        action="store_true",
        help="Start the local server without opening a browser.",
    )
    dashboard_parser.add_argument(
        "--dev",
        action="store_true",
        help="Prefer the Vite HMR dev launcher if running from a local repository checkout.",
    )
    dashboard_parser.add_argument(
        "--verbose", action="store_true", help="Print HTTP request logs."
    )


def handle_support_control_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    registry_was_supplied: bool,
    print_payload: PrintPayload,
    output_format: FormatSelector,
) -> int | None:
    if args.command not in SUPPORT_CONTROL_COMMANDS:
        return None

    if args.command == "automation-prompts":
        from .automation_prompts import run, render
        try:
            payload = run(args, registry_path)
        except Exception as error:
            payload = {"ok": False, "error": str(error)}
        print_payload(payload, output_format(args), render)
        return 0 if payload.get("ok") else 1

    if args.command == "chat-endpoint":
        return handle_chat_endpoint_command(
            args,
            registry_path=registry_path,
            print_payload=print_payload,
        )

    if args.command == "backup-state":
        return handle_backup_state_command(
            args,
            registry_path=registry_path,
            print_payload=print_payload,
            output_format=output_format,
        )

    if args.command == "heartbeat-prequota":
        prequota_registry = (
            registry_path
            if registry_was_supplied
            else explicit_global_registry(args.runtime_root)
        )
        payload = run_heartbeat_pre_quota(
            registry_path=prequota_registry,
            runtime_root_arg=args.runtime_root,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            fetch_timeout_seconds=args.fetch_timeout_seconds,
        )
        print_payload(
            payload,
            output_format(args),
            render_heartbeat_pre_quota_markdown,
        )
        return 0

    if args.command == "heartbeat-prompt":
        active_state = None
        resolved_active_state = None
        active_state_source = None
        registered_agents = None
        effective_agent_id = args.agent_id
        try:
            active_state, resolved_active_state, active_state_source = (
                resolve_heartbeat_active_state(
                    goal_id=args.goal_id,
                    active_state_arg=args.active_state,
                    registry_path=registry_path,
                    runtime_root_arg=args.runtime_root,
                    allow_global_goal_lookup_fallback=not registry_was_supplied,
                )
            )
            agent_registry_path = registry_path
            if active_state_source.startswith("registry:"):
                agent_registry_path = Path(
                    active_state_source.removeprefix("registry:")
                )
            registered_agents = registered_agent_ids_from_registry(
                agent_registry_path, args.goal_id
            )
            registry_goal = load_goal_from_registry(
                agent_registry_path,
                args.goal_id,
            )
            turn_granularity = execution_profile_turn_granularity(
                registry_goal.get("execution_profile")
                if isinstance(registry_goal, dict)
                else None
            )
            agent_profile = None
            if args.agent_id:
                effective_agent_id = require_registered_agent_id(
                    registry_path=agent_registry_path,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    field="agent_id",
                )
                agent_profile = agent_profile_from_registry(
                    agent_registry_path, args.goal_id, effective_agent_id
                )
            explicit_scheduler_fields = (
                args.host_surface,
                args.scheduler_owner,
                args.execution_mode,
            )
            if args.codex_app and (
                args.runtime_profile or any(explicit_scheduler_fields)
            ):
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
            payload = build_heartbeat_prompt(
                goal_id=args.goal_id,
                active_state=active_state,
                active_state_source=active_state_source,
                resolved_active_state=resolved_active_state,
                material_queue_rule=args.material_rule,
                permission_rule=args.permission_rule,
                full=bool(args.full),
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
                runtime_root=args.runtime_root,
                agent_id=effective_agent_id,
                agent_scopes=args.agent_scopes,
                agent_profile=agent_profile,
                registered_agents=registered_agents,
                available_capabilities=args.available_capabilities,
                runtime_profile=runtime_profile,
                scheduler_execution_context=(
                    {
                        "host_surface": args.host_surface,
                        "scheduler_owner": args.scheduler_owner,
                        "execution_mode": args.execution_mode,
                    }
                    if any(explicit_scheduler_fields)
                    else None
                ),
                visible_goal_host=args.visible_goal_host,
                turn_granularity=turn_granularity,
                turn_instance_id=args.turn_instance_id,
            )
            if args.bootstrap and payload.get("ok"):
                from ..control_plane.heartbeat.bootstrap_prompt import goal_bootstrap
                from ..control_plane.heartbeat.budget import build_interface_budget
                body = goal_bootstrap(args, registry=agent_registry_path)
                payload["task_body"] = body
                payload["bootstrap"] = True
                payload["interface_budget"] = build_interface_budget(
                    task_body=body, goal_id=args.goal_id,
                    active_state=str(payload.get("active_state") or ""), thin=True,
                )
                if not payload["interface_budget"]["within_budget"]:
                    raise ValueError("bootstrap exceeds the thin budget; move lengthy policy into registered state")
        except Exception as exc:
            fallback_active_state = active_state
            fallback_resolved_active_state = resolved_active_state
            fallback_active_state_source = active_state_source
            if fallback_active_state is None and args.active_state:
                fallback_active_state = Path(args.active_state).expanduser()
                fallback_resolved_active_state = (
                    fallback_resolved_active_state or fallback_active_state
                )
                fallback_active_state_source = (
                    fallback_active_state_source or "explicit"
                )
            elif fallback_active_state_source is None:
                fallback_active_state_source = "registry"
            payload = build_heartbeat_prompt_error_payload(
                goal_id=args.goal_id,
                error=str(exc),
                active_state=fallback_active_state,
                active_state_source=fallback_active_state_source,
                resolved_active_state=fallback_resolved_active_state,
                material_queue_rule=args.material_rule,
                permission_rule=args.permission_rule,
                full=bool(args.full),
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
                runtime_root=args.runtime_root,
                agent_id=effective_agent_id or args.agent_id,
                agent_scopes=args.agent_scopes,
                registered_agents=registered_agents,
                available_capabilities=args.available_capabilities,
            )
        print_payload(payload, output_format(args), render_heartbeat_prompt_markdown)
        return 0 if payload.get("ok") else 1

    supervisor_result = handle_supervisor_control_command(
        args,
        registry_path=registry_path,
        registry_was_supplied=registry_was_supplied,
        print_payload=print_payload,
        output_format=output_format,
    )
    if supervisor_result is not None:
        return supervisor_result

    if args.command == "promotion-gate":
        try:
            payload = build_promotion_gate(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "gate": "promotion_readiness",
                "gate_state": "error",
                "can_promote": False,
                "should_warn": True,
                "non_blocking": True,
                "error": str(exc),
                "recommended_action": "fix promotion readiness gate collection before promotion",
            }
        print_payload(payload, output_format(args), render_promotion_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "promotion-readiness":
        try:
            payload = record_promotion_readiness(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                dashboard_readiness=args.dashboard_readiness,
                execute=args.execute,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not args.execute,
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "evidence_scope": "runtime_release",
                "error": str(exc),
            }
        print_payload(
            payload,
            output_format(args),
            render_promotion_readiness_record_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.command == "upgrade-plan":
        try:
            payload = build_upgrade_plan(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                installed_manifest=Path(args.installed_manifest).expanduser()
                if args.installed_manifest
                else None,
                cli_bin=args.cli_bin,
                modes=args.mode or None,
                goal_ids=args.goal_id or None,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "mode": "upgrade-plan",
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "summary": {
                    "managed_goal_count": 0,
                    "current_prompt_count": 0,
                    "stale_prompt_count": 0,
                    "unknown_prompt_count": 0,
                    "not_installed_prompt_count": 0,
                    "stage_deferred_goal_count": 0,
                    "ready_for_default_promotion": False,
                    "installed_manifest_available": False,
                    "installed_manifest_source": None,
                    "installed_manifest_entry_count": 0,
                    "installed_manifest_task_body_count": 0,
                    "installed_manifest_has_task_body": False,
                },
                "recommended_action": "fix upgrade-plan collection before default promotion",
            }
        print_payload(payload, output_format(args), render_upgrade_plan_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "update":
        update_action = UpdateAction.PLAN
        try:
            update_action = resolve_update_action(
                args.update_action,
                check=args.check,
                dry_run=args.dry_run,
                execute=args.execute,
            )
            if args.rollback and args.update_action:
                raise ValueError(
                    "update rollback cannot be combined with check, plan, or apply"
                )
            if args.installed_doctor_json and update_action is not UpdateAction.CHECK:
                raise ValueError(
                    "--installed-doctor-json requires `loopx update check`"
                )
            if args.rollback:
                payload = build_rollback_plan(release_id=args.rollback)
                payload = execute_rollback_plan(
                    payload, timeout_seconds=args.timeout_seconds
                )
            else:
                doctor_payload = None
                if args.installed_doctor_json:
                    doctor_path = Path(args.installed_doctor_json).expanduser()
                    loaded_doctor = json.loads(doctor_path.read_text(encoding="utf-8"))
                    if not isinstance(loaded_doctor, dict):
                        raise ValueError(
                            "--installed-doctor-json must contain a JSON object"
                        )
                    doctor_payload = loaded_doctor
                payload = build_update_plan(
                    repo=args.repo,
                    ref=args.ref,
                    archive_url=args.archive_url,
                    action=update_action,
                    doctor_payload=doctor_payload,
                )
                payload["installed_doctor_source"] = (
                    "explicit_json" if doctor_payload is not None else "current_runtime"
                )
                if update_action is UpdateAction.APPLY and payload.get("plan", {}).get(
                    "apply_supported"
                ):
                    from ..control_plane.heartbeat.installed_prompt_update import update_with_prompts
                    payload = update_with_prompts(
                        payload, registry=(registry_path if registry_was_supplied else explicit_global_registry(args.runtime_root)),
                        runtime_root=args.runtime_root,
                        timeout_seconds=args.timeout_seconds, runtime_update=execute_update_plan,
                    )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_update_plan_v0",
                "mode": "update",
                "requested_action": update_action.value,
                "check_only": update_action is UpdateAction.CHECK,
                "dry_run": update_action is not UpdateAction.APPLY,
                "execute_requested": update_action is UpdateAction.APPLY,
                "changes_applied": False,
                "error": str(exc),
                "recommended_action": "fix update planning or installation before retrying",
            }
        print_payload(payload, output_format(args), render_update_plan_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry":
        payload = inspect_registry(registry_path)
        print_payload(payload, args.format, render_registry_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry-boundary":
        boundary_path = Path(args.path).expanduser() if args.path else registry_path
        payload = inspect_registry_boundary(boundary_path)
        git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
        if (
            args.require_not_tracked
            and payload.get("ok")
            and git.get("tracked")
            and not payload.get("github_push_allowed")
        ):
            payload = dict(payload)
            payload["ok"] = False
            payload.setdefault("risks", []).append(
                "registry_tracked_but_not_push_allowed"
            )
        if (
            args.require_gitignored
            and payload.get("ok")
            and payload.get("should_be_gitignored")
        ):
            if (
                git.get("inside_worktree")
                and not git.get("ignored")
                and not git.get("tracked")
            ):
                payload = dict(payload)
                payload["ok"] = False
                payload.setdefault("risks", []).append("registry_should_be_gitignored")
        print_payload(payload, args.format, render_registry_boundary_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            status_registry_path = (
                explicit_global_registry(args.runtime_root)
                if args.global_registry
                else registry_path
            )
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            serve_status(
                registry_path=status_registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                status_path=args.path,
                enable_reward_write_api=bool(args.enable_reward_write_api),
                enable_control_plane_write_api=bool(
                    args.enable_control_plane_write_api
                ),
                verbose=bool(args.verbose),
                enable_goal_subagent_configuration=bool(
                    args.enable_goal_subagent_configuration
                ),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(
                    status_registry_path
                    if "status_registry_path" in locals()
                    else registry_path
                ),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    if args.command == "dashboard":
        try:
            dashboard_registry_path = (
                explicit_global_registry(args.runtime_root)
                if getattr(args, "global_registry", False)
                else registry_path
            )
            scan_roots = [
                Path(item).expanduser() for item in getattr(args, "scan_path", []) or []
            ]
            if not scan_roots and getattr(args, "scan_root", None):
                scan_roots = [Path(args.scan_root).expanduser()]
            return launch_dashboard(
                registry_path=dashboard_registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, getattr(args, "limit", 20)),
                host=getattr(args, "host", DEFAULT_CHAT_HOST),
                port=getattr(args, "port", DEFAULT_CHAT_PORT),
                goal_id=getattr(args, "goal_id", None),
                codex_bin=getattr(args, "codex_bin", "codex"),
                claude_bin=getattr(args, "claude_bin", "claude"),
                kiro_cli_bin=getattr(args, "kiro_cli_bin", KIRO_CLI_BIN),
                lark_cli_bin=getattr(args, "lark_cli_bin", None),
                assets_dir=Path(args.assets_dir).expanduser().resolve()
                if getattr(args, "assets_dir", None)
                else None,
                verbose=getattr(args, "verbose", False),
                open_browser=not getattr(args, "no_open", False),
                prefer_dev=getattr(args, "dev", False),
                enable_goal_subagent_configuration=bool(
                    getattr(args, "enable_goal_subagent_configuration", False)
                ),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_dashboard_start_v0",
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1

    if args.command == "chat":
        try:
            chat_registry_path = (
                explicit_global_registry(args.runtime_root)
                if args.global_registry
                else registry_path
            )
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            if bool(getattr(args, "replace_existing_loopx_chat", False)):
                replace_existing_loopx_chat(args.host, args.port)
            serve_chat(
                registry_path=chat_registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                goal_id=args.goal_id,
                codex_bin=args.codex_bin,
                claude_bin=args.claude_bin,
                kiro_cli_bin=getattr(args, "kiro_cli_bin", KIRO_CLI_BIN),
                lark_cli_bin=args.lark_cli_bin,
                startup_timeout_sec=max(0.1, float(args.startup_timeout_seconds)),
                idle_timeout_sec=max(0.1, float(args.idle_timeout_seconds)),
                hard_timeout_sec=max(0.1, float(args.hard_timeout_seconds)),
                assets_dir=Path(args.assets_dir).expanduser()
                if args.assets_dir
                else None,
                open_browser=not bool(args.no_open),
                verbose=bool(args.verbose),
                enable_goal_subagent_configuration=bool(
                    args.enable_goal_subagent_configuration
                ),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_chat_start_v0",
                "error": str(exc),
                "gate": {
                    "kind": "host_tool_gate",
                    "summary": "LoopX Chat could not start on this host.",
                    "next_action": "Resolve the reported local host capability, then retry loopx chat.",
                },
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return None
