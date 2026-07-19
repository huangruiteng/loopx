from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..agent_registry import normalize_registered_agents
from ..configure_goal import configure_goal, render_configure_goal_markdown
from ..control_plane.goals.configure_goal_service import (
    configure_goal_with_global_sync,
)
from ..global_registry import (
    render_global_goal_retirement_markdown,
    render_global_sync_markdown,
    retire_global_registry_goals,
    sync_project_registry_to_global,
)
from ..history import load_registry
from ..orchestration import EXPLORE_HARNESS_PROFILES
from ..paths import DEFAULT_RUNTIME_ROOT, global_registry_path, resolve_runtime_root
from ..project_uninstall import render_project_uninstall_markdown, uninstall_project
from ..registry_writability import probe_registry_write_path
from ..registry import registry_goals
from ..runtime import archive_runtime_goal, render_archive_runtime_markdown
from ..state_migration import (
    LEGACY_GLOBAL_REGISTRY,
    LEGACY_RUNTIME_ROOT,
    legacy_registry_goal_ids,
    migrate_legacy_state,
    parse_key_value_map,
    render_state_migration_markdown,
)
from ..upgrade import build_upgrade_plan
from .registry_authority import (
    REGISTRY_AUTHORITY_COMMANDS,
    handle_registry_authority_command,
    register_registry_authority_commands,
)
from .registry_admin_peer import (
    register_peer_runtime_arguments,
    register_peer_supervisor_arguments,
    render_register_agent_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]

REGISTRY_ADMIN_COMMANDS = {
    "configure-goal",
    "register-agent",
    "archive-runtime",
    "retire-global-goal",
    "uninstall-project",
    "sync-global",
    "migrate-state",
} | REGISTRY_AUTHORITY_COMMANDS


def explicit_global_registry(runtime_root_arg: str | None) -> Path:
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    return global_registry_path(runtime_root)


