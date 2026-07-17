from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agents_last_exam import (
    build_agents_last_exam_result_benchmark_report,
)
from ..control_plane.runtime.benchmark_comparison import (
    compact_benchmark_comparison,
)
from ..control_plane.work_items.delivery_batch_scale import DELIVERY_BATCH_SCALE_CHOICES
from ..control_plane.work_items.delivery_outcome import DELIVERY_OUTCOME_CHOICES
from ..control_plane.runtime.trajectory_hygiene import build_trajectory_hygiene_summary
from ..global_registry import sync_project_registry_to_global
from ..history import (
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
    rebuild_index_artifact_collisions,
    render_active_user_assisted_pilot_append_markdown,
    render_benchmark_comparison_append_markdown,
    render_benchmark_experiment_report_append_markdown,
    render_benchmark_learning_ledger_append_markdown,
    render_benchmark_result_append_markdown,
    render_benchmark_run_append_markdown,
    render_history_markdown,
    render_index_duplicate_inspection_markdown,
    render_index_duplicate_repair_markdown,
    render_index_collision_rebuild_markdown,
)
from ..paths import resolve_runtime_root
from ..presentation.renderers.trajectory_hygiene_markdown import (
    render_trajectory_hygiene_markdown,
)
from ..status import (
    compact_active_user_assisted_pilot,
    compact_benchmark_experiment_report,
    compact_benchmark_learning_ledger,
    compact_benchmark_result,
    compact_benchmark_run,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
BenchmarkRolloutEventAppender = Callable[..., dict[str, object]]


def register_history_command(subparsers: argparse._SubParsersAction) -> None:
    history_parser = subparsers.add_parser(
        "history",
        help="Read compact run history from the shared runtime root.",
    )
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
            "rebuild-index-collisions",
            "trajectory-hygiene",
        ],
        help=(
            "Append a compact benchmark_run_v0, benchmark_result_v0, benchmark_comparison_v0, "
            "benchmark_learning_ledger_v0, benchmark_experiment_report_v0, ALE compact result report, or "
            "active_user_assisted_pilot_v0 event; inspect duplicate run-index identities; "
            "repair safe duplicate index rows; rebuild reviewed artifact collisions without deleting events; "
            "or audit compact-history trajectory hygiene."
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
    history_parser.add_argument(
        "--review-plan-json",
        help=(
            "For rebuild-index-collisions --execute, a JSON review plan emitted by the dry-run. "
            "Use '-' to read stdin."
        ),
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
    history_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview append without writing. This is the default.",
    )
    history_parser.add_argument(
        "--execute",
        action="store_true",
        help="Append or repair. Without this flag, history write actions are dry-run previews.",
    )
    history_parser.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Skip global registry sync after append.",
    )


def handle_history_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    print_payload: PrintPayload,
    append_benchmark_run_rollout_event: BenchmarkRolloutEventAppender,
    append_benchmark_result_rollout_event: BenchmarkRolloutEventAppender,
) -> int:
    if args.history_action == "trajectory-hygiene":
        try:
            if not args.goal_id:
                raise ValueError("history trajectory-hygiene requires --goal-id")
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(
                registry,
                runtime_root_arg,
                registry_path=registry_path,
            )
            history = collect_history(
                registry_path=registry_path,
                runtime_root=runtime_root,
                goal_id=args.goal_id,
                limit=max(0, args.limit),
            )
            payload = build_trajectory_hygiene_summary(history)
            payload["registry"] = str(registry_path)
            payload["runtime_root"] = str(runtime_root)
        except Exception as exc:
            payload = {
                "ok": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
                "goal_filter": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_trajectory_hygiene_markdown)
        return 0 if payload.get("ok") else 1

    if args.history_action == "inspect-index-duplicates":
        try:
            payload = inspect_index_duplicates(
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
                goal_id=args.goal_id,
                limit=args.limit,
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(
                registry,
                runtime_root_arg,
                registry_path=registry_path,
            )
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
                runtime_root_override=runtime_root_arg,
                goal_id=args.goal_id,
                limit=args.limit,
                execute=bool(args.execute),
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(
                registry,
                runtime_root_arg,
                registry_path=registry_path,
            )
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

    if args.history_action == "rebuild-index-collisions":
        try:
            if args.dry_run and args.execute:
                raise ValueError(
                    "history rebuild-index-collisions accepts either --dry-run or --execute, not both"
                )
            reviewed_plan = None
            if args.review_plan_json:
                raw_plan = (
                    sys.stdin.read()
                    if args.review_plan_json == "-"
                    else Path(args.review_plan_json).expanduser().read_text(encoding="utf-8")
                )
                reviewed_plan = json.loads(raw_plan)
                if not isinstance(reviewed_plan, dict):
                    raise ValueError("--review-plan-json must contain a JSON object")
            payload = rebuild_index_artifact_collisions(
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
                goal_id=args.goal_id,
                limit=args.limit,
                reviewed_plan=reviewed_plan,
                execute=bool(args.execute),
            )
        except Exception as exc:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(
                registry,
                runtime_root_arg,
                registry_path=registry_path,
            )
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "registry": str(registry_path),
                "runtime_root": str(runtime_root),
                "goal_filter": args.goal_id,
                "error": str(exc),
            }
        print_payload(payload, args.format, render_index_collision_rebuild_markdown)
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
            append_benchmark_run_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                command="history",
                action="append-benchmark-run",
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
            append_benchmark_result_rollout_event(
                payload,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                command="history",
                action="append-benchmark-result",
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
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
                runtime_root_override=runtime_root_arg,
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
                    runtime_root_override=runtime_root_arg,
                    goal_id=args.goal_id,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "appended": False,
                "registry": str(registry_path),
                "runtime_root": runtime_root_arg,
                "goal_id": args.goal_id,
                "classification": args.classification or "active_user_assisted_pilot_v0",
                "error": str(exc),
            }
        print_payload(payload, args.format, render_active_user_assisted_pilot_append_markdown)
        return 0 if payload.get("ok") else 1

    try:
        registry = load_registry(registry_path)
        runtime_root = resolve_runtime_root(
            registry,
            runtime_root_arg,
            registry_path=registry_path,
        )
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
            "runtime_root": runtime_root_arg,
            "error": str(exc),
        }
    print_payload(payload, args.format, render_history_markdown)
    return 0 if payload.get("ok") else 1
