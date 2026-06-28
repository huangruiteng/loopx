from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from . import (
    AUTO_RESEARCH_DEFAULT_GOAL_ID,
    AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
    build_auto_research_board_projection,
    build_auto_research_demo_acceptance_packet,
    build_auto_research_demo_supervisor_plan,
    build_auto_research_quickstart,
    build_auto_research_rollout_events,
    build_live_auto_research_projection,
    build_auto_research_projection,
    load_auto_research_evidence_packet,
    load_auto_research_evidence_packet_inputs,
    load_auto_research_fixture,
    render_auto_research_markdown,
)
from ...history import load_registry
from ...paths import resolve_runtime_root
from ...quota import build_quota_should_run
from ...rollout_event_log import (
    append_rollout_event,
    load_rollout_events,
    rollout_event_log_path,
)
from ...status import collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_auto_research_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    auto_research_parser = subparsers.add_parser(
        "auto-research",
        help="Project public-safe decentralized auto-research frontiers.",
    )
    auto_research_sub = auto_research_parser.add_subparsers(
        dest="auto_research_command",
        required=True,
    )
    quickstart_parser = auto_research_sub.add_parser(
        "quickstart",
        help="Preview or create a protected starter pack for decentralized auto-research.",
    )
    add_subcommand_format(quickstart_parser)
    quickstart_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id that should receive the first runnable hypothesis.",
    )
    quickstart_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id for the generated contract.",
    )
    quickstart_parser.add_argument(
        "--objective",
        default=AUTO_RESEARCH_DEFAULT_OBJECTIVE,
        help="Compact public-safe research objective for the generated contract.",
    )
    quickstart_parser.add_argument(
        "--output-dir",
        default="auto_research_knn_pack",
        help="Relative output directory for --execute. Refuses to overwrite an existing pack.",
    )
    quickstart_parser.add_argument(
        "--template",
        choices=[AUTO_RESEARCH_QUICKSTART_TEMPLATE],
        default=AUTO_RESEARCH_QUICKSTART_TEMPLATE,
        help="Starter pack template.",
    )
    quickstart_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the starter pack. Omit for a read-only preview.",
    )

    frontier_parser = auto_research_sub.add_parser(
        "frontier",
        help="Render a per-agent decentralized research frontier from a public fixture or live LoopX state.",
    )
    add_subcommand_format(frontier_parser)
    frontier_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    frontier_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    frontier_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose runnable frontier should be projected.",
    )

    board_parser = auto_research_sub.add_parser(
        "board",
        help="Render a read-only Frontstage board packet from a fixture or live LoopX rollout projection.",
    )
    add_subcommand_format(board_parser)
    board_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    board_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    board_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose board/frontier should be projected.",
    )

    acceptance_parser = auto_research_sub.add_parser(
        "acceptance",
        help="Render an operator acceptance packet that links board output, dry-run supervisor, and takeover checks.",
    )
    add_subcommand_format(acceptance_parser)
    acceptance_parser.add_argument(
        "--fixture",
        help="Path to a decentralized_auto_research_fixture_v0 JSON file.",
    )
    acceptance_parser.add_argument(
        "--goal-id",
        help="Goal id for live LoopX quota/status input. Mutually exclusive with --fixture.",
    )
    acceptance_parser.add_argument(
        "--agent-id",
        required=True,
        help="Agent id whose board/frontier should be projected.",
    )
    acceptance_parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help=(
            "Supervisor agent/lane pair as agent_id:lane_id. Repeat for each visible lane. "
            "Omit to use the default LoopX auto-research demo lane set."
        ),
    )
    acceptance_parser.add_argument(
        "--session-name",
        default="loopx-auto-research",
        help="Public-safe tmux session name for the dry-run supervisor packet.",
    )
    acceptance_parser.add_argument("--cli-bin", default="loopx", help="LoopX CLI executable name.")
    acceptance_parser.add_argument("--codex-bin", default="codex", help="Codex CLI executable name.")
    acceptance_parser.add_argument("--tmux-bin", default="tmux", help="tmux executable name.")

    evidence_parser = auto_research_sub.add_parser(
        "evidence",
        help="Build public-safe research hypothesis/evidence records from protected eval outputs.",
    )
    add_subcommand_format(evidence_parser)
    evidence_parser.add_argument("--contract", required=True, help="Path to research_contract_v0 JSON.")
    evidence_parser.add_argument(
        "--eval-result",
        action="append",
        required=True,
        help="Path to a protected evaluator JSON result. Repeat for dev/holdout or retry evidence.",
    )
    evidence_parser.add_argument("--hypothesis-id", required=True)
    evidence_parser.add_argument("--todo-id", required=True)
    evidence_parser.add_argument("--agent-id", required=True)
    evidence_parser.add_argument("--claimed-by", required=True)
    evidence_parser.add_argument("--mechanism-family", required=True)
    evidence_parser.add_argument("--hypothesis", required=True)
    evidence_parser.add_argument("--parent-hypothesis-id")
    evidence_parser.add_argument("--grounding-ref", action="append", default=[])
    evidence_parser.add_argument("--novelty-audit-ref")
    evidence_parser.add_argument("--branch-ref")
    evidence_parser.add_argument("--attempt-start", type=int, default=1)

    append_parser = auto_research_sub.add_parser(
        "append-evidence",
        help="Append an auto_research_evidence_packet_v0 into the LoopX rollout event log.",
    )
    add_subcommand_format(append_parser)
    append_parser.add_argument("--packet", required=True, help="Path to auto_research_evidence_packet_v0 JSON.")
    append_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rollout events without appending them.",
    )

    demo_supervisor_parser = auto_research_sub.add_parser(
        "demo-supervisor",
        help="Plan a dry-run tmux/Codex-CLI supervisor for decentralized auto-research lanes.",
    )
    add_subcommand_format(demo_supervisor_parser)
    demo_supervisor_parser.add_argument(
        "--goal-id",
        default=AUTO_RESEARCH_DEFAULT_GOAL_ID,
        help="Research goal id whose frontier each lane should inspect.",
    )
    demo_supervisor_parser.add_argument(
        "--agent",
        action="append",
        default=[],
        help=(
            "Agent/lane pair as agent_id:lane_id. Repeat for each visible lane. "
            "Omit to use the default LoopX auto-research demo lane set."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--session-name",
        default="loopx-auto-research",
        help="Public-safe tmux session name for the generated dry-run script.",
    )
    demo_supervisor_parser.add_argument("--cli-bin", default="loopx", help="LoopX CLI executable name.")
    demo_supervisor_parser.add_argument("--codex-bin", default="codex", help="Codex CLI executable name.")
    demo_supervisor_parser.add_argument("--tmux-bin", default="tmux", help="tmux executable name.")
    demo_supervisor_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually launch visible Codex CLI lanes. Omit for the default dry-run packet. "
            "This only starts local visible terminals; LoopX writeback still happens through normal lane commands."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--launcher",
        choices=["auto", "tmux", "terminal"],
        default="auto",
        help="Visible process launcher for --execute. auto prefers tmux, then macOS Terminal.",
    )
    demo_supervisor_parser.add_argument(
        "--attach",
        action="store_true",
        help="After --execute with tmux, attach to the session. Terminal launcher opens visible windows directly.",
    )
    demo_supervisor_parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="With tmux launcher, kill an existing session with the same name before launching.",
    )
    demo_supervisor_parser.add_argument(
        "--workspace",
        help=(
            "Directory where visible Codex lanes should start. Defaults to the current directory. "
            "For demos, prefer an empty user-owned research workspace that shares LoopX state through "
            "--registry/--runtime-root."
        ),
    )
    demo_supervisor_parser.add_argument(
        "--create-workspace",
        action="store_true",
        help="Create --workspace when it does not already exist.",
    )


