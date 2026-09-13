"""Owner-local parser registration for the compact reward overlay command.

The command is a cohesive slice: one overlay append with its optional lesson
fields and state-summary writeback. Keeping it beside the other project
lifecycle registrations pushed that module over its size budget, so it owns a
module here instead of growing the shared file.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from ..feedback import LESSON_KINDS


def register_reward_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
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


__all__ = ["register_reward_command"]
