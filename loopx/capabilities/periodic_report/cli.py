from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .core import build_periodic_report_run
from .extension_envelope import build_openviking_archive_execution_envelope
from .profile import build_periodic_report_activation
from .presets import (
    PERIODIC_REPORT_PROFILE_PRESET_ALIASES,
    build_periodic_report_preset_activation,
)
from .triggers import build_periodic_report_trigger_decision
from ...extensions.runtime import execute_extension_runtime_binding


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
        help="Inspect a built-in preset or project profile without provider effects.",
    )
    add_subcommand_format(inspect_profile)
    profile_source = inspect_profile.add_mutually_exclusive_group(required=True)
    profile_source.add_argument(
        "--profile-json",
        help="Path to periodic_report_profile_v0 JSON; use '-' for stdin.",
    )
    profile_source.add_argument(
        "--preset",
        choices=sorted(PERIODIC_REPORT_PROFILE_PRESET_ALIASES),
        help="Built-in profile preset or short alias, such as 'weekly'.",
    )
    archive = commands.add_parser(
        "archive-openviking",
        help=(
            "Invoke the optional doctor-ready OpenViking archive extension after "
            "checking capability activation and runtime write authority."
        ),
    )
    add_subcommand_format(archive)
    archive.add_argument(
        "--request-json",
        required=True,
        help="Path to openviking_periodic_report_archive_request_v0 JSON.",
    )
    archive.add_argument("--runtime-root")
    archive.add_argument(
        "--available-capability",
        action="append",
        default=[],
        help="Observed runtime capability; repeat for multiple values.",
    )
    archive.add_argument("--openviking-url")
    archive.add_argument("--openviking-path")
    archive.add_argument("--openviking-config")
    archive.add_argument("--openviking-actor-peer-id")
    archive.add_argument(
        "--openviking-api-key-env",
        default="OPENVIKING_API_KEY",
        help="Environment variable containing the API key; never pass the key itself.",
    )
    archive.add_argument("--execute", action="store_true")


def _archive_openviking(
    request: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    from ...extensions.openviking_periodic_report.activation import (
        resolve_openviking_periodic_report_activation,
    )
    from ...extensions.openviking_periodic_report.provider import REQUEST_SCHEMA

    if request.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError(f"request must use {REQUEST_SCHEMA}")
    if "execution_envelope" in request:
        raise ValueError("execution_envelope is created by the capability command")
    context = request.get("context")
    if not isinstance(context, dict):
        raise ValueError("request.context must be an object")
    activation_receipt = request.get("activation_receipt")
    if not isinstance(activation_receipt, dict):
        raise ValueError("request.activation_receipt must be an object")
    resolved = resolve_openviking_periodic_report_activation(
        activation_receipt,
        available_capabilities=args.available_capability,
        sink_id=str(context.get("sink_id") or ""),
        runtime_root=args.runtime_root,
    )
    binding = resolved["runtime_binding"]
    argv = [str(item) for item in binding["argv"]]
    if args.openviking_url:
        argv.extend(["--url", args.openviking_url])
    if args.openviking_path:
        argv.extend(["--path", args.openviking_path])
    if args.openviking_config:
        argv.extend(["--config", args.openviking_config])
    if args.openviking_actor_peer_id:
        argv.extend(["--actor-peer-id", args.openviking_actor_peer_id])
    if args.openviking_api_key_env:
        argv.extend(["--api-key-env", args.openviking_api_key_env])
    provider_request = {
        **request,
        "execute": args.execute,
    }
    provider_request.pop("available_capabilities", None)
    if args.execute:
        provider_request["execution_envelope"] = (
            build_openviking_archive_execution_envelope(
                provider_request,
                extension_revision=str(binding["revision"]),
            )
        )
    provider_env = dict(os.environ)
    provider_env.update(
        {
            "LOOPX_EXTENSION_ID": str(binding["extension_id"]),
            "LOOPX_EXTENSION_REVISION": str(binding["revision"]),
            "LOOPX_EXTENSION_PROTOCOL": str(binding["protocol"]),
        }
    )
    response = execute_extension_runtime_binding(
        {**binding, "argv": argv},
        request=provider_request,
        environment=provider_env,
    )
    return {
        **response,
        "extension_receipt": resolved["extension_receipt"],
    }


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
    if payload.get("schema_version") == "periodic_report_sink_result_v0":
        return "\n".join(
            [
                f"# Periodic Report Archive `{payload.get('archive_id')}`",
                "",
                f"- status: `{payload.get('status')}`",
                f"- receipt_ref: `{payload.get('receipt_ref')}`",
                f"- result_id: `{payload.get('result_id')}`",
                f"- readback_verified: `{payload.get('readback_verified')}`",
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
        if args.periodic_report_command == "archive-openviking":
            payload = _archive_openviking(
                _load_json_object(args.request_json),
                args,
            )
        elif args.periodic_report_command == "inspect-profile":
            payload = (
                build_periodic_report_preset_activation(args.preset)
                if args.preset
                else build_periodic_report_activation(
                    _load_json_object(args.profile_json)
                )
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
