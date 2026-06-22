from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..benchmark import (
    build_benchmark_adapter_kwarg_absorption_review,
    build_benchmark_attempt_learning_gate,
    build_benchmark_claim_review,
    build_benchmark_learning_ledger,
    build_benchmark_lifecycle_state,
)
from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_MANAGED_CODEX_LOOPX_KWARGS,
    agent_kwargs_from_invocation,
)
from ..status import (
    compact_benchmark_comparison,
    compact_benchmark_learning_ledger,
    compact_benchmark_post_launch_materialization,
    compact_benchmark_run,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_REVIEW_LIFECYCLE_COMMANDS = {
    "review-claim",
    "learning-ledger",
    "attempt-learning-gate",
    "review-adapter-kwargs",
    "lifecycle-state",
}


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
        f"- Treatment worker GH calls: `{treatment.get('worker_loopx_cli_call_total')}`",
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
        f"- Generated GH kwargs: `{payload.get('generated_loopx_kwarg_count')}`",
        f"- Absorbed GH kwargs: `{payload.get('absorbed_loopx_kwarg_count')}`",
        f"- Leaked GH kwargs: `{payload.get('leaked_loopx_kwarg_count')}`",
        f"- Leaked keys: `{payload.get('leaked_loopx_kwarg_keys')}`",
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



def register_benchmark_review_lifecycle_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    benchmark_claim_review_parser = benchmark_subparsers.add_parser(
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

    benchmark_learning_ledger_parser = benchmark_subparsers.add_parser(
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
            "LoopX learning signal, such as a repair candidate or clean "
            "score-recovery evidence."
        ),
    )

    benchmark_attempt_learning_gate_parser = benchmark_subparsers.add_parser(
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

    benchmark_adapter_kwarg_review_parser = benchmark_subparsers.add_parser(
        "review-adapter-kwargs",
        help=(
            "Review generated benchmark adapter kwargs and flag loopx_* "
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
        "--accepted-loopx-kwarg",
        action="append",
        default=[],
        help=(
            "LoopX kwarg key explicitly consumed by the adapter. Repeat "
            "as needed unless --terminal-bench-managed-codex is used."
        ),
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--allowed-base-passthrough",
        action="append",
        default=[],
        help="Optional loopx_* kwarg key allowed to pass to the base constructor.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--terminal-bench-managed-codex",
        action="store_true",
        help="Use the built-in GoalHarnessManagedCodex accepted kwarg contract.",
    )
    benchmark_adapter_kwarg_review_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero unless all generated loopx_* kwargs are absorbed.",
    )

    benchmark_lifecycle_state_parser = benchmark_subparsers.add_parser(
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



def handle_benchmark_review_lifecycle_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_REVIEW_LIFECYCLE_COMMANDS:
        return None

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
                    or "missing_actionable_loopx_learning_signal"
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
            accepted = list(args.accepted_loopx_kwarg)
            if args.terminal_bench_managed_codex:
                accepted.extend(TERMINAL_BENCH_MANAGED_CODEX_LOOPX_KWARGS)
            payload = build_benchmark_adapter_kwarg_absorption_review(
                adapter_label=args.adapter_label,
                agent_kwargs=agent_kwargs,
                accepted_loopx_kwargs=accepted,
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
