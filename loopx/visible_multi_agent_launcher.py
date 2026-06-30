from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path


_QUOTA_GATE_PY = (
    "import json,sys; "
    "p=json.load(sys.stdin); "
    "u=p.get('interaction_contract',{}).get('user_channel',{}); "
    "a=p.get('interaction_contract',{}).get('agent_channel',{}); "
    "delivery=a.get('delivery_allowed', p.get('should_run', True)); "
    "ok=(not bool(u.get('action_required'))) and delivery is not False; "
    "sys.exit(0 if ok else 42)"
)

_QUOTA_BLOCKER_SUMMARY_PY = (
    "import json,sys; "
    "p=json.load(sys.stdin); "
    "ic=p.get('interaction_contract',{}); "
    "u=ic.get('user_channel',{}); "
    "a=ic.get('agent_channel',{}); "
    "reason=u.get('reason') or p.get('reason') or p.get('recommended_action') or 'blocked'; "
    "primary=a.get('primary_action') or p.get('recommended_action') or ''; "
    "print('reason=' + str(reason)); "
    "print('primary_action=' + str(primary))"
)


def _q(value: object) -> str:
    return shlex.quote(str(value))


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
    return "; ".join(
        [
            "set -euo pipefail" if errexit else "set -uo pipefail",
            f"export LOOPX_PROJECT={_q(project)}",
            f"export LOOPX_REGISTRY={_q(registry)}",
            f"export LOOPX_RUNTIME_ROOT={_q(runtime_root)}",
            command,
        ]
    )


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


def resolve_visible_launcher(*, requested: str, tmux_bin: str) -> str:
    if requested not in {"auto", "tmux"}:
        raise ValueError("only the tmux visible launcher is supported")
    require_executable(tmux_bin, field="tmux_bin")
    return "tmux"


def build_visible_lane_command(
    *,
    role_id: str,
    role_profile_ref: str,
    role_profile_command: str,
    quota_command: str,
    frontier_command: str,
    bootstrap_command: str,
    codex_bin: str,
    reasoning_effort: str,
    frontier_label: str = "[LoopX frontier]",
) -> str:
    visible_summary = (
        'printf "\\n[LoopX visible acceptance]\\n"; '
        'printf "role_profile=printed\\n"; '
        'printf "quota_guard=printed\\n"; '
        'printf "frontier_or_blocked_reason=printed\\n"; '
        'printf "bootstrap_or_stop=printed\\n"; '
        'printf "loopx_agent_handshake=role_profile_quota_frontier_bootstrap\\n"; '
        'printf "loopx_polling_prompt=visible_bootstrap_prompt\\n"; '
        'printf "takeover_controls=visible\\n"; '
        f"printf 'reasoning_effort=%s\\n' {_q(reasoning_effort)}"
    )
    keep_visible = (
        f"{visible_summary}; "
        'printf "\\n[user takeover]\\ninspect this pane; interrupt, close, or retry manually\\n"; '
        "exec /bin/sh -i"
    )
    return (
        "set -uo pipefail; "
        f"export LOOPX_ROLE_ID={_q(role_id)}; "
        f"export LOOPX_ROLE_PROFILE_REF={_q(role_profile_ref)}; "
        'cd "$LOOPX_PROJECT"; '
        f"{role_profile_command}"
        "printf '\\n[LoopX quota guard]\\n'; "
        f"QUOTA_PACKET=\"$({quota_command} 2>&1)\"; "
        "QUOTA_STATUS=$?; "
        "printf '%s\\n' \"$QUOTA_PACKET\"; "
        "if [ \"$QUOTA_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'quota_command_failed exit=%s\\n' \"$QUOTA_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_QUOTA_GATE_PY)}; "
        "QUOTA_GATE_STATUS=$?; "
        "if [ \"$QUOTA_GATE_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_QUOTA_BLOCKER_SUMMARY_PY)} || true; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '\\n{frontier_label}\\n'; "
        f"{frontier_command}; "
        "FRONTIER_STATUS=$?; "
        "if [ \"$FRONTIER_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'frontier_command_failed exit=%s\\n' \"$FRONTIER_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_bootstrap\\n'; "
        f"{keep_visible}; "
        "fi; "
        "printf '\\n[bootstrap-or-stop]\\ncontinuing_to_visible_bootstrap\\n'; "
        "printf '\\n[Codex bootstrap prompt]\\n'; "
        f"BOOTSTRAP_PROMPT=\"$({bootstrap_command} 2>&1)\"; "
        "BOOTSTRAP_STATUS=$?; "
        "printf '%s\\n' \"$BOOTSTRAP_PROMPT\"; "
        "if [ \"$BOOTSTRAP_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'bootstrap_command_failed exit=%s\\n' \"$BOOTSTRAP_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_codex\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"{visible_summary}; "
        'sleep "${LOOPX_VISIBLE_BOOTSTRAP_PAUSE_SECONDS:-1}"; '
        "printf '\\n[Starting visible Codex exec]\\n'; "
        f"{_q(codex_bin)} exec -c model_reasoning_effort={_q(reasoning_effort)} "
        '--cd "$LOOPX_PROJECT" --sandbox danger-full-access "$BOOTSTRAP_PROMPT"; '
        "CODEX_STATUS=$?; "
        "printf '\\n[Codex CLI exited]\\nexit=%s\\n' \"$CODEX_STATUS\"; "
        f"{keep_visible}"
    )


