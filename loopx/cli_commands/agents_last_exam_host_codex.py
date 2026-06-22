from __future__ import annotations

import argparse
from collections.abc import Callable

from ..benchmark_adapters.agents_last_exam import (
    build_agents_last_exam_host_codex_cli_route,
    build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_HOST_CODEX_COMMANDS = {
    "ale-host-codex-cli-route",
    "ale-host-codex-cua-no-task-e2e",
}


def render_agents_last_exam_host_codex_cli_route_markdown(
    payload: dict[str, object],
) -> str:
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    codex_cli = (
        payload.get("host_codex_cli")
        if isinstance(payload.get("host_codex_cli"), dict)
        else {}
    )
    host_auth = (
        payload.get("host_auth") if isinstance(payload.get("host_auth"), dict) else {}
    )
    cua_assets = (
        payload.get("cua_mcp_assets")
        if isinstance(payload.get("cua_mcp_assets"), dict)
        else {}
    )
    ale_sandbox = (
        payload.get("ale_sandbox")
        if isinstance(payload.get("ale_sandbox"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CLI Route",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route mode: `{route.get('mode')}`",
        f"- Host Codex binary/version: `{codex_cli.get('binary')}` / `{codex_cli.get('version')}`",
        f"- Host Codex available: `{codex_cli.get('binary_available')}`",
        f"- Host auth/config present: `{host_auth.get('auth_cache_present')}`/`{host_auth.get('config_present')}`",
        f"- Credential values recorded: `{host_auth.get('credential_values_recorded')}`",
        f"- Auth copied to sandbox: `{host_auth.get('auth_material_copied_to_sandbox')}`",
        f"- CUA MCP assets ready: `{cua_assets.get('available')}`",
        f"- ALE CUA smoke ready: `{ale_sandbox.get('cua_smoke_ready')}`",
        f"- Runs Codex in sandbox: `{route.get('runs_codex_inside_ale_sandbox')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_host_codex_cua_no_task_smoke_markdown(
    payload: dict[str, object],
) -> str:
    codex_exec = (
        payload.get("codex_exec_surface")
        if isinstance(payload.get("codex_exec_surface"), dict)
        else {}
    )
    mcp_config = (
        payload.get("codex_mcp_config")
        if isinstance(payload.get("codex_mcp_config"), dict)
        else {}
    )
    cua_bridge = (
        payload.get("cua_mcp_bridge")
        if isinstance(payload.get("cua_mcp_bridge"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Host Codex CUA No-Task E2E",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Route gate ready: `{payload.get('route_gate_ready')}`",
        f"- Codex exec surface ready: `{codex_exec.get('available')}`",
        f"- Codex MCP config ready: `{mcp_config.get('available')}`",
        f"- CUA MCP bridge ready: `{cua_bridge.get('available')}`",
        f"- Codex prompt sent: `{boundary.get('codex_prompt_sent')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Raw output recorded: `{boundary.get('raw_output_recorded')}`",
        f"- Container started/task read: `{boundary.get('container_started')}`/`{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_host_codex_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_host_codex_cli_route_parser = benchmark_subparsers.add_parser(
        "ale-host-codex-cli-route",
        help=(
            "Check the host Codex CLI auth route for a future Agents' Last Exam "
            "run. This verifies only compact host-side readiness signals and "
            "does not read credential values, copy auth into the sandbox, start "
            "containers, read task bodies, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cli_route_parser)
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free smokes; records no binary path.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text. If omitted, the command "
            "runs `<codex-binary> --version` without recording argv or paths."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help=(
            "Mark that host Codex auth cache existence was verified. The value "
            "is not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help=(
            "Mark that host Codex config existence was verified. The content is "
            "not read or recorded."
        ),
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--cua-mcp-assets-root",
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke is already ready.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cli_route_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the host Codex CLI route gate is ready.",
    )

    ale_host_codex_cua_no_task_e2e_parser = benchmark_subparsers.add_parser(
        "ale-host-codex-cua-no-task-e2e",
        help=(
            "Build compact no-task evidence that host Codex CLI help, Codex MCP "
            "config loading, and the CUA MCP bridge are ready. This does not "
            "send a Codex prompt, invoke a model API, read task bodies, record "
            "raw output, upload, or submit."
        ),
    )
    add_subcommand_format(ale_host_codex_cua_no_task_e2e_parser)
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-binary",
        default="codex",
        help="PATH-visible host Codex CLI binary name to probe. Paths are not recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--assume-codex-binary-available",
        action="store_true",
        help="Fixture flag for dependency-free route-gate smokes; records no binary path.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--codex-version-text",
        help=(
            "Optional pre-probed Codex version text for the route gate. If "
            "omitted, the command runs `<codex-binary> --version` without "
            "recording argv or paths."
        ),
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-auth-cache-present",
        action="store_true",
        help="Mark that host Codex auth cache existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--host-config-present",
        action="store_true",
        help="Mark that host Codex config existence was verified without reading it.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-host-config",
        action="store_true",
        help="Require host config existence in addition to host auth cache.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-mcp-assets-root",
        required=True,
        help="Local CUA MCP server asset root to probe. The path is never recorded.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--cua-server-url",
        default="http://127.0.0.1:8000",
        help="Local CUA server URL used only inside a temporary Codex MCP config.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--install-node-deps",
        action="store_true",
        help="Allow npm install in a temporary copy of the CUA MCP assets if node_modules is absent.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--ale-sandbox-cua-smoke-ready",
        action="store_true",
        help="Mark that the ALE DockerProvider CUA smoke/e2e prerequisite is already ready.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--operator-authorized-host-codex-auth",
        action="store_true",
        help="Mark that the owner authorized using host Codex auth for this route.",
    )
    ale_host_codex_cua_no_task_e2e_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the no-task host Codex CUA E2E gate is ready.",
    )


def handle_agents_last_exam_host_codex_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_HOST_CODEX_COMMANDS:
        return None

    if args.benchmark_command == "ale-host-codex-cli-route":
        try:
            payload = build_agents_last_exam_host_codex_cli_route(
                codex_binary=args.codex_binary,
                codex_binary_available=True
                if args.assume_codex_binary_available
                else None,
                codex_version_text=args.codex_version_text,
                host_auth_cache_present=True
                if args.host_auth_cache_present
                else None,
                host_config_present=True if args.host_config_present else None,
                require_host_config=bool(args.require_host_config),
                cua_mcp_assets_root=args.cua_mcp_assets_root,
                ale_sandbox_cua_smoke_ready=bool(
                    args.ale_sandbox_cua_smoke_ready
                ),
                operator_authorized_host_codex_auth=bool(
                    args.operator_authorized_host_codex_auth
                ),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_host_codex_cli_route_v0",
                "error": "ale_host_codex_cli_route_failed",
                "read_boundary": {
                    "compact_only": True,
                    "auth_values_read": False,
                    "config_content_read": False,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_host_codex_cli_route_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_host_codex_cli_route_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-host-codex-cua-no-task-e2e":
        try:
            payload = build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
                codex_binary=args.codex_binary,
                codex_binary_available=True
                if args.assume_codex_binary_available
                else None,
                codex_version_text=args.codex_version_text,
                host_auth_cache_present=True
                if args.host_auth_cache_present
                else None,
                host_config_present=True if args.host_config_present else None,
                require_host_config=bool(args.require_host_config),
                cua_mcp_assets_root=args.cua_mcp_assets_root,
                cua_server_url=args.cua_server_url,
                install_node_deps=bool(args.install_node_deps),
                ale_sandbox_cua_smoke_ready=bool(
                    args.ale_sandbox_cua_smoke_ready
                ),
                operator_authorized_host_codex_auth=bool(
                    args.operator_authorized_host_codex_auth
                ),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_host_codex_cua_no_task_smoke_v0",
                "error": "ale_host_codex_cua_no_task_e2e_failed",
                "read_boundary": {
                    "compact_only": True,
                    "auth_values_read": False,
                    "config_content_read": False,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_host_codex_cua_no_task_e2e_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_host_codex_cua_no_task_smoke_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
