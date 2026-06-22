from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_DEFAULT_TASK,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
    build_terminal_bench_environment_setup_probe_gate,
    build_terminal_bench_result_finalization_gate,
    launch_terminal_bench_case_run,
    launch_terminal_bench_environment_setup_probe,
    launch_terminal_bench_worker_materialization_probe,
    poll_terminal_bench_worker_materialization_probe,
    resume_terminal_bench_materialized_job,
    summarize_terminal_bench_post_launch_materialization,
)
from ..status import compact_benchmark_run


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

TERMINAL_BENCH_ENVIRONMENT_RESULT_COMMANDS = {
    "environment-setup-gate",
    "launch-environment-setup-probe",
    "launch-worker-materialization-probe",
    "launch-terminal-bench-run",
    "poll-worker-materialization-probe",
    "result-finalization-gate",
    "resume-terminal-bench-job",
    "summarize-post-launch",
}


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




def register_terminal_bench_environment_result_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    benchmark_post_launch_parser = benchmark_subparsers.add_parser(
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

    benchmark_result_finalization_gate_parser = benchmark_subparsers.add_parser(
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


    benchmark_environment_setup_gate_parser = benchmark_subparsers.add_parser(
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

    benchmark_environment_setup_probe_launch_parser = benchmark_subparsers.add_parser(
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

    benchmark_worker_materialization_probe_launch_parser = benchmark_subparsers.add_parser(
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

    benchmark_case_run_launch_parser = benchmark_subparsers.add_parser(
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
            "codex-loopx",
            "loopx-managed-codex",
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

    benchmark_resume_terminal_bench_job_parser = benchmark_subparsers.add_parser(
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

    benchmark_worker_materialization_probe_poll_parser = benchmark_subparsers.add_parser(
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



def handle_terminal_bench_environment_result_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in TERMINAL_BENCH_ENVIRONMENT_RESULT_COMMANDS:
        return None

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

    return None
