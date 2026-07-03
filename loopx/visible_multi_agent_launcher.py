from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path

from .capabilities.multi_agent.contract import (
    GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
    INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION,
    PANE_LOCAL_A2A_WAKEUP_PROMPT,
    TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
    VISIBLE_LAUNCHER_ACCEPTANCE_CONTRACT_SCHEMA_VERSION,
    as_string_list as _as_string_list,
    build_decentralized_a2a_driver_contract,
    build_compact_human_status,
    build_generic_role_profile,
    build_tui_multi_agent_runner_contract,
    generic_role_prompt as _generic_role_prompt,
    positive_int_value as _positive_int_value,
    role_skill_profile as _role_skill_profile,
)
from .capabilities.multi_agent.runtime_scripts import (
    CODEX_TUI_EXEC_PY as _CODEX_TUI_EXEC_PY,
    SCOPED_LOOPX_WRAPPER_PY as _SCOPED_LOOPX_WRAPPER_PY,
)


def _q(value: object) -> str:
    return shlex.quote(str(value))


PANE_A2A_WAKEUP_SCHEMA_VERSION = "multi_agent_pane_a2a_wakeup_v0"
PANE_A2A_WAKEUP_PROMPT = PANE_LOCAL_A2A_WAKEUP_PROMPT


def require_executable(command: str, *, field: str) -> str:
    path = shutil.which(command)
    if not path:
        raise ValueError(f"{field} executable not found on PATH: {command}")
    return path


def build_pane_a2a_wakeup_prompt() -> str:
    """Return the fixed prompt broadcast to live Codex TUI panes."""

    return PANE_A2A_WAKEUP_PROMPT


