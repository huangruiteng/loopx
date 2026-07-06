from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..history import load_registry
from ..paths import resolve_runtime_root
from ..visible_multi_agent_launcher import (
    build_visible_multi_agent_payload_from_spec,
    execute_visible_multi_agent_launcher,
    wake_visible_multi_agent_panes,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_multi_agent_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "multi-agent",
        help="Launch visible Codex TUI agents from a small role spec.",
    )
    multi_agent_sub = parser.add_subparsers(dest="multi_agent_command", required=True)
    launch = multi_agent_sub.add_parser(
        "launch",
        help="Preview or launch a tmux session with one interactive Codex TUI per role.",
    )
    add_subcommand_format(launch)
    launch.add_argument("--spec", required=True, help="Path to a generic_multi_agent_launch_spec_v0 JSON file.")
    launch.add_argument("--execute", action="store_true", help="Start the visible TUI session. Omit for preview.")
    launch.add_argument("--workspace", help="Workspace root for all lanes. Defaults to the current directory.")
    launch.add_argument("--create-workspace", action="store_true", help="Create --workspace if it is missing.")
    launch.add_argument("--session-name", help="Override spec.session_name.")
    launch.add_argument("--reasoning-effort", help="Override spec.default_reasoning_effort.")
    launch.add_argument("--launcher", choices=["auto", "tmux"], default="tmux")
    launch.add_argument("--tmux-bin", default="tmux")
    launch.add_argument("--cli-bin", default="loopx")
    launch.add_argument("--codex-bin", default="codex")
    launch.add_argument("--attach", action="store_true", help="Attach to the session after launch.")
    launch.add_argument("--replace-existing", action="store_true", help="Replace an existing session of the same name.")
    launch.add_argument(
        "--auto-wake",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Run a session-scoped background wake loop. The loop only broadcasts "
            "the fixed pane-local A2A prompt; each pane still reads its own state."
        ),
    )
    launch.add_argument(
        "--auto-wake-interval-seconds",
        type=float,
        default=45.0,
        help=argparse.SUPPRESS,
    )
    launch.add_argument(
        "--codex-trust-workspace",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Pass a trusted project config to each Codex TUI lane.",
    )
    wake = multi_agent_sub.add_parser(
        "wake",
        help="Broadcast the fixed pane-local A2A prompt to live visible Codex TUI panes.",
    )
    add_subcommand_format(wake)
    wake.add_argument("--session-name", required=True, help="tmux session to wake.")
    wake.add_argument(
        "--lane",
        action="append",
        default=[],
        help="Specific pane/window name to wake. Repeat to target multiple panes. Omit with --execute to list the session windows.",
    )
    wake.add_argument("--tmux-bin", default="tmux")
    wake.add_argument("--execute", action="store_true", help="Send the fixed prompt to tmux panes.")


def _load_spec(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("multi-agent spec must be a JSON object")
    return value


def _render_multi_agent_launch_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"LoopX multi-agent launch failed: {payload.get('error')}"
    lanes = [lane for lane in payload.get("lanes", []) if isinstance(lane, dict)]
    lines = [
        "# LoopX Multi-Agent Launch",
        f"- mode: {payload.get('mode')}",
        f"- goal: {payload.get('goal_id')}",
        f"- session: {payload.get('session_name')}",
        f"- roles: {len(lanes)}",
    ]
    for lane in lanes:
        lines.append(
            f"- {lane.get('lane_id')}: {lane.get('role_id')} "
            f"({lane.get('agent_id')})"
        )
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    if commands.get("attach"):
        lines.append("")
        lines.append(f"attach: `{commands.get('attach')}`")
    launch_result = payload.get("launch_result")
    if isinstance(launch_result, dict):
        accepted = (
            launch_result.get("visible_acceptance", {})
            if isinstance(launch_result.get("visible_acceptance"), dict)
            else {}
        )
        lines.append("")
        lines.append(f"visible accepted: {accepted.get('accepted')}")
        lines.append(f"started lanes: {', '.join(str(item) for item in launch_result.get('started_lanes', []))}")
    return "\n".join(lines)


def _render_multi_agent_wake_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"LoopX multi-agent wake failed: {payload.get('error')}"
    lines = [
        "# LoopX Multi-Agent Wake",
        f"- mode: {payload.get('mode')}",
        f"- session: {payload.get('session_name')}",
        f"- wakeup_model: {payload.get('wakeup_model')}",
        f"- coordination_model: {payload.get('coordination_model')}",
        f"- workflow_driver: {payload.get('workflow_driver')}",
        f"- target_lanes: {', '.join(str(item) for item in payload.get('target_lanes') or [])}",
    ]
    return "\n".join(lines)


def handle_multi_agent_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "multi-agent":
        return None
    try:
        if args.multi_agent_command == "wake":
            payload = wake_visible_multi_agent_panes(
                session_name=args.session_name,
                tmux_bin=args.tmux_bin,
                lanes=args.lane,
                execute=bool(args.execute),
            )
            print_payload(payload, output_format(args), _render_multi_agent_wake_markdown)
            return 0
        if args.multi_agent_command != "launch":
            raise ValueError("multi-agent requires the `launch` or `wake` subcommand")
        spec_path = Path(args.spec).expanduser()
        spec = _load_spec(spec_path)
        if args.session_name:
            spec = {**spec, "session_name": args.session_name}
        if args.reasoning_effort:
            spec = {**spec, "default_reasoning_effort": args.reasoning_effort}
        payload = build_visible_multi_agent_payload_from_spec(
            spec,
            tmux_bin=args.tmux_bin,
            cli_bin=args.cli_bin,
            codex_bin=args.codex_bin,
        )
        if args.execute:
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, runtime_root_arg)
            launch_result, chosen, workspace_mode = execute_visible_multi_agent_launcher(
                payload=payload,
                registry=registry_path,
                runtime_root=runtime_root,
                requested_launcher=args.launcher,
                tmux_bin=args.tmux_bin,
                cli_bin=args.cli_bin,
                codex_bin=args.codex_bin,
                attach=bool(args.attach),
                replace_existing=bool(args.replace_existing),
                workspace=args.workspace,
                create_workspace=bool(args.create_workspace),
                cwd=Path.cwd(),
                codex_trust_workspace=bool(args.codex_trust_workspace),
                source_root=spec_path.parent,
                auto_wake=bool(args.auto_wake),
                auto_wake_interval_seconds=args.auto_wake_interval_seconds,
            )
            payload["mode"] = "execute"
            payload["chosen_launcher"] = chosen
            payload["workspace_mode"] = workspace_mode
            payload["launch_result"] = launch_result
            payload["boundary"] = {
                **payload["boundary"],
                "starts_visible_processes": True,
                "runs_agent_processes": True,
            }
    except Exception as exc:
        payload = {"ok": False, "mode": "multi-agent", "error": str(exc)}
    print_payload(payload, output_format(args), _render_multi_agent_launch_markdown)
    return 0 if payload.get("ok") else 1
