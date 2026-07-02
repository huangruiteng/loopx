from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path


_SCOPED_LOOPX_WRAPPER_PY = r"""
import os
from pathlib import Path

project = Path(os.environ["LOOPX_PROJECT"])
real = os.environ["LOOPX_REAL_CLI"]
registry = os.environ["LOOPX_REGISTRY"]
runtime = os.environ["LOOPX_RUNTIME_ROOT"]
bin_dir = project / ".local" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)

json_target = bin_dir / "loopx-json"
json_target.write_text(
    "#!/usr/bin/env python3\n"
    "import os, stat, sys\n"
    f"real = {real!r}\n"
    f"registry = {registry!r}\n"
    f"runtime = {runtime!r}\n"
    "explicit = os.environ.get('LOOPX_MACHINE_JSON') == '1' or os.environ.get('LOOPX_ALLOW_TTY_JSON') == '1' or os.environ.get('LOOPX_ALLOW_VISIBLE_JSON') == '1'\n"
    "stdout_mode = os.fstat(sys.stdout.fileno()).st_mode\n"
    "stdout_is_file = stat.S_ISREG(stdout_mode)\n"
    "if not explicit and not stdout_is_file:\n"
    "    print('\\n[LoopX machine JSON hidden]\\nraw JSON is not printed in visible panes.\\n')\n"
    "    print('Use $LOOPX_PANE_LOOPX for human-readable output, or redirect machine JSON:')\n"
    "    print('  $LOOPX_PANE_LOOPX_JSON ... --format json > .local/<role>/<name>.public.json')\n"
    "    print('Internal launcher pipes must set LOOPX_MACHINE_JSON=1 explicitly.')\n"
    "    raise SystemExit(2)\n"
    "os.execv(real, [real, '--registry', registry, '--runtime-root', runtime] + sys.argv[1:])\n",
    encoding="utf-8",
)
json_target.chmod(0o700)

human_target = bin_dir / "loopx"
human_target.write_text(
    "#!/usr/bin/env python3\n"
    "import os, sys\n"
    f"real = {real!r}\n"
    f"registry = {registry!r}\n"
    f"runtime = {runtime!r}\n"
    "args = sys.argv[1:]\n"
    "force = os.environ.get('LOOPX_VISIBLE_FORCE_MARKDOWN', '1') != '0'\n"
    "machine_json = os.environ.get('LOOPX_MACHINE_JSON') == '1'\n"
    "changed = False\n"
    "if force and not machine_json:\n"
    "    rewritten = []\n"
    "    index = 0\n"
    "    while index < len(args):\n"
    "        arg = args[index]\n"
    "        if arg == '--format' and index + 1 < len(args):\n"
    "            rewritten.append(arg)\n"
    "            value = args[index + 1]\n"
    "            if value == 'json':\n"
    "                value = 'markdown'\n"
    "                changed = True\n"
    "            rewritten.append(value)\n"
    "            index += 2\n"
    "            continue\n"
    "        if arg == '--format=json':\n"
    "            arg = '--format=markdown'\n"
    "            changed = True\n"
    "        rewritten.append(arg)\n"
    "        index += 1\n"
    "    args = rewritten\n"
    "if changed:\n"
    "    print('\\n[LoopX human view]\\nformat=markdown; machine_json_wrapper=$LOOPX_PANE_LOOPX_JSON\\n', flush=True)\n"
    "os.execv(real, [real, '--registry', registry, '--runtime-root', runtime] + args)\n",
    encoding="utf-8",
)
human_target.chmod(0o700)
"""

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
) -> str:
    trust_config_py = (
        'import json, os; '
        'print("projects." + json.dumps(os.environ["LOOPX_PROJECT"]) + '
        '".trust_level=\\"trusted\\"")'
    )
    codex_trust_args = (
        'if [ "${LOOPX_CODEX_TRUST_WORKSPACE:-0}" = "1" ]; then '
        f'CODEX_TRUST_CONFIG="$(python3 -c {_q(trust_config_py)})"; '
        f"exec {_q(codex_bin)} "
        '-c "$CODEX_TRUST_CONFIG" '
        f"-c model_reasoning_effort={_q(reasoning_effort)} "
        '-C "$LOOPX_PROJECT" "$BOOTSTRAP_PROMPT"; '
        "fi; "
    )
    scoped_loopx_wrapper = (
        'LOOPX_REAL_CLI="$(command -v loopx)"; '
        "export LOOPX_REAL_CLI; "
        'mkdir -p "$LOOPX_PROJECT/.local/bin"; '
        f"python3 -c {_q(_SCOPED_LOOPX_WRAPPER_PY)}; "
        'chmod +x "$LOOPX_PROJECT/.local/bin/loopx"; '
        'chmod +x "$LOOPX_PROJECT/.local/bin/loopx-json"; '
        'export LOOPX_PANE_LOOPX="$LOOPX_PROJECT/.local/bin/loopx"; '
        'export LOOPX_PANE_LOOPX_JSON="$LOOPX_PROJECT/.local/bin/loopx-json"; '
        'export LOOPX_VISIBLE_FORCE_MARKDOWN="${LOOPX_VISIBLE_FORCE_MARKDOWN:-1}"; '
        'export PATH="$LOOPX_PROJECT/.local/bin:$PATH"; '
    )
    return (
        "set -uo pipefail; "
        "export LOOPX_VISIBLE_TUI_SILENT_BOOTSTRAP=1; "
        f"export LOOPX_ROLE_ID={_q(role_id)}; "
        f"export LOOPX_ROLE_PROFILE_REF={_q(role_profile_ref)}; "
        'cd "$LOOPX_PROJECT"; '
        f"{scoped_loopx_wrapper}"
        f"{role_profile_command}"
        'VISIBLE_ARTIFACT_PREFIX="${LOOPX_LANE_ID:-${LOOPX_ROLE_ID:-lane}}"; '
        f"BOOTSTRAP_PROMPT=\"$({bootstrap_command} 2>&1)\"; "
        "BOOTSTRAP_STATUS=$?; "
        'BOOTSTRAP_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$VISIBLE_ARTIFACT_PREFIX.bootstrap-prompt.public.txt"; '
        'printf "%s\\n" "$BOOTSTRAP_PROMPT" > "$BOOTSTRAP_ARTIFACT"; '
        "if [ \"$BOOTSTRAP_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'bootstrap_command_failed exit=%s\\n' \"$BOOTSTRAP_STATUS\"; "
        "exec /bin/sh -i; "
        "fi; "
        "export LOOPX_CODEX_TUI_MODE=interactive; "
        "export LOOPX_CODEX_TUI_PROMPT_ARTIFACT=\"$BOOTSTRAP_ARTIFACT\"; "
        f"{codex_trust_args}"
        f"exec {_q(codex_bin)} -c model_reasoning_effort={_q(reasoning_effort)} "
        '-C "$LOOPX_PROJECT" "$BOOTSTRAP_PROMPT"'
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
        "interactive_tui_contract": {
            "schema_version": "multi_agent_visible_interactive_tui_contract_v0",
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
            "schema_version": "multi_agent_visible_launcher_acceptance_contract_v0",
            "required_runtime_shape": [
                "one_tmux_window_per_role",
                "each_role_window_execs_codex_cli_tui",
                "no_frontier_or_json_status_window",
                "no_pre_codex_character_stream",
            ],
            "interactive_tui_contract": "multi_agent_visible_interactive_tui_contract_v0",
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
            "all_lane_workspace_isolation": False,
            "public_safe_redaction": True,
        },
    }


