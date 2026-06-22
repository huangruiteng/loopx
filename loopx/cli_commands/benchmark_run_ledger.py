from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.skillsbench import (
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_ROUTE,
    SKILLSBENCH_DEFAULT_TASK,
    SKILLSBENCH_ROUTES,
    build_skillsbench_benchmark_run,
    build_skillsbench_benchflow_result_benchmark_run,
    skillsbench_recommended_action,
)
from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_DEFAULT_TASK,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE,
    TERMINAL_BENCH_MODES,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_harbor_result_benchmark_run,
    collect_terminal_bench_loopx_cli_bridge_trace,
    terminal_bench_recommended_action,
)
from ..benchmark_case_analysis import (
    apply_accepted_case_analysis_records,
    build_case_analysis_candidate_report,
    load_json as load_benchmark_case_analysis_json,
    render_case_analysis_candidate_report_markdown,
    render_case_analysis_markdown,
)
from ..benchmark_core import (
    build_codex_app_parity_posthoc_check,
    render_codex_app_parity_posthoc_check_markdown,
)
from ..benchmark_ledger import (
    BENCHMARK_RUN_LEDGER_DEFAULT_PATH,
    check_benchmark_run_ledger_drift,
    load_benchmark_run_ledger,
    update_benchmark_run_ledger,
)
from ..delivery_outcome import DELIVERY_OUTCOME_CHOICES
from ..global_registry import sync_project_registry_to_global
from ..history import (
    append_benchmark_run,
    collect_history,
    load_registry,
    render_benchmark_run_append_markdown,
)
from ..paths import resolve_runtime_root
from ..state_refresh import DELIVERY_BATCH_SCALE_CHOICES
from ..status import (
    compact_benchmark_post_launch_materialization,
    compact_benchmark_run,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]
AppendBenchmarkRunRolloutEvent = Callable[..., dict[str, object]]

BENCHMARK_RUN_LEDGER_COMMANDS = {
    "case-analysis-candidates",
    "parity-check",
    "run",
    "run-ledger-check",
    "run-ledger-upsert",
}


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
            + (
                "\n## Accepted Upsert\n\n"
                f"- output_written: `{payload['accepted_upsert'].get('output_written')}`\n"
                f"- markdown_written: `{payload['accepted_upsert'].get('markdown_written')}`\n"
                f"- added_count: `{payload['accepted_upsert'].get('added_count')}`\n"
                f"- skipped_count: `{payload['accepted_upsert'].get('skipped_count')}`\n"
                if isinstance(payload.get("accepted_upsert"), dict)
                else ""
            )
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




