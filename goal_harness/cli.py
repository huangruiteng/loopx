from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .authority import (
    AUTHORITY_SOURCE_BOUNDARIES,
    import_doc_registry_authority,
    register_authority_source,
    render_doc_registry_authority_import_markdown,
    render_authority_source_markdown,
)
from .agent_registry import (
    agent_profile_from_registry,
    primary_agent_id_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from .bootstrap import (
    DEFAULT_DOMAIN,
    DEFAULT_OBJECTIVE,
    bootstrap_project,
    render_bootstrap_markdown,
)
from .benchmark import (
    benchmark_result_from_benchmark_run_for_baseline_gate,
    build_benchmark_adapter_kwarg_absorption_review,
    build_benchmark_attempt_learning_gate,
    build_benchmark_baseline_failure_gate_comparison,
    build_benchmark_claim_review,
    build_benchmark_learning_ledger,
    build_benchmark_lifecycle_state,
    build_benchmark_runner_invariant_review,
    build_benchmark_verifier_attribution_review,
)
from .benchmark_adapters.agentissue import (
    AGENTISSUE_BENCHMARK_ID,
    AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION,
    AGENTISSUE_DEFAULT_TAG,
    build_agentissue_codex_cli_runner_wrapper,
    materialize_agentissue_codex_cli_runner_execution_gate,
    materialize_agentissue_codex_cli_runner_first_run_handoff,
    materialize_agentissue_codex_cli_runner_private_script,
    materialize_agentissue_codex_cli_runner_real_result,
    materialize_agentissue_codex_cli_runner_run_gate,
    materialize_agentissue_codex_cli_runner_synthetic_staging,
    materialize_agentissue_codex_cli_runner_target_handoff,
    materialize_agentissue_codex_cli_runner_workflow_check,
)
from .benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    build_agents_last_exam_baked_task_input_readiness,
    build_agents_last_exam_baked_task_input_scan,
    build_agents_last_exam_candidate_task_data_scan,
    build_agents_last_exam_host_codex_cli_route,
    build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment,
    build_agents_last_exam_local_dry_run_plan,
    build_agents_last_exam_local_exact_dry_run_result,
    build_agents_last_exam_local_launch_packet,
    build_agents_last_exam_local_preflight,
    build_agents_last_exam_local_runner_readiness,
    build_agents_last_exam_local_source_readiness,
    build_agents_last_exam_result_benchmark_report,
    build_agents_last_exam_task_material_readiness,
    build_agents_last_exam_validation_run_gate,
)
from .benchmark_adapters.skillsbench import (
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_ROUTE,
    SKILLSBENCH_DEFAULT_TASK,
    SKILLSBENCH_ROUTES,
    build_skillsbench_benchmark_run,
    build_skillsbench_benchflow_result_benchmark_run,
    skillsbench_recommended_action,
)
from .benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_DEFAULT_TASK,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE,
    TERMINAL_BENCH_MANAGED_CODEX_GOAL_HARNESS_KWARGS,
    TERMINAL_BENCH_MODES,
    TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
    agent_kwargs_from_invocation,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_environment_setup_probe_gate,
    build_terminal_bench_harbor_result_benchmark_run,
    build_terminal_bench_remote_executor_command_adapter,
    build_terminal_bench_remote_executor_launch_adapter,
    build_terminal_bench_remote_executor_materializer,
    build_terminal_bench_result_finalization_gate,
    collect_terminal_bench_goal_harness_cli_bridge_trace,
    launch_terminal_bench_environment_setup_probe,
    launch_terminal_bench_case_run,
    launch_terminal_bench_worker_materialization_probe,
    poll_terminal_bench_worker_materialization_probe,
    resume_terminal_bench_materialized_job,
    summarize_terminal_bench_post_launch_materialization,
    terminal_bench_recommended_action,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
)
from .benchmark_ledger import (
    BENCHMARK_RUN_LEDGER_DEFAULT_PATH,
    check_benchmark_run_ledger_drift,
    load_benchmark_run_ledger,
    update_benchmark_run_ledger,
)
from .benchmark_case_analysis import (
    build_case_analysis_candidate_report,
    load_json as load_benchmark_case_analysis_json,
    render_case_analysis_candidate_report_markdown,
)
from .benchmark_core import (
    build_benchmark_candidate_source_boundary,
    build_codex_app_parity_posthoc_check,
    filter_public_benchmark_artifact_paths,
    build_split_control_remote_executor_execution_seam,
    build_split_control_remote_executor_launch_plan,
    build_split_control_remote_executor_readiness,
    build_split_control_remote_executor_runner_batch,
    render_codex_app_parity_posthoc_check_markdown,
)
from .configure_goal import configure_goal, render_configure_goal_markdown
from .delivery_outcome import DELIVERY_OUTCOME_CHOICES
from .cli_commands import (
    handle_check_command,
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
    handle_diagnose_command,
    handle_demo_command,
    handle_doctor_command,
    handle_dreaming_command,
    handle_new_project_prompt_command,
    handle_review_packet_command,
    handle_status_command,
    register_doctor_command,
    register_dreaming_commands,
    register_starter_commands,
    register_status_commands,
)
from .execution_profile import DEFAULT_EXECUTION_PROFILE
from .feedback import append_human_reward, compact_reward, render_reward_markdown
from .global_registry import render_global_sync_markdown, sync_project_registry_to_global
from .heartbeat_prompt import build_heartbeat_prompt, render_heartbeat_prompt_markdown
from .history import (
    append_active_user_assisted_pilot,
    append_benchmark_comparison,
    append_benchmark_experiment_report,
    append_benchmark_learning_ledger,
    append_benchmark_result,
    append_benchmark_run,
    collect_history,
    inspect_index_duplicates,
    load_registry,
    repair_index_duplicates,
    render_active_user_assisted_pilot_append_markdown,
    render_benchmark_comparison_append_markdown,
    render_benchmark_experiment_report_append_markdown,
    render_benchmark_learning_ledger_append_markdown,
    render_benchmark_result_append_markdown,
    render_benchmark_run_append_markdown,
    render_history_markdown,
    render_index_duplicate_inspection_markdown,
    render_index_duplicate_repair_markdown,
)
from .operator_gate import (
    DEFAULT_OPERATOR_GATE,
    OPERATOR_GATE_DECISIONS,
    record_operator_gate,
    render_operator_gate_markdown,
)
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path, resolve_runtime_root
from .project_map import (
    DEFAULT_PROJECT_MAP_CLASSIFICATION,
    read_only_project_map_run,
    render_read_only_project_map_markdown,
)
from .promotion_gate import build_promotion_gate, render_promotion_gate_markdown
from .quota import (
    build_quota_plan,
    build_quota_should_run,
    record_quota_monitor_poll,
    render_quota_markdown,
    render_quota_monitor_poll_markdown,
    render_quota_should_run_markdown,
    render_quota_slot_preview_markdown,
    spend_quota_slot,
    void_quota_slot,
)
from .registry import (
    inspect_registry,
    inspect_registry_boundary,
    registry_goals,
    render_registry_boundary_markdown,
    render_registry_markdown,
    resolve_state_file,
)
from .rollout_event_log import (
    append_rollout_event,
    build_rollout_event,
    rollout_event_log_path,
)
from .runtime import archive_runtime_goal, render_archive_runtime_markdown
from .state_refresh import (
    DEFAULT_REFRESH_ACTION,
    DEFAULT_REFRESH_CLASSIFICATION,
    DELIVERY_BATCH_SCALE_CHOICES,
    refresh_state_run,
    render_state_refresh_markdown,
)
from .status import (
    AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK,
    collect_status,
    compact_active_user_assisted_pilot,
    compact_benchmark_comparison,
    compact_benchmark_experiment_report,
    compact_benchmark_learning_ledger,
    compact_benchmark_post_launch_materialization,
    compact_benchmark_result,
    compact_benchmark_run,
    render_status_markdown,
)
from .status_server import (
    DEFAULT_STATUS_HOST,
    DEFAULT_STATUS_PATH,
    DEFAULT_STATUS_PORT,
    serve_status,
)
from .todos import (
    archive_completed_todos,
    add_goal_todo,
    complete_goal_todo,
    render_todo_markdown,
    supersede_goal_todo,
    update_goal_todo,
)
from .upgrade import build_upgrade_plan, render_upgrade_plan_markdown
from .worker_bridge import (
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    DEFAULT_WORKER_BRIDGE_MODULE,
    DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
    DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
    DEFAULT_ACTIVE_USER_CODEX_BIN,
    DEFAULT_ACTIVE_USER_SIMULATOR_CONTEXT_DIR,
    DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_JSON,
    DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_SCHEMA_JSON,
    DEFAULT_ACTIVE_USER_SIMULATOR_PROMPT_JSON,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
    append_worker_bridge_counter_trace_row,
    build_active_user_codex_simulator_contract,
    build_active_user_intervention,
    build_active_user_intervention_channel_contract,
    build_active_user_intervention_from_simulator_output,
    build_worker_bridge_benchmark_run,
    build_worker_bridge_benchmark_run_from_counters,
    build_worker_bridge_install_contract,
    build_worker_bridge_interaction_counters_from_trace,
    build_worker_bridge_outcome,
    load_worker_bridge_counter_trace_file,
    observe_active_user_intervention_feed,
    render_worker_bridge_install_contract_markdown,
    write_active_user_observation_file,
    write_worker_bridge_benchmark_run_file,
)


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def render_benchmark_artifact_path_filter_markdown(payload: dict[str, object]) -> str:
    artifact_policy = (
        payload.get("artifact_policy")
        if isinstance(payload.get("artifact_policy"), dict)
        else {}
    )
    lines = [
        "# Benchmark Artifact Path Filter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Adapter policy: `{artifact_policy.get('adapter_kind')}`",
        f"- Allowed to read: `{payload.get('allowed_to_read_count')}`",
        f"- Blocked: `{payload.get('blocked_count')}`",
        f"- Full paths recorded: `{payload.get('path_recorded')}`",
    ]
    allowed = payload.get("allowed_artifact_basenames")
    if isinstance(allowed, list) and allowed:
        lines.append("- Allowed basenames: " + ", ".join(f"`{item}`" for item in allowed))
    blocked = payload.get("blocked_reasons")
    if isinstance(blocked, dict) and blocked:
        reasons = ", ".join(f"`{key}`={value}" for key, value in blocked.items())
        lines.append("- Blocked reasons: " + reasons)
    return "\n".join(lines) + "\n"


def render_benchmark_candidate_source_boundary_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Benchmark Candidate Source Boundary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Clean: `{payload.get('clean')}`",
        f"- Allowed: `{payload.get('allowed_source_count')}`",
        f"- Blocked: `{payload.get('blocked_source_count')}`",
        f"- Paths recorded: `{payload.get('path_recorded')}`",
    ]
    blocked = payload.get("blocked_reasons")
    if isinstance(blocked, dict) and blocked:
        reasons = ", ".join(f"`{key}`={value}" for key, value in blocked.items())
        lines.append("- Blocked reasons: " + reasons)
    if payload.get("next_action"):
        lines.append(f"- Next action: {payload.get('next_action')}")
    return "\n".join(lines) + "\n"


def render_split_control_execution_seam_markdown(payload: dict[str, object]) -> str:
    cases = payload.get("execution_cases") if isinstance(payload.get("execution_cases"), list) else []
    lines = [
        "# Benchmark Split-Control Execution Seam",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready to execute: `{payload.get('ready_to_execute')}`",
        f"- Ready to spend: `{payload.get('ready_to_spend')}`",
        f"- Cases: `{len(cases)}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    missing_adapters = payload.get("missing_command_adapter_ids")
    if isinstance(missing_adapters, list) and missing_adapters:
        lines.append(
            "- Missing command adapters: "
            + ", ".join(f"`{item}`" for item in missing_adapters)
        )
    missing_reducers = payload.get("missing_result_reducer_ids")
    if isinstance(missing_reducers, list) and missing_reducers:
        lines.append(
            "- Missing result reducers: "
            + ", ".join(f"`{item}`" for item in missing_reducers)
        )
    if payload.get("next_action"):
        lines.append(f"- Next action: {payload.get('next_action')}")
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Shell commands embedded: `{boundary.get('shell_commands_embedded')}`",
            f"- argv embedded: `{boundary.get('argv_embedded')}`",
            f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
            f"- raw logs public: `{boundary.get('raw_logs_public')}`",
            f"- upload allowed: `{boundary.get('upload_allowed')}`",
            f"- submit allowed: `{boundary.get('submit_allowed')}`",
        ]
    )
    if cases:
        lines.extend(["", "## Cases", ""])
        for case in cases:
            if not isinstance(case, dict):
                continue
            materialization = (
                case.get("command_materialization")
                if isinstance(case.get("command_materialization"), dict)
                else {}
            )
            local_driver = (
                case.get("local_driver_contract")
                if isinstance(case.get("local_driver_contract"), dict)
                else {}
            )
            remote_sandbox = (
                case.get("remote_sandbox_contract")
                if isinstance(case.get("remote_sandbox_contract"), dict)
                else {}
            )
            reducer = case.get("result_reducer") if isinstance(case.get("result_reducer"), dict) else {}
            lines.append(
                "- "
                + f"`{case.get('benchmark_id')}`: command_ready="
                + f"`{materialization.get('ready')}`, reducer_ready="
                + f"`{reducer.get('ready')}`, local_driver="
                + f"`{local_driver.get('ready')}`, remote_sandbox="
                + f"`{remote_sandbox.get('ready')}`, blockers="
                + "`"
                + ",".join(str(item) for item in case.get("blockers", []))
                + "`"
            )
    return "\n".join(lines) + "\n"