def _as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _role_skill_profile(skill: object) -> dict[str, str]:
    if not skill:
        return {}
    if isinstance(skill, str):
        source = skill.strip()
        if not source:
            return {}
        name = Path(source).parent.name or Path(source).stem or "worker-skill"
        return {"required_skill": name, "worker_skill_source": source}
    if not isinstance(skill, dict):
        return {}
    name = str(skill.get("name") or skill.get("skill_name") or "").strip()
    source = str(skill.get("source") or skill.get("path") or "").strip()
    if not name and source:
        name = Path(source).parent.name or Path(source).stem
    if not name or not source:
        return {}
    return {"required_skill": name, "worker_skill_source": source}


def _generic_role_prompt(
    *,
    goal_id: str,
    agent_id: str,
    role_id: str,
    scope: str,
    handoff_hints: list[str],
    skill_name: str | None,
) -> str:
    lines = [
        "LoopX multi-agent role",
        f"Goal: {goal_id}",
        f"Agent: {agent_id}",
        f"Role: {role_id}",
    ]
    if scope:
        lines.extend(["", "Scope:", scope])
    if skill_name:
        lines.extend(["", "Local skill:", f"Use ${skill_name} when it applies to this role."])
    lines.extend(
        [
            "",
            "How to work:",
            "- Treat LoopX state as the shared A2A surface.",
            "- Start by reading your agent-scoped todo/quota/frontier with $LOOPX_PANE_LOOPX.",
            "- Keep machine JSON redirected through $LOOPX_PANE_LOOPX_JSON into .local artifacts.",
            "- Write compact public-safe evidence before completing or handing off a todo.",
            "- The user may type into this pane; respond like a normal Codex CLI agent.",
        ]
    )
    if handoff_hints:
        lines.append("")
        lines.append("Handoff hints:")
        lines.extend(f"- {hint}" for hint in handoff_hints)
    return "\n".join(lines)


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
        handoff_hints = _as_string_list(
            raw_role.get("handoff")
            or raw_role.get("handoff_hints")
            or raw_role.get("interaction_hints")
        )
        skill_profile = _role_skill_profile(raw_role.get("skill"))
        reasoning_effort = str(raw_role.get("reasoning_effort") or default_reasoning_effort)
        role_profile = {
            "schema_version": "generic_multi_agent_role_profile_v0",
            "role_id": role_id,
            "agent_id": agent_id,
            "agent_scope": scope,
            "responsibility": responsibility,
            "handoff_hints": handoff_hints,
        }
        role_profile.update(skill_profile)
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
            "role_profile_ref": f"generic_multi_agent_launch_spec_v0:{role_id}",
            "quota_guard": (
                "$LOOPX_PANE_LOOPX_JSON quota should-run "
                f"--goal-id {_q(goal_id)} --agent-id {_q(agent_id)} "
                f"> .local/{lane_slug}/quota.public.json"
            ),
            "frontier": "agent-scoped LoopX todo/quota/frontier projection",
            "bootstrap_message": "role_prompt_inside_codex_tui",
            "visible_launch_command": build_visible_lane_command(
                role_id=role_id,
                role_profile_ref=f"generic_multi_agent_launch_spec_v0:{role_id}",
                role_profile_command=role_profile_command,
                bootstrap_command=bootstrap_command,
                codex_bin=codex_bin,
                reasoning_effort=reasoning_effort,
            ),
            "reasoning_effort": reasoning_effort,
            "lane_timeline": ["role_profile", "quota_guard", "frontier", "codex_tui"],
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
                ],
                "role_count": len(lanes),
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
        "codex_trust_scope": (
            "per_invocation_selected_workspace"
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
            blocked_before_bootstrap = any(marker in capture for marker in failure_markers)
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
            ok = lane in surviving and not blocked_before_bootstrap and script_execs_codex_tui
            pane_checks.append(
                {
                    "lane_id": lane,
                    "accepted": ok,
                    "blocked_before_bootstrap": blocked_before_bootstrap,
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
        if accepted:
            return last_payload
    assert last_payload is not None
    return last_payload