def _append_auto_research_rollout_events(
    *,
    packet_path: str,
    registry_path: Path,
    runtime_root_arg: str | None,
    dry_run: bool,
) -> dict[str, object]:
    packet = load_auto_research_evidence_packet(packet_path)
    goal_id = packet["research_contract"]["goal_id"]
    events = build_auto_research_rollout_events(packet)
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    log_path = rollout_event_log_path(runtime_root, goal_id)
    existing_ids = {
        str(event.get("event_id"))
        for event in load_rollout_events(log_path)
        if event.get("event_id")
    }
    appended_ids: list[str] = []
    skipped_ids: list[str] = []
    for event in events:
        event_id = str(event["event_id"])
        if event_id in existing_ids:
            skipped_ids.append(event_id)
            continue
        if not dry_run:
            append_rollout_event(log_path, event)
            existing_ids.add(event_id)
        appended_ids.append(event_id)
    counts_by_kind = Counter(str(event.get("event_kind") or "") for event in events)
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_ROLLOUT_APPEND_SCHEMA_VERSION,
        "goal_id": goal_id,
        "dry_run": dry_run,
        "event_count": len(events),
        "appended_count": 0 if dry_run else len(appended_ids),
        "would_append_count": len(appended_ids),
        "skipped_existing_count": len(skipped_ids),
        "event_ids": [str(event["event_id"]) for event in events],
        "appended_event_ids": [] if dry_run else appended_ids,
        "skipped_existing_event_ids": skipped_ids,
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "packet_summary": packet["summary"],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "loopx_rollout_event_log",
        },
    }


