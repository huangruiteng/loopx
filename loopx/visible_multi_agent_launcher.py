from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path


def require_executable(command: str, *, field: str) -> str:
    path = shutil.which(command)
    if not path:
        raise ValueError(f"{field} executable not found on PATH: {command}")
    return path


def runtime_shell_command(
    command: str,
    *,
    project: Path,
    registry: Path,
    runtime_root: Path,
    errexit: bool = True,
) -> str:
    exports = [
        "set -euo pipefail" if errexit else "set -uo pipefail",
        f"export LOOPX_PROJECT={shlex.quote(str(project))}",
        f"export LOOPX_REGISTRY={shlex.quote(str(registry))}",
        f"export LOOPX_RUNTIME_ROOT={shlex.quote(str(runtime_root))}",
    ]
    return "; ".join([*exports, command])


def resolve_visible_workspace(
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


def mac_terminal_available() -> bool:
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


def resolve_visible_launcher(*, requested: str, tmux_bin: str) -> str:
    if requested != "auto":
        return requested
    if shutil.which(tmux_bin):
        return "tmux"
    if mac_terminal_available():
        return "terminal"
    raise ValueError("no visible launcher found: install tmux or run on macOS with Terminal available")


def execute_visible_multi_agent_launcher(
    *,
    payload: dict[str, object],
    registry: Path,
    runtime_root: Path,
    requested_launcher: str,
    tmux_bin: str,
    cli_bin: str,
    codex_bin: str,
    attach: bool,
    replace_existing: bool,
    workspace: str | None,
    create_workspace: bool,
    cwd: Path,
    launch_result_schema: str = "multi_agent_visible_launch_result_v0",
    acceptance_schema: str = "multi_agent_visible_launch_acceptance_v0",
    lane_default: str = "agent-lane",
    terminal_lane_label_template: str = "[LoopX visible lane: {lane_id}]",
    frontier_or_blocker_markers: Iterable[str] = ("[LoopX frontier]", "[LoopX blocked reason]"),
    frontier_or_blocker_status_markers: Iterable[str] = ("frontier_or_blocked_reason=printed",),
) -> tuple[dict[str, object], str, str]:
    require_executable(cli_bin, field="cli_bin")
    require_executable(codex_bin, field="codex_bin")
    chosen = resolve_visible_launcher(requested=requested_launcher, tmux_bin=tmux_bin)
    project, workspace_mode = resolve_visible_workspace(
        workspace,
        create=create_workspace,
        cwd=cwd,
    )
    if chosen == "tmux":
        result = launch_visible_multi_agent_with_tmux(
            payload=payload,
            project=project,
            workspace_mode=workspace_mode,
            registry=registry,
            runtime_root=runtime_root,
            tmux_bin=tmux_bin,
            attach=attach,
            replace_existing=replace_existing,
            launch_result_schema=launch_result_schema,
            acceptance_schema=acceptance_schema,
            lane_default=lane_default,
            frontier_or_blocker_markers=frontier_or_blocker_markers,
            frontier_or_blocker_status_markers=frontier_or_blocker_status_markers,
        )
    elif chosen == "terminal":
        result = launch_visible_multi_agent_with_terminal(
            payload=payload,
            project=project,
            workspace_mode=workspace_mode,
            registry=registry,
            runtime_root=runtime_root,
            launch_result_schema=launch_result_schema,
            lane_default=lane_default,
            terminal_lane_label_template=terminal_lane_label_template,
        )
    else:
        raise ValueError(f"unsupported visible launcher: {chosen}")
    return result, chosen, workspace_mode


def launch_visible_multi_agent_with_tmux(
    *,
    payload: dict[str, object],
    project: Path,
    workspace_mode: str,
    registry: Path,
    runtime_root: Path,
    tmux_bin: str,
    attach: bool,
    replace_existing: bool,
    launch_result_schema: str,
    acceptance_schema: str,
    lane_default: str,
    frontier_or_blocker_markers: Iterable[str],
    frontier_or_blocker_status_markers: Iterable[str],
) -> dict[str, object]:
    require_executable(tmux_bin, field="tmux_bin")
    session = str(payload.get("session_name") or "loopx-visible-agents")
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    if not lanes:
        raise ValueError("visible multi-agent launcher has no lanes to launch")

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
    frontier_command = runtime_shell_command(
        f'cd "$LOOPX_PROJECT"; {first_frontier}; '
        'FRONTIER_STATUS=$?; '
        'printf "\\n[frontier window ready]\\nexit=%s\\n" "$FRONTIER_STATUS"; '
        'exec /bin/sh -i',
        project=project,
        registry=registry,
        runtime_root=runtime_root,
        errexit=False,
    )
    subprocess.run(
        [tmux_bin, "new-session", "-d", "-s", session, "-n", "frontier", "bash", "-lc", frontier_command],
        check=True,
        env=env,
    )
    started_lanes: list[str] = []
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or lane_default)
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
                runtime_shell_command(
                    launch_command,
                    project=project,
                    registry=registry,
                    runtime_root=runtime_root,
                    errexit=False,
                ),
            ],
            check=True,
            env=env,
        )
        started_lanes.append(lane_id)
    if attach:
        subprocess.run([tmux_bin, "attach", "-t", session], check=True, env=env)
    acceptance = tmux_visible_launch_acceptance(
        tmux_bin=tmux_bin,
        session=session,
        expected_lanes=started_lanes,
        env=env,
        schema_version=acceptance_schema,
        frontier_or_blocker_markers=frontier_or_blocker_markers,
        frontier_or_blocker_status_markers=frontier_or_blocker_status_markers,
    )
    return {
        "schema_version": launch_result_schema,
        "executed": True,
        "launcher": "tmux",
        "session_name": session,
        "started_lane_count": len(started_lanes),
        "started_lanes": started_lanes,
        "surviving_lane_count": len(acceptance["surviving_lanes"]),
        "surviving_lanes": acceptance["surviving_lanes"],
        "attach_command": f"{tmux_bin} attach -t {session}",
        "stop_command": f"{tmux_bin} kill-session -t {session}",
        "workspace_mode": workspace_mode,
        "attach_requested": attach,
        "operator_takeover": "attach to the tmux session, interrupt any lane, or kill the session",
        "visible_acceptance": acceptance,
    }


