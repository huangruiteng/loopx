from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..worker_bridge import (
    DEFAULT_ACTIVE_USER_CODEX_BIN,
    DEFAULT_ACTIVE_USER_SIMULATOR_CONTEXT_DIR,
    DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_JSON,
    DEFAULT_ACTIVE_USER_SIMULATOR_OUTPUT_SCHEMA_JSON,
    DEFAULT_ACTIVE_USER_SIMULATOR_PROMPT_JSON,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    DEFAULT_WORKER_BRIDGE_MODULE,
    DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
    DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
    LOOPX_PROJECT_ROOT_PLACEHOLDER,
    LOOPX_RUNTIME_ROOT_PLACEHOLDER,
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


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

WORKER_BRIDGE_COMMANDS = {
    "active-user-codex-simulator-contract",
    "active-user-contract",
    "active-user-intervention",
    "active-user-observe",
    "active-user-simulator-output",
    "benchmark-run",
    "contract",
    "outcome",
}


def _add_worker_bridge_outcome_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--worker-cli-call-total",
        type=int,
        default=0,
        help="Compact count of in-worker LoopX CLI calls.",
    )
    parser.add_argument(
        "--required-worker-cli-call-total-min",
        type=int,
        default=1,
        help="Minimum worker CLI call count required to claim bridge verification.",
    )
    parser.add_argument(
        "--counter-trace-present",
        action="store_true",
        help="Whether a compact worker counter trace was observed.",
    )
    parser.add_argument(
        "--runner-return-completed",
        action="store_true",
        help="Whether the runner returned a completed case result.",
    )
    parser.add_argument(
        "--official-score-completed",
        action="store_true",
        help="Whether an official task score is available.",
    )
    parser.add_argument(
        "--official-score-value",
        type=float,
        help="Official task score value when --official-score-completed is set.",
    )
    parser.add_argument(
        "--interrupted",
        action="store_true",
        help="Whether the controller interrupted the worker run.",
    )
    parser.add_argument(
        "--interrupt-reason",
        default="",
        help="Public-safe interrupt reason label.",
    )
    parser.add_argument(
        "--wall-time-seconds",
        type=float,
        help="Observed wall time in seconds, if available.",
    )
    parser.add_argument(
        "--wall-time-limit-seconds",
        type=float,
        default=DEFAULT_WORKER_BRIDGE_WALL_TIME_LIMIT_SECONDS,
        help="Controller wall-time limit for this worker bridge outcome.",
    )
    parser.add_argument(
        "--side-effect-audit-failed",
        action="store_true",
        help="Mark the side-effect audit as failed.",
    )


