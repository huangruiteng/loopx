from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..control_plane.todos.contract import TODO_CONTINUATION_POLICY_VALUES
from ..control_plane.todos.markdown import render_todo_markdown
from ..control_plane.work_items.task_lease import TaskLeaseError
from ..file_lock import lock_timeout_error_fields
from ..todo_followups import capture_followup_todos
from ..todo_suggestion_prompt import (
    ALLOWED_TODO_SUGGESTION_SOURCES,
    ALLOWED_TODO_SUGGESTION_TRIGGERS,
    build_todo_suggestion_prompt_packet,
    render_todo_suggestion_prompt_markdown,
)
from ..todos import (
    ARCHIVE_COMPLETED_DEFAULT_MAX_ACTIVE_DONE,
    add_goal_todo,
    archive_completed_todos,
    complete_goal_todo,
    list_goal_todos,
    supersede_goal_todo,
    update_goal_todo,
)
from .todo_argument_validation import (
    register_todo_linkage_arguments,
    register_todo_successor_creation_arguments,
    validate_capability_gap_options,
    validate_shared_todo_options,
    validate_todo_add_options,
    validate_todo_archive_completed_options,
    validate_todo_capture_followups_options,
    validate_todo_claim_options,
    validate_todo_complete_options,
    validate_todo_list_options,
    validate_todo_suggest_options,
    validate_todo_supersede_options,
    validate_todo_update_options,
)
from .todo_event import RolloutEventAppender, append_todo_rollout_event

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_todo_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    todo_parser = subparsers.add_parser(
        "todo",
        help="Add a user or agent todo to a goal's active state.",
        description=(
            "Manage goal todos. The options below are the union for every todo "
            "command; each option's help names the commands that accept it, and "
            "unsupported combinations fail before state is read or written."
        ),
    )
    add_subcommand_format(todo_parser)
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
        default=None,
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
    todo_parser.add_argument("--status", choices=["open", "done", "blocked", "deferred"], help="For todo add/update, set the lifecycle status.")
    todo_parser.add_argument("--note", help="Public-safe note to attach to a lifecycle transition.")
    todo_parser.add_argument("--evidence", help="Public-safe evidence pointer or short result for complete/update.")
    todo_parser.add_argument("--reason", help="Public-safe reason for blocked/deferred/supersede transitions.")
    todo_parser.add_argument(
        "--authority-reason",
        help=(
            "For a delegated lifecycle override, record the public-safe reason. "
            "Required when the matching coordination.todo_lifecycle_authority "
            "grant sets requires_reason=true."
        ),
    )
    todo_parser.add_argument(
        "--task-class",
        choices=["advancement_task", "continuous_monitor", "user_gate", "user_action", "blocker"],
        help=(
            "For todo add/update, explicitly register the routing lane. Use "
            "advancement_task for executable delivery work; user_gate for blocking "
            "owner/controller decisions; user_action for non-blocking user-visible "
            "todos; continuous_monitor and blocker are non-executable lanes."
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
        "--task-domain",
        help=(
            "For agent todo add/update, declare the bounded responsibility domain "
            "used by adaptive child admission, such as code, docs, or validation."
        ),
    )
    todo_parser.add_argument(
        "--capability-binding-ref",
        help=(
            "For agent todo add, persist the opaque capability admission binding "
            "projected by a validated capability packet."
        ),
    )
    todo_parser.add_argument(
        "--task-repository",
        help=(
            "For agent todo add/update, declare the credential-free Git repository "
            "identity that owns the task, such as git:github.com/owner/repo. This "
            "selects workspace isolation; it does not grant write permission."
        ),
    )
    todo_parser.add_argument(
        "--continuation-policy",
        choices=sorted(TODO_CONTINUATION_POLICY_VALUES),
        help=(
            "Closed completion/handoff policy for this todo. action_kind remains "
            "an extensible domain token; defaults to independent_handoff."
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
            "repairing, materializing, or parity-checking. On complete, pair it "
            "with --capability-gap-status to close that lifecycle. This is not a "
            "hard execution prerequisite."
        ),
    )
    todo_parser.add_argument(
        "--capability-gap-status",
        choices=["found", "fixed", "real_callsite_verified"],
        help=(
            "For agent todo add/update/complete, append an auditable capability-gap "
            "lifecycle event. Requires --target-capability; the todo_id is the "
            "stable gap id."
        ),
    )
    todo_parser.add_argument(
        "--explore-result-node-ref",
        dest="explore_result_node_refs",
        action="append",
        help=(
            "For todo add/update, link an explicit public-safe Explore result node id. "
            "Repeat for multiple nodes; analysis resolves only these links."
        ),
    )
    todo_parser.add_argument(
        "--clear-explore-result-node-refs",
        action="store_true",
        help="For todo update, remove all explicit Explore result node links.",
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
        "--decision-outcome",
        choices=["approve", "reject", "cancel"],
        help=(
            "For todo complete on a user_gate, record the explicit owner decision. "
            "Only approve consumes authority and resumes linked work."
        ),
    )
    todo_parser.add_argument(
        "--claimed-by",
        help=(
            "For agent todo add/claim/update, assign the soft execution owner to a "
            "registered public-safe agent id such as codex-main-control. This names "
            "the assignment target, not the lifecycle actor; multi-agent lifecycle "
            "commands still require --agent-id. User todos use --bound-agent or "
            "--goal-bound instead."
        ),
    )
    todo_parser.add_argument(
        "--task-lease-idempotency-key",
        help=(
            "For todo complete, prove the execution instance that owns an active "
            "hard task lease. Required when that todo has an effective lease."
        ),
    )
    todo_parser.add_argument(
        "--task-lease-expected-version",
        type=int,
        help=(
            "For todo complete, optionally CAS the active hard task lease version. "
            "Requires --task-lease-idempotency-key."
        ),
    )
    todo_parser.add_argument(
        "--bound-agent",
        help=(
            "For user todo add/update, bind reminder delivery and post-response "
            "continuation to one registered agent lane. This is not a gate."
        ),
    )
    todo_parser.add_argument(
        "--goal-bound",
        action="store_true",
        help=(
            "For user todo add/update, explicitly bind the item to the whole goal "
            "instead of one agent lane."
        ),
    )
    todo_parser.add_argument(
        "--blocks-agent",
        help=(
            "For user_gate add/update, scope the gate to one registered agent."
        ),
    )
    todo_parser.add_argument(
        "--clear-blocks-agent",
        action="store_true",
        help="For todo update, remove the existing blocks_agent field.",
    )
    todo_parser.add_argument(
        "--excluded-agent",
        dest="excluded_agents",
        action="append",
        help=(
            "For agent todo add/update, exclude one registered peer from claiming or "
            "executing the todo. Repeat for multiple peers."
        ),
    )
    todo_parser.add_argument(
        "--clear-excluded-agents",
        action="store_true",
        help="For todo update, remove all executor exclusions from the todo.",
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
        "--clear-global-gate",
        action="store_true",
        help=(
            "For todo update on a user_gate, remove global_gate. In a multi-agent "
            "goal, provide --blocks-agent in the same update so the gate retains "
            "an explicit lane scope."
        ),
    )
    register_todo_linkage_arguments(todo_parser)
    todo_parser.add_argument(
        "--target-key",
        "--monitor-target-key",
        dest="monitor_target_key",
        help=(
            "For agent todo add/update, declare a stable public-safe execution "
            "target key. --monitor-target-key remains a compatibility alias."
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
    register_todo_successor_creation_arguments(todo_parser)
    todo_parser.add_argument(
        "--max-active-done",
        type=int,
        default=ARCHIVE_COMPLETED_DEFAULT_MAX_ACTIVE_DONE,
        help=(
            "For archive-completed, keep this many completed todos in the active section. "
            "The default leaves a small buffer below the status warning threshold."
        ),
    )
    todo_parser.add_argument(
        "--agent-id",
        help=(
            "For user todo add, mark the authoring registered agent and bind the "
            "user response continuation to that lane; for user_gate, the gate also "
            "blocks this agent when --blocks-agent is omitted. For "
            "claim/update/complete/supersede, attribute the "
            "lifecycle actor; registered multi-agent goals require it unless an "
            "exact linked user_gate decision_scope supplies the typed owner/controller "
            "override. For list/suggest, select the project agent lane. Agent todo "
            "add intentionally does not accept this option; use --claimed-by to "
            "assign execution, or omit both options to leave the todo unclaimed."
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


def _todo_path_args(args: argparse.Namespace) -> dict[str, Path | None]:
    return {
        "project": Path(args.project).expanduser() if args.project else None,
        "state_file": Path(args.state_file).expanduser() if args.state_file else None,
    }


def handle_todo_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    append_cli_rollout_event: RolloutEventAppender,
    format_name: str | None = None,
) -> int:
    renderer = (
        render_todo_suggestion_prompt_markdown
        if args.todo_command == "suggest"
        else render_todo_markdown
    )
    try:
        if args.todo_command is None:
            raise ValueError(
                "`loopx todo` requires an explicit command; use `loopx todo add`, "
                "`loopx todo claim`, `loopx todo update`, or another command shown "
                "by `loopx todo --help`"
            )
        validate_shared_todo_options(args)
        validate_capability_gap_options(args)
        if args.todo_command == "list":
            validate_todo_list_options(args)
            payload = list_goal_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                status=args.status,
                todo_id=args.todo_id,
                agent_id=args.agent_id,
                **_todo_path_args(args),
                runtime_root_arg=runtime_root_arg,
            )
        elif args.todo_command == "add":
            validate_todo_add_options(args)
            payload = add_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                text=args.text,
                status=args.status,
                task_class=args.task_class,
                action_kind=args.action_kind,
                task_domain=args.task_domain,
                capability_binding_ref=args.capability_binding_ref,
                task_repository=args.task_repository,
                continuation_policy=args.continuation_policy,
                required_write_scopes=args.required_write_scopes,
                required_capabilities=args.required_capabilities,
                target_capabilities=args.target_capabilities,
                explore_result_node_refs=args.explore_result_node_refs,
                decision_scope=args.decision_scope,
                required_decision_scopes=args.required_decision_scopes,
                claimed_by=args.claimed_by,
                bound_agent=args.bound_agent,
                goal_bound=bool(args.goal_bound),
                blocks_agent=args.blocks_agent,
                excluded_agents=args.excluded_agents,
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
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "claim":
            validate_todo_claim_options(args)
            payload = update_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                claimed_by=args.claimed_by,
                agent_id=args.agent_id,
                claim_only=True,
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "update":
            validate_todo_update_options(args)
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
                task_domain=args.task_domain,
                task_repository=args.task_repository,
                continuation_policy=args.continuation_policy,
                required_write_scopes=args.required_write_scopes,
                required_capabilities=args.required_capabilities,
                target_capabilities=args.target_capabilities,
                explore_result_node_refs=(
                    []
                    if args.clear_explore_result_node_refs
                    else args.explore_result_node_refs
                ),
                decision_scope=args.decision_scope,
                required_decision_scopes=args.required_decision_scopes,
                claimed_by=args.claimed_by,
                bound_agent=args.bound_agent,
                goal_bound=bool(args.goal_bound),
                blocks_agent=args.blocks_agent,
                clear_blocks_agent=bool(args.clear_blocks_agent),
                excluded_agents=args.excluded_agents,
                clear_excluded_agents=bool(args.clear_excluded_agents),
                global_gate=bool(args.global_gate),
                clear_global_gate=bool(args.clear_global_gate),
                agent_id=args.agent_id,
                authority_reason=args.authority_reason,
                unblocks_todo_id=args.unblocks_todo_id,
                successor_todo_ids=args.successor_todo_ids,
                resume_when=args.resume_when,
                clear_resume_when=bool(args.clear_resume_when),
                no_followup=True if args.no_follow_up else None,
                monitor_metadata={
                    "target_key": args.monitor_target_key,
                    "cadence": args.cadence,
                    "next_due_at": args.next_due_at,
                    "expires_at": args.expires_at,
                },
                clear_claim=bool(args.clear_claim),
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "complete":
            validate_todo_complete_options(args)
            payload = complete_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                decision_outcome=args.decision_outcome,
                evidence=args.evidence,
                task_lease_idempotency_key=args.task_lease_idempotency_key,
                task_lease_expected_version=args.task_lease_expected_version,
                note=args.note,
                no_followup=bool(args.no_follow_up),
                successor_todo_ids=args.successor_todo_ids,
                claimed_by=args.claimed_by,
                clear_claim=bool(args.clear_claim),
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_user_task_class=args.next_user_task_class,
                next_claimed_by=args.next_claimed_by,
                next_task_class=args.next_task_class,
                next_action_kind=args.next_action_kind,
                next_task_repository=args.next_task_repository,
                next_required_capabilities=args.next_required_capabilities,
                next_continuation_policy=args.next_continuation_policy,
                next_excluded_agents=args.next_excluded_agents,
                self_merged=bool(args.self_merged),
                agent_id=args.agent_id,
                authority_reason=args.authority_reason,
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "supersede":
            validate_todo_supersede_options(args)
            payload = supersede_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                reason=args.reason,
                next_agent_todo=args.next_agent_todo,
                next_user_todo=args.next_user_todo,
                next_user_task_class=args.next_user_task_class,
                next_claimed_by=args.next_claimed_by,
                next_task_class=args.next_task_class,
                next_action_kind=args.next_action_kind,
                next_task_repository=args.next_task_repository,
                next_required_capabilities=args.next_required_capabilities,
                next_continuation_policy=args.next_continuation_policy,
                next_excluded_agents=args.next_excluded_agents,
                agent_id=args.agent_id,
                authority_reason=args.authority_reason,
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "archive-completed":
            validate_todo_archive_completed_options(args)
            payload = archive_completed_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role or "agent",
                max_active_done=args.max_active_done,
                **_todo_path_args(args),
                dry_run=not bool(args.execute),
            )
        elif args.todo_command == "suggest":
            validate_todo_suggest_options(args)
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
            validate_todo_capture_followups_options(args)
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
                **_todo_path_args(args),
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
            **lock_timeout_error_fields(exc),
        }
        if isinstance(exc, TaskLeaseError):
            payload["error_code"] = exc.code
            payload.update(exc.payload)
    append_todo_rollout_event(
        payload,
        args=args,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        append_cli_rollout_event=append_cli_rollout_event,
    )
    print_payload(
        payload,
        format_name or str(getattr(args, "format", None) or "markdown"),
        renderer,
    )
    return 0 if payload.get("ok") else 1
