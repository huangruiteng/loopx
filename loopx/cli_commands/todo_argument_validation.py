from __future__ import annotations

import argparse
from collections.abc import Iterable


TODO_OPTION_FIELDS = (
    ("--role", "role"),
    ("--text", "text"),
    ("--follow-up", "followups"),
    ("--todo-id", "todo_id"),
    ("--status", "status"),
    ("--note", "note"),
    ("--evidence", "evidence"),
    ("--reason", "reason"),
    ("--authority-reason", "authority_reason"),
    ("--task-class", "task_class"),
    ("--action-kind", "action_kind"),
    ("--task-repository", "task_repository"),
    ("--continuation-policy", "continuation_policy"),
    ("--required-write-scope", "required_write_scopes"),
    ("--required-capability", "required_capabilities"),
    ("--target-capability", "target_capabilities"),
    ("--capability-gap-status", "capability_gap_status"),
    ("--explore-result-node-ref", "explore_result_node_refs"),
    ("--clear-explore-result-node-refs", "clear_explore_result_node_refs"),
    ("--decision-scope", "decision_scope"),
    ("--required-decision-scope", "required_decision_scopes"),
    ("--claimed-by", "claimed_by"),
    ("--bound-agent", "bound_agent"),
    ("--goal-bound", "goal_bound"),
    ("--blocks-agent", "blocks_agent"),
    ("--clear-blocks-agent", "clear_blocks_agent"),
    ("--excluded-agent", "excluded_agents"),
    ("--clear-excluded-agents", "clear_excluded_agents"),
    ("--global-gate", "global_gate"),
    ("--clear-global-gate", "clear_global_gate"),
    ("--unblocks-todo-id", "unblocks_todo_id"),
    ("--successor-todo-id", "successor_todo_ids"),
    ("--resume-when", "resume_when"),
    ("--clear-resume-when", "clear_resume_when"),
    ("--monitor-target-key", "monitor_target_key"),
    ("--cadence", "cadence"),
    ("--next-due-at", "next_due_at"),
    ("--expires-at", "expires_at"),
    ("--clear-claim", "clear_claim"),
    ("--no-follow-up", "no_follow_up"),
    ("--next-agent-todo", "next_agent_todo"),
    ("--next-user-todo", "next_user_todo"),
    ("--next-user-task-class", "next_user_task_class"),
    ("--next-claimed-by", "next_claimed_by"),
    ("--next-task-class", "next_task_class"),
    ("--next-action-kind", "next_action_kind"),
    ("--next-task-repository", "next_task_repository"),
    ("--next-required-capability", "next_required_capabilities"),
    ("--next-continuation-policy", "next_continuation_policy"),
    ("--next-excluded-agent", "next_excluded_agents"),
    ("--self-merged", "self_merged"),
    ("--agent-id", "agent_id"),
    ("--from", "suggestion_sources"),
    ("--limit", "suggestion_limit"),
    ("--trigger", "suggestion_trigger"),
    ("--state-file", "state_file"),
    ("--execute", "execute"),
)


def unsupported_todo_options(
    args: argparse.Namespace,
    *,
    allowed_fields: Iterable[str],
) -> list[str]:
    allowed = set(allowed_fields)
    return [
        flag
        for flag, field in TODO_OPTION_FIELDS
        if field not in allowed and getattr(args, field, None)
    ]


def validate_shared_todo_options(args: argparse.Namespace) -> None:
    agent_id_allowed_for_user_authoring = (
        args.todo_command == "add"
        and args.role == "user"
        and args.task_class in {"user_gate", "user_action"}
    )
    agent_id_allowed_for_read = args.todo_command == "list"
    agent_id_allowed_for_lifecycle = args.todo_command in {
        "claim",
        "update",
        "complete",
        "supersede",
    }
    global_gate_allowed = args.todo_command in {"add", "update"}
    clear_global_gate_allowed = args.todo_command == "update"
    authority_reason_allowed = args.todo_command in {
        "update",
        "complete",
        "supersede",
    }
    if args.authority_reason and not authority_reason_allowed:
        raise ValueError(
            "--authority-reason is supported only by todo update/complete/supersede"
        )
    if (
        args.todo_command not in {"suggest", "capture-followups"}
        and args.agent_id
        and not agent_id_allowed_for_user_authoring
        and not agent_id_allowed_for_read
        and not agent_id_allowed_for_lifecycle
    ):
        if args.todo_command == "add" and args.role == "agent":
            raise ValueError(
                "todo add does not support --agent-id for agent todos; omit "
                "--agent-id and use --claimed-by <registered-agent> only when "
                "assigning execution, or omit both options to leave the todo "
                "unclaimed."
            )
        raise ValueError(
            f"todo {args.todo_command} does not support --agent-id; --agent-id "
            "scopes todo list/suggest, user-todo authoring, and lifecycle actor "
            "attribution only."
        )
    if args.global_gate and not global_gate_allowed:
        raise ValueError(
            "--global-gate is supported only by todo add/update for user_gate items"
        )
    if args.clear_global_gate and not clear_global_gate_allowed:
        raise ValueError(
            "--clear-global-gate is supported only by todo update for user_gate items"
        )
    if args.clear_resume_when and args.todo_command != "update":
        raise ValueError("--clear-resume-when is supported only by todo update")
    if args.clear_resume_when and args.resume_when:
        raise ValueError(
            "todo update accepts either --resume-when or --clear-resume-when, not both"
        )
    if (
        args.todo_command not in {"suggest", "capture-followups"}
        and (
            args.suggestion_sources
            or args.suggestion_limit is not None
            or args.suggestion_trigger
        )
    ):
        raise ValueError(
            "--from, --limit, and --trigger are supported only by todo suggest"
        )


def validate_capability_gap_options(args: argparse.Namespace) -> None:
    if not args.capability_gap_status:
        return
    if args.todo_command not in {"add", "update"}:
        raise ValueError("--capability-gap-status is supported only by todo add/update")
    if args.role != "agent":
        raise ValueError("--capability-gap-status requires --role agent")
    if not args.target_capabilities:
        raise ValueError(
            "--capability-gap-status requires at least one --target-capability"
        )
    if (
        args.capability_gap_status in {"fixed", "real_callsite_verified"}
        and not args.evidence
    ):
        raise ValueError(
            "fixed and real_callsite_verified capability gaps require "
            "public-safe --evidence"
        )


def validate_successor_routing_options(args: argparse.Namespace) -> None:
    if args.next_user_task_class and not args.next_user_todo:
        raise ValueError("--next-user-task-class requires --next-user-todo")
    if args.next_continuation_policy and not args.next_agent_todo:
        raise ValueError("--next-continuation-policy requires --next-agent-todo")
    if args.next_task_repository and not args.next_agent_todo:
        raise ValueError("--next-task-repository requires --next-agent-todo")
    if args.next_required_capabilities and not args.next_agent_todo:
        raise ValueError("--next-required-capability requires --next-agent-todo")
    if args.next_excluded_agents and not args.next_agent_todo:
        raise ValueError("--next-excluded-agent requires --next-agent-todo")
