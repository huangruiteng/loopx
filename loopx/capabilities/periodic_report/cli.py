from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .core import build_periodic_report_run
from .profile import build_periodic_report_activation
from .triggers import build_periodic_report_trigger_decision


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _load_json_object(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path_text} must contain a JSON object")
    return payload


def register_periodic_report_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "periodic-report",
        help="Compose provider-neutral periodic report run receipts.",
    )
    commands = parser.add_subparsers(dest="periodic_report_command", required=True)
    compose = commands.add_parser(
        "compose-run",
        help="Normalize one periodic_report_v0 attempt without provider effects.",
    )
    add_subcommand_format(compose)
    compose.add_argument(
        "--request-json",
        required=True,
        help="Path to periodic_report_run_request_v0 JSON; use '-' for stdin.",
    )
    evaluate = commands.add_parser(
        "evaluate-trigger",
        help="Evaluate cadence and material progress triggers without effects.",
    )
    add_subcommand_format(evaluate)
    evaluate.add_argument(
        "--request-json",
        required=True,
        help="Path to periodic_report_trigger_request_v0 JSON; use '-' for stdin.",
    )
    inspect_profile = commands.add_parser(
        "inspect-profile",
        help="Validate one default-off project profile without provider effects.",
    )
    add_subcommand_format(inspect_profile)
    inspect_profile.add_argument(
        "--profile-json",
        required=True,
        help="Path to periodic_report_profile_v0 JSON; use '-' for stdin.",
    )


def render_periodic_report_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# Periodic Report Error\n\n- error: {payload.get('error')}\n"
    if payload.get("schema_version") == "periodic_report_activation_v0":
        profile = payload.get("profile")
        normalized_profile = profile if isinstance(profile, dict) else {}
        return "\n".join(
            [
                f"# Periodic Report Profile `{normalized_profile.get('profile_id')}`",
                "",
                f"- status: `{payload.get('status')}`",
                f"- active: `{payload.get('active')}`",
                f"- extension_mode: `{payload.get('extension_mode')}`",
                "",
            ]
        )
    if payload.get("schema_version") == "periodic_report_trigger_decision_v0":
        return "\n".join(
            [
                f"# Periodic Report Trigger `{payload.get('decision_id')}`",
                "",
                f"- eligible: `{payload.get('eligible')}`",
                f"- reason: `{payload.get('reason')}`",
                f"- report_kind: `{payload.get('report_kind')}`",
                f"- report_key: `{payload.get('report_key')}`",
                "",
            ]
        )
    run_state = payload.get("run_state")
    retry = payload.get("retry")
    state = run_state if isinstance(run_state, dict) else {}
    retry_info = retry if isinstance(retry, dict) else {}
    return "\n".join(
        [
            f"# Periodic Report `{payload.get('run_id')}`",
            "",
            f"- schema: `{payload.get('schema_version')}`",
            f"- status: `{state.get('status')}`",
            f"- idempotency_key: `{payload.get('idempotency_key')}`",
            f"- retry_allowed: `{retry_info.get('allowed')}`",
            "",
        ]
    )


def handle_periodic_report_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "periodic-report":
        return None
    try:
        if args.periodic_report_command == "inspect-profile":
            payload = build_periodic_report_activation(
                _load_json_object(args.profile_json)
            )
        elif args.periodic_report_command == "evaluate-trigger":
            request = _load_json_object(args.request_json)
            payload = build_periodic_report_trigger_decision(request)
        else:
            request = _load_json_object(args.request_json)
            payload = build_periodic_report_run(request)
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "periodic_report_error_v0",
            "command": args.periodic_report_command,
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_periodic_report_markdown)
    return 0 if payload.get("ok") else 1