def wake_visible_multi_agent_panes(
    *,
    session_name: str,
    tmux_bin: str = "tmux",
    lanes: Iterable[str] | None = None,
    execute: bool = False,
    prompt: str | None = None,
) -> dict[str, object]:
    """Broadcast the fixed A2A prompt; each pane still decides via LoopX state."""

    session = str(session_name or "").strip()
    if not session:
        raise ValueError("multi-agent wake requires --session-name")
    prompt_text = str(prompt or build_pane_a2a_wakeup_prompt()).strip()
    if not prompt_text:
        raise ValueError("multi-agent wake prompt must not be empty")
    prompt_hash = sha256(prompt_text.encode("utf-8")).hexdigest()[:16]
    target_lanes = [str(lane).strip() for lane in lanes or [] if str(lane).strip()]
    driver_contract = build_decentralized_a2a_driver_contract()

    if execute:
        require_executable(tmux_bin, field="tmux_bin")
        env = os.environ.copy()
        if not target_lanes:
            listed = subprocess.run(
                [tmux_bin, "list-windows", "-t", session, "-F", "#{window_name}"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            target_lanes = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
        if not target_lanes:
            raise ValueError("multi-agent wake found no target panes")
        buffer_name = f"loopx-pane-a2a-wakeup-{prompt_hash}"
        subprocess.run(
            [tmux_bin, "set-buffer", "-b", buffer_name, "--", prompt_text],
            check=True,
            env=env,
        )
        for lane in target_lanes:
            target = f"{session}:{lane}"
            subprocess.run(
                [tmux_bin, "paste-buffer", "-b", buffer_name, "-t", target],
                check=True,
                env=env,
            )
            subprocess.run(
                [tmux_bin, "send-keys", "-t", target, "Enter"],
                check=True,
                env=env,
            )

    return {
        "ok": True,
        "schema_version": PANE_A2A_WAKEUP_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "session_name": session,
        "target_lanes": target_lanes if target_lanes else ["<all-session-windows>"],
        "prompt": prompt_text,
        "prompt_hash": prompt_hash,
        "coordination_model": "decentralized_state_a2a",
        "wakeup_model": "fixed_prompt_broadcast",
        "driver_contract": driver_contract,
        "workflow_driver": False,
        "broadcaster_reads_frontier": driver_contract["broadcaster"]["reads_frontier"],
        "broadcaster_selects_todo": driver_contract["broadcaster"]["selects_todo"],
        "pane_decision_owner": driver_contract["pane"]["decision_owner"],
        "boundary": {
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "runs_worker_turn_directly": False,
        },
    }


def _codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "config.toml"


def _toml_project_header(path: str) -> str:
    return f"[projects.{json.dumps(path)}]"


def _trust_project_in_config_text(text: str, path: str) -> str:
    header = _toml_project_header(path)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        end = index + 1
        while end < len(lines) and not lines[end].lstrip().startswith("["):
            end += 1
        for trust_index in range(index + 1, end):
            if lines[trust_index].strip().startswith("trust_level"):
                lines[trust_index] = 'trust_level = "trusted"'
                break
        else:
            lines.insert(index + 1, 'trust_level = "trusted"')
        return "\n".join(lines) + "\n"
    suffix = "" if not text or text.endswith("\n") else "\n"
    return text + suffix + f"\n{header}\ntrust_level = \"trusted\"\n"


def _codex_trust_candidate_paths(project: Path) -> list[str]:
    candidates = [str(project), os.path.realpath(project)]
    git_root = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if git_root:
        candidates.extend([git_root, os.path.realpath(git_root)])
    trusted: list[str] = []
    seen = set()
    for path in candidates:
        if path and path not in seen:
            seen.add(path)
            trusted.append(path)
    return trusted


def _persist_codex_workspace_trust(paths: Iterable[str]) -> dict[str, object]:
    config = _codex_config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    before = config.read_text(encoding="utf-8") if config.exists() else ""
    after = before
    trusted_paths = []
    for path in paths:
        trusted_paths.append(path)
        after = _trust_project_in_config_text(after, path)
    if after != before:
        config.write_text(after, encoding="utf-8")
    return {
        "persisted": after != before,
        "trusted_path_count": len(trusted_paths),
    }


def runtime_shell_command(
    command: str,
    *,
    project: Path,
    registry: Path,
    runtime_root: Path,
    visible_session: str | None = None,
    errexit: bool = True,
) -> str:
    parts = [
        "set -euo pipefail" if errexit else "set -uo pipefail",
        f"export LOOPX_PROJECT={_q(project)}",
        f"export LOOPX_REGISTRY={_q(registry)}",
        f"export LOOPX_RUNTIME_ROOT={_q(runtime_root)}",
    ]
    if visible_session is not None:
        parts.append(f"export LOOPX_VISIBLE_SESSION={_q(visible_session)}")
    parts.extend(
        [
            'export LOOPX_VISIBLE_ARTIFACT_DIR="${LOOPX_VISIBLE_ARTIFACT_DIR:-$LOOPX_RUNTIME_ROOT/visible-launcher-artifacts/${LOOPX_VISIBLE_SESSION:-default}}"',
            'mkdir -p "$LOOPX_VISIBLE_ARTIFACT_DIR"',
            command,
        ]
    )
    return "; ".join(parts)


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
    bootstrap_command: str,
    codex_bin: str,
    reasoning_effort: str,
    goal_id: str | None = None,
    agent_id: str | None = None,
    worker_turn_command: str | None = None,
    worker_loop_command: str | None = None,
    tick_rounds: int | None = None,
    tick_sleep_seconds: int | None = None,
    visible_lane_count: int | None = None,
) -> str:
    codex_exec_env = (
        f"export LOOPX_CODEX_BIN={_q(codex_bin)}; "
        f"export LOOPX_CODEX_REASONING_EFFORT={_q(reasoning_effort)}; "
    )
    scoped_loopx_wrapper = (
        'LOOPX_REAL_CLI="$(command -v loopx)"; '
        "export LOOPX_REAL_CLI; "
        'mkdir -p "$LOOPX_PROJECT/.local/bin"; '
        f"python3 -c {_q(_SCOPED_LOOPX_WRAPPER_PY)}; "
        'chmod +x "$LOOPX_PROJECT/.local/bin/loopx"; '
        'chmod +x "$LOOPX_PROJECT/.local/bin/loopx-json"; '
        'chmod +x "$LOOPX_PROJECT/.local/bin/loopx-pane-a2a-tick"; '
        'export LOOPX_PANE_LOOPX="$LOOPX_PROJECT/.local/bin/loopx"; '
        'export LOOPX_PANE_LOOPX_JSON="$LOOPX_PROJECT/.local/bin/loopx-json"; '
        'export LOOPX_PANE_A2A_TICK="$LOOPX_PROJECT/.local/bin/loopx-pane-a2a-tick"; '
        'export LOOPX_VISIBLE_FORCE_MARKDOWN="${LOOPX_VISIBLE_FORCE_MARKDOWN:-1}"; '
        'export PATH="$LOOPX_PROJECT/.local/bin:$PATH"; '
    )
    pane_a2a_env = ""
    if goal_id:
        pane_a2a_env += f"export LOOPX_GOAL_ID={_q(goal_id)}; "
    if agent_id:
        pane_a2a_env += f"export LOOPX_AGENT_ID={_q(agent_id)}; "
    if worker_turn_command:
        pane_a2a_env += f"export LOOPX_PANE_WORKER_TURN={_q(worker_turn_command)}; "
    if worker_loop_command:
        pane_a2a_env += f"export LOOPX_PANE_WORKER_LOOP={_q(worker_loop_command)}; "
    if tick_rounds and tick_rounds > 1:
        pane_a2a_env += f"export LOOPX_PANE_TICK_ROUNDS={_q(tick_rounds)}; "
    if tick_sleep_seconds and tick_sleep_seconds > 0:
        pane_a2a_env += f"export LOOPX_PANE_TICK_SLEEP_SECONDS={_q(tick_sleep_seconds)}; "
    if visible_lane_count and visible_lane_count > 0:
        pane_a2a_env += f"export LOOPX_VISIBLE_LANE_COUNT={_q(visible_lane_count)}; "
    return (
        "set -uo pipefail; "
        "export LOOPX_VISIBLE_TUI_SILENT_BOOTSTRAP=1; "
        f"export LOOPX_ROLE_ID={_q(role_id)}; "
        f"export LOOPX_ROLE_PROFILE_REF={_q(role_profile_ref)}; "
        'export LOOPX_PANE_ARTIFACT_DIR="${LOOPX_PANE_ARTIFACT_DIR:-$LOOPX_VISIBLE_ARTIFACT_DIR/${LOOPX_ROLE_ID:-lane}}"; '
        'mkdir -p "$LOOPX_PANE_ARTIFACT_DIR"; '
        'cd "$LOOPX_PROJECT"; '
        f"{scoped_loopx_wrapper}"
        f"{pane_a2a_env}"
        f"{role_profile_command}"
        'VISIBLE_ARTIFACT_PREFIX="${LOOPX_LANE_ID:-${LOOPX_ROLE_ID:-lane}}"; '
        f"BOOTSTRAP_PROMPT=\"$({bootstrap_command} 2>&1)\"; "
        "BOOTSTRAP_STATUS=$?; "
        "export BOOTSTRAP_PROMPT; "
        'BOOTSTRAP_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$VISIBLE_ARTIFACT_PREFIX.bootstrap-prompt.public.txt"; '
        'printf "%s\\n" "$BOOTSTRAP_PROMPT" > "$BOOTSTRAP_ARTIFACT"; '
        "if [ \"$BOOTSTRAP_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'bootstrap_command_failed exit=%s\\n' \"$BOOTSTRAP_STATUS\"; "
        "exec /bin/sh -i; "
        "fi; "
        'PANE_A2A_TICK_ARTIFACT="$LOOPX_PANE_ARTIFACT_DIR/pane-a2a-tick.output.txt"; '
        '"$LOOPX_PANE_A2A_TICK" > "$PANE_A2A_TICK_ARTIFACT" 2>&1; '
        "PANE_A2A_TICK_STATUS=$?; "
        "if [ \"$PANE_A2A_TICK_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX pane A2A blocked]\\n'; "
        "printf 'tick_exit=%s artifact=%s\\n' \"$PANE_A2A_TICK_STATUS\" \"$PANE_A2A_TICK_ARTIFACT\"; "
        "fi; "
        "export LOOPX_CODEX_TUI_MODE=interactive; "
        "export LOOPX_CODEX_TUI_PROMPT_ARTIFACT=\"$BOOTSTRAP_ARTIFACT\"; "
        f"{codex_exec_env}"
        f"exec python3 -c {_q(_CODEX_TUI_EXEC_PY)}"
    )


def build_visible_multi_agent_payload(
    *,
    goal_id: str,
    session_name: str,
    lanes: Iterable[dict[str, object]],
    tmux_bin: str = "tmux",
    schema_version: str = "multi_agent_visible_launcher_v0",
) -> dict[str, object]:
    lane_list = [lane for lane in lanes if isinstance(lane, dict)]
    if not lane_list:
        raise ValueError("visible multi-agent launcher has no lanes")
    session = str(session_name or "loopx-visible-agents")
    attach_command = f"{_q(tmux_bin)} attach -t {_q(session)}"
    stop_command = f"{_q(tmux_bin)} kill-session -t {_q(session)}"
    retry_command = (
        "rerun the same visible launcher packet after refreshing quota, "
        "frontier, and bootstrap"
    )
    all_lane_workspace_isolation = all(
        bool(lane.get("workspace") or lane.get("project")) for lane in lane_list
    )
    runner_contract = build_tui_multi_agent_runner_contract(
        session_name=session,
        lane_count=len(lane_list),
        attach_command=attach_command,
        stop_command=stop_command,
        retry_command=retry_command,
        all_lane_workspace_isolation=all_lane_workspace_isolation,
    )
    start_script = [
        "set -uo pipefail",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before running}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before running}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before running}",
        f"export LOOPX_VISIBLE_SESSION={_q(session)}",
        'export LOOPX_VISIBLE_ARTIFACT_DIR="${LOOPX_VISIBLE_ARTIFACT_DIR:-$LOOPX_RUNTIME_ROOT/visible-launcher-artifacts/$LOOPX_VISIBLE_SESSION}"',
        'mkdir -p "$LOOPX_VISIBLE_ARTIFACT_DIR"',
    ]
    for index, lane in enumerate(lane_list):
        lane_id = str(lane.get("lane_id") or "agent-lane")
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        if index == 0:
            start_script.append(
                f"{_q(tmux_bin)} new-session -d -s {_q(session)} "
                f"-n {_q(lane_id)} bash -lc {_q(launch_command)}"
            )
            start_script.append(f"{_q(tmux_bin)} set-option -t {_q(session)} remain-on-exit on")
        else:
            start_script.append(
                f"{_q(tmux_bin)} new-window -d -t {_q(session)} "
                f"-n {_q(lane_id)} bash -lc {_q(launch_command)}"
            )
    start_script.append(
        f"{_q(tmux_bin)} display-message -t {_q(session)} "
        f"{_q('LoopX visible multi-agent Codex TUI session started; each window is interactive')}"
    )
    return {
        "ok": True,
        "schema_version": schema_version,
        "mode": "dry_run",
        "goal_id": str(goal_id),
        "session_name": session,
        "lanes": lane_list,
        "runner_contract": runner_contract,
        "interactive_tui_contract": {
            "schema_version": INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION,
            "runner_contract": TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
            "human_pane": [
                "codex_cli_tui",
                "role_prompt_inside_codex",
                "normal_user_typing",
                "normal_codex_tool_output",
                "takeover_controls",
            ],
            "machine_artifacts": [
                "quota.public.json",
                "frontier.public.json",
                "bootstrap-prompt.public.txt",
                "role_local_public_artifacts",
            ],
            "machine_json_policy": "file_or_explicit_machine_channel_only",
            "visible_json_policy": "not_printed_before_tui",
            "codex_surface": "interactive_cli_tui",
            "forbidden_visible_content": [
                "raw_quota_json",
                "raw_frontier_json",
                "raw_role_profile_json",
                "pre_codex_character_stream",
                "credentials",
                "raw_private_logs",
                "absolute_local_artifact_paths",
            ],
        },
        "commands": {
            "start_script": start_script,
            "attach": attach_command,
            "stop": stop_command,
            "retry": retry_command,
        },
        "acceptance": {
            "schema_version": VISIBLE_LAUNCHER_ACCEPTANCE_CONTRACT_SCHEMA_VERSION,
            "required_runtime_shape": [
                "one_tmux_window_per_role",
                "each_role_window_execs_codex_cli_tui",
                "no_frontier_or_json_status_window",
                "no_pre_codex_character_stream",
            ],
            "interactive_tui_contract": INTERACTIVE_TUI_CONTRACT_SCHEMA_VERSION,
            "runner_contract": TUI_MULTI_AGENT_RUNNER_CONTRACT_SCHEMA_VERSION,
            "machine_json_file_bound": True,
            "codex_tui_interactive": True,
        },
        "boundary": {
            "starts_visible_processes": False,
            "runs_agent_processes": False,
            "writes_loopx_state": False,
            "spends_loopx_quota": False,
            "reads_raw_transcripts": False,
            "reads_session_files": False,
            "reads_credentials": False,
            "hidden_prompt_injection": False,
            "shared_goal_surface": True,
            "all_lane_workspace_isolation": all_lane_workspace_isolation,
            "public_safe_redaction": True,
        },
    }