def build_visible_multi_agent_payload(
    *,
    goal_id: str,
    session_name: str,
    lanes: Iterable[dict[str, object]],
    tmux_bin: str = "tmux",
    frontier_command: str | None = None,
    schema_version: str = "multi_agent_visible_launcher_v0",
) -> dict[str, object]:
    lane_list = [lane for lane in lanes if isinstance(lane, dict)]
    if not lane_list:
        raise ValueError("visible multi-agent launcher has no lanes")
    session = str(session_name or "loopx-visible-agents")
    attach_command = f"{_q(tmux_bin)} attach -t {_q(session)}"
    stop_command = f"{_q(tmux_bin)} kill-session -t {_q(session)}"
    first_frontier = str(frontier_command or lane_list[0].get("frontier") or "")
    frontier_launcher = (
        'cd "$LOOPX_PROJECT"; '
        + first_frontier
        + '; FRONTIER_STATUS=$?; '
        + 'printf "\\n[frontier window ready]\\nexit=%s\\n" "$FRONTIER_STATUS"; '
        + 'exec /bin/sh -i'
    )
    start_script = [
        "set -uo pipefail",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before running}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before running}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before running}",
        (
            f"{_q(tmux_bin)} new-session -d -s {_q(session)} -n frontier "
            f"bash -lc {_q(frontier_launcher)}"
        ),
        (
            f"{_q(tmux_bin)} display-message -t {_q(session)} "
            f"{_q('LoopX visible multi-agent session started; attach before accepting prompts')}"
        ),
    ]
    for lane in lane_list:
        lane_id = str(lane.get("lane_id") or "agent-lane")
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        start_script.append(
            f"{_q(tmux_bin)} new-window -d -t {_q(session)} "
            f"-n {_q(lane_id)} bash -lc {_q(launch_command)}"
        )
    return {
        "ok": True,
        "schema_version": schema_version,
        "mode": "dry_run",
        "goal_id": str(goal_id),
        "session_name": session,
        "lanes": lane_list,
        "commands": {
            "start_script": start_script,
            "attach": attach_command,
            "stop": stop_command,
        },
    }


def _materialize_worker_skills(
    *,
    payload: dict[str, object],
    project: Path,
    source_root: Path,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    for lane in lanes:
        profile = lane.get("role_profile")
        if not isinstance(profile, dict):
            continue
        skill_name = str(profile.get("required_skill") or "").strip()
        source_name = str(profile.get("worker_skill_source") or "").strip()
        if not skill_name or not source_name:
            continue
        source = Path(source_name)
        if not source.is_absolute():
            source = source_root / source
        workspace_values = [project]
        lane_workspace = _lane_workspace(lane, default_project=project)
        if lane_workspace != project:
            workspace_values.append(lane_workspace)
        item = {
            "skill": skill_name,
            "source": source_name,
            "destination": f".codex/skills/{skill_name}/SKILL.md",
            "materialized": False,
            "workspace_count": len(workspace_values),
        }
        if source.is_file():
            for workspace in workspace_values:
                destination = workspace / ".codex" / "skills" / skill_name / "SKILL.md"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            item["materialized"] = True
        else:
            item["missing_source"] = True
        results.append(item)
    return results


def _lane_workspace(lane: dict[str, object], *, default_project: Path) -> Path:
    raw = lane.get("workspace") or lane.get("project")
    if not raw:
        return default_project
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = default_project / path
    return path.resolve()


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
    del terminal_lane_label_template
    require_executable(cli_bin, field="cli_bin")
    require_executable(codex_bin, field="codex_bin")
    chosen = resolve_visible_launcher(requested=requested_launcher, tmux_bin=tmux_bin)
    project, workspace_mode = resolve_visible_workspace(workspace, create=create_workspace, cwd=cwd)
    worker_skills = _materialize_worker_skills(
        payload=payload,
        project=project,
        source_root=cwd,
    )
    result = _launch_with_tmux(
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
    result["worker_skill_materialization"] = worker_skills
    return result, chosen, workspace_mode


def _launch_with_tmux(
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
    started_lanes = []
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or lane_default)
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        lane_project = _lane_workspace(lane, default_project=project)
        if not lane_project.is_dir():
            raise ValueError(f"lane {lane_id} workspace does not exist")
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
                    project=lane_project,
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
    acceptance = _tmux_acceptance(
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


def _tmux_acceptance(
    *,
    tmux_bin: str,
    session: str,
    expected_lanes: list[str],
    env: dict[str, str],
    schema_version: str,
    frontier_or_blocker_markers: Iterable[str],
    frontier_or_blocker_status_markers: Iterable[str],
) -> dict[str, object]:
    frontier_markers = tuple(frontier_or_blocker_markers) + tuple(frontier_or_blocker_status_markers)
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
        observed = [line.strip() for line in list_result.stdout.splitlines() if line.strip()]
        surviving = [lane for lane in expected_lanes if lane in observed]
        pane_checks = []
        for lane in expected_lanes:
            capture = subprocess.run(
                [tmux_bin, "capture-pane", "-pt", f"{session}:{lane}", "-S", "-200"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            ).stdout
            ok = (
                lane in surviving
                and ("[LoopX role profile]" in capture or "role_profile=printed" in capture)
                and ("[LoopX quota guard]" in capture or "quota_guard=printed" in capture)
                and any(marker in capture for marker in frontier_markers)
                and ("[bootstrap-or-stop]" in capture or "bootstrap_or_stop=printed" in capture)
                and "loopx_agent_handshake=role_profile_quota_frontier_bootstrap" in capture
            )
            pane_checks.append(
                {
                    "lane_id": lane,
                    "accepted": ok,
                }
            )
        accepted = list_result.returncode == 0 and len(surviving) == len(expected_lanes) and all(
            item["accepted"] for item in pane_checks
        )
        last_payload = {
            "schema_version": schema_version,
            "accepted": accepted,
            "surviving_lanes": surviving,
            "missing_lanes": [lane for lane in expected_lanes if lane not in surviving],
            "pane_checks": pane_checks,
        }
        if accepted:
            return last_payload
    assert last_payload is not None
    return last_payload
