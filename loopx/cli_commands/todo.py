from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..control_plane.todos.contract import TODO_CONTINUATION_POLICY_VALUES
from ..todo_suggestion_prompt import (
    ALLOWED_TODO_SUGGESTION_SOURCES,
    ALLOWED_TODO_SUGGESTION_TRIGGERS,
    build_todo_suggestion_prompt_packet,
    render_todo_suggestion_prompt_markdown,
)
from ..todo_followups import capture_followup_todos
from ..control_plane.todos.markdown import render_todo_markdown
from ..todos import (
    ARCHIVE_COMPLETED_DEFAULT_MAX_ACTIVE_DONE,
    archive_completed_todos,
    add_goal_todo,
    complete_goal_todo,
    list_goal_todos,
    supersede_goal_todo,
    update_goal_todo,
)
from .todo_argument_validation import (
    unsupported_todo_options,
    validate_capability_gap_options,
    validate_shared_todo_options,
    validate_successor_routing_options,
)
from .todo_event import RolloutEventAppender, append_todo_rollout_event


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_todo_command(subparsers: argparse._SubParsersAction) -> None:
    todo_parser = subparsers.add_parser(
        "todo",
        help="Add a user or agent todo to a goal's active state.",
        description=(
            "Manage goal todos. The options below are the union for every todo "
            "command; each option's help names the commands that accept it, and "
            "unsupported combinations fail before state is read or written."
        ),
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
            "repairing, materializing, or parity-checking. This is not a hard "
            "execution prerequisite."
        ),
    )
    todo_parser.add_argument(
        "--capability-gap-status",
        choices=["found", "fixed", "real_callsite_verified"],
        help=(
            "For agent todo add/update, append an auditable capability-gap lifecycle "
            "event. Requires --target-capability; the todo_id is the stable gap id."
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
            "For agent todo add/claim/update/complete, soft-claim execution for a "
            "registered public-safe agent id such as codex-main-control. User todos "
            "use --bound-agent or --goal-bound instead."
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
    todo_parser.add_argument(
        "--unblocks-todo-id",
        help=(
            "For todo add/update, link this todo to the blocked todo it unblocks, "
            "for example todo_ab12cd34ef56. Completing an exactly linked user_gate "
            "also consumes the target required decision scopes covered by that gate."
        ),
    )
    todo_parser.add_argument(
        "--successor-todo-id",
        dest="successor_todo_ids",
        action="append",
        help=(
            "For todo update/complete, link an existing successor todo to the "
            "current todo. Repeat for multiple successors."
        ),
    )
    todo_parser.add_argument(
        "--resume-when",
        help=(
            "For deferred todo add/update, declare a machine-readable resume condition "
            "such as todo_done:todo_ab12cd34ef56, pr_merged:#532, or "
            "capacity_available:short_pool. Capacity keys are resolved from quota "
            "--available-capability declarations."
        ),
    )
    todo_parser.add_argument(
        "--clear-resume-when",
        action="store_true",
        help=(
            "For todo update, remove the existing resume condition after its "
            "successor replan has made the todo runnable."
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
        "--next-user-task-class",
        choices=["user_gate", "user_action"],
        help=(
            "Task class for --next-user-todo. Defaults to user_gate for backward "
            "compatibility; use user_action for a visible reminder that must not "
            "block the bound agent lane."
        ),
    )
    todo_parser.add_argument(
        "--next-claimed-by",
        help=(
            "For complete/supersede with --next-agent-todo, soft-claim the successor "
            "todo for a registered agent. Independent handoffs remain unclaimed unless "
            "explicitly assigned, while same-agent non-delivery "
            "continuations keep the current owner. Use --self-merged with --evidence "
            "for an eligible same-agent delivery."
        ),
    )
    todo_parser.add_argument(
        "--self-merged",
        action="store_true",
        help=(
            "For todo complete, record that a small validated change was self-merged; "
            "requires --evidence."
        ),
    )
    todo_parser.add_argument(
        "--next-task-class",
        choices=["advancement_task", "continuous_monitor", "blocker"],
        help="Task class for --next-agent-todo. Defaults to advancement_task.",
    )
    todo_parser.add_argument("--next-action-kind", help="Action kind for --next-agent-todo.")
    todo_parser.add_argument(
        "--next-task-repository",
        help=(
            "Credential-free Git repository identity for --next-agent-todo, such as "
            "git:github.com/owner/repo."
        ),
    )
    todo_parser.add_argument(
        "--next-required-capability",
        dest="next_required_capabilities",
        action="append",
        help=(
            "Execution capability required by --next-agent-todo. Repeat for multiple "
            "capabilities."
        ),
    )
    todo_parser.add_argument(
        "--next-continuation-policy",
        choices=sorted(TODO_CONTINUATION_POLICY_VALUES),
        help="Continuation policy for --next-agent-todo.",
    )
    todo_parser.add_argument(
        "--next-excluded-agent",
        dest="next_excluded_agents",
        action="append",
        help=(
            "For complete/supersede with --next-agent-todo, exclude one registered "
            "peer from claiming or executing the successor. Repeat for multiple peers."
        ),
    )
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
        validate_shared_todo_options(args)
        validate_capability_gap_options(args)
        if args.todo_command == "list":
            unsupported = unsupported_todo_options(
                args,
                allowed_fields={"role", "todo_id", "status", "agent_id", "state_file"},
            )
            if unsupported:
                raise ValueError(
                    "todo list only accepts --goal-id, optional --role, --status, --todo-id, "
                    "--agent-id, --project, --state-file, --dry-run, and --format; unsupported: "
                    + ", ".join(unsupported)
                )
            payload = list_goal_todos(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                status=args.status,
                todo_id=args.todo_id,
                agent_id=args.agent_id,
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                runtime_root_arg=runtime_root_arg,
            )
        elif args.todo_command == "add":
            if args.decision_outcome:
                raise ValueError(
                    "todo add does not accept --decision-outcome; record it on completion"
                )
            if args.followups:
                raise ValueError("todo add does not support --follow-up; use `todo capture-followups`")
            if not args.role:
                raise ValueError("todo add requires --role")
            if not args.text:
                raise ValueError("todo add requires --text")
            if args.clear_claim:
                raise ValueError("todo add accepts --claimed-by but not --clear-claim")
            if args.clear_explore_result_node_refs:
                raise ValueError(
                    "todo add accepts --explore-result-node-ref but not --clear-explore-result-node-refs"
                )
            if args.next_claimed_by:
                raise ValueError("todo add does not support --next-claimed-by")
            if args.next_task_repository:
                raise ValueError("todo add does not support --next-task-repository")
            if args.next_required_capabilities:
                raise ValueError("todo add does not support --next-required-capability")
            if args.next_continuation_policy:
                raise ValueError("todo add does not support --next-continuation-policy")
            if args.next_excluded_agents:
                raise ValueError("todo add does not support --next-excluded-agent")
            if args.clear_excluded_agents:
                raise ValueError("todo add does not support --clear-excluded-agents")
            if args.clear_blocks_agent:
                raise ValueError("todo add does not support --clear-blocks-agent")
            if args.self_merged:
                raise ValueError("todo add does not support --self-merged")
            if args.no_follow_up:
                raise ValueError("todo add does not support --no-follow-up")
            if args.successor_todo_ids:
                raise ValueError("todo add does not support --successor-todo-id; use todo update/complete to link existing successor work")
            payload = add_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                role=args.role,
                text=args.text,
                status=args.status,
                task_class=args.task_class,
                action_kind=args.action_kind,
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
                    ("--task-repository", args.task_repository),
                    ("--continuation-policy", args.continuation_policy),
                    ("--required-write-scope", args.required_write_scopes),
                    ("--required-capability", args.required_capabilities),
                    ("--target-capability", args.target_capabilities),
                    ("--explore-result-node-ref", args.explore_result_node_refs),
                    ("--clear-explore-result-node-refs", args.clear_explore_result_node_refs),
                    ("--decision-scope", args.decision_scope),
                    ("--required-decision-scope", args.required_decision_scopes),
                    ("--decision-outcome", args.decision_outcome),
                    ("--bound-agent", args.bound_agent),
                    ("--goal-bound", args.goal_bound),
                    ("--blocks-agent", args.blocks_agent),
                    ("--clear-blocks-agent", args.clear_blocks_agent),
                    ("--excluded-agent", args.excluded_agents),
                    ("--clear-excluded-agents", args.clear_excluded_agents),
                    ("--global-gate", args.global_gate),
                    ("--clear-global-gate", args.clear_global_gate),
                    ("--unblocks-todo-id", args.unblocks_todo_id),
                    ("--successor-todo-id", args.successor_todo_ids),
                    ("--resume-when", args.resume_when),
                    ("--monitor-target-key", args.monitor_target_key),
                    ("--cadence", args.cadence),
                    ("--next-due-at", args.next_due_at),
                    ("--expires-at", args.expires_at),
                    ("--no-follow-up", args.no_follow_up),
                    ("--next-agent-todo", args.next_agent_todo),
                    ("--next-user-todo", args.next_user_todo),
                    ("--next-user-task-class", args.next_user_task_class),
                    ("--next-claimed-by", args.next_claimed_by),
                    ("--next-task-class", args.next_task_class),
                    ("--next-action-kind", args.next_action_kind),
                    ("--next-task-repository", args.next_task_repository),
                    ("--next-required-capability", args.next_required_capabilities),
                    ("--next-continuation-policy", args.next_continuation_policy),
                    ("--next-excluded-agent", args.next_excluded_agents),
                    ("--self-merged", args.self_merged),
                    ("--follow-up", args.followups),
                )
                if value
            ]
            if unsupported:
                raise ValueError(
                    "todo claim only accepts --todo-id, --claimed-by, --agent-id, optional --role, "
                    "--project, --state-file, and --dry-run; unsupported: "
                    + ", ".join(unsupported)
                )
            payload = update_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                claimed_by=args.claimed_by,
                agent_id=args.agent_id,
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
            if args.explore_result_node_refs and args.clear_explore_result_node_refs:
                raise ValueError(
                    "todo update accepts either --explore-result-node-ref or "
                    "--clear-explore-result-node-refs, not both"
                )
            if not any([
                args.text,
                args.followups,
                args.status,
                args.note,
                args.evidence,
                args.reason,
                args.task_class,
                args.action_kind,
                args.task_repository,
                args.continuation_policy,
                args.required_write_scopes,
                args.required_capabilities,
                args.target_capabilities,
                args.capability_gap_status,
                args.explore_result_node_refs,
                args.clear_explore_result_node_refs,
                args.decision_scope,
                args.required_decision_scopes,
                args.claimed_by,
                args.bound_agent,
                args.goal_bound,
                args.blocks_agent,
                args.clear_blocks_agent,
                args.excluded_agents,
                args.clear_excluded_agents,
                args.global_gate,
                args.clear_global_gate,
                args.unblocks_todo_id,
                args.successor_todo_ids,
                args.resume_when,
                args.clear_resume_when,
                args.no_follow_up,
                args.monitor_target_key,
                args.cadence,
                args.next_due_at,
                args.expires_at,
                args.clear_claim,
            ]):
                raise ValueError("todo update requires at least one mutable todo field")
            if args.no_follow_up and not (args.note or args.reason or args.evidence):
                raise ValueError("--no-follow-up requires --note, --reason, or --evidence")
            if args.decision_outcome:
                raise ValueError(
                    "todo update does not accept --decision-outcome; use todo complete"
                )
            if args.followups:
                raise ValueError("todo update does not support --follow-up; use `todo capture-followups`")
            if args.next_claimed_by:
                raise ValueError("todo update does not support --next-claimed-by")
            if args.next_task_repository:
                raise ValueError("todo update does not support --next-task-repository")
            if args.next_required_capabilities:
                raise ValueError("todo update does not support --next-required-capability")
            if args.next_continuation_policy:
                raise ValueError("todo update does not support --next-continuation-policy")
            if args.next_excluded_agents:
                raise ValueError("todo update does not support --next-excluded-agent")
            if args.self_merged:
                raise ValueError("todo update does not support --self-merged")
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
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "complete":
            if not args.todo_id:
                raise ValueError("todo complete requires --todo-id")
            if args.explore_result_node_refs or args.clear_explore_result_node_refs:
                raise ValueError(
                    "todo complete does not update --explore-result-node-ref; use todo update first"
                )
            if args.claimed_by and args.clear_claim:
                raise ValueError("todo complete accepts either --claimed-by or --clear-claim, not both")
            if args.task_repository or args.bound_agent or args.goal_bound or args.blocks_agent or args.clear_blocks_agent or args.excluded_agents or args.clear_excluded_agents or args.global_gate or args.clear_global_gate or args.unblocks_todo_id or args.resume_when:
                raise ValueError("todo complete does not update current todo routing metadata; use todo update first")
            if args.monitor_target_key or args.cadence or args.next_due_at or args.expires_at:
                raise ValueError("todo complete does not support monitor schedule metadata; use todo update before completion")
            if args.no_follow_up and (args.next_agent_todo or args.next_user_todo):
                raise ValueError("--no-follow-up cannot be combined with successor todos")
            if args.no_follow_up and args.successor_todo_ids:
                raise ValueError("--no-follow-up cannot be combined with successor todos")
            if args.successor_todo_ids and (args.next_agent_todo or args.next_user_todo):
                raise ValueError("--successor-todo-id links existing work and cannot be combined with --next-agent-todo or --next-user-todo")
            if args.no_follow_up and not (args.note or args.evidence):
                raise ValueError("--no-follow-up requires --note or --evidence")
            if args.followups:
                raise ValueError("todo complete does not support --follow-up; use `todo capture-followups`")
            if args.continuation_policy:
                raise ValueError(
                    "todo complete does not update --continuation-policy; use todo update first"
                )
            validate_successor_routing_options(args)
            payload = complete_goal_todo(
                registry_path=registry_path,
                goal_id=args.goal_id,
                todo_id=args.todo_id,
                role=args.role,
                decision_outcome=args.decision_outcome,
                evidence=args.evidence,
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
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "supersede":
            if not args.todo_id:
                raise ValueError("todo supersede requires --todo-id")
            if args.explore_result_node_refs or args.clear_explore_result_node_refs:
                raise ValueError(
                    "todo supersede does not update --explore-result-node-ref; use todo update first"
                )
            if args.decision_outcome:
                raise ValueError(
                    "todo supersede does not accept --decision-outcome; use todo complete"
                )
            if args.claimed_by:
                raise ValueError(
                    "todo supersede does not support --claimed-by; use --next-claimed-by "
                    "to assign the successor, or omit it to inherit the superseded todo "
                    "owner when present"
                )
            if args.clear_claim:
                raise ValueError("todo supersede does not support --clear-claim")
            if args.self_merged:
                raise ValueError("todo supersede does not support --self-merged")
            if args.no_follow_up:
                raise ValueError("todo supersede does not support --no-follow-up")
            if args.followups:
                raise ValueError("todo supersede does not support --follow-up; use `todo capture-followups`")
            if args.continuation_policy:
                raise ValueError(
                    "todo supersede does not update --continuation-policy; use todo update first"
                )
            validate_successor_routing_options(args)
            if args.blocks_agent or args.clear_blocks_agent or args.excluded_agents or args.clear_excluded_agents or args.global_gate or args.clear_global_gate or args.unblocks_todo_id or args.resume_when:
                raise ValueError("todo supersede does not update current todo routing metadata; use todo update first")
            if args.successor_todo_ids:
                raise ValueError("todo supersede does not support --successor-todo-id; use --next-agent-todo or update the source todo before supersede")
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
                project=Path(args.project).expanduser() if args.project else None,
                state_file=Path(args.state_file).expanduser() if args.state_file else None,
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "archive-completed":
            if args.decision_outcome:
                raise ValueError(
                    "todo archive-completed does not support --decision-outcome"
                )
            if args.claimed_by or args.clear_claim:
                raise ValueError("todo archive-completed does not support --claimed-by or --clear-claim")
            if args.clear_blocks_agent or args.excluded_agents or args.clear_excluded_agents or args.next_excluded_agents:
                raise ValueError("todo archive-completed does not support executor exclusions")
            if args.next_claimed_by:
                raise ValueError("todo archive-completed does not support --next-claimed-by")
            if args.next_task_repository or args.next_required_capabilities:
                raise ValueError(
                    "todo archive-completed does not support successor routing metadata"
                )
            if args.self_merged:
                raise ValueError("todo archive-completed does not support --self-merged")
            if args.no_follow_up:
                raise ValueError("todo archive-completed does not support --no-follow-up")
            if args.followups:
                raise ValueError("todo archive-completed does not support --follow-up; use `todo capture-followups`")
            if args.successor_todo_ids:
                raise ValueError("todo archive-completed does not support --successor-todo-id")
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
            unsupported = unsupported_todo_options(
                args,
                allowed_fields={
                    "agent_id",
                    "suggestion_sources",
                    "suggestion_limit",
                    "suggestion_trigger",
                },
            )
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
            unsupported = unsupported_todo_options(
                args,
                allowed_fields={
                    "text",
                    "followups",
                    "evidence",
                    "task_class",
                    "action_kind",
                    "continuation_policy",
                    "required_write_scopes",
                    "required_capabilities",
                    "target_capabilities",
                    "required_decision_scopes",
                    "state_file",
                },
            )
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
    append_todo_rollout_event(
        payload,
        args=args,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        append_cli_rollout_event=append_cli_rollout_event,
    )
    print_payload(payload, args.format, renderer)
    return 0 if payload.get("ok") else 1