def build_visible_multi_agent_payload_from_spec(
    spec: dict[str, object],
    *,
    tmux_bin: str = "tmux",
    cli_bin: str = "loopx",
    codex_bin: str = "codex",
) -> dict[str, object]:
    """Build a visible launcher packet from a small user-facing role spec."""

    if not isinstance(spec, dict):
        raise ValueError("multi-agent launch spec must be an object")
    goal_id = str(spec.get("goal_id") or "").strip()
    if not goal_id:
        raise ValueError("multi-agent launch spec requires goal_id")
    roles = spec.get("roles") or spec.get("agents") or spec.get("lanes")
    if not isinstance(roles, list) or not roles:
        raise ValueError("multi-agent launch spec requires a non-empty roles list")
    session_name = str(spec.get("session_name") or f"loopx-{_script_slug(goal_id)}-agents")
    default_reasoning_effort = str(
        spec.get("default_reasoning_effort") or spec.get("reasoning_effort") or "high"
    )
    lanes: list[dict[str, object]] = []
    for index, raw_role in enumerate(roles, start=1):
        if not isinstance(raw_role, dict):
            raise ValueError(f"role #{index} must be an object")
        agent_id = str(raw_role.get("agent_id") or "").strip()
        if not agent_id:
            raise ValueError(f"role #{index} requires agent_id")
        lane_id = str(raw_role.get("lane_id") or raw_role.get("role_id") or agent_id).strip()
        role_id = str(raw_role.get("role_id") or lane_id).strip()
        scope = str(
            raw_role.get("scope")
            or raw_role.get("agent_scope")
            or raw_role.get("responsibility")
            or ""
        ).strip()
        responsibility = str(raw_role.get("responsibility") or scope or role_id).strip()
        role_profile_ref = str(
            raw_role.get("role_profile_ref")
            or f"generic_multi_agent_launch_spec_v0:{role_id}"
        ).strip()
        handoff_hints = _as_string_list(
            raw_role.get("handoff")
            or raw_role.get("handoff_hints")
            or raw_role.get("interaction_hints")
        )
        skill_profile = _role_skill_profile(raw_role.get("skill"))
        reasoning_effort = str(raw_role.get("reasoning_effort") or default_reasoning_effort)
        worker_turn_command = str(raw_role.get("worker_turn_command") or "").strip()
        worker_loop_command = str(raw_role.get("worker_loop_command") or "").strip()
        tick_rounds = _positive_int_value(
            raw_role.get("tick_rounds") or raw_role.get("auto_tick_rounds"),
            default=1,
        )
        tick_sleep_seconds = _positive_int_value(raw_role.get("tick_sleep_seconds"), default=3)
        role_profile = build_generic_role_profile(
            role_id=role_id,
            agent_id=agent_id,
            scope=scope,
            responsibility=responsibility,
            handoff_hints=handoff_hints,
            skill_profile=skill_profile,
            extra_profile=raw_role.get("role_profile"),
        )
        lane_slug = _script_slug(lane_id)
        role_profile_json = json.dumps(role_profile, ensure_ascii=False, sort_keys=True)
        role_profile_command = (
            "mkdir -p \"$LOOPX_VISIBLE_ARTIFACT_DIR\"; "
            f"printf '%s\\n' {_q(role_profile_json)} "
            f"> \"$LOOPX_VISIBLE_ARTIFACT_DIR/{lane_slug}.role-profile.public.json\"; "
        )
        prompt = _generic_role_prompt(
            goal_id=goal_id,
            agent_id=agent_id,
            role_id=role_id,
            scope=scope,
            handoff_hints=handoff_hints,
            skill_name=skill_profile.get("required_skill"),
        )
        bootstrap_command = f"printf '%s\\n' {_q(prompt)}"
        lane = {
            "lane_id": lane_id,
            "agent_id": agent_id,
            "role_id": role_id,
            "responsibility": responsibility,
            "agent_scope": scope,
            "handoff_hints": handoff_hints,
            "role_profile": role_profile,
            "role_profile_ref": role_profile_ref,
            "quota_guard": (
                "mkdir -p \"$LOOPX_PANE_ARTIFACT_DIR\" && "
                "$LOOPX_PANE_LOOPX_JSON quota should-run "
                f"--goal-id {_q(goal_id)} --agent-id {_q(agent_id)} "
                "> \"$LOOPX_PANE_ARTIFACT_DIR/quota.public.json\""
            ),
            "frontier": "agent-scoped LoopX todo/quota/frontier projection",
            "pane_local_a2a": {
                "tick_command": "$LOOPX_PANE_A2A_TICK",
                "worker_turn_configured": bool(worker_turn_command),
                "worker_loop_configured": bool(worker_loop_command),
                "auto_start": True,
                "tick_rounds": tick_rounds,
                "tick_sleep_seconds": tick_sleep_seconds,
            },
            "bootstrap_message": "role_prompt_inside_codex_tui",
            "visible_launch_command": build_visible_lane_command(
                role_id=role_id,
                role_profile_ref=role_profile_ref,
                role_profile_command=role_profile_command,
                bootstrap_command=bootstrap_command,
                codex_bin=codex_bin,
                reasoning_effort=reasoning_effort,
                goal_id=goal_id,
                agent_id=agent_id,
                worker_turn_command=worker_turn_command,
                worker_loop_command=worker_loop_command,
                tick_rounds=tick_rounds,
                tick_sleep_seconds=tick_sleep_seconds,
                visible_lane_count=len(roles),
            ),
            "reasoning_effort": reasoning_effort,
            "lane_timeline": [
                "role_profile",
                "auto_start_pane_local_a2a_tick",
                "codex_tui",
                "frontier",
            ],
        }
        if raw_role.get("workspace") or raw_role.get("project"):
            lane["workspace"] = str(raw_role.get("workspace") or raw_role.get("project"))
        lanes.append(lane)

    packet = build_visible_multi_agent_payload(
        goal_id=goal_id,
        session_name=session_name,
        lanes=lanes,
        tmux_bin=tmux_bin,
    )
    packet.update(
        {
            "product_spec": {
                "schema_version": "generic_multi_agent_launch_spec_v0",
                "input_shape": ["goal_id", "session_name", "roles"],
                "role_fields": [
                    "agent_id",
                    "role_id",
                    "scope",
                    "skill",
                    "handoff_hints",
                    "reasoning_effort",
                    "worker_turn_command",
                    "worker_loop_command",
                ],
                "role_count": len(lanes),
                "role_profile_schema_version": GENERIC_MULTI_AGENT_ROLE_PROFILE_SCHEMA_VERSION,
                "uses_generic_runner": True,
                "domain_specific": False,
            },
            "reasoning_contract": {
                "default_reasoning_effort": default_reasoning_effort,
                "codex_cli_config_key": "model_reasoning_effort",
            },
            "shared_goal_surface": {
                "shared_goal_id": goal_id,
                "shared_state_route": "LOOPX_REGISTRY_and_LOOPX_RUNTIME_ROOT",
                "shared_frontier": True,
                "lane_identity_source": "role_profile_plus_agent_scoped_quota",
                "all_lane_workspace_isolation": any("workspace" in lane for lane in lanes),
                "mutation_isolation_policy": (
                    "mutating attempts require agent-scoped todo/frontier and a claimed "
                    "worktree or equivalent execution boundary"
                ),
            },
            "cli_contract": {
                "cli_bin": cli_bin,
                "codex_bin": codex_bin,
                "tmux_bin": tmux_bin,
                "machine_json_policy": "artifact_only_in_visible_panes",
            },
        }
    )
    packet["compact_human_status"] = build_compact_human_status(packet)
    return packet


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
        source, source_resolution = _resolve_worker_skill_source(
            source_name,
            source_root=source_root,
        )
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
            "source_resolution": source_resolution,
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