def _require_executable(command: str, *, field: str) -> str:
    path = shutil.which(command)
    if not path:
        raise ValueError(f"{field} executable not found on PATH: {command}")
    return path


def _apple_script_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _runtime_shell_command(
    command: str,
    *,
    project: Path,
    registry: Path,
    runtime_root: Path,
) -> str:
    exports = [
        "set -euo pipefail",
        f"export LOOPX_PROJECT={shlex.quote(str(project))}",
        f"export LOOPX_REGISTRY={shlex.quote(str(registry))}",
        f"export LOOPX_RUNTIME_ROOT={shlex.quote(str(runtime_root))}",
    ]
    return "; ".join([*exports, command])


def _resolve_demo_workspace(
    workspace: str | None,
    *,
    create: bool,
    cwd: Path,
) -> tuple[Path, str]:
    if not workspace:
        return cwd.resolve(), "current_directory"
    path = Path(workspace).expanduser()
    if not path.is_absolute():
        path = cwd / path
    if not path.exists():
        if not create:
            raise ValueError("workspace does not exist; pass --create-workspace to create it")
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError("workspace must be a directory")
    return path.resolve(), "explicit_workspace"


def _mac_terminal_available() -> bool:
    if platform.system() != "Darwin" or not shutil.which("osascript"):
        return False
    result = subprocess.run(
        ["osascript", "-e", 'id of application "Terminal"'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )
    return result.returncode == 0


def _resolve_auto_research_launcher(*, requested: str, tmux_bin: str) -> str:
    if requested != "auto":
        return requested
    if shutil.which(tmux_bin):
        return "tmux"
    if _mac_terminal_available():
        return "terminal"
    raise ValueError("no visible launcher found: install tmux or run on macOS with Terminal available")


def _launch_auto_research_with_tmux(
    *,
    payload: dict[str, object],
    project: Path,
    workspace_mode: str,
    registry: Path,
    runtime_root: Path,
    tmux_bin: str,
    attach: bool,
    replace_existing: bool,
) -> dict[str, object]:
    _require_executable(tmux_bin, field="tmux_bin")
    session = str(payload.get("session_name") or "loopx-auto-research")
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    if not lanes:
        raise ValueError("demo supervisor has no lanes to launch")

    env = os.environ.copy()
    env.update(
        {
            "LOOPX_PROJECT": str(project),
            "LOOPX_REGISTRY": str(registry),
            "LOOPX_RUNTIME_ROOT": str(runtime_root),
        }
    )
    exists = subprocess.run(
        [tmux_bin, "has-session", "-t", session],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        env=env,
    )
    if exists.returncode == 0:
        if not replace_existing:
            raise ValueError(
                f"tmux session already exists: {session}; use --replace-existing or attach manually"
            )
        subprocess.run([tmux_bin, "kill-session", "-t", session], check=True, env=env)

    first_frontier = str(lanes[0].get("frontier") or "")
    if not first_frontier:
        raise ValueError("first lane is missing a frontier command")
    frontier_command = _runtime_shell_command(
        f'cd "$LOOPX_PROJECT"; {first_frontier}',
        project=project,
        registry=registry,
        runtime_root=runtime_root,
    )
    subprocess.run(
        [tmux_bin, "new-session", "-d", "-s", session, "-n", "frontier", "bash", "-lc", frontier_command],
        check=True,
        env=env,
    )
    started_lanes: list[str] = []
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "research-lane")
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        subprocess.run(
            [
                tmux_bin,
                "new-window",
                "-d",
                "-t",
                session,
                "-n",
                lane_id,
                "bash",
                "-lc",
                _runtime_shell_command(
                    launch_command,
                    project=project,
                    registry=registry,
                    runtime_root=runtime_root,
                ),
            ],
            check=True,
            env=env,
        )
        started_lanes.append(lane_id)
    if attach:
        subprocess.run([tmux_bin, "attach", "-t", session], check=True, env=env)
    return {
        "schema_version": "auto_research_demo_launch_result_v0",
        "executed": True,
        "launcher": "tmux",
        "session_name": session,
        "started_lane_count": len(started_lanes),
        "started_lanes": started_lanes,
        "attach_command": f"{tmux_bin} attach -t {session}",
        "stop_command": f"{tmux_bin} kill-session -t {session}",
        "workspace_mode": workspace_mode,
        "attach_requested": attach,
        "operator_takeover": "attach to the tmux session, interrupt any lane, or kill the session",
    }


