from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..extensions.bundled import BUNDLED_EXTENSION_IDS, bundled_extension_manifest
from ..extensions.runtime import (
    default_extension_state_file,
    disable_extension,
    doctor_installed_extension,
    extension_status,
    install_extension,
    rollback_extension,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _render(payload: dict[str, object]) -> str:
    lines = ["# LoopX Extensions", ""]
    for key in (
        "operation",
        "extension_id",
        "version",
        "revision",
        "status",
        "enabled",
        "changed",
        "error",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload.get(key)}`")
    extensions = payload.get("extensions")
    if isinstance(extensions, list):
        lines.append(f"- extension_count: `{len(extensions)}`")
        for item in extensions:
            if isinstance(item, dict):
                lines.append(
                    f"- `{item.get('id')}`: enabled=`{item.get('enabled')}`, "
                    f"doctor_verified=`{item.get('doctor_verified')}`"
                )
    return "\n".join(lines) + "\n"


def _state_file(args: argparse.Namespace, runtime_root_arg: str | None) -> Path:
    if args.extension_state_file:
        return Path(args.extension_state_file).expanduser()
    return default_extension_state_file(runtime_root_arg)


def _add_common(
    parser: argparse.ArgumentParser,
    add_subcommand_format: AddFormat,
) -> None:
    add_subcommand_format(parser)
    parser.add_argument(
        "--state-file",
        dest="extension_state_file",
        help="Override the local extension activation state file.",
    )


def _add_manifest_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest")
    source.add_argument("--bundled", choices=BUNDLED_EXTENSION_IDS)


def register_extension_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "extension",
        help="Manage explicitly enabled subprocess extension providers.",
    )
    commands = parser.add_subparsers(dest="extension_command", required=True)

    list_parser = commands.add_parser("list", help="List installed extensions.")
    _add_common(list_parser, add_subcommand_format)

    for command in ("install", "upgrade"):
        operation = commands.add_parser(
            command,
            help=(
                "Register a preinstalled extension after its doctor passes."
                if command == "install"
                else "Activate a new manifest revision after its doctor passes."
            ),
        )
        _add_common(operation, add_subcommand_format)
        _add_manifest_source(operation)
        operation.add_argument("--execute", action="store_true")

    for command in ("disable", "rollback", "doctor"):
        operation = commands.add_parser(command)
        _add_common(operation, add_subcommand_format)
        operation.add_argument("extension_id")
        if command != "doctor":
            operation.add_argument("--execute", action="store_true")
        else:
            operation.add_argument(
                "--execute",
                action="store_true",
                help="Run the configured read-only provider probe.",
            )


def handle_extension_command(
    args: argparse.Namespace,
    *,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "extension":
        return None
    state_file = _state_file(args, runtime_root_arg)
    try:
        if args.extension_command == "list":
            payload = extension_status(state_file=state_file)
        elif args.extension_command in {"install", "upgrade"}:
            manifest_path = (
                bundled_extension_manifest(args.bundled)
                if args.bundled
                else Path(args.manifest).expanduser()
            )
            payload = install_extension(
                manifest_path,
                state_file=state_file,
                operation=args.extension_command,
                execute=args.execute,
            )
        elif args.extension_command == "disable":
            payload = disable_extension(
                args.extension_id,
                state_file=state_file,
                execute=args.execute,
            )
        elif args.extension_command == "rollback":
            payload = rollback_extension(
                args.extension_id,
                state_file=state_file,
                execute=args.execute,
            )
        else:
            payload = doctor_installed_extension(
                args.extension_id,
                state_file=state_file,
                execute=args.execute,
            )
    except ValueError as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_extension_error_v0",
            "status": "invalid_request",
            "error": str(exc),
        }
        print_payload(payload, output_format(args), _render)
        return 2
    print_payload(payload, output_format(args), _render)
    return 0
