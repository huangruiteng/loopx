"""Modular CLI command registrations.

Command modules expose two small functions:

- ``register_*_command(subparsers)`` wires argparse for one command group.
- ``handle_*_command(args, print_payload)`` executes the parsed command.

The top-level CLI keeps global options, registry fallback, and dispatch order.
"""

from .doctor import handle_doctor_command, register_doctor_command
from .dreaming import handle_dreaming_command, register_dreaming_commands
from .starter import (
    handle_codex_cli_bounded_visible_pilot_adapter_command,
    handle_codex_cli_bootstrap_message_command,
    handle_codex_cli_exec_handoff_command,
    handle_codex_cli_local_driver_plan_command,
    handle_codex_cli_local_scheduler_exec_command,
    handle_codex_cli_local_scheduler_tick_command,
    handle_codex_cli_one_message_loop_pilot_command,
    handle_codex_cli_runtime_idle_detector_command,
    handle_codex_cli_session_probe_command,
    handle_codex_cli_tui_bootstrap_smoke_bundle_command,
    handle_codex_cli_visible_attach_acceptance_command,
    handle_codex_cli_visible_local_driver_pilot_command,
    handle_codex_cli_visible_driver_run_command,
    handle_codex_cli_visible_driver_plan_command,
    handle_codex_cli_visible_session_proof_command,
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
    "handle_codex_cli_bounded_visible_pilot_adapter_command",
    "handle_codex_cli_bootstrap_message_command",
    "handle_codex_cli_exec_handoff_command",
    "handle_codex_cli_local_driver_plan_command",
    "handle_codex_cli_local_scheduler_exec_command",
    "handle_codex_cli_local_scheduler_tick_command",
    "handle_codex_cli_one_message_loop_pilot_command",
    "handle_codex_cli_runtime_idle_detector_command",
    "handle_codex_cli_session_probe_command",
    "handle_codex_cli_tui_bootstrap_smoke_bundle_command",
    "handle_codex_cli_visible_attach_acceptance_command",
    "handle_codex_cli_visible_local_driver_pilot_command",
    "handle_codex_cli_visible_driver_run_command",
    "handle_codex_cli_visible_driver_plan_command",
    "handle_codex_cli_visible_session_proof_command",
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