def tmux_visible_launch_acceptance(
    *,
    tmux_bin: str,
    session: str,
    expected_lanes: list[str],
    env: dict[str, str],
    schema_version: str,
    frontier_or_blocker_markers: Iterable[str],
    frontier_or_blocker_status_markers: Iterable[str],
) -> dict[str, object]:
    """Read back tmux pane evidence so launch success is not only process creation."""

    required_markers = [
        "[LoopX quota guard]",
        "[bootstrap-or-stop]",
    ]
    frontier_markers = tuple(frontier_or_blocker_markers)
    frontier_status_markers = tuple(frontier_or_blocker_status_markers)
    last_payload: dict[str, object] | None = None
    for attempt in range(20):
        time.sleep(0.25)
        list_result = subprocess.run(
            [tmux_bin, "list-windows", "-t", session, "-F", "#{window_name}"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        observed_windows = [
            line.strip()
            for line in list_result.stdout.splitlines()
            if line.strip()
        ]
        surviving_lanes = [lane for lane in expected_lanes if lane in observed_windows]
        lane_checks: list[dict[str, object]] = []
        for lane in expected_lanes:
            capture_result = subprocess.run(
                [tmux_bin, "capture-pane", "-pt", f"{session}:{lane}", "-S", "-200"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            capture = capture_result.stdout
            visible_summary = "[LoopX visible acceptance]" in capture
            role_profile_visible = (
                "[LoopX role profile]" in capture
                or "[LoopX role_profile]" in capture
                or "role_profile=printed" in capture
            )
            quota_packet_visible = (
                "[LoopX quota guard]" in capture
                or "quota_guard=printed" in capture
            )
            bootstrap_or_stop_visible = (
                "[bootstrap-or-stop]" in capture
                or "bootstrap_or_stop=printed" in capture
            )
            markers_present = [marker for marker in required_markers if marker in capture]
            if visible_summary:
                markers_present.insert(0, "[LoopX visible acceptance]")
            if role_profile_visible:
                markers_present.insert(0, "[LoopX role profile]")
            frontier_or_blocker_visible = (
                any(marker in capture for marker in frontier_markers)
                or any(marker in capture for marker in frontier_status_markers)
            )
            lane_checks.append(
                {
                    "lane_id": lane,
                    "window_survived": lane in surviving_lanes,
                    "capture_available": capture_result.returncode == 0,
                    "role_profile_visible": role_profile_visible,
                    "quota_packet_visible": quota_packet_visible,
                    "frontier_or_blocked_reason_visible": frontier_or_blocker_visible,
                    "bootstrap_or_stop_visible": bootstrap_or_stop_visible,
                    "visible_acceptance_summary": visible_summary,
                    "markers_present": markers_present,
                }
            )
        accepted = (
            list_result.returncode == 0
            and len(surviving_lanes) == len(expected_lanes)
            and all(
                item["role_profile_visible"]
                and item["quota_packet_visible"]
                and item["frontier_or_blocked_reason_visible"]
                and item["bootstrap_or_stop_visible"]
                for item in lane_checks
            )
        )
        last_payload = {
            "schema_version": schema_version,
            "accepted": accepted,
            "attempt_count": attempt + 1,
            "observed_windows": observed_windows,
            "expected_lanes": expected_lanes,
            "surviving_lanes": surviving_lanes,
            "missing_lanes": [lane for lane in expected_lanes if lane not in surviving_lanes],
            "pane_checks": lane_checks,
            "takeover_controls_visible": {
                "attach_command": f"{tmux_bin} attach -t {session}",
                "stop_command": f"{tmux_bin} kill-session -t {session}",
            },
        }
        if accepted:
            return last_payload
    return last_payload or {
        "schema_version": schema_version,
        "accepted": False,
        "attempt_count": 0,
        "observed_windows": [],
        "expected_lanes": expected_lanes,
        "surviving_lanes": [],
        "missing_lanes": expected_lanes,
        "pane_checks": [],
        "takeover_controls_visible": {
            "attach_command": f"{tmux_bin} attach -t {session}",
            "stop_command": f"{tmux_bin} kill-session -t {session}",
        },
    }


def launch_visible_multi_agent_with_terminal(
    *,
    payload: dict[str, object],
    project: Path,
    workspace_mode: str,
    registry: Path,
    runtime_root: Path,
    launch_result_schema: str,
    lane_default: str,
    terminal_lane_label_template: str,
) -> dict[str, object]:
    require_executable("osascript", field="osascript")
    if not mac_terminal_available():
        raise ValueError("macOS Terminal is not available for --launcher terminal")
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    if not lanes:
        raise ValueError("visible multi-agent launcher has no lanes to launch")

    first_frontier = str(lanes[0].get("frontier") or "")
    frontier_command = runtime_shell_command(
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
        lane_id = str(lane.get("lane_id") or lane_default)
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        command = runtime_shell_command(
            f"printf '\\n{terminal_lane_label_template.format(lane_id=lane_id)}\\n'; {launch_command}",
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
        "schema_version": launch_result_schema,
        "executed": True,
        "launcher": "terminal",
        "session_name": str(payload.get("session_name") or "loopx-visible-agents"),
        "started_lane_count": len(started_lanes),
        "started_lanes": started_lanes,
        "attach_command": "already visible in Terminal windows",
        "stop_command": "interrupt or close the opened Terminal windows",
        "workspace_mode": workspace_mode,
        "attach_requested": False,
        "operator_takeover": "use the visible Terminal windows; interrupt any lane before writeback",
    }


def _apple_script_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
