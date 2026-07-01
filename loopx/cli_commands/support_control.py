from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..agent_registry import (
    agent_profile_from_registry,
    primary_agent_id_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
    side_agent_handoff_agent_id_from_registry,
)
from ..heartbeat_prompt import (
    build_heartbeat_prompt,
    build_heartbeat_prompt_error_payload,
    render_heartbeat_prompt_markdown,
)
from ..history import load_registry
from ..paths import DEFAULT_RUNTIME_ROOT, global_registry_path, resolve_runtime_root
from ..promotion_gate import build_promotion_gate, render_promotion_gate_markdown
from ..registry import (
    inspect_registry,
    inspect_registry_boundary,
    registry_goals,
    render_registry_boundary_markdown,
    render_registry_markdown,
    resolve_state_file,
)
from ..self_update import (
    build_rollback_plan,
    build_update_plan,
    execute_rollback_plan,
    execute_update_plan,
    render_update_plan_markdown,
)
from ..state_backup import (
    build_state_backup_plan,
    execute_state_backup_plan,
    render_state_backup_markdown,
)
from ..status import render_status_markdown
from ..status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)
from ..upgrade import build_upgrade_plan, render_upgrade_plan_markdown


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]

SUPPORT_CONTROL_COMMANDS = {
    "backup-state",
    "heartbeat-prompt",
    "promotion-gate",
    "upgrade-plan",
    "update",
    "registry",
    "registry-boundary",
    "serve-status",
}


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def fallback_global_registry(registry_path: Path, runtime_root_arg: str | None) -> Path:
    if registry_path.exists():
        return registry_path
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    fallback_registry = global_registry_path(runtime_root)
    return fallback_registry if fallback_registry.exists() else registry_path


def explicit_global_registry(runtime_root_arg: str | None) -> Path:
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    return global_registry_path(runtime_root)


def resolve_heartbeat_active_state(
    *,
    goal_id: str,
    active_state_arg: str | None,
    registry_path: Path,
    runtime_root_arg: str | None,
    allow_global_goal_lookup_fallback: bool = True,
) -> tuple[Path | None, Path | None, str]:
    if active_state_arg:
        active_state = Path(active_state_arg).expanduser()
        return active_state, active_state, "explicit"

    resolved_registry = fallback_global_registry(registry_path, runtime_root_arg)
    registry = load_registry(resolved_registry)
    goal = next((item for item in registry_goals(registry) if item.get("id") == goal_id), None)
    if goal is None and allow_global_goal_lookup_fallback:
        global_registry = explicit_global_registry(runtime_root_arg)
        if global_registry != resolved_registry and global_registry.exists():
            global_payload = load_registry(global_registry)
            global_goal = next((item for item in registry_goals(global_payload) if item.get("id") == goal_id), None)
            if global_goal is not None:
                resolved_registry = global_registry
                registry = global_payload
                goal = global_goal
    if goal is None:
        raise ValueError(f"goal_id not found in registry for heartbeat active-state lookup: {goal_id}")
    repo_text = str(goal.get("repo") or "")
    if not repo_text:
        raise ValueError(f"{goal_id}: registry goal has no repo for active-state lookup")
    state_file = resolve_state_file(Path(repo_text).expanduser(), goal.get("state_file"))
    if state_file is None:
        raise ValueError(f"{goal_id}: registry goal has no state_file for active-state lookup")
    if not state_file.exists():
        raise FileNotFoundError(f"{goal_id}: registry-declared active state file does not exist: {state_file}")
    return None, state_file, f"registry:{resolved_registry}"