def register_agent_via_source_registry(
    *,
    runtime_root_arg: str | None,
    goal_id: str,
    agent_ids: list[str],
    execute: bool,
) -> dict[str, object]:
    global_path = explicit_global_registry(runtime_root_arg)
    if not global_path.exists():
        raise FileNotFoundError(f"global registry does not exist: {global_path}")
    global_registry = load_registry(global_path)
    goal = next((item for item in registry_goals(global_registry) if item.get("id") == goal_id), None)
    if goal is None:
        raise ValueError(f"goal_id not found in global registry: {goal_id}")
    source_registry = goal.get("source_registry")
    if not source_registry:
        raise ValueError(
            f"{goal_id}: global registry entry has no source_registry; "
            "use configure-goal with an explicit --registry instead of connect"
        )
    source_registry_path = Path(str(source_registry)).expanduser()
    source_payload = load_registry(source_registry_path)
    source_goal = next((item for item in registry_goals(source_payload) if item.get("id") == goal_id), None)
    if source_goal is None:
        raise ValueError(f"{goal_id}: source_registry does not contain the goal: {source_registry_path}")
    coordination = source_goal.get("coordination") if isinstance(source_goal.get("coordination"), dict) else {}
    existing_agents = normalize_registered_agents(coordination.get("registered_agents"))
    requested_agents = normalize_registered_agents(agent_ids)
    merged_agents = list(existing_agents)
    for agent_id in requested_agents:
        if agent_id not in merged_agents:
            merged_agents.append(agent_id)
    global_writability: dict[str, object] | None = None
    if execute:
        global_writability = probe_registry_write_path(global_path, create_parent=True)
        if not global_writability.get("ok"):
            return {
                "ok": False,
                "dry_run": False,
                "execute": True,
                "goal_id": goal_id,
                "global_registry": str(global_path),
                "source_registry": str(source_registry_path),
                "existing_agents": existing_agents,
                "requested_agents": requested_agents,
                "registered_agents": merged_agents,
                "changed": merged_agents != existing_agents,
                "written": False,
                "host_loop_activation": loop_activation_for_goal(
                    registry_path=global_path,
                    runtime_root_arg=runtime_root_arg,
                    goal_id=goal_id,
                ),
                "global_registry_writability": global_writability,
                "global_sync": {
                    "ok": False,
                    "enabled": True,
                    "wrote": False,
                    "write_denied": True,
                    "error_kind": "global_registry_write_denied",
                    "global_registry": str(global_path),
                    "global_registry_writability": global_writability,
                    "recommended_action": global_writability.get("recommended_action"),
                },
                "error": str(global_writability.get("error") or "global registry is not writable"),
                "recommended_action": global_writability.get("recommended_action"),
            }
    configure_payload = configure_goal(
        registry_path=source_registry_path,
        goal_id=goal_id,
        registered_agents=merged_agents,
        agent_model="peer_v1",
        execute=execute,
    )
    sync_payload: dict[str, object] | None = None
    if execute and configure_payload.get("written"):
        sync_payload = sync_project_registry_to_global(
            registry_path=source_registry_path,
            # Sync back to the same shared registry that supplied source_registry.
            # A project-local common_runtime_root must not redirect this write.
            runtime_root_override=str(global_path.parent),
            goal_id=goal_id,
            dry_run=False,
        )
    result = {
        "ok": bool(sync_payload.get("ok", True)) if isinstance(sync_payload, dict) else True,
        "dry_run": not execute,
        "execute": execute,
        "goal_id": goal_id,
        "global_registry": str(global_path),
        "source_registry": str(source_registry_path),
        "existing_agents": existing_agents,
        "requested_agents": requested_agents,
        "registered_agents": merged_agents,
        "changed": configure_payload.get("changed"),
        "written": configure_payload.get("written"),
        "configure_goal": configure_payload,
        "global_registry_writability": global_writability or {},
        "partial_write": bool(
            execute
            and configure_payload.get("written")
            and isinstance(sync_payload, dict)
            and sync_payload.get("ok") is False
        ),
        "recommended_action": (
            sync_payload.get("recommended_action")
            if isinstance(sync_payload, dict) and sync_payload.get("ok") is False
            else None
        ),
        "global_sync": sync_payload or {"enabled": bool(execute), "wrote": False},
    }
    result["host_loop_activation"] = loop_activation_for_goal(
        registry_path=global_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=goal_id,
    )
    return result


def loop_activation_for_goal(
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    goal_id: str,
) -> dict[str, object]:
    try:
        plan = build_upgrade_plan(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            goal_ids=[goal_id],
        )
        goals = plan.get("managed_heartbeats") if isinstance(plan.get("managed_heartbeats"), list) else []
        if not goals:
            return {
                "schema_version": "loopx_host_loop_activation_v0",
                "host_surface": "codex_app_heartbeat",
                "status": "unavailable",
                "activated": False,
                "recommended_action": (
                    "run loopx upgrade-plan for this goal; do not claim setup complete until "
                    "host_loop_activation.activated=true or a concrete host-tool gate is reported"
                ),
            }
        activation = goals[0].get("host_loop_activation")
        if isinstance(activation, dict):
            return activation
    except Exception as exc:
        return {
            "schema_version": "loopx_host_loop_activation_v0",
            "host_surface": "codex_app_heartbeat",
            "status": "error",
            "activated": False,
            "error": str(exc),
            "recommended_action": (
                "repair the host-loop activation check; do not claim setup complete until "
                "host_loop_activation.activated=true or a concrete host-tool gate is reported"
            ),
        }
    return {
        "schema_version": "loopx_host_loop_activation_v0",
        "host_surface": "codex_app_heartbeat",
        "status": "unknown",
        "activated": False,
        "recommended_action": (
            "create or update the Codex App heartbeat automation from loopx heartbeat-prompt"
        ),
    }


