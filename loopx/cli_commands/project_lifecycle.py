from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..delivery_batch_scale import DELIVERY_BATCH_SCALE_CHOICES
from ..delivery_outcome import DELIVERY_OUTCOME_CHOICES
from ..feedback import LESSON_KINDS, append_human_reward, compact_reward, render_reward_markdown
from ..operator_gate import (
    DEFAULT_OPERATOR_GATE,
    OPERATOR_GATE_DECISIONS,
    record_operator_gate,
    render_operator_gate_markdown,
)
from ..project_map import (
    DEFAULT_PROJECT_MAP_CLASSIFICATION,
    read_only_project_map_run,
    render_read_only_project_map_markdown,
)
from ..state_refresh import (
    DEFAULT_REFRESH_ACTION,
    DEFAULT_REFRESH_CLASSIFICATION,
    refresh_state_run,
    render_state_refresh_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]
AppendCliRolloutEvent = Callable[..., dict[str, object]]

PROJECT_LIFECYCLE_COMMANDS = {
    "refresh-state",
    "read-only-map",
    "reward",
    "operator-gate",
}


def register_project_lifecycle_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    refresh_state_parser = subparsers.add_parser(
        "refresh-state",
        help="Append a read-only run from active goal state after state-only updates.",
    )
    add_subcommand_format(refresh_state_parser)
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
        "--next-action",
        help=(
            "Explicitly update the active state's durable ## Next Action before "
            "appending the refresh run. Without this flag, --recommended-action "
            "only describes the run record."
        ),
    )
    refresh_state_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional explicit delivery scale for this refresh run, overriding classification-name inference.",
    )
    refresh_state_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional explicit outcome-floor signal for this refresh run.",
    )
    refresh_state_parser.add_argument(
        "--autonomous-replan-recorded",
        action="store_true",
        help=(
            "Mark this refresh as the explicit autonomous replan ACK. "
            "Use only after the agent has performed and written back the bounded replan slice."
        ),
    )
    refresh_state_parser.add_argument(
        "--agent-id",
        help=(
            "Registered agent id for agent-lane state refreshes. When set, the "
            "refresh is visible in run history but does not replace goal-level status."
        ),
    )
    refresh_state_parser.add_argument(
        "--agent-lane",
        help="Public-safe lane label for --agent-id scoped refreshes, such as productization_frontstage.",
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

    read_only_map_parser = subparsers.add_parser(
        "read-only-map",
        help="Append a generic read-only project-map run for a connected project.",
    )
    add_subcommand_format(read_only_map_parser)
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

    reward_parser = subparsers.add_parser(
        "reward",
        help="Append a compact human reward overlay to a goal run index.",
    )
    add_subcommand_format(reward_parser)
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
        "--lesson-kind",
        choices=sorted(LESSON_KINDS),
        help="Optional public-safe lesson kind when this reward records an explicit user correction.",
    )
    reward_parser.add_argument(
        "--lesson-summary",
        help="Short public-safe lesson summary. Required when --lesson-kind is set.",
    )
    reward_parser.add_argument(
        "--lesson-avoid",
        action="append",
        default=[],
        help="Public-safe phrase/action that future recommended_action should avoid. Repeatable.",
    )
    reward_parser.add_argument(
        "--lesson-prefer",
        action="append",
        default=[],
        help="Public-safe phrase/action that future recommended_action should prefer. Repeatable.",
    )
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

    gate_parser = subparsers.add_parser(
        "operator-gate",
        help="Record an operator gate decision such as read-only map opt-in.",
    )
    add_subcommand_format(gate_parser)
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


def handle_project_lifecycle_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
    output_format: OutputFormat,
    append_cli_rollout_event: AppendCliRolloutEvent,
) -> int | None:
    if args.command not in PROJECT_LIFECYCLE_COMMANDS:
        return None

    fmt = output_format(args)
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
                next_action=args.next_action,
                delivery_batch_scale=args.delivery_batch_scale,
                delivery_outcome=args.delivery_outcome,
                agent_id=args.agent_id,
                agent_lane=args.agent_lane,
                autonomous_replan_recorded=bool(args.autonomous_replan_recorded),
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
        if payload.get("ok") and payload.get("appended") and not payload.get("dry_run"):
            append_cli_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
                event_kind="refresh_state",
                agent_id=args.agent_id,
                status="appended",
                summary=(
                    "refresh-state appended compact control-plane state with "
                    f"classification={payload.get('classification')}"
                ),
                details={
                    "command": "refresh-state",
                    "progress_scope": payload.get("progress_scope") or "",
                    "agent_lane": payload.get("agent_lane") or "",
                    "autonomous_replan_recorded": bool(
                        payload.get("autonomous_replan_recorded")
                    ),
                    "global_sync_wrote": bool(
                        isinstance(payload.get("global_sync"), dict)
                        and payload["global_sync"].get("wrote")
                    ),
                },
            )
        print_payload(payload, fmt, render_state_refresh_markdown)
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
        print_payload(payload, fmt, render_read_only_project_map_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "reward":
        try:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
                lesson={
                    "kind": args.lesson_kind,
                    "summary": args.lesson_summary,
                    "avoid": args.lesson_avoid,
                    "prefer": args.lesson_prefer,
                }
                if args.lesson_kind
                else None,
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
        print_payload(payload, fmt, render_reward_markdown)
        return 0 if payload.get("ok") else 1

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
    print_payload(payload, fmt, render_operator_gate_markdown)
    return 0 if payload.get("ok") else 1
