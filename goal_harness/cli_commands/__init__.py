"""Modular CLI command registrations.

Command modules expose two small functions:

- ``register_*_command(subparsers)`` wires argparse for one command group.
- ``handle_*_command(args, print_payload)`` executes the parsed command.

The top-level CLI keeps global options, registry fallback, and dispatch order.
"""

from .doctor import handle_doctor_command, register_doctor_command
from .dreaming import handle_dreaming_command, register_dreaming_commands
from .starter import (
    handle_demo_command,
    handle_new_project_prompt_command,
    register_starter_commands,
)
from .status import (
    handle_check_command,
    handle_diagnose_command,
    handle_review_packet_command,
    handle_status_command,
    register_status_commands,
)

__all__ = [
    "handle_check_command",
    "handle_diagnose_command",
    "handle_demo_command",
    "handle_doctor_command",
    "handle_dreaming_command",
    "handle_new_project_prompt_command",
    "handle_review_packet_command",
    "handle_status_command",
    "register_doctor_command",
    "register_dreaming_commands",
    "register_starter_commands",
    "register_status_commands",
]