def register_support_control_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    backup_state_parser = subparsers.add_parser(
        "backup-state",
        help="Preview or create a private local archive of LoopX state.",
    )
    add_subcommand_format(backup_state_parser)
    backup_state_parser.add_argument(
        "--project",
        default=".",
        help="Project root whose .loopx, .codex/goals, and .local/goals state should be included.",
    )
    backup_state_parser.add_argument(
        "--output-dir",
        help="Directory for the backup archive and manifest. Defaults to <runtime-root>/backups.",
    )
    backup_state_parser.add_argument(
        "--backup-id",
        help="Stable id for the archive name. Defaults to a UTC timestamp.",
    )
    backup_state_parser.add_argument(
        "--no-automations",
        action="store_true",
        help="Exclude $CODEX_HOME/automations from the backup.",
    )
    backup_state_parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Exclude $CODEX_HOME/skills/loopx-* skill directories from the backup.",
    )
    backup_state_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the backup archive and manifest. Omit for a dry-run plan.",
    )

    heartbeat_prompt_parser = subparsers.add_parser(
        "heartbeat-prompt",
        help="Generate a guarded Codex App heartbeat automation task body.",
    )
    add_subcommand_format(heartbeat_prompt_parser)
    heartbeat_prompt_parser.add_argument("--goal-id", required=True, help="Stable LoopX goal id.")
    heartbeat_prompt_parser.add_argument(
        "--active-state",
        help="Active goal state file the heartbeat should read and write back. Defaults to the registry goal state_file.",
    )
    heartbeat_prompt_parser.add_argument(
        "--material-rule",
        help="Optional project-specific material queue rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--permission-rule",
        help="Optional trusted-session permission rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="Command name embedded in generated preflight/guard/spend commands. Use loopx-canary for gray rollout targets.",
    )
    heartbeat_prompt_parser.add_argument(
        "--agent-id",
        help="Optional public-safe automation agent id, such as codex-main-control or codex-side-bypass.",
    )
    heartbeat_prompt_parser.add_argument(
        "--agent-scope",
        dest="agent_scopes",
        action="append",
        help="Optional natural-language scope for this automation agent. Repeat for multiple scope lines.",
    )
    heartbeat_style_group = heartbeat_prompt_parser.add_mutually_exclusive_group()
    heartbeat_style_group.add_argument(
        "--compact",
        action="store_true",
        help="Generate a shorter automation body that points edge cases back to the expanded lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--brief",
        action="store_true",
        help="Generate a minimal installed automation body that delegates details to the compact lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--thin",
        action="store_true",
        help="Generate the thinnest generic dispatcher body for trusted agents that inspect LoopX state themselves.",
    )

    promotion_gate_parser = subparsers.add_parser(
        "promotion-gate",
        help="Emit a compact machine-readable canary promotion readiness gate result.",
    )
    add_subcommand_format(promotion_gate_parser)

    upgrade_plan_parser = subparsers.add_parser(
        "upgrade-plan",
        help="Plan local default upgrade propagation for managed heartbeat automations.",
    )
    add_subcommand_format(upgrade_plan_parser)
    upgrade_plan_parser.add_argument("--goal-id", action="append", default=[], help="Only include one goal id. Repeatable.")
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
        help="Check or execute a no-clone LoopX self-update.",
    )
    add_subcommand_format(update_parser)
    update_mode = update_parser.add_mutually_exclusive_group()
    update_mode.add_argument("--check", action="store_true", help="Only report install freshness and update source.")
    update_mode.add_argument("--dry-run", action="store_true", help="Preview the update plan without installing.")
    update_mode.add_argument("--execute", action="store_true", help="Run the installer and validate with loopx doctor.")
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
        "--timeout-seconds",
        type=int,
        default=600,
        help="Timeout for --execute installer and post-update doctor commands.",
    )

    subparsers.add_parser("registry", help="Inspect registry goals and adapter declarations.")
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

    serve_status_parser = subparsers.add_parser("serve-status", help="Serve live status JSON for the local dashboard.")
    serve_status_parser.add_argument("--host", default=DEFAULT_STATUS_HOST, help="Bind host. Defaults to localhost only.")
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status JSON route.")
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
        "--global-registry",
        action="store_true",
        help="Serve the shared global registry view even when invoked from a project directory.",
    )
    serve_status_parser.add_argument("--verbose", action="store_true", help="Print HTTP request logs.")


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

    if args.command == "backup-state":
        try:
            backup_runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            if backup_runtime_root is None and registry_path.exists():
                backup_runtime_root = resolve_runtime_root(load_registry(registry_path))
            payload = build_state_backup_plan(
                project=Path(args.project).expanduser(),
                runtime_root=backup_runtime_root,
                output_dir=Path(args.output_dir).expanduser() if args.output_dir else None,
                backup_id=args.backup_id,
                include_automations=not bool(args.no_automations),
                include_skills=not bool(args.no_skills),
            )
            if args.execute:
                payload = execute_state_backup_plan(payload)
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_state_backup_v0",
                "mode": "state_backup",
                "dry_run": not bool(getattr(args, "execute", False)),
                "execute_requested": bool(getattr(args, "execute", False)),
                "error": str(exc),
                "recommended_action": "fix backup planning before retrying",
            }
        print_payload(payload, output_format(args), render_state_backup_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "heartbeat-prompt":
        active_state = None
        resolved_active_state = None
        active_state_source = None
        registered_agents = None
        primary_agent = None
        side_agent_handoff_agent = None
        effective_agent_id = args.agent_id
        try:
            active_state, resolved_active_state, active_state_source = resolve_heartbeat_active_state(
                goal_id=args.goal_id,
                active_state_arg=args.active_state,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
                allow_global_goal_lookup_fallback=not registry_was_supplied,
            )
            agent_registry_path = registry_path
            if active_state_source.startswith("registry:"):
                agent_registry_path = Path(active_state_source.removeprefix("registry:"))
            registered_agents = registered_agent_ids_from_registry(agent_registry_path, args.goal_id)
            primary_agent = primary_agent_id_from_registry(agent_registry_path, args.goal_id)
            agent_profile = None
            if args.agent_id:
                effective_agent_id = require_registered_agent_id(
                    registry_path=agent_registry_path,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    field="agent_id",
                )
                agent_profile = agent_profile_from_registry(agent_registry_path, args.goal_id, effective_agent_id)
            side_agent_handoff_agent = side_agent_handoff_agent_id_from_registry(
                agent_registry_path,
                args.goal_id,
                agent_id=effective_agent_id,
            )
            payload = build_heartbeat_prompt(
                goal_id=args.goal_id,
                active_state=active_state,
                active_state_source=active_state_source,
                resolved_active_state=resolved_active_state,
                material_queue_rule=args.material_rule,
                permission_rule=args.permission_rule,
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
                agent_id=effective_agent_id,
                agent_scopes=args.agent_scopes,
                agent_profile=agent_profile,
                registered_agents=registered_agents,
                primary_agent=primary_agent,
                side_agent_handoff_agent=side_agent_handoff_agent,
            )
        except Exception as exc:
            fallback_active_state = active_state
            fallback_resolved_active_state = resolved_active_state
            fallback_active_state_source = active_state_source
            if fallback_active_state is None and args.active_state:
                fallback_active_state = Path(args.active_state).expanduser()
                fallback_resolved_active_state = fallback_resolved_active_state or fallback_active_state
                fallback_active_state_source = fallback_active_state_source or "explicit"
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
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
                agent_id=effective_agent_id or args.agent_id,
                agent_scopes=args.agent_scopes,
                registered_agents=registered_agents,
                primary_agent=primary_agent,
                side_agent_handoff_agent=side_agent_handoff_agent,
            )
        print_payload(payload, output_format(args), render_heartbeat_prompt_markdown)
        return 0 if payload.get("ok") else 1

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

    if args.command == "upgrade-plan":
        try:
            payload = build_upgrade_plan(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                installed_manifest=Path(args.installed_manifest).expanduser() if args.installed_manifest else None,
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
        try:
            if args.rollback:
                payload = build_rollback_plan(release_id=args.rollback)
                payload = execute_rollback_plan(payload, timeout_seconds=args.timeout_seconds)
            else:
                payload = build_update_plan(
                    repo=args.repo,
                    ref=args.ref,
                    archive_url=args.archive_url,
                    check_only=args.check,
                    execute=args.execute,
                )
                if args.execute:
                    payload = execute_update_plan(payload, timeout_seconds=args.timeout_seconds)
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_update_plan_v0",
                "mode": "update",
                "check_only": bool(getattr(args, "check", False)),
                "dry_run": not bool(getattr(args, "execute", False)),
                "execute_requested": bool(getattr(args, "execute", False)),
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
        if args.require_not_tracked and payload.get("ok") and git.get("tracked") and not payload.get(
            "github_push_allowed"
        ):
            payload = dict(payload)
            payload["ok"] = False
            payload.setdefault("risks", []).append("registry_tracked_but_not_push_allowed")
        if args.require_gitignored and payload.get("ok") and payload.get("should_be_gitignored"):
            if git.get("inside_worktree") and not git.get("ignored") and not git.get("tracked"):
                payload = dict(payload)
                payload["ok"] = False
                payload.setdefault("risks", []).append("registry_should_be_gitignored")
        print_payload(payload, args.format, render_registry_boundary_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            status_registry_path = explicit_global_registry(args.runtime_root) if args.global_registry else registry_path
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
                enable_control_plane_write_api=bool(args.enable_control_plane_write_api),
                verbose=bool(args.verbose),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(status_registry_path if "status_registry_path" in locals() else registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return None