def _launch_auto_research_with_terminal(
    *,
    payload: dict[str, object],
    project: Path,
    workspace_mode: str,
    registry: Path,
    runtime_root: Path,
) -> dict[str, object]:
    _require_executable("osascript", field="osascript")
    if not _mac_terminal_available():
        raise ValueError("macOS Terminal is not available for --launcher terminal")
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    if not lanes:
        raise ValueError("demo supervisor has no lanes to launch")

    first_frontier = str(lanes[0].get("frontier") or "")
    frontier_command = _runtime_shell_command(
        f'cd "$LOOPX_PROJECT"; {first_frontier}; printf "\\n[Terminal window ready]\\n"; exec $SHELL -l',
        project=project,
        registry=registry,
        runtime_root=runtime_root,
    )
    subprocess.run(
        [
            "osascript",
            "-e",
            f'tell application "Terminal" to do script {_apple_script_string(frontier_command)}',
        ],
        check=True,
    )
    started_lanes: list[str] = []
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "research-lane")
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        command = _runtime_shell_command(
            f"printf '\\n[LoopX auto-research lane: {lane_id}]\\n'; {launch_command}",
            project=project,
            registry=registry,
            runtime_root=runtime_root,
        )
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script {_apple_script_string(command)}',
            ],
            check=True,
        )
        started_lanes.append(lane_id)
    return {
        "schema_version": "auto_research_demo_launch_result_v0",
        "executed": True,
        "launcher": "terminal",
        "session_name": str(payload.get("session_name") or "loopx-auto-research"),
        "started_lane_count": len(started_lanes),
        "started_lanes": started_lanes,
        "attach_command": "already visible in Terminal windows",
        "stop_command": "interrupt or close the opened Terminal windows",
        "workspace_mode": workspace_mode,
        "attach_requested": False,
        "operator_takeover": "use the visible Terminal windows; interrupt any lane before writeback",
    }


def _execute_auto_research_demo_supervisor(
    payload: dict[str, object],
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    launcher: str,
    tmux_bin: str,
    cli_bin: str,
    codex_bin: str,
    attach: bool,
    replace_existing: bool,
    workspace: str | None,
    create_workspace: bool,
) -> dict[str, object]:
    _require_executable(cli_bin, field="cli_bin")
    _require_executable(codex_bin, field="codex_bin")
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    chosen = _resolve_auto_research_launcher(requested=launcher, tmux_bin=tmux_bin)
    project, workspace_mode = _resolve_demo_workspace(
        workspace,
        create=create_workspace,
        cwd=Path.cwd(),
    )
    if chosen == "tmux":
        result = _launch_auto_research_with_tmux(
            payload=payload,
            project=project,
            workspace_mode=workspace_mode,
            registry=registry_path,
            runtime_root=runtime_root,
            tmux_bin=tmux_bin,
            attach=attach,
            replace_existing=replace_existing,
        )
    else:
        result = _launch_auto_research_with_terminal(
            payload=payload,
            project=project,
            workspace_mode=workspace_mode,
            registry=registry_path,
            runtime_root=runtime_root,
        )
    payload["mode"] = "executed_visible_launch"
    payload["launch_result"] = result
    boundary = payload.get("boundary")
    if isinstance(boundary, dict):
        boundary.update(
            {
                "dry_run_plan_only": False,
                "starts_tmux": chosen == "tmux",
                "opens_terminal": chosen == "terminal",
                "runs_codex": True,
                "writes_loopx_state": False,
                "spends_loopx_quota": False,
                "external_service_call": False,
                "workspace_mode": workspace_mode,
                "workspace_write_scope": "user_selected_workspace_only",
                "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
            }
        )
    return payload


