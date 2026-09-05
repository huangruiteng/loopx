from __future__ import annotations

import argparse
import os
import stat
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from ..control_plane.todos.contract import (
    TODO_CONTINUATION_POLICY_VALUES,
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_todo_continuation_policy,
    normalize_todo_task_class,
    replan_successor_semantic_binding,
)
from ..control_plane.capability_hooks import PostWritebackHookRegistration
from ..control_plane.coordination.runtime_shadow import (
    build_todo_runtime_shadow_projection,
    dispatch_coordination_runtime_shadow,
    load_task_lease_runtime_shadow_records,
    resolve_coordination_runtime_shadow_config,
)
from ..control_plane.coordination.local_authority import (
    read_canonical_todos_if_promoted,
)
from ..control_plane.quota.settlement import (
    QuotaSettlementReadback,
    read_heartbeat_settlement,
    settlement_result_payload,
)
from ..control_plane.todos.markdown import render_todo_markdown
from ..control_plane.todos.machine_section_projection import (
    render_canonical_todo_sections,
)
from ..file_lock import exclusive_file_lock
from ..history import load_index, load_registry
from ..paths import resolve_runtime_root
from ..registry import find_registry_goal, registry_goals
from ..control_plane.work_items.semantic_replan_writeback import (
    qualify_replan_writeback,
)
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
    resolve_todo_state,
    resolve_todo_state_path,
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
    validate_todo_project_markdown_options,
    validate_todo_suggest_options,
    validate_todo_supersede_options,
    validate_todo_update_options,
)
from .todo_event import (
    RolloutEventAppender,
    TODO_EVENT_KINDS,
    append_todo_rollout_event,
    todo_error_payload,
)
from .post_writeback import (
    PostWritebackProjectionBuilder,
    dispatch_committed_cli_post_writeback_hooks,
)
from ..control_plane.agents.capability_gate import (
    runtime_capabilities_for_cli_projection,
)
from ..control_plane.turn_driver.journal_store import (
    turn_journal_observed_capabilities,
)


