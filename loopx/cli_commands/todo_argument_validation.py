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
    ("--task-class", "task_class"),
    ("--action-kind", "action_kind"),
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
    ("--blocks-agent", "blocks_agent"),
    ("--clear-blocks-agent", "clear_blocks_agent"),
    ("--excluded-agent", "excluded_agents"),
    ("--clear-excluded-agents", "clear_excluded_agents"),
    ("--global-gate", "global_gate"),
    ("--unblocks-todo-id", "unblocks_todo_id"),
    ("--successor-todo-id", "successor_todo_ids"),
    ("--resume-when", "resume_when"),
    ("--monitor-target-key", "monitor_target_key"),
    ("--cadence", "cadence"),
    ("--next-due-at", "next_due_at"),
    ("--expires-at", "expires_at"),
    ("--clear-claim", "clear_claim"),
    ("--no-follow-up", "no_follow_up"),
    ("--next-agent-todo", "next_agent_todo"),
    ("--next-user-todo", "next_user_todo"),
    ("--next-claimed-by", "next_claimed_by"),
    ("--next-task-class", "next_task_class"),
    ("--next-action-kind", "next_action_kind"),
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
    agent_id_allowed_for_gate_authoring = (
        args.todo_command in {"add", "update"}
        and args.role == "user"
        and args.task_class == "user_gate"
    )
    agent_id_allowed_for_read = args.todo_command == "list"
    global_gate_allowed = args.todo_command in {"add", "update"}
    if args.todo_command not in {"suggest", "capture-followups"} and (
        (
            args.agent_id
            and not agent_id_allowed_for_gate_authoring
            and not agent_id_allowed_for_read
        )
        or (args.global_gate and not global_gate_allowed)
        or args.suggestion_sources
        or args.suggestion_limit is not None
        or args.suggestion_trigger
    ):
        raise ValueError(
            "todo --agent-id is supported by `todo list`, `todo suggest`, and "
            "by `todo add/update --role user --task-class user_gate` for "
            "agent-scoped user gates; --global-gate is supported by "
            "`todo add/update --role user --task-class user_gate`; --from, --limit, and "
            "--trigger are only supported by `todo suggest`"
        )