def handle_auto_research_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.auto_research_command == "quickstart":
            payload = build_auto_research_quickstart(
                agent_id=args.agent_id,
                goal_id=args.goal_id,
                objective=args.objective,
                output_dir=args.output_dir,
                template=args.template,
                execute=args.execute,
                cwd=Path.cwd(),
            )
        elif args.auto_research_command in {"frontier", "board", "acceptance"}:
            if bool(args.fixture) == bool(args.goal_id):
                raise ValueError(f"auto-research {args.auto_research_command} requires exactly one of --fixture or --goal-id")
            if args.fixture:
                fixture = load_auto_research_fixture(args.fixture)
                payload = build_auto_research_projection(
                    fixture,
                    agent_id=args.agent_id,
                )
            else:
                status_payload = collect_status(
                    registry_path=registry_path,
                    runtime_root_override=runtime_root_arg,
                    scan_roots=[Path.cwd()],
                    limit=5,
                )
                quota_payload = build_quota_should_run(
                    status_payload,
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                )
                registry = load_registry(registry_path)
                runtime_root = resolve_runtime_root(registry, runtime_root_arg)
                rollout_events = load_rollout_events(
                    rollout_event_log_path(runtime_root, args.goal_id)
                )
                payload = build_live_auto_research_projection(
                    goal_id=args.goal_id,
                    agent_id=args.agent_id,
                    quota_payload=quota_payload,
                    rollout_events=rollout_events,
                )
            if args.auto_research_command in {"board", "acceptance"}:
                payload = build_auto_research_board_projection(payload)
            if args.auto_research_command == "acceptance":
                supervisor = build_auto_research_demo_supervisor_plan(
                    goal_id=args.goal_id or payload["research_contract"]["goal_id"],
                    agent_specs=args.agent,
                    session_name=args.session_name,
                    cli_bin=args.cli_bin,
                    codex_bin=args.codex_bin,
                    tmux_bin=args.tmux_bin,
                )
                payload = build_auto_research_demo_acceptance_packet(payload, supervisor)
        elif args.auto_research_command == "evidence":
            payload = load_auto_research_evidence_packet_inputs(
                contract_path=args.contract,
                eval_result_paths=args.eval_result,
                hypothesis_id=args.hypothesis_id,
                todo_id=args.todo_id,
                agent_id=args.agent_id,
                claimed_by=args.claimed_by,
                mechanism_family=args.mechanism_family,
                hypothesis=args.hypothesis,
                parent_hypothesis_id=args.parent_hypothesis_id,
                grounding_refs=args.grounding_ref,
                novelty_audit_ref=args.novelty_audit_ref,
                branch_ref=args.branch_ref,
                attempt_start=args.attempt_start,
            )
        elif args.auto_research_command == "append-evidence":
            payload = _append_auto_research_rollout_events(
                packet_path=args.packet,
                registry_path=registry_path,
                runtime_root_arg=runtime_root_arg,
                dry_run=args.dry_run,
            )
        elif args.auto_research_command == "demo-supervisor":
            payload = build_auto_research_demo_supervisor_plan(
                goal_id=args.goal_id,
                agent_specs=args.agent,
                session_name=args.session_name,
                cli_bin=args.cli_bin,
                codex_bin=args.codex_bin,
                tmux_bin=args.tmux_bin,
            )
            if args.execute:
                payload = _execute_auto_research_demo_supervisor(
                    payload,
                    registry_path=registry_path,
                    runtime_root_arg=runtime_root_arg,
                    launcher=args.launcher,
                    tmux_bin=args.tmux_bin,
                    cli_bin=args.cli_bin,
                    codex_bin=args.codex_bin,
                    attach=args.attach,
                    replace_existing=args.replace_existing,
                    workspace=args.workspace,
                    create_workspace=args.create_workspace,
                )
        else:
            raise ValueError(
                "auto-research requires the `quickstart`, `frontier`, `evidence`, "
                "`board`, `acceptance`, `append-evidence`, or `demo-supervisor` subcommand"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "auto-research",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_auto_research_markdown)
    return 0 if payload.get("ok") else 1
