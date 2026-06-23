from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..benchmark import (
    build_benchmark_adapter_kwarg_absorption_review,
    build_benchmark_attempt_learning_gate,
    build_benchmark_baseline_failure_gate_comparison,
    build_benchmark_claim_review,
    build_benchmark_learning_ledger,
    build_benchmark_lifecycle_state,
    build_benchmark_runner_invariant_review,
    build_benchmark_verifier_attribution_review,
    benchmark_result_from_benchmark_run_for_baseline_gate,
)
from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_MANAGED_CODEX_LOOPX_KWARGS,
    agent_kwargs_from_invocation,
)
from ..delivery_batch_scale import DELIVERY_BATCH_SCALE_CHOICES
from ..delivery_outcome import DELIVERY_OUTCOME_CHOICES
from ..global_registry import sync_project_registry_to_global
from ..history import append_benchmark_comparison
from ..status import (
    compact_benchmark_comparison,
    compact_benchmark_learning_ledger,
    compact_benchmark_result,
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
    "baseline-failure-gate",
    "review-adapter-kwargs",
    "lifecycle-state",
    "review-runner-invariants",
    "review-verifier-attribution",
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
        lines.append(
            f"- negative_selection_reason: {gate.get('negative_selection_reason')}"
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
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

    benchmark_baseline_gate_parser = benchmark_subparsers.add_parser(
        "baseline-failure-gate",
        help=(
            "Reduce a compact goal-mode baseline benchmark_result_v0 or "
            "benchmark_run_v0 into a benchmark_comparison_v0 baseline-failure "
            "gate. This reads only compact JSON, not raw task text, logs, "
            "traces, Harbor job directories, Docker, model APIs, uploads, "
            "screenshots, or credentials."
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
        default="codex_loopx",
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
        help=(
            "Mark the baseline failure as plausibly fixable by LoopX "
            "control-plane intervention."
        ),
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
    benchmark_baseline_gate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing. This is the default.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--execute",
        action="store_true",
        help="Append the compact baseline gate comparison.",
    )
    benchmark_baseline_gate_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Skip global registry sync after append.",
    )

    benchmark_verifier_attribution_parser = benchmark_subparsers.add_parser(
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

    benchmark_runner_invariant_parser = benchmark_subparsers.add_parser(
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



def handle_benchmark_review_lifecycle_command(
    args: argparse.Namespace,
    *,
    registry_path: Path | None = None,
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
    if args.benchmark_command == "review-verifier-attribution":
        try:
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
                    "raw_artifacts_read": args.expect_raw_artifacts_read == "true",
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
            if args.execute and registry_path is None:
                raise ValueError(
                    "benchmark baseline-failure-gate requires registry_path with --execute"
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
                    baseline_result = benchmark_result_from_benchmark_run_for_baseline_gate(
                        benchmark_run
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
                    classification=args.classification or "benchmark_comparison_v0",
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
