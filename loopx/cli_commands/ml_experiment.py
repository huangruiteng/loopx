from __future__ import annotations

import argparse
from collections.abc import Callable

from ..ml_experiment import (
    GUARDRAIL_STATUSES,
    HYPOTHESIS_STATUSES,
    VOLC_MLP_TASK_STATES,
    build_ml_experiment_advisory_packet,
    build_volc_mlp_result_ledger,
    build_volc_mlp_task_packet,
    render_ml_experiment_advisory_markdown,
    render_volc_mlp_result_ledger_markdown,
    render_volc_mlp_task_packet_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_ml_experiment_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    ml_experiment_parser = subparsers.add_parser(
        "ml-experiment",
        help="Render default-off ML experiment advisory packets.",
    )
    ml_experiment_sub = ml_experiment_parser.add_subparsers(dest="ml_experiment_command", required=True)
    preview_parser = ml_experiment_sub.add_parser(
        "preview",
        help="Preview a public-safe ML experiment result, hypothesis ledger, and replan packet.",
    )
    add_subcommand_format(preview_parser)
    preview_parser.add_argument("--experiment-id", required=True, help="Public experiment id.")
    preview_parser.add_argument("--primary-metric", required=True, help="Primary metric label.")
    preview_parser.add_argument("--baseline-value", type=float, required=True)
    preview_parser.add_argument("--candidate-value", type=float, required=True)
    metric_direction = preview_parser.add_mutually_exclusive_group()
    metric_direction.add_argument(
        "--higher-is-better",
        dest="higher_is_better",
        action="store_true",
        default=True,
        help="Classify positive metric deltas as improvements. This is the default.",
    )
    metric_direction.add_argument(
        "--lower-is-better",
        dest="higher_is_better",
        action="store_false",
        help="Classify negative metric deltas as improvements.",
    )
    preview_parser.add_argument(
        "--guardrail-status",
        choices=GUARDRAIL_STATUSES,
        default="unknown",
        help="Compact guardrail classification.",
    )
    preview_parser.add_argument("--train-window", required=True)
    preview_parser.add_argument("--eval-window", required=True)
    preview_parser.add_argument("--granularity", default="daily")
    preview_parser.add_argument("--hypothesis-id", required=True)
    preview_parser.add_argument("--mechanism-family", required=True)
    preview_parser.add_argument("--route", required=True)
    preview_parser.add_argument(
        "--hypothesis-status",
        choices=HYPOTHESIS_STATUSES,
        default="active",
    )
    preview_parser.add_argument(
        "--positive-evidence",
        action="append",
        default=[],
        help="Compact public-safe evidence label. Repeatable.",
    )
    preview_parser.add_argument(
        "--negative-evidence",
        action="append",
        default=[],
        help="Compact public-safe evidence label. Repeatable.",
    )
    preview_parser.add_argument(
        "--next-candidate",
        action="append",
        default=[],
        help="Compact public-safe follow-up candidate label. Repeatable.",
    )

    volc_parser = ml_experiment_sub.add_parser(
        "volc-task-packet",
        help="Render a public-safe Volc/MLP external task packet.",
    )
    add_subcommand_format(volc_parser)
    volc_parser.add_argument("--task-id", required=True, help="Volc task id, for example t-... .")
    volc_parser.add_argument("--task-name", required=True, help="Compact public task label.")
    volc_parser.add_argument("--state", choices=VOLC_MLP_TASK_STATES, default="Unknown")
    volc_parser.add_argument("--priority", type=int)
    volc_parser.add_argument("--retried-times", type=int)
    volc_parser.add_argument("--train-window", required=True)
    volc_parser.add_argument("--eval-window", required=True)
    volc_parser.add_argument("--code-ref", required=True, help="Branch, commit, or other public code alias.")
    volc_parser.add_argument("--model-name", required=True)
    volc_parser.add_argument("--mechanism-family", default="unknown")
    volc_parser.add_argument("--source-task-id")
    volc_parser.add_argument(
        "--workspace-ref",
        help="Optional workspace handle. Raw paths or URLs are redacted in output.",
    )
    volc_parser.add_argument(
        "--metric-ref",
        action="append",
        default=[],
        help="Optional metric artifact handle. Raw paths or URLs are redacted in output. Repeatable.",
    )
    volc_parser.add_argument("--primary-metric", default="offline_auc")
    volc_parser.add_argument(
        "--guardrail-metric",
        action="append",
        default=[],
        help="Compact guardrail metric label. Repeatable.",
    )
    volc_parser.add_argument("--next-action", default="monitor_task_until_terminal_metrics")

    volc_result_parser = ml_experiment_sub.add_parser(
        "volc-result-ledger",
        help="Render a public-safe Volc/MLP benchmark result ledger row.",
    )
    add_subcommand_format(volc_result_parser)
    volc_result_parser.add_argument("--experiment-id", required=True)
    volc_result_parser.add_argument("--task-id", required=True, help="Volc task id, for example t-... .")
    volc_result_parser.add_argument("--task-name", required=True, help="Compact public task label.")
    volc_result_parser.add_argument("--state", choices=VOLC_MLP_TASK_STATES, default="Unknown")
    volc_result_parser.add_argument("--priority", type=int)
    volc_result_parser.add_argument("--retried-times", type=int)
    volc_result_parser.add_argument("--train-window", required=True)
    volc_result_parser.add_argument("--eval-window", required=True)
    volc_result_parser.add_argument("--code-ref", required=True, help="Branch, commit, or other public code alias.")
    volc_result_parser.add_argument("--model-name", required=True)
    volc_result_parser.add_argument("--mechanism-family", default="unknown")
    volc_result_parser.add_argument("--primary-metric", default="offline_auc")
    volc_result_parser.add_argument("--baseline-value", type=float)
    volc_result_parser.add_argument("--candidate-value", type=float)
    result_metric_direction = volc_result_parser.add_mutually_exclusive_group()
    result_metric_direction.add_argument(
        "--higher-is-better",
        dest="higher_is_better",
        action="store_true",
        default=True,
        help="Classify positive metric deltas as improvements. This is the default.",
    )
    result_metric_direction.add_argument(
        "--lower-is-better",
        dest="higher_is_better",
        action="store_false",
        help="Classify negative metric deltas as improvements.",
    )
    volc_result_parser.add_argument(
        "--guardrail-status",
        choices=GUARDRAIL_STATUSES,
        default="unknown",
    )
    volc_result_parser.add_argument("--baseline-task-id")
    volc_result_parser.add_argument("--source-task-id")
    volc_result_parser.add_argument(
        "--workspace-ref",
        help="Optional workspace handle. Raw paths or URLs are redacted in output.",
    )
    volc_result_parser.add_argument(
        "--metric-ref",
        action="append",
        default=[],
        help="Optional metric artifact handle. Raw paths or URLs are redacted in output. Repeatable.",
    )
    volc_result_parser.add_argument(
        "--guardrail-metric",
        action="append",
        default=[],
        help="Compact guardrail metric label. Repeatable.",
    )
    volc_result_parser.add_argument(
        "--positive-evidence",
        action="append",
        default=[],
        help="Compact public-safe evidence label. Repeatable.",
    )
    volc_result_parser.add_argument(
        "--negative-evidence",
        action="append",
        default=[],
        help="Compact public-safe evidence label. Repeatable.",
    )
    volc_result_parser.add_argument(
        "--failure-label",
        action="append",
        default=[],
        help="Compact public-safe failure attribution label. Repeatable.",
    )
    volc_result_parser.add_argument("--next-action")


def handle_ml_experiment_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.ml_experiment_command == "preview":
            payload = build_ml_experiment_advisory_packet(
                experiment_id=args.experiment_id,
                primary_metric=args.primary_metric,
                baseline_value=args.baseline_value,
                candidate_value=args.candidate_value,
                higher_is_better=bool(args.higher_is_better),
                guardrail_status=args.guardrail_status,
                train_window=args.train_window,
                eval_window=args.eval_window,
                granularity=args.granularity,
                hypothesis_id=args.hypothesis_id,
                mechanism_family=args.mechanism_family,
                route=args.route,
                hypothesis_status=args.hypothesis_status,
                positive_evidence=args.positive_evidence,
                negative_evidence=args.negative_evidence,
                next_candidates=args.next_candidate,
            )
            renderer = render_ml_experiment_advisory_markdown
        elif args.ml_experiment_command == "volc-task-packet":
            payload = build_volc_mlp_task_packet(
                task_id=args.task_id,
                task_name=args.task_name,
                state=args.state,
                priority=args.priority,
                retried_times=args.retried_times,
                train_window=args.train_window,
                eval_window=args.eval_window,
                code_ref=args.code_ref,
                model_name=args.model_name,
                mechanism_family=args.mechanism_family,
                source_task_id=args.source_task_id,
                workspace_ref=args.workspace_ref,
                metric_refs=args.metric_ref,
                primary_metric=args.primary_metric,
                guardrail_metrics=args.guardrail_metric,
                next_action=args.next_action,
            )
            renderer = render_volc_mlp_task_packet_markdown
        elif args.ml_experiment_command == "volc-result-ledger":
            payload = build_volc_mlp_result_ledger(
                experiment_id=args.experiment_id,
                task_id=args.task_id,
                task_name=args.task_name,
                state=args.state,
                priority=args.priority,
                retried_times=args.retried_times,
                train_window=args.train_window,
                eval_window=args.eval_window,
                code_ref=args.code_ref,
                model_name=args.model_name,
                mechanism_family=args.mechanism_family,
                primary_metric=args.primary_metric,
                baseline_value=args.baseline_value,
                candidate_value=args.candidate_value,
                higher_is_better=bool(args.higher_is_better),
                guardrail_status=args.guardrail_status,
                baseline_task_id=args.baseline_task_id,
                source_task_id=args.source_task_id,
                workspace_ref=args.workspace_ref,
                metric_refs=args.metric_ref,
                guardrail_metrics=args.guardrail_metric,
                positive_evidence=args.positive_evidence,
                negative_evidence=args.negative_evidence,
                failure_labels=args.failure_label,
                next_action=args.next_action,
            )
            renderer = render_volc_mlp_result_ledger_markdown
        else:
            raise ValueError("ml-experiment requires a supported subcommand")
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "ml-experiment",
            "error": str(exc),
        }
        renderer = render_ml_experiment_advisory_markdown
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
