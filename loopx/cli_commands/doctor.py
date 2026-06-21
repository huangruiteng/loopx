from __future__ import annotations

import argparse
from collections.abc import Callable

from ..doctor import collect_doctor, render_doctor_markdown


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_doctor_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "doctor",
        help="Diagnose local CLI installation, PATH, wrapper, and import health.",
    )


def handle_doctor_command(args: argparse.Namespace, print_payload: PrintPayload) -> int:
    payload = collect_doctor()
    print_payload(payload, args.format, render_doctor_markdown)
    return 0 if payload.get("ok") else 1