def render_terminal_bench_remote_executor_command_adapter_markdown(
    payload: dict[str, object],
) -> str:
    adapter = (
        payload.get("command_adapter")
        if isinstance(payload.get("command_adapter"), dict)
        else {}
    )
    boundary = (
        adapter.get("boundary") if isinstance(adapter.get("boundary"), dict) else {}
    )
    surface_contract = (
        adapter.get("surface_contract")
        if isinstance(adapter.get("surface_contract"), dict)
        else {}
    )
    local_driver_contract = (
        adapter.get("local_driver_contract")
        if isinstance(adapter.get("local_driver_contract"), dict)
        else {}
    )
    remote_sandbox_contract = (
        adapter.get("remote_sandbox_contract")
        if isinstance(adapter.get("remote_sandbox_contract"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Command Adapter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Command adapter ready: `{adapter.get('command_adapter_ready')}`",
        f"- Result reducer ready: `{adapter.get('result_reducer_ready')}`",
        "- Remote materializer ready: "
        f"`{surface_contract.get('remote_materializer_ready')}`",
        f"- Entrypoint label: `{adapter.get('entrypoint_label')}`",
        f"- Result reducer label: `{adapter.get('result_reducer_label')}`",
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Local Driver And Remote Sandbox",
        "",
        f"- Local driver ready: `{local_driver_contract.get('ready')}`",
        f"- Local driver label: `{local_driver_contract.get('driver_label')}`",
        f"- Remote sandbox ready: `{remote_sandbox_contract.get('ready')}`",
        f"- Remote sandbox label: `{remote_sandbox_contract.get('sandbox_label')}`",
        "",
        "## Boundary",
        "",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def render_terminal_bench_remote_executor_materializer_markdown(
    payload: dict[str, object],
) -> str:
    materializer = (
        payload.get("materializer")
        if isinstance(payload.get("materializer"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Materializer",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Entrypoint label: `{materializer.get('entrypoint_label')}`",
        f"- Manifest read: `{materializer.get('handle_manifest_read')}`",
        "- Public handle values recorded: "
        f"`{materializer.get('public_handle_values_recorded')}`",
        "- Local Codex driver ready: "
        f"`{materializer.get('local_codex_driver_ready')}`",
        "- Remote agent runtime required: "
        f"`{materializer.get('remote_agent_runtime_required')}`",
        "- Remote Codex runtime required: "
        f"`{materializer.get('remote_codex_runtime_required')}`",
        "- Present handle fields: "
        + ", ".join(f"`{item}`" for item in materializer.get("present_handle_fields", [])),
        "- Missing handle fields: "
        + ", ".join(f"`{item}`" for item in materializer.get("missing_handle_fields", [])),
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Boundary",
        "",
        f"- Compact only: `{boundary.get('compact_only')}`",
        f"- Local Codex driver required: `{boundary.get('local_codex_driver_required')}`",
        f"- Remote agent runtime allowed: `{boundary.get('remote_agent_runtime_allowed')}`",
        f"- Remote Codex runtime allowed: `{boundary.get('remote_codex_runtime_allowed')}`",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- remote path embedded: `{boundary.get('remote_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        "- Codex credentials synced to remote: "
        f"`{boundary.get('codex_credentials_synced_to_remote')}`",
        "- Remote model API invocation allowed: "
        f"`{boundary.get('remote_model_api_invocation_allowed')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def render_terminal_bench_remote_executor_launch_adapter_markdown(
    payload: dict[str, object],
) -> str:
    launch_adapter = (
        payload.get("launch_adapter")
        if isinstance(payload.get("launch_adapter"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Launch Adapter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        "- Ready to request remote sandbox: "
        f"`{launch_adapter.get('ready_to_request_remote_sandbox')}`",
        "- Remote launch result read: "
        f"`{launch_adapter.get('remote_launch_result_read')}`",
        "- Local Codex driver ready: "
        f"`{launch_adapter.get('local_codex_driver_ready')}`",
        "- Remote sandbox ready: "
        f"`{launch_adapter.get('remote_sandbox_ready')}`",
        "- Missing request fields: "
        + ", ".join(
            f"`{item}`" for item in launch_adapter.get("missing_request_fields", [])
        ),
        "- Missing launch result fields: "
        + ", ".join(
            f"`{item}`"
            for item in launch_adapter.get("missing_launch_result_fields", [])
        ),
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Boundary",
        "",
        f"- Compact only: `{boundary.get('compact_only')}`",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- remote path embedded: `{boundary.get('remote_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        "- Codex credentials synced to remote: "
        f"`{boundary.get('codex_credentials_synced_to_remote')}`",
        "- Remote model API invocation allowed: "
        f"`{boundary.get('remote_model_api_invocation_allowed')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_upsert_markdown(payload: dict[str, object]) -> str:
    ledger = (
        payload.get("benchmark_run_ledger")
        if isinstance(payload.get("benchmark_run_ledger"), dict)
        else {}
    )
    entry = ledger.get("entry") if isinstance(ledger.get("entry"), dict) else {}
    decision = (
        ledger.get("case_decision")
        if isinstance(ledger.get("case_decision"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Upsert",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{ledger.get('updated')}`",
        f"- benchmark: `{entry.get('benchmark_id')}`",
        f"- case: `{entry.get('case_id')}`",
        f"- arm: `{entry.get('arm_id')}`",
        f"- score: `{entry.get('official_score')}`",
        f"- failure: `{entry.get('failure_class')}`",
        f"- decision: `{decision.get('decision')}`",
        f"- ledger: `{ledger.get('ledger_path')}`",
        f"- compact only: `{read_boundary.get('compact_only')}`",
        f"- raw logs read: `{read_boundary.get('raw_logs_read')}`",
        f"- task text read: `{read_boundary.get('task_text_read')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_case_analysis_candidates_markdown(
    payload: dict[str, object],
) -> str:
    if payload.get("ok") and isinstance(payload.get("report"), dict):
        report = payload["report"]
        text = render_case_analysis_candidate_report_markdown(report)
        read_boundary = (
            payload.get("read_boundary")
            if isinstance(payload.get("read_boundary"), dict)
            else {}
        )
        return (
            text
            + "\n## Read Boundary\n\n"
            + f"- compact only: `{read_boundary.get('compact_only')}`\n"
            + f"- raw logs read: `{read_boundary.get('raw_logs_read')}`\n"
            + f"- task text read: `{read_boundary.get('task_text_read')}`\n"
            + f"- trajectory read: `{read_boundary.get('trajectory_read')}`\n"
        )
    lines = [
        "# Benchmark Case-Analysis Candidates",
        "",
        f"- ok: `{payload.get('ok')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_check_markdown(payload: dict[str, object]) -> str:
    drift = (
        payload.get("benchmark_run_ledger_drift")
        if isinstance(payload.get("benchmark_run_ledger_drift"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Drift Check",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- drift_detected: `{drift.get('drift_detected')}`",
        f"- checked_history_run_count: `{drift.get('checked_history_run_count')}`",
        f"- terminal_history_run_count: `{drift.get('terminal_history_run_count')}`",
        f"- matched_history_run_count: `{drift.get('matched_history_run_count')}`",
        f"- missing_ledger_run_count: `{drift.get('missing_ledger_run_count')}`",
        f"- non_terminal_skipped_count: `{drift.get('non_terminal_skipped_count')}`",
        f"- ledger_run_count: `{drift.get('ledger_run_count')}`",
    ]
    missing_runs = drift.get("missing_runs") if isinstance(drift.get("missing_runs"), list) else []
    if missing_runs:
        lines.extend(
            [
                "",
                "## Missing Compact Runs",
                "",
                "| Benchmark | Case | Arm | Score | Failure | Catch-up |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for run in missing_runs:
            if not isinstance(run, dict):
                continue
            lines.append(
                "| "
                f"`{run.get('benchmark_id')}` | "
                f"`{run.get('case_id')}` | "
                f"`{run.get('arm_id')}` | "
                f"`{run.get('official_score')}` | "
                f"`{run.get('failure_class')}` | "
                f"`{run.get('catch_up_command_template')}` |"
            )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_baseline_failure_gate_markdown(payload: dict[str, object]) -> str:
    comparison = (
        payload.get("benchmark_comparison")
        if isinstance(payload.get("benchmark_comparison"), dict)
        else {}
    )
    gate = (
        comparison.get("baseline_failure_gate")
        if isinstance(comparison.get("baseline_failure_gate"), dict)
        else {}
    )
    lines = [
        "# Benchmark Baseline Failure Gate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- benchmark_id: `{comparison.get('benchmark_id')}`",
        f"- task_id: `{comparison.get('task_id')}`",
        f"- baseline_failed: `{gate.get('baseline_failed')}`",
        f"- control_plane_addressable: `{gate.get('control_plane_addressable')}`",
        f"- treatment_eligible: `{gate.get('treatment_eligible')}`",
        f"- failure_class: `{gate.get('failure_class')}`",
    ]
    if gate.get("minimum_next_evidence"):
        lines.append(f"- minimum_next_evidence: {gate.get('minimum_next_evidence')}")
    if gate.get("negative_selection_reason"):
        lines.append(f"- negative_selection_reason: {gate.get('negative_selection_reason')}")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_preflight_markdown(payload: dict[str, object]) -> str:
    provider = (
        payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    )
    required_image = (
        provider.get("required_image")
        if isinstance(provider.get("required_image"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Preflight",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Provider: `{provider.get('kind')}`",
        f"- No cloud: `{provider.get('no_cloud')}`",
        f"- Required image present: `{required_image.get('present')}`",
        f"- Required image arch/os: `{required_image.get('architecture')}`/`{required_image.get('os')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_dry_run_plan_markdown(payload: dict[str, object]) -> str:
    adapter_plan = (
        payload.get("adapter_plan")
        if isinstance(payload.get("adapter_plan"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Dry-Run Plan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Mode: `{adapter_plan.get('mode')}`",
        f"- Provider: `{adapter_plan.get('provider')}`",
        f"- Will start container: `{adapter_plan.get('will_start_container')}`",
        f"- Will read task body: `{adapter_plan.get('will_read_task_body')}`",
        f"- Will upload/submit: `{adapter_plan.get('will_upload')}`/`{adapter_plan.get('will_submit')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_runner_readiness_markdown(
    payload: dict[str, object],
) -> str:
    runner_probe = (
        payload.get("runner_probe")
        if isinstance(payload.get("runner_probe"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Runner Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Preflight ready: `{payload.get('preflight_ready')}`",
        f"- Dry-run plan ready: `{payload.get('dry_run_plan_ready')}`",
        f"- Runner binary: `{runner_probe.get('binary')}`",
        f"- Runner binary available: `{runner_probe.get('binary_available')}`",
        f"- Runner Python module: `{runner_probe.get('python_module')}`",
        f"- Runner Python module available: `{runner_probe.get('python_module_available')}`",
        f"- Runner source root declared/available: `{runner_probe.get('source_root_declared')}`/`{runner_probe.get('source_root_available')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Public task material authorized: `{boundary.get('operator_authorized_public_task_material')}`",
        f"- Upload/submit allowed: `{boundary.get('upload_allowed')}`/`{boundary.get('submit_allowed')}`",
        f"- Model API allowed/invoked: `{boundary.get('model_api_allowed')}`/`{boundary.get('model_api_invoked')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_source_readiness_markdown(
    payload: dict[str, object],
) -> str:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    runner_probe = (
        payload.get("runner_probe")
        if isinstance(payload.get("runner_probe"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Source Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Expected repo: `{source.get('expected_repo')}`",
        f"- Remote matches expected: `{source.get('remote_matches_expected')}`",
        f"- Source head: `{source.get('head')}`",
        f"- Upstream current: `{source.get('head_matches_upstream')}`",
        f"- Upstream ahead/behind: `{source.get('upstream_ahead_count')}`/`{source.get('upstream_behind_count')}`",
        f"- Fetch origin attempted/ok: `{source.get('fetch_origin_attempted')}`/`{source.get('fetch_origin_ok')}`",
        f"- Source root path recorded: `{source.get('source_root_path_recorded')}`",
        f"- Runner Python module: `{runner_probe.get('python_module')}`",
        f"- Runner Python module available: `{runner_probe.get('python_module_available')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_task_material_readiness_markdown(
    payload: dict[str, object],
) -> str:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    public_lists = (
        payload.get("public_task_lists")
        if isinstance(payload.get("public_task_lists"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    task_data = payload.get("task_data") if isinstance(payload.get("task_data"), dict) else {}
    local_staging = (
        task_data.get("local_task_data_staging")
        if isinstance(task_data.get("local_task_data_staging"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Task Material Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Task: `{task.get('task_id')}`",
        f"- Task dir/card/scripts: `{task.get('task_dir_available')}`/`{task.get('task_card_json_present')}`/`{task.get('scripts_dir_present')}`",
        f"- Scorer script count: `{task.get('scorer_script_count')}`",
        f"- Task data checked/ready/source: `{task_data.get('checked')}`/`{task_data.get('ready')}`/`{task_data.get('task_data_source')}`",
        f"- Local task-data staging route/tool/auth checked: `{local_staging.get('route')}`/`{local_staging.get('fetch_tool_present')}`/`{local_staging.get('auth_status_checked')}`",
        f"- Public list membership checked/present: `{public_lists.get('checked')}`/`{public_lists.get('present_count')}`",
        f"- Task body/card/script content read: `{boundary.get('task_body_read')}`/`{boundary.get('task_card_content_read')}`/`{boundary.get('script_content_read')}`",
        f"- Local paths/raw output recorded: `{boundary.get('local_paths_recorded')}`/`{boundary.get('raw_output_recorded')}`",
        f"- Container/model/upload/submit: `{boundary.get('container_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_baked_task_input_readiness_markdown(
    payload: dict[str, object],
) -> str:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    image = payload.get("image") if isinstance(payload.get("image"), dict) else {}
    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Baked Task Input Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected task: `{task.get('task_id')}`",
        f"- Image present: `{image.get('present')}`",
        f"- Probe attempted/container started: `{probe.get('attempted')}`/`{probe.get('container_started')}`",
        f"- Baked input present/readable: `{probe.get('baked_input_present')}`/`{probe.get('baked_input_readable')}`",
        f"- Expected path recorded: `{probe.get('expected_path_recorded')}`",
        f"- Task run/model/upload/submit: `{boundary.get('task_run_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Task data content read: `{boundary.get('task_data_content_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_baked_task_input_scan_markdown(
    payload: dict[str, object],
) -> str:
    selected = (
        payload.get("selected_tasks")
        if isinstance(payload.get("selected_tasks"), dict)
        else {}
    )
    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    candidates = (
        payload.get("candidates")
        if isinstance(payload.get("candidates"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Baked Task Input Scan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected/probed tasks: `{selected.get('selected_task_count')}`/`{selected.get('probed_task_count')}`",
        f"- Probe attempted/container started: `{probe.get('attempted')}`/`{probe.get('container_started')}`",
        f"- Baked input candidate count: `{probe.get('baked_input_candidate_count')}`",
        f"- Candidate ids: `{candidates.get('eligible_baked_input_candidates')}`",
        f"- Expected paths/argv/stdout recorded: `{probe.get('expected_path_recorded')}`/`{probe.get('command_argv_recorded')}`/`{probe.get('stdout_recorded')}`",
        f"- Task run/model/upload/submit: `{boundary.get('task_run_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Task data content read/listed: `{boundary.get('task_data_content_read')}`/`{boundary.get('directory_listed')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_candidate_task_data_scan_markdown(
    payload: dict[str, object],
) -> str:
    selected = (
        payload.get("selected_task_lists")
        if isinstance(payload.get("selected_task_lists"), dict)
        else {}
    )
    summary = (
        payload.get("scan_summary")
        if isinstance(payload.get("scan_summary"), dict)
        else {}
    )
    candidates = (
        payload.get("candidate_tasks")
        if isinstance(payload.get("candidate_tasks"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Candidate Task-Data Scan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected tasks/lists: `{selected.get('selected_task_count')}`/`{selected.get('checked_list_count')}`",
        f"- Configs checked/missing: `{summary.get('task_config_checked_count')}`/`{summary.get('task_config_missing_or_unreadable_count')}`",
        f"- No-task-data formal/demo candidates: `{summary.get('formal_no_task_data_candidate_count')}`/`{summary.get('demo_no_task_data_candidate_count')}`",
        f"- Eligible candidates: `{candidates.get('eligible_no_task_data_candidates')}`",
        f"- Config line scan/source recorded: `{boundary.get('task_config_line_scan')}`/`{boundary.get('task_config_source_content_recorded')}`",
        f"- Task card/script/instruction read: `{boundary.get('task_card_content_read')}`/`{boundary.get('script_content_read')}`/`{boundary.get('task_instruction_file_read')}`",
        f"- Local paths/raw output recorded: `{boundary.get('local_paths_recorded')}`/`{boundary.get('raw_output_recorded')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_launch_packet_markdown(
    payload: dict[str, object],
) -> str:
    source_lock = (
        payload.get("source_lock")
        if isinstance(payload.get("source_lock"), dict)
        else {}
    )
    runner = payload.get("runner") if isinstance(payload.get("runner"), dict) else {}
    experiment_spec = (
        payload.get("experiment_spec")
        if isinstance(payload.get("experiment_spec"), dict)
        else {}
    )
    launch_packet = (
        payload.get("launch_packet")
        if isinstance(payload.get("launch_packet"), dict)
        else {}
    )
    case_state = (
        payload.get("case_state_init_contract")
        if isinstance(payload.get("case_state_init_contract"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Launch Packet",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Source head: `{source_lock.get('head')}`",
        f"- Upstream current: `{source_lock.get('head_matches_upstream')}`",
        f"- Fetch origin attempted/ok: `{source_lock.get('fetch_origin_attempted')}`/`{source_lock.get('fetch_origin_ok')}`",
        f"- Source root path recorded: `{source_lock.get('source_root_path_recorded')}`",
        f"- Runner command label: `{runner.get('command_label')}`",
        f"- Runner module available: `{runner.get('python_module_available')}`",
        f"- Experiment spec: `{experiment_spec.get('relative_path')}`",
        f"- Experiment spec exists/content read: `{experiment_spec.get('exists')}`/`{experiment_spec.get('content_read')}`",
        f"- Mode: `{launch_packet.get('mode')}`",
        f"- Will execute/start container: `{launch_packet.get('will_execute')}`/`{launch_packet.get('will_start_container')}`",
        f"- Will upload/submit: `{launch_packet.get('will_upload')}`/`{launch_packet.get('will_submit')}`",
        f"- Case state init required/path: `{case_state.get('init_required_before_worker')}`/`{case_state.get('case_state_path')}`",
        f"- Case state schema: `{case_state.get('schema_version')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_exact_dry_run_result_markdown(
    payload: dict[str, object],
) -> str:
    environment = (
        payload.get("environment")
        if isinstance(payload.get("environment"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Exact Dry-Run Result",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Exit code: `{payload.get('exit_code')}`",
        f"- Experiment: `{payload.get('experiment')}`",
        f"- Environment: `{environment.get('kind')}` / `{environment.get('route')}`",
        f"- Concurrency: `{payload.get('concurrency')}`",
        f"- Unit count declared/parsed: `{payload.get('unit_count_declared')}`/`{payload.get('unit_count_parsed')}`",
        f"- Raw stdout recorded: `{boundary.get('raw_stdout_recorded')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_host_codex_cli_route_markdown(
    payload: dict[str, object],
) -> str:
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    codex_cli = (
        payload.get("host_codex_cli")
        if isinstance(payload.get("host_codex_cli"), dict)
        else {}
    )
    host_auth = (
        payload.get("host_auth") if isinstance(payload.get("host_auth"), dict) else {}
    )
    cua_assets = (
        payload.get("cua_mcp_assets")
        if isinstance(payload.get("cua_mcp_assets"), dict)
        else {}
    )
    ale_sandbox = (
        payload.get("ale_sandbox")
        if isinstance(payload.get("ale_sandbox"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CLI Route",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route mode: `{route.get('mode')}`",
        f"- Host Codex binary/version: `{codex_cli.get('binary')}` / `{codex_cli.get('version')}`",
        f"- Host Codex available: `{codex_cli.get('binary_available')}`",
        f"- Host auth/config present: `{host_auth.get('auth_cache_present')}`/`{host_auth.get('config_present')}`",
        f"- Credential values recorded: `{host_auth.get('credential_values_recorded')}`",
        f"- Auth copied to sandbox: `{host_auth.get('auth_material_copied_to_sandbox')}`",
        f"- CUA MCP assets ready: `{cua_assets.get('available')}`",
        f"- ALE CUA smoke ready: `{ale_sandbox.get('cua_smoke_ready')}`",
        f"- Runs Codex in sandbox: `{route.get('runs_codex_inside_ale_sandbox')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_host_codex_cua_no_task_smoke_markdown(
    payload: dict[str, object],
) -> str:
    codex_exec = (
        payload.get("codex_exec_surface")
        if isinstance(payload.get("codex_exec_surface"), dict)
        else {}
    )
    mcp_config = (
        payload.get("codex_mcp_config")
        if isinstance(payload.get("codex_mcp_config"), dict)
        else {}
    )
    cua_bridge = (
        payload.get("cua_mcp_bridge")
        if isinstance(payload.get("cua_mcp_bridge"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CUA No-Task E2E",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route gate ready: `{payload.get('route_gate_ready')}`",
        f"- Codex exec surface ready: `{codex_exec.get('available')}`",
        f"- Codex MCP config ready: `{mcp_config.get('available')}`",
        f"- CUA MCP bridge ready: `{cua_bridge.get('available')}`",
        f"- Codex prompt sent: `{boundary.get('codex_prompt_sent')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Raw output recorded: `{boundary.get('raw_output_recorded')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_validation_run_gate_markdown(
    payload: dict[str, object],
) -> str:
    selected_task = (
        payload.get("selected_task")
        if isinstance(payload.get("selected_task"), dict)
        else {}
    )
    readiness = (
        payload.get("readiness_inputs")
        if isinstance(payload.get("readiness_inputs"), dict)
        else {}
    )
    model_policy = (
        payload.get("model_policy")
        if isinstance(payload.get("model_policy"), dict)
        else {}
    )
    run_boundary = (
        payload.get("run_boundary")
        if isinstance(payload.get("run_boundary"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Validation Run Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected task: `{selected_task.get('task_id')}`",
        f"- Task material ready: `{readiness.get('task_material_ready')}`",
        f"- Host Codex no-task E2E ready: `{readiness.get('host_codex_no_task_e2e_ready')}`",
        f"- Exact dry-run ready: `{readiness.get('exact_dry_run_ready')}`",
        f"- Launch packet ready: `{readiness.get('launch_packet_ready')}`",
        f"- Fresh source required/ready: `{readiness.get('fresh_source_required')}`/`{readiness.get('fresh_source_ready')}`",
        f"- Compact reducer ready: `{readiness.get('compact_result_reducer_ready')}`",
        f"- Connectivity model: `{model_policy.get('connectivity_e2e_model')}`",
        f"- Formal score agent/candidate: `{model_policy.get('formal_score_agent')}`/`{model_policy.get('formal_score_candidate')}`",
        f"- Task run started by gate: `{run_boundary.get('task_run_started_by_this_gate')}`",
        f"- Upload/submit eligible: `{run_boundary.get('no_upload')}`/`{run_boundary.get('submit_eligible')}`",
        f"- Raw trajectory/task body read: `{run_boundary.get('raw_trajectory_read')}`/`{run_boundary.get('task_body_read_by_goal_harness')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_claim_review_markdown(payload: dict[str, object]) -> str:
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    treatment = (
        payload.get("treatment_worker_evidence")
        if isinstance(payload.get("treatment_worker_evidence"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Claim Review",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Comparison: `{payload.get('comparison_id')}`",
        f"- Official delta: `{payload.get('official_task_score_delta')}`",
        f"- Claim strength: `{decision.get('claim_strength')}`",
        f"- Validation candidate: `{decision.get('validation_enhancement_candidate')}`",
        f"- Clean validation: `{decision.get('clean_validation_enhancement')}`",
        f"- Blockers: `{decision.get('blockers')}`",
        f"- Next action: {decision.get('next_action')}",
        f"- Treatment worker GH calls: `{treatment.get('worker_goal_harness_cli_call_total')}`",
        f"- Baseline attribution: `{payload.get('baseline_score_failure_attribution')}`",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_learning_ledger_markdown(payload: dict[str, object]) -> str:
    lifecycle_gate = (
        payload.get("lifecycle_gate")
        if isinstance(payload.get("lifecycle_gate"), dict)
        else {}
    )
    learning_quota_gate = (
        payload.get("learning_quota_gate")
        if isinstance(payload.get("learning_quota_gate"), dict)
        else {}
    )
    routing = (
        payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
    )
    overhead = (
        payload.get("overhead") if isinstance(payload.get("overhead"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Learning Ledger",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Comparison: `{payload.get('comparison_id')}`",
        f"- Official delta: `{payload.get('official_task_score_delta')}`",
        f"- Learning status: `{payload.get('learning_status')}`",
        f"- Claim strength: `{payload.get('claim_strength')}`",
        f"- Repair candidates: `{payload.get('repair_candidates')}`",
        f"- Claim blockers: `{payload.get('claim_blockers')}`",
        f"- Budget count allowed: `{lifecycle_gate.get('budget_count_allowed')}`",
        f"- Learning spend allowed: `{learning_quota_gate.get('spend_allowed')}`",
        f"- Actionable reasons: `{learning_quota_gate.get('actionable_reasons')}`",
        f"- Overhead label: `{overhead.get('label')}`",
        f"- Repeat allowed: `{routing.get('repeat_allowed')}`",
        f"- New candidate allowed: `{routing.get('new_candidate_allowed')}`",
        f"- Next action: {routing.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_attempt_learning_gate_markdown(
    payload: dict[str, object],
) -> str:
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Attempt Learning Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Mode: `{payload.get('mode')}`",
        f"- Classification: `{payload.get('classification')}`",
        f"- Countable attempt: `{payload.get('countable_attempt')}`",
        f"- Learning row present: `{payload.get('learning_row_present')}`",
        f"- Learning row actionable: `{payload.get('learning_row_actionable')}`",
        f"- Budget count allowed: `{payload.get('budget_count_allowed')}`",
        f"- Repair candidates: `{payload.get('repair_candidates')}`",
        f"- Next action: {payload.get('next_required_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_adapter_kwarg_absorption_review_markdown(
    payload: dict[str, object],
) -> str:
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Adapter Kwarg Absorption Review",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Adapter: `{payload.get('adapter_label')}`",
        f"- Classification: `{payload.get('classification')}`",
        f"- Clean: `{payload.get('clean')}`",
        f"- Generated GH kwargs: `{payload.get('generated_goal_harness_kwarg_count')}`",
        f"- Absorbed GH kwargs: `{payload.get('absorbed_goal_harness_kwarg_count')}`",
        f"- Leaked GH kwargs: `{payload.get('leaked_goal_harness_kwarg_count')}`",
        f"- Leaked keys: `{payload.get('leaked_goal_harness_kwarg_keys')}`",
        f"- Next action: {payload.get('next_required_action')}",
        f"- Kwarg values recorded: `{(payload.get('claim_boundary') or {}).get('kwarg_values_recorded') if isinstance(payload.get('claim_boundary'), dict) else None}`",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_lifecycle_state_markdown(payload: dict[str, object]) -> str:
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    setup = (
        payload.get("environment_setup_readiness_preflight")
        if isinstance(payload.get("environment_setup_readiness_preflight"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    return "\n".join(
        [
            "# Benchmark Lifecycle State",
            "",
            f"- Schema: `{payload.get('schema_version')}`",
            f"- Current phase: `{payload.get('current_phase')}`",
            f"- First blocker: `{payload.get('first_blocker')}`",
            f"- Next transition: `{payload.get('next_required_transition')}`",
            f"- Launch state countable: `{gates.get('launch_state_countable')}`",
            f"- Compact ingest allowed: `{gates.get('compact_result_ingest_allowed')}`",
            f"- Budget count allowed: `{gates.get('budget_count_allowed')}`",
            f"- New candidate allowed: `{gates.get('new_candidate_allowed')}`",
            f"- Repeat allowed: `{gates.get('repeat_allowed')}`",
            "- Environment setup repeat allowed: "
            f"`{gates.get('environment_setup_repeat_allowed')}`",
            "- Environment setup next action: "
            f"{setup.get('next_allowed_action') or ''}",
            f"- Compact only: `{read_boundary.get('compact_only')}`",
            f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
        ]
    ) + "\n"


def render_terminal_bench_environment_setup_gate_markdown(
    payload: dict[str, object],
) -> str:
    capability = (
        payload.get("harbor_run_help_capability")
        if isinstance(payload.get("harbor_run_help_capability"), dict)
        else {}
    )
    contract = (
        payload.get("probe_contract")
        if isinstance(payload.get("probe_contract"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Environment Setup Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Preflight ready: `{payload.get('preflight_ready')}`",
        "- Previous setup failure: "
        f"`{payload.get('previous_environment_setup_failure_present')}`",
        f"- Help probe ok: `{capability.get('probe_ok')}`",
        f"- Direct setup-only route: `{payload.get('direct_setup_only_route_allowed')}`",
        "- NOP disable-verification route: "
        f"`{payload.get('nop_disable_verification_probe_allowed')}`",
        "- Environment setup probe allowed: "
        f"`{payload.get('environment_setup_probe_allowed')}`",
        f"- Same-task repeat allowed: `{payload.get('same_task_repeat_allowed')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Next action: {payload.get('next_allowed_action')}",
        f"- Probe agent: `{contract.get('agent')}`",
        f"- No upload / submit eligible: `{contract.get('no_upload')}` / `{contract.get('submit_eligible')}`",
        f"- Codex invoked: `{contract.get('codex_invoked')}`",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw help recorded: `{read_boundary.get('raw_help_recorded')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_environment_setup_probe_launch_markdown(
    payload: dict[str, object],
) -> str:
    post_launch = (
        payload.get("post_launch_materialization")
        if isinstance(payload.get("post_launch_materialization"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    lines = [
        "# Terminal-Bench Environment Setup Probe Launch",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Run: `{payload.get('run_basename')}`",
        f"- Job: `{payload.get('job_name')}`",
        f"- Process started: `{payload.get('process_started')}`",
        f"- Process state: `{payload.get('process_state')}`",
        f"- Return code: `{payload.get('returncode')}`",
        f"- Timed out: `{payload.get('process_timed_out')}`",
        f"- Materialization wait seconds: `{payload.get('materialization_wait_seconds')}`",
        f"- Materialization wait timed out: `{payload.get('materialization_wait_timed_out')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Compact failure: `{payload.get('compact_failure_class')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        f"- Ready for compact ingest: `{payload.get('ready_for_compact_result_ingest')}`",
        f"- Ready for failure marker: `{payload.get('ready_for_compact_failure_marker')}`",
        f"- Post-launch blocker: `{post_launch.get('first_blocker')}`",
        f"- No upload / submit eligible: `{boundary.get('no_upload')}` / `{boundary.get('submit_eligible')}`",
        f"- Raw logs read: `{boundary.get('raw_logs_read')}`",
        f"- Task text read: `{boundary.get('task_text_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_worker_materialization_probe_launch_markdown(
    payload: dict[str, object],
) -> str:
    post_launch = (
        payload.get("post_launch_materialization")
        if isinstance(payload.get("post_launch_materialization"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    command_shape = (
        payload.get("command_shape")
        if isinstance(payload.get("command_shape"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Worker Materialization Probe Launch",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Run: `{payload.get('run_basename')}`",
        f"- Job: `{payload.get('job_name')}`",
        f"- Process started: `{payload.get('process_started')}`",
        f"- Process state: `{payload.get('process_state')}`",
        f"- Return code: `{payload.get('returncode')}`",
        f"- Timed out: `{payload.get('process_timed_out')}`",
        f"- Resume after materialization: `{payload.get('resume_after_materialization')}`",
        f"- Resume attempted: `{payload.get('resume_after_materialization_attempted')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Compact failure: `{payload.get('compact_failure_class')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        f"- Ready for compact ingest: `{payload.get('ready_for_compact_result_ingest')}`",
        f"- Post-launch blocker: `{post_launch.get('first_blocker')}`",
        "- Probe-only kwarg: "
        f"`{command_shape.get('worker_materialization_probe_only')}`",
        f"- No upload / submit eligible: `{boundary.get('no_upload')}` / `{boundary.get('submit_eligible')}`",
        f"- Task solver invoked by probe: `{boundary.get('task_solver_invoked_by_probe')}`",
        f"- Raw logs read: `{boundary.get('raw_logs_read')}`",
        f"- Task text read: `{boundary.get('task_text_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_case_run_launch_markdown(
    payload: dict[str, object],
) -> str:
    post_launch = (
        payload.get("post_launch_materialization")
        if isinstance(payload.get("post_launch_materialization"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    command_shape = (
        payload.get("command_shape")
        if isinstance(payload.get("command_shape"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Case Run Launch",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Run: `{payload.get('run_basename')}`",
        f"- Job: `{payload.get('job_name')}`",
        f"- Process started: `{payload.get('process_started')}`",
        f"- Process state: `{payload.get('process_state')}`",
        f"- Return code: `{payload.get('returncode')}`",
        f"- Timed out: `{payload.get('process_timed_out')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Compact failure: `{payload.get('compact_failure_class')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        f"- Ready for compact ingest: `{payload.get('ready_for_compact_result_ingest')}`",
        f"- Post-launch blocker: `{post_launch.get('first_blocker')}`",
        "- Probe-only kwarg: "
        f"`{command_shape.get('worker_materialization_probe_only')}`",
        f"- No upload / submit eligible: `{boundary.get('no_upload')}` / `{boundary.get('submit_eligible')}`",
        f"- Task solver invoked: `{boundary.get('task_solver_invoked')}`",
        f"- Model API expected: `{boundary.get('model_api_expected')}`",
        f"- Raw logs read: `{boundary.get('raw_logs_read')}`",
        f"- Task text read: `{boundary.get('task_text_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_worker_materialization_probe_poll_markdown(
    payload: dict[str, object],
) -> str:
    post_launch = (
        payload.get("post_launch_materialization")
        if isinstance(payload.get("post_launch_materialization"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    pid_state = (
        payload.get("pid_state") if isinstance(payload.get("pid_state"), dict) else {}
    )
    lines = [
        "# Terminal-Bench Worker Materialization Probe Poll",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Run: `{payload.get('run_basename')}`",
        f"- Job: `{payload.get('job_name')}`",
        f"- Process state: `{payload.get('process_state')}`",
        f"- PID file present/parsed: `{pid_state.get('pid_file_present')}`/`{pid_state.get('pid_parse_ok')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Compact failure: `{payload.get('compact_failure_class')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        f"- Ready for compact ingest: `{payload.get('ready_for_compact_result_ingest')}`",
        f"- Ready for failure marker: `{payload.get('ready_for_compact_failure_marker')}`",
        f"- Post-launch blocker: `{post_launch.get('first_blocker')}`",
        f"- No upload / submit eligible: `{boundary.get('no_upload')}` / `{boundary.get('submit_eligible')}`",
        f"- Raw logs read: `{boundary.get('raw_logs_read')}`",
        f"- Task text read: `{boundary.get('task_text_read')}`",
        f"- Command line read: `{boundary.get('command_line_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_resume_observation_markdown(
    payload: dict[str, object],
) -> str:
    post_launch = (
        payload.get("post_launch_materialization")
        if isinstance(payload.get("post_launch_materialization"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    command_shape = (
        payload.get("command_shape")
        if isinstance(payload.get("command_shape"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Job Resume",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Run: `{payload.get('run_basename')}`",
        f"- Job: `{payload.get('job_name')}`",
        f"- Process started: `{payload.get('process_started')}`",
        f"- Process state: `{payload.get('process_state')}`",
        f"- Return code: `{payload.get('returncode')}`",
        f"- Timed out: `{payload.get('process_timed_out')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Compact failure: `{payload.get('compact_failure_class')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        f"- Ready for compact ingest: `{payload.get('ready_for_compact_result_ingest')}`",
        f"- Ready for failure marker: `{payload.get('ready_for_compact_failure_marker')}`",
        f"- Post-launch blocker: `{post_launch.get('first_blocker')}`",
        f"- Uses Harbor job resume: `{command_shape.get('uses_harbor_job_resume')}`",
        f"- No upload / submit eligible: `{boundary.get('no_upload')}` / `{boundary.get('submit_eligible')}`",
        f"- Resume invoked: `{boundary.get('resume_invoked')}`",
        f"- Raw logs read: `{boundary.get('raw_logs_read')}`",
        f"- Task text read: `{boundary.get('task_text_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_verifier_attribution_review_markdown(
    payload: dict[str, object],
) -> str:
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    routing = (
        payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Verifier Attribution Review",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Reviewed runs: `{payload.get('reviewed_run_count')}`",
        f"- Baseline index: `{payload.get('baseline_run_index')}`",
        "- Baseline caveat resolved: "
        f"`{decision.get('baseline_claim_caveat_resolved')}`",
        f"- Clean model attribution: `{decision.get('clean_model_failure_attribution')}`",
        f"- Blockers: `{decision.get('blockers')}`",
        f"- Next action: {decision.get('next_action')}",
        f"- Treatment eligible: `{routing.get('treatment_eligible')}`",
        f"- Repeat allowed: `{routing.get('repeat_allowed')}`",
        f"- New candidate allowed: `{routing.get('new_candidate_allowed')}`",
        f"- Routing action: {routing.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_benchmark_runner_invariant_review_markdown(
    payload: dict[str, object],
) -> str:
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Runner Invariant Review",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Mode: `{payload.get('mode')}`",
        f"- Runner label: `{payload.get('runner_label')}`",
        f"- Classification: `{payload.get('classification')}`",
        f"- Clean: `{payload.get('clean')}`",
        f"- Mismatches: `{payload.get('mismatch_count')}`",
        f"- Missing fields: `{payload.get('missing_field_count')}`",
        f"- Repair: {payload.get('repair_recommendation')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_terminal_bench_post_launch_materialization_markdown(
    payload: dict[str, object],
) -> str:
    lines = [
        "# Terminal-Bench Post-Launch Materialization",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Checked: `{payload.get('checked')}`",
        f"- Ready for launch state: `{payload.get('ready_for_launch_state')}`",
        "- Ready for compact result ingest: "
        f"`{payload.get('ready_for_compact_result_ingest')}`",
        "- Ready for compact failure marker: "
        f"`{payload.get('ready_for_compact_failure_marker')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Job name: `{payload.get('job_name')}`",
        f"- Jobs dir present: `{payload.get('jobs_dir_present')}`",
        f"- Job root present: `{payload.get('job_root_present')}`",
        f"- Job lock present: `{payload.get('job_lock_present')}`",
        f"- Job result present: `{payload.get('job_result_present')}`",
        f"- Trial results: `{payload.get('trial_result_present_count')}`",
        f"- Raw paths recorded: `{payload.get('raw_paths_recorded')}`",
        f"- Raw logs read: `{payload.get('raw_logs_read')}`",
        f"- Task text read: `{payload.get('raw_task_text_read')}`",
        f"- Trajectory read: `{payload.get('trajectory_read')}`",
        f"- External handle kind: `{payload.get('external_handle_kind')}`",
        f"- External handle state: `{payload.get('external_handle_state')}`",
        f"- External handle terminal: `{payload.get('external_handle_terminal')}`",
        f"- Compact monitor class: `{payload.get('compact_monitor_class')}`",
        "- Stale active reconcile requested: "
        f"`{payload.get('stale_active_reconcile_requested')}`",
        f"- Compact failure class: `{payload.get('compact_failure_class')}`",
    ]
    if payload.get("error"):
        lines.append(f"- Error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_terminal_bench_result_finalization_gate_markdown(
    payload: dict[str, object],
) -> str:
    conditions = (
        payload.get("gate_conditions")
        if isinstance(payload.get("gate_conditions"), dict)
        else {}
    )
    constraints = (
        payload.get("rerun_constraints")
        if isinstance(payload.get("rerun_constraints"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Result Finalization Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Failure class: `{payload.get('failure_class')}`",
        f"- Root cause: `{payload.get('root_cause')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Repair class: `{payload.get('repair_class')}`",
        "- Result finalization repair required: "
        f"`{payload.get('result_finalization_repair_required')}`",
        "- Repaired baseline rerun allowed: "
        f"`{payload.get('repaired_baseline_rerun_allowed')}`",
        f"- Next action: {payload.get('next_allowed_action')}",
        f"- Launch state countable: `{conditions.get('launch_state_countable')}`",
        f"- External handle terminal: `{conditions.get('external_handle_terminal')}`",
        f"- No trial result: `{conditions.get('no_trial_result')}`",
        f"- Baseline only: `{constraints.get('baseline_only')}`",
        f"- Max reruns: `{constraints.get('max_reruns')}`",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    if payload.get("error"):
        lines.append(f"- Error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def add_subcommand_format(arg_parser: argparse.ArgumentParser) -> None:
    arg_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand. Equivalent to global --format before the command.",
    )


def output_format(args: argparse.Namespace, *local_dests: str) -> str:
    for dest in (*local_dests, "subcommand_format"):
        value = getattr(args, dest, None)
        if value:
            return str(value)
    return str(args.format)


def user_supplied_registry(argv: list[str] | None) -> bool:
    values = sys.argv[1:] if argv is None else argv
    return any(value == "--registry" or value.startswith("--registry=") for value in values)


def fallback_global_registry(registry_path: Path, runtime_root_arg: str | None) -> Path:
    if registry_path.exists():
        return registry_path
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    fallback_registry = global_registry_path(runtime_root)
    return fallback_registry if fallback_registry.exists() else registry_path


def explicit_global_registry(runtime_root_arg: str | None) -> Path:
    runtime_root = Path(runtime_root_arg).expanduser() if runtime_root_arg else DEFAULT_RUNTIME_ROOT
    return global_registry_path(runtime_root)


def append_cli_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    event_kind: str,
    agent_id: str | None = None,
    todo_id: str | None = None,
    benchmark_id: str | None = None,
    case_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    summary: str | None = None,
    labels: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    details: dict[str, object] | None = None,
    allow_failed: bool = False,
) -> dict[str, object]:
    """Append a compact rollout event for core CLI lifecycle commands.

    Rollout logging is intentionally best-effort so the diagnostic log cannot
    turn a successful state transition into a failed CLI command. Failures are
    surfaced in the command payload as compact metadata.
    """

    if not payload.get("ok") and not allow_failed:
        return payload
    goal_id = str(payload.get("goal_id") or "").strip()
    if not goal_id:
        return payload
    try:
        runtime_root_value = payload.get("runtime_root")
        if runtime_root_value:
            runtime_root = Path(str(runtime_root_value)).expanduser()
        else:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, runtime_root_arg)
        event = build_rollout_event(
            goal_id=goal_id,
            event_kind=event_kind,
            agent_id=agent_id or str(payload.get("agent_id") or "").strip() or None,
            todo_id=todo_id or str(payload.get("todo_id") or "").strip() or None,
            benchmark_id=benchmark_id,
            case_id=case_id,
            run_id=run_id,
            status=status,
            classification=str(payload.get("classification") or "").strip() or None,
            delivery_outcome=str(payload.get("delivery_outcome") or "").strip() or None,
            labels=labels,
            summary=summary,
            artifact_refs=artifact_refs,
            details=details,
        )
        appended = append_rollout_event(rollout_event_log_path(runtime_root, goal_id), event)
        payload["rollout_event"] = {
            "schema_version": appended["schema_version"],
            "event_id": appended["event_id"],
            "event_kind": appended["event_kind"],
            "recorded_at": appended["recorded_at"],
            "status": appended.get("status"),
        }
    except Exception as exc:
        payload["rollout_event_log_error"] = {
            "recorded": False,
            "error_type": type(exc).__name__,
            "message": "rollout event append failed; primary command payload remains authoritative",
        }
    return payload


def _compact_benchmark_rollout_label(value: object, *, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _first_benchmark_trial_value(
    benchmark_record: dict[str, object],
    key: str,
) -> object | None:
    trials = benchmark_record.get("trials")
    if not isinstance(trials, list):
        return None
    for trial in trials:
        if isinstance(trial, dict) and trial.get(key) is not None:
            return trial.get(key)
    return None


def _benchmark_rollout_case_id(benchmark_record: dict[str, object]) -> str | None:
    return _compact_benchmark_rollout_label(
        benchmark_record.get("case_id")
        or benchmark_record.get("task_id")
        or _first_benchmark_trial_value(benchmark_record, "task_id")
        or benchmark_record.get("scenario_id")
    )


def _benchmark_official_score_summary(
    benchmark_record: dict[str, object],
) -> tuple[object | None, object | None, str | None]:
    official = benchmark_record.get("official_task_score")
    if isinstance(official, dict):
        return (
            official.get("value"),
            official.get("passed"),
            _compact_benchmark_rollout_label(
                official.get("status") or official.get("kind")
            ),
        )
    return (
        benchmark_record.get("official_score"),
        benchmark_record.get("official_score_passed"),
        _compact_benchmark_rollout_label(benchmark_record.get("official_score_status")),
    )


def _benchmark_rollout_status(benchmark_record: dict[str, object]) -> str:
    failure_attribution = _compact_benchmark_rollout_label(
        benchmark_record.get("score_failure_attribution")
        or benchmark_record.get("failure_attribution")
    )
    score, passed, score_status = _benchmark_official_score_summary(benchmark_record)
    if failure_attribution and failure_attribution not in {
        "none",
        "no_score_failure",
    }:
        return "precise_blocker"
    if passed is True:
        return "passed"
    if passed is False:
        return "failed"
    if score_status == "not_run":
        return "not_run"
    runner_status = _compact_benchmark_rollout_label(
        benchmark_record.get("runner_return_status")
        or benchmark_record.get("terminal_state")
    )
    if runner_status:
        return runner_status
    if score is not None:
        return "scored"
    return "appended"


def _benchmark_rollout_event_kind(benchmark_record: dict[str, object]) -> str:
    return (
        "compact_blocker"
        if _benchmark_rollout_status(benchmark_record) == "precise_blocker"
        else "compact_case_result"
    )


def _benchmark_rollout_labels(benchmark_record: dict[str, object]) -> list[str]:
    labels: list[str] = []
    for value in (
        benchmark_record.get("mode"),
        benchmark_record.get("source_runner"),
        benchmark_record.get("runner_return_status"),
        benchmark_record.get("official_score_status"),
        benchmark_record.get("score_failure_attribution"),
        benchmark_record.get("failure_attribution"),
    ):
        label = _compact_benchmark_rollout_label(value, limit=80)
        if label and label not in labels:
            labels.append(label)
    return labels


def _benchmark_rollout_details(
    benchmark_record: dict[str, object],
    *,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    score, passed, score_status = _benchmark_official_score_summary(benchmark_record)
    progress = (
        benchmark_record.get("progress")
        if isinstance(benchmark_record.get("progress"), dict)
        else {}
    )
    trials = benchmark_record.get("trials")
    return {
        "command": command,
        "action": action or "",
        "mode": benchmark_record.get("mode") or "",
        "source_runner": benchmark_record.get("source_runner") or "",
        "runner_status": benchmark_record.get("runner_return_status") or "",
        "score_status": score_status or "",
        "official_score": score if isinstance(score, (int, float)) else "",
        "official_passed": passed if isinstance(passed, bool) else "",
        "failure_attribution": benchmark_record.get("score_failure_attribution")
        or benchmark_record.get("failure_attribution")
        or "",
        "trial_count": len(trials) if isinstance(trials, list) else "",
        "progress_completed": progress.get("n_completed_trials") or "",
        "progress_total": progress.get("n_total_trials") or "",
    }


def append_benchmark_run_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    benchmark_run = (
        payload.get("benchmark_run")
        if isinstance(payload.get("benchmark_run"), dict)
        else {}
    )
    if not benchmark_run or payload.get("dry_run") or not payload.get("appended"):
        return payload
    benchmark_id = _compact_benchmark_rollout_label(benchmark_run.get("benchmark_id"))
    case_id = _benchmark_rollout_case_id(benchmark_run)
    status = _benchmark_rollout_status(benchmark_run)
    return append_cli_rollout_event(
        payload,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        event_kind=_benchmark_rollout_event_kind(benchmark_run),
        benchmark_id=benchmark_id,
        case_id=case_id,
        run_id=_compact_benchmark_rollout_label(payload.get("generated_at")),
        status=status,
        summary=(
            "benchmark_run compact lifecycle event recorded: "
            f"benchmark={benchmark_id or 'unknown'} "
            f"case={case_id or 'unknown'} status={status}"
        ),
        labels=_benchmark_rollout_labels(benchmark_run),
        details=_benchmark_rollout_details(
            benchmark_run,
            command=command,
            action=action,
        ),
    )


def append_benchmark_result_rollout_event(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    command: str,
    action: str | None = None,
) -> dict[str, object]:
    benchmark_result = (
        payload.get("benchmark_result")
        if isinstance(payload.get("benchmark_result"), dict)
        else {}
    )
    if not benchmark_result or payload.get("dry_run") or not payload.get("appended"):
        return payload
    benchmark_id = _compact_benchmark_rollout_label(
        benchmark_result.get("benchmark_id") or "benchmark_result"
    )
    case_id = _benchmark_rollout_case_id(benchmark_result)
    status = _benchmark_rollout_status(benchmark_result)
    return append_cli_rollout_event(
        payload,
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        event_kind=_benchmark_rollout_event_kind(benchmark_result),
        benchmark_id=benchmark_id,
        case_id=case_id,
        run_id=_compact_benchmark_rollout_label(payload.get("generated_at")),
        status=status,
        summary=(
            "benchmark_result compact lifecycle event recorded: "
            f"benchmark={benchmark_id or 'unknown'} "
            f"case={case_id or 'unknown'} status={status}"
        ),
        labels=_benchmark_rollout_labels(benchmark_result),
        details=_benchmark_rollout_details(
            benchmark_result,
            command=command,
            action=action,
        ),
    )


def resolve_heartbeat_active_state(
    *,
    goal_id: str,
    active_state_arg: str | None,
    registry_path: Path,
    runtime_root_arg: str | None,
    allow_global_goal_lookup_fallback: bool = True,
) -> tuple[Path | None, Path | None, str]:
    if active_state_arg:
        active_state = Path(active_state_arg).expanduser()
        return active_state, active_state, "explicit"

    resolved_registry = fallback_global_registry(registry_path, runtime_root_arg)
    registry = load_registry(resolved_registry)
    goal = next((item for item in registry_goals(registry) if item.get("id") == goal_id), None)
    if goal is None and allow_global_goal_lookup_fallback:
        global_registry = explicit_global_registry(runtime_root_arg)
        if global_registry != resolved_registry and global_registry.exists():
            global_payload = load_registry(global_registry)
            global_goal = next((item for item in registry_goals(global_payload) if item.get("id") == goal_id), None)
            if global_goal is not None:
                resolved_registry = global_registry
                registry = global_payload
                goal = global_goal
    if goal is None:
        raise ValueError(f"goal_id not found in registry for heartbeat active-state lookup: {goal_id}")
    repo_text = str(goal.get("repo") or "")
    if not repo_text:
        raise ValueError(f"{goal_id}: registry goal has no repo for active-state lookup")
    state_file = resolve_state_file(Path(repo_text).expanduser(), goal.get("state_file"))
    if state_file is None:
        raise ValueError(f"{goal_id}: registry goal has no state_file for active-state lookup")
    if not state_file.exists():
        raise FileNotFoundError(f"{goal_id}: registry-declared active state file does not exist: {state_file}")
    return None, state_file, f"registry:{resolved_registry}"


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Goal Harness control-plane helper.")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = sub.add_parser(
        "bootstrap",
        aliases=["connect"],
        help="Create or connect a project-local registry and active goal state.",
    )
    bootstrap_parser.add_argument("--project", default=".", help="Project directory to connect.")
    bootstrap_parser.add_argument("--goal-id", help="Stable goal id. Defaults to <project-name>-goal.")
    bootstrap_parser.add_argument("--objective", default=DEFAULT_OBJECTIVE, help="Initial goal objective.")
    bootstrap_parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Goal domain label.")
    bootstrap_parser.add_argument("--role", choices=["controller", "subagent"], default="controller")
    bootstrap_parser.add_argument("--parent-goal-id", help="Parent goal id when --role subagent.")
    bootstrap_parser.add_argument("--state-file", help="Active goal state path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--goal-doc", help="Primary goal document path, relative to project unless absolute.")
    bootstrap_parser.add_argument("--adapter-kind", default="generic_project_goal_v0")
    bootstrap_parser.add_argument("--adapter-status", default="connected")
    bootstrap_parser.add_argument("--next-probe", help="Optional project-specific pre-tick command.")
    bootstrap_parser.add_argument("--spawn-allowed", action="store_true", help="Declare that this controller may spawn child agents.")
    bootstrap_parser.add_argument("--max-children", type=int, default=3)
    bootstrap_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    bootstrap_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")
    bootstrap_parser.add_argument("--claim-ttl-minutes", type=int, default=30)
    bootstrap_parser.add_argument(
        "--execution-minimum-scale",
        default=str(DEFAULT_EXECUTION_PROFILE["minimum_scale"]),
        help="Minimum delivery scale after repeated small follow-through.",
    )
    bootstrap_parser.add_argument(
        "--execution-must-include",
        action="append",
        default=[],
        help="Required delivery component. Repeatable; defaults to artifact, validation, and state writeback.",
    )
    bootstrap_parser.add_argument(
        "--execution-small-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["degradation_policy"]["small_scale_streak_threshold"]),
        help="Repeated small-scale streak that triggers the delivery contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-marker",
        action="append",
        default=[],
        help="Classification substring that counts as primary outcome/evidence progress. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-only-hint",
        action="append",
        default=[],
        help="Classification substring that counts as surface-only progress unless an outcome marker is present. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--execution-surface-streak-threshold",
        type=int,
        default=int(DEFAULT_EXECUTION_PROFILE["outcome_floor"]["surface_streak_threshold"]),
        help="Surface-progress streak that triggers the outcome-floor contract.",
    )
    bootstrap_parser.add_argument(
        "--execution-outcome-must-advance",
        action="append",
        default=[],
        help="Outcome/evidence floor label that future delivery must advance. Repeatable.",
    )
    bootstrap_parser.add_argument(
        "--no-onboarding-scan",
        action="store_true",
        help="Skip the fast first-connect repository scan and todo candidate proposal.",
    )
    bootstrap_parser.add_argument(
        "--accept-onboarding-agent-todos",
        action="store_true",
        help="Write all proposed onboarding agent todos into the initial active state.",
    )
    bootstrap_parser.add_argument(
        "--begin-autonomous-advance",
        action="store_true",
        help="Record that Codex may begin from accepted onboarding agent todos after the quota guard permits work.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-commits",
        type=int,
        default=5,
        help="Maximum recent commits sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-status-paths",
        type=int,
        default=12,
        help="Maximum git status lines sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument(
        "--onboarding-max-top-level-files",
        type=int,
        default=24,
        help="Maximum top-level names sampled by the fast onboarding scan.",
    )
    bootstrap_parser.add_argument("--force", action="store_true", help="Replace existing goal entry or state file.")
    bootstrap_parser.add_argument("--dry-run", action="store_true", help="Show planned writes without changing files.")
    bootstrap_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not merge this project registry into the shared global registry.",
    )

    register_starter_commands(sub)

    heartbeat_prompt_parser = sub.add_parser(
        "heartbeat-prompt",
        help="Generate a guarded Codex App heartbeat automation task body.",
    )
    add_subcommand_format(heartbeat_prompt_parser)
    heartbeat_prompt_parser.add_argument("--goal-id", required=True, help="Stable Goal Harness goal id.")
    heartbeat_prompt_parser.add_argument(
        "--active-state",
        help="Active goal state file the heartbeat should read and write back. Defaults to the registry goal state_file.",
    )
    heartbeat_prompt_parser.add_argument(
        "--material-rule",
        help="Optional project-specific material queue rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--permission-rule",
        help="Optional trusted-session permission rule appended to the task body.",
    )
    heartbeat_prompt_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Command name embedded in generated preflight/guard/spend commands. Use goal-harness-canary for gray rollout targets.",
    )
    heartbeat_prompt_parser.add_argument(
        "--agent-id",
        help="Optional public-safe automation agent id, such as codex-main-control or codex-side-bypass.",
    )
    heartbeat_prompt_parser.add_argument(
        "--agent-scope",
        dest="agent_scopes",
        action="append",
        help="Optional natural-language scope for this automation agent. Repeat for multiple scope lines.",
    )
    heartbeat_style_group = heartbeat_prompt_parser.add_mutually_exclusive_group()
    heartbeat_style_group.add_argument(
        "--compact",
        action="store_true",
        help="Generate a shorter automation body that points edge cases back to the expanded lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--brief",
        action="store_true",
        help="Generate a minimal installed automation body that delegates details to the compact lifecycle contract.",
    )
    heartbeat_style_group.add_argument(
        "--thin",
        action="store_true",
        help="Generate the thinnest generic dispatcher body for trusted agents that inspect Goal Harness state themselves.",
    )

    register_doctor_command(sub)

    worker_bridge_parser = sub.add_parser(
        "worker-bridge",
        help="Render runner-agnostic worker bridge/install contracts.",
    )
    worker_bridge_sub = worker_bridge_parser.add_subparsers(dest="worker_bridge_command")
    worker_bridge_contract_parser = worker_bridge_sub.add_parser(
        "contract",
        help="Render a Goal Harness worker bridge/install contract.",
    )
    add_subcommand_format(worker_bridge_contract_parser)
    worker_bridge_contract_parser.add_argument(
        "--project-root",
        default=GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness project root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--runtime-root",
        dest="worker_bridge_runtime_root",
        default=GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness runtime root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    worker_bridge_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="Goal Harness CLI module import path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--scan-path",
        help="Container-visible public scan path. Defaults to the Goal Harness benchmark module.",
    )
    worker_bridge_contract_parser.add_argument(
        "--benchmark-run-json",
        default=DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
        help="Worker-visible benchmark_run_v0 JSON write path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--counter-trace-json",
        default=DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
        help="Worker-visible compact counter trace JSONL path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--classification",
        default="<classification>",
        help="Classification label for worker-side compact writeback.",
    )
    worker_bridge_outcome_parser = worker_bridge_sub.add_parser(
        "outcome",
        help="Render compact worker bridge evidence and runner-return outcome.",
    )
    add_subcommand_format(worker_bridge_outcome_parser)
    worker_bridge_outcome_parser.add_argument(
        "--worker-cli-call-total",
        type=int,
        default=0,
        help="Compact count of in-worker Goal Harness CLI calls.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--required-worker-cli-call-total-min",
        type=int,
        default=1,
        help="Minimum worker CLI call count required to claim bridge verification.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--counter-trace-present",
        action="store_true",
        help="Whether a compact worker counter trace was observed.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--runner-return-completed",
        action="store_true",
        help="Whether the runner returned a completed case result.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--official-score-completed",
        action="store_true",
        help="Whether an official task score is available.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--official-score-value",
        type=float,
        help="Official task score value when --official-score-completed is set.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--interrupted",
        action="store_true",
        help="Whether the controller interrupted the worker run.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--interrupt-reason",
        default="",
        help="Public-safe interrupt reason label.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--wall-time-seconds",
        type=float,
        help="Observed wall time in seconds, if available.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--wall-time-limit-seconds",
        type=float,
        default=DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
        help="Controller wall-time limit for this worker bridge outcome.",
    )
    worker_bridge_outcome_parser.add_argument(
        "--side-effect-audit-failed",
        action="store_true",
        help="Mark the side-effect audit as failed.",
    )
    worker_bridge_benchmark_run_parser = worker_bridge_sub.add_parser(
        "benchmark-run",
        help="Render a worker-side benchmark_run_v0 writeback payload.",
    )
    add_subcommand_format(worker_bridge_benchmark_run_parser)
    worker_bridge_benchmark_run_parser.add_argument(
        "--source-runner",
        default="worker_bridge_runner",
        help="Public-safe runner label for the worker-side benchmark_run_v0 payload.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--benchmark-id",
        default="worker-bridge-sample@v0",
        help="Public-safe benchmark id.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--job-name",
        default="goal_harness_worker_bridge_sample",
        help="Public-safe job name.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--mode",
        dest="worker_bridge_benchmark_mode",
        default="codex_goal_harness_active_worker",
        help="Benchmark treatment mode.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--worker-mode",
        default="codex_goal_harness_cli",
        help="Worker mode label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--task-id",
        default="worker-bridge-sample",
        help="Public-safe task id.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--trial-name",
        default="worker-bridge-sample-worker",
        help="Public-safe trial name.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-kind",
        help="Official score kind label. Defaults to a blocker or sample-success label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--worker-cli-call-total",
        type=int,
        default=0,
        help="Compact count of in-worker Goal Harness CLI calls.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--required-worker-cli-call-total-min",
        type=int,
        default=1,
        help="Minimum worker CLI call count required to claim bridge verification.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--counter-trace-present",
        action="store_true",
        help="Whether a compact worker counter trace was observed.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--runner-return-completed",
        action="store_true",
        help="Whether the runner returned a completed case result.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-completed",
        action="store_true",
        help="Whether an official task score is available.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--official-score-value",
        type=float,
        help="Official task score value when --official-score-completed is set.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--interrupted",
        action="store_true",
        help="Whether the controller interrupted the worker run.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--interrupt-reason",
        default="",
        help="Public-safe interrupt reason label.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--wall-time-seconds",
        type=float,
        help="Observed wall time in seconds, if available.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--wall-time-limit-seconds",
        type=float,
        default=DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
        help="Controller wall-time limit for this worker bridge outcome.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--side-effect-audit-failed",
        action="store_true",
        help="Mark the side-effect audit as failed.",
    )
    active_user_contract_parser = worker_bridge_sub.add_parser(
        "active-user-contract",
        help="Render the active-user simulator external-update channel contract.",
    )
    add_subcommand_format(active_user_contract_parser)
    active_user_contract_parser.add_argument(
        "--project-root",
        default=GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness project root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--runtime-root",
        dest="active_user_runtime_root",
        default=GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible Goal Harness runtime root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    active_user_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="Goal Harness CLI module import path.",
    )
    active_user_contract_parser.add_argument(
        "--feed-jsonl",
        default=DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        help="Worker-visible active-user intervention feed JSONL path.",
    )
    active_user_contract_parser.add_argument(
        "--observation-json",
        default=DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
        help="Worker-visible active-user observation JSON path.",
    )
    active_user_contract_parser.add_argument(
        "--counter-trace-json",
        default=DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
        help="Worker-visible compact counter trace JSONL path.",
    )
    active_user_contract_parser.add_argument(
        "--benchmark-run-json",
        default=DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
        help="Worker-visible compact benchmark_run checkpoint JSON path.",
    )
    active_user_contract_parser.add_argument(
        "--classification",
        default="active_user_observe_checkpoint",
        help="Compact classification label for observe checkpoints.",
    )
    active_user_contract_parser.add_argument(
        "--min-interval-seconds",
        type=int,
        default=300,
        help="Minimum interval between proactive simulator interventions.",
    )
    active_user_contract_parser.add_argument(
        "--max-interventions-per-task",
        type=int,
        default=3,
        help="Maximum proactive simulator interventions per task.",
    )
    active_user_codex_simulator_contract_parser = worker_bridge_sub.add_parser(
        "active-user-codex-simulator-contract",
        help="Render the formal Codex CLI active-user simulator launch contract.",
    )
    add_subcommand_format(active_user_codex_simulator_contract_parser)
    active_user_codex_simulator_contract_parser.add_argument(
        "--project-root",
        default=GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
        help="Goal Harness project root visible to the simulator launcher.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable used to append the validated simulator output.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="Goal Harness CLI module import path.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_ACTIVE_USER_CODEX_BIN,
        help="Codex CLI executable used for the user simulator.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--context-dir",
        default=DEFAULT_ACTIVE_USER_SIMULATOR_CONTEXT_DIR,
        help="Public context directory made readable to the Codex CLI simulator.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--prompt-json",
        default=DEFAULT_ACTIVE_USER_SIMULATOR_PROMPT_JSON,
        help="Prompt/context JSON file passed to Codex CLI on stdin.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--simulator-output-json",
        default=DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_JSON,
        help="Path where Codex CLI writes the simulator JSON output.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--simulator-output-schema-json",
        default=DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_SCHEMA_JSON,
        help="JSON Schema file constraining the Codex CLI simulator response.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--feed-jsonl",
        default=DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        help="Worker-visible active-user intervention feed JSONL path.",
    )
    active_user_intervention_parser = worker_bridge_sub.add_parser(
        "active-user-intervention",
        help="Render one public-safe active-user simulator intervention event.",
    )
    add_subcommand_format(active_user_intervention_parser)
    active_user_intervention_parser.add_argument("--seq", type=int, required=True)
    active_user_intervention_parser.add_argument("--message", required=True)
    active_user_intervention_parser.add_argument(
        "--trigger",
        default="public_progress_or_stall_signal",
        help="Public-safe intervention trigger label.",
    )
    active_user_intervention_parser.add_argument(
        "--channel",
        default="simulator_proactive_user_message",
        help="Public-safe intervention channel label.",
    )
    active_user_intervention_parser.add_argument(
        "--before-worker-start",
        action="store_true",
        help="Mark this intervention as created before the worker start marker.",
    )
    active_user_intervention_parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Print compact single-line JSON for appending to an intervention feed.",
    )
    active_user_simulator_output_parser = worker_bridge_sub.add_parser(
        "active-user-simulator-output",
        help="Validate a Codex CLI simulator JSON output and render feed JSON.",
    )
    add_subcommand_format(active_user_simulator_output_parser)
    active_user_simulator_output_parser.add_argument("--seq", type=int, required=True)
    active_user_simulator_output_parser.add_argument(
        "--simulator-output-json",
        required=True,
        help="Path to Codex CLI simulator JSON output, or '-' for stdin.",
    )
    active_user_simulator_output_parser.add_argument(
        "--before-worker-start",
        action="store_true",
        help="Mark the resulting intervention as created before the worker start marker.",
    )
    active_user_simulator_output_parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Print compact single-line JSON for appending to an intervention feed.",
    )
    active_user_observe_parser = worker_bridge_sub.add_parser(
        "active-user-observe",
        help="Observe active-user interventions created after the worker start marker.",
    )
    add_subcommand_format(active_user_observe_parser)
    active_user_observe_parser.add_argument(
        "--feed-jsonl",
        required=True,
        help="Active-user intervention feed JSONL path to read.",
    )
    active_user_observe_parser.add_argument(
        "--worker-start-seq",
        type=int,
        default=0,
        help="Worker start marker sequence; only later interventions are observable.",
    )
    active_user_observe_parser.add_argument(
        "--observation-json",
        help="Optional path to write the compact observation JSON.",
    )
    active_user_observe_parser.add_argument(
        "--counter-trace-json",
        help="Optional worker counter trace JSONL path to append active_user_observe.",
    )
    active_user_observe_parser.add_argument(
        "--benchmark-run-json",
        help="Optional compact worker benchmark_run checkpoint JSON path to write.",
    )
    active_user_observe_parser.add_argument(
        "--goal-id",
        default="worker-bridge-active-user",
        help="Compact goal id label for optional counter/checkpoint writeback.",
    )
    active_user_observe_parser.add_argument(
        "--bridge-mode",
        default="codex_goal_harness_active_worker",
        help="Compact worker bridge mode label for optional counter/checkpoint writeback.",
    )
    active_user_observe_parser.add_argument(
        "--classification",
        default="active_user_observe_checkpoint",
        help="Compact classification label for optional counter/checkpoint writeback.",
    )
    active_user_observe_parser.add_argument(
        "--task-id",
        default="worker-bridge-active-user",
        help="Compact task id label for optional benchmark_run checkpoint.",
    )
    active_user_observe_parser.add_argument(
        "--trial-name",
        default="worker-bridge-active-user-observe-checkpoint",
        help="Compact trial name for optional benchmark_run checkpoint.",
    )

    promotion_gate_parser = sub.add_parser(
        "promotion-gate",
        help="Emit a compact machine-readable canary promotion readiness gate result.",
    )
    add_subcommand_format(promotion_gate_parser)

    upgrade_plan_parser = sub.add_parser(
        "upgrade-plan",
        help="Plan local default upgrade propagation for managed heartbeat automations.",
    )
    add_subcommand_format(upgrade_plan_parser)
    upgrade_plan_parser.add_argument("--goal-id", action="append", default=[], help="Only include one goal id. Repeatable.")
    upgrade_plan_parser.add_argument(
        "--installed-manifest",
        help=(
            "Optional JSON manifest of installed automations with goal_id, mode, automation_id, and "
            "prompt_sha256/task_body. If omitted, upgrade-plan auto-discovers Codex App heartbeat "
            "automations from $CODEX_HOME/automations or ~/.codex/automations."
        ),
    )
    upgrade_plan_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="CLI command embedded in generated heartbeat prompts for the promoted default.",
    )
    upgrade_plan_parser.add_argument(
        "--mode",
        action="append",
        choices=["thin", "brief", "compact"],
        default=[],
        help="Prompt mode to compare. Repeatable; defaults to the thin installed heartbeat contract.",
    )

    sub.add_parser("registry", help="Inspect registry goals and adapter declarations.")
    registry_boundary_parser = sub.add_parser(
        "registry-boundary",
        help="Classify a registry file as local-only, global-local, public projection, or public fixture.",
    )
    registry_boundary_parser.add_argument(
        "--path",
        help="Registry path to classify. Defaults to the active --registry path.",
    )
    registry_boundary_parser.add_argument(
        "--require-not-tracked",
        action="store_true",
        help="Return non-zero if the registry is tracked while publication policy disallows pushing it.",
    )
    registry_boundary_parser.add_argument(
        "--require-gitignored",
        action="store_true",
        help="Return non-zero if the registry should be ignored but is neither ignored nor tracked.",
    )

    configure_goal_parser = sub.add_parser(
        "configure-goal",
        help="Preview or apply per-goal registry settings for quota, self-repair, and orchestration.",
    )
    configure_goal_parser.add_argument("--goal-id", required=True, help="Goal id to configure.")
    configure_goal_parser.add_argument("--quota-compute", type=float, help="Per-goal quota compute multiplier.")
    configure_goal_parser.add_argument("--quota-window-hours", type=float, help="Quota rolling window in hours.")
    configure_goal_parser.add_argument(
        "--self-repair-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control_plane.self_repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-health",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable control-plane health blocker repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--self-repair-waiting-projection",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable waiting-projection repair for this goal.",
    )
    configure_goal_parser.add_argument(
        "--orchestration-mode",
        choices=["default", "multi_subagent"],
        help="Per-goal orchestration mode.",
    )
    configure_goal_parser.add_argument(
        "--spawn-allowed",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Allow or block sub-agent spawning for this goal.",
    )
    configure_goal_parser.add_argument("--max-children", type=int, help="Maximum child agents for orchestration.")
    configure_goal_parser.add_argument(
        "--allowed-domain",
        action="append",
        default=None,
        help="Allowed child-agent domain. Repeatable; comma-separated values are also accepted.",
    )
    configure_goal_parser.add_argument(
        "--clear-allowed-domains",
        action="store_true",
        help="Clear allowed child-agent domains.",
    )
    configure_goal_parser.add_argument(
        "--registered-agent",
        dest="registered_agents",
        action="append",
        default=None,
        help=(
            "Registered public-safe agent id allowed to claim todos and receive scoped "
            "heartbeat prompts. Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-registered-agents",
        action="store_true",
        help="Clear coordination.registered_agents.",
    )
    configure_goal_parser.add_argument(
        "--primary-agent",
        help=(
            "The single registered agent id that owns main-control review, "
            "verification, merge, and final project coordination."
        ),
    )
    configure_goal_parser.add_argument(
        "--clear-primary-agent",
        action="store_true",
        help="Clear coordination.primary_agent.",
    )
    configure_goal_parser.add_argument(
        "--waiting-on",
        choices=["codex", "user_or_controller", "controller", "external_evidence"],
        help="Override registry waiting owner for status/quota routing.",
    )
    configure_goal_parser.add_argument(
        "--clear-waiting-on",
        action="store_true",
        help="Remove the registry waiting_on override.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-scope",
        action="append",
        default=None,
        help=(
            "Checkpointed write scope approved by an operator/controller decision. "
            "Repeatable; comma-separated values are also accepted."
        ),
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-source",
        help="Public-safe provenance for the checkpointed boundary authority.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-decision-id",
        help="Public-safe decision/run/gate id for the checkpointed boundary authority.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-recorded-at",
        help="ISO timestamp for the checkpointed decision. Defaults to now.",
    )
    configure_goal_parser.add_argument(
        "--boundary-authority-expires-at",
        help="Optional ISO timestamp after which the checkpointed authority is no longer fresh.",
    )
    configure_goal_parser.add_argument(
        "--clear-boundary-authority",
        action="store_true",
        help="Clear coordination.checkpointed_boundary_authority.",
    )
    configure_goal_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the registry. Without this flag, configure-goal is a dry-run preview.",
    )

    history_parser = sub.add_parser("history", help="Read compact run history from the shared runtime root.")
    history_parser.add_argument(
        "history_action",
        nargs="?",
        choices=[
            "append-benchmark-run",
            "append-benchmark-result",
            "append-benchmark-comparison",
            "append-benchmark-learning-ledger",
            "append-benchmark-report",
            "append-agents-last-exam-result-report",
            "append-active-user-assisted-pilot",
            "inspect-index-duplicates",
            "repair-index-duplicates",
        ],
        help=(
            "Append a compact benchmark_run_v0, benchmark_result_v0, benchmark_comparison_v0, "
            "benchmark_learning_ledger_v0, benchmark_experiment_report_v0, ALE compact result report, or "
            "active_user_assisted_pilot_v0 event; inspect duplicate run-index identities; "
            "or repair safe duplicate index rows."
        ),
    )
    history_parser.add_argument("--goal-id", help="Only show one goal.")
    history_parser.add_argument("--limit", type=int, default=10)
    history_parser.add_argument(
        "--benchmark-run-json",
        help="Path to a benchmark_run_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-result-json",
        help="Path to a benchmark_result_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-comparison-json",
        help="Path to a benchmark_comparison_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-learning-ledger-json",
        help="Path to a benchmark_learning_ledger_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--benchmark-report-json",
        help="Path to a benchmark_experiment_report_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument(
        "--agents-last-exam-run-dir",
        help=(
            "Path to an existing Agents' Last Exam run directory. The ingest reads "
            "only run.json, eval_result.json, and events.jsonl; raw trajectory, "
            "origin_log, output, task bodies, screenshots, credentials, and local "
            "absolute paths are excluded."
        ),
    )
    history_parser.add_argument(
        "--report-id",
        help="Optional public-safe report id for append-agents-last-exam-result-report.",
    )
    history_parser.add_argument(
        "--active-user-pilot-json",
        help="Path to an active_user_assisted_pilot_v0 JSON object. Use '-' to read stdin.",
    )
    history_parser.add_argument("--classification")
    history_parser.add_argument(
        "--recommended-action",
        help="Recommended next action for the compact append event.",
    )
    history_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    history_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    history_parser.add_argument("--dry-run", action="store_true", help="Preview append without writing. This is the default.")
    history_parser.add_argument("--execute", action="store_true", help="Append or repair. Without this flag, history write actions are dry-run previews.")
    history_parser.add_argument("--no-global-sync", action="store_true", help="Skip global registry sync after append.")

    benchmark_parser = sub.add_parser(
        "benchmark",
        help="Benchmark runner skeletons. Current public surface is fixture-only and no-run by default.",
    )
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    benchmark_parity_check_parser = benchmark_sub.add_parser(
        "parity-check",
        help=(
            "Posthoc-check whether a compact benchmark_run_v0 has enough "
            "public-safe evidence to support Codex App product-path attribution."
        ),
    )
    add_subcommand_format(benchmark_parity_check_parser)
    benchmark_parity_check_parser.add_argument(
        "--benchmark-run-json",
        required=True,
        help="Path to a compact benchmark_run_v0 JSON object. Use '-' to read stdin.",
    )

    benchmark_run_parser = benchmark_sub.add_parser(
        "run",
        help="Build or append a compact benchmark_run_v0 fixture or ingest a Harbor job result.",
    )
    benchmark_run_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench", "skillsbench"],
        help=(
            "Benchmark family. terminal-bench supports Harbor ingest and fixtures; "
            "skillsbench supports a no-run compact adapter skeleton."
        ),
    )
    benchmark_run_parser.add_argument("--goal-id", required=True, help="Goal id for dry-run/append context.")
    benchmark_run_parser.add_argument(
        "--mode",
        choices=TERMINAL_BENCH_MODES,
        default="goal-harness-managed-codex",
        help="Terminal-Bench worker mode. Defaults to the managed Goal Harness treatment.",
    )
    benchmark_run_parser.add_argument("--dataset", default=TERMINAL_BENCH_DEFAULT_DATASET)
    benchmark_run_parser.add_argument("--include-task-name", default=TERMINAL_BENCH_DEFAULT_TASK)
    benchmark_run_parser.add_argument("--runner", choices=["harbor"], default="harbor")
    benchmark_run_parser.add_argument("--agent", choices=["codex"], default="codex")
    benchmark_run_parser.add_argument("--model", default=TERMINAL_BENCH_DEFAULT_MODEL)
    benchmark_run_parser.add_argument(
        "--skillsbench-route",
        choices=SKILLSBENCH_ROUTES,
        default=SKILLSBENCH_DEFAULT_ROUTE,
        help=(
            "SkillsBench route for the no-run compact adapter skeleton. "
            "Default is goal-harness-blind-loop-treatment: ordinary Codex "
            "inside the case, no /goal mode, and no official reward/pass-fail "
            "or verifier output returned during the loop. "
            "automation-loop-treatment is a reward-feedback ablation."
        ),
    )
    benchmark_run_parser.add_argument(
        "--skillsbench-result-json",
        help=(
            "Ingest an official SkillsBench/BenchFlow result.json into a compact "
            "benchmark_run_v0. This reducer reads only result.json and sibling "
            "timing.json; it does not read prompts, trajectories, verifier logs, "
            "task text, credentials, upload, or submit."
        ),
    )
    benchmark_run_parser.add_argument(
        "--timeout-multiplier",
        type=float,
        help="Preview Harbor --timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--agent-timeout-multiplier",
        type=float,
        help="Preview Harbor --agent-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--verifier-timeout-multiplier",
        type=float,
        help="Preview Harbor --verifier-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--agent-setup-timeout-multiplier",
        type=float,
        help="Preview Harbor --agent-setup-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--environment-build-timeout-multiplier",
        type=float,
        help="Preview Harbor --environment-build-timeout-multiplier for private long-horizon tiers.",
    )
    benchmark_run_parser.add_argument(
        "--codex-install-strategy",
        choices=TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
        default=TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
        help=(
            "Preview the managed Codex setup strategy. require_existing_codex "
            "disables runtime npm install and fails fast if Codex is not already "
            "usable in the worker image."
        ),
    )
    benchmark_run_parser.add_argument(
        "--codex-preflight-timeout-sec",
        type=int,
        help=(
            "Preview the per-command timeout for fail-fast Codex CLI setup probes "
            "inside the worker before a benchmark task starts."
        ),
    )
    benchmark_run_parser.add_argument(
        "--worker-codex-materialization-strategy",
        choices=TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
        help=(
            "Declare how Codex becomes visible inside the worker. "
            "Use worker_path_preprovisioned only after a worker image or launcher "
            "already proves codex is on PATH; use runtime_install_extended_setup "
            "for a bounded setup probe that installs Codex during worker setup."
        ),
    )
    benchmark_run_parser.add_argument(
        "--worker-materialization-probe-only",
        action="store_true",
        help=(
            "Preview a no-upload worker materialization probe that stops after "
            "Codex install/preflight writes compact benchmark_run_v0 evidence; "
            "it does not run task-solving or claim case success."
        ),
    )
    benchmark_run_parser.add_argument(
        "--setup-timeout-repair-profile",
        action="store_true",
        help=(
            "Apply the generic pre-worker setup-timeout repair launch profile: "
            "explicit 8x agent and setup timeout multipliers plus "
            "a declared worker Codex materialization strategy. Without a "
            "runtime materialization strategy it uses require_existing_codex "
            "fail-fast probes."
        ),
    )
    benchmark_run_parser.add_argument(
        "--harbor-job-dir",
        help=(
            "Ingest an existing Harbor job directory into a compact benchmark_run_v0. "
            "This reads runner artifacts and worker counter files only; it does not run "
            "Harbor, Terminal-Bench, Codex, Docker, model APIs, or upload."
        ),
    )
    benchmark_run_parser.add_argument(
        "--fake-worker",
        action="store_true",
        help="Use the deterministic fake managed-worker event path. No real Codex is invoked.",
    )
    benchmark_run_parser.add_argument(
        "--preflight-guard",
        action="store_true",
        help=(
            "Build a managed real-run preflight guard event. This may probe local CLI surfaces "
            "but does not run Harbor, Terminal-Bench, Codex workers, task containers, or uploads."
        ),
    )
    benchmark_run_parser.add_argument(
        "--require-task-material-ready",
        action="store_true",
        help=(
            "With --preflight-guard, require locally resolved Terminal-Bench task material "
            "before the private launch summary can be ready. Unknown or uncached material is "
            "reported as a blocker; no task prompt text is read."
        ),
    )
    benchmark_run_parser.add_argument(
        "--cli-bridge-contract",
        action="store_true",
        help=(
            "Execute the host-agent Goal Harness CLI bridge contract fixture for "
            "codex-goal-harness. This runs Goal Harness CLI read commands and an "
            "append-benchmark-run dry-run only; no Harbor, Terminal-Bench, Codex "
            "worker, model API, or upload is invoked."
        ),
    )
    benchmark_run_parser.add_argument(
        "--worker-cli-bridge-fixture",
        action="store_true",
        help=(
            "Build the codex-goal-harness worker in-case CLI bridge fixture. "
            "This records worker-side Goal Harness call counters separately "
            "from runner bridge calls and does not run Harbor, Terminal-Bench, "
            "Codex workers, model APIs, or uploads."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-cli-bridge",
        action="store_true",
        help=(
            "With codex-goal-harness --preflight-guard, build the private no-upload "
            "repeat preflight that enables the worker Goal Harness CLI bridge and "
            "requires worker-side CLI call counters before any in-case use claim."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-user-assisted-treatment",
        action="store_true",
        help=(
            "With codex-goal-harness --preflight-guard --active-cli-bridge, build "
            "the active-user assisted treatment preflight contract. This does not "
            "run Harbor, Codex, a simulator, or inject user messages."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-user-observation-fixture",
        action="store_true",
        help=(
            "With --active-user-assisted-treatment, build the deterministic worker "
            "after-start active-user observation fixture. This does not run Harbor, "
            "Codex, a model-backed simulator, task containers, or uploads."
        ),
    )
    benchmark_run_parser.add_argument("--classification")
    benchmark_run_parser.add_argument("--recommended-action")
    benchmark_run_parser.add_argument(
        "--update-run-ledger",
        action="store_true",
        help=(
            "After building/appending the compact benchmark_run_v0, upsert a "
            "public-safe benchmark_run_ledger_v0 JSON row and Markdown view."
        ),
    )
    benchmark_run_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON. Markdown is rendered next to it.",
    )
    benchmark_run_parser.add_argument(
        "--run-group-id",
        help="Optional stable run group id for the ledger row.",
    )
    benchmark_run_parser.add_argument(
        "--arm-id",
        help="Optional arm id override for the ledger row.",
    )
    benchmark_run_parser.add_argument(
        "--run-ledger-note",
        help="Optional compact note for the ledger row.",
    )
    benchmark_run_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    benchmark_run_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    benchmark_run_parser.add_argument("--dry-run", action="store_true", help="Preview append without writing. This is the default.")
    benchmark_run_parser.add_argument("--execute", action="store_true", help="Append the compact fixture event.")
    benchmark_run_parser.add_argument("--no-global-sync", action="store_true", help="Skip global registry sync after append.")

    benchmark_run_ledger_upsert_parser = benchmark_sub.add_parser(
        "run-ledger-upsert",
        help=(
            "Upsert benchmark_run_ledger_v0 from an existing compact "
            "benchmark_run_v0 JSON file. This does not read raw runner artifacts."
        ),
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--benchmark-run-json",
        help="Path to a compact benchmark_run_v0 JSON object. Use '-' to read stdin.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--post-launch-json",
        help=(
            "Path to a compact terminal_bench_post_launch_materialization_v0 "
            "object. Use '-' to read stdin. This records result-finalization "
            "or post-launch failure markers without reading raw runner artifacts."
        ),
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON. Markdown is rendered next to it.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-group-id",
        help="Optional stable run group id for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--arm-id",
        help="Optional arm id override for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--compact-artifact-ref",
        help="Optional public-safe relative reference to the compact run artifact.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-ledger-note",
        help="Optional compact note for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview ledger update without writing. This is the default.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the benchmark run ledger update.",
    )
    benchmark_run_ledger_check_parser = benchmark_sub.add_parser(
        "run-ledger-check",
        help=(
            "Compare compact benchmark_run_v0 run history with the public "
            "benchmark_run_ledger_v0. This reads compact history only."
        ),
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose compact benchmark run history should be checked.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--history-limit",
        type=int,
        default=500,
        help="Maximum recent compact run-history rows to compare.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum missing rows to include in output.",
    )
    benchmark_case_analysis_candidates_parser = benchmark_sub.add_parser(
        "case-analysis-candidates",
        help=(
            "Find public-safe benchmark case-analysis candidates from the compact "
            "benchmark run ledger and existing case-analysis keys."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--case-analysis-path",
        default=str(
            BENCHMARK_RUN_LEDGER_DEFAULT_PATH.with_name(
                "benchmark-case-analysis.json"
            )
        ),
        help="Path to benchmark_case_analysis_v0 JSON.",
    )

    agentissue_runner_flow_parser = benchmark_sub.add_parser(
        "agentissue-codex-runner-flow",
        help=(
            "Render or append the AgentIssue-Bench lagent_239 Codex CLI runner "
            "dry-run wrapper. No Codex, Docker, model API, upload, or submit is run."
        ),
    )
    add_subcommand_format(agentissue_runner_flow_parser)
    agentissue_runner_flow_parser.add_argument("--goal-id", required=True, help="Goal id for dry-run/append context.")
    agentissue_runner_flow_parser.add_argument(
        "--tag",
        default=AGENTISSUE_DEFAULT_TAG,
        help="Selected public AgentIssue-Bench tag. Currently only lagent_239 is supported.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="Public command label for host-local Codex CLI command rendering.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="Public command label for selected-tag Docker eval command rendering.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--synthetic-staging-root",
        help=(
            "Materialize a synthetic private job root at PATH with placeholder "
            "prompt, patch-output parent, and compact reducer files. Still no "
            "Codex, Docker, model API, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--execution-gate-root",
        help=(
            "Materialize a guarded no-execute real-source/host-Codex gate at "
            "PATH. It renders selected-container source extraction, private git "
            "baseline, host Codex, patch export, and eval command shapes without "
            "running Codex, Docker, model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--first-run-handoff-root",
        help=(
            "Materialize a no-execute first-run handoff packet at PATH. It "
            "includes the execution gate plus public handoff JSON/Markdown with "
            "command shape, private artifact boundary, compact outputs, and "
            "budget/auth safety checks."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--workflow-check-root",
        help=(
            "Materialize a no-execute workflow invariant check packet at PATH. "
            "It includes the first-run handoff plus workflow-check.public.json "
            "for phase, auth, artifact, and stop-rule checks without running "
            "Codex, Docker, model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--run-gate-root",
        help=(
            "Materialize a no-execute run-specific gate packet at PATH. It "
            "includes the workflow check plus run-specific owner/agent gates "
            "for a later no-upload lagent_239 run without running Codex, Docker, "
            "model APIs, upload, submit, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--target-runner-handoff-root",
        help=(
            "Materialize a no-execute target-runner handoff packet at PATH. It "
            "includes the run-specific gate plus a compact checklist for a "
            "separate benchmark execution thread without running Codex, Docker, "
            "model APIs, upload, submit, ranking paths, or real task material."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--real-result-root",
        help=(
            "Reduce an already completed private real run from "
            "benchmark_run.compact.json and benchmark_result.compact.json at "
            "PATH. Reads compact files only; no Codex, Docker, model API, raw "
            "artifact, upload, submit, or public ranking path is invoked."
        ),
    )
    agentissue_runner_flow_parser.add_argument(
        "--private-runner-root",
        help=(
            "Materialize a private runnable lagent_239 script plus public "
            "manifest at PATH. The generator itself invokes no Codex, Docker, "
            "model API, upload, submit, or public ranking path; the script is "
            "for a later trusted local execution."
        ),
    )
    agentissue_runner_flow_parser.add_argument("--classification")
    agentissue_runner_flow_parser.add_argument("--recommended-action")
    agentissue_runner_flow_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview append without writing. This is the default.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--execute",
        action="store_true",
        help="Append the selected compact runner-flow event.",
    )
    agentissue_runner_flow_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Skip global registry sync after append.",
    )

    benchmark_artifact_filter_parser = benchmark_sub.add_parser(
        "classify-artifacts",
        help=(
            "Classify benchmark artifact paths before reading them. The classifier "
            "returns basenames and blocker reasons only; it does not read files or "
            "echo host directories."
        ),
    )
    add_subcommand_format(benchmark_artifact_filter_parser)
    benchmark_artifact_filter_parser.add_argument(
        "artifact_paths",
        nargs="+",
        help="Candidate benchmark artifact paths to classify without reading.",
    )
    benchmark_artifact_filter_parser.add_argument(
        "--adapter-kind",
        default="default",
        help=(
            "Benchmark adapter artifact policy key. Unknown values fall back to "
            "default without recording paths."
        ),
    )
    benchmark_artifact_filter_parser.add_argument(
        "--allow-public-filename",
        action="append",
        default=[],
        help=(
            "Additional public compact basename to allow for this classification "
            "run. Only the basename is used and values are filtered."
        ),
    )

    benchmark_candidate_source_parser = benchmark_sub.add_parser(
        "candidate-source-boundary",
        help=(
            "Classify candidate-selection source paths before using them. This "
            "does not read files or echo host paths; it blocks raw runner roots, "
            "trial directories, task bodies, trajectories, and Codex transcripts."
        ),
    )
    add_subcommand_format(benchmark_candidate_source_parser)
    benchmark_candidate_source_parser.add_argument(
        "source_paths",
        nargs="+",
        help="Candidate-selection source paths to classify without reading.",
    )
    benchmark_candidate_source_parser.add_argument(
        "--adapter-kind",
        default="default",
        help="Benchmark adapter artifact policy key for compact artifact allowlists.",
    )
    benchmark_candidate_source_parser.add_argument(
        "--allow-public-filename",
        action="append",
        default=[],
        help=(
            "Additional compact/public basename to allow for this classification "
            "run. Only the basename is used and values are filtered."
        ),
    )
    benchmark_candidate_source_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero if any source is blocked.",
    )

    split_control_execution_parser = benchmark_sub.add_parser(
        "split-control-execution-seam",
        help=(
            "Build the public-safe execution seam from split-control readiness "
            "and command-adapter facts. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(split_control_execution_parser)
    split_control_execution_parser.add_argument(
        "--readiness-json",
        required=True,
        help=(
            "Path to a benchmark_split_control_remote_executor_readiness_v0 "
            "object. Use '-' to read stdin."
        ),
    )
    split_control_execution_parser.add_argument(
        "--command-adapter-json",
        help=(
            "Optional JSON object keyed by benchmark id with "
            "command_adapter_ready/result_reducer_ready facts. If omitted, "
            "all launch cases are treated as missing command adapters."
        ),
    )
    split_control_execution_parser.add_argument(
        "--execution-mode",
        default="compact_no_upload_dry_run",
        help="Public-safe execution mode label for runner cases.",
    )

    terminal_bench_command_adapter_parser = benchmark_sub.add_parser(
        "terminal-bench-command-adapter",
        help=(
            "Emit Terminal-Bench command-adapter facts for the split-control "
            "execution seam. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_command_adapter_parser)
    terminal_bench_command_adapter_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--launch-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing launch surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--poll-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact poll surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--resume-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing no-upload resume surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--compact-ingest-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact Harbor result ingest surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--result-reducer-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact result reducer.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--remote-materializer-ready",
        action="store_true",
        help=(
            "Declare that a real remote-executor materializer exists for the "
            "adapter labels. Omit until the runner can actually stage and poll "
            "remote Docker/runner/data handles."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help=(
            "Declare that the local Codex driver owns agent/model/auth/state "
            "for the Terminal-Bench case."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--remote-sandbox-ready",
        action="store_true",
        help=(
            "Declare that the remote executor is only a sandbox for "
            "Docker/runner/data execution and compact artifact return."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--surface-blocker",
        action="append",
        default=[],
        help="Public-safe adapter blocker label. Repeat as needed.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the adapter facts are ready.",
    )

    terminal_bench_remote_materializer_parser = benchmark_sub.add_parser(
        "terminal-bench-remote-materializer",
        help=(
            "Reduce private Terminal-Bench remote-executor handles to a "
            "public-safe materializer payload. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_remote_materializer_parser)
    terminal_bench_remote_materializer_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--handle-manifest-json",
        help=(
            "Path to a private JSON object with remote-executor handle fields. "
            "Only field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--handle-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture field name to mark present without reading a "
            "private manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--no-upload-disabled",
        action="store_true",
        help="Fixture flag proving upload-enabled runs are blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help=(
            "Declare that a local Codex driver can control the case while the "
            "remote executor owns only Docker/runner/data work."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-agent-runtime-required",
        action="store_true",
        help="Fixture flag proving remote agent-runtime execution is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-codex-runtime-required",
        action="store_true",
        help="Fixture flag proving remote Codex-runtime execution is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--local-codex-credential-sync",
        action="store_true",
        help="Fixture flag proving Codex credential sync to remote is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-model-invocation",
        action="store_true",
        help="Fixture flag proving remote model invocation is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--raw-material-allowed",
        action="store_true",
        help="Fixture flag proving raw task/log/trajectory exposure is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the materializer payload is ready.",
    )

    terminal_bench_remote_launch_adapter_parser = benchmark_sub.add_parser(
        "terminal-bench-remote-launch-adapter",
        help=(
            "Reduce a local-driver request plus private remote launch result "
            "to public-safe Terminal-Bench launch-adapter facts. This does "
            "not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_remote_launch_adapter_parser)
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--request-json",
        help=(
            "Path to a private local-driver request JSON object. Only required "
            "field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--request-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture request field name to mark present without "
            "reading a private request manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--launch-result-json",
        help=(
            "Path to a private remote launch result JSON object. Only required "
            "handle field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--launch-result-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture launch-result field name to mark present "
            "without reading a private result manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help="Declare that the local Codex driver owns auth/model/state.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-sandbox-ready",
        action="store_true",
        help=(
            "Declare that the remote executor is only a Docker/runner/data "
            "sandbox and can return compact launch results."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--no-upload-disabled",
        action="store_true",
        help="Fixture flag proving upload-enabled runs are blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--local-codex-credential-sync",
        action="store_true",
        help="Fixture flag proving Codex credential sync to remote is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-agent-runtime-required",
        action="store_true",
        help="Fixture flag proving remote agent-runtime execution is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-codex-runtime-required",
        action="store_true",
        help="Fixture flag proving remote Codex-runtime execution is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-model-invocation",
        action="store_true",
        help="Fixture flag proving remote model invocation is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--raw-material-allowed",
        action="store_true",
        help="Fixture flag proving raw task/log/trajectory exposure is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the launch adapter is ready.",
    )

    ale_local_preflight_parser = benchmark_sub.add_parser(
        "ale-local-preflight",
        help=(
            "Check Agents' Last Exam local no-cloud/no-upload adapter readiness. "
            "This may inspect local Docker image metadata, but it does not start "
            "containers, read task bodies, call model APIs, upload, or claim "
            "leaderboard evidence."
        ),
    )
    add_subcommand_format(ale_local_preflight_parser)
    ale_local_preflight_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_preflight_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_preflight_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_preflight_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_preflight_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is preflight-ready.",
    )
    ale_local_preflight_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the local no-cloud/no-upload preflight is ready.",
    )
    ale_local_preflight_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked preflight. "
            "Used by dependency-free smokes."
        ),
    )

    ale_local_dry_run_plan_parser = benchmark_sub.add_parser(
        "ale-local-dry-run-plan",
        help=(
            "Build an Agents' Last Exam local adapter dry-run plan without "
            "running the adapter. This contract-only gate may inspect local "
            "Docker image metadata, but it does not start containers, read task "
            "bodies, invoke model APIs, upload, or claim score evidence."
        ),
    )
    add_subcommand_format(ale_local_dry_run_plan_parser)
    ale_local_dry_run_plan_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is dry-run-plan-ready.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the contract-only dry-run plan is ready.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked plan. "
            "Used by dependency-free smokes."
        ),
    )

    ale_local_runner_readiness_parser = benchmark_sub.add_parser(
        "ale-local-runner-readiness",
        help=(
            "Check whether a real Agents' Last Exam local dry-run runner is "
            "explicitly configured. This may inspect local Docker image metadata "
            "and PATH availability for a runner binary, but it does not start "
            "containers, read task bodies, invoke model APIs, upload, or submit."
        ),
    )
    add_subcommand_format(ale_local_runner_readiness_parser)
    ale_local_runner_readiness_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is runner-ready.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-binary",
        help=(
            "PATH-visible runner binary name to probe. Absolute or relative paths "
            "are rejected so local paths are not recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-python-module",
        help=(
            "Optional Python module to probe when the runner command is "
            "`python -m <module>`. The module path is never recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-source-root",
        help=(
            "Optional local source checkout root to add only for module probing. "
            "The local path is never recorded in output."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-command-label",
        help=(
            "Public-safe label for the configured runner command. The command "
            "argv itself is never recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Mark that the operator authorized local container start for dry-run.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--allow-public-task-material",
        action="store_true",
        help="Mark that public ALE task material may be touched by a later dry-run.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the local runner readiness gate is ready.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked readiness payload. "
            "Used by dependency-free smokes."
        ),
    )

    ale_local_source_readiness_parser = benchmark_sub.add_parser(
        "ale-local-source-readiness",
        help=(
            "Check whether a local Agents' Last Exam source checkout can be used "
            "as a redacted public runner source lock. This reads git metadata and "
            "module availability only; it does not start containers, read task "
            "bodies, invoke model APIs, upload, or submit."
        ),
    )
    add_subcommand_format(ale_local_source_readiness_parser)
    ale_local_source_readiness_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--expected-repo-url",
        default="https://github.com/rdi-berkeley/agents-last-exam.git",
        help="Expected public ALE repository URL.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--runner-python-module",
        default="ale_run",
        help="Python module expected to provide the ALE runner CLI.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--fetch-origin",
        action="store_true",
        help=(
            "Run git fetch --prune origin before checking freshness. The command "
            "argv, local path, and raw git output are never recorded."
        ),
    )
    ale_local_source_readiness_parser.add_argument(
        "--require-upstream-current",
        action="store_true",
        help="Require HEAD to match the configured upstream ref before returning ready.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the source readiness gate is ready.",
    )

    ale_task_material_readiness_parser = benchmark_sub.add_parser(
        "ale-task-material-readiness",
        help=(
            "Check whether a selected public ALE task has local material signals "
            "needed for a future local/no-upload run. This checks directory, "
            "task_card.json, scripts, scorer scripts, and public selected-task "
            "list membership only; it does not read task card content, task "
            "bodies, scripts, trajectories, screenshots, credentials, upload, or submit."
        ),
    )
    add_subcommand_format(ale_task_material_readiness_parser)
    ale_task_material_readiness_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to check, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--requires-task-data",
        choices=("true", "false", "unknown"),
        help=(
            "Optional compact task-data requirement signal. Use unknown with "
            "--enforce-task-data-source to fail closed before a formal task run."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--task-data-source",
        help=(
            "Compact task_data_source label such as baked_in_sandbox or "
            "gs://ale-data-public. Credential values and paths are never recorded."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--baked-task-input-present",
        action="store_true",
        help="Mark that the selected task's baked sandbox input directory was verified present.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--baked-task-input-readiness-json",
        help=(
            "Compact ale-baked-task-input-readiness JSON artifact to consume "
            "instead of relying on a manual baked-input boolean."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--gcs-sa-key",
        help="Service-account key path to check for existence only; the path/value is never recorded.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--gcs-sa-key-present",
        action="store_true",
        help="Fixture/operator assertion that the service-account key file presence was verified.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--enforce-task-data-source",
        action="store_true",
        help="Require task-data source readiness before returning ready.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the task material readiness gate is ready.",
    )

    ale_baked_task_input_readiness_parser = benchmark_sub.add_parser(
        "ale-baked-task-input-readiness",
        help=(
            "Probe whether a local ALE Docker image contains a selected task's "
            "baked input directory. This may start a tiny shell in Docker, but "
            "it does not run the task, list files, read task data, invoke models, "
            "upload, submit, or record local/container paths."
        ),
    )
    add_subcommand_format(ale_baked_task_input_readiness_parser)
    ale_baked_task_input_readiness_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Local ALE Docker image ref to probe.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="PATH-visible Docker binary name to use.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for the tiny Docker path-existence probe.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--no-docker-run",
        action="store_true",
        help="Do not start Docker; emit a fixture-like blocked readiness payload.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the baked task input readiness gate is ready.",
    )

    ale_baked_task_input_scan_parser = benchmark_sub.add_parser(
        "ale-baked-task-input-scan",
        help=(
            "Batch-scan public ALE selected tasks for baked input directories in "
            "a local Docker image. This may start one tiny shell in Docker, but "
            "does not run tasks, list files, read task data, invoke models, "
            "upload, submit, or record local/container paths."
        ),
    )
    add_subcommand_format(ale_baked_task_input_scan_parser)
    ale_baked_task_input_scan_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to read selected-task lists from. The path is never recorded.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to scan, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Local ALE Docker image ref to probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="PATH-visible Docker binary name to use.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--max-tasks",
        type=int,
        default=120,
        help="Maximum selected public task ids to probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Timeout for the batch Docker path-existence probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--no-docker-run",
        action="store_true",
        help="Do not start Docker; emit a fixture-like blocked scan payload.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless at least one baked-input candidate is found.",
    )

    ale_candidate_task_data_scan_parser = benchmark_sub.add_parser(
        "ale-candidate-task-data-scan",
        help=(
            "Scan public ALE selected-task lists for tasks with an explicit "
            "REQUIRES_TASK_DATA=False config signal. The scan records only "
            "counts and public task ids; it does not record task source text, "
            "task cards, instructions, scripts, trajectories, screenshots, "
            "credentials, uploads, or submits."
        ),
    )
    add_subcommand_format(ale_candidate_task_data_scan_parser)
    ale_candidate_task_data_scan_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to scan, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--allow-demo-candidate",
        action="store_true",
        help="Allow demo/* no-task-data tasks to satisfy readiness.",
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless at least one eligible no-task-data candidate is found.",
    )

    ale_local_launch_packet_parser = benchmark_sub.add_parser(
        "ale-local-launch-packet",
        help=(
            "Build a no-execution Agents' Last Exam local dry-run launch packet. "
            "This combines source, runner, Docker preflight, and experiment-spec "
            "existence gates without starting containers, reading task bodies, "
            "invoking model APIs, uploading, or submitting."
        ),
    )
    add_subcommand_format(ale_local_launch_packet_parser)
    ale_local_launch_packet_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec",
        required=True,
        help=(
            "Public relative path to the ALE experiment spec under source root "
            "or --experiment-spec-root."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec-root",
        help=(
            "Optional external spec root for Goal Harness wrapper specs. The "
            "path is probed for existence only and never recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--expected-repo-url",
        default="https://github.com/rdi-berkeley/agents-last-exam.git",
        help="Expected public ALE repository URL.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-binary",
        default="python3",
        help="PATH-visible runner binary name to probe.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-python-module",
        default="ale_run",
        help="Python module expected to provide the ALE runner CLI.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-command-label",
        default="python-m-ale-run",
        help="Public-safe label for the configured runner command.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Mark that the operator authorized local container start for dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--allow-public-task-material",
        action="store_true",
        help="Mark that public ALE task material may be touched by a later dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--fetch-origin",
        action="store_true",
        help=(
            "Run git fetch --prune origin before launch-packet source freshness "
            "checks. No raw git output, command argv, or local paths are recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-upstream-current",
        action="store_true",
        help="Require the ALE checkout HEAD to match upstream before the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help="Do not call Docker; emit a fixture-like blocked launch packet.",
    )

    ale_local_exact_dry_run_result_parser = benchmark_sub.add_parser(
        "ale-local-exact-dry-run-result",
        help=(
            "Reduce ALE `run --dry-run` stdout into a compact public-safe result. "
            "This reads only the provided dry-run stdout file and records labels "
            "and counts, never raw stdout, task text, paths, trajectories, "
            "screenshots, credentials, uploads, or command argv."
        ),
    )
    add_subcommand_format(ale_local_exact_dry_run_result_parser)
    ale_local_exact_dry_run_result_parser.add_argument(
        "--stdout-file",
        required=True,
        help=(
            "File containing ALE dry-run stdout to reduce. The path and raw text "
            "are not recorded."
        ),
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--exit-code",
        required=True,
        help="Exit code from the ALE dry-run command.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-task-id",
        help="Optional public task id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-agent-id",
        help="Optional public agent id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the compact dry-run result is ready.",
    )

    ale_host_codex_cli_route_parser = benchmark_sub.add_parser(
        "ale-host-codex-cli-route",
        help=(
            "Check the host Codex CLI auth route for a future Agents' Last Exam "
            "run. This verifies only compact host-side readiness signals and "
            "does not read credential values, copy auth into the sandbox, start "
            "containers, read task bodies, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cli_route_parser)
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free smokes; records no binary path.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text. If omitted, the command "
            "runs `<codex-binary> --version` without recording argv or paths."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help=(
            "Mark that host Codex auth cache existence was verified. The value "
            "is not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help=(
            "Mark that host Codex config existence was verified. The content is "
            "not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--cua-mcp-assets-root",
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke is already ready.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the host Codex CLI route gate is ready.",
    )

    ale_host_codex_cua_no_task_e2e_parser = benchmark_sub.add_parser(
        "ale-host-codex-cua-no-task-e2e",
        help=(
            "Build compact no-task evidence that host Codex CLI help, Codex MCP "
            "config loading, and the CUA MCP bridge are ready. This does not "
            "send a Codex prompt, invoke a model API, read task bodies, record "
            "raw output, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cua_no_task_e2e_parser)
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free route-gate smokes; records no binary path.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text for the route gate. If "
            "omitted, the command runs `<codex-binary> --version` without "
            "recording argv or paths."
        ),
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help="Mark that host Codex auth cache existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help="Mark that host Codex config existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-mcp-assets-root",
        required=True,
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-server-url",
        default="http://127.0.0.1:8000",
        help="Local CUA server URL used only inside a temporary Codex MCP config.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--install-node-deps",
        action="store_true",
        help="Allow npm install in a temporary copy of the CUA MCP assets if node_modules is absent.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke/e2e prerequisite is already ready.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the no-task host Codex CUA E2E gate is ready.",
    )

    ale_validation_run_gate_parser = benchmark_sub.add_parser(
        "ale-validation-run-gate",
        help=(
            "Combine compact ALE readiness artifacts into a pre-run decision "
            "for one local/no-upload validation run. This reads only compact "
            "JSON gates and does not start containers, send Codex prompts, "
            "read raw trajectories, upload, submit, or record local paths."
        ),
    )
    add_subcommand_format(ale_validation_run_gate_parser)
    ale_validation_run_gate_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--validation-hypothesis",
        required=True,
        help="Public-safe hypothesis for why this run can improve Goal Harness validation.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--task-material-readiness-json",
        required=True,
        help="Compact ale-task-material-readiness JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--host-codex-no-task-e2e-json",
        required=True,
        help="Compact ale-host-codex-cua-no-task-e2e JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--exact-dry-run-json",
        required=True,
        help="Compact ale-local-exact-dry-run-result JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--launch-packet-json",
        help="Optional compact ale-local-launch-packet JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--result-reducer-ready",
        action="store_true",
        help="Mark that the compact ALE result reducer is ready for post-run ingest.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--formal-score-candidate",
        action="store_true",
        help="Mark that the next run is intended as a formal score candidate.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-fresh-source",
        action="store_true",
        help=(
            "Require the launch packet to prove fetch-origin and upstream-current "
            "source freshness. Formal score candidates imply this requirement."
        ),
    )
    ale_validation_run_gate_parser.add_argument(
        "--expected-formal-agent",
        default="host_codex_gpt55_xhigh",
        help="Public-safe expected formal scoring agent id.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks submit-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--leaderboard-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks leaderboard-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the validation-run gate is ready.",
    )

    benchmark_post_launch_parser = benchmark_sub.add_parser(
        "summarize-post-launch",
        help=(
            "Summarize whether a Terminal-Bench Harbor launch materialized a "
            "pollable job directory. This records booleans, counts, and job "
            "basenames only; it does not read logs, task text, trajectories, "
            "Docker, model APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_post_launch_parser)
    benchmark_post_launch_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family.",
    )
    benchmark_post_launch_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory to check. The value is used only for "
            "local filesystem probing and is not echoed in output."
        ),
    )
    benchmark_post_launch_parser.add_argument(
        "--job-name",
        help="Expected Harbor job directory basename.",
    )
    benchmark_post_launch_parser.add_argument(
        "--detached-process-state",
        choices=["unknown", "running", "ended"],
        default="unknown",
        help=(
            "Optional public-safe state of the detached worker process observed "
            "by an external handle. When ended and no compact result exists, the "
            "summary emits a compact failure marker instead of an open-ended "
            "polling blocker."
        ),
    )
    benchmark_post_launch_parser.add_argument(
        "--require-ready-for-launch-state",
        action="store_true",
        help=(
            "Return non-zero unless the job root and lock.json are present. "
            "Use this before declaring a private launch state durable."
        ),
    )
    benchmark_post_launch_parser.add_argument(
        "--reconcile-stale-active",
        action="store_true",
        help=(
            "When an externally ended worker still has a stale active Harbor "
            "job with no trial result, emit a compact failure marker instead "
            "of leaving the state as polling. This does not read logs, task "
            "text, trajectories, Docker, model APIs, or uploads."
        ),
    )

    benchmark_result_finalization_gate_parser = benchmark_sub.add_parser(
        "result-finalization-gate",
        help=(
            "Reduce compact Terminal-Bench post-launch evidence into a "
            "result-finalization repair and repaired-baseline rerun gate. "
            "This reads only compact JSON, not logs, task text, trajectories, "
            "Docker, model APIs, uploads, or local paths."
        ),
    )
    add_subcommand_format(benchmark_result_finalization_gate_parser)
    benchmark_result_finalization_gate_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family.",
    )
    benchmark_result_finalization_gate_parser.add_argument(
        "--post-launch-json",
        required=True,
        help=(
            "Path to compact terminal_bench_post_launch_materialization_v0 JSON. "
            "Use '-' to read stdin."
        ),
    )
    benchmark_result_finalization_gate_parser.add_argument(
        "--max-repaired-baseline-reruns",
        type=int,
        default=1,
        help="Maximum repaired baseline reruns this gate may authorize.",
    )
    benchmark_result_finalization_gate_parser.add_argument(
        "--require-rerun-allowed",
        action="store_true",
        help="Return non-zero unless the gate allows exactly one repaired baseline rerun.",
    )

    benchmark_baseline_gate_parser = benchmark_sub.add_parser(
        "baseline-failure-gate",
        help=(
            "Reduce a compact goal-mode baseline benchmark_result_v0 or benchmark_run_v0 into a "
            "benchmark_comparison_v0 baseline-failure gate. This reads only "
            "compact JSON, not raw task text, logs, traces, Harbor job "
            "directories, Docker, model APIs, uploads, screenshots, or credentials."
        ),
    )
    add_subcommand_format(benchmark_baseline_gate_parser)
    benchmark_baseline_gate_parser.add_argument(
        "--goal-id",
        help="Goal id for optional append context. Required with --execute.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--benchmark-id",
        required=True,
        help="Public-safe benchmark id for the comparison row.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--baseline-result-json",
        required=True,
        help=(
            "Path to a compact benchmark_result_v0 or benchmark_run_v0 JSON object. "
            "Use '-' to read stdin."
        ),
    )
    benchmark_baseline_gate_parser.add_argument(
        "--baseline-mode",
        default="codex_cli_goal_mode",
        help="Public-safe baseline mode label.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--treatment-scenario-id",
        default="codex_goal_harness",
        help="Public-safe treatment scenario id planned after the gate.",
    )
    benchmark_baseline_gate_parser.add_argument("--comparison-id")
    benchmark_baseline_gate_parser.add_argument("--failure-phase")
    benchmark_baseline_gate_parser.add_argument("--failure-class")
    benchmark_baseline_gate_parser.add_argument(
        "--failure-attribution-label",
        action="append",
        default=[],
        help="Public-safe failure attribution label. Repeat as needed.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--control-plane-addressable",
        action="store_true",
        help="Mark the baseline failure as plausibly fixable by Goal Harness control-plane intervention.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--same-task-semantics",
        action="store_true",
        help="Confirm treatment will use the same benchmark task semantics.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--same-runner-protocol",
        action="store_true",
        help="Confirm treatment will use the same runner protocol.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--trace-publicness-verified",
        action="store_true",
        help="Confirm the compact result excludes private raw trace material.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--baseline-attempt-count",
        type=int,
        default=1,
        help="Number of baseline attempts represented by this gate.",
    )
    benchmark_baseline_gate_parser.add_argument("--minimum-next-evidence")
    benchmark_baseline_gate_parser.add_argument("--negative-selection-reason")
    benchmark_baseline_gate_parser.add_argument("--next-action")
    benchmark_baseline_gate_parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="Public-safe compact evidence reference. Repeat as needed.",
    )
    benchmark_baseline_gate_parser.add_argument("--classification")
    benchmark_baseline_gate_parser.add_argument("--recommended-action")
    benchmark_baseline_gate_parser.add_argument(
        "--delivery-batch-scale",
        choices=DELIVERY_BATCH_SCALE_CHOICES,
        help="Optional delivery scale label for the run index.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--delivery-outcome",
        choices=DELIVERY_OUTCOME_CHOICES,
        help="Optional delivery outcome label for the run index.",
    )
    benchmark_baseline_gate_parser.add_argument("--dry-run", action="store_true", help="Preview without writing. This is the default.")
    benchmark_baseline_gate_parser.add_argument("--execute", action="store_true", help="Append the compact baseline gate comparison.")
    benchmark_baseline_gate_parser.add_argument("--no-global-sync", action="store_true", help="Skip global registry sync after append.")

    benchmark_claim_review_parser = benchmark_sub.add_parser(
        "review-claim",
        help=(
            "Review compact benchmark comparison/run JSON and classify claim strength. "
            "This reads only compact JSON inputs, not raw task text, logs, traces, "
            "Harbor job directories, Docker, model APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_claim_review_parser)
    benchmark_claim_review_parser.add_argument(
        "--benchmark-comparison-json",
        required=True,
        help="Path to a compact benchmark_comparison_v0 JSON object.",
    )
    benchmark_claim_review_parser.add_argument(
        "--benchmark-run-json",
        action="append",
        default=[],
        help=(
            "Path to a compact benchmark_run_v0 JSON object. Repeat for baseline "
            "and treatment compact run files."
        ),
    )

    benchmark_learning_ledger_parser = benchmark_sub.add_parser(
        "learning-ledger",
        help=(
            "Build a compact benchmark learning ledger row from comparison/run "
            "JSON. This turns paired outcomes into repair-vs-repeat guidance "
            "without opening raw task text, logs, traces, Harbor job directories, "
            "Docker, model APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_learning_ledger_parser)
    benchmark_learning_ledger_parser.add_argument(
        "--benchmark-comparison-json",
        required=True,
        help="Path to a compact benchmark_comparison_v0 JSON object.",
    )
    benchmark_learning_ledger_parser.add_argument(
        "--benchmark-run-json",
        action="append",
        default=[],
        help=(
            "Path to a compact benchmark_run_v0 JSON object. Repeat for baseline "
            "and treatment compact run files."
        ),
    )
    benchmark_learning_ledger_parser.add_argument(
        "--require-actionable-learning",
        action="store_true",
        help=(
            "Return non-zero unless the compact ledger contains an actionable "
            "Goal Harness learning signal, such as a repair candidate or clean "
            "score-recovery evidence."
        ),
    )

    benchmark_attempt_learning_gate_parser = benchmark_sub.add_parser(
        "attempt-learning-gate",
        help=(
            "Gate benchmark budget counting and follow-up routing on a durable "
            "compact learning ledger row. This reads only compact JSON, not raw "
            "task text, logs, traces, Harbor job directories, Docker, model APIs, "
            "uploads, screenshots, or credentials."
        ),
    )
    add_subcommand_format(benchmark_attempt_learning_gate_parser)
    benchmark_attempt_learning_gate_parser.add_argument(
        "--benchmark-run-json",
        required=True,
        help="Path to a compact benchmark_run_v0 JSON object.",
    )
    benchmark_attempt_learning_gate_parser.add_argument(
        "--benchmark-learning-ledger-json",
        help="Optional path to a compact benchmark_learning_ledger_v0 JSON object.",
    )
    benchmark_attempt_learning_gate_parser.add_argument(
        "--require-budget-count-allowed",
        action="store_true",
        help=(
            "Return non-zero unless the compact attempt has an actionable "
            "learning row and may be counted."
        ),
    )

    benchmark_adapter_kwarg_review_parser = benchmark_sub.add_parser(
        "review-adapter-kwargs",
        help=(
            "Review generated benchmark adapter kwargs and flag goal_harness_* "
            "keys that are not absorbed by the adapter contract. Values are not "
            "recorded. This does not start workers, Docker, model APIs, uploads, "
            "or read task material."
        ),
    )
    add_subcommand_format(benchmark_adapter_kwarg_review_parser)
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--adapter-label",
        default="benchmark-adapter",
        help="Public-safe adapter label.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--agent-kwarg",
        action="append",
        default=[],
        help="Generated agent kwarg in KEY=VALUE form. Repeat as needed.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--command-json",
        help=(
            "Optional JSON file containing a command argv list from which "
            "--agent-kwarg entries will be extracted. The path is not recorded."
        ),
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--accepted-goal-harness-kwarg",
        action="append",
        default=[],
        help=(
            "Goal Harness kwarg key explicitly consumed by the adapter. Repeat "
            "as needed unless --terminal-bench-managed-codex is used."
        ),
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--allowed-base-passthrough",
        action="append",
        default=[],
        help="Optional goal_harness_* kwarg key allowed to pass to the base constructor.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--terminal-bench-managed-codex",
        action="store_true",
        help="Use the built-in GoalHarnessManagedCodex accepted kwarg contract.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless all generated goal_harness_* kwargs are absorbed.",
    )

    benchmark_lifecycle_state_parser = benchmark_sub.add_parser(
        "lifecycle-state",
        help=(
            "Reduce compact benchmark preflight/launch/materialization/result/"
            "comparison/ledger JSON into an explicit lifecycle state without "
            "opening raw task text, logs, traces, job directories, Docker, model "
            "APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_lifecycle_state_parser)
    benchmark_lifecycle_state_parser.add_argument(
        "--preflight-json",
        help="Path to compact benchmark preflight JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--launch-json",
        help="Path to compact launch summary JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--post-launch-json",
        help="Path to compact post-launch materialization JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--benchmark-run-json",
        help="Path to compact benchmark_run_v0 JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--benchmark-comparison-json",
        help="Path to compact benchmark_comparison_v0 JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--claim-review-json",
        help="Path to compact benchmark_claim_review_v0 JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--benchmark-learning-ledger-json",
        help="Path to compact benchmark_learning_ledger_v0 JSON.",
    )
    benchmark_lifecycle_state_parser.add_argument(
        "--require-budget-count-allowed",
        action="store_true",
        help="Return non-zero unless the lifecycle state allows budget counting.",
    )

    benchmark_environment_setup_gate_parser = benchmark_sub.add_parser(
        "environment-setup-gate",
        help=(
            "Gate a Terminal-Bench same-task environment setup probe after a "
            "compact environment_setup failure. Reads compact JSON and optional "
            "Harbor help only; it does not start Docker, Codex, model APIs, "
            "uploads, or benchmark tasks."
        ),
    )
    add_subcommand_format(benchmark_environment_setup_gate_parser)
    benchmark_environment_setup_gate_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--dataset",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--include-task-name",
        default=TERMINAL_BENCH_DEFAULT_TASK,
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--preflight-json",
        help="Path to compact preflight or benchmark-run append JSON.",
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--benchmark-run-json",
        required=True,
        help="Path to the compact benchmark_run_v0 with the prior environment_setup failure.",
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--probe-runner-help",
        action="store_true",
        help=(
            "Probe `harbor run --help` via uvx and store only compact capability "
            "booleans. This does not run Docker, Codex, model APIs, uploads, or tasks."
        ),
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--harbor-run-help-text",
        help=(
            "Fixture help text for deterministic tests. The raw text is consumed "
            "only to derive capability booleans and is not emitted."
        ),
    )
    benchmark_environment_setup_gate_parser.add_argument(
        "--require-probe-allowed",
        action="store_true",
        help="Return non-zero unless a no-upload environment setup probe route is allowed.",
    )

    benchmark_environment_setup_probe_launch_parser = benchmark_sub.add_parser(
        "launch-environment-setup-probe",
        help=(
            "Launch a gated Terminal-Bench no-upload NOP/disable-verification "
            "environment setup probe and emit only compact process/materialization "
            "signals. Stdout/stderr stay in a private log and are not read."
        ),
    )
    add_subcommand_format(benchmark_environment_setup_probe_launch_parser)
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "--gate-json",
        required=True,
        help="Path to terminal_bench_environment_setup_probe_gate_v0 JSON.",
    )
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "--run-root",
        required=True,
        help=(
            "Private run root for launcher artifacts. The value is used locally "
            "and only its basename is emitted."
        ),
    )
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory. The value is used locally and is not "
            "echoed in output."
        ),
    )
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="Seconds to wait for an immediate launcher exit before returning running state.",
    )
    benchmark_environment_setup_probe_launch_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually start the local no-upload setup probe. Without this flag, dry-run only.",
    )

    benchmark_worker_materialization_probe_launch_parser = benchmark_sub.add_parser(
        "launch-worker-materialization-probe",
        help=(
            "Launch a Terminal-Bench no-upload Codex worker materialization "
            "probe that stops after Codex setup/preflight and emits compact "
            "process/materialization signals. Stdout/stderr stay in a private "
            "log and are not read."
        ),
    )
    add_subcommand_format(benchmark_worker_materialization_probe_launch_parser)
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--mode",
        choices=["codex-goal-mode", "hardened-codex"],
        default="codex-goal-mode",
        help="Baseline worker surface to materialize without solving the task.",
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--dataset",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--include-task-name",
        default=TERMINAL_BENCH_DEFAULT_TASK,
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--model",
        default=TERMINAL_BENCH_DEFAULT_MODEL,
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--job-name",
        help="Optional public-safe Harbor job basename.",
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--worker-codex-materialization-strategy",
        choices=TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
        default=TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
        help=(
            "Worker Codex materialization route to probe before task solving. "
            "Defaults to the fail-fast worker PATH probe."
        ),
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--run-root",
        required=True,
        help=(
            "Private run root for launcher artifacts. The value is used locally "
            "and only its basename is emitted."
        ),
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory. The value is used locally and is not "
            "echoed in output."
        ),
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="Seconds to wait for an immediate launcher exit before returning running state.",
    )
    benchmark_worker_materialization_probe_launch_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually start the local no-upload worker materialization probe. "
            "Without this flag, dry-run only."
        ),
    )

    benchmark_case_run_launch_parser = benchmark_sub.add_parser(
        "launch-terminal-bench-run",
        help=(
            "Launch one Terminal-Bench no-upload case run with compact "
            "process/materialization reporting. Stdout/stderr stay in a "
            "private log and are not read."
        ),
    )
    add_subcommand_format(benchmark_case_run_launch_parser)
    benchmark_case_run_launch_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_case_run_launch_parser.add_argument(
        "--mode",
        choices=[
            "codex-goal-mode",
            "codex-app-server-goal",
            "hardened-codex",
            "codex-goal-harness",
            "goal-harness-managed-codex",
        ],
        default="codex-goal-mode",
        help="Terminal-Bench worker surface to run.",
    )
    benchmark_case_run_launch_parser.add_argument(
        "--dataset",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--include-task-name",
        default=TERMINAL_BENCH_DEFAULT_TASK,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--model",
        default=TERMINAL_BENCH_DEFAULT_MODEL,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--job-name",
        help="Optional public-safe Harbor job basename.",
    )
    benchmark_case_run_launch_parser.add_argument(
        "--run-root",
        required=True,
        help=(
            "Private run root for launcher artifacts. The value is used locally "
            "and only its basename is emitted."
        ),
    )
    benchmark_case_run_launch_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory. The value is used locally and is not "
            "echoed in output."
        ),
    )
    benchmark_case_run_launch_parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="Seconds to wait for an immediate launcher exit before returning running state.",
    )
    benchmark_case_run_launch_parser.add_argument(
        "--materialization-wait-seconds",
        type=int,
        default=0,
        help=(
            "Seconds to wait for the Harbor job root or a compact startup "
            "failure marker after launching. This observes only process state "
            "and compact job materialization signals."
        ),
    )
    benchmark_case_run_launch_parser.add_argument(
        "--resume-after-materialization",
        action="store_true",
        help=(
            "If the launch driver exits after a Harbor job materializes with "
            "active pending/running trials but no trial result, run one "
            "no-upload `harbor job resume` driver and report compact state."
        ),
    )
    benchmark_case_run_launch_parser.add_argument("--timeout-multiplier", type=float)
    benchmark_case_run_launch_parser.add_argument("--agent-timeout-multiplier", type=float)
    benchmark_case_run_launch_parser.add_argument("--verifier-timeout-multiplier", type=float)
    benchmark_case_run_launch_parser.add_argument("--agent-setup-timeout-multiplier", type=float)
    benchmark_case_run_launch_parser.add_argument(
        "--environment-build-timeout-multiplier",
        type=float,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--codex-install-strategy",
        choices=TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
        default=TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--codex-preflight-timeout-sec",
        type=int,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--worker-codex-materialization-strategy",
        choices=TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    )
    benchmark_case_run_launch_parser.add_argument(
        "--setup-timeout-repair-profile",
        action="store_true",
        help=(
            "Apply the generic setup-timeout repair launch profile before "
            "starting the case run."
        ),
    )
    benchmark_case_run_launch_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually start the local no-upload Terminal-Bench case run. "
            "Without this flag, dry-run only."
        ),
    )

    benchmark_resume_terminal_bench_job_parser = benchmark_sub.add_parser(
        "resume-terminal-bench-job",
        help=(
            "Run one no-upload Harbor job resume for a materialized "
            "Terminal-Bench job and emit compact process/result-finalization "
            "state. Stdout/stderr stay private and are not read."
        ),
    )
    add_subcommand_format(benchmark_resume_terminal_bench_job_parser)
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "--run-root",
        required=True,
        help=(
            "Private run root for resume artifacts. The value is used locally "
            "and only its basename is emitted."
        ),
    )
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory. The value is used locally and is not "
            "echoed in output."
        ),
    )
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "--job-name",
        required=True,
        help="Public-safe Harbor job basename to resume.",
    )
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "--wait-seconds",
        type=int,
        default=120,
        help="Seconds to wait for the resume process before returning running state.",
    )
    benchmark_resume_terminal_bench_job_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually start the local no-upload Harbor resume. Without this "
            "flag, dry-run only."
        ),
    )

    benchmark_worker_materialization_probe_poll_parser = benchmark_sub.add_parser(
        "poll-worker-materialization-probe",
        help=(
            "Poll a Terminal-Bench worker materialization probe by private pid "
            "state plus compact Harbor materialization signals. This does not "
            "read stdout/stderr logs, task text, trajectories, argv, Docker, "
            "model APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_worker_materialization_probe_poll_parser)
    benchmark_worker_materialization_probe_poll_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    benchmark_worker_materialization_probe_poll_parser.add_argument(
        "--run-root",
        required=True,
        help=(
            "Private run root containing the probe pid file. The value is used "
            "locally and only its basename is emitted."
        ),
    )
    benchmark_worker_materialization_probe_poll_parser.add_argument(
        "--jobs-dir",
        required=True,
        help=(
            "Private Harbor jobs directory. The value is used locally and is not "
            "echoed in output."
        ),
    )
    benchmark_worker_materialization_probe_poll_parser.add_argument(
        "--job-name",
        required=True,
        help="Public-safe Harbor job basename to summarize.",
    )

    benchmark_verifier_attribution_parser = benchmark_sub.add_parser(
        "review-verifier-attribution",
        help=(
            "Review compact benchmark_run_v0 verifier attribution and decide "
            "whether a score-failure caveat is resolved without opening raw logs, "
            "task text, traces, Harbor job directories, Docker, model APIs, or uploads."
        ),
    )
    add_subcommand_format(benchmark_verifier_attribution_parser)
    benchmark_verifier_attribution_parser.add_argument(
        "--benchmark-run-json",
        action="append",
        required=True,
        help=(
            "Path to a compact benchmark_run_v0 JSON object. Repeat for baseline "
            "and treatment compact run files."
        ),
    )

    benchmark_runner_invariant_parser = benchmark_sub.add_parser(
        "review-runner-invariants",
        help=(
            "Review compact benchmark_run_v0 runner-owned boundary invariants "
            "before trusting worker writeback. This reads only compact JSON, not "
            "raw task text, logs, traces, Harbor job directories, Docker, model "
            "APIs, uploads, or screenshots."
        ),
    )
    add_subcommand_format(benchmark_runner_invariant_parser)
    benchmark_runner_invariant_parser.add_argument(
        "--benchmark-run-json",
        required=True,
        help="Path to a compact benchmark_run_v0 JSON object.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--runner-label",
        help="Public-safe runner label to include in the review payload.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-submit-eligible",
        choices=["true", "false"],
        default="false",
        help="Expected runner-owned submit_eligible value. Defaults to false.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-leaderboard-evidence",
        choices=["true", "false"],
        default="false",
        help="Expected runner-owned leaderboard_evidence value. Defaults to false.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-compact-only",
        choices=["true", "false"],
        default="true",
        help="Expected compact read boundary. Defaults to true.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-raw-artifacts-read",
        choices=["true", "false"],
        default="false",
        help="Expected raw artifact read boundary. Defaults to false.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-task-text-read",
        choices=["true", "false"],
        default="false",
        help="Expected task text read boundary. Defaults to false.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--expect-local-paths-recorded",
        choices=["true", "false"],
        default="false",
        help="Expected local path recording boundary. Defaults to false.",
    )
    benchmark_runner_invariant_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless all runner-owned invariant fields match.",
    )

    archive_runtime_parser = sub.add_parser(
        "archive-runtime",
        help="Move an obsolete runtime goal directory into the archive area. Defaults to dry-run.",
    )
    archive_runtime_parser.add_argument("--goal-id", required=True, help="Runtime goal id to archive.")
    archive_runtime_parser.add_argument(
        "--archive-root",
        help="Archive directory. Defaults to <runtime-root>/archived-goals.",
    )
    archive_runtime_parser.add_argument(
        "--allow-registered",
        action="store_true",
        help="Allow archiving a goal that is still present in the registry.",
    )
    archive_runtime_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move the runtime directory. Without this flag the command is a dry-run.",
    )

    sync_global_parser = sub.add_parser(
        "sync-global",
        help="Merge this project-local registry into the shared global registry.",
    )
    sync_global_parser.add_argument("--goal-id", help="Only sync one goal id from the source registry.")
    sync_global_parser.add_argument("--dry-run", action="store_true", help="Preview the global registry merge.")

    refresh_state_parser = sub.add_parser(
        "refresh-state",
        help="Append a read-only run from active goal state after state-only updates.",
    )
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

    read_only_map_parser = sub.add_parser(
        "read-only-map",
        help="Append a generic read-only project-map run for a connected project.",
    )
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

    reward_parser = sub.add_parser(
        "reward",
        help="Append a compact human reward overlay to a goal run index.",
    )
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
        "--state-file",
        help="Active goal state path for optional summary writeback. Defaults to the registry goal state_file.",
    )
    reward_parser.add_argument(
        "--write-active-state-summary",
        action="store_true",
        help="After a real append, also add the returned active_state_summary to the active state's Progress Ledger. With --dry-run, preview only.",
    )
    reward_parser.add_argument("--dry-run", action="store_true", help="Print the overlay without appending it.")

    gate_parser = sub.add_parser(
        "operator-gate",
        help="Record an operator gate decision such as read-only map opt-in.",
    )
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

    authority_parser = sub.add_parser(
        "register-authority-source",
        help="Register a redacted local authority/material source for a goal.",
    )
    authority_parser.add_argument("--goal-id", required=True, help="Goal id whose local registry should be updated.")
    authority_parser.add_argument("--source-id", required=True, help="Stable local source id.")
    authority_parser.add_argument(
        "--source-ref",
        help="Raw local source reference to hash and redact. The raw value is never stored.",
    )
    authority_parser.add_argument("--source-kind", required=True, help="Public-safe source kind, such as doc or repository.")
    authority_parser.add_argument("--role", required=True, help="Public-safe material role.")
    authority_parser.add_argument("--freshness", required=True, help="Public-safe freshness state.")
    authority_parser.add_argument("--owner-status", help="Optional public-safe owner/review status.")
    authority_parser.add_argument("--gate-status", help="Optional public-safe gate status.")
    authority_parser.add_argument(
        "--boundary",
        choices=sorted(AUTHORITY_SOURCE_BOUNDARIES),
        default="private_redacted",
        help="Public/private boundary for this source. Defaults to private_redacted.",
    )
    authority_parser.add_argument("--revision", help="Optional public-safe revision label.")
    authority_parser.add_argument("--conflict-rule", help="Optional public-safe conflict rule.")
    authority_parser.add_argument("--topic", help="Optional topic_authority key to map to this source id.")
    authority_parser.add_argument("--dry-run", action="store_true", help="Preview the registry update without writing.")
    authority_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the local source registry.",
    )

    doc_registry_authority_parser = sub.add_parser(
        "import-doc-registry-authority",
        help="Import a redacted DOC_REGISTRY summary as a local authority/material source.",
    )
    doc_registry_authority_parser.add_argument(
        "--goal-id", required=True, help="Goal id whose local registry should be updated."
    )
    doc_registry_authority_parser.add_argument("--source-id", required=True, help="Stable local source id.")
    doc_registry_authority_parser.add_argument(
        "--doc-registry-path",
        required=True,
        help="Local DOC_REGISTRY.yaml path to read. The raw path is hashed and not stored.",
    )
    doc_registry_authority_parser.add_argument(
        "--source-kind",
        default="doc_registry",
        help="Public-safe source kind. Defaults to doc_registry.",
    )
    doc_registry_authority_parser.add_argument(
        "--role",
        default="external_doc_authority_registry",
        help="Public-safe material role. Defaults to external_doc_authority_registry.",
    )
    doc_registry_authority_parser.add_argument(
        "--freshness",
        default="current",
        help="Public-safe freshness state. Defaults to current.",
    )
    doc_registry_authority_parser.add_argument("--owner-status", help="Optional public-safe owner/review status.")
    doc_registry_authority_parser.add_argument("--gate-status", help="Optional public-safe gate status.")
    doc_registry_authority_parser.add_argument(
        "--boundary",
        choices=sorted(AUTHORITY_SOURCE_BOUNDARIES),
        default="private_redacted",
        help="Public/private boundary for this source. Defaults to private_redacted.",
    )
    doc_registry_authority_parser.add_argument("--revision", help="Optional public-safe revision label.")
    doc_registry_authority_parser.add_argument("--conflict-rule", help="Optional public-safe conflict rule.")
    doc_registry_authority_parser.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Additional local topic_authority key to map to this source id. Repeatable.",
    )
    doc_registry_authority_parser.add_argument(
        "--import-topic-prefix",
        help="Prefix imported DOC_REGISTRY topic keys with this value before mapping them to the source id.",
    )
    doc_registry_authority_parser.add_argument(
        "--max-imported-topics",
        type=int,
        default=50,
        help="Maximum DOC_REGISTRY topics to map when --import-topic-prefix is set. Defaults to 50.",
    )
    doc_registry_authority_parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")
    doc_registry_authority_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Do not refresh the shared global registry after writing the local source registry.",
    )

    register_status_commands(sub, add_subcommand_format)
    register_dreaming_commands(sub, add_subcommand_format)

    todo_parser = sub.add_parser(
        "todo",
        help="Add a user or agent todo to a goal's active state.",
    )
    todo_parser.add_argument(
        "todo_command",
        nargs="?",
        choices=["add", "claim", "update", "complete", "supersede", "archive-completed"],
        default="add",
        help=(
            "Use add to append a checkbox todo, claim to soft-claim by registered "
            "agent id, update/complete/supersede to transition by todo_id, or "
            "archive-completed to move older completed todos into Completed Work Archive."
        ),
    )
    todo_parser.add_argument("--goal-id", required=True, help="Goal id whose active state should receive the todo.")
    todo_parser.add_argument("--role", choices=["user", "agent"], help="Todo owner. Required for add; optional todo_id search scope for lifecycle commands. Defaults to agent for archive-completed.")
    todo_parser.add_argument("--text", help="Todo text. Required for add; keep it short and public-safe enough for local status.")
    todo_parser.add_argument("--todo-id", help="Structured todo id from status/quota, such as todo_ab12cd34ef56.")
    todo_parser.add_argument("--status", choices=["open", "done", "blocked", "deferred"], help="For todo update, set the lifecycle status by todo_id.")
    todo_parser.add_argument("--note", help="Public-safe note to attach to a lifecycle transition.")
    todo_parser.add_argument("--evidence", help="Public-safe evidence pointer or short result for complete/update.")
    todo_parser.add_argument("--reason", help="Public-safe reason for blocked/deferred/supersede transitions.")
    todo_parser.add_argument(
        "--task-class",
        choices=["advancement_task", "continuous_monitor", "user_gate", "blocker"],
        help=(
            "For todo add/update, explicitly register the routing lane. Use "
            "advancement_task for executable delivery work; continuous_monitor, "
            "user_gate, and blocker are non-executable lanes."
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
        "--claimed-by",
        help=(
            "For todo add/claim/update/complete, soft-claim the todo for a registered "
            "public-safe agent id such as codex-main-control."
        ),
    )
    todo_parser.add_argument(
        "--clear-claim",
        action="store_true",
        help="For todo update, remove the soft claimed_by owner from the todo.",
    )
    todo_parser.add_argument("--next-agent-todo", help="For complete/supersede, atomically add or update the next agent todo.")
    todo_parser.add_argument("--next-user-todo", help="For complete/supersede, atomically add or update the next user todo.")
    todo_parser.add_argument(
        "--next-claimed-by",
        help=(
            "For complete with --next-agent-todo, soft-claim the successor todo for "
            "a registered agent. Side-agent review handoffs default this to primary_agent; "
            "self-merged side-agent continuations may claim their own successor."
        ),
    )
    todo_parser.add_argument(
        "--side-agent-self-merged",
        action="store_true",
        help=(
            "For todo complete by a side agent, explicitly record that a small validated "
            "side-agent change was self-merged; requires --evidence and bypasses the "
            "default primary review successor todo."
        ),
    )
    todo_parser.add_argument(
        "--next-task-class",
        choices=["advancement_task", "continuous_monitor", "user_gate", "blocker"],
        help="Task class for --next-agent-todo. Defaults to advancement_task.",
    )
    todo_parser.add_argument("--next-action-kind", help="Action kind for --next-agent-todo.")
    todo_parser.add_argument(
        "--max-active-done",
        type=int,
        default=12,
        help="For archive-completed, keep this many completed todos in the active section.",
    )
    todo_parser.add_argument("--project", help="Project root. Defaults to the registry goal repo.")
    todo_parser.add_argument("--state-file", help="Active goal state path. Defaults to the registry goal state_file.")
    todo_parser.add_argument("--dry-run", action="store_true", help="Preview the active-state edit without writing.")
    todo_parser.add_argument("--execute", action="store_true", help="For archive-completed, write the active-state edit.")

    quota_parser = sub.add_parser(
        "quota",
        help="Show agent-facing compute quota status or next-turn plan.",
    )
    quota_parser.add_argument(
        "quota_command",
        nargs="?",
        choices=["status", "plan", "should-run", "monitor-poll", "spend-slot", "void-slot"],
        default="status",
        help="Use status for all groups, plan for next-turn groups, should-run for one goal, monitor-poll for no-spend quiet poll evidence, spend-slot for accounting, or void-slot for a non-destructive accounting correction.",
    )
    quota_parser.add_argument("--goal-id", help="Goal id to check. Required for `quota should-run`, `quota monitor-poll`, `quota spend-slot`, and `quota void-slot`.")
    quota_parser.add_argument(
        "--agent-id",
        help="Registered agent id for `quota should-run`; suppresses identity-upgrade warnings for current prompts.",
    )
    quota_parser.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
        help=(
            "For `quota should-run` and `quota spend-slot`, declare a capability "
            "available in this current agent environment. Repeat for multiple "
            "capabilities; basic local shell/filesystem capabilities are assumed."
        ),
    )
    quota_parser.add_argument("--slots", type=int, default=1, help="Slots to account for `quota spend-slot`.")
    quota_parser.add_argument("--source", choices=["heartbeat", "controller", "adapter"], default="heartbeat", help="Source label for `quota spend-slot`.")
    quota_parser.add_argument("--void-generated-at", help="generated_at timestamp of the quota_slot_spent run to void.")
    quota_parser.add_argument("--reason-summary", help="Public-safe reason for `quota void-slot`.")
    quota_parser.add_argument("--dry-run", action="store_true", help="Keep quota accounting writes as preview-only. This is the default.")
    quota_parser.add_argument("--execute", action="store_true", help="Append the compact quota accounting runtime event for spend-slot or void-slot.")
    quota_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    quota_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    quota_parser.add_argument("--limit", type=int, default=5)

    serve_status_parser = sub.add_parser("serve-status", help="Serve live status JSON for the local dashboard.")
    serve_status_parser.add_argument("--host", default=DEFAULT_STATUS_HOST, help="Bind host. Defaults to localhost only.")
    serve_status_parser.add_argument("--port", type=int, default=DEFAULT_STATUS_PORT)
    serve_status_parser.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status JSON route.")
    serve_status_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the Goal Harness install root.",
    )
    serve_status_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    serve_status_parser.add_argument("--limit", type=int, default=5)
    serve_status_parser.add_argument(
        "--enable-reward-write-api",
        action="store_true",
        help="Enable POST /reward/append on loopback only so the dashboard can append human_reward overlays.",
    )
    serve_status_parser.add_argument(
        "--enable-control-plane-write-api",
        action="store_true",
        help="Enable POST /control-plane/configure-goal/apply on loopback only so the dashboard can write registry settings.",
    )
    serve_status_parser.add_argument(
        "--global-registry",
        action="store_true",
        help="Serve the shared global registry view even when invoked from a project directory.",
    )
    serve_status_parser.add_argument("--verbose", action="store_true", help="Print HTTP request logs.")

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {
            "bootstrap",
            "connect",
            "codex-cli-bootstrap-message",
            "codex-cli-bounded-visible-pilot-adapter",
            "codex-cli-exec-handoff",
            "codex-cli-local-driver-plan",
            "codex-cli-local-scheduler-exec",
            "codex-cli-local-scheduler-tick",
            "codex-cli-one-message-loop-pilot",
            "codex-cli-runtime-idle-detector",
            "codex-cli-session-probe",
            "codex-cli-visible-attach-acceptance",
            "codex-cli-visible-local-driver-pilot",
            "codex-cli-visible-driver-run",
            "codex-cli-visible-driver-plan",
            "codex-cli-visible-session-proof",
            "demo",
            "doctor",
            "new-project-prompt",
            "heartbeat-prompt",
            "sync-global",
        }
        and not user_supplied_registry(argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    if args.command in {"bootstrap", "connect"}:
        try:
            runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else None
            state_file = Path(args.state_file).expanduser() if args.state_file else None
            goal_doc = Path(args.goal_doc).expanduser() if args.goal_doc else None
            payload = bootstrap_project(
                project=Path(args.project),
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                objective=args.objective,
                domain=args.domain,
                role=args.role,
                parent_goal_id=args.parent_goal_id,
                state_file=state_file,
                goal_doc=goal_doc,
                adapter_kind=args.adapter_kind,
                adapter_status=args.adapter_status,
                next_probe=args.next_probe,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                write_scope=args.write_scope,
                claim_ttl_minutes=args.claim_ttl_minutes,
                execution_minimum_scale=args.execution_minimum_scale,
                execution_must_include=args.execution_must_include or None,
                execution_small_streak_threshold=args.execution_small_streak_threshold,
                execution_outcome_markers=args.execution_outcome_marker or None,
                execution_surface_only_hints=args.execution_surface_only_hint or None,
                execution_surface_streak_threshold=args.execution_surface_streak_threshold,
                execution_outcome_must_advance=args.execution_outcome_must_advance or None,
                onboarding_scan_enabled=not bool(args.no_onboarding_scan),
                accept_onboarding_agent_todos=bool(args.accept_onboarding_agent_todos),
                begin_autonomous_advance=bool(args.begin_autonomous_advance),
                onboarding_max_commits=args.onboarding_max_commits,
                onboarding_max_status_paths=args.onboarding_max_status_paths,
                onboarding_max_top_level_files=args.onboarding_max_top_level_files,
                force=args.force,
                dry_run=args.dry_run,
                sync_global=not bool(args.no_global_sync),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_bootstrap_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "new-project-prompt":
        return handle_new_project_prompt_command(args, print_payload)

    if args.command == "codex-cli-bootstrap-message":
        return handle_codex_cli_bootstrap_message_command(args, print_payload)

    if args.command == "codex-cli-tui-bootstrap-smoke-bundle":
        return handle_codex_cli_tui_bootstrap_smoke_bundle_command(args, print_payload)

    if args.command == "codex-cli-one-message-loop-pilot":
        return handle_codex_cli_one_message_loop_pilot_command(args, print_payload)

    if args.command == "codex-cli-visible-local-driver-pilot":
        return handle_codex_cli_visible_local_driver_pilot_command(args, print_payload)

    if args.command == "codex-cli-bounded-visible-pilot-adapter":
        return handle_codex_cli_bounded_visible_pilot_adapter_command(args, print_payload)

    if args.command == "codex-cli-visible-attach-acceptance":
        return handle_codex_cli_visible_attach_acceptance_command(args, print_payload)

    if args.command == "codex-cli-exec-handoff":
        return handle_codex_cli_exec_handoff_command(args, print_payload)

    if args.command == "codex-cli-session-probe":
        return handle_codex_cli_session_probe_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-plan":
        return handle_codex_cli_visible_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-local-driver-plan":
        return handle_codex_cli_local_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-run":
        return handle_codex_cli_visible_driver_run_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-tick":
        return handle_codex_cli_local_scheduler_tick_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-exec":
        return handle_codex_cli_local_scheduler_exec_command(args, print_payload)

    if args.command == "codex-cli-visible-session-proof":
        return handle_codex_cli_visible_session_proof_command(args, print_payload)

    if args.command == "codex-cli-runtime-idle-detector":
        return handle_codex_cli_runtime_idle_detector_command(args, print_payload)

    if args.command == "heartbeat-prompt":
        try:
            active_state, resolved_active_state, active_state_source = resolve_heartbeat_active_state(
                goal_id=args.goal_id,
                active_state_arg=args.active_state,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
                allow_global_goal_lookup_fallback=not user_supplied_registry(argv),
            )
            agent_registry_path = registry_path
            if active_state_source.startswith("registry:"):
                agent_registry_path = Path(active_state_source.removeprefix("registry:"))
            registered_agents = registered_agent_ids_from_registry(agent_registry_path, args.goal_id)
            primary_agent = primary_agent_id_from_registry(agent_registry_path, args.goal_id)
            effective_agent_id = None
            agent_profile = None
            if args.agent_id:
                effective_agent_id = require_registered_agent_id(
                    registry_path=agent_registry_path,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    field="agent_id",
                )
                agent_profile = agent_profile_from_registry(agent_registry_path, args.goal_id, effective_agent_id)
            payload = build_heartbeat_prompt(
                goal_id=args.goal_id,
                active_state=active_state,
                active_state_source=active_state_source,
                resolved_active_state=resolved_active_state,
                material_queue_rule=args.material_rule,
                permission_rule=args.permission_rule,
                compact=bool(args.compact),
                brief=bool(args.brief),
                thin=bool(args.thin),
                cli_bin=args.cli_bin,
                agent_id=effective_agent_id,
                agent_scopes=args.agent_scopes,
                agent_profile=agent_profile,
                registered_agents=registered_agents,
                primary_agent=primary_agent,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "goal_id": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, output_format(args), render_heartbeat_prompt_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "demo":
        return handle_demo_command(args, print_payload)

    if args.command == "doctor":
        return handle_doctor_command(args, print_payload)

    if args.command == "worker-bridge":
        if args.worker_bridge_command not in (
            "contract",
            "outcome",
            "benchmark-run",
            "active-user-contract",
            "active-user-codex-simulator-contract",
            "active-user-intervention",
            "active-user-simulator-output",
            "active-user-observe",
        ):
            payload = {
                "ok": False,
                "mode": "worker-bridge",
                "error": (
                    "worker-bridge requires a subcommand; use `contract`, "
                    "`outcome`, `benchmark-run`, `active-user-contract`, "
                    "`active-user-codex-simulator-contract`, "
                    "`active-user-intervention`, `active-user-simulator-output`, "
                    "or `active-user-observe`."
                ),
            }
            print_payload(payload, args.format, render_worker_bridge_install_contract_markdown)
            return 1
        try:
            if args.worker_bridge_command == "contract":
                payload = build_worker_bridge_install_contract(
                    project_root=args.project_root,
                    runtime_root=args.worker_bridge_runtime_root,
                    python_bin=args.python_bin,
                    module=args.module,
                    scan_path=args.scan_path,
                    benchmark_run_json=args.benchmark_run_json,
                    counter_trace_json=args.counter_trace_json,
                    classification=args.classification,
                )
            elif args.worker_bridge_command == "outcome":
                payload = build_worker_bridge_outcome(
                    worker_goal_harness_cli_call_total=args.worker_cli_call_total,
                    counter_trace_present=bool(args.counter_trace_present),
                    runner_return_completed=bool(args.runner_return_completed),
                    official_score_completed=bool(args.official_score_completed),
                    official_score_value=args.official_score_value,
                    interrupted=bool(args.interrupted),
                    interrupt_reason=args.interrupt_reason,
                    wall_time_seconds=args.wall_time_seconds,
                    wall_time_limit_seconds=args.wall_time_limit_seconds,
                    required_worker_goal_harness_cli_call_total_min=(
                        args.required_worker_cli_call_total_min
                    ),
                    side_effect_audit_passed=not bool(args.side_effect_audit_failed),
                )
            elif args.worker_bridge_command == "benchmark-run":
                payload = build_worker_bridge_benchmark_run(
                    source_runner=args.source_runner,
                    benchmark_id=args.benchmark_id,
                    job_name=args.job_name,
                    mode=args.worker_bridge_benchmark_mode,
                    worker_mode=args.worker_mode,
                    task_id=args.task_id,
                    trial_name=args.trial_name,
                    official_score_kind=args.official_score_kind,
                    worker_goal_harness_cli_call_total=args.worker_cli_call_total,
                    counter_trace_present=bool(args.counter_trace_present),
                    runner_return_completed=bool(args.runner_return_completed),
                    official_score_completed=bool(args.official_score_completed),
                    official_score_value=args.official_score_value,
                    interrupted=bool(args.interrupted),
                    interrupt_reason=args.interrupt_reason,
                    wall_time_seconds=args.wall_time_seconds,
                    wall_time_limit_seconds=args.wall_time_limit_seconds,
                    required_worker_goal_harness_cli_call_total_min=(
                        args.required_worker_cli_call_total_min
                    ),
                    side_effect_audit_passed=not bool(args.side_effect_audit_failed),
                )
            elif args.worker_bridge_command == "active-user-contract":
                payload = build_active_user_intervention_channel_contract(
                    project_root=args.project_root,
                    runtime_root=args.active_user_runtime_root,
                    python_bin=args.python_bin,
                    module=args.module,
                    feed_jsonl=args.feed_jsonl,
                    observation_json=args.observation_json,
                    benchmark_run_json=args.benchmark_run_json,
                    counter_trace_json=args.counter_trace_json,
                    classification=args.classification,
                    min_interval_seconds=args.min_interval_seconds,
                    max_interventions_per_task=args.max_interventions_per_task,
                )
            elif args.worker_bridge_command == "active-user-codex-simulator-contract":
                payload = build_active_user_codex_simulator_contract(
                    project_root=args.project_root,
                    python_bin=args.python_bin,
                    module=args.module,
                    codex_bin=args.codex_bin,
                    context_dir=args.context_dir,
                    prompt_json=args.prompt_json,
                    simulator_output_json=args.simulator_output_json,
                    simulator_output_schema_json=args.simulator_output_schema_json,
                    feed_jsonl=args.feed_jsonl,
                )
            elif args.worker_bridge_command == "active-user-intervention":
                payload = build_active_user_intervention(
                    seq=args.seq,
                    message=args.message,
                    trigger=args.trigger,
                    channel=args.channel,
                    created_after_worker_start=not bool(args.before_worker_start),
                )
                if args.jsonl:
                    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                    return 0
            elif args.worker_bridge_command == "active-user-simulator-output":
                if args.simulator_output_json == "-":
                    simulator_output = json.loads(sys.stdin.read())
                else:
                    simulator_output = json.loads(
                        Path(args.simulator_output_json).expanduser().read_text(
                            encoding="utf-8"
                        )
                    )
                payload = build_active_user_intervention_from_simulator_output(
                    seq=args.seq,
                    simulator_output=simulator_output,
                    created_after_worker_start=not bool(args.before_worker_start),
                )
                if args.jsonl:
                    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                    return 0
            else:
                payload = observe_active_user_intervention_feed(
                    args.feed_jsonl,
                    worker_start_seq=args.worker_start_seq,
                )
                if args.observation_json:
                    payload["observation_written"] = write_active_user_observation_file(
                        args.observation_json,
                        payload,
                    )
                if args.counter_trace_json:
                    payload["counter_trace_written"] = (
                        append_worker_bridge_counter_trace_row(
                            args.counter_trace_json,
                            command="active_user_observe",
                            ok=bool(payload.get("ok")),
                            goal_id=args.goal_id,
                            mode=args.bridge_mode,
                            classification=args.classification,
                            observed_after_worker_start=payload.get(
                                "observed_after_worker_start"
                            ),
                            worker_observation_proof=payload.get(
                                "worker_observation_proof"
                            ),
                        )
                    )
                if args.benchmark_run_json:
                    trace_rows = load_worker_bridge_counter_trace_file(
                        args.counter_trace_json
                    )
                    interaction_counters = (
                        build_worker_bridge_interaction_counters_from_trace(
                            trace_rows
                        )
                    )
                    checkpoint = build_worker_bridge_benchmark_run_from_counters(
                        interaction_counters,
                        counter_trace_present=bool(trace_rows),
                        source_runner="worker_bridge_active_user_observe",
                        benchmark_id="worker-bridge-active-user@v0",
                        job_name="goal_harness_active_user_observe_checkpoint",
                        mode=args.bridge_mode,
                        task_id=args.task_id,
                        trial_name=args.trial_name,
                    )
                    checkpoint["worker_bridge_checkpoint"] = {
                        "schema_version": "goal_harness_worker_bridge_checkpoint_v0",
                        "checkpoint_kind": "active_user_observe",
                        "interrupted": False,
                        "trace_row_count": len(trace_rows),
                        "raw_trace_recorded": False,
                        "raw_paths_recorded": False,
                    }
                    payload["benchmark_run_checkpoint_written"] = (
                        write_worker_bridge_benchmark_run_file(
                            args.benchmark_run_json,
                            checkpoint,
                        )
                    )
                    payload["benchmark_run_checkpoint_schema_version"] = (
                        checkpoint.get("schema_version")
                    )
        except Exception as exc:
            payload = {
                "ok": False,
                "mode": "worker-bridge",
                "error": str(exc),
            }
        print_payload(payload, output_format(args), render_worker_bridge_install_contract_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "promotion-gate":
        try:
            payload = build_promotion_gate(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "gate": "promotion_readiness",
                "gate_state": "error",
                "can_promote": False,
                "should_warn": True,
                "non_blocking": True,
                "error": str(exc),
                "recommended_action": "fix promotion readiness gate collection before promotion",
            }
        print_payload(payload, output_format(args), render_promotion_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "upgrade-plan":
        try:
            payload = build_upgrade_plan(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                installed_manifest=Path(args.installed_manifest).expanduser() if args.installed_manifest else None,
                cli_bin=args.cli_bin,
                modes=args.mode or None,
                goal_ids=args.goal_id or None,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "mode": "upgrade-plan",
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
                "summary": {
                    "managed_goal_count": 0,
                    "current_prompt_count": 0,
                    "stale_prompt_count": 0,
                    "unknown_prompt_count": 0,
                    "not_installed_prompt_count": 0,
                    "stage_deferred_goal_count": 0,
                    "ready_for_default_promotion": False,
                    "installed_manifest_available": False,
                    "installed_manifest_source": None,
                    "installed_manifest_entry_count": 0,
                    "installed_manifest_task_body_count": 0,
                    "installed_manifest_has_task_body": False,
                },
                "recommended_action": "fix upgrade-plan collection before default promotion",
            }
        print_payload(payload, output_format(args), render_upgrade_plan_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry":
        payload = inspect_registry(registry_path)
        print_payload(payload, args.format, render_registry_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "registry-boundary":
        boundary_path = Path(args.path).expanduser() if args.path else registry_path
        payload = inspect_registry_boundary(boundary_path)
        git = payload.get("git") if isinstance(payload.get("git"), dict) else {}
        if args.require_not_tracked and payload.get("ok") and git.get("tracked") and not payload.get(
            "github_push_allowed"
        ):
            payload = dict(payload)
            payload["ok"] = False
            payload.setdefault("risks", []).append("registry_tracked_but_not_push_allowed")
        if args.require_gitignored and payload.get("ok") and payload.get("should_be_gitignored"):
            if git.get("inside_worktree") and not git.get("ignored") and not git.get("tracked"):
                payload = dict(payload)
                payload["ok"] = False
                payload.setdefault("risks", []).append("registry_should_be_gitignored")
        print_payload(payload, args.format, render_registry_boundary_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "configure-goal":
        try:
            payload = configure_goal(
                registry_path=registry_path,
                goal_id=args.goal_id,
                quota_compute=args.quota_compute,
                quota_window_hours=args.quota_window_hours,
                self_repair_enabled=args.self_repair_enabled,
                self_repair_health=args.self_repair_health,
                self_repair_waiting_projection=args.self_repair_waiting_projection,
                orchestration_mode=args.orchestration_mode,
                spawn_allowed=args.spawn_allowed,
                max_children=args.max_children,
                allowed_domains=args.allowed_domain,
                clear_allowed_domains=bool(args.clear_allowed_domains),
                registered_agents=args.registered_agents,
                clear_registered_agents=bool(args.clear_registered_agents),
                primary_agent=args.primary_agent,
                clear_primary_agent=bool(args.clear_primary_agent),
                waiting_on=args.waiting_on,
                clear_waiting_on=bool(args.clear_waiting_on),
                boundary_authority_scopes=args.boundary_authority_scope,
                boundary_authority_source=args.boundary_authority_source,
                boundary_authority_decision_id=args.boundary_authority_decision_id,
                boundary_authority_recorded_at=args.boundary_authority_recorded_at,
                boundary_authority_expires_at=args.boundary_authority_expires_at,
                clear_boundary_authority=bool(args.clear_boundary_authority),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "execute": bool(args.execute),
                "registry": str(registry_path),
                "goal_id": args.goal_id,
                "changed": False,
                "written": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_configure_goal_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "benchmark":
        if args.benchmark_command == "agentissue-codex-runner-flow":
            classification = (
                args.classification
                or (
                    AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION
                    if args.private_runner_root
                    else (
                        AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION
                        if args.real_result_root
                        else (
                            AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION
                            if args.target_runner_handoff_root
                            else (
                                AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION
                                if args.run_gate_root
                                else (
                                    AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION
                                    if args.workflow_check_root
                                    else (
                                        AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION
                                        if args.first_run_handoff_root
                                        else (
                                            AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION
                                            if args.execution_gate_root
                                            else (
                                                AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION
                                                if args.synthetic_staging_root
                                                else AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "agentissue-codex-runner-flow accepts either --dry-run or --execute, not both"
                    )
                selected_roots = [
                    value
                    for value in (
                        args.synthetic_staging_root,
                        args.execution_gate_root,
                        args.first_run_handoff_root,
                        args.workflow_check_root,
                        args.run_gate_root,
                        args.target_runner_handoff_root,
                        args.real_result_root,
                        args.private_runner_root,
                    )
                    if value
                ]
                if len(selected_roots) > 1:
                    raise ValueError(
                        "agentissue-codex-runner-flow accepts at most one root option, not both: --synthetic-staging-root, --execution-gate-root, --first-run-handoff-root, --workflow-check-root, --run-gate-root, --target-runner-handoff-root, --real-result-root, or --private-runner-root"
                    )
                wrapper = build_agentissue_codex_cli_runner_wrapper(
                    selected_tag=args.tag,
                    codex_binary=args.codex_binary,
                    docker_binary=args.docker_binary,
                )
                synthetic_staging = None
                execution_gate = None
                first_run_handoff = None
                workflow_check = None
                run_gate = None
                target_handoff = None
                real_result = None
                private_runner_script = None
                benchmark_run_source = wrapper["benchmark_run"]
                if args.private_runner_root:
                    private_runner_script = (
                        materialize_agentissue_codex_cli_runner_private_script(
                            args.private_runner_root,
                            selected_tag=args.tag,
                            codex_binary=args.codex_binary,
                            docker_binary=args.docker_binary,
                        )
                    )
                    benchmark_run_source = private_runner_script["benchmark_run"]
                elif args.real_result_root:
                    real_result = materialize_agentissue_codex_cli_runner_real_result(
                        args.real_result_root,
                        selected_tag=args.tag,
                    )
                    benchmark_run_source = real_result["benchmark_run"]
                elif args.target_runner_handoff_root:
                    target_handoff = materialize_agentissue_codex_cli_runner_target_handoff(
                        args.target_runner_handoff_root,
                        selected_tag=args.tag,
                        codex_binary=args.codex_binary,
                        docker_binary=args.docker_binary,
                    )
                    benchmark_run_source = target_handoff["benchmark_run"]
                elif args.run_gate_root:
                    run_gate = materialize_agentissue_codex_cli_runner_run_gate(
                        args.run_gate_root,
                        selected_tag=args.tag,
                        codex_binary=args.codex_binary,
                        docker_binary=args.docker_binary,
                    )
                    benchmark_run_source = run_gate["benchmark_run"]
                elif args.workflow_check_root:
                    workflow_check = materialize_agentissue_codex_cli_runner_workflow_check(
                        args.workflow_check_root,
                        selected_tag=args.tag,
                        codex_binary=args.codex_binary,
                        docker_binary=args.docker_binary,
                    )
                    benchmark_run_source = workflow_check["benchmark_run"]
                elif args.first_run_handoff_root:
                    first_run_handoff = (
                        materialize_agentissue_codex_cli_runner_first_run_handoff(
                            args.first_run_handoff_root,
                            selected_tag=args.tag,
                            codex_binary=args.codex_binary,
                            docker_binary=args.docker_binary,
                        )
                    )
                    benchmark_run_source = first_run_handoff["benchmark_run"]
                elif args.execution_gate_root:
                    execution_gate = materialize_agentissue_codex_cli_runner_execution_gate(
                        args.execution_gate_root,
                        selected_tag=args.tag,
                        codex_binary=args.codex_binary,
                        docker_binary=args.docker_binary,
                    )
                    benchmark_run_source = execution_gate["benchmark_run"]
                elif args.synthetic_staging_root:
                    synthetic_staging = (
                        materialize_agentissue_codex_cli_runner_synthetic_staging(
                            args.synthetic_staging_root,
                            selected_tag=args.tag,
                            codex_binary=args.codex_binary,
                            docker_binary=args.docker_binary,
                        )
                    )
                    benchmark_run_source = synthetic_staging["benchmark_run"]
                benchmark_run = compact_benchmark_run(benchmark_run_source)
                if not benchmark_run:
                    raise ValueError(
                        "agentissue Codex runner wrapper did not produce a compactable benchmark_run_v0"
                    )
                dry_run = not bool(args.execute)
                payload = append_benchmark_run(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_run=benchmark_run,
                    classification=classification,
                    recommended_action=args.recommended_action
                    or (
                        private_runner_script["recommended_next_action"]
                        if private_runner_script
                        else (
                            real_result["recommended_next_action"]
                            if real_result
                            else (
                                target_handoff["recommended_next_action"]
                                if target_handoff
                                else (
                                    run_gate["recommended_next_action"]
                                    if run_gate
                                    else (
                                        workflow_check["recommended_next_action"]
                                        if workflow_check
                                        else (
                                            first_run_handoff["recommended_next_action"]
                                            if first_run_handoff
                                            else (
                                                execution_gate["recommended_next_action"]
                                                if execution_gate
                                                else (
                                                    synthetic_staging[
                                                        "recommended_next_action"
                                                    ]
                                                    if synthetic_staging
                                                    else wrapper["recommended_next_action"]
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    ),
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                payload["benchmark_cli"] = {
                    "benchmark": AGENTISSUE_BENCHMARK_ID,
                    "command": "agentissue-codex-runner-flow",
                    "tag": args.tag,
                    "dry_run_default": True,
                    "real_runner_invoked": False,
                    "real_codex_invoked": False,
                    "real_docker_invoked": False,
                    "model_api_invoked": False,
                    "auth_values_read": False,
                    "submit_eligible": False,
                    "leaderboard_evidence": False,
                    "synthetic_staging_materialized": bool(synthetic_staging),
                    "synthetic_staging_root_path_recorded": False,
                    "execution_gate_materialized": bool(execution_gate),
                    "execution_gate_root_path_recorded": False,
                    "first_run_handoff_materialized": bool(first_run_handoff),
                    "first_run_handoff_root_path_recorded": False,
                    "workflow_check_materialized": bool(workflow_check),
                    "workflow_check_root_path_recorded": False,
                    "run_gate_materialized": bool(run_gate),
                    "run_gate_root_path_recorded": False,
                    "target_handoff_materialized": bool(target_handoff),
                    "target_handoff_root_path_recorded": False,
                    "real_result_materialized": bool(real_result),
                    "real_result_root_path_recorded": False,
                    "real_result_read_boundary": "compact_only" if real_result else None,
                    "private_runner_script_materialized": bool(private_runner_script),
                    "private_runner_root_path_recorded": False,
                    "private_runner_script_content_public": False,
                }
                payload["agentissue_runner_flow"] = wrapper
                if synthetic_staging:
                    payload["agentissue_synthetic_staging"] = synthetic_staging
                if execution_gate:
                    payload["agentissue_execution_gate"] = execution_gate
                if first_run_handoff:
                    payload["agentissue_first_run_handoff"] = first_run_handoff
                if workflow_check:
                    payload["agentissue_workflow_check"] = workflow_check
                if run_gate:
                    payload["agentissue_run_gate"] = run_gate
                if target_handoff:
                    payload["agentissue_target_handoff"] = target_handoff
                if real_result:
                    payload["agentissue_real_result"] = real_result
                    payload["benchmark_result"] = real_result["benchmark_result"]
                if private_runner_script:
                    payload["agentissue_private_runner_script"] = private_runner_script
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(getattr(args, "execute", False)),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": classification,
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_run_append_markdown)
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "classify-artifacts":
            payload = filter_public_benchmark_artifact_paths(
                args.artifact_paths,
                adapter_kind=args.adapter_kind,
                extra_public_filenames=args.allow_public_filename,
            )
            print_payload(
                payload,
                output_format(args),
                render_benchmark_artifact_path_filter_markdown,
            )
            return 0
        if args.benchmark_command == "candidate-source-boundary":
            payload = build_benchmark_candidate_source_boundary(
                args.source_paths,
                adapter_kind=args.adapter_kind,
                extra_public_filenames=args.allow_public_filename,
            )
            print_payload(
                payload,
                output_format(args),
                render_benchmark_candidate_source_boundary_markdown,
            )
            if args.require_clean and not payload.get("clean"):
                return 1
            return 0
        if args.benchmark_command == "split-control-execution-seam":
            def read_json_arg(path_text: str | None, label: str) -> dict[str, object]:
                if not path_text:
                    return {}
                raw = sys.stdin.read() if path_text == "-" else Path(path_text).expanduser().read_text(encoding="utf-8")
                loaded = json.loads(raw)
                if not isinstance(loaded, dict):
                    raise ValueError(f"{label} must contain a JSON object")
                return loaded

            try:
                readiness = read_json_arg(args.readiness_json, "--readiness-json")
                command_adapter_payload = read_json_arg(
                    args.command_adapter_json,
                    "--command-adapter-json",
                )
                command_adapters = (
                    command_adapter_payload.get("command_adapters")
                    if isinstance(
                        command_adapter_payload.get("command_adapters"), dict
                    )
                    else command_adapter_payload
                )
                launch_plan = build_split_control_remote_executor_launch_plan(
                    readiness
                )
                runner_batch = build_split_control_remote_executor_runner_batch(
                    launch_plan,
                    fresh_readiness=readiness,
                    execution_mode=args.execution_mode,
                )
                payload = build_split_control_remote_executor_execution_seam(
                    runner_batch,
                    command_adapters=command_adapters,
                )
                payload["ok"] = True
                payload["dry_run"] = True
                payload["read_boundary"] = {
                    "compact_only": True,
                    "readiness_json_read": True,
                    "command_adapter_json_read": bool(args.command_adapter_json),
                    "command_adapter_wrapper_unwrapped": bool(
                        args.command_adapter_json
                        and isinstance(
                            command_adapter_payload.get("command_adapters"), dict
                        )
                    ),
                    "raw_task_text_read": False,
                    "raw_logs_read": False,
                    "trajectory_read": False,
                    "shell_commands_read": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                    "submit_invoked": False,
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": True,
                    "schema_version": "benchmark_split_control_remote_executor_execution_seam_v1",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_task_text_read": False,
                        "raw_logs_read": False,
                        "trajectory_read": False,
                        "shell_commands_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                        "submit_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_split_control_execution_seam_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "terminal-bench-command-adapter":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = build_terminal_bench_remote_executor_command_adapter(
                    benchmark_id=args.benchmark_id,
                    launch_surface_ready=not bool(args.launch_surface_not_ready),
                    poll_surface_ready=not bool(args.poll_surface_not_ready),
                    resume_surface_ready=not bool(args.resume_surface_not_ready),
                    compact_ingest_ready=not bool(args.compact_ingest_not_ready),
                    result_reducer_ready=not bool(args.result_reducer_not_ready),
                    remote_materializer_ready=bool(args.remote_materializer_ready),
                    local_codex_driver_ready=bool(args.local_codex_driver_ready),
                    remote_sandbox_ready=bool(args.remote_sandbox_ready),
                    no_upload=not bool(args.submit_enabled),
                    submit_enabled=bool(args.submit_enabled),
                    known_blockers=args.surface_blocker,
                )
                payload["ok"] = True
                payload["dry_run"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "terminal_bench_command_adapter_not_ready"
                    )
                payload["require_ready"] = bool(args.require_ready)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": True,
                    "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "shell_commands_read": False,
                        "argv_read": False,
                        "raw_task_text_read": False,
                        "raw_logs_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "remote_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                        "submit_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_remote_executor_command_adapter_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "terminal-bench-remote-materializer":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                handle_manifest = None
                if args.handle_manifest_json:
                    try:
                        loaded_manifest = json.loads(
                            Path(args.handle_manifest_json).read_text(
                                encoding="utf-8"
                            )
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        raise ValueError(
                            "private handle manifest could not be read as a JSON object"
                        ) from exc
                    if not isinstance(loaded_manifest, dict):
                        raise ValueError("private handle manifest must be a JSON object")
                    handle_manifest = loaded_manifest
                payload = build_terminal_bench_remote_executor_materializer(
                    benchmark_id=args.benchmark_id,
                    handle_manifest=handle_manifest,
                    present_handle_fields=args.handle_field,
                    no_upload=not bool(args.no_upload_disabled),
                    submit_enabled=bool(args.submit_enabled),
                    local_codex_driver_ready=bool(args.local_codex_driver_ready),
                    remote_agent_runtime_required=bool(
                        args.remote_agent_runtime_required
                    ),
                    remote_codex_runtime_required=bool(
                        args.remote_codex_runtime_required
                    ),
                    local_codex_credential_sync=bool(
                        args.local_codex_credential_sync
                    ),
                    remote_model_invocation=bool(args.remote_model_invocation),
                    raw_material_allowed=bool(args.raw_material_allowed),
                )
                payload["ok"] = True
                payload["dry_run"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "terminal_bench_remote_materializer_not_ready"
                    )
                payload["require_ready"] = bool(args.require_ready)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": True,
                    "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "handle_manifest_values_recorded": False,
                        "shell_commands_read": False,
                        "argv_read": False,
                        "raw_task_text_read": False,
                        "raw_logs_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "remote_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                        "submit_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_remote_executor_materializer_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "terminal-bench-remote-launch-adapter":
            def read_private_manifest(path_text: str | None, label: str) -> dict[str, object] | None:
                if not path_text:
                    return None
                try:
                    loaded = json.loads(
                        Path(path_text).expanduser().read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"{label} could not be read as a JSON object"
                    ) from exc
                if not isinstance(loaded, dict):
                    raise ValueError(f"{label} must be a JSON object")
                return loaded

            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                request_manifest = read_private_manifest(
                    args.request_json,
                    "--request-json",
                )
                launch_result_manifest = read_private_manifest(
                    args.launch_result_json,
                    "--launch-result-json",
                )
                payload = build_terminal_bench_remote_executor_launch_adapter(
                    benchmark_id=args.benchmark_id,
                    request_manifest=request_manifest,
                    present_request_fields=args.request_field,
                    launch_result_manifest=launch_result_manifest,
                    present_launch_result_fields=args.launch_result_field,
                    local_codex_driver_ready=bool(args.local_codex_driver_ready),
                    remote_sandbox_ready=bool(args.remote_sandbox_ready),
                    no_upload=not bool(args.no_upload_disabled),
                    submit_enabled=bool(args.submit_enabled),
                    local_codex_credential_sync=bool(
                        args.local_codex_credential_sync
                    ),
                    remote_agent_runtime_required=bool(
                        args.remote_agent_runtime_required
                    ),
                    remote_codex_runtime_required=bool(
                        args.remote_codex_runtime_required
                    ),
                    remote_model_invocation=bool(args.remote_model_invocation),
                    raw_material_allowed=bool(args.raw_material_allowed),
                )
                payload["ok"] = True
                payload["dry_run"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "terminal_bench_remote_launch_adapter_not_ready"
                    )
                payload["require_ready"] = bool(args.require_ready)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": True,
                    "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "request_manifest_values_recorded": False,
                        "launch_result_values_recorded": False,
                        "shell_commands_read": False,
                        "argv_read": False,
                        "raw_task_text_read": False,
                        "raw_logs_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "remote_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                        "submit_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_remote_executor_launch_adapter_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-preflight":
            try:
                image_metadata = None
                alternate_image_metadata = None
                if args.no_docker_probe:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                    alternate_image_metadata = {
                        "image_ref": args.alternate_image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                payload = build_agents_last_exam_local_preflight(
                    selected_task_id=args.selected_task_id,
                    snapshot=args.snapshot,
                    provider_kind=args.provider_kind,
                    image_ref=args.image,
                    alternate_image_ref=args.alternate_image,
                    image_metadata=image_metadata,
                    alternate_image_metadata=alternate_image_metadata,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_preflight_v0",
                    "error": "ale_local_preflight_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_preflight_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_preflight_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-dry-run-plan":
            try:
                image_metadata = None
                alternate_image_metadata = None
                if args.no_docker_probe:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                    alternate_image_metadata = {
                        "image_ref": args.alternate_image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                payload = build_agents_last_exam_local_dry_run_plan(
                    selected_task_id=args.selected_task_id,
                    snapshot=args.snapshot,
                    provider_kind=args.provider_kind,
                    image_ref=args.image,
                    alternate_image_ref=args.alternate_image,
                    image_metadata=image_metadata,
                    alternate_image_metadata=alternate_image_metadata,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_dry_run_plan_v0",
                    "error": "ale_local_dry_run_plan_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_dry_run_plan_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_dry_run_plan_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-runner-readiness":
            try:
                image_metadata = None
                alternate_image_metadata = None
                if args.no_docker_probe:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                    alternate_image_metadata = {
                        "image_ref": args.alternate_image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                payload = build_agents_last_exam_local_runner_readiness(
                    selected_task_id=args.selected_task_id,
                    snapshot=args.snapshot,
                    provider_kind=args.provider_kind,
                    image_ref=args.image,
                    alternate_image_ref=args.alternate_image,
                    runner_binary=args.runner_binary,
                    runner_python_module=args.runner_python_module,
                    runner_source_root=args.runner_source_root,
                    runner_command_label=args.runner_command_label,
                    operator_authorized=bool(args.operator_authorized),
                    allow_public_task_material=bool(args.allow_public_task_material),
                    fetch_origin=bool(getattr(args, "fetch_origin", False)),
                    require_upstream_current=bool(
                        getattr(args, "require_upstream_current", False)
                    ),
                    image_metadata=image_metadata,
                    alternate_image_metadata=alternate_image_metadata,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_runner_readiness_v0",
                    "error": "ale_local_runner_readiness_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_runner_readiness_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_runner_readiness_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-source-readiness":
            try:
                payload = build_agents_last_exam_local_source_readiness(
                    source_root=args.source_root,
                    expected_repo_url=args.expected_repo_url,
                    runner_python_module=args.runner_python_module,
                    fetch_origin=bool(args.fetch_origin),
                    require_upstream_current=bool(args.require_upstream_current),
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_source_readiness_v0",
                    "error": "ale_local_source_readiness_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_source_readiness_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_source_readiness_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-task-material-readiness":
            try:
                selected_task_lists = (
                    args.selected_task_list
                    if args.selected_task_list
                    else ["linux_only.txt", "unlicensed/near-term.txt"]
                )
                baked_task_input_readiness = None
                if args.baked_task_input_readiness_json:
                    baked_task_input_readiness = json.loads(
                        Path(args.baked_task_input_readiness_json)
                        .expanduser()
                        .read_text(encoding="utf-8")
                    )
                payload = build_agents_last_exam_task_material_readiness(
                    source_root=args.source_root,
                    selected_task_id=args.selected_task_id,
                    selected_task_lists=selected_task_lists,
                    requires_task_data=None
                    if args.requires_task_data in {None, "unknown"}
                    else args.requires_task_data,
                    task_data_source=args.task_data_source,
                    baked_task_input_present=True
                    if args.baked_task_input_present
                    else None,
                    baked_task_input_readiness=baked_task_input_readiness,
                    gcs_sa_key=args.gcs_sa_key,
                    gcs_sa_key_present=True if args.gcs_sa_key_present else None,
                    enforce_task_data_source=bool(args.enforce_task_data_source),
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_task_material_readiness_v0",
                    "error": "ale_task_material_readiness_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "task_card_content_read": False,
                        "script_content_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_task_material_readiness_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_task_material_readiness_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-baked-task-input-readiness":
            try:
                image_metadata = None
                if args.no_docker_run:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_run_probe_disabled",
                    }
                payload = build_agents_last_exam_baked_task_input_readiness(
                    selected_task_id=args.selected_task_id,
                    image_ref=args.image,
                    image_metadata=image_metadata,
                    docker_binary=args.docker_binary,
                    timeout_seconds=args.timeout_seconds,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_baked_task_input_readiness_v0",
                    "error": "ale_baked_task_input_readiness_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "path_existence_only": True,
                        "task_text_read": False,
                        "task_card_content_read": False,
                        "script_content_read": False,
                        "task_data_content_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_baked_task_input_readiness_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_baked_task_input_readiness_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-baked-task-input-scan":
            try:
                selected_task_lists = (
                    args.selected_task_list
                    if args.selected_task_list
                    else ["linux_only.txt", "unlicensed/near-term.txt"]
                )
                image_metadata = None
                if args.no_docker_run:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_run_probe_disabled",
                    }
                payload = build_agents_last_exam_baked_task_input_scan(
                    source_root=args.source_root,
                    selected_task_lists=selected_task_lists,
                    image_ref=args.image,
                    image_metadata=image_metadata,
                    docker_binary=args.docker_binary,
                    max_tasks=args.max_tasks,
                    timeout_seconds=args.timeout_seconds,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_baked_task_input_scan_v0",
                    "error": "ale_baked_task_input_scan_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "path_existence_only": True,
                        "selected_task_lists_read": True,
                        "task_text_read": False,
                        "task_card_content_read": False,
                        "script_content_read": False,
                        "task_data_content_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_baked_task_input_scan_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_baked_task_input_scan_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-candidate-task-data-scan":
            try:
                selected_task_lists = (
                    args.selected_task_list
                    if args.selected_task_list
                    else ["linux_only.txt", "unlicensed/near-term.txt"]
                )
                payload = build_agents_last_exam_candidate_task_data_scan(
                    source_root=args.source_root,
                    selected_task_lists=selected_task_lists,
                    allow_demo_candidate=bool(args.allow_demo_candidate),
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_candidate_task_data_scan_v0",
                    "error": "ale_candidate_task_data_scan_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_config_source_content_recorded": False,
                        "task_card_content_read": False,
                        "script_content_read": False,
                        "task_instruction_file_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_candidate_task_data_scan_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_candidate_task_data_scan_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-launch-packet":
            try:
                image_metadata = None
                alternate_image_metadata = None
                if args.no_docker_probe:
                    image_metadata = {
                        "image_ref": args.image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                    alternate_image_metadata = {
                        "image_ref": args.alternate_image,
                        "present": False,
                        "probe_available": False,
                        "first_blocker": "docker_probe_disabled",
                    }
                payload = build_agents_last_exam_local_launch_packet(
                    source_root=args.source_root,
                    experiment_spec_relative_path=args.experiment_spec,
                    experiment_spec_root=args.experiment_spec_root,
                    selected_task_id=args.selected_task_id,
                    expected_repo_url=args.expected_repo_url,
                    snapshot=args.snapshot,
                    image_ref=args.image,
                    alternate_image_ref=args.alternate_image,
                    runner_binary=args.runner_binary,
                    runner_python_module=args.runner_python_module,
                    runner_command_label=args.runner_command_label,
                    operator_authorized=bool(args.operator_authorized),
                    allow_public_task_material=bool(args.allow_public_task_material),
                    fetch_origin=bool(args.fetch_origin),
                    require_upstream_current=bool(args.require_upstream_current),
                    image_metadata=image_metadata,
                    alternate_image_metadata=alternate_image_metadata,
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_launch_packet_v0",
                    "error": "ale_local_launch_packet_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "experiment_spec_content_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_launch_packet_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_launch_packet_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-local-exact-dry-run-result":
            try:
                stdout_text = Path(args.stdout_file).expanduser().read_text(
                    encoding="utf-8"
                )
                payload = build_agents_last_exam_local_exact_dry_run_result(
                    stdout_text=stdout_text,
                    exit_code=args.exit_code,
                    expected_task_id=args.expected_task_id,
                    expected_agent_id=args.expected_agent_id,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_local_exact_dry_run_result_v0",
                    "error": "ale_local_exact_dry_run_result_failed",
                    "error_type": type(exc).__name__,
                    "read_boundary": {
                        "compact_only": True,
                        "raw_stdout_recorded": False,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_local_exact_dry_run_result_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_local_exact_dry_run_result_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-host-codex-cli-route":
            try:
                payload = build_agents_last_exam_host_codex_cli_route(
                    codex_binary=args.codex_binary,
                    codex_binary_available=True
                    if args.assume_codex_binary_available
                    else None,
                    codex_version_text=args.codex_version_text,
                    host_auth_cache_present=True
                    if args.host_auth_cache_present
                    else None,
                    host_config_present=True if args.host_config_present else None,
                    require_host_config=bool(args.require_host_config),
                    cua_mcp_assets_root=args.cua_mcp_assets_root,
                    ale_sandbox_cua_smoke_ready=bool(
                        args.ale_sandbox_cua_smoke_ready
                    ),
                    operator_authorized_host_codex_auth=bool(
                        args.operator_authorized_host_codex_auth
                    ),
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_host_codex_cli_route_v0",
                    "error": "ale_host_codex_cli_route_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "auth_values_read": False,
                        "config_content_read": False,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_host_codex_cli_route_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_host_codex_cli_route_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-host-codex-cua-no-task-e2e":
            try:
                payload = build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
                    codex_binary=args.codex_binary,
                    codex_binary_available=True
                    if args.assume_codex_binary_available
                    else None,
                    codex_version_text=args.codex_version_text,
                    host_auth_cache_present=True
                    if args.host_auth_cache_present
                    else None,
                    host_config_present=True if args.host_config_present else None,
                    require_host_config=bool(args.require_host_config),
                    cua_mcp_assets_root=args.cua_mcp_assets_root,
                    cua_server_url=args.cua_server_url,
                    install_node_deps=bool(args.install_node_deps),
                    ale_sandbox_cua_smoke_ready=bool(
                        args.ale_sandbox_cua_smoke_ready
                    ),
                    operator_authorized_host_codex_auth=bool(
                        args.operator_authorized_host_codex_auth
                    ),
                )
            except Exception:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_host_codex_cua_no_task_smoke_v0",
                    "error": "ale_host_codex_cua_no_task_e2e_failed",
                    "read_boundary": {
                        "compact_only": True,
                        "auth_values_read": False,
                        "config_content_read": False,
                        "task_text_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_host_codex_cua_no_task_e2e_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_host_codex_cua_no_task_smoke_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "ale-validation-run-gate":
            try:
                task_material_readiness = json.loads(
                    Path(args.task_material_readiness_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
                host_codex_no_task_e2e = json.loads(
                    Path(args.host_codex_no_task_e2e_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
                exact_dry_run_result = json.loads(
                    Path(args.exact_dry_run_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
                launch_packet = None
                if args.launch_packet_json:
                    launch_packet = json.loads(
                        Path(args.launch_packet_json)
                        .expanduser()
                        .read_text(encoding="utf-8")
                    )
                payload = build_agents_last_exam_validation_run_gate(
                    selected_task_id=args.selected_task_id,
                    validation_hypothesis=args.validation_hypothesis,
                    task_material_readiness=task_material_readiness,
                    host_codex_no_task_e2e=host_codex_no_task_e2e,
                    exact_dry_run_result=exact_dry_run_result,
                    launch_packet=launch_packet,
                    result_reducer_ready=bool(args.result_reducer_ready),
                    submit_enabled=bool(args.submit_enabled),
                    leaderboard_enabled=bool(args.leaderboard_enabled),
                    formal_score_candidate=bool(args.formal_score_candidate),
                    require_fresh_source=bool(args.require_fresh_source),
                    expected_formal_agent=args.expected_formal_agent,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "agents_last_exam_validation_run_gate_v0",
                    "error": "ale_validation_run_gate_failed",
                    "error_type": type(exc).__name__,
                    "read_boundary": {
                        "compact_only": True,
                        "task_text_read": False,
                        "task_card_content_read": False,
                        "script_content_read": False,
                        "raw_artifacts_read": False,
                        "local_paths_recorded": False,
                        "container_started": False,
                        "model_api_invoked": False,
                        "codex_prompt_sent": False,
                    },
                }
            else:
                payload["ok"] = True
                if args.require_ready and payload.get("ready") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "ale_validation_run_gate_not_ready"
                    )
            print_payload(
                payload,
                output_format(args),
                render_agents_last_exam_validation_run_gate_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "review-claim":
            try:
                comparison_input = json.loads(
                    Path(args.benchmark_comparison_json).expanduser().read_text(encoding="utf-8")
                )
                if not isinstance(comparison_input, dict):
                    raise ValueError("--benchmark-comparison-json must contain a JSON object")
                comparison = compact_benchmark_comparison(comparison_input)
                if not comparison:
                    raise ValueError(
                        "--benchmark-comparison-json did not contain a compactable benchmark_comparison_v0 object"
                    )
                runs = []
                for run_json in args.benchmark_run_json:
                    run_input = json.loads(
                        Path(run_json).expanduser().read_text(encoding="utf-8")
                    )
                    if not isinstance(run_input, dict):
                        raise ValueError("--benchmark-run-json must contain JSON objects")
                    run = compact_benchmark_run(run_input)
                    if not run:
                        raise ValueError(
                            "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                        )
                    runs.append(run)
                payload = build_benchmark_claim_review(
                    comparison,
                    benchmark_runs=runs,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_claim_review_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
            print_payload(
                payload,
                output_format(args),
                render_benchmark_claim_review_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "learning-ledger":
            try:
                comparison_input = json.loads(
                    Path(args.benchmark_comparison_json).expanduser().read_text(encoding="utf-8")
                )
                if not isinstance(comparison_input, dict):
                    raise ValueError("--benchmark-comparison-json must contain a JSON object")
                comparison = compact_benchmark_comparison(comparison_input)
                if not comparison:
                    raise ValueError(
                        "--benchmark-comparison-json did not contain a compactable benchmark_comparison_v0 object"
                    )
                runs = []
                for run_json in args.benchmark_run_json:
                    run_input = json.loads(
                        Path(run_json).expanduser().read_text(encoding="utf-8")
                    )
                    if not isinstance(run_input, dict):
                        raise ValueError("--benchmark-run-json must contain JSON objects")
                    run = compact_benchmark_run(run_input)
                    if not run:
                        raise ValueError(
                            "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                        )
                    runs.append(run)
                payload = build_benchmark_learning_ledger(
                    comparison,
                    benchmark_runs=runs,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_learning_ledger_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
                learning_gate = (
                    payload.get("learning_quota_gate")
                    if isinstance(payload.get("learning_quota_gate"), dict)
                    else {}
                )
                if (
                    args.require_actionable_learning
                    and learning_gate.get("spend_allowed") is not True
                ):
                    payload["ok"] = False
                    payload["error"] = (
                        learning_gate.get("blocked_reason")
                        or "missing_actionable_goal_harness_learning_signal"
                    )
            print_payload(
                payload,
                output_format(args),
                render_benchmark_learning_ledger_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "attempt-learning-gate":
            try:
                run_input = json.loads(
                    Path(args.benchmark_run_json).expanduser().read_text(encoding="utf-8")
                )
                if not isinstance(run_input, dict):
                    raise ValueError("--benchmark-run-json must contain a JSON object")
                run = compact_benchmark_run(run_input)
                if not run:
                    raise ValueError(
                        "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                    )

                learning_ledger = None
                if args.benchmark_learning_ledger_json:
                    ledger_input = json.loads(
                        Path(args.benchmark_learning_ledger_json)
                        .expanduser()
                        .read_text(encoding="utf-8")
                    )
                    if not isinstance(ledger_input, dict):
                        raise ValueError(
                            "--benchmark-learning-ledger-json must contain a JSON object"
                        )
                    learning_ledger = compact_benchmark_learning_ledger(ledger_input)
                    if not learning_ledger:
                        raise ValueError(
                            "--benchmark-learning-ledger-json did not contain a compactable benchmark_learning_ledger_v0 object"
                        )

                payload = build_benchmark_attempt_learning_gate(
                    run,
                    benchmark_learning_ledger=learning_ledger,
                )
                payload["ok"] = True
                if (
                    args.require_budget_count_allowed
                    and payload.get("budget_count_allowed") is not True
                ):
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("classification")
                        or "benchmark_attempt_learning_gate_not_ready"
                    )
                payload["require_budget_count_allowed"] = bool(
                    args.require_budget_count_allowed
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_attempt_learning_gate_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_benchmark_attempt_learning_gate_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "review-adapter-kwargs":
            try:
                agent_kwargs: dict[str, Any] = {}
                if args.command_json:
                    command_input = json.loads(
                        Path(args.command_json).expanduser().read_text(encoding="utf-8")
                    )
                    if not isinstance(command_input, list):
                        raise ValueError("--command-json must contain a JSON argv list")
                    agent_kwargs.update(agent_kwargs_from_invocation(command_input))
                for raw_kwarg in args.agent_kwarg:
                    key, separator, value = str(raw_kwarg).partition("=")
                    key = key.strip()
                    if not separator or not key:
                        raise ValueError("--agent-kwarg values must use KEY=VALUE form")
                    agent_kwargs[key] = value
                accepted = list(args.accepted_goal_harness_kwarg)
                if args.terminal_bench_managed_codex:
                    accepted.extend(TERMINAL_BENCH_MANAGED_CODEX_GOAL_HARNESS_KWARGS)
                payload = build_benchmark_adapter_kwarg_absorption_review(
                    adapter_label=args.adapter_label,
                    agent_kwargs=agent_kwargs,
                    accepted_goal_harness_kwargs=accepted,
                    allowed_base_passthrough=args.allowed_base_passthrough,
                )
                payload["ok"] = True
                if args.require_clean and payload.get("clean") is not True:
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("classification")
                        or "benchmark_adapter_kwarg_absorption_not_clean"
                    )
                payload["require_clean"] = bool(args.require_clean)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_adapter_kwarg_absorption_review_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_benchmark_adapter_kwarg_absorption_review_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "lifecycle-state":
            def read_optional_json(path_text: str | None) -> dict[str, object] | None:
                if not path_text:
                    return None
                payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("lifecycle input JSON must contain an object")
                return payload

            try:
                preflight = read_optional_json(args.preflight_json)
                launch = read_optional_json(args.launch_json)
                post_launch = read_optional_json(args.post_launch_json)

                benchmark_run = None
                run_input = read_optional_json(args.benchmark_run_json)
                if run_input is not None:
                    benchmark_run = compact_benchmark_run(run_input)
                    if not benchmark_run:
                        raise ValueError(
                            "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                        )

                benchmark_comparison = None
                comparison_input = read_optional_json(args.benchmark_comparison_json)
                if comparison_input is not None:
                    benchmark_comparison = compact_benchmark_comparison(comparison_input)
                    if not benchmark_comparison:
                        raise ValueError(
                            "--benchmark-comparison-json did not contain a compactable benchmark_comparison_v0 object"
                        )

                claim_review = read_optional_json(args.claim_review_json)
                if (
                    claim_review is not None
                    and claim_review.get("schema_version") != "benchmark_claim_review_v0"
                ):
                    raise ValueError("--claim-review-json must contain benchmark_claim_review_v0")

                learning_ledger = None
                ledger_input = read_optional_json(args.benchmark_learning_ledger_json)
                if ledger_input is not None:
                    learning_ledger = compact_benchmark_learning_ledger(ledger_input)
                    if not learning_ledger:
                        raise ValueError(
                            "--benchmark-learning-ledger-json did not contain a compactable benchmark_learning_ledger_v0 object"
                        )

                payload = build_benchmark_lifecycle_state(
                    preflight=preflight,
                    launch=launch,
                    post_launch_materialization=post_launch,
                    benchmark_run=benchmark_run,
                    benchmark_comparison=benchmark_comparison,
                    claim_review=claim_review,
                    learning_ledger=learning_ledger,
                )
                payload["ok"] = True
                gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
                if (
                    args.require_budget_count_allowed
                    and gates.get("budget_count_allowed") is not True
                ):
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "benchmark_lifecycle_budget_count_not_allowed"
                    )
                payload["require_budget_count_allowed"] = bool(
                    args.require_budget_count_allowed
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_lifecycle_state_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_benchmark_lifecycle_state_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "environment-setup-gate":
            def read_optional_json(path_text: str | None) -> dict[str, object] | None:
                if not path_text:
                    return None
                payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("environment setup gate input JSON must contain an object")
                return payload

            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                preflight = read_optional_json(args.preflight_json)
                run_input = read_optional_json(args.benchmark_run_json)
                if run_input is None:
                    raise ValueError("--benchmark-run-json is required")
                benchmark_run = compact_benchmark_run(run_input)
                if not benchmark_run:
                    raise ValueError(
                        "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                    )
                payload = build_terminal_bench_environment_setup_probe_gate(
                    dataset=args.dataset,
                    task_id=args.include_task_name,
                    preflight=preflight,
                    previous_benchmark_run=benchmark_run,
                    harbor_run_help_text=args.harbor_run_help_text,
                    probe_runner_help=bool(args.probe_runner_help),
                )
                payload["ok"] = True
                if (
                    args.require_probe_allowed
                    and payload.get("environment_setup_probe_allowed") is not True
                ):
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "environment_setup_probe_not_allowed"
                    )
                payload["require_probe_allowed"] = bool(args.require_probe_allowed)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_environment_setup_probe_gate_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_help_recorded": False,
                        "raw_artifacts_read": False,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "credential_values_recorded": False,
                        "codex_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_environment_setup_gate_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "launch-environment-setup-probe":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                gate = json.loads(Path(args.gate_json).expanduser().read_text(encoding="utf-8"))
                if not isinstance(gate, dict):
                    raise ValueError("--gate-json must contain a JSON object")
                payload = launch_terminal_bench_environment_setup_probe(
                    gate=gate,
                    jobs_dir=args.jobs_dir,
                    run_root=args.run_root,
                    wait_seconds=args.wait_seconds,
                    execute=bool(args.execute),
                )
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_environment_setup_probe_launch_v0",
                    "dry_run": not bool(args.execute),
                    "error": str(exc),
                    "boundary": {
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "command_argv_recorded": False,
                        "codex_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_environment_setup_probe_launch_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "launch-worker-materialization-probe":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = launch_terminal_bench_worker_materialization_probe(
                    jobs_dir=args.jobs_dir,
                    run_root=args.run_root,
                    dataset=args.dataset,
                    task_id=args.include_task_name,
                    model=args.model,
                    mode=args.mode,
                    job_name=args.job_name,
                    worker_codex_materialization_strategy=(
                        args.worker_codex_materialization_strategy
                    ),
                    wait_seconds=args.wait_seconds,
                    execute=bool(args.execute),
                )
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_worker_materialization_probe_launch_v0",
                    "dry_run": not bool(args.execute),
                    "error": str(exc),
                    "boundary": {
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "command_argv_recorded": False,
                        "task_solver_invoked_by_probe": False,
                        "model_api_expected": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_worker_materialization_probe_launch_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "launch-terminal-bench-run":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = launch_terminal_bench_case_run(
                    jobs_dir=args.jobs_dir,
                    run_root=args.run_root,
                    dataset=args.dataset,
                    task_id=args.include_task_name,
                    model=args.model,
                    mode=args.mode,
                    job_name=args.job_name,
                    wait_seconds=args.wait_seconds,
                    materialization_wait_seconds=(
                        args.materialization_wait_seconds
                    ),
                    resume_after_materialization=bool(
                        args.resume_after_materialization
                    ),
                    execute=bool(args.execute),
                    timeout_multiplier=args.timeout_multiplier,
                    agent_timeout_multiplier=args.agent_timeout_multiplier,
                    verifier_timeout_multiplier=args.verifier_timeout_multiplier,
                    agent_setup_timeout_multiplier=(
                        args.agent_setup_timeout_multiplier
                    ),
                    environment_build_timeout_multiplier=(
                        args.environment_build_timeout_multiplier
                    ),
                    codex_install_strategy=args.codex_install_strategy,
                    codex_preflight_timeout_sec=args.codex_preflight_timeout_sec,
                    worker_codex_materialization_strategy=(
                        args.worker_codex_materialization_strategy
                    ),
                    setup_timeout_repair_profile=bool(
                        args.setup_timeout_repair_profile
                    ),
                )
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_case_run_launch_v0",
                    "dry_run": not bool(args.execute),
                    "error": str(exc),
                    "boundary": {
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "command_argv_recorded": False,
                        "task_solver_invoked": False,
                        "model_api_expected": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_case_run_launch_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "resume-terminal-bench-job":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = resume_terminal_bench_materialized_job(
                    jobs_dir=args.jobs_dir,
                    run_root=args.run_root,
                    job_name=args.job_name,
                    wait_seconds=args.wait_seconds,
                    execute=bool(args.execute),
                )
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_harbor_resume_observation_v0",
                    "dry_run": not bool(args.execute),
                    "error": str(exc),
                    "boundary": {
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "command_argv_recorded": False,
                        "resume_invoked": False,
                        "model_api_expected": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_resume_observation_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "poll-worker-materialization-probe":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = poll_terminal_bench_worker_materialization_probe(
                    jobs_dir=args.jobs_dir,
                    run_root=args.run_root,
                    job_name=args.job_name,
                )
                payload["ok"] = True
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_worker_materialization_probe_poll_v0",
                    "error": str(exc),
                    "boundary": {
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "local_paths_recorded": False,
                        "command_argv_recorded": False,
                        "command_line_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_worker_materialization_probe_poll_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "review-verifier-attribution":
            try:
                runs = []
                for run_json in args.benchmark_run_json:
                    run_input = json.loads(Path(run_json).expanduser().read_text(encoding="utf-8"))
                    if not isinstance(run_input, dict):
                        raise ValueError("--benchmark-run-json must contain JSON objects")
                    run = compact_benchmark_run(run_input)
                    if not run:
                        raise ValueError(
                            "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                        )
                    runs.append(run)
                payload = build_benchmark_verifier_attribution_review(
                    benchmark_runs=runs,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_verifier_attribution_review_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                    },
                }
            else:
                payload["ok"] = True
            print_payload(
                payload,
                output_format(args),
                render_benchmark_verifier_attribution_review_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "review-runner-invariants":
            try:
                run_input = json.loads(
                    Path(args.benchmark_run_json).expanduser().read_text(encoding="utf-8")
                )
                if not isinstance(run_input, dict):
                    raise ValueError("--benchmark-run-json must contain a JSON object")
                run = compact_benchmark_run(run_input)
                if not run:
                    raise ValueError(
                        "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                    )
                payload = build_benchmark_runner_invariant_review(
                    run,
                    expected_flags={
                        "submit_eligible": args.expect_submit_eligible == "true",
                        "leaderboard_evidence": args.expect_leaderboard_evidence
                        == "true",
                    },
                    expected_read_boundary={
                        "compact_only": args.expect_compact_only == "true",
                        "raw_artifacts_read": args.expect_raw_artifacts_read
                        == "true",
                        "task_text_read": args.expect_task_text_read == "true",
                        "local_paths_recorded": args.expect_local_paths_recorded
                        == "true",
                    },
                    runner_label=args.runner_label,
                )
                payload["ok"] = True
                if args.require_clean and payload.get("clean") is not True:
                    payload["ok"] = False
                    payload["error"] = payload.get("classification") or (
                        "benchmark_runner_invariant_review_not_clean"
                    )
                payload["require_clean"] = bool(args.require_clean)
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "benchmark_runner_invariant_review_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_benchmark_runner_invariant_review_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "summarize-post-launch":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                payload = summarize_terminal_bench_post_launch_materialization(
                    args.jobs_dir,
                    job_name=args.job_name,
                    detached_process_state=args.detached_process_state,
                    reconcile_stale_active=args.reconcile_stale_active,
                )
                ready = payload.get("ready_for_launch_state") is True
                payload["ok"] = (
                    ready if args.require_ready_for_launch_state else True
                )
                payload["require_ready_for_launch_state"] = bool(
                    args.require_ready_for_launch_state
                )
                payload["read_boundary"] = {
                    "raw_paths_recorded": False,
                    "raw_logs_read": False,
                    "task_text_read": False,
                    "trajectory_read": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                }
                if args.require_ready_for_launch_state and not ready:
                    payload["error"] = (
                        "post-launch materialization is not ready for launch state"
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_post_launch_materialization_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "raw_paths_recorded": False,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_post_launch_materialization_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "result-finalization-gate":
            try:
                if args.benchmark_name != "terminal-bench":
                    raise ValueError("only terminal-bench is supported")
                if args.post_launch_json == "-":
                    post_launch = json.loads(sys.stdin.read())
                else:
                    post_launch = json.loads(
                        Path(args.post_launch_json)
                        .expanduser()
                        .read_text(encoding="utf-8")
                    )
                if not isinstance(post_launch, dict):
                    raise ValueError("--post-launch-json must contain a JSON object")
                payload = build_terminal_bench_result_finalization_gate(
                    post_launch,
                    max_repaired_baseline_reruns=(
                        args.max_repaired_baseline_reruns
                    ),
                )
                payload["require_rerun_allowed"] = bool(
                    args.require_rerun_allowed
                )
                if (
                    args.require_rerun_allowed
                    and payload.get("repaired_baseline_rerun_allowed") is not True
                ):
                    payload["ok"] = False
                    payload["error"] = (
                        payload.get("first_blocker")
                        or "result_finalization_gate_rerun_not_allowed"
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "schema_version": "terminal_bench_result_finalization_gate_v0",
                    "error": str(exc),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_artifacts_read": False,
                        "raw_paths_recorded": False,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                        "raw_external_handle_payload_recorded": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_terminal_bench_result_finalization_gate_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "baseline-failure-gate":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "benchmark baseline-failure-gate accepts either --dry-run or --execute, not both"
                    )
                if args.execute and not args.goal_id:
                    raise ValueError(
                        "benchmark baseline-failure-gate requires --goal-id with --execute"
                    )
                if args.baseline_result_json == "-":
                    baseline_result_input = json.loads(sys.stdin.read())
                else:
                    baseline_result_input = json.loads(
                        Path(args.baseline_result_json)
                        .expanduser()
                        .read_text(encoding="utf-8")
                    )
                if not isinstance(baseline_result_input, dict):
                    raise ValueError("--baseline-result-json must contain a JSON object")
                baseline_result = compact_benchmark_result(baseline_result_input)
                baseline_gate_source = "compact_benchmark_result_v0"
                if not baseline_result:
                    benchmark_run = compact_benchmark_run(baseline_result_input)
                    if benchmark_run:
                        baseline_result = (
                            benchmark_result_from_benchmark_run_for_baseline_gate(
                                benchmark_run
                            )
                        )
                        baseline_gate_source = "compact_benchmark_run_v0"
                    else:
                        raise ValueError(
                            "--baseline-result-json did not contain a compactable benchmark_result_v0 or benchmark_run_v0 object"
                        )
                comparison_input = build_benchmark_baseline_failure_gate_comparison(
                    baseline_result=baseline_result,
                    benchmark_id=args.benchmark_id,
                    baseline_mode=args.baseline_mode,
                    treatment_scenario_id=args.treatment_scenario_id,
                    comparison_id=args.comparison_id,
                    failure_phase=args.failure_phase,
                    failure_class=args.failure_class,
                    failure_attribution_labels=args.failure_attribution_label,
                    control_plane_addressable=bool(args.control_plane_addressable),
                    same_task_semantics=bool(args.same_task_semantics),
                    same_runner_protocol=bool(args.same_runner_protocol),
                    trace_publicness_verified=bool(args.trace_publicness_verified),
                    baseline_attempt_count=args.baseline_attempt_count,
                    minimum_next_evidence=args.minimum_next_evidence,
                    negative_selection_reason=args.negative_selection_reason,
                    next_action=args.next_action,
                    evidence_refs=args.evidence_ref,
                )
                comparison = compact_benchmark_comparison(comparison_input)
                if not comparison:
                    raise ValueError(
                        "baseline gate reducer did not produce a compactable benchmark_comparison_v0 object"
                    )
                dry_run = not bool(args.execute)
                if args.execute:
                    payload = append_benchmark_comparison(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        benchmark_comparison=comparison,
                        classification=args.classification
                        or "benchmark_comparison_v0",
                        recommended_action=args.recommended_action
                        or (
                            comparison.get("next_action")
                            if isinstance(comparison.get("next_action"), str)
                            else None
                        )
                        or "route the baseline failure gate before any treatment run",
                        delivery_batch_scale=args.delivery_batch_scale,
                        delivery_outcome=args.delivery_outcome,
                        dry_run=False,
                    )
                    if args.no_global_sync:
                        payload["global_sync"] = {
                            "ok": True,
                            "dry_run": False,
                            "skipped": True,
                            "reason": "disabled by --no-global-sync",
                        }
                    else:
                        payload["global_sync"] = sync_project_registry_to_global(
                            registry_path=registry_path,
                            runtime_root_override=args.runtime_root,
                            goal_id=args.goal_id,
                            dry_run=False,
                        )
                else:
                    payload = {
                        "ok": True,
                        "dry_run": dry_run,
                        "appended": False,
                        "goal_id": args.goal_id,
                        "classification": args.classification
                        or "benchmark_comparison_v0",
                        "benchmark_comparison": comparison,
                    }
                payload["baseline_gate_cli"] = {
                    "source": baseline_gate_source,
                    "accepted_schemas": [
                        "benchmark_result_v0",
                        "benchmark_run_v0",
                    ],
                    "raw_artifacts_read": False,
                    "task_text_read": False,
                    "local_paths_recorded": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(getattr(args, "execute", False)),
                    "appended": False,
                    "goal_id": getattr(args, "goal_id", None),
                    "classification": getattr(args, "classification", None)
                    or "benchmark_comparison_v0",
                    "error": str(exc),
                    "baseline_gate_cli": {
                        "source": "compact_benchmark_result_v0_or_benchmark_run_v0",
                        "accepted_schemas": [
                            "benchmark_result_v0",
                            "benchmark_run_v0",
                        ],
                        "raw_artifacts_read": False,
                        "task_text_read": False,
                        "local_paths_recorded": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            print_payload(
                payload,
                output_format(args),
                render_benchmark_baseline_failure_gate_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "parity-check":
            try:
                if args.benchmark_run_json == "-":
                    run_input = json.loads(sys.stdin.read())
                else:
                    run_input = json.loads(
                        Path(args.benchmark_run_json).expanduser().read_text(
                            encoding="utf-8"
                        )
                    )
                benchmark_run = compact_benchmark_run(run_input)
                if not benchmark_run:
                    raise ValueError(
                        "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                    )
                payload = {
                    "ok": True,
                    "codex_app_parity_posthoc_check": (
                        build_codex_app_parity_posthoc_check(benchmark_run)
                    ),
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "codex_app_parity_posthoc_check": {
                        "full_product_claim_allowed": False,
                        "claim_level": "invalid_or_unreadable_compact_benchmark_run",
                    },
                    "error": str(exc),
                }
            print_payload(
                payload,
                args.format,
                lambda value: render_codex_app_parity_posthoc_check_markdown(
                    value["codex_app_parity_posthoc_check"]
                ),
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "run-ledger-check":
            try:
                history_payload = collect_history(
                    registry_path=registry_path,
                    runtime_root=resolve_runtime_root(
                        load_registry(registry_path),
                        args.runtime_root,
                    ),
                    goal_id=args.goal_id,
                    limit=max(0, int(args.history_limit)),
                )
                ledger = load_benchmark_run_ledger(args.run_ledger_path)
                drift = check_benchmark_run_ledger_drift(
                    history_records=[
                        run
                        for run in history_payload.get("runs", [])
                        if isinstance(run, dict)
                    ],
                    ledger=ledger,
                    ledger_path=args.run_ledger_path,
                    limit=max(0, int(args.limit)),
                    cwd=Path.cwd(),
                )
                payload = {
                    "ok": True,
                    "goal_id": args.goal_id,
                    "history_limit": args.history_limit,
                    "benchmark_run_ledger_drift": drift,
                    "read_boundary": drift.get("read_boundary"),
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "goal_id": args.goal_id,
                    "benchmark_run_ledger_drift": {
                        "schema_version": "benchmark_run_ledger_drift_v0",
                        "ok": False,
                        "drift_detected": False,
                    },
                    "read_boundary": {
                        "compact_only": True,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                    "error": str(exc),
                }
            print_payload(
                payload,
                args.format,
                render_benchmark_run_ledger_check_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "case-analysis-candidates":
            try:
                ledger = load_benchmark_case_analysis_json(args.run_ledger_path)
                analysis = load_benchmark_case_analysis_json(
                    args.case_analysis_path
                )
                report = build_case_analysis_candidate_report(
                    ledger=ledger,
                    analysis=analysis,
                )
                payload = {
                    "ok": True,
                    "report": report,
                    "run_ledger_path": str(args.run_ledger_path),
                    "case_analysis_path": str(args.case_analysis_path),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "run_ledger_path": str(args.run_ledger_path),
                    "case_analysis_path": str(args.case_analysis_path),
                    "read_boundary": {
                        "compact_only": True,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                    "error": str(exc),
                }
            print_payload(
                payload,
                args.format,
                render_benchmark_case_analysis_candidates_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "run-ledger-upsert":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "benchmark run-ledger-upsert accepts either --dry-run or --execute, not both"
                    )
                if bool(args.benchmark_run_json) == bool(args.post_launch_json):
                    raise ValueError(
                        "provide exactly one of --benchmark-run-json or --post-launch-json"
                    )

                input_path_text = args.benchmark_run_json or args.post_launch_json
                if input_path_text == "-":
                    run_input = json.loads(sys.stdin.read())
                    compact_artifact_ref = args.compact_artifact_ref
                else:
                    input_path = Path(input_path_text).expanduser()
                    run_input = json.loads(input_path.read_text(encoding="utf-8"))
                    compact_artifact_ref = args.compact_artifact_ref or str(input_path)
                if not isinstance(run_input, dict):
                    raise ValueError("ledger input JSON must contain an object")

                if args.benchmark_run_json:
                    benchmark_run = compact_benchmark_run(run_input)
                    if not benchmark_run:
                        raise ValueError(
                            "--benchmark-run-json did not contain a compactable benchmark_run_v0 object"
                        )
                    input_kind = "benchmark_run_v0"
                else:
                    benchmark_run = compact_benchmark_post_launch_materialization(
                        run_input
                    )
                    if not benchmark_run:
                        raise ValueError(
                            "--post-launch-json did not contain a compactable terminal_bench_post_launch_materialization_v0 object"
                        )
                    input_kind = "terminal_bench_post_launch_materialization_v0"
                dry_run = not bool(args.execute)
                ledger_update = update_benchmark_run_ledger(
                    ledger_path=args.run_ledger_path,
                    benchmark_run=benchmark_run,
                    compact_artifact_ref=compact_artifact_ref,
                    run_group_id=args.run_group_id,
                    arm_id=args.arm_id,
                    notes=args.run_ledger_note,
                    dry_run=dry_run,
                )
                payload = {
                    "ok": True,
                    "dry_run": dry_run,
                    "input_kind": input_kind,
                    "benchmark_run_ledger": ledger_update,
                    "read_boundary": {
                        "compact_only": True,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                }
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "benchmark_run_ledger": {
                        "updated": False,
                        "ledger_path": args.run_ledger_path,
                    },
                    "read_boundary": {
                        "compact_only": True,
                        "raw_logs_read": False,
                        "task_text_read": False,
                        "trajectory_read": False,
                        "docker_invoked": False,
                        "model_api_invoked": False,
                        "upload_invoked": False,
                    },
                    "error": str(exc),
                }
            print_payload(
                payload,
                args.format,
                render_benchmark_run_ledger_upsert_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.benchmark_command == "run":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("benchmark run accepts either --dry-run or --execute, not both")
                if args.benchmark_name == "skillsbench":
                    classification = args.classification or (
                        "skillsbench_official_benchflow_result_ingest_v0"
                        if args.skillsbench_result_json
                        else (
                            "skillsbench_"
                            + str(args.skillsbench_route).replace("-", "_")
                            + "_skeleton_v0"
                        )
                    )
                else:
                    classification = args.classification or (
                        "terminal_bench_harbor_runner_result_ingest_v0"
                        if args.harbor_job_dir
                        else
                        "terminal_bench_active_user_assisted_observation_fixture_v0"
                        if args.active_user_observation_fixture
                        else
                        "terminal_bench_active_user_assisted_treatment_preflight_v0"
                        if args.active_user_assisted_treatment
                        else
                        "terminal_bench_codex_goal_harness_active_cli_bridge_preflight_v0"
                        if args.active_cli_bridge
                        else
                        "terminal_bench_codex_goal_harness_worker_cli_bridge_fixture_v0"
                        if args.worker_cli_bridge_fixture
                        else
                        "terminal_bench_codex_goal_harness_cli_bridge_contract_runner_fixture_v0"
                        if args.cli_bridge_contract
                        else (
                            (
                                "terminal_bench_codex_goal_harness_preflight_guard_v0"
                                if args.mode == "codex-goal-harness"
                                else (
                                    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE
                                    + "_v0"
                                )
                                if args.mode == "hardened-codex"
                                else "terminal_bench_codex_goal_mode_baseline_preflight_guard_v0"
                                if args.mode == "codex-goal-mode"
                                else "terminal_bench_managed_real_run_preflight_guard_v0"
                            )
                            if args.preflight_guard
                            else (
                                (
                                    "terminal_bench_codex_goal_harness_fake_worker_v0"
                                    if args.mode == "codex-goal-harness"
                                    else "terminal_bench_cli_fake_worker_v0"
                                )
                                if args.fake_worker
                                else (
                                    "terminal_bench_codex_goal_harness_dry_run_v0"
                                    if args.mode == "codex-goal-harness"
                                    else "terminal_bench_codex_goal_mode_baseline_dry_run_v0"
                                    if args.mode == "codex-goal-mode"
                                    else "terminal_bench_cli_dry_run_v0"
                                )
                            )
                        )
                    )
                terminal_bench_only_flags = (
                    args.harbor_job_dir
                    or args.fake_worker
                    or args.preflight_guard
                    or args.require_task_material_ready
                    or args.cli_bridge_contract
                    or args.worker_cli_bridge_fixture
                    or args.active_cli_bridge
                    or args.active_user_assisted_treatment
                    or args.active_user_observation_fixture
                    or args.setup_timeout_repair_profile
                    or args.timeout_multiplier is not None
                    or args.agent_timeout_multiplier is not None
                    or args.verifier_timeout_multiplier is not None
                    or args.agent_setup_timeout_multiplier is not None
                    or args.environment_build_timeout_multiplier is not None
                    or args.codex_preflight_timeout_sec is not None
                    or args.worker_codex_materialization_strategy is not None
                    or args.worker_materialization_probe_only
                )
                if args.benchmark_name == "skillsbench" and terminal_bench_only_flags:
                    raise ValueError(
                        "skillsbench skeleton does not accept Terminal-Bench runner, "
                        "Harbor ingest, preflight, timeout, fake-worker, or bridge flags"
                    )
                if args.harbor_job_dir and (
                    args.fake_worker
                    or args.preflight_guard
                    or args.require_task_material_ready
                    or args.cli_bridge_contract
                    or args.worker_cli_bridge_fixture
                    or args.active_cli_bridge
                    or args.active_user_assisted_treatment
                    or args.active_user_observation_fixture
                    or args.setup_timeout_repair_profile
                    or args.worker_materialization_probe_only
                ):
                    raise ValueError(
                        "--harbor-job-dir cannot be combined with fixture or preflight flags"
                    )
                if args.require_task_material_ready and not args.preflight_guard:
                    raise ValueError("--require-task-material-ready requires --preflight-guard")
                timeout_multiplier_preview_requested = any(
                    value is not None
                    for value in (
                        args.timeout_multiplier,
                        args.agent_timeout_multiplier,
                        args.verifier_timeout_multiplier,
                        args.agent_setup_timeout_multiplier,
                        args.environment_build_timeout_multiplier,
                        args.codex_preflight_timeout_sec,
                        args.worker_codex_materialization_strategy,
                    )
                )
                timeout_multiplier_preview_defaulted = (
                    args.active_cli_bridge and args.agent_timeout_multiplier is None
                )
                if args.harbor_job_dir and timeout_multiplier_preview_requested:
                    raise ValueError(
                        "--harbor-job-dir reads timeout policy from Harbor artifacts; "
                        "do not pass preview timeout multiplier flags"
                    )
                cli_bridge_trace = None
                if args.cli_bridge_contract:
                    runtime_root = resolve_runtime_root(
                        load_registry(registry_path),
                        args.runtime_root,
                    )
                    cli_bridge_trace = collect_terminal_bench_goal_harness_cli_bridge_trace(
                        goal_id=args.goal_id,
                        registry=str(registry_path),
                        runtime_root=str(runtime_root),
                        command_prefix=[sys.executable, "-m", "goal_harness.cli"],
                        scan_path="goal_harness/benchmark.py",
                        classification=classification,
                    )
                if args.benchmark_name == "skillsbench":
                    skillsbench_dataset = (
                        SKILLSBENCH_DEFAULT_DATASET
                        if args.dataset == TERMINAL_BENCH_DEFAULT_DATASET
                        else args.dataset
                    )
                    skillsbench_task = (
                        SKILLSBENCH_DEFAULT_TASK
                        if args.include_task_name == TERMINAL_BENCH_DEFAULT_TASK
                        else args.include_task_name
                    )
                    skillsbench_model = (
                        SKILLSBENCH_DEFAULT_MODEL
                        if args.model == TERMINAL_BENCH_DEFAULT_MODEL
                        else args.model
                    )
                    if args.skillsbench_result_json:
                        benchmark_run_input = build_skillsbench_benchflow_result_benchmark_run(
                            args.skillsbench_result_json,
                            route=args.skillsbench_route,
                            dataset=skillsbench_dataset,
                            agent=args.agent,
                            model=skillsbench_model,
                        )
                    else:
                        benchmark_run_input = build_skillsbench_benchmark_run(
                            route=args.skillsbench_route,
                            dataset=skillsbench_dataset,
                            task_id=skillsbench_task,
                            agent=args.agent,
                            model=skillsbench_model,
                        )
                elif args.harbor_job_dir:
                    benchmark_run_input = build_terminal_bench_harbor_result_benchmark_run(
                        args.harbor_job_dir,
                    )
                else:
                    benchmark_run_input = build_terminal_bench_benchmark_run(
                        mode=args.mode,
                        dataset=args.dataset,
                        task_id=args.include_task_name,
                        runner=args.runner,
                        agent=args.agent,
                        model=args.model,
                        fake_worker=bool(args.fake_worker),
                        preflight_guard=bool(args.preflight_guard),
                        cli_bridge_contract=bool(args.cli_bridge_contract),
                        cli_bridge_trace=cli_bridge_trace,
                        worker_cli_bridge_fixture=bool(args.worker_cli_bridge_fixture),
                        active_cli_bridge_preflight=bool(args.active_cli_bridge),
                        active_user_assisted_treatment_preflight=bool(
                            args.active_user_assisted_treatment
                        ),
                        active_user_observation_fixture=bool(
                            args.active_user_observation_fixture
                        ),
                        require_task_material_ready=bool(args.require_task_material_ready),
                        timeout_multiplier=args.timeout_multiplier,
                        agent_timeout_multiplier=args.agent_timeout_multiplier,
                        verifier_timeout_multiplier=args.verifier_timeout_multiplier,
                        agent_setup_timeout_multiplier=args.agent_setup_timeout_multiplier,
                        environment_build_timeout_multiplier=args.environment_build_timeout_multiplier,
                        codex_install_strategy=args.codex_install_strategy,
                        codex_preflight_timeout_sec=args.codex_preflight_timeout_sec,
                        worker_codex_materialization_strategy=(
                            args.worker_codex_materialization_strategy
                        ),
                        worker_materialization_probe_only=bool(
                            args.worker_materialization_probe_only
                        ),
                        setup_timeout_repair_profile=bool(
                            args.setup_timeout_repair_profile
                        ),
                    )
                benchmark_run = compact_benchmark_run(benchmark_run_input)
                if not benchmark_run:
                    raise ValueError("benchmark command did not produce a compactable benchmark_run_v0")
                if args.harbor_job_dir:
                    benchmark_cli_mode = str(benchmark_run.get("mode") or args.mode)
                elif (
                    args.benchmark_name == "terminal-bench"
                    and args.active_user_assisted_treatment
                ):
                    benchmark_cli_mode = str(benchmark_run.get("mode") or args.mode)
                elif args.benchmark_name == "skillsbench":
                    benchmark_cli_mode = str(args.skillsbench_route)
                else:
                    benchmark_cli_mode = str(args.mode)
                benchmark_cli_mode_source = (
                    "harbor_job_result"
                    if args.harbor_job_dir
                    else "skillsbench_route"
                    if args.benchmark_name == "skillsbench"
                    else "cli_arg"
                )

                dry_run = not bool(args.execute)
                payload = append_benchmark_run(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_run=benchmark_run,
                    classification=classification,
                    recommended_action=args.recommended_action
                    or (
                        skillsbench_recommended_action(route=args.skillsbench_route)
                        if args.benchmark_name == "skillsbench"
                        else
                        "inspect runner-side Terminal-Bench result and refine worker closure/writeback"
                        if args.harbor_job_dir
                        else terminal_bench_recommended_action(
                            mode=args.mode,
                            fake_worker=bool(args.fake_worker),
                            preflight_guard=bool(args.preflight_guard),
                            cli_bridge_contract=bool(args.cli_bridge_contract),
                            worker_cli_bridge_fixture=bool(args.worker_cli_bridge_fixture),
                            active_cli_bridge_preflight=bool(args.active_cli_bridge),
                            active_user_assisted_treatment_preflight=bool(
                                args.active_user_assisted_treatment
                            ),
                        )
                    ),
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                payload["benchmark_cli"] = {
                    "benchmark": args.benchmark_name,
                    "mode": benchmark_cli_mode,
                    "requested_mode": args.mode,
                    "skillsbench_route": args.skillsbench_route
                    if args.benchmark_name == "skillsbench"
                    else None,
                    "mode_source": benchmark_cli_mode_source,
                    "fake_worker": bool(args.fake_worker),
                    "preflight_guard": bool(args.preflight_guard),
                    "require_task_material_ready": bool(args.require_task_material_ready),
                    "cli_bridge_contract": bool(args.cli_bridge_contract),
                    "worker_cli_bridge_fixture": bool(args.worker_cli_bridge_fixture),
                    "active_cli_bridge": bool(args.active_cli_bridge),
                    "active_user_assisted_treatment": bool(
                        args.active_user_assisted_treatment
                    ),
                    "harbor_job_result_ingested": bool(args.harbor_job_dir),
                    "skillsbench_result_ingested": bool(
                        getattr(args, "skillsbench_result_json", None)
                    ),
                    "timeout_multiplier_preview_requested": (
                        timeout_multiplier_preview_requested
                        or timeout_multiplier_preview_defaulted
                    ),
                    "timeout_multiplier_preview_defaulted": timeout_multiplier_preview_defaulted,
                    "cli_bridge_trace_observed": bool(
                        isinstance(cli_bridge_trace, dict)
                        and cli_bridge_trace.get("bridge_available") is True
                    ),
                    "real_runner_invoked": False,
                    "real_codex_invoked": False,
                    "auth_values_read": False,
                    "submit_eligible": False,
                }
                if args.update_run_ledger:
                    harbor_job_path = (
                        Path(args.harbor_job_dir).expanduser()
                        if args.harbor_job_dir
                        else None
                    )
                    skillsbench_result_path = (
                        Path(args.skillsbench_result_json).expanduser()
                        if getattr(args, "skillsbench_result_json", None)
                        else None
                    )
                    inferred_run_group_id = args.run_group_id
                    if not inferred_run_group_id and harbor_job_path is not None:
                        inferred_run_group_id = (
                            harbor_job_path.parent.parent.name
                            if harbor_job_path.parent.name == "jobs"
                            else harbor_job_path.parent.name
                        )
                    if (
                        not inferred_run_group_id
                        and skillsbench_result_path is not None
                    ):
                        inferred_run_group_id = (
                            skillsbench_result_path.parent.parent.name
                        )
                    payload["benchmark_run_ledger"] = update_benchmark_run_ledger(
                        ledger_path=args.run_ledger_path,
                        benchmark_run=benchmark_run,
                        artifact_ref=(
                            str(harbor_job_path)
                            if harbor_job_path is not None
                            else (
                                skillsbench_result_path.parent.name
                                if skillsbench_result_path is not None
                                else None
                            )
                        ),
                        result_ref=(
                            str(harbor_job_path / "result.json")
                            if harbor_job_path is not None
                            else (
                                skillsbench_result_path.name
                                if skillsbench_result_path is not None
                                else None
                            )
                        ),
                        compact_artifact_ref=payload.get("json_path")
                        if isinstance(payload.get("json_path"), str)
                        else None,
                        run_group_id=inferred_run_group_id,
                        arm_id=args.arm_id,
                        notes=args.run_ledger_note,
                        dry_run=dry_run,
                    )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
                append_benchmark_run_rollout_event(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=args.runtime_root,
                    command="benchmark",
                    action=args.benchmark_name,
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification
                    or (
                        (
                            "skillsbench_official_benchflow_result_ingest_v0"
                            if getattr(args, "skillsbench_result_json", None)
                            else (
                                "skillsbench_"
                                + str(getattr(args, "skillsbench_route", "")).replace("-", "_")
                                + "_skeleton_v0"
                            )
                        )
                        if getattr(args, "benchmark_name", None) == "skillsbench"
                        else
                        "terminal_bench_active_user_assisted_treatment_preflight_v0"
                        if getattr(args, "active_user_assisted_treatment", False)
                        else
                        "terminal_bench_codex_goal_harness_worker_cli_bridge_fixture_v0"
                        if getattr(args, "worker_cli_bridge_fixture", False)
                        else
                        "terminal_bench_codex_goal_harness_cli_bridge_contract_runner_fixture_v0"
                        if getattr(args, "cli_bridge_contract", False)
                        else "terminal_bench_codex_goal_mode_baseline_preflight_guard_v0"
                        if getattr(args, "preflight_guard", False)
                        and getattr(args, "mode", None) == "codex-goal-mode"
                        else "terminal_bench_managed_real_run_preflight_guard_v0"
                        if getattr(args, "preflight_guard", False)
                        else "terminal_bench_codex_goal_mode_baseline_dry_run_v0"
                        if getattr(args, "mode", None) == "codex-goal-mode"
                        else "terminal_bench_cli_dry_run_v0"
                    ),
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_run_append_markdown)
            return 0 if payload.get("ok") else 1

    if args.command == "history":
        if args.history_action == "inspect-index-duplicates":
            try:
                payload = inspect_index_duplicates(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    limit=args.limit,
                )
            except Exception as exc:
                registry = load_registry(registry_path)
                runtime_root = resolve_runtime_root(registry, args.runtime_root)
                payload = {
                    "ok": False,
                    "registry": str(registry_path),
                    "runtime_root": str(runtime_root),
                    "goal_filter": args.goal_id,
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_index_duplicate_inspection_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "repair-index-duplicates":
            try:
                payload = repair_index_duplicates(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    limit=args.limit,
                    execute=bool(args.execute),
                )
            except Exception as exc:
                registry = load_registry(registry_path)
                runtime_root = resolve_runtime_root(registry, args.runtime_root)
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "registry": str(registry_path),
                    "runtime_root": str(runtime_root),
                    "goal_filter": args.goal_id,
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_index_duplicate_repair_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-run":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-run accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-run requires --goal-id")
                if not args.benchmark_run_json:
                    raise ValueError("history append-benchmark-run requires --benchmark-run-json")

                if args.benchmark_run_json == "-":
                    benchmark_run_input = json.loads(sys.stdin.read())
                else:
                    benchmark_run_input = json.loads(Path(args.benchmark_run_json).expanduser().read_text(encoding="utf-8"))
                if not isinstance(benchmark_run_input, dict):
                    raise ValueError("--benchmark-run-json must contain a JSON object")
                benchmark_run = compact_benchmark_run(benchmark_run_input)
                if not benchmark_run:
                    raise ValueError("--benchmark-run-json did not contain a compactable benchmark_run_v0 object")

                dry_run = not bool(args.execute)
                payload = append_benchmark_run(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_run=benchmark_run,
                    classification=args.classification or "benchmark_run_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
                append_benchmark_run_rollout_event(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=args.runtime_root,
                    command="history",
                    action="append-benchmark-run",
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_run_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_run_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-result":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-result accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-result requires --goal-id")
                if not args.benchmark_result_json:
                    raise ValueError("history append-benchmark-result requires --benchmark-result-json")

                if args.benchmark_result_json == "-":
                    benchmark_result_input = json.loads(sys.stdin.read())
                else:
                    benchmark_result_input = json.loads(Path(args.benchmark_result_json).expanduser().read_text(encoding="utf-8"))
                if not isinstance(benchmark_result_input, dict):
                    raise ValueError("--benchmark-result-json must contain a JSON object")
                benchmark_result = compact_benchmark_result(benchmark_result_input)
                if not benchmark_result:
                    raise ValueError("--benchmark-result-json did not contain a compactable benchmark_result_v0 object")

                dry_run = not bool(args.execute)
                payload = append_benchmark_result(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_result=benchmark_result,
                    classification=args.classification or "benchmark_result_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
                append_benchmark_result_rollout_event(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=args.runtime_root,
                    command="history",
                    action="append-benchmark-result",
                )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_result_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_result_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-comparison":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-comparison accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-comparison requires --goal-id")
                if not args.benchmark_comparison_json:
                    raise ValueError("history append-benchmark-comparison requires --benchmark-comparison-json")

                if args.benchmark_comparison_json == "-":
                    benchmark_comparison_input = json.loads(sys.stdin.read())
                else:
                    benchmark_comparison_input = json.loads(
                        Path(args.benchmark_comparison_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(benchmark_comparison_input, dict):
                    raise ValueError("--benchmark-comparison-json must contain a JSON object")
                benchmark_comparison = compact_benchmark_comparison(benchmark_comparison_input)
                if not benchmark_comparison:
                    raise ValueError(
                        "--benchmark-comparison-json did not contain a compactable benchmark_comparison_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_comparison(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_comparison=benchmark_comparison,
                    classification=args.classification or "benchmark_comparison_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_comparison_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_comparison_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-learning-ledger":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "history append-benchmark-learning-ledger accepts either --dry-run or --execute, not both"
                    )
                if not args.goal_id:
                    raise ValueError("history append-benchmark-learning-ledger requires --goal-id")
                if not args.benchmark_learning_ledger_json:
                    raise ValueError(
                        "history append-benchmark-learning-ledger requires --benchmark-learning-ledger-json"
                    )

                if args.benchmark_learning_ledger_json == "-":
                    ledger_input = json.loads(sys.stdin.read())
                else:
                    ledger_input = json.loads(
                        Path(args.benchmark_learning_ledger_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(ledger_input, dict):
                    raise ValueError("--benchmark-learning-ledger-json must contain a JSON object")
                benchmark_learning_ledger = compact_benchmark_learning_ledger(ledger_input)
                if not benchmark_learning_ledger:
                    raise ValueError(
                        "--benchmark-learning-ledger-json did not contain a compactable benchmark_learning_ledger_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_learning_ledger(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_learning_ledger=benchmark_learning_ledger,
                    classification=args.classification or "benchmark_learning_ledger_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_learning_ledger_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_learning_ledger_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-benchmark-report":
            try:
                if args.dry_run and args.execute:
                    raise ValueError("history append-benchmark-report accepts either --dry-run or --execute, not both")
                if not args.goal_id:
                    raise ValueError("history append-benchmark-report requires --goal-id")
                if not args.benchmark_report_json:
                    raise ValueError("history append-benchmark-report requires --benchmark-report-json")

                if args.benchmark_report_json == "-":
                    benchmark_report_input = json.loads(sys.stdin.read())
                else:
                    benchmark_report_input = json.loads(
                        Path(args.benchmark_report_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(benchmark_report_input, dict):
                    raise ValueError("--benchmark-report-json must contain a JSON object")
                benchmark_report = compact_benchmark_experiment_report(benchmark_report_input)
                if not benchmark_report:
                    raise ValueError(
                        "--benchmark-report-json did not contain a compactable benchmark_experiment_report_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_experiment_report(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_experiment_report=benchmark_report,
                    classification=args.classification or "benchmark_experiment_report_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "benchmark_experiment_report_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_experiment_report_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-agents-last-exam-result-report":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "history append-agents-last-exam-result-report accepts either --dry-run or --execute, not both"
                    )
                if not args.goal_id:
                    raise ValueError("history append-agents-last-exam-result-report requires --goal-id")
                if not args.agents_last_exam_run_dir:
                    raise ValueError(
                        "history append-agents-last-exam-result-report requires --agents-last-exam-run-dir"
                    )

                benchmark_report_input = build_agents_last_exam_result_benchmark_report(
                    Path(args.agents_last_exam_run_dir).expanduser(),
                    report_id=args.report_id,
                )
                benchmark_report = compact_benchmark_experiment_report(benchmark_report_input)
                if not benchmark_report:
                    raise ValueError(
                        "--agents-last-exam-run-dir did not produce a compactable benchmark_experiment_report_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_benchmark_experiment_report(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    benchmark_experiment_report=benchmark_report,
                    classification=args.classification or "agents_last_exam_result_report_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                payload["benchmark_report_source"] = {
                    "kind": "agents_last_exam_run_dir",
                    "raw_surfaces_excluded": True,
                    "raw_surface_content_recorded": False,
                    "local_paths_recorded": False,
                }
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "agents_last_exam_result_report_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_benchmark_experiment_report_append_markdown)
            return 0 if payload.get("ok") else 1

        if args.history_action == "append-active-user-assisted-pilot":
            try:
                if args.dry_run and args.execute:
                    raise ValueError(
                        "history append-active-user-assisted-pilot accepts either --dry-run or --execute, not both"
                    )
                if not args.goal_id:
                    raise ValueError("history append-active-user-assisted-pilot requires --goal-id")
                if not args.active_user_pilot_json:
                    raise ValueError(
                        "history append-active-user-assisted-pilot requires --active-user-pilot-json"
                    )

                if args.active_user_pilot_json == "-":
                    active_user_pilot_input = json.loads(sys.stdin.read())
                else:
                    active_user_pilot_input = json.loads(
                        Path(args.active_user_pilot_json).expanduser().read_text(encoding="utf-8")
                    )
                if not isinstance(active_user_pilot_input, dict):
                    raise ValueError("--active-user-pilot-json must contain a JSON object")
                active_user_pilot = compact_active_user_assisted_pilot(active_user_pilot_input)
                if not active_user_pilot:
                    raise ValueError(
                        "--active-user-pilot-json did not contain a compactable active_user_assisted_pilot_v0 object"
                    )

                dry_run = not bool(args.execute)
                payload = append_active_user_assisted_pilot(
                    registry_path=registry_path,
                    runtime_root_override=args.runtime_root,
                    goal_id=args.goal_id,
                    active_user_assisted_pilot=active_user_pilot,
                    classification=args.classification or "active_user_assisted_pilot_v0",
                    recommended_action=args.recommended_action,
                    delivery_batch_scale=args.delivery_batch_scale,
                    delivery_outcome=args.delivery_outcome,
                    dry_run=dry_run,
                )
                if args.no_global_sync:
                    payload["global_sync"] = {
                        "ok": True,
                        "dry_run": dry_run,
                        "skipped": True,
                        "reason": "disabled by --no-global-sync",
                    }
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=dry_run,
                    )
            except Exception as exc:
                payload = {
                    "ok": False,
                    "dry_run": not bool(args.execute),
                    "appended": False,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "goal_id": args.goal_id,
                    "classification": args.classification or "active_user_assisted_pilot_v0",
                    "error": str(exc),
                }
            print_payload(payload, args.format, render_active_user_assisted_pilot_append_markdown)
            return 0 if payload.get("ok") else 1

        try:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = collect_history(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                limit=max(0, args.limit),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_history_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "archive-runtime":
        try:
            payload = archive_runtime_goal(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                archive_root=Path(args.archive_root).expanduser() if args.archive_root else None,
                allow_registered=bool(args.allow_registered),
                execute=bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "dry_run": not bool(args.execute),
                "archived": False,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_archive_runtime_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "sync-global":
        try:
            payload = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                goal_id=args.goal_id,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, args.runtime_root)
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": str(runtime_root),
                "global_registry": str(global_registry_path(runtime_root)),
                "dry_run": bool(args.dry_run),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_global_sync_markdown)
        return 0 if payload.get("ok") else 1

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
        print_payload(payload, args.format, render_state_refresh_markdown)
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
        print_payload(payload, args.format, render_read_only_project_map_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "reward":
        try:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
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
        print_payload(payload, args.format, render_reward_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "operator-gate":
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
        print_payload(payload, args.format, render_operator_gate_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "register-authority-source":
        try:
            payload = register_authority_source(
                registry_path=registry_path,
                goal_id=args.goal_id,
                source_id=args.source_id,
                source_ref=args.source_ref,
                source_kind=args.source_kind,
                role=args.role,
                freshness=args.freshness,
                owner_status=args.owner_status,
                gate_status=args.gate_status,
                boundary=args.boundary,
                revision=args.revision,
                conflict_rule=args.conflict_rule,
                topic=args.topic,
                dry_run=bool(args.dry_run),
            )
            if not bool(args.no_global_sync):
                if args.dry_run:
                    payload["global_sync"] = {"enabled": True, "dry_run": True, "wrote": False}
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=False,
                    )
            else:
                payload["global_sync"] = {"enabled": False}
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "source_id": getattr(args, "source_id", None),
                "written": False,
                "dry_run": bool(getattr(args, "dry_run", False)),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_authority_source_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "import-doc-registry-authority":
        try:
            payload = import_doc_registry_authority(
                registry_path=registry_path,
                goal_id=args.goal_id,
                source_id=args.source_id,
                doc_registry_path=Path(args.doc_registry_path),
                source_kind=args.source_kind,
                role=args.role,
                freshness=args.freshness,
                owner_status=args.owner_status,
                gate_status=args.gate_status,
                boundary=args.boundary,
                revision=args.revision,
                conflict_rule=args.conflict_rule,
                topics=list(args.topic or []),
                import_topic_prefix=args.import_topic_prefix,
                max_imported_topics=int(args.max_imported_topics),
                dry_run=bool(args.dry_run),
            )
            if not bool(args.no_global_sync):
                if args.dry_run:
                    payload["global_sync"] = {"enabled": True, "dry_run": True, "wrote": False}
                else:
                    payload["global_sync"] = sync_project_registry_to_global(
                        registry_path=registry_path,
                        runtime_root_override=args.runtime_root,
                        goal_id=args.goal_id,
                        dry_run=False,
                    )
            else:
                payload["global_sync"] = {"enabled": False}
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": args.runtime_root,
                "goal_id": args.goal_id,
                "source_id": getattr(args, "source_id", None),
                "written": False,
                "dry_run": bool(getattr(args, "dry_run", False)),
                "error": str(exc),
            }
        print_payload(payload, args.format, render_doc_registry_authority_import_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "check":
        return handle_check_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            allow_missing_registry=not user_supplied_registry(argv),
            print_payload=print_payload,
        )

    if args.command == "status":
        return handle_status_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "diagnose":
        return handle_diagnose_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "review-packet":
        return handle_review_packet_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "dreaming":
        return handle_dreaming_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "todo":
        try:
            if args.todo_command == "add":
                if not args.role:
                    raise ValueError("todo add requires --role")
                if not args.text:
                    raise ValueError("todo add requires --text")
                if args.clear_claim:
                    raise ValueError("todo add accepts --claimed-by but not --clear-claim")
                if args.next_claimed_by:
                    raise ValueError("todo add does not support --next-claimed-by")
                if args.side_agent_self_merged:
                    raise ValueError("todo add does not support --side-agent-self-merged")
                payload = add_goal_todo(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    role=args.role,
                    text=args.text,
                    task_class=args.task_class,
                    action_kind=args.action_kind,
                    required_write_scopes=args.required_write_scopes,
                    required_capabilities=args.required_capabilities,
                    claimed_by=args.claimed_by,
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=bool(args.dry_run),
                )
            elif args.todo_command == "claim":
                if not args.todo_id:
                    raise ValueError("todo claim requires --todo-id")
                if not args.claimed_by:
                    raise ValueError("todo claim requires --claimed-by")
                if args.clear_claim:
                    raise ValueError("todo claim requires --claimed-by and does not support --clear-claim")
                unsupported = [
                    flag
                    for flag, value in (
                        ("--text", args.text),
                        ("--status", args.status),
                        ("--note", args.note),
                        ("--evidence", args.evidence),
                        ("--reason", args.reason),
                        ("--task-class", args.task_class),
                        ("--action-kind", args.action_kind),
                        ("--required-write-scope", args.required_write_scopes),
                        ("--required-capability", args.required_capabilities),
                        ("--next-agent-todo", args.next_agent_todo),
                        ("--next-user-todo", args.next_user_todo),
                        ("--next-claimed-by", args.next_claimed_by),
                        ("--next-task-class", args.next_task_class),
                        ("--next-action-kind", args.next_action_kind),
                        ("--side-agent-self-merged", args.side_agent_self_merged),
                    )
                    if value
                ]
                if unsupported:
                    raise ValueError(
                        "todo claim only accepts --todo-id, --claimed-by, optional --role, "
                        "--project, --state-file, and --dry-run; unsupported: "
                        + ", ".join(unsupported)
                    )
                payload = update_goal_todo(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    todo_id=args.todo_id,
                    role=args.role,
                    claimed_by=args.claimed_by,
                    claim_only=True,
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=bool(args.dry_run),
                )
            elif args.todo_command == "update":
                if not args.todo_id:
                    raise ValueError("todo update requires --todo-id")
                if args.claimed_by and args.clear_claim:
                    raise ValueError("todo update accepts either --claimed-by or --clear-claim, not both")
                if not any([
                    args.text,
                    args.status,
                    args.note,
                    args.evidence,
                    args.reason,
                    args.task_class,
                    args.action_kind,
                    args.required_write_scopes,
                    args.required_capabilities,
                    args.claimed_by,
                    args.clear_claim,
                ]):
                    raise ValueError("todo update requires at least one of --text, --status, --note, --evidence, --reason, --task-class, --action-kind, --required-write-scope, --required-capability, --claimed-by, or --clear-claim")
                if args.next_claimed_by:
                    raise ValueError("todo update does not support --next-claimed-by")
                if args.side_agent_self_merged:
                    raise ValueError("todo update does not support --side-agent-self-merged")
                payload = update_goal_todo(
                    registry_path=registry_path,
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
                    required_write_scopes=args.required_write_scopes,
                    required_capabilities=args.required_capabilities,
                    claimed_by=args.claimed_by,
                    clear_claim=bool(args.clear_claim),
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=bool(args.dry_run),
                )
            elif args.todo_command == "complete":
                if not args.todo_id:
                    raise ValueError("todo complete requires --todo-id")
                if args.claimed_by and args.clear_claim:
                    raise ValueError("todo complete accepts either --claimed-by or --clear-claim, not both")
                payload = complete_goal_todo(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    todo_id=args.todo_id,
                    role=args.role,
                    evidence=args.evidence,
                    note=args.note,
                    claimed_by=args.claimed_by,
                    clear_claim=bool(args.clear_claim),
                    next_agent_todo=args.next_agent_todo,
                    next_user_todo=args.next_user_todo,
                    next_claimed_by=args.next_claimed_by,
                    next_task_class=args.next_task_class,
                    next_action_kind=args.next_action_kind,
                    side_agent_self_merged=bool(args.side_agent_self_merged),
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=bool(args.dry_run),
                )
            elif args.todo_command == "supersede":
                if not args.todo_id:
                    raise ValueError("todo supersede requires --todo-id")
                if args.claimed_by or args.clear_claim:
                    raise ValueError("todo supersede does not support --claimed-by or --clear-claim")
                if args.next_claimed_by:
                    raise ValueError("todo supersede does not support --next-claimed-by")
                if args.side_agent_self_merged:
                    raise ValueError("todo supersede does not support --side-agent-self-merged")
                payload = supersede_goal_todo(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    todo_id=args.todo_id,
                    role=args.role,
                    reason=args.reason,
                    next_agent_todo=args.next_agent_todo,
                    next_user_todo=args.next_user_todo,
                    next_task_class=args.next_task_class,
                    next_action_kind=args.next_action_kind,
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=bool(args.dry_run),
                )
            elif args.todo_command == "archive-completed":
                if args.claimed_by or args.clear_claim:
                    raise ValueError("todo archive-completed does not support --claimed-by or --clear-claim")
                if args.next_claimed_by:
                    raise ValueError("todo archive-completed does not support --next-claimed-by")
                if args.side_agent_self_merged:
                    raise ValueError("todo archive-completed does not support --side-agent-self-merged")
                payload = archive_completed_todos(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    role=args.role or "agent",
                    max_active_done=args.max_active_done,
                    project=Path(args.project).expanduser() if args.project else None,
                    state_file=Path(args.state_file).expanduser() if args.state_file else None,
                    dry_run=not bool(args.execute),
                )
            else:
                raise ValueError("unsupported todo command")
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute)
                if args.todo_command == "archive-completed"
                else bool(args.dry_run),
                "added": False,
                "already_exists": False,
                "goal_id": args.goal_id,
                "role": args.role,
                "todo": args.text or "",
                "error": str(exc),
            }
        todo_event_kinds = {
            "add": "todo_add",
            "claim": "todo_claim",
            "update": "todo_update",
            "complete": "todo_complete",
            "supersede": "todo_supersede",
            "archive-completed": "todo_archive_completed",
        }
        if payload.get("ok") and not payload.get("dry_run"):
            append_cli_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
                event_kind=todo_event_kinds.get(args.todo_command, "todo_update"),
                agent_id=args.claimed_by,
                todo_id=args.todo_id or str(payload.get("todo_id") or "").strip() or None,
                status=str(payload.get("status") or args.todo_command or "").strip(),
                summary=(
                    f"todo {args.todo_command} recorded for "
                    f"{payload.get('todo_id') or args.todo_id or 'unstructured todo'}"
                ),
                details={
                    "command": "todo",
                    "todo_command": args.todo_command,
                    "role": payload.get("role") or args.role or "",
                    "changed": bool(payload.get("changed")),
                    "added": bool(payload.get("added")),
                    "already_exists": bool(payload.get("already_exists")),
                },
            )
        print_payload(payload, args.format, render_todo_markdown)
        return 0 if payload.get("ok") else 1

    if args.command == "quota":
        try:
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            status_limit = max(0, args.limit)
            if args.quota_command == "should-run":
                status_limit = max(status_limit, AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK)
            status_payload = collect_status(
                registry_path=registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=status_limit,
            )
            if args.quota_command == "should-run":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota should-run` requires --goal-id")
                payload = build_quota_should_run(
                    status_payload,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    available_capabilities=args.available_capabilities,
                )
            elif args.quota_command == "monitor-poll":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota monitor-poll` requires --goal-id")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota monitor-poll` accepts only one of --dry-run or --execute")
                payload = record_quota_monitor_poll(
                    status_payload,
                    goal_id=args.goal_id,
                    execute=bool(args.execute),
                    source=args.source,
                    reason_summary=args.reason_summary,
                )
            elif args.quota_command == "spend-slot":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota spend-slot` requires --goal-id")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota spend-slot` accepts only one of --dry-run or --execute")
                payload = spend_quota_slot(
                    status_payload,
                    goal_id=args.goal_id,
                    slots=args.slots,
                    execute=bool(args.execute),
                    source=args.source,
                    agent_id=args.agent_id,
                    available_capabilities=args.available_capabilities,
                )
            elif args.quota_command == "void-slot":
                if not args.goal_id:
                    raise ValueError("`goal-harness quota void-slot` requires --goal-id")
                if not args.void_generated_at:
                    raise ValueError("`goal-harness quota void-slot` requires --void-generated-at")
                if args.dry_run and args.execute:
                    raise ValueError("`goal-harness quota void-slot` accepts only one of --dry-run or --execute")
                payload = void_quota_slot(
                    status_payload,
                    goal_id=args.goal_id,
                    voided_run_generated_at=args.void_generated_at,
                    execute=bool(args.execute),
                    source=args.source,
                    reason_summary=args.reason_summary,
                )
            else:
                payload = build_quota_plan(status_payload, mode=args.quota_command)
        except Exception as exc:
            if args.quota_command in {"should-run", "monitor-poll", "spend-slot", "void-slot"}:
                payload = {
                    "ok": False,
                    "mode": args.quota_command,
                    "goal_id": args.goal_id,
                    "decision": "skip",
                    "should_run": False,
                    "reason": str(exc),
                    "state": "blocked_health",
                    "waiting_on": "codex",
                    "status": "quota_collection_failed",
                    "source": "quota",
                    "recommended_action": "fix quota/status collection before spending automatic compute",
                }
            else:
                payload = {
                    "ok": False,
                    "mode": args.quota_command,
                    "registry": str(registry_path),
                    "runtime_root": args.runtime_root,
                    "error": str(exc),
                    "summary": {
                        "registered_goals": 0,
                        "health_blockers": 1,
                        "next_automatic_turn": None,
                        "states": {},
                    },
                    "groups": {},
                    "health_items": [
                        {
                            "goal_id": "goal-harness-quota",
                            "status": "quota_collection_failed",
                            "waiting_on": "codex",
                            "severity": "high",
                            "recommended_action": str(exc),
                            "source": "quota",
                        }
                    ],
                }
        quota_event_kinds = {
            "should-run": "quota_should_run",
            "monitor-poll": "quota_monitor_poll",
            "spend-slot": "quota_spend",
            "void-slot": "quota_void",
        }
        should_log_quota = (
            args.quota_command in quota_event_kinds
            and (
                args.quota_command == "should-run"
                or (payload.get("ok") and bool(payload.get("appended")))
            )
        )
        if should_log_quota:
            append_cli_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=args.runtime_root,
                event_kind=quota_event_kinds[args.quota_command],
                agent_id=args.agent_id,
                status=str(
                    payload.get("effective_action")
                    or payload.get("decision")
                    or payload.get("mode")
                    or args.quota_command
                ),
                summary=(
                    f"quota {args.quota_command} decision="
                    f"{payload.get('decision') or payload.get('mode')} "
                    f"state={payload.get('state') or ''}"
                ),
                details={
                    "command": "quota",
                    "quota_command": args.quota_command,
                    "ok": bool(payload.get("ok")),
                    "should_run": bool(payload.get("should_run")),
                    "appended": bool(payload.get("appended")),
                    "slots": payload.get("slots") or "",
                    "source": payload.get("source") or "",
                },
                allow_failed=args.quota_command == "should-run",
            )
        renderer = (
            render_quota_should_run_markdown
            if args.quota_command == "should-run"
            else render_quota_monitor_poll_markdown
            if args.quota_command == "monitor-poll"
            else render_quota_slot_preview_markdown
            if args.quota_command in {"spend-slot", "void-slot"}
            else render_quota_markdown
        )
        print_payload(payload, args.format, renderer)
        return 0 if payload.get("ok") else 1

    if args.command == "serve-status":
        try:
            status_registry_path = explicit_global_registry(args.runtime_root) if args.global_registry else registry_path
            scan_roots = [Path(item).expanduser() for item in args.scan_path]
            if not scan_roots:
                scan_roots = [Path(args.scan_root).expanduser()]
            serve_status(
                registry_path=status_registry_path,
                runtime_root_override=args.runtime_root,
                scan_roots=scan_roots,
                limit=max(0, args.limit),
                host=args.host,
                port=args.port,
                status_path=args.path,
                enable_reward_write_api=bool(args.enable_reward_write_api),
                enable_control_plane_write_api=bool(args.enable_control_plane_write_api),
                verbose=bool(args.verbose),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(status_registry_path if "status_registry_path" in locals() else registry_path),
                "runtime_root": args.runtime_root,
                "error": str(exc),
            }
            print_payload(payload, args.format, render_status_markdown)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
