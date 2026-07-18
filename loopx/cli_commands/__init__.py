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
from .agents_last_exam_baked_input import (
    handle_agents_last_exam_baked_input_command,
    register_agents_last_exam_baked_input_commands,
)
from .agents_last_exam_host_codex import (
    handle_agents_last_exam_host_codex_command,
    register_agents_last_exam_host_codex_commands,
)
from .agents_last_exam_local_plan import (
    handle_agents_last_exam_local_plan_command,
    register_agents_last_exam_local_plan_commands,
)
from .agents_last_exam_launch_dry_run import (
    handle_agents_last_exam_launch_dry_run_command,
    register_agents_last_exam_launch_dry_run_commands,
)
from .agents_last_exam_runner_source import (
    handle_agents_last_exam_runner_source_command,
    register_agents_last_exam_runner_source_commands,
)
from .agents_last_exam_task_material import (
    handle_agents_last_exam_task_material_command,
    register_agents_last_exam_task_material_commands,
)
from .agents_last_exam_validation_gate import (
    handle_agents_last_exam_validation_gate_command,
    register_agents_last_exam_validation_gate_commands,
)
from .agentissue_runner_flow import (
    handle_agentissue_runner_flow_command,
    register_agentissue_runner_flow_commands,
)
from .turn import handle_turn_command, register_turn_commands
from .benchmark_boundary import (
    handle_benchmark_boundary_command,
    register_benchmark_boundary_commands,
)
from .benchmark_dispatch import (
    handle_benchmark_command,
    register_benchmark_command_group,
)
from .benchmark_review_lifecycle import (
    handle_benchmark_review_lifecycle_command,
    register_benchmark_review_lifecycle_commands,
)
from .benchmark_run_ledger import (
    handle_benchmark_run_ledger_command,
    register_benchmark_run_ledger_commands,
)
from .benchmark_run_ledger_case_analysis import (
    handle_benchmark_run_ledger_case_analysis_command,
    register_benchmark_run_ledger_case_analysis_commands,
)
from .benchmark_run_ledger_maintenance import (
    handle_benchmark_run_ledger_maintenance_command,
)
from .benchmark_run_ledger_maintenance_registration import (
    register_benchmark_run_ledger_maintenance_commands,
)
from .benchmark_run_ledger_parity import (
    handle_benchmark_run_ledger_parity_command,
    register_benchmark_run_ledger_parity_commands,
)
from .bootstrap_connect import (
    handle_bootstrap_connect_command,
    register_bootstrap_connect_command,
)
from .canary import handle_canary_command, register_canary_commands
from .capability import handle_capability_command, register_capability_commands
from .extension import handle_extension_command, register_extension_commands
from .doctor import handle_doctor_command, register_doctor_command
from .dreaming import handle_dreaming_command, register_dreaming_commands
from .evidence_log import handle_evidence_log_command, register_evidence_log_command
from .explore import handle_explore_command, register_explore_commands
from .history import handle_history_command, register_history_command
from .lark_inbox import handle_lark_inbox_command, register_lark_inbox_commands
from .lark_kanban import handle_lark_kanban_command, register_lark_kanban_commands
from .ml_experiment import handle_ml_experiment_command, register_ml_experiment_commands
from .multi_agent import handle_multi_agent_command, register_multi_agent_commands
from .project_lifecycle import (
    handle_project_lifecycle_command,
    register_project_lifecycle_commands,
)
from .preset import handle_preset_command, register_preset_commands
from .presentation import handle_presentation_command, register_presentation_commands
from .pr_review import handle_pr_review_command, register_pr_review_command
from .quota import handle_quota_command, register_quota_command
from .ready_score import handle_ready_score_command, register_ready_score_command
from .registry_admin import (
    handle_registry_admin_command,
    register_registry_admin_commands,
)
from .slash_commands import handle_slash_commands_command, register_slash_commands_command
from .starter import (
    handle_demo_command,
    handle_starter_command,
    register_starter_commands,
)
from .starter_bootstrap import (
    handle_codex_cli_bootstrap_message_command,
    handle_codex_cli_exec_handoff_command,
    handle_codex_cli_tui_bootstrap_smoke_bundle_command,
    handle_loopx_bootstrap_command_pack_command,
    handle_new_project_prompt_command,
    handle_starter_bootstrap_command,
)
from .starter_bootstrap_registration import register_starter_bootstrap_commands
from .starter_scheduler import (
    handle_codex_cli_local_scheduler_exec_command,
    handle_codex_cli_local_scheduler_tick_command,
    handle_starter_scheduler_command,
    register_starter_scheduler_commands,
)
from .starter_session_runtime import (
    handle_codex_cli_runtime_idle_detector_command,
    handle_codex_cli_session_probe_command,
    handle_codex_cli_visible_session_proof_command,
    handle_starter_session_runtime_command,
    register_starter_session_runtime_commands,
)
from .starter_visible_driver import (
    handle_codex_cli_local_driver_plan_command,
    handle_codex_cli_visible_driver_plan_command,
    handle_codex_cli_visible_driver_run_command,
    handle_starter_visible_driver_command,
    register_starter_visible_driver_commands,
)
from .starter_visible_pilot import (
    handle_codex_cli_bounded_visible_pilot_adapter_command,
    handle_codex_cli_one_message_loop_pilot_command,
    handle_codex_cli_visible_attach_acceptance_command,
    handle_codex_cli_visible_first_response_capture_plan_command,
    handle_codex_cli_visible_local_driver_pilot_command,
    handle_starter_visible_pilot_command,
    register_starter_visible_pilot_commands,
)
from .summary_all import handle_summary_all_command, register_summary_all_command
from .status import (
    handle_check_command,
    handle_diagnose_command,
    handle_review_packet_command,
    handle_status_command,
    register_status_commands,
)
from .support_control import (
    handle_support_control_command,
    register_support_control_commands,
)
from .task_lease import handle_task_lease_command, register_task_lease_command
from .terminal_bench_adapter import (
    handle_terminal_bench_adapter_command,
    register_terminal_bench_adapter_commands,
)
from .terminal_bench_environment_result import (
    handle_terminal_bench_environment_result_command,
    register_terminal_bench_environment_result_commands,
)
from .todo import handle_todo_command, register_todo_command
from .version import handle_version_command, register_version_command
from .worker_bridge import handle_worker_bridge_command, register_worker_bridge_commands