def register_worker_bridge_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    worker_bridge_parser = subparsers.add_parser(
        "worker-bridge",
        help="Render runner-agnostic worker bridge/install contracts.",
    )
    worker_bridge_sub = worker_bridge_parser.add_subparsers(
        dest="worker_bridge_command"
    )

    worker_bridge_contract_parser = worker_bridge_sub.add_parser(
        "contract",
        help="Render a LoopX worker bridge/install contract.",
    )
    add_subcommand_format(worker_bridge_contract_parser)
    worker_bridge_contract_parser.add_argument(
        "--project-root",
        default=LOOPX_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible LoopX project root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--runtime-root",
        dest="worker_bridge_runtime_root",
        default=LOOPX_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible LoopX runtime root. Defaults to a public placeholder.",
    )
    worker_bridge_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    worker_bridge_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="LoopX CLI module import path.",
    )
    worker_bridge_contract_parser.add_argument(
        "--scan-path",
        help="Container-visible public scan path. Defaults to the LoopX benchmark module.",
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
    _add_worker_bridge_outcome_args(worker_bridge_outcome_parser)

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
        default="loopx_worker_bridge_sample",
        help="Public-safe job name.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--mode",
        dest="worker_bridge_benchmark_mode",
        default="codex_loopx_active_worker",
        help="Benchmark treatment mode.",
    )
    worker_bridge_benchmark_run_parser.add_argument(
        "--worker-mode",
        default="codex_loopx_cli",
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
    _add_worker_bridge_outcome_args(worker_bridge_benchmark_run_parser)

    active_user_contract_parser = worker_bridge_sub.add_parser(
        "active-user-contract",
        help="Render the active-user simulator external-update channel contract.",
    )
    add_subcommand_format(active_user_contract_parser)
    active_user_contract_parser.add_argument(
        "--project-root",
        default=LOOPX_PROJECT_ROOT_PLACEHOLDER,
        help="Container-visible LoopX project root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--runtime-root",
        dest="active_user_runtime_root",
        default=LOOPX_RUNTIME_ROOT_PLACEHOLDER,
        help="Container-visible LoopX runtime root. Defaults to a public placeholder.",
    )
    active_user_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable inside the worker environment.",
    )
    active_user_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="LoopX CLI module import path.",
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
        default=LOOPX_PROJECT_ROOT_PLACEHOLDER,
        help="LoopX project root visible to the simulator launcher.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--python-bin",
        default=DEFAULT_WORKER_BRIDGE_PYTHON_BIN,
        help="Python executable used to append the validated simulator output.",
    )
    active_user_codex_simulator_contract_parser.add_argument(
        "--module",
        default=DEFAULT_WORKER_BRIDGE_MODULE,
        help="LoopX CLI module import path.",
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
        default="codex_loopx_active_worker",
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


def handle_worker_bridge_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.command != "worker-bridge":
        return None

    if args.worker_bridge_command not in WORKER_BRIDGE_COMMANDS:
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
        print_payload(
            payload,
            output_format(args),
            render_worker_bridge_install_contract_markdown,
        )
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
                worker_loopx_cli_call_total=args.worker_cli_call_total,
                counter_trace_present=bool(args.counter_trace_present),
                runner_return_completed=bool(args.runner_return_completed),
                official_score_completed=bool(args.official_score_completed),
                official_score_value=args.official_score_value,
                interrupted=bool(args.interrupted),
                interrupt_reason=args.interrupt_reason,
                wall_time_seconds=args.wall_time_seconds,
                wall_time_limit_seconds=args.wall_time_limit_seconds,
                required_worker_loopx_cli_call_total_min=(
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
                worker_loopx_cli_call_total=args.worker_cli_call_total,
                counter_trace_present=bool(args.counter_trace_present),
                runner_return_completed=bool(args.runner_return_completed),
                official_score_completed=bool(args.official_score_completed),
                official_score_value=args.official_score_value,
                interrupted=bool(args.interrupted),
                interrupt_reason=args.interrupt_reason,
                wall_time_seconds=args.wall_time_seconds,
                wall_time_limit_seconds=args.wall_time_limit_seconds,
                required_worker_loopx_cli_call_total_min=(
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
                    Path(args.simulator_output_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
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
                interaction_counters = build_worker_bridge_interaction_counters_from_trace(
                    trace_rows
                )
                checkpoint = build_worker_bridge_benchmark_run_from_counters(
                    interaction_counters,
                    counter_trace_present=bool(trace_rows),
                    source_runner="worker_bridge_active_user_observe",
                    benchmark_id="worker-bridge-active-user@v0",
                    job_name="loopx_active_user_observe_checkpoint",
                    mode=args.bridge_mode,
                    task_id=args.task_id,
                    trial_name=args.trial_name,
                )
                checkpoint["worker_bridge_checkpoint"] = {
                    "schema_version": "loopx_worker_bridge_checkpoint_v0",
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
                payload["benchmark_run_checkpoint_schema_version"] = checkpoint.get(
                    "schema_version"
                )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "worker-bridge",
            "error": str(exc),
        }
    print_payload(
        payload,
        output_format(args),
        render_worker_bridge_install_contract_markdown,
    )
    return 0 if payload.get("ok") else 1