def register_registry_admin_commands(subparsers: argparse._SubParsersAction) -> None:
    configure_goal_parser = subparsers.add_parser(
        "configure-goal",
        help=(
            "Inspect current goal settings and optional features, or preview/apply an "
            "incremental configuration change."
        ),
        description=(
            "Inspect current per-goal settings, or preview/apply an incremental change. "
            "With no setting flags this is read-only and includes the on-demand optional "
            "feature catalog; first-run setup requires no optional configuration."
        ),
    )
    configure_goal_parser.add_argument("--goal-id", required=True, help="Goal id to configure.")
    configure_goal_parser.add_argument("--quota-compute", type=float, help="Per-goal quota compute multiplier.")
    configure_goal_parser.add_argument("--quota-window-hours", type=float, help="Quota rolling window in hours.")
    configure_goal_parser.add_argument(
        "--self-repair-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control_plane.self_repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-health",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control-plane health blocker repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-waiting-projection",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable waiting-projection repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--multi-subagent-feature",
        choices=["off", "enabled"],
        help=(
            "Default-off product switch for bounded child-agent orchestration. "
            "`enabled` maps to multi_subagent with spawn allowed; `off` maps to single-agent mode."
        ),
    )
    configure_goal_parser.add_argument(
        "--orchestration-mode",
        choices=["default", "multi_subagent"],
        help="Per-goal orchestration mode.",
    )
    configure_goal_parser.add_argument(
        "--spawn-allowed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow or block sub-agent spawning for this goal.",
    )
    configure_goal_parser.add_argument("--max-children", type=int, help="Maximum child agents for orchestration.")
    configure_goal_parser.add_argument(
        "--allowed-domain",
        action="append",
        default=None,
        help="Allowed child-agent domain. Repeatable; comma-separated values are also accepted.",
    )
    configure_goal_parser.add_argument(
        "--clear-allowed-domains",
        action="store_true",
        help="Clear allowed child-agent domains.",
    )
    configure_goal_parser.add_argument(
        "--explore-graph-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable or disable automatic Explore Graph projection at material "
            "refresh boundaries. This is independent from Explore Harness planning."
        ),
    )
    configure_goal_parser.add_argument(
        "--explore-harness-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable or disable analysis-only explore planning for this goal. "
            "This does not grant child-agent spawn permission."
        ),
    )
    configure_goal_parser.add_argument(
        "--explore-harness-profile",
        choices=EXPLORE_HARNESS_PROFILES,
        help="Pin the explore planner profile on this goal's orchestration boundary.",
    )
    configure_goal_parser.add_argument(
        "--clear-explore-harness-profile",
        action="store_true",
        help="Remove the goal-pinned explore profile while preserving the opt-in bit.",
    )
    configure_goal_parser.add_argument(
        "--registered-agent",
        dest="registered_agents",
        action="append",
        default=None,
        help=(
            "Registered public-safe agent id allowed to claim todos and receive scoped "
            "heartbeat prompts. Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-registered-agents",
        action="store_true",
        help="Clear coordination.registered_agents.",
    )
    configure_goal_parser.add_argument(
        "--agent-profile-json",
        dest="agent_profile_jsons",
        action="append",
        default=None,
        help=(
            "Validated agent_profile_v1 JSON object for a registered peer. "
            "Repeatable; writes advisory task routing hints plus the peer lane's "
            "vision requirement."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-agent-profile",
        dest="clear_agent_profiles",
        action="append",
        default=None,
        help="Registered agent id whose advisory profile should be removed. Repeatable.",
    )
    configure_goal_parser.add_argument(
        "--todo-lifecycle-authority-json",
        dest="todo_lifecycle_authority_jsons",
        action="append",
        default=None,
        help=(
            "JSON grant with agent_id, actions, and requires_reason for explicit "
            "cross-owner todo lifecycle overrides. Repeatable."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-todo-lifecycle-authority",
        action="append",
        default=None,
        help=(
            "Registered agent id whose todo lifecycle authority grant should be "
            "removed. Repeatable."
        ),
    )
    register_peer_runtime_arguments(configure_goal_parser)
    register_peer_supervisor_arguments(configure_goal_parser)
    configure_goal_parser.add_argument(
        "--write-scope",
        action="append",
        default=None,
        help=(
            "Allowed repository/local-state write scope to add to coordination.write_scope. "
            "Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--replace-write-scope",
        action="store_true",
        help="Replace coordination.write_scope with the supplied --write-scope values instead of merging.",
    )
    configure_goal_parser.add_argument(
        "--clear-write-scope",
        action="store_true",
        help="Clear coordination.write_scope.",
    )
    configure_goal_parser.add_argument(
        "--waiting-on",
        choices=["codex", "user_or_controller", "controller", "external_evidence"],
        help="Override registry waiting owner for status/quota routing.",
    )
    configure_goal_parser.add_argument(
        "--clear-waiting-on",
        action="store_true",
        help="Remove the registry waiting_on override.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-scope",
        action="append",
        default=None,
        help=(
            "Checkpointed write scope approved by an operator/controller decision. "
            "Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-source",
        help="Public-safe provenance for the checkpointed boundary authority.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-decision-id",
        help="Public-safe decision/run/gate id for the checkpointed boundary authority.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-recorded-at",
        help="ISO timestamp for the checkpointed decision. Defaults to now.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-expires-at",
        help="Optional ISO timestamp after which the checkpointed authority is no longer fresh.",
    )
    configure_goal_parser.add_argument(
        "--clear-boundary-authority",
        action="store_true",
        help="Clear coordination.checkpointed_boundary_authority.",
    )
    configure_goal_parser.add_argument(
        "--issue-fix-reviewer-notification-config",
        help=(
            "Register a repo-relative local-private JSON config pointer under "
            ".loopx/config/ for automatic issue-fix reviewer notifications."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-issue-fix-reviewer-notification-config",
        action="store_true",
        help="Remove the goal's automatic reviewer-notification config pointer.",
    )
    configure_goal_parser.add_argument(
        "--lark-event-inbox-config",
        help=(
            "Register a repo-relative local-private generic Lark event inbox "
            "config pointer under .loopx/config/."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-lark-event-inbox-config",
        action="store_true",
        help="Remove the goal's generic Lark event inbox config pointer.",
    )
    configure_goal_parser.add_argument(
        "--reward-memory-config",
        help=(
            "Register a repo-relative ignored provider-neutral Reward Memory "
            "experiment config under .loopx/config/."
        ),
    )
    configure_goal_parser.add_argument(
        "--reward-memory-agent",
        dest="reward_memory_agents",
        action="append",
        default=None,
        help=(
            "Registered agent id allowed to use the Reward Memory experiment. "
            "Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-reward-memory-config",
        action="store_true",
        help="Disable the Reward Memory experiment and clear its agent allowlist.",
    )
    configure_goal_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the registry. Without this flag, configure-goal is a dry-run preview.",
    )

    register_agent_parser = subparsers.add_parser(
        "register-agent",
        help="Register an automation agent through the existing global source_registry without reconnecting the goal.",
    )
    register_agent_parser.add_argument("--goal-id", required=True, help="Goal id already present in the global registry.")
    register_agent_parser.add_argument(
        "--agent-id",
        action="append",
        required=True,
        help="Public-safe agent id to add. Repeatable; comma-separated values are also accepted.",
    )
    register_agent_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the source registry and sync it globally. Without this flag, preview only.",
    )

    archive_runtime_parser = subparsers.add_parser(
        "archive-runtime",
        help="Move an obsolete runtime goal directory into the archive area. Defaults to dry-run.",
    )
    archive_runtime_parser.add_argument("--goal-id", required=True, help="Runtime goal id to archive.")
    archive_runtime_parser.add_argument(
        "--archive-root",
        help="Archive directory. Defaults to <runtime-root>/archived-goals.",
    )
    archive_runtime_parser.add_argument(
        "--allow-registered",
        action="store_true",
        help="Allow archiving a goal that is still present in the registry.",
    )
    archive_runtime_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move the runtime directory. Without this flag the command is a dry-run.",
    )

    retire_global_goal_parser = subparsers.add_parser(
        "retire-global-goal",
        help=(
            "Remove explicitly named obsolete goals from the global registry only when "
            "both source_registry and state_file are missing. Defaults to dry-run."
        ),
    )
    retire_global_goal_parser.add_argument(
        "--goal-id",
        action="append",
        required=True,
        help="Obsolete global goal id to retire. Repeat for multiple explicit goals.",
    )
    retire_global_goal_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write a full registry backup, then remove the eligible goals.",
    )

    uninstall_project_parser = subparsers.add_parser(
        "uninstall-project",
        help="Disconnect the current project from LoopX without uninstalling the LoopX CLI or other projects.",
    )
    uninstall_project_parser.add_argument(
        "--goal-id",
        action="append",
        default=None,
        help="Goal id to disconnect. Repeatable; defaults to every goal in this project registry.",
    )
    uninstall_project_parser.add_argument(
        "--archive-state",
        action="store_true",
        help="Move each selected project-local .codex/goals/<goal-id> state directory into .loopx/archived-project-state/.",
    )
    uninstall_project_parser.add_argument(
        "--remove-empty-registry",
        action="store_true",
        help="Remove .loopx/registry.json when all local goals are uninstalled. A backup is written first on --execute.",
    )
    uninstall_project_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write registry changes. Without this flag, uninstall-project is a dry-run preview.",
    )

    sync_global_parser = subparsers.add_parser(
        "sync-global",
        help="Merge this project-local registry into the shared global registry.",
    )
    sync_global_parser.add_argument("--goal-id", help="Only sync one goal id from the source registry.")
    sync_global_parser.add_argument(
        "--replace-state",
        action="store_true",
        help="Allow replacing an existing global route and write a backup before doing so.",
    )
    sync_global_parser.add_argument("--dry-run", action="store_true", help="Preview the global registry merge.")

    migrate_state_parser = subparsers.add_parser(
        "migrate-state",
        help="One-shot migration from a legacy Goal Harness registry/runtime into LoopX state.",
    )
    migrate_state_parser.add_argument(
        "--legacy-registry",
        default=str(LEGACY_GLOBAL_REGISTRY),
        help="Legacy registry JSON to import from. Defaults to ~/.codex/goal-harness/registry.global.json.",
    )
    migrate_state_parser.add_argument(
        "--legacy-runtime-root",
        default=str(LEGACY_RUNTIME_ROOT),
        help="Legacy runtime root. Defaults to ~/.codex/goal-harness.",
    )
    migrate_state_parser.add_argument(
        "--target-runtime-root",
        help="LoopX runtime root. Defaults to --runtime-root or ~/.codex/loopx.",
    )
    migrate_goal_selector = migrate_state_parser.add_mutually_exclusive_group(required=True)
    migrate_goal_selector.add_argument(
        "--goal-id",
        action="append",
        help="Legacy goal id to migrate. Repeat for multiple explicit goals.",
    )
    migrate_goal_selector.add_argument(
        "--all-goals",
        action="store_true",
        help="Migrate every goal listed in the explicit legacy registry. Still dry-run by default.",
    )
    migrate_state_parser.add_argument(
        "--goal-id-map",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Rename a goal id during migration, for example goal-harness-meta=loopx-meta.",
    )
    migrate_state_parser.add_argument(
        "--path-map",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Rewrite local path prefixes during migration.",
    )
    migrate_state_parser.add_argument(
        "--copy-active-state",
        action="store_true",
        help="Copy and rewrite selected goals' active-state files into their migrated target paths.",
    )
    migrate_state_parser.add_argument(
        "--copy-runtime",
        action="store_true",
        help="Copy and rewrite selected runtime goal directories from the legacy runtime root.",
    )
    migrate_state_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not sync the migrated project registry into the LoopX global registry after --execute.",
    )
    migrate_state_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write migrated state. Without this flag the command is a dry-run preview.",
    )

    register_registry_authority_commands(subparsers)


def handle_registry_admin_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
) -> int | None:
    if args.command not in REGISTRY_ADMIN_COMMANDS:
        return None

    if args.command == "configure-goal":
        try:
            agent_profiles = [
                json.loads(raw_profile)
                for raw_profile in (args.agent_profile_jsons or [])
            ]
            todo_lifecycle_authority = [
                json.loads(raw_grant)
                for raw_grant in (args.todo_lifecycle_authority_jsons or [])
            ]
            payload = configure_goal_with_global_sync(
                registry_path=registry_path,
                goal_id=args.goal_id,
                runtime_root_override=args.runtime_root,
                quota_compute=args.quota_compute,
                quota_window_hours=args.quota_window_hours,
                self_repair_enabled=args.self_repair_enabled,
                self_repair_health=args.self_repair_health,
                self_repair_waiting_projection=args.self_repair_waiting_projection,
                multi_subagent_feature=args.multi_subagent_feature,
                orchestration_mode=args.orchestration_mode,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                clear_allowed_domains=bool(args.clear_allowed_domains),
                explore_harness_enabled=args.explore_harness_enabled,
                explore_harness_profile=args.explore_harness_profile,
                clear_explore_harness_profile=bool(args.clear_explore_harness_profile),
                explore_graph_enabled=args.explore_graph_enabled,
                registered_agents=args.registered_agents,
                clear_registered_agents=bool(args.clear_registered_agents),
                agent_profiles=agent_profiles,
                clear_agent_profiles=args.clear_agent_profiles,
                todo_lifecycle_authority=todo_lifecycle_authority,
                clear_todo_lifecycle_authority=(
                    args.clear_todo_lifecycle_authority
                ),
                agent_model=args.agent_model,
                automation_prompt_migration_ack=args.ack_automation_prompt_migration,
                supervisor_agent=args.supervisor_agent,
                supervised_agents=args.supervised_agents,
                clear_supervisor=bool(args.clear_supervisor),
                write_scope=args.write_scope,
                replace_write_scope=bool(args.replace_write_scope),
                clear_write_scope=bool(args.clear_write_scope),
                waiting_on=args.waiting_on,
                clear_waiting_on=bool(args.clear_waiting_on),
                boundary_authority_scopes=args.boundary_authority_scope,
                boundary_authority_source=args.boundary_authority_source,
                boundary_authority_decision_id=args.boundary_authority_decision_id,
                boundary_authority_recorded_at=args.boundary_authority_recorded_at,
                boundary_authority_expires_at=args.boundary_authority_expires_at,
                clear_boundary_authority=bool(args.clear_boundary_authority),
                issue_fix_reviewer_notification_config=(
                    args.issue_fix_reviewer_notification_config
                ),
                clear_issue_fix_reviewer_notification_config=bool(
                    args.clear_issue_fix_reviewer_notification_config
                ),
                lark_event_inbox_config=args.lark_event_inbox_config,
                clear_lark_event_inbox_config=bool(
                    args.clear_lark_event_inbox_config
                ),
                reward_memory_config=args.reward_memory_config,
                reward_memory_agents=args.reward_memory_agents,
                clear_reward_memory_config=bool(
                    args.clear_reward_memory_config
                ),
                execute=bool(args.execute),
            )
            if payload.get("ok"):
                payload["host_loop_activation"] = loop_activation_for_goal(
                    registry_path=registry_path,
                    runtime_root_arg=args.runtime_root,
                    goal_id=args.goal_id,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "registry": str(registry_path),
                "goal_id": args.goal_id,
                "changed": False,
                "written": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_configure_goal_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "register-agent":
        try:
            payload = register_agent_via_source_registry(
                runtime_root_arg=args.runtime_root,
                goal_id=args.goal_id,
                agent_ids=args.agent_id,
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "goal_id": args.goal_id,
                "changed": False,
                "written": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_register_agent_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "archive-runtime":
        try:
            payload = archive_runtime_goal(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                archive_root=Path(args.archive_root).expanduser() if args.archive_root else None,
                allow_registered=bool(args.allow_registered),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "dry_run": not bool(args.execute),
                "archived": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_archive_runtime_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "retire-global-goal":
        try:
            payload = retire_global_registry_goals(
                runtime_root_override=args.runtime_root,
                goal_ids=args.goal_id,
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_global_goal_retirement_v0",
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "requested_goal_ids": args.goal_id or [],
                "retired_goal_ids": [],
                "wrote": False,
                "backup_written": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_global_goal_retirement_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "uninstall-project":
        try:
            payload = uninstall_project(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_ids=args.goal_id,
                archive_state=bool(args.archive_state),
                remove_empty_registry=bool(args.remove_empty_registry),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_project_uninstall_v0",
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "registry": str(registry_path),
                "goal_ids": args.goal_id or [],
                "wrote_local_registry": False,
                "wrote_global_registry": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_project_uninstall_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "sync-global":
        try:
            payload = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                dry_run=bool(args.dry_run),
                allow_route_replacement=bool(args.replace_state),
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": str(runtime_root),
                "global_registry": str(global_registry_path(runtime_root)),
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_global_sync_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "migrate-state":
        try:
            target_runtime_root = (
                Path(args.target_runtime_root).expanduser()
                if args.target_runtime_root
                else (Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT)
            )
            selected_goal_ids = (
                legacy_registry_goal_ids(Path(args.legacy_registry))
                if args.all_goals
                else (args.goal_id or [])
            )
            payload = migrate_legacy_state(
                legacy_registry_path=Path(args.legacy_registry),
                target_registry_path=registry_path,
                legacy_runtime_root=Path(args.legacy_runtime_root),
                target_runtime_root=target_runtime_root,
                goal_ids=selected_goal_ids,
                goal_id_map=parse_key_value_map(args.goal_id_map, flag_name="--goal-id-map"),
                path_map=parse_key_value_map(args.path_map, flag_name="--path-map"),
                copy_active_state=bool(args.copy_active_state),
                copy_runtime=bool(args.copy_runtime),
                execute=bool(args.execute),
            )
            if payload.get("ok") and args.execute and not args.no_global_sync:
                sync_results = []
                for migrated_goal_id in payload.get("migrated_goal_ids") or []:
                    sync_results.append(
                        sync_project_registry_to_global(
                            registry_path=registry_path,
                            runtime_root_override=str(target_runtime_root),
                            goal_id=str(migrated_goal_id),
                            dry_run=False,
                        )
                    )
                payload["global_sync"] = {
                    "ok": all(result.get("ok") for result in sync_results),
                    "dry_run": False,
                    "wrote": bool(sync_results),
                    "results": sync_results,
                    "synced_goal_ids": [
                        goal_id
                        for result in sync_results
                        for goal_id in (result.get("synced_goal_ids") or [])
                    ],
                }
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "loopx_state_migration_v0",
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "legacy_registry": args.legacy_registry,
                "target_registry": str(registry_path),
                "legacy_runtime_root": args.legacy_runtime_root,
                "target_runtime_root": args.target_runtime_root or args.runtime_root or str(DEFAULT_RUNTIME_ROOT),
                "selected_goal_ids": args.goal_id or ([] if not getattr(args, "all_goals", False) else ["<all-goals>"]),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_state_migration_markdown)
        return 0 if payload.get("ok") else 1

    return handle_registry_authority_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
