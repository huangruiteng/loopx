from __future__ import annotations

import argparse
from collections.abc import Callable

from .contract import application_receipt, recall
from .openviking_provider import (
    handle_openviking_provider,
    register_openviking_provider_arguments,
)


def _render(payload: dict[str, object]) -> str:
    lines = ["# Semantic Preference", ""]
    for key in ("status", "surface", "outcome", "application_id"):
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
    recall_parser.add_argument("--context", action="append", default=[])
    recall_parser.add_argument("--execute", action="store_true")

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


def handle_semantic_preference_command(
    args: argparse.Namespace,
    *,
    output_format: Callable[..., str],
    print_payload: Callable[[dict[str, object], str, Callable], None],
) -> int | None:
    if args.command != "semantic-preference":
        return None
    if args.semantic_preference_command == "openviking-provider":
        return handle_openviking_provider(args)
    if args.semantic_preference_command == "recall":
        payload = recall(
            args.config,
            project=args.project,
            surface=args.surface,
            context=args.context,
            execute=args.execute,
        )
    else:
        payload = application_receipt(
            surface=args.surface,
            application_id=args.application_id,
            outcome=args.outcome,
            preference_refs=args.preference_ref,
            artifact_ref=args.artifact_ref,
        )
    print_payload(payload, output_format(args), _render)
    return 0