def register_benchmark_run_ledger_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    benchmark_parity_check_parser = benchmark_subparsers.add_parser(
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

    benchmark_run_parser = benchmark_subparsers.add_parser(
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
        default="loopx-managed-codex",
        help="Terminal-Bench worker mode. Defaults to the managed LoopX treatment.",
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
            "Default is loopx-blind-loop-treatment: ordinary Codex "
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
            "Execute the host-agent LoopX CLI bridge contract fixture for "
            "codex-loopx. This runs LoopX CLI read commands and an "
            "append-benchmark-run dry-run only; no Harbor, Terminal-Bench, Codex "
            "worker, model API, or upload is invoked."
        ),
    )
    benchmark_run_parser.add_argument(
        "--worker-cli-bridge-fixture",
        action="store_true",
        help=(
            "Build the codex-loopx worker in-case CLI bridge fixture. "
            "This records worker-side LoopX call counters separately "
            "from runner bridge calls and does not run Harbor, Terminal-Bench, "
            "Codex workers, model APIs, or uploads."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-cli-bridge",
        action="store_true",
        help=(
            "With codex-loopx --preflight-guard, build the private no-upload "
            "repeat preflight that enables the worker LoopX CLI bridge and "
            "requires worker-side CLI call counters before any in-case use claim."
        ),
    )
    benchmark_run_parser.add_argument(
        "--active-user-assisted-treatment",
        action="store_true",
        help=(
            "With codex-loopx --preflight-guard --active-cli-bridge, build "
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

    benchmark_run_ledger_upsert_parser = benchmark_subparsers.add_parser(
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
    benchmark_run_ledger_check_parser = benchmark_subparsers.add_parser(
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
    benchmark_case_analysis_candidates_parser = benchmark_subparsers.add_parser(
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
    benchmark_case_analysis_candidates_parser.add_argument(
        "--include-proposed-records",
        action="store_true",
        help=(
            "Include proposal-only benchmark_case_analysis_v0 record drafts. "
            "This does not edit the case-analysis file."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--proposal-limit",
        type=int,
        default=None,
        help="Maximum proposal records to include when --include-proposed-records is set.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--acceptance-policy",
        choices=("proposal-only", "generated-safe"),
        default="proposal-only",
        help=(
            "Policy for proposed records. generated-safe marks only narrow, "
            "compact-ledger-derived records as accepted for explicit upsert."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--apply-accepted",
        action="store_true",
        help=(
            "Apply accepted generated-safe records to --output-case-analysis-path. "
            "This never reads raw logs/task text/trajectories."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--output-case-analysis-path",
        default=None,
        help="Output path for --apply-accepted. Required when applying.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--output-case-analysis-markdown-path",
        default=None,
        help=(
            "Optional Markdown output path for --apply-accepted. The generated "
            "summary/table is refreshed from compact JSON and existing deep "
            "case notes are preserved when available."
        ),
    )



def handle_benchmark_run_ledger_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
    output_format: OutputFormat,
    append_benchmark_run_rollout_event: AppendBenchmarkRunRolloutEvent,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_RUN_LEDGER_COMMANDS:
        return None

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
            if (
                args.apply_accepted
                and args.acceptance_policy != "generated-safe"
            ):
                raise ValueError(
                    "--apply-accepted requires --acceptance-policy generated-safe"
                )
            if args.apply_accepted and not args.output_case_analysis_path:
                raise ValueError(
                    "--apply-accepted requires --output-case-analysis-path"
                )
            ledger = load_benchmark_case_analysis_json(args.run_ledger_path)
            analysis = load_benchmark_case_analysis_json(
                args.case_analysis_path
            )
            report = build_case_analysis_candidate_report(
                ledger=ledger,
                analysis=analysis,
                include_proposed_records=(
                    args.include_proposed_records or args.apply_accepted
                ),
                proposal_limit=args.proposal_limit,
                acceptance_policy=args.acceptance_policy,
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
            if args.apply_accepted:
                result = apply_accepted_case_analysis_records(
                    analysis=analysis,
                    records=report.get("proposed_records", []),
                )
                output_path = Path(args.output_case_analysis_path)
                output_path.write_text(
                    json.dumps(
                        result["analysis"],
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                markdown_written = False
                if args.output_case_analysis_markdown_path:
                    markdown_path = Path(args.output_case_analysis_markdown_path)
                    existing_markdown = None
                    if markdown_path.exists():
                        existing_markdown = markdown_path.read_text(
                            encoding="utf-8"
                        )
                    else:
                        default_markdown_path = Path(
                            args.case_analysis_path
                        ).with_suffix(".md")
                        if default_markdown_path.exists():
                            existing_markdown = default_markdown_path.read_text(
                                encoding="utf-8"
                            )
                    markdown_path.write_text(
                        render_case_analysis_markdown(
                            result["analysis"],
                            existing_markdown=existing_markdown,
                        ),
                        encoding="utf-8",
                    )
                    markdown_written = True
                payload["accepted_upsert"] = {
                    "output_written": True,
                    "markdown_written": markdown_written,
                    "added_count": result["added_count"],
                    "skipped_count": result["skipped_count"],
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
                    "terminal_bench_codex_loopx_active_cli_bridge_preflight_v0"
                    if args.active_cli_bridge
                    else
                    "terminal_bench_codex_loopx_worker_cli_bridge_fixture_v0"
                    if args.worker_cli_bridge_fixture
                    else
                    "terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture_v0"
                    if args.cli_bridge_contract
                    else (
                        (
                            "terminal_bench_codex_loopx_preflight_guard_v0"
                            if args.mode == "codex-loopx"
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
                                "terminal_bench_codex_loopx_fake_worker_v0"
                                if args.mode == "codex-loopx"
                                else "terminal_bench_cli_fake_worker_v0"
                            )
                            if args.fake_worker
                            else (
                                "terminal_bench_codex_loopx_dry_run_v0"
                                if args.mode == "codex-loopx"
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
                cli_bridge_trace = collect_terminal_bench_loopx_cli_bridge_trace(
                    goal_id=args.goal_id,
                    registry=str(registry_path),
                    runtime_root=str(runtime_root),
                    command_prefix=[sys.executable, "-m", "loopx.cli"],
                    scan_path="loopx/benchmark.py",
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
                    "terminal_bench_codex_loopx_worker_cli_bridge_fixture_v0"
                    if getattr(args, "worker_cli_bridge_fixture", False)
                    else
                    "terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture_v0"
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


    return None
