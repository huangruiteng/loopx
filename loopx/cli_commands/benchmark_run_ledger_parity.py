from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_core import (
    build_codex_app_parity_posthoc_check,
    render_codex_app_parity_posthoc_check_markdown,
)
from ..status import compact_benchmark_run


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_RUN_LEDGER_PARITY_COMMANDS = {"parity-check"}


def register_benchmark_run_ledger_parity_commands(
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


def handle_benchmark_run_ledger_parity_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_RUN_LEDGER_PARITY_COMMANDS:
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
            output_format(args),
            lambda value: render_codex_app_parity_posthoc_check_markdown(
                value["codex_app_parity_posthoc_check"]
            ),
        )
        return 0 if payload.get("ok") else 1

    return None
