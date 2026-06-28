from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..todo_suggestion_prompt import (
    ALLOWED_TODO_SUGGESTION_SOURCES,
    ALLOWED_TODO_SUGGESTION_TRIGGERS,
    build_todo_suggestion_prompt_packet,
    render_todo_suggestion_prompt_markdown,
)
from ..todo_followups import capture_followup_todos
from ..todos import (
    archive_completed_todos,
    add_goal_todo,
    complete_goal_todo,
    list_goal_todos,
    render_todo_markdown,
    supersede_goal_todo,
    update_goal_todo,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
RolloutEventAppender = Callable[..., dict[str, object]]


def register_todo_command(subparsers: argparse._SubParsersAction) -> None:
    todo_parser = subparsers.add_parser(
        "todo",
        help="Add a user or agent todo to a goal's active state.",
    )
    todo_parser.add_argument(
        "todo_command",
        nargs="?",
        choices=[
            "add",
            "list",
            "claim",
            "update",
            "complete",
            "supersede",
            "archive-completed",
            "suggest",
            "capture-followups",
        ],
        default="add",
        help=(
            "Use add to append a checkbox todo, claim to soft-claim by registered "
            "agent id, list to read projected todos, update/complete/supersede to transition by todo_id, or "
            "archive-completed to move older completed todos into Completed Work Archive. "
            "Use suggest to generate an agent-facing candidate todo analysis prompt without writing state. "
            "Use capture-followups to record a capped public-safe unclaimed follow-up batch."
        ),
    )
    todo_parser.add_argument("--goal-id", required=True, help="Goal id whose active state should receive the todo.")
    todo_parser.add_argument("--role", choices=["user", "agent"], help="Todo owner. Required for add; optional todo_id search scope for lifecycle commands. Defaults to agent for archive-completed.")
    todo_parser.add_argument("--text", help="Todo text. Required for add; keep it short and public-safe enough for local status.")
    todo_parser.add_argument(
        "--follow-up",
        dest="followups",
        action="append",
        help="For capture-followups, append one public-safe agent follow-up todo. Repeat up to the requested batch.",
    )
    todo_parser.add_argument("--todo-id", help="Structured todo id from status/quota, such as todo_ab12cd34ef56.")
    todo_parser.add_argument("--status", choices=["open", "done", "blocked", "deferred"], help="For todo update, set the lifecycle status by todo_id.")
    todo_parser.add_argument("--note", help="Public-safe note to attach to a lifecycle transition.")
    todo_parser.add_argument("--evidence", help="Public-safe evidence pointer or short result for complete/update.")
    todo_parser.add_argument("--reason", help="Public-safe reason for blocked/deferred/supersede transitions.")
    todo_parser.add_argument(
        "--task-class",
        choices=["advancement_task", "continuous_monitor", "user_gate", "blocker"],
        help=(
            "For todo add/update, explicitly register the routing lane. Use "
            "advancement_task for executable delivery work; continuous_monitor, "
            "user_gate, and blocker are non-executable lanes."
        ),
    )
    todo_parser.add_argument(
        "--action-kind",
        help=(
            "For todo add, optional public-safe action token such as run_eval, "
            "rebuild_score, compact_blocker_writeback, or monitor."
        ),
    )
    todo_parser.add_argument(
        "--required-write-scope",
        dest="required_write_scopes",
        action="append",
        help=(
            "For todo add/update, declare a required relative write scope such as "
            "src/** or runners/openviking/**. Repeat for multiple scopes."
        ),
    )
    todo_parser.add_argument(
        "--required-capability",
        dest="required_capabilities",
        action="append",
        help=(
            "For todo add/update, declare an execution capability such as shell, "
            "filesystem_write, network, benchmark_runner, or external_evidence_poll. "
            "Repeat for multiple capabilities."
        ),
    )
    todo_parser.add_argument(
        "--target-capability",
        dest="target_capabilities",
        action="append",
        help=(
            "For todo add/update, declare a capability this todo is building, "
            "repairing, materializing, or parity-checking. This is not a hard "
            "execution prerequisite."
        ),
    )
    todo_parser.add_argument(
        "--decision-scope",
        help=(
            "For user_gate add/update, declare the concrete decision as "
            "kind:granularity:scope_key, for example direction:action:benchmark_target."
        ),
    )
    todo_parser.add_argument(
        "--required-decision-scope",
        dest="required_decision_scopes",
        action="append",
        help=(
            "For agent todo add/update, declare a required decision scope as "
            "kind:granularity:scope_key. Repeat for multiple scopes."
        ),
    )
    todo_parser.add_argument(
        "--claimed-by",
        help=(
            "For todo add/claim/update/complete, soft-claim the todo for a registered "
            "public-safe agent id such as codex-main-control."
        ),
    )
    todo_parser.add_argument(
        "--blocks-agent",
        help=(
            "For todo add/update, mark that this todo unblocks a registered agent, "
            "for example codex-side-bypass."
        ),
    )
    todo_parser.add_argument(
        "--global-gate",
        action="store_true",
        help=(
            "For todo add/update on role=user task-class=user_gate, explicitly mark "
            "that the gate blocks every registered agent. Prefer --blocks-agent or "
            "--agent-id when only one lane is waiting."
        ),
    )
    todo_parser.add_argument(
        "--unblocks-todo-id",
        help=(
            "For todo add/update, link this todo to the blocked todo it unblocks, "
            "for example todo_ab12cd34ef56."
        ),
    )
    todo_parser.add_argument(
        "--resume-when",
        help=(
            "For deferred todo add/update, declare a machine-readable resume condition "
            "such as todo_done:todo_ab12cd34ef56."
        ),
    )
    todo_parser.add_argument(
        "--monitor-target-key",
        dest="monitor_target_key",
        help=(
            "For agent continuous_monitor add/update, declare the stable public-safe "
            "watch target key, such as github-pr-123 or update-note-draft-pr."
        ),
    )
    todo_parser.add_argument(
        "--cadence",
        help=(
            "For agent continuous_monitor add/update, declare the monitor cadence, "
            "such as 30m, 2h, or 1d."
        ),
    )
    todo_parser.add_argument(
        "--next-due-at",
        dest="next_due_at",
        help=(
            "For agent continuous_monitor add/update, declare the next due ISO "
            "timestamp; due monitor scheduling is based on this field."
        ),
    )
    todo_parser.add_argument(
        "--expires-at",
        dest="expires_at",
        help=(
            "For agent continuous_monitor add/update, declare the ISO timestamp "
            "after which the monitor is no longer due and must not catch up."
        ),
    )
    todo_parser.add_argument(
        "--clear-claim",
        action="store_true",
        help="For todo update, remove the soft claimed_by owner from the todo.",
    )
    todo_parser.add_argument(
        "--no-follow-up",
        action="store_true",
        help=(
            "For todo update/complete, record a structured no-follow-up rationale "
            "when a completed todo intentionally has no successor."
        ),
    )
    todo_parser.add_argument("--next-agent-todo", help="For complete/supersede, atomically add or update the next agent todo.")
    todo_parser.add_argument("--next-user-todo", help="For complete/supersede, atomically add or update the next user todo.")
    todo_parser.add_argument(
        "--next-claimed-by",
        help=(
            "For complete/supersede with --next-agent-todo, soft-claim the successor "
            "todo for a registered agent. If omitted, claimed successors inherit the "
            "completed/superseded todo owner when available; broad side-agent handoffs "
            "default to coordination.side_agent_handoff_agent when configured, otherwise "
            "primary_agent. Same-agent broad handoff is rejected; use "
            "--side-agent-self-merged with --evidence for same-agent delivery."
        ),
    )
    todo_parser.add_argument(
        "--side-agent-self-merged",
        action="store_true",
        help=(
            "For todo complete by a side agent, explicitly record that a small validated "
            "side-agent change was self-merged; requires --evidence and bypasses the "
            "default review successor todo."
        ),
    )
    todo_parser.add_argument(
        "--next-task-class",
        choices=["advancement_task", "continuous_monitor", "user_gate", "blocker"],
        help="Task class for --next-agent-todo. Defaults to advancement_task.",
    )
    todo_parser.add_argument("--next-action-kind", help="Action kind for --next-agent-todo.")
    todo_parser.add_argument(
        "--max-active-done",
        type=int,
        default=12,
        help="For archive-completed, keep this many completed todos in the active section.",
    )
    todo_parser.add_argument(
        "--agent-id",
        help=(
            "For todo add/update on role=user task-class=user_gate, mark the "
            "authoring registered agent; when --blocks-agent is omitted, the "
            "gate blocks this agent. For todo suggest, name the project agent "
            "that should perform the repository analysis."
        ),
    )
    todo_parser.add_argument(
        "--from",
        dest="suggestion_sources",
        choices=ALLOWED_TODO_SUGGESTION_SOURCES,
        action="append",
        help="For todo suggest, include a source lane for agent analysis. Repeat for multiple lanes.",
    )
    todo_parser.add_argument(
        "--limit",
        dest="suggestion_limit",
        type=int,
        help="For todo suggest, maximum candidate count. Values above 5 are clamped to 5.",
    )
    todo_parser.add_argument(
        "--trigger",
        dest="suggestion_trigger",
        choices=ALLOWED_TODO_SUGGESTION_TRIGGERS,
        help="For todo suggest, why this candidate queue is being requested.",
    )
    todo_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    todo_parser.add_argument("--state-file", help="Active goal state path. Defaults to the registry goal state_file.")
    todo_parser.add_argument("--dry-run", action="store_true", help="Preview the active-state edit without writing.")
    todo_parser.add_argument("--execute", action="store_true", help="For archive-completed, write the active-state edit.")


def handle_todo_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    append_cli_rollout_event: RolloutEventAppender,
) -> int:
    renderer = (
        render_todo_suggestion_prompt_markdown
        if args.todo_command == "suggest"
        else render_todo_markdown
    )
    try:
        agent_id_allowed_for_gate_authoring = (
            args.todo_command in {"add", "update"}
            and args.role == "user"
            and args.task_class == "user_gate"
        )
        global_gate_allowed = args.todo_command in {"add", "update"}
        if args.todo_command not in {"suggest", "capture-followups"} and (
            (args.agent_id and not agent_id_allowed_for_gate_authoring)
            or (args.global_gate and not global_gate_allowed)
            or args.suggestion_sources
            or args.suggestion_limit is not None
            or args.suggestion_trigger
        ):
            raise ValueError(
                "todo --agent-id is supported by `todo suggest` and by "
                "`todo add/update --role user --task-class user_gate` for "
                "agent-scoped user gates; --global-gate is supported by "
                "`todo add/update` for user gates; --from, --limit, and "
                "--trigger are only supported by `todo suggest`"
            )
        if args.todo_command == "list":
            unsupported = [
                flag
                for flag, value in (
                    ("--text", args.text),
                    ("--follow-up", args.followups),
                    ("--todo-id", args.todo_id),
                    ("--note", args.note),
                    ("--evidence", args.evidence),
                    ("--reason", args.reason),
                    ("--task-class", args.task_class),
                    ("--action-kind", args.action_kind),
                    ("--required-write-scope", args.required_write_scopes),
                    ("--required-capability", args.required_capabilities),
                    ("--target-capability", args.target_capabilities),
                    ("--decision-scope", args.decision_scope),
                    ("--required-decision-scope", args.required_decision_scopes),
                    ("--claimed-by", args.claimed_by),
                    ("--blocks-agent", args.blocks_agent),
                    ("--global-gate", args.global_gate),
                    ("--unblocks-todo-id", args.unblocks_todo_id),
                    ("--resume-when", args.resume_when),
                    ("--monitor-target-key", args.monitor_target_key),
                    ("--cadence", args.cadence),
                    ("--next-due-at", args.next_due_at),
                    ("--expires-at", args.expires_at),
                    ("--clear-claim", args.clear_claim),
                    ("--no-follow-up", args.no_follow_up),
                    ("--next-agent-todo", args.next_agent_todo),
                    ("--next-user-todo", args.next_user_todo),
                    ("--next-claimed-by", args.next_claimed_by),
                    ("--next-task-class", args.next_task_class),
                    ("--next-action-kind", args.next_action_kind),
                    ("--side-agent-self-merged", args.side_agent_self_merged),
                    ("--agent-id", args.agent_id),
                    ("--from", args.suggestion_sources),
                    ("--limit", args.suggestion_limit),
                    ("--trigger", args.suggestion_trigger),
                    ("--execute", args.execute),
                )
                if value
            ]
            if unsupported:
                raise ValueError(
                    "todo list only accepts --goal-id, optional --role, --status, "
                    "--project, --state-file, --dry-run, and --format; unsupported: "
                    + ", ".join(unsupported)
                )
            payload = list_goal_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                status=args.status,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
            )
        elif args.todo_command == "add":
            if args.followups:
                raise ValueError("todo add does not support --follow-up; use `todo capture-followups`")
            if not args.role:
                raise ValueError("todo add requires --role")
            if not args.text:
                raise ValueError("todo add requires --text")
            if args.clear_claim:
                raise ValueError("todo add accepts --claimed-by but not --clear-claim")
            if args.next_claimed_by:
                raise ValueError("todo add does not support --next-claimed-by")
            if args.side_agent_self_merged:
                raise ValueError("todo add does not support --side-agent-self-merged")
            if args.no_follow_up:
                raise ValueError("todo add does not support --no-follow-up")
            payload = add_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                text=args.text,
                task_class=args.task_class,
                action_kind=args.action_kind,
                required_write_scopes=args.required_write_scopes,
                required_capabilities=args.required_capabilities,
                target_capabilities=args.target_capabilities,
                decision_scope=args.decision_scope,
                required_decision_scopes=args.required_decision_scopes,
                claimed_by=args.claimed_by,
                blocks_agent=args.blocks_agent,
                global_gate=bool(args.global_gate),
                agent_id=args.agent_id,
                unblocks_todo_id=args.unblocks_todo_id,
                resume_when=args.resume_when,
                monitor_metadata={
                    "target_key": args.monitor_target_key,
                    "cadence": args.cadence,
                    "next_due_at": args.next_due_at,
                    "expires_at": args.expires_at,
                },
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "claim":
            if not args.todo_id:
                raise ValueError("todo claim requires --todo-id")
            if not args.claimed_by:
                raise ValueError("todo claim requires --claimed-by")
            if args.clear_claim:
                raise ValueError("todo claim requires --claimed-by and does not support --clear-claim")
            unsupported = [
                flag
                for flag, value in (
                    ("--text", args.text),
                    ("--status", args.status),
                    ("--note", args.note),
                    ("--evidence", args.evidence),
                    ("--reason", args.reason),
                    ("--task-class", args.task_class),
                    ("--action-kind", args.action_kind),
                    ("--required-write-scope", args.required_write_scopes),
                    ("--required-capability", args.required_capabilities),
                    ("--target-capability", args.target_capabilities),
                    ("--decision-scope", args.decision_scope),
                    ("--required-decision-scope", args.required_decision_scopes),
                    ("--blocks-agent", args.blocks_agent),
                    ("--global-gate", args.global_gate),
                    ("--unblocks-todo-id", args.unblocks_todo_id),
                    ("--resume-when", args.resume_when),
                    ("--monitor-target-key", args.monitor_target_key),
                    ("--cadence", args.cadence),
                    ("--next-due-at", args.next_due_at),
                    ("--expires-at", args.expires_at),
                    ("--no-follow-up", args.no_follow_up),
                    ("--next-agent-todo", args.next_agent_todo),
                    ("--next-user-todo", args.next_user_todo),
                    ("--next-claimed-by", args.next_claimed_by),
                    ("--next-task-class", args.next_task_class),
                    ("--next-action-kind", args.next_action_kind),
                    ("--side-agent-self-merged", args.side_agent_self_merged),
                    ("--follow-up", args.followups),
                )
                if value
            ]
            if unsupported:
                raise ValueError(
                    "todo claim only accepts --todo-id, --claimed-by, optional --role, "
                    "--project, --state-file, and --dry-run; unsupported: "
                    + ", ".join(unsupported)
                )
            payload = update_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                claimed_by=args.claimed_by,
                claim_only=True,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "update":
            if not args.todo_id:
                raise ValueError("todo update requires --todo-id")
            if args.claimed_by and args.clear_claim:
                raise ValueError("todo update accepts either --claimed-by or --clear-claim, not both")
            if not any([
                args.text,
                args.followups,
                args.status,
                args.note,
                args.evidence,
                args.reason,
                args.task_class,
                args.action_kind,
                args.required_write_scopes,
                args.required_capabilities,
                args.target_capabilities,
                args.decision_scope,
                args.required_decision_scopes,
                args.claimed_by,
                args.blocks_agent,
                args.global_gate,
                args.unblocks_todo_id,
                args.resume_when,
                args.no_follow_up,
                args.monitor_target_key,
                args.cadence,
                args.next_due_at,
                args.expires_at,
                args.clear_claim,
            ]):
                raise ValueError("todo update requires at least one of --text, --status, --note, --evidence, --reason, --task-class, --action-kind, --required-write-scope, --required-capability, --target-capability, --decision-scope, --required-decision-scope, --claimed-by, --blocks-agent, --global-gate, --unblocks-todo-id, --resume-when, --monitor-target-key, --cadence, --next-due-at, --expires-at, --no-follow-up, or --clear-claim")
            if args.no_follow_up and not (args.note or args.reason or args.evidence):
                raise ValueError("--no-follow-up requires --note, --reason, or --evidence")
            if args.followups:
                raise ValueError("todo update does not support --follow-up; use `todo capture-followups`")
            if args.next_claimed_by:
                raise ValueError("todo update does not support --next-claimed-by")
            if args.side_agent_self_merged:
                raise ValueError("todo update does not support --side-agent-self-merged")
            payload = update_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                text=args.text,
                status=args.status,
                role=args.role,
                note=args.note,
                evidence=args.evidence,
                reason=args.reason,
                task_class=args.task_class,
                action_kind=args.action_kind,
                required_write_scopes=args.required_write_scopes,
                required_capabilities=args.required_capabilities,
                target_capabilities=args.target_capabilities,
                decision_scope=args.decision_scope,
                required_decision_scopes=args.required_decision_scopes,
                claimed_by=args.claimed_by,
                blocks_agent=args.blocks_agent,
                global_gate=bool(args.global_gate),
                agent_id=args.agent_id,
                unblocks_todo_id=args.unblocks_todo_id,
                resume_when=args.resume_when,
                no_followup=True if args.no_follow_up else None,
                monitor_metadata={
                    "target_key": args.monitor_target_key,
                    "cadence": args.cadence,
                    "next_due_at": args.next_due_at,
                    "expires_at": args.expires_at,
                },
                clear_claim=bool(args.clear_claim),
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "complete":
            if not args.todo_id:
                raise ValueError("todo complete requires --todo-id")
            if args.claimed_by and args.clear_claim:
                raise ValueError("todo complete accepts either --claimed-by or --clear-claim, not both")
            if args.blocks_agent or args.global_gate or args.unblocks_todo_id or args.resume_when:
                raise ValueError("todo complete does not support --blocks-agent, --global-gate, --unblocks-todo-id, or --resume-when; use todo update before completion or side-agent handoff successor metadata")
            if args.monitor_target_key or args.cadence or args.next_due_at or args.expires_at:
                raise ValueError("todo complete does not support monitor schedule metadata; use todo update before completion")
            if args.no_follow_up and (args.next_agent_todo or args.next_user_todo):
                raise ValueError("--no-follow-up cannot be combined with successor todos")
            if args.no_follow_up and not (args.note or args.evidence):
                raise ValueError("--no-follow-up requires --note or --evidence")
            if args.followups:
                raise ValueError("todo complete does not support --follow-up; use `todo capture-followups`")
            payload = complete_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                evidence=args.evidence,
                note=args.note,
                no_followup=bool(args.no_follow_up),
                claimed_by=args.claimed_by,
                clear_claim=bool(args.clear_claim),
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_claimed_by=args.next_claimed_by,
                next_task_class=args.next_task_class,
                next_action_kind=args.next_action_kind,
                side_agent_self_merged=bool(args.side_agent_self_merged),
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "supersede":
            if not args.todo_id:
                raise ValueError("todo supersede requires --todo-id")
            if args.claimed_by:
                raise ValueError(
                    "todo supersede does not support --claimed-by; use --next-claimed-by "
                    "to assign the successor, or omit it to inherit the superseded todo "
                    "owner when present"
                )
            if args.clear_claim:
                raise ValueError("todo supersede does not support --clear-claim")
            if args.side_agent_self_merged:
                raise ValueError("todo supersede does not support --side-agent-self-merged")
            if args.no_follow_up:
                raise ValueError("todo supersede does not support --no-follow-up")
            if args.followups:
                raise ValueError("todo supersede does not support --follow-up; use `todo capture-followups`")
            if args.blocks_agent or args.global_gate or args.unblocks_todo_id or args.resume_when:
                raise ValueError("todo supersede does not support --blocks-agent, --global-gate, --unblocks-todo-id, or --resume-when; update the source todo first so the successor can inherit dependency metadata")
            if args.monitor_target_key or args.cadence or args.next_due_at or args.expires_at:
                raise ValueError("todo supersede does not support monitor schedule metadata; use todo update before supersede")
            payload = supersede_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                reason=args.reason,
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_claimed_by=args.next_claimed_by,
                next_task_class=args.next_task_class,
                next_action_kind=args.next_action_kind,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "archive-completed":
            if args.claimed_by or args.clear_claim:
                raise ValueError("todo archive-completed does not support --claimed-by or --clear-claim")
            if args.next_claimed_by:
                raise ValueError("todo archive-completed does not support --next-claimed-by")
            if args.side_agent_self_merged:
                raise ValueError("todo archive-completed does not support --side-agent-self-merged")
            if args.no_follow_up:
                raise ValueError("todo archive-completed does not support --no-follow-up")
            if args.followups:
                raise ValueError("todo archive-completed does not support --follow-up; use `todo capture-followups`")
            payload = archive_completed_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role or "agent",
                max_active_done=args.max_active_done,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=not bool(args.execute),
            )
        elif args.todo_command == "suggest":
            unsupported = [
                flag
                for flag, value in (
                    ("--role", args.role),
                    ("--text", args.text),
                    ("--todo-id", args.todo_id),
                    ("--status", args.status),
                    ("--note", args.note),
                    ("--evidence", args.evidence),
                    ("--reason", args.reason),
                    ("--task-class", args.task_class),
                    ("--action-kind", args.action_kind),
                    ("--required-write-scope", args.required_write_scopes),
                    ("--required-capability", args.required_capabilities),
                    ("--target-capability", args.target_capabilities),
                    ("--decision-scope", args.decision_scope),
                    ("--required-decision-scope", args.required_decision_scopes),
                    ("--claimed-by", args.claimed_by),
                    ("--blocks-agent", args.blocks_agent),
                    ("--global-gate", args.global_gate),
                    ("--unblocks-todo-id", args.unblocks_todo_id),
                    ("--resume-when", args.resume_when),
                    ("--monitor-target-key", args.monitor_target_key),
                    ("--cadence", args.cadence),
                    ("--next-due-at", args.next_due_at),
                    ("--expires-at", args.expires_at),
                    ("--no-follow-up", args.no_follow_up),
                    ("--clear-claim", args.clear_claim),
                    ("--next-agent-todo", args.next_agent_todo),
                    ("--next-user-todo", args.next_user_todo),
                    ("--next-claimed-by", args.next_claimed_by),
                    ("--next-task-class", args.next_task_class),
                    ("--next-action-kind", args.next_action_kind),
                    ("--side-agent-self-merged", args.side_agent_self_merged),
                    ("--follow-up", args.followups),
                    ("--state-file", args.state_file),
                    ("--execute", args.execute),
                )
                if value
            ]
            if unsupported:
                raise ValueError(
                    "todo suggest only accepts --goal-id, optional --project, --agent-id, "
                    "--from, --limit, --trigger, --dry-run, and --format; unsupported: "
                    + ", ".join(unsupported)
                )
            payload = build_todo_suggestion_prompt_packet(
                goal_id=args.goal_id,
                project=Path(args.project).expanduser() if args.project else None,
                agent_id=args.agent_id,
                sources=args.suggestion_sources,
                limit=args.suggestion_limit,
                trigger=args.suggestion_trigger,
            )
            payload["dry_run"] = True
        elif args.todo_command == "capture-followups":
            if args.role:
                raise ValueError("todo capture-followups always records agent todos; do not pass --role")
            if args.claimed_by:
                raise ValueError("todo capture-followups writes unclaimed todos; do not pass --claimed-by")
            unsupported = [
                flag
                for flag, value in (
                    ("--todo-id", args.todo_id),
                    ("--status", args.status),
                    ("--note", args.note),
                    ("--reason", args.reason),
                    ("--decision-scope", args.decision_scope),
                    ("--blocks-agent", args.blocks_agent),
                    ("--global-gate", args.global_gate),
                    ("--unblocks-todo-id", args.unblocks_todo_id),
                    ("--resume-when", args.resume_when),
                    ("--monitor-target-key", args.monitor_target_key),
                    ("--cadence", args.cadence),
                    ("--next-due-at", args.next_due_at),
                    ("--expires-at", args.expires_at),
                    ("--no-follow-up", args.no_follow_up),
                    ("--clear-claim", args.clear_claim),
                    ("--next-agent-todo", args.next_agent_todo),
                    ("--next-user-todo", args.next_user_todo),
                    ("--next-claimed-by", args.next_claimed_by),
                    ("--next-task-class", args.next_task_class),
                    ("--next-action-kind", args.next_action_kind),
                    ("--side-agent-self-merged", args.side_agent_self_merged),
                    ("--agent-id", args.agent_id),
                    ("--from", args.suggestion_sources),
                    ("--limit", args.suggestion_limit),
                    ("--trigger", args.suggestion_trigger),
                    ("--execute", args.execute),
                )
                if value
            ]
            if unsupported:
                raise ValueError(
                    "todo capture-followups only accepts --goal-id, --follow-up, optional "
                    "--text shorthand, --evidence, routing metadata, --project, --state-file, "
                    "and --dry-run; unsupported: "
                    + ", ".join(unsupported)
                )
            followups = list(args.followups or [])
            if args.text:
                followups.append(args.text)
            payload = capture_followup_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                followups=followups,
                evidence=args.evidence or "",
                task_class=args.task_class,
                action_kind=args.action_kind,
                required_write_scopes=args.required_write_scopes,
                required_capabilities=args.required_capabilities,
                target_capabilities=args.target_capabilities,
                required_decision_scopes=args.required_decision_scopes,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        else:
            raise ValueError("unsupported todo command")
    except Exception as exc:
        payload = {
            "ok": False,
            "dry_run": True
            if args.todo_command == "suggest"
            else not bool(args.execute)
            if args.todo_command == "archive-completed"
            else bool(args.dry_run),
            "added": False,
            "already_exists": False,
            "goal_id": args.goal_id,
            "role": args.role,
            "todo": args.text or "",
            "error": str(exc),
        }
    todo_event_kinds = {
        "add": "todo_add",
        "claim": "todo_claim",
        "update": "todo_update",
        "complete": "todo_complete",
        "supersede": "todo_supersede",
        "archive-completed": "todo_archive_completed",
        "capture-followups": "todo_capture_followups",
    }
    if payload.get("ok") and not payload.get("dry_run"):
        append_cli_rollout_event(
            payload,
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            event_kind=todo_event_kinds.get(args.todo_command, "todo_update"),
            agent_id=args.agent_id or args.claimed_by,
            todo_id=args.todo_id or str(payload.get("todo_id") or "").strip() or None,
            status=str(payload.get("status") or args.todo_command or "").strip(),
            summary=(
                f"todo {args.todo_command} recorded for "
                f"{payload.get('todo_id') or args.todo_id or 'unstructured todo'}"
            ),
            details={
                "command": "todo",
                "todo_command": args.todo_command,
                "role": payload.get("role") or args.role or "",
                "changed": bool(payload.get("changed")),
                "added": bool(payload.get("added")),
                "already_exists": bool(payload.get("already_exists")),
            },
        )
    print_payload(payload, args.format, renderer)
    return 0 if payload.get("ok") else 1
