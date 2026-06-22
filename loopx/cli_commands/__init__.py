"""Modular CLI command registrations.

Command modules expose two small functions:

- ``register_*_command(subparsers)`` wires argparse for one command group.
- ``handle_*_command(args, print_payload)`` executes the parsed command.

The top-level CLI keeps global options, registry fallback, and dispatch order.
"""

from .agents_last_exam import (
    handle_agents_last_exam_command,
    register_agents_last_exam_commands,
)
from .benchmark_boundary import (
    handle_benchmark_boundary_command,
    register_benchmark_boundary_commands,
)
from .benchmark_review_lifecycle import (
    handle_benchmark_review_lifecycle_command,
    register_benchmark_review_lifecycle_commands,
)
from .doctor import handle_doctor_command, register_doctor_command
from .dreaming import handle_dreaming_command, register_dreaming_commands
from .history import handle_history_command, register_history_command
from .ml_experiment import handle_ml_experiment_command, register_ml_experiment_commands
from .quota import handle_quota_command, register_quota_command
from .starter import (
    handle_codex_cli_bounded_visible_pilot_adapter_command,
    handle_codex_cli_bootstrap_message_command,
    handle_codex_cli_exec_handoff_command,
    handle_codex_cli_visible_first_response_capture_plan_command,
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
from .terminal_bench_adapter import (
    handle_terminal_bench_adapter_command,
    register_terminal_bench_adapter_commands,
)
from .todo import handle_todo_command, register_todo_command

__all__ = [
    "handle_agents_last_exam_command",
    "handle_benchmark_boundary_command",
    "handle_benchmark_review_lifecycle_command",
    "handle_check_command",
    "handle_codex_cli_bounded_visible_pilot_adapter_command",
    "handle_codex_cli_bootstrap_message_command",
    "handle_codex_cli_exec_handoff_command",
    "handle_codex_cli_visible_first_response_capture_plan_command",
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
    "handle_history_command",
    "handle_ml_experiment_command",
    "handle_new_project_prompt_command",
    "handle_quota_command",
    "handle_review_packet_command",
    "handle_status_command",
    "handle_terminal_bench_adapter_command",
    "handle_todo_command",
    "register_agents_last_exam_commands",
    "register_benchmark_boundary_commands",
    "register_benchmark_review_lifecycle_commands",
    "register_doctor_command",
    "register_dreaming_commands",
    "register_history_command",
    "register_ml_experiment_commands",
    "register_quota_command",
    "register_starter_commands",
    "register_status_commands",
    "register_terminal_bench_adapter_commands",
    "register_todo_command",
]
