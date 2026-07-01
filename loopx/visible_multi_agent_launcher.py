from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path


_QUOTA_READY_PY = (
    "import json,sys; "
    "p=json.load(sys.stdin); "
    "u=p.get('interaction_contract',{}).get('user_channel',{}); "
    "a=p.get('interaction_contract',{}).get('agent_channel',{}); "
    "delivery=a.get('delivery_allowed', p.get('should_run', True)); "
    "hard_gate=bool(u.get('action_required')); "
    "sys.exit(42 if hard_gate else (0 if delivery is not False else 43))"
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

_FRONTIER_READY_PY = (
    "import json,os,sys; "
    "p=json.load(sys.stdin); "
    "selected=(p.get('frontier') or {}).get('selected') or {}; "
    "agent=os.environ.get('LOOPX_AGENT_ID'); "
    "claimed=selected.get('claimed_by'); "
    "ok=bool(selected) and (not claimed or claimed==agent); "
    "sys.exit(0 if ok else 43)"
)

_HUMAN_VIEW_PACKET_PY = r"""
import json
import sys
from pathlib import Path

kind = sys.argv[1] if len(sys.argv) > 1 else "packet"
artifact = Path(sys.argv[2]) if len(sys.argv) > 2 else None
raw = sys.stdin.read()
if artifact is not None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(raw, encoding="utf-8")


def emit(key, value):
    if value is None or value == "":
        return
    text = str(value).replace("\n", " ").strip()
    if len(text) > 220:
        text = text[:217] + "..."
    print(f"{key}={text}")


emit(f"{kind}_artifact", artifact.name if artifact is not None else None)
try:
    payload = json.loads(raw)
except Exception:
    emit(f"{kind}_status", "not_json")
    emit(f"{kind}_summary", " ".join(raw.strip().splitlines()[:3]))
    raise SystemExit(0)

if kind == "quota":
    interaction = payload.get("interaction_contract") or {}
    user_channel = interaction.get("user_channel") or {}
    agent_channel = interaction.get("agent_channel") or {}
    emit("quota_decision", payload.get("decision") or payload.get("state") or payload.get("effective_action"))
    emit("should_run", payload.get("should_run"))
    emit("user_action_required", user_channel.get("action_required"))
    emit("delivery_allowed", agent_channel.get("delivery_allowed", payload.get("normal_delivery_allowed")))
    emit("reason", user_channel.get("reason") or payload.get("reason"))
    emit("next_action", agent_channel.get("primary_action") or payload.get("recommended_action"))
else:
    frontier = payload.get("frontier") or payload.get("agent_scope_frontier") or payload
    selected = frontier.get("selected") or frontier.get("selected_todo") or payload.get("selected") or {}
    emit("frontier_goal", frontier.get("goal_id") or payload.get("goal_id"))
    emit("frontier_agent", frontier.get("agent_id") or payload.get("agent_id"))
    if selected:
        emit("selected_todo", selected.get("todo_id") or selected.get("id"))
        emit("selected_title", selected.get("title") or selected.get("text"))
        emit("selected_status", selected.get("status"))
        emit("claimed_by", selected.get("claimed_by"))
        emit("allowed_action", selected.get("allowed_action") or selected.get("action_kind") or selected.get("mechanism_family"))
    else:
        emit("selected_todo", "none")
    for key in ("runnable", "blocked", "promotion_candidates", "retirement_candidates"):
        value = frontier.get(key)
        if isinstance(value, list):
            emit(f"{key}_count", len(value))
    evidence_graph = payload.get("evidence_graph") or frontier.get("evidence_graph") or {}
    if isinstance(evidence_graph, dict):
        for key in ("hypothesis_count", "evidence_event_count", "positive_event_count", "negative_evidence_count"):
            if key in evidence_graph:
                emit(key, evidence_graph.get(key))
"""

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

_VISIBLE_CODEX_STREAM_FILTER_PY = r"""
import re
import sys


def redact_local_paths(text):
    slash = chr(47)
    prefixes = [
        slash + "private" + slash + "var" + slash + "folders",
        slash + "var" + slash + "folders",
        slash + "private" + slash + "tmp",
        slash + "tmp",
    ]
    for prefix in prefixes:
        text = re.sub(re.escape(prefix) + r"[^ \n\r\t'\"`]+", "<local-path>", text)
    return text


skip_skill_block = False
waiting_for_first_codex = True
for raw in sys.stdin:
    line = raw.rstrip("\n")
    if waiting_for_first_codex:
        if line == "codex":
            waiting_for_first_codex = False
            print("[Codex]", flush=True)
        continue
    if "BEGIN_SKILL" in line:
        skip_skill_block = True
        print("[Codex stream note] worker-local skill block hidden; Codex output continues below.", flush=True)
        continue
    if "END_SKILL" in line:
        skip_skill_block = False
        continue
    if skip_skill_block:
        continue
    if " WARN codex_core_" in line:
        continue
    if line.startswith("warning: Skill descriptions were shortened"):
        continue
    print(redact_local_paths(line), flush=True)
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


def build_visible_frontier_command(
    frontier_command: str,
    *,
    frontier_label: str = "[LoopX frontier]",
) -> str:
    return (
        'cd "$LOOPX_PROJECT"; '
        f"printf '\\n%s\\n' {_q(frontier_label)}; "
        f"FRONTIER_PACKET=\"$(LOOPX_MACHINE_JSON=1; export LOOPX_MACHINE_JSON; {frontier_command} 2>&1)\"; "
        "FRONTIER_STATUS=$?; "
        'FRONTIER_ARTIFACT_NAME="frontier.public.json"; '
        'FRONTIER_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$FRONTIER_ARTIFACT_NAME"; '
        f"printf '%s\\n' \"$FRONTIER_PACKET\" | python3 -c {_q(_HUMAN_VIEW_PACKET_PY)} frontier \"$FRONTIER_ARTIFACT\" || true; "
        'printf "\\n[frontier window ready]\\nexit=%s\\nartifact=%s\\n" "$FRONTIER_STATUS" "$FRONTIER_ARTIFACT_NAME"; '
        "exec /bin/sh -i"
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
    visible_summary = (
        'printf "\\n[LoopX visible acceptance]\\n"; '
        'printf "role_profile=printed\\n"; '
        'printf "quota_guard=printed\\n"; '
        'printf "frontier_or_blocked_reason=printed\\n"; '
        'printf "bootstrap_or_stop=printed\\n"; '
        'printf "loopx_agent_handshake=role_profile_quota_frontier_bootstrap\\n"; '
        'printf "loopx_polling_prompt=visible_bootstrap_prompt\\n"; '
        'printf "loopx_cli_scope=scoped_loopx_wrapper\\n"; '
        'printf "human_stream_contract=role_todo_progress_codex_stream\\n"; '
        'printf "machine_json_policy=file_or_explicit_machine_channel_only\\n"; '
        'printf "machine_artifacts=quota_frontier_bootstrap_public_files\\n"; '
        'printf "takeover_controls=visible\\n"; '
        f"printf 'reasoning_effort=%s\\n' {_q(reasoning_effort)}"
    )
    keep_visible = (
        f"{visible_summary}; "
        'printf "\\n[user takeover]\\ninspect this pane; interrupt, close, or retry manually\\n"; '
        "exec /bin/sh -i"
    )
    poll_header = (
        'POLL_ATTEMPTS="${LOOPX_VISIBLE_POLL_ATTEMPTS:-6}"; '
        'POLL_SLEEP="${LOOPX_VISIBLE_POLL_INTERVAL_SECONDS:-5}"; '
        'POLL_INDEX=1; '
        "while :; do "
    )
    poll_retry = (
        'if [ "$POLL_INDEX" -lt "$POLL_ATTEMPTS" ]; then '
        'printf "\\n[LoopX waiting for lane turn]\\nattempt=%s/%s sleep=%s\\n" "$POLL_INDEX" "$POLL_ATTEMPTS" "$POLL_SLEEP"; '
        'POLL_INDEX=$((POLL_INDEX + 1)); '
        'sleep "$POLL_SLEEP"; '
        "continue; "
        "fi; "
    )
    return (
        "set -uo pipefail; "
        f"export LOOPX_ROLE_ID={_q(role_id)}; "
        f"export LOOPX_ROLE_PROFILE_REF={_q(role_profile_ref)}; "
        'cd "$LOOPX_PROJECT"; '
        f"{scoped_loopx_wrapper}"
        f"{role_profile_command}"
        f"{poll_header}"
        "printf '\\n[LoopX quota guard]\\nattempt=%s/%s\\n' \"$POLL_INDEX\" \"$POLL_ATTEMPTS\"; "
        f"QUOTA_PACKET=\"$(LOOPX_MACHINE_JSON=1; export LOOPX_MACHINE_JSON; {quota_command} 2>&1)\"; "
        "QUOTA_STATUS=$?; "
        'VISIBLE_ARTIFACT_PREFIX="${LOOPX_LANE_ID:-${LOOPX_ROLE_ID:-lane}}"; '
        'QUOTA_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$VISIBLE_ARTIFACT_PREFIX.quota.public.json"; '
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_HUMAN_VIEW_PACKET_PY)} quota \"$QUOTA_ARTIFACT\" || true; "
        "if [ \"$QUOTA_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'quota_command_failed exit=%s\\n' \"$QUOTA_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_QUOTA_READY_PY)}; "
        "QUOTA_GATE_STATUS=$?; "
        "if [ \"$QUOTA_GATE_STATUS\" -eq 43 ]; then "
        f"{poll_retry}"
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'quota_wait_timeout attempts=%s\\n' \"$POLL_ATTEMPTS\"; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_QUOTA_BLOCKER_SUMMARY_PY)} || true; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        "if [ \"$QUOTA_GATE_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        f"printf '%s\\n' \"$QUOTA_PACKET\" | python3 -c {_q(_QUOTA_BLOCKER_SUMMARY_PY)} || true; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_frontier\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '\\n{frontier_label}\\n'; "
        f"FRONTIER_PACKET=\"$(LOOPX_MACHINE_JSON=1; export LOOPX_MACHINE_JSON; {frontier_command} 2>&1)\"; "
        "FRONTIER_STATUS=$?; "
        'FRONTIER_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$VISIBLE_ARTIFACT_PREFIX.frontier.public.json"; '
        f"printf '%s\\n' \"$FRONTIER_PACKET\" | python3 -c {_q(_HUMAN_VIEW_PACKET_PY)} frontier \"$FRONTIER_ARTIFACT\" || true; "
        "if [ \"$FRONTIER_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'frontier_command_failed exit=%s\\n' \"$FRONTIER_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_bootstrap\\n'; "
        f"{keep_visible}; "
        "fi; "
        f"printf '%s\\n' \"$FRONTIER_PACKET\" | python3 -c {_q(_FRONTIER_READY_PY)}; "
        "FRONTIER_READY_STATUS=$?; "
        "if [ \"$FRONTIER_READY_STATUS\" -eq 43 ]; then "
        f"{poll_retry}"
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'frontier_wait_timeout attempts=%s\\n' \"$POLL_ATTEMPTS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_bootstrap\\n'; "
        f"{keep_visible}; "
        "fi; "
        "if [ \"$FRONTIER_READY_STATUS\" -ne 0 ]; then "
        "printf '\\n[LoopX blocked reason]\\n'; "
        "printf 'frontier_not_ready exit=%s\\n' \"$FRONTIER_READY_STATUS\"; "
        "printf '\\n[bootstrap-or-stop]\\nstopped_before_bootstrap\\n'; "
        f"{keep_visible}; "
        "fi; "
        "break; "
        "done; "
        "printf '\\n[bootstrap-or-stop]\\ncontinuing_to_visible_bootstrap\\n'; "
        f"BOOTSTRAP_PROMPT=\"$({bootstrap_command} 2>&1)\"; "
        "BOOTSTRAP_STATUS=$?; "
        'BOOTSTRAP_ARTIFACT="$LOOPX_VISIBLE_ARTIFACT_DIR/$VISIBLE_ARTIFACT_PREFIX.bootstrap-prompt.public.txt"; '
        'printf "%s\\n" "$BOOTSTRAP_PROMPT" > "$BOOTSTRAP_ARTIFACT"; '
        "printf '\\n[Codex bootstrap]\\n'; "
        "printf 'bootstrap_prompt_artifact=%s\\n' \"$VISIBLE_ARTIFACT_PREFIX.bootstrap-prompt.public.txt\"; "
        'if [ -n "${LOOPX_GOAL_ID:-}" ]; then printf "goal=%s\\n" "$LOOPX_GOAL_ID"; fi; '
        'if [ -n "${LOOPX_AGENT_ID:-}" ]; then printf "agent=%s\\n" "$LOOPX_AGENT_ID"; fi; '
        'if [ -n "${LOOPX_LANE_ID:-}" ]; then printf "lane=%s\\n" "$LOOPX_LANE_ID"; fi; '
        "printf 'codex_output=streaming_below\\n'; "
        "printf 'codex_stream_filter=public_safe\\n'; "
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
        '--cd "$LOOPX_PROJECT" --skip-git-repo-check --sandbox danger-full-access "$BOOTSTRAP_PROMPT" '
        f"2>&1 | python3 -u -c {_q(_VISIBLE_CODEX_STREAM_FILTER_PY)}; "
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
    retry_command = (
        "rerun the same visible launcher packet after refreshing quota, "
        "frontier, and bootstrap"
    )
    first_frontier = str(frontier_command or lane_list[0].get("frontier") or "")
    frontier_launcher = build_visible_frontier_command(first_frontier)
    start_script = [
        "set -uo pipefail",
        ": ${LOOPX_PROJECT:?set LOOPX_PROJECT to the repo root before running}",
        ": ${LOOPX_REGISTRY:?set LOOPX_REGISTRY to the LoopX registry path before running}",
        ": ${LOOPX_RUNTIME_ROOT:?set LOOPX_RUNTIME_ROOT to the LoopX runtime root before running}",
        f"export LOOPX_VISIBLE_SESSION={_q(session)}",
        'export LOOPX_VISIBLE_ARTIFACT_DIR="${LOOPX_VISIBLE_ARTIFACT_DIR:-$LOOPX_RUNTIME_ROOT/visible-launcher-artifacts/$LOOPX_VISIBLE_SESSION}"',
        'mkdir -p "$LOOPX_VISIBLE_ARTIFACT_DIR"',
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
        "human_stream_contract": {
            "schema_version": "multi_agent_visible_human_stream_contract_v0",
            "human_pane": [
                "role_profile_summary",
                "quota_summary",
                "frontier_or_blocked_summary",
                "bootstrap_artifact_ref",
                "codex_stream",
                "compact_exit_summary",
                "takeover_controls",
            ],
            "machine_artifacts": [
                "quota.public.json",
                "frontier.public.json",
                "bootstrap-prompt.public.txt",
                "role_local_public_artifacts",
            ],
            "machine_json_policy": "file_or_explicit_machine_channel_only",
            "visible_json_policy": "markdown_or_compact_summary_only",
            "codex_stream": "public_filtered_stdout_stderr_visible_below_bootstrap",
            "forbidden_visible_content": [
                "raw_quota_json",
                "raw_frontier_json",
                "raw_role_profile_json",
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
            "required_markers": [
                "role_profile=printed",
                "quota_guard=printed",
                "frontier_or_blocked_reason=printed",
                "bootstrap_or_stop=printed",
                "loopx_agent_handshake=role_profile_quota_frontier_bootstrap",
                "human_stream_contract=role_todo_progress_codex_stream",
                "machine_json_policy=file_or_explicit_machine_channel_only",
            ],
            "human_stream_contract": "multi_agent_visible_human_stream_contract_v0",
            "machine_json_file_bound": True,
            "codex_stream_visible": True,
            "codex_stream_public_filter": True,
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
    launch_result_schema: str = "multi_agent_visible_launch_result_v0",
    acceptance_schema: str = "multi_agent_visible_launch_acceptance_v0",
    lane_default: str = "agent-lane",
    frontier_or_blocker_markers: Iterable[str] = ("[LoopX frontier]", "[LoopX blocked reason]"),
    frontier_or_blocker_status_markers: Iterable[str] = ("frontier_or_blocked_reason=printed",),
) -> tuple[dict[str, object], str, str]:
    require_executable(cli_bin, field="cli_bin")
    require_executable(codex_bin, field="codex_bin")
    chosen = resolve_visible_launcher(requested=requested_launcher, tmux_bin=tmux_bin)
    project, workspace_mode = resolve_visible_workspace(workspace, create=create_workspace, cwd=cwd)
    worker_skills = _materialize_worker_skills(
        payload=payload,
        project=project,
        source_root=cwd,
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
            "LOOPX_VISIBLE_SESSION": session,
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
    first_frontier = str(lanes[0].get("frontier") or "")
    frontier_command = runtime_shell_command(
        build_visible_frontier_command(first_frontier),
        project=project,
        registry=registry,
        runtime_root=runtime_root,
        visible_session=session,
        errexit=False,
    )
    frontier_script = _write_tmux_script(
        script_dir=script_dir,
        name="frontier",
        command=frontier_command,
    )
    subprocess.run(
        [tmux_bin, "new-session", "-d", "-s", session, "-n", "frontier", "bash", str(frontier_script)],
        check=True,
        env=env,
    )
    started_lanes = []
    launcher_scripts = {"frontier": str(frontier_script)}
    for lane in lanes:
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
                launch_command,
                project=lane_project,
                registry=registry,
                runtime_root=runtime_root,
                visible_session=session,
                errexit=False,
            ),
        )
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
            failure_markers = [
                "stopped_before_frontier",
                "stopped_before_bootstrap",
                "stopped_before_codex",
                "quota_wait_timeout",
                "frontier_wait_timeout",
                "frontier_not_ready",
            ]
            blocked_before_bootstrap = any(marker in capture for marker in failure_markers)
            ok = (
                lane in surviving
                and ("[LoopX role profile]" in capture or "role_profile=printed" in capture)
                and ("[LoopX quota guard]" in capture or "quota_guard=printed" in capture)
                and any(marker in capture for marker in frontier_markers)
                and ("[bootstrap-or-stop]" in capture or "bootstrap_or_stop=printed" in capture)
                and "loopx_agent_handshake=role_profile_quota_frontier_bootstrap" in capture
                and "human_stream_contract=role_todo_progress_codex_stream" in capture
                and "machine_json_policy=file_or_explicit_machine_channel_only" in capture
                and not blocked_before_bootstrap
            )
            pane_checks.append(
                {
                    "lane_id": lane,
                    "accepted": ok,
                    "blocked_before_bootstrap": blocked_before_bootstrap,
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