def _fsync_parent_directory(path: Path) -> None:
    if os.name != "posix":  # pragma: no cover - Windows has no directory fsync
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_text(path: Path, text: str) -> None:
    """Durably replace a projection without changing the state-file mode."""

    original_mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            os.chmod(temporary_path, original_mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_parent_directory(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_text_exact(path: Path) -> str:
    """Decode UTF-8 while preserving every source newline sequence."""

    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def _mirror_committed_todo_runtime_shadow(
    payload: dict[str, object],
    *,
    args: argparse.Namespace,
    registry_path: Path,
    runtime_root_arg: str | None,
) -> dict[str, object] | None:
    """Mirror an actual Todo write only after the legacy write has committed."""

    if not payload.get("ok") or payload.get("dry_run"):
        return None
    changed = bool(payload.get("changed")) or any(
        bool(payload.get(field))
        for field in ("added", "metadata_updated", "status_changed")
    )
    if not changed:
        return None

    try:
        registry = load_registry(registry_path)
        goal = find_registry_goal(registry, args.goal_id)
        shadow_enabled = resolve_coordination_runtime_shadow_config(goal).enabled
    except Exception:
        # The optional observer cannot turn a committed canonical mutation into
        # a failed command while the feature remains absent or unreadable.
        return None
    if not shadow_enabled:
        return None

    rollout_event = payload.get("rollout_event")
    event_id = (
        str(rollout_event.get("event_id") or "").strip()
        if isinstance(rollout_event, dict)
        else ""
    )
    source_version = str(payload.get("updated_at") or "").strip()
    if not event_id or not source_version:
        return {
            "schema_version": "loopx_coordination_runtime_shadow_dispatch_v0",
            "status": "failed",
            "reason_code": "canonical_mutation_identity_missing",
            "primary_writeback_preserved": True,
            "decision_read_from_shadow": False,
        }

    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    try:
        todo_projection = list_goal_todos(
            registry_path=registry_path,
            goal_id=args.goal_id,
            **_todo_path_args(args),
            runtime_root_arg=runtime_root_arg,
        )
        projection = build_todo_runtime_shadow_projection(
            goal_id=args.goal_id,
            todos=todo_projection.get("todos"),
            leases=load_task_lease_runtime_shadow_records(
                runtime_root=runtime_root,
                goal_id=args.goal_id,
            ),
        )
    except Exception as exc:
        return {
            "schema_version": "loopx_coordination_runtime_shadow_dispatch_v0",
            "status": "failed",
            "reason_code": "shadow_projection_unavailable",
            "reason": str(exc),
            "primary_writeback_preserved": True,
            "decision_read_from_shadow": False,
        }
    return dispatch_coordination_runtime_shadow(
        goal=goal,
        runtime_root=runtime_root,
        goal_id=args.goal_id,
        operation_id=f"todo-shadow:{event_id}",
        event_kind=TODO_EVENT_KINDS.get(args.todo_command, "todo_update"),
        source_version=source_version,
        projection=projection,
    )


def _completion_settlement_requirement(
    todo: dict[str, object],
    *,
    no_follow_up: bool,
) -> str | None:
    if no_follow_up:
        return "terminal no-follow-up closeout"
    task_class = normalize_todo_task_class(
        todo.get("task_class"),
        text=str(todo.get("text") or ""),
        action_kind=todo.get("action_kind"),
    )
    continuation_policy = normalize_todo_continuation_policy(
        todo.get("continuation_policy")
    )
    if (
        str(todo.get("role") or "") == "agent"
        and task_class == TODO_TASK_CLASS_ADVANCEMENT
        and continuation_policy != "same_agent_non_delivery"
    ):
        return "turn-scoped advancement completion"
    return None


def _completion_settlement_error(
    todo: dict[str, object],
    settlement_readback: QuotaSettlementReadback,
    *,
    no_follow_up: bool,
) -> str | None:
    requirement = _completion_settlement_requirement(
        todo,
        no_follow_up=no_follow_up,
    )
    if requirement is None or settlement_readback.settlement.failure is None:
        return None
    return (
        f"{requirement} requires matching writeback and quota spend receipts: "
        + settlement_readback.settlement.failure.reason
    )


def _validated_replan_successor_obligation(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
) -> str | None:
    requested = str(getattr(args, "replan_obligation_id", None) or "").strip()
    if not requested:
        return None
    if not (
        args.role == "agent"
        and args.task_class == "advancement_task"
        and args.claimed_by
    ):
        raise ValueError(
            "--replan-obligation-id requires --role agent --task-class "
            "advancement_task and --claimed-by"
        )
    if replan_successor_semantic_binding(
        action_kind=args.action_kind,
        target_key=args.monitor_target_key,
        explore_result_node_refs=args.explore_result_node_refs,
    ) is None:
        raise ValueError(
            "--replan-obligation-id requires --action-kind and either "
            "--target-key or --explore-result-node-ref"
        )
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    _, _, state_text, _ = resolve_todo_state(
        registry_path=registry_path,
        goal_id=args.goal_id,
        **_todo_path_args(args),
    )
    existing_runs, _ = load_index(
        runtime_root / "goals" / args.goal_id / "runs" / "index.jsonl"
    )
    newest_first_runs = [
        run
        for _, run in sorted(
            enumerate(existing_runs),
            key=lambda item: (
                str(item[1].get("generated_at") or ""),
                item[0],
            ),
            reverse=True,
        )
    ]
    registry_goal = next(
        (
            item
            for item in registry_goals(registry)
            if str(item.get("id") or "").strip() == args.goal_id
        ),
        None,
    )
    obligation, _ = qualify_replan_writeback(
        newest_first_runs=newest_first_runs,
        state_text=state_text,
        agent_id=args.claimed_by,
        goal_id=args.goal_id,
        registry_goal=registry_goal,
    )
    current = str((obligation or {}).get("obligation_id") or "").strip()
    if not current:
        raise ValueError(
            "--replan-obligation-id was provided but this agent has no open "
            "replan obligation"
        )
    if current != requested:
        raise ValueError(
            "--replan-obligation-id does not match the current open obligation: "
            f"expected {current}"
        )
    return current


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
            "project-markdown",
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
    todo_parser.add_argument(
        "--turn-instance-id",
        help=(
            "For todo complete, bind the lifecycle receipt to the original "
            "turn-scoped quota guard and reuse it on retries."
        ),
    )
    todo_parser.add_argument(
        "--completion-identity-key",
        help=(
            "For todo complete --no-follow-up lifecycle reentry, reuse the "
            "exact completion identity projected by LoopX. This is not a quota "
            "turn id and cannot be combined with --turn-instance-id."
        ),
    )
    todo_parser.add_argument(
        "--replan-obligation-id",
        help=(
            "For todo add, bind one newly selected runnable advancement successor "
            "to the exact open replan obligation. Requires --action-kind and a "
            "stable --target-key or --explore-result-node-ref. The Todo write "
            "becomes the semantic receipt; no follow-up ACK command is required."
        ),
    )
    todo_parser.add_argument("--status", choices=["open", "done", "blocked", "deferred"], help="For todo add/update, set the lifecycle status.")
    todo_parser.add_argument("--note", help="Public-safe note to attach to a lifecycle transition.")
    todo_parser.add_argument("--evidence", help="Public-safe evidence pointer or short result for complete/update.")
    todo_parser.add_argument(
        "--validation-command",
        help=(
            "Caller-approved validation command (no shell) to run before a "
            "todo's completion commits, e.g. 'pytest -q tests/test_x.py'. Set "
            "on `todo add`; completion runs it independently and blocks on a "
            "non-zero exit."
        ),
    )
    todo_parser.add_argument(
        "--validation-label",
        help="Optional public-safe label for the validation receipt.",
    )
    todo_parser.add_argument(
        "--validation-command-json",
        help=(
            "Trusted JSON string array (argv form, no shell parsing) for the "
            "completion validation command, e.g. '[\"pytest\",\"-q\",\"tests/"
            "test_x.py\"]'. Mutually exclusive with --validation-command; set "
            "on `todo add`."
        ),
    )
    todo_parser.add_argument(
        "--validation-timeout-seconds",
        type=int,
        help=(
            "Per-todo timeout for the caller-approved validation command. "
            "Only meaningful with --validation-command or "
            "--validation-command-json on `todo add`; must be 1-29 so a "
            "timed-out validation still produces a typed receipt inside the "
            "30s outer subprocess budget. Defaults to 20."
        ),
    )
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
            "For todo complete and todo supersede, prove the execution instance "
            "that owns an active hard task lease. Required when that todo has an "
            "effective lease."
        ),
    )
    todo_parser.add_argument(
        "--task-lease-expected-version",
        type=int,
        help=(
            "For todo complete and todo supersede, supply the active hard task "
            "lease version. Required with --task-lease-idempotency-key when the "
            "lease is effective."
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
        "--watch-only",
        action="store_true",
        help=(
            "For agent continuous_monitor add/update, declare an intentionally "
            "unbounded liveness watch. Watch-only monitors remain schedulable but "
            "do not drive autonomous replan or block goal convergence."
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
        dest="todo_limit",
        type=int,
        help=(
            "For todo suggest, maximum candidate count; values above 5 are "
            "clamped to 5. For todo list, explicit per-section cold-path cap: "
            "keep the top N todos of each role section after filtering; must "
            "be an integer >= 1, and the payload discloses the truncation via "
            "explicit_limit."
        ),
    )
    todo_parser.add_argument(
        "--thin",
        dest="todo_thin",
        action="store_true",
        help=(
            "For todo list, return the explicit field-only projection and omit "
            "detail lanes; returns at most two items per role, and --limit can "
            "lower but not expand that bound."
        ),
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
    todo_parser.add_argument(
        "--execute",
        action="store_true",
        help="For archive-completed or project-markdown, write the active-state edit.",
    )
    todo_parser.add_argument(
        "--provider-revision",
        help=(
            "For project-markdown, exact canonical authority revision rendered "
            "into the Todo section markers."
        ),
    )


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
    post_writeback_hooks: Sequence[PostWritebackHookRegistration] | None = None,
    post_writeback_projection_builder: PostWritebackProjectionBuilder | None = None,
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
                limit=args.todo_limit,
                thin=bool(args.todo_thin),
                **_todo_path_args(args),
                runtime_root_arg=runtime_root_arg,
            )
        elif args.todo_command == "project-markdown":
            validate_todo_project_markdown_options(args)
            registry = load_registry(registry_path)
            authority_read = read_canonical_todos_if_promoted(
                runtime_root=resolve_runtime_root(registry, runtime_root_arg),
                goal_id=args.goal_id,
            )
            if not isinstance(authority_read, dict):
                raise ValueError(
                    "todo project-markdown requires promoted canonical authority; "
                    "legacy Markdown mode is unchanged"
                )
            if authority_read.get("provider_revision") != args.provider_revision:
                raise ValueError(
                    "todo project-markdown provider revision does not match the "
                    "canonical read head"
                )
            _resolved_project, state_path = resolve_todo_state_path(
                registry_path=registry_path,
                goal_id=args.goal_id,
                **_todo_path_args(args),
            )
            with exclusive_file_lock(
                state_path,
                operation="project_canonical_todo_sections",
            ):
                source = _read_text_exact(state_path)
                projection = render_canonical_todo_sections(
                    source,
                    authority_read["todos"],
                    provider_revision=args.provider_revision,
                )
                if args.execute and projection.changed:
                    _atomic_write_text(state_path, projection.markdown)
                    if _read_text_exact(state_path) != projection.markdown:
                        raise RuntimeError("Todo Markdown projection readback mismatch")
            payload = {
                "ok": True,
                "dry_run": not bool(args.execute),
                "command": "project-markdown",
                "goal_id": args.goal_id,
                "state_file": str(state_path),
                "source_authority": authority_read.get("source_authority"),
                "provider_revision": projection.provider_revision,
                "todo_count": projection.todo_count,
                "changed": projection.changed,
                "executed": bool(args.execute),
                "source_sha256": projection.source_sha256,
                "rendered_sha256": projection.rendered_sha256,
                "narrative_sha256": projection.narrative_sha256,
                "section_record_sha256": projection.section_record_sha256,
                "parse_render_parity": True,
                "narrative_preserved": True,
                "legacy_fallback_used": False,
            }
        elif args.todo_command == "add":
            validate_todo_add_options(args)
            replan_obligation_id = _validated_replan_successor_obligation(
                args,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
            )
            payload = add_goal_todo(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                goal_id=args.goal_id,
                role=args.role,
                text=args.text,
                status=args.status,
                note=args.note,
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
                replan_obligation_id=replan_obligation_id,
                resume_when=args.resume_when,
                validation_command=args.validation_command,
                validation_command_json=args.validation_command_json,
                validation_label=args.validation_label,
                validation_timeout_seconds=args.validation_timeout_seconds,
                monitor_metadata={
                    key: value
                    for key, value in {
                        "target_key": args.monitor_target_key,
                        "cadence": args.cadence,
                        "next_due_at": args.next_due_at,
                        "expires_at": args.expires_at,
                        "watch_only": "true" if args.watch_only else None,
                    }.items()
                    if value is not None
                },
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
            if replan_obligation_id and payload.get("ok"):
                payload["replan_transition"] = {
                    "schema_version": "replan_successor_transition_v0",
                    "obligation_id": replan_obligation_id,
                    "outcome": "new_runnable_successor",
                    "successor_todo_id": payload.get("todo_id"),
                    "recorded": not bool(payload.get("dry_run")),
                    "turn_boundary": "end_current_heartbeat",
                }
                if not payload.get("dry_run"):
                    payload["host_action"] = "end_current_heartbeat"
        elif args.todo_command == "claim":
            validate_todo_claim_options(args)
            payload = update_goal_todo(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
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
                runtime_root_arg=runtime_root_arg,
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
                    key: value
                    for key, value in {
                        "target_key": args.monitor_target_key,
                        "cadence": args.cadence,
                        "next_due_at": args.next_due_at,
                        "expires_at": args.expires_at,
                        "watch_only": "true" if args.watch_only else None,
                    }.items()
                    if value is not None
                },
                clear_claim=bool(args.clear_claim),
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "complete":
            validate_todo_complete_options(args)
            settlement_result = None
            settlement_identity = None
            settlement_readback = None
            completion_requires_settlement = False
            completion_error = None
            completion_turn_key = None
            completion_identity_source = None
            if getattr(args, "turn_instance_id", None):
                runtime_root = resolve_runtime_root(
                    load_registry(registry_path),
                    runtime_root_arg,
                )
                settlement_readback = read_heartbeat_settlement(
                    runtime_root,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    todo_id=args.todo_id,
                    turn_instance_id=getattr(args, "turn_instance_id", None),
                )
                if settlement_readback is None:
                    raise RuntimeError(
                        "exact settlement readback unexpectedly returned not-found"
                    )
                settlement_result = settlement_readback.identity
                if settlement_result.failure is not None:
                    raise ValueError(settlement_result.failure.reason)
                if settlement_result.value is None:
                    raise ValueError("turn-scoped Todo completion has no identity")
                identity = settlement_result.value
                settlement_identity = identity
                todo_payload = list_goal_todos(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    todo_id=args.todo_id,
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=(
                        Path(args.state_file).expanduser()
                        if args.state_file
                        else None
                    ),
                    runtime_root_arg=runtime_root_arg,
                )
                todo = (
                    todo_payload.get("todo")
                    if isinstance(todo_payload.get("todo"), dict)
                    else None
                )
                if todo is None:
                    raise ValueError(
                        "turn-scoped Todo completion requires one durable Todo"
                    )
                completion_requirement = _completion_settlement_requirement(
                    todo,
                    no_follow_up=bool(args.no_follow_up),
                )
                completion_requires_settlement = completion_requirement is not None
                completion_error = _completion_settlement_error(
                    todo,
                    settlement_readback=settlement_readback,
                    no_follow_up=bool(args.no_follow_up),
                )
                if completion_error is not None:
                    settlement_result = settlement_readback.settlement
                    payload = {
                        "ok": False,
                        "dry_run": bool(args.dry_run),
                        "completed": False,
                        "changed": False,
                        "goal_id": args.goal_id,
                        "todo_id": args.todo_id,
                        "settlement_blocked_completion": True,
                        "settlement_identity": identity.as_dict(),
                        "settlement_result": settlement_result_payload(
                            settlement_result
                        ),
                        "error": completion_error,
                    }
                completion_turn_key = identity.effect_id
                completion_identity_source = "turn_settlement"
            elif getattr(args, "completion_identity_key", None):
                completion_turn_key = str(args.completion_identity_key)
                completion_identity_source = "lifecycle_reentry"
            if completion_error is None:
                payload = complete_goal_todo(
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    goal_id=args.goal_id,
                    todo_id=args.todo_id,
                    role=args.role,
                    decision_outcome=args.decision_outcome,
                    evidence=args.evidence,
                    completion_turn_key=completion_turn_key,
                    completion_identity_source=completion_identity_source,
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
                if settlement_identity is not None:
                    payload["settlement_identity"] = settlement_identity.as_dict()
                    payload["settlement_result"] = settlement_result_payload(
                        settlement_result
                    )
        elif args.todo_command == "supersede":
            validate_todo_supersede_options(args)
            payload = supersede_goal_todo(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
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
                task_lease_idempotency_key=args.task_lease_idempotency_key,
                task_lease_expected_version=args.task_lease_expected_version,
                **_todo_path_args(args),
                dry_run=bool(args.dry_run),
            )
        elif args.todo_command == "archive-completed":
            validate_todo_archive_completed_options(args)
            payload = archive_completed_todos(
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
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
                limit=args.todo_limit,
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
                runtime_root_arg=runtime_root_arg,
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
        payload = todo_error_payload(args, exc)
    append_todo_rollout_event(
        payload,
        args=args,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        append_cli_rollout_event=append_cli_rollout_event,
    )
    runtime_shadow = _mirror_committed_todo_runtime_shadow(
        payload,
        args=args,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
    )
    if runtime_shadow is not None:
        payload["coordination_runtime_shadow"] = runtime_shadow
    if (
        args.todo_command == "complete"
        and getattr(args, "turn_instance_id", None)
        and payload.get("ok")
        and not payload.get("dry_run")
    ):
        runtime_root = resolve_runtime_root(
            load_registry(registry_path),
            runtime_root_arg,
        )
        settlement_readback = read_heartbeat_settlement(
            runtime_root,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            todo_id=args.todo_id,
            turn_instance_id=getattr(args, "turn_instance_id", None),
        )
        if settlement_readback is None:
            raise RuntimeError("exact settlement readback unexpectedly returned not-found")
        settlement_result = (
            settlement_readback.terminal_settlement
            if args.no_follow_up and settlement_identity is not None
            else settlement_readback.settlement
            if completion_requires_settlement
            else settlement_readback.identity
        )
        payload["settlement_result"] = settlement_result_payload(
            settlement_result
        )
        if settlement_result.failure is not None:
            payload["ok"] = False
            payload["receipt_repair_required"] = True
            payload["error"] = settlement_result.failure.reason
    if (
        args.todo_command == "complete"
        and payload.get("ok")
        and payload.get("completed")
        and not payload.get("dry_run")
        and post_writeback_hooks
        and settlement_identity is not None
    ):
        identity = settlement_identity.as_dict()
        committed_at = str(payload.get("updated_at") or "").strip()
        if committed_at:
            # Capability evidence comes only from the validated Turn
            # settlement context: the journaled envelope froze what this
            # Turn's scheduler already observed. No journal means no
            # evidence, and gated successors stay excluded (fail closed).
            observed = turn_journal_observed_capabilities(
                resolve_runtime_root(load_registry(registry_path), runtime_root_arg),
                goal_id=args.goal_id,
                turn_instance_id=str(identity.get("turn_instance_id") or ""),
            )
            projected = runtime_capabilities_for_cli_projection(observed)
            if projected:
                payload["available_capabilities"] = projected
            payload["post_writeback_hooks"] = (
                dispatch_committed_cli_post_writeback_hooks(
                    payload=payload,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    goal_id=args.goal_id,
                    event_kind="todo_complete",
                    identity=identity,
                    state_version=committed_at,
                    committed_at=committed_at,
                    hooks=post_writeback_hooks,
                    projection_builder=post_writeback_projection_builder,
                )
            )
    print_payload(
        payload,
        format_name or str(getattr(args, "format", None) or "markdown"),
        renderer,
    )
    return 0 if payload.get("ok") else 1
