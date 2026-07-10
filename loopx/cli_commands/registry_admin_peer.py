from __future__ import annotations

import argparse


def register_peer_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agent-model",
        choices=("peer_v1",),
        help=(
            "Agent runtime model. peer_v1 removes identity rank and routes work through "
            "claims, leases, deterministic task assignment, and task-scoped coordination."
        ),
    )
    parser.add_argument(
        "--ack-automation-prompt-migration",
        metavar="MIGRATION_ID",
        help=(
            "Acknowledge that the installed host automation was updated for this stable "
            "migration id, then atomically remove legacy hierarchy fields. Repeating the "
            "same completed id is a no-op."
        ),
    )