def _resolve_worker_skill_source(source_name: str, *, source_root: Path) -> tuple[Path, str]:
    source = Path(source_name)
    if source.is_absolute():
        return source, "absolute"

    package_root = Path(__file__).resolve().parents[1]
    candidates = [
        ("source_root", source_root / source),
        ("package_root", package_root / source),
        ("module_root", Path(__file__).resolve().parent / source),
    ]
    seen: set[Path] = set()
    for label, candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved, label
    return (source_root / source), "missing"


def _worker_skill_materialization_errors(items: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    for item in items:
        if item.get("missing_source"):
            errors.append(f"{item.get('skill')}: missing {item.get('source')}")
        elif item and not item.get("materialized"):
            errors.append(f"{item.get('skill')}: not materialized")
    return errors


def _lane_workspace(lane: dict[str, object], *, default_project: Path) -> Path:
    raw = lane.get("workspace") or lane.get("project")
    if not raw:
        return default_project
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = default_project / path
    return path.resolve()


def _script_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    slug = "-".join(part for part in slug.split("-") if part)
    return (slug or "lane")[:80]


def _write_tmux_script(*, script_dir: Path, name: str, command: str) -> Path:
    script_dir.mkdir(parents=True, exist_ok=True)
    script = script_dir / f"{_script_slug(name)}.sh"
    script.write_text(f"#!/usr/bin/env bash\n{command}\n", encoding="utf-8")
    script.chmod(0o700)
    return script


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
    codex_trust_workspace: bool = False,
    source_root: Path | None = None,
    launch_result_schema: str = "multi_agent_visible_launch_result_v0",
    acceptance_schema: str = "multi_agent_visible_launch_acceptance_v0",
    lane_default: str = "agent-lane",
) -> tuple[dict[str, object], str, str]:
    require_executable(cli_bin, field="cli_bin")
    require_executable(codex_bin, field="codex_bin")
    chosen = resolve_visible_launcher(requested=requested_launcher, tmux_bin=tmux_bin)
    project, workspace_mode = resolve_visible_workspace(workspace, create=create_workspace, cwd=cwd)
    worker_skills = _materialize_worker_skills(
        payload=payload,
        project=project,
        source_root=source_root or cwd,
    )
    worker_skill_errors = _worker_skill_materialization_errors(worker_skills)
    if worker_skill_errors:
        raise ValueError(
            "worker-local skill materialization failed: "
            + "; ".join(worker_skill_errors)
        )
    result = _launch_with_tmux(
        payload=payload,
        project=project,
        workspace_mode=workspace_mode,
        registry=registry,
        runtime_root=runtime_root,
        tmux_bin=tmux_bin,
        codex_bin=codex_bin,
        attach=attach,
        replace_existing=replace_existing,
        launch_result_schema=launch_result_schema,
        acceptance_schema=acceptance_schema,
        lane_default=lane_default,
        codex_trust_workspace=codex_trust_workspace,
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
    codex_bin: str,
    attach: bool,
    replace_existing: bool,
    launch_result_schema: str,
    acceptance_schema: str,
    lane_default: str,
    codex_trust_workspace: bool,
) -> dict[str, object]:
    session = str(payload.get("session_name") or "loopx-visible-agents")
    lanes = [item for item in payload.get("lanes", []) if isinstance(item, dict)]
    if not lanes:
        raise ValueError("visible multi-agent launcher has no lanes to launch")
    codex_trust_config: dict[str, object] = {
        "persisted": False,
        "trusted_path_count": 0,
    }
    if codex_trust_workspace:
        trust_paths: list[str] = []
        for lane in lanes:
            trust_paths.extend(
                _codex_trust_candidate_paths(_lane_workspace(lane, default_project=project))
            )
        codex_trust_config = _persist_codex_workspace_trust(trust_paths)

    env = os.environ.copy()
    env.update(
        {
            "LOOPX_PROJECT": str(project),
            "LOOPX_REGISTRY": str(registry),
            "LOOPX_RUNTIME_ROOT": str(runtime_root),
            "LOOPX_VISIBLE_SESSION": session,
            "LOOPX_CODEX_TRUST_WORKSPACE": "1" if codex_trust_workspace else "0",
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

    script_dir = runtime_root / "visible-launcher" / _script_slug(session)
    started_lanes = []
    launcher_scripts: dict[str, str] = {}
    for index, lane in enumerate(lanes):
        lane_id = str(lane.get("lane_id") or lane_default)
        launch_command = str(lane.get("visible_launch_command") or "")
        if not launch_command:
            raise ValueError(f"lane {lane_id} is missing visible_launch_command")
        lane_project = _lane_workspace(lane, default_project=project)
        if not lane_project.is_dir():
            raise ValueError(f"lane {lane_id} workspace does not exist")
        lane_script = _write_tmux_script(
            script_dir=script_dir,
            name=lane_id,
            command=runtime_shell_command(
                f"export LOOPX_CODEX_TRUST_WORKSPACE={_q('1' if codex_trust_workspace else '0')}; "
                f"export LOOPX_VISIBLE_LANE_COUNT={_q(len(lanes))}; "
                f"{launch_command}",
                project=lane_project,
                registry=registry,
                runtime_root=runtime_root,
                visible_session=session,
                errexit=False,
            ),
        )
        if index == 0:
            subprocess.run(
                [
                    tmux_bin,
                    "new-session",
                    "-d",
                    "-s",
                    session,
                    "-n",
                    lane_id,
                    "bash",
                    str(lane_script),
                ],
                check=True,
                env=env,
            )
            subprocess.run(
                [tmux_bin, "set-option", "-t", session, "remain-on-exit", "on"],
                check=False,
                env=env,
            )
        else:
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
                    str(lane_script),
                ],
                check=True,
                env=env,
            )
        started_lanes.append(lane_id)
        launcher_scripts[lane_id] = str(lane_script)
    if attach:
        subprocess.run([tmux_bin, "attach", "-t", session], check=True, env=env)
    acceptance = _tmux_acceptance(
        tmux_bin=tmux_bin,
        session=session,
        expected_lanes=started_lanes,
        env=env,
        schema_version=acceptance_schema,
        lane_scripts=launcher_scripts,
        codex_bin=codex_bin,
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
        "codex_trust_workspace": codex_trust_workspace,
        "codex_trust_config": codex_trust_config,
        "codex_trust_scope": (
            "persisted_selected_workspace_and_git_root"
            if codex_trust_workspace
            else "native_codex_trust_prompt"
        ),
        "script_mode": "runtime_local_files",
        "launcher_script_count": len(launcher_scripts),
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
    lane_scripts: dict[str, str],
    codex_bin: str,
) -> dict[str, object]:
    codex_name = Path(codex_bin).name or "codex"
    last_payload: dict[str, object] | None = None
    min_stable_acceptance_attempts = 12
    for attempt in range(32):
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
            current_command = subprocess.run(
                [tmux_bin, "display-message", "-p", "-t", f"{session}:{lane}", "#{pane_current_command}"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            ).stdout.strip()
            script_path = Path(lane_scripts.get(lane, ""))
            script_text = script_path.read_text(encoding="utf-8") if script_path.is_file() else ""
            failure_markers = [
                "stopped_before_bootstrap",
                "stopped_before_codex",
                "quota_wait_timeout",
                "bootstrap_command_failed",
            ]
            trust_prompt_markers = [
                "Do you trust the contents of this directory?",
                "Working with untrusted contents",
                "Trusting will apply to the repository root:",
                "Press enter to continue",
            ]
            blocked_before_bootstrap = any(marker in capture for marker in failure_markers)
            trust_prompt_blocked = any(marker in capture for marker in trust_prompt_markers)
            script_words = script_text.replace("\n", " ").replace(";", " ").split()
            uses_headless_codex_subcommand = any(
                Path(word).name == codex_name
                and index + 1 < len(script_words)
                and script_words[index + 1] == "exec"
                for index, word in enumerate(script_words)
            )
            script_execs_codex_tui = (
                "exec " in script_text
                and codex_name in script_text
                and "| python3" not in script_text
                and not uses_headless_codex_subcommand
            )
            ok = (
                lane in surviving
                and not blocked_before_bootstrap
                and not trust_prompt_blocked
                and script_execs_codex_tui
            )
            pane_checks.append(
                {
                    "lane_id": lane,
                    "accepted": ok,
                    "blocked_before_bootstrap": blocked_before_bootstrap,
                    "trust_prompt_blocked": trust_prompt_blocked,
                    "interactive_codex_tui_script": script_execs_codex_tui,
                    "pane_current_command": current_command,
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
        if any(item["trust_prompt_blocked"] for item in pane_checks):
            return last_payload
        if accepted and attempt + 1 >= min_stable_acceptance_attempts:
            return last_payload
    assert last_payload is not None
    return last_payload