__all__ = [
    "handle_agents_last_exam_command",
    "handle_agents_last_exam_baked_input_command",
    "handle_agents_last_exam_host_codex_command",
    "handle_agents_last_exam_launch_dry_run_command",
    "handle_agents_last_exam_local_plan_command",
    "handle_agents_last_exam_runner_source_command",
    "handle_agents_last_exam_task_material_command",
    "handle_agents_last_exam_validation_gate_command",
    "handle_agentissue_runner_flow_command",
    "handle_turn_command",
    "handle_benchmark_boundary_command",
    "handle_benchmark_command",
    "handle_benchmark_review_lifecycle_command",
    "handle_benchmark_run_ledger_command",
    "handle_benchmark_run_ledger_case_analysis_command",
    "handle_benchmark_run_ledger_maintenance_command",
    "handle_benchmark_run_ledger_parity_command",
    "handle_bootstrap_connect_command",
    "handle_canary_command",
    "handle_capability_command",
    "handle_extension_command",
    "handle_check_command",
    "handle_codex_cli_bounded_visible_pilot_adapter_command",
    "handle_codex_cli_bootstrap_message_command",
    "handle_codex_cli_exec_handoff_command",
    "handle_loopx_bootstrap_command_pack_command",
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
    "handle_evidence_log_command",
    "handle_explore_command",
    "handle_history_command",
    "handle_lark_inbox_command",
    "handle_lark_kanban_command",
    "handle_ml_experiment_command",
    "handle_multi_agent_command",
    "handle_new_project_prompt_command",
    "handle_preset_command",
    "handle_presentation_command",
    "handle_project_lifecycle_command",
    "handle_pr_review_command",
    "handle_quota_command",
    "handle_ready_score_command",
    "handle_registry_admin_command",
    "handle_review_packet_command",
    "handle_slash_commands_command",
    "handle_status_command",
    "handle_starter_command",
    "handle_starter_bootstrap_command",
    "handle_starter_scheduler_command",
    "handle_starter_session_runtime_command",
    "handle_starter_visible_driver_command",
    "handle_starter_visible_pilot_command",
    "handle_summary_all_command",
    "handle_support_control_command",
    "handle_task_lease_command",
    "handle_terminal_bench_adapter_command",
    "handle_terminal_bench_environment_result_command",
    "handle_todo_command",
    "handle_version_command",
    "handle_worker_bridge_command",
    "register_agents_last_exam_commands",
    "register_agents_last_exam_baked_input_commands",
    "register_agents_last_exam_host_codex_commands",
    "register_agents_last_exam_launch_dry_run_commands",
    "register_agents_last_exam_local_plan_commands",
    "register_agents_last_exam_runner_source_commands",
    "register_agents_last_exam_task_material_commands",
    "register_agents_last_exam_validation_gate_commands",
    "register_agentissue_runner_flow_commands",
    "register_turn_commands",
    "register_benchmark_boundary_commands",
    "register_benchmark_command_group",
    "register_benchmark_review_lifecycle_commands",
    "register_benchmark_run_ledger_commands",
    "register_benchmark_run_ledger_case_analysis_commands",
    "register_benchmark_run_ledger_maintenance_commands",
    "register_benchmark_run_ledger_parity_commands",
    "register_bootstrap_connect_command",
    "register_canary_commands",
    "register_capability_commands",
    "register_extension_commands",
    "register_doctor_command",
    "register_dreaming_commands",
    "register_evidence_log_command",
    "register_explore_commands",
    "register_history_command",
    "register_lark_inbox_commands",
    "register_lark_kanban_commands",
    "register_ml_experiment_commands",
    "register_multi_agent_commands",
    "register_project_lifecycle_commands",
    "register_pr_review_command",
    "register_preset_commands",
    "register_presentation_commands",
    "register_quota_command",
    "register_ready_score_command",
    "register_registry_admin_commands",
    "register_slash_commands_command",
    "register_starter_commands",
    "register_starter_bootstrap_commands",
    "register_starter_scheduler_commands",
    "register_starter_session_runtime_commands",
    "register_starter_visible_driver_commands",
    "register_starter_visible_pilot_commands",
    "register_summary_all_command",
    "register_status_commands",
    "register_support_control_commands",
    "register_task_lease_command",
    "register_terminal_bench_adapter_commands",
    "register_terminal_bench_environment_result_commands",
    "register_todo_command",
    "register_version_command",
    "register_worker_bridge_commands",
]
