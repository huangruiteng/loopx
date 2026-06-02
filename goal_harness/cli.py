from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from .contract import check_contract, render_contract_markdown
from .doctor import collect_doctor, render_doctor_markdown
from .feedback import append_human_reward, compact_reward, render_reward_markdown
from .global_registry import render_global_sync_markdown, sync_project_registry_to_global
from .heartbeat_prompt import build_heartbeat_prompt, render_heartbeat_prompt_markdown
from .history import collect_history, load_registry, render_history_markdown
from .operator_gate import (
    DEFAULT_OPERATOR_GATE,
    OPERATOR_GATE_DECISIONS,
    record_operator_gate,
    render_operator_gate_markdown,
)
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path, resolve_runtime_root
from .project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    build_new_project_prompt,
    render_new_project_prompt_markdown,
)
from .project_map import (
    DEFAULT_PROJECT_MAP_CLASSIFICATION,
    read_only_project_map_run,
    render_read_only_project_map_markdown,
)
from .quota import (
    build_quota_plan,
    build_quota_should_run,
    render_quota_markdown,
    render_quota_should_run_markdown,
    render_quota_slot_preview_markdown,
    spend_quota_slot,
)
from .registry import inspect_registry, render_registry_markdown
from .review_packet import build_review_packet, render_review_packet_markdown
from .runtime import archive_runtime_goal, render_archive_runtime_markdown
from .state_refresh import (
    DEFAULT_REFRESH_ACTION,
    DEFAULT_REFRESH_CLASSIFICATION,
    refresh_state_run,
    render_state_refresh_markdown,
)
from .status import collect_status, render_status_markdown
from .status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def user_supplied_registry(argv: list[str] | None) -> bool:
    values = sys.argv[1:] if argv is None else argv
    return any(value == "--registry" or value.startswith("--registry=") for value in values)


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal Harness control-plane helper.")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = sub.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE, help="Initial goal objective.")
    bootstrap_parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Goal domain label.")
    bootstrap_parser.add_argument("--role", choices=["controller", "subagent"], default="controller")
    bootstrap_parser.add_argument("--parent-goal-id", help="Parent goal id when --role subagent.")
    bootstrap_parser.add_argument("--state-file", help="Active goal state path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--goal-doc", help="Primary goal document path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--adapter-kind", default="generic_project_goal_v0")
    bootstrap_parser.add_argument("--adapter-status", default="connected")
    bootstrap_parser.add_argument("--next-probe", help="Optional project-specific pre-tick command.")
    bootstrap_parser.add_argument("--spawn-allowed", action="store_true", help="Declare that this controller may spawn child agents.")
    bootstrap_parser.add_argument("--max-children", type=int, default=3)
    bootstrap_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    bootstrap_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")
    bootstrap_parser.add_argument("--claim-ttl-minutes", type=int, default=30)
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    bootstrap_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not merge this project registry into the shared global registry.",
    )

    prompt_parser = sub.add_parser(
        "new-project-prompt",
        help="Generate a copy-paste Codex prompt for connecting a project from a goal document.",
    )
    prompt_parser.add_argument("--project", required=True, help="Project directory the target Codex session can access.")
    prompt_parser.add_argument("--goal-doc", required=True, help="Goal document path for the target project.")
    prompt_parser.add_argument("--goal-id", help="Initial stable goal id. Defaults to <project-name>-goal.")
    prompt_parser.add_argument("--objective", help="Initial objective. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--domain", help="Initial domain label. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--adapter-kind", default=DEFAULT_HANDOFF_ADAPTER_KIND)
    prompt_parser.add_argument("--adapter-status", default=DEFAULT_HANDOFF_ADAPTER_STATUS)
    prompt_parser.add_argument("--next-probe", help="Optional read-only pre-tick command for the target project.")
    prompt_parser.add_argument("--spawn-allowed", action="store_true", help="Include controller/sub-agent flags.")
    prompt_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    prompt_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")

    heartbeat_prompt_parser = sub.add_parser(
        "heartbeat-prompt",
        help="Generate a guarded Codex App heartbeat automation task body.",
    )
    heartbeat_prompt_parser.add_argument("--goal-id", required=True, help="Stable Goal Harness goal id.")
    heartbeat_prompt_parser.add_argument(
        "--active-state",
        required=True,
        help="Active goal state file the heartbeat should read and write back.",
    )
    heartbeat_prompt_parser.add_argument(
        "--material-rule",
        help="Optional project-specific material queue rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--permission-rule",
        help="Optional trusted-session permission rule appended to the task body.",
    )

    sub.add_parser("doctor", help="Diagnose local CLI installation, PATH, wrapper, and import health.")

    sub.add_parser("registry", help="Inspect registry goals and adapter declarations.")

    history_parser = sub.add_parser("history", help="Read compact run history from the shared runtime root.")
    history_parser.add_argument("--goal-id", help="Only show one goal.")
    history_parser.add_argument("--limit", type=int, default=10)

    archive_runtime_parser = sub.add_parser(
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

    sync_global_parser = sub.add_parser(
        "sync-global",
        help="Merge this project-local registry into the shared global registry.",
    )
    sync_global_parser.add_argument("--goal-id", help="Only sync one goal id from the source registry.")
    sync_global_parser.add_argument("--dry-run", action="store_true", help="Preview the global registry merge.")

    refresh_state_parser = sub.add_parser(
        "refresh-state",
        help="Append a read-only run from active goal state after state-only updates.",
    )
    refresh_state_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose active state should be refreshed.",
    )
    refresh_state_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    refresh_state_parser.add_argument(
        "--state-file",
        help="Active goal state path. Defaults to the registry goal state_file.",
    )
    refresh_state_parser.add_argument(
        "--classification",
        default=DEFAULT_REFRESH_CLASSIFICATION,
        help=f"Refresh run classification. Defaults to {DEFAULT_REFRESH_CLASSIFICATION}.",
    )
    refresh_state_parser.add_argument(
        "--recommended-action",
        help=f"Public-safe next action. Defaults to: {DEFAULT_REFRESH_ACTION}",
    )
    refresh_state_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the refresh payload without appending.",
    )
    refresh_state_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the state run.",
    )

    read_only_map_parser = sub.add_parser(
        "read-only-map",
        help="Append a generic read-only project-map run for a connected project.",
    )
    read_only_map_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose project should be mapped.",
    )
    read_only_map_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    read_only_map_parser.add_argument(
        "--state-file",
        help="Active goal state path. Defaults to the registry goal state_file.",
    )
    read_only_map_parser.add_argument(
        "--classification",
        default=DEFAULT_PROJECT_MAP_CLASSIFICATION,
        help=f"Project-map run classification. Defaults to {DEFAULT_PROJECT_MAP_CLASSIFICATION}.",
    )
    read_only_map_parser.add_argument(
        "--recommended-action",
        help="Public-safe next action. Defaults to the first public-safe item from the active state's Next Action.",
    )
    read_only_map_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the project-map payload without appending.",
    )
    read_only_map_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the project-map run.",
    )

    reward_parser = sub.add_parser(
        "reward",
        help="Append a compact human reward overlay to a goal run index.",
    )
    reward_parser.add_argument("--goal-id", required=True, help="Goal id whose latest run should receive feedback.")
    reward_parser.add_argument(
        "--run-generated-at",
        help="Exact run generated_at timestamp. Defaults to the latest compact run for the goal.",
    )
    reward_parser.add_argument("--recorded-at", help="Reward timestamp. Defaults to current UTC time.")
    reward_parser.add_argument("--decision", required=True, help="Operator decision label, such as continue_route.")
    reward_parser.add_argument(
        "--reward",
        required=True,
        choices=["positive", "negative", "mixed", "neutral"],
        help="Compact reward polarity.",
    )
    reward_parser.add_argument(
        "--reason-summary",
        required=True,
        help="Short public-safe reason. Do not include raw private evidence.",
    )
    reward_parser.add_argument("--follow-up", help="Optional next handoff or experiment condition.")
    reward_parser.add_argument(
        "--state-file",
        help="Active goal state path for optional summary writeback. Defaults to the registry goal state_file.",
    )
    reward_parser.add_argument(
        "--write-active-state-summary",
        action="store_true",
        help="After a real append, also add the returned active_state_summary to the active state's Progress Ledger. With --dry-run, preview only.",
    )
    reward_parser.add_argument("--dry-run", action="store_true", help="Print the overlay without appending it.")

    gate_parser = sub.add_parser(
        "operator-gate",
        help="Record an operator gate decision such as read-only map opt-in.",
    )
    gate_parser.add_argument("--goal-id", required=True, help="Goal id whose operator gate is being judged.")
    gate_parser.add_argument("--gate", default=DEFAULT_OPERATOR_GATE, help=f"Gate id. Defaults to {DEFAULT_OPERATOR_GATE}.")
    gate_parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(OPERATOR_GATE_DECISIONS),
        help="Operator decision for this gate.",
    )
    gate_parser.add_argument("--recorded-at", help="Decision timestamp. Defaults to current local time.")
    gate_parser.add_argument(
        "--operator-question",
        help="Human-facing question being answered. Defaults from --gate and --goal-id.",
    )
    gate_parser.add_argument(
        "--reason-summary",
        required=True,
        help="Short public-safe reason. Do not include raw private evidence.",
    )
    gate_parser.add_argument("--follow-up", help="Optional next handoff or evidence condition.")
    gate_parser.add_argument(
        "--agent-command",
        help="Target-agent command that becomes valid after approval. Defaults for read_only_map_opt_in approvals.",
    )
    gate_parser.add_argument("--recommended-action", help="Public-safe next action for status/dashboard.")
    gate_parser.add_argument("--dry-run", action="store_true", help="Print the decision run without appending it.")
    gate_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the gate decision.",
    )

    check_parser = sub.add_parser("check", help="Run a read-only contract and public/private boundary check.")
    check_parser.add_argument("--scan-root", default=".", help="Public files to scan for obvious private material.")
    check_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    check_parser.add_argument("--limit", type=int, default=5)

    status_parser = sub.add_parser("status", help="Show a first-screen goal status and attention queue.")
    status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    status_parser.add_argument("--limit", type=int, default=5)

    review_packet_parser = sub.add_parser(
        "review-packet",
        help="Generate a CLI-visible Review Packet from the current status contract.",
    )
    review_packet_parser.add_argument("--goal-id", required=True, help="Goal id to package for review or handoff.")
    review_packet_parser.add_argument(
        "--action-kind",
        choices=["reward", "controller", "codex", "evidence", "health"],
        help="Override inferred action kind. Defaults to the goal's current attention item.",
    )
    review_packet_parser.add_argument("--review-url", help="Optional dashboard review URL to include in the packet.")
    review_packet_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    review_packet_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    review_packet_parser.add_argument("--limit", type=int, default=5)

    quota_parser = sub.add_parser(
        "quota",
        help="Show agent-facing compute quota status or next-turn plan.",
    )
    quota_parser.add_argument(
        "quota_command",
        nargs="?",
        choices=["status", "plan", "should-run", "spend-slot"],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, or spend-slot for a slot accounting preview/write.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for `quota should-run` and `quota spend-slot`.")
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument("--source", choices=["heartbeat", "controller", "adapter"], default="heartbeat", help="Source label for `quota spend-slot`.")
    quota_parser.add_argument("--dry-run", action="store_true", help="Keep `quota spend-slot` as preview-only. This is the default.")
    quota_parser.add_argument("--execute", action="store_true", help="Append the compact quota_slot_spent runtime event for `quota spend-slot`.")
    quota_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    quota_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    quota_parser.add_argument("--limit", type=int, default=5)

    serve_status_parser = sub.add_parser("serve-status", help="Serve live status JSON for the local dashboard.")
    serve_status_parser.add_argument("--host", default=DEFAULT_STATUS_HOST, help="Bind host. Defaults to localhost only.")
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status JSON route.")
    serve_status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    serve_status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    serve_status_parser.add_argument("--limit", type=int, default=5)
    serve_status_parser.add_argument("--verbose", action="store_true", help="Print HTTP request logs.")

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {"bootstrap", "connect", "doctor", "new-project-prompt", "heartbeat-prompt", "sync-global"}
        and not user_supplied_registry(argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    if args.command in {"bootstrap", "connect"}:
        try:
            runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            state_file = Path(args.state_file).expanduser() if args.state_file else None
            goal_doc = Path(args.goal_doc).expanduser() if args.goal_doc else None
            payload = bootstrap_project(
                project=Path(args.project),
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
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
                force=args.force,
                dry_run=args.dry_run,
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_bootstrap_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "new-project-prompt":
        payload = build_new_project_prompt(
            project=Path(args.project),
            goal_doc=Path(args.goal_doc),
            goal_id=args.goal_id,
            objective=args.objective,
            domain=args.domain,
            adapter_kind=args.adapter_kind,
            adapter_status=args.adapter_status,
            next_probe=args.next_probe,
            spawn_allowed=bool(args.spawn_allowed),
            allowed_domains=args.allowed_domain,
            write_scope=args.write_scope,
        )
        print_payload(payload, args.format, render_new_project_prompt_markdown)
        return 0

    if args.command == "heartbeat-prompt":
        payload = build_heartbeat_prompt(
            goal_id=args.goal_id,
            active_state=Path(args.active_state),
            material_queue_rule=args.material_rule,
            permission_rule=args.permission_rule,
        )
        print_payload(payload, args.format, render_heartbeat_prompt_markdown)
        return 0

    if args.command == "doctor":
        payload = collect_doctor()
        print_payload(payload, args.format, render_doctor_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry":
        payload = inspect_registry(registry_path)
        print_payload(payload, args.format, render_registry_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "history":
        try:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = collect_history(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_history_markdown)
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

    if args.command == "sync-global":
        try:
            payload = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                dry_run=bool(args.dry_run),
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

    if args.command == "refresh-state":
        try:
            payload = refresh_state_run(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                classification=args.classification,
                recommended_action=args.recommended_action,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "classification": args.classification,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_state_refresh_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "read-only-map":
        try:
            payload = read_only_project_map_run(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                classification=args.classification,
                recommended_action=args.recommended_action,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "classification": args.classification,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_read_only_project_map_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "reward":
        try:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
            )
            payload = append_human_reward(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                run_generated_at=args.run_generated_at,
                reward=reward,
                dry_run=bool(args.dry_run),
                state_file_override=Path(args.state_file).expanduser() if args.state_file else None,
                write_active_state_summary=bool(args.write_active_state_summary),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_reward_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "operator-gate":
        try:
            payload = record_operator_gate(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                gate=args.gate,
                decision=args.decision,
                operator_question=args.operator_question,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
                agent_command=args.agent_command,
                recommended_action=args.recommended_action,
                recorded_at=args.recorded_at,
                dry_run=bool(args.dry_run),
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "appended": False,
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_operator_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "check":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = check_contract(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "scan_roots": args.scan_path or [args.scan_root],
                "summary": {"errors": 1, "warnings": 0, "checks": 0},
                "errors": [str(exc)],
                "warnings": [],
                "checks": [],
            }
        print_payload(payload, args.format, render_contract_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "status":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "attention_queue": {
                    "available": False,
                    "item_count": 1,
                    "needs_user_or_controller": 0,
                    "needs_codex": 1,
                    "watching_external_evidence": 0,
                    "items": [
                        {
                            "goal_id": "goal-harness-status",
                            "status": "status_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "status",
                        }
                    ],
                },
            }
        print_payload(payload, args.format, render_status_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "review-packet":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
            payload = build_review_packet(
                status_payload,
                goal_id=args.goal_id,
                action_kind=args.action_kind,
                review_url=args.review_url,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "goal_id": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_review_packet_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "quota":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
            )
            if args.quota_command == "should-run":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota should-run` requires --goal-id")
                payload = build_quota_should_run(status_payload, goal_id=args.goal_id)
            elif args.quota_command == "spend-slot":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota spend-slot` requires --goal-id")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota spend-slot` accepts only one of --dry-run or --execute")
                payload = spend_quota_slot(
                    status_payload,
                    goal_id=args.goal_id,
                    slots=args.slots,
                    execute=bool(args.execute),
                    source=args.source,
                )
            else:
                payload = build_quota_plan(status_payload, mode=args.quota_command)
        except Exception as exc:
            if args.quota_command in {"should-run", "spend-slot"}:
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
            else:
                payload = {
                    "ok": False,
                    "mode": args.quota_command,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
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
                            "goal_id": "goal-harness-quota",
                            "status": "quota_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "quota",
                        }
                    ],
                }
        renderer = (
            render_quota_should_run_markdown
            if args.quota_command == "should-run"
            else render_quota_slot_preview_markdown
            if args.quota_command == "spend-slot"
            else render_quota_markdown
        )
        print_payload(payload, args.format, renderer)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            serve_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                status_path=args.path,
                verbose=bool(args.verbose),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
