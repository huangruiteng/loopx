from __future__ import annotations

import argparse
from collections.abc import Callable

from .contract import (
    application_receipt,
    maintenance_receipt,
    provider_doctor,
    recall,
)
from ...extensions.openviking_semantic_preference.provider import (
    handle_openviking_provider,
    register_openviking_provider_arguments,
)


def _render(payload: dict[str, object]) -> str:
    lines = ["# Semantic Preference", ""]
    for key in (
        "status",
        "surface",
        "outcome",
        "application_id",
        "provider_id",
        "available",
        "verified",
        "error",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload.get(key)}`")
    items = payload.get("items")
    if isinstance(items, list):
        lines.append(f"- item_count: `{len(items)}`")
    return "\n".join(lines) + "\n"


def register_semantic_preference_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "semantic-preference",
        help="Recall optional provider-owned preferences and build compact receipts.",
    )
    commands = parser.add_subparsers(dest="semantic_preference_command", required=True)
    recall_parser = commands.add_parser("recall")
    add_subcommand_format(recall_parser)
    recall_parser.add_argument("--config", required=True)
    recall_parser.add_argument("--project", default=".")
    recall_parser.add_argument("--surface", required=True)
    recall_parser.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="LOWER_SNAKE=VALUE",
        help="Repeatable bounded context entry, for example repository=owner/repo.",
    )
    recall_parser.add_argument("--execute", action="store_true")

    doctor_parser = commands.add_parser(
        "doctor",
        help="Inspect provider availability and configured setup hints without changing the host.",
    )
    add_subcommand_format(doctor_parser)
    doctor_parser.add_argument("--config", required=True)
    doctor_parser.add_argument("--project", default=".")
    doctor_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the optional read-only provider probe; never install, configure, or write credentials.",
    )

    provider_parser = commands.add_parser(
        "openviking-provider",
        help="Run the opt-in OpenViking project-as-peer provider protocol.",
    )
    register_openviking_provider_arguments(provider_parser)

    receipt_parser = commands.add_parser("receipt")
    add_subcommand_format(receipt_parser)
    receipt_parser.add_argument("--surface", required=True)
    receipt_parser.add_argument("--application-id", required=True)
    receipt_parser.add_argument(
        "--outcome", choices=["applied", "ignored", "failed"], required=True
    )
    receipt_parser.add_argument("--preference-ref", action="append", default=[])
    receipt_parser.add_argument("--artifact-ref")

    maintenance_parser = commands.add_parser(
        "maintenance-receipt",
        help=(
            "Build a compact receipt after a provider-owned corpus "
            "maintenance decision."
        ),
    )
    add_subcommand_format(maintenance_parser)
    maintenance_parser.add_argument(
        "--trigger",
        choices=["explicit_feedback", "source_truth_changed"],
        required=True,
    )
    maintenance_parser.add_argument(
        "--outcome",
        choices=["verified", "no_write_rationale", "failed"],
        required=True,
    )
    maintenance_parser.add_argument("--corpus-id", action="append", default=[])
    maintenance_parser.add_argument("--scope-ref", action="append", default=[])
    maintenance_parser.add_argument("--evidence-ref")


def handle_semantic_preference_command(
    args: argparse.Namespace,
    *,
    runtime_root_arg: str | None,
    output_format: Callable[..., str],
    print_payload: Callable[[dict[str, object], str, Callable], None],
) -> int | None:
    if args.command != "semantic-preference":
        return None
    if args.semantic_preference_command == "openviking-provider":
        return handle_openviking_provider(args)
    try:
        if args.semantic_preference_command == "recall":
            payload = recall(
                args.config,
                project=args.project,
                surface=args.surface,
                context=args.context,
                runtime_root=runtime_root_arg,
                execute=args.execute,
            )
        elif args.semantic_preference_command == "doctor":
            payload = provider_doctor(
                args.config,
                project=args.project,
                runtime_root=runtime_root_arg,
                execute=args.execute,
            )
        elif args.semantic_preference_command == "receipt":
            payload = application_receipt(
                surface=args.surface,
                application_id=args.application_id,
                outcome=args.outcome,
                preference_refs=args.preference_ref,
                artifact_ref=args.artifact_ref,
            )
        else:
            payload = maintenance_receipt(
                trigger=args.trigger,
                outcome=args.outcome,
                corpus_ids=args.corpus_id,
                scope_refs=args.scope_ref,
                evidence_ref=args.evidence_ref,
            )
    except ValueError as exc:
        payload = {
            "ok": False,
            "schema_version": "semantic_preference_error_v0",
            "status": "invalid_request",
            "error": str(exc),
        }
        print_payload(payload, output_format(args), _render)
        return 2
    print_payload(payload, output_format(args), _render)
    return 0
