from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .bootstrap import default_goal_id


DEFAULT_HANDOFF_OBJECTIVE = "<OBJECTIVE_FROM_GOAL_DOC>"
DEFAULT_HANDOFF_DOMAIN = "<DOMAIN>"
DEFAULT_HANDOFF_ADAPTER_KIND = "read_only_project_map_v0"
DEFAULT_HANDOFF_ADAPTER_STATUS = "connected-read-only"
DEFAULT_HANDOFF_NEXT_PROBE = "(omit --next-probe until a read-only pre-tick command exists)"
SHARED_GLOBAL_REGISTRY = '"$HOME/.codex/loopx/registry.global.json"'
NO_CLONE_INSTALL_URL = "https://raw.githubusercontent.com/huangruiteng/loopx/main/scripts/install-from-github.sh"


def shell_arg(value: str) -> str:
    return shlex.quote(value)


def render_cli_preflight(*, cli_bin: str = "loopx") -> str:
    cli_bin_arg = shell_arg(cli_bin)
    return f"""export PATH="$HOME/.local/bin:$PATH"
install_script="$HOME/loopx/scripts/install-local.sh"
if ! command -v {cli_bin_arg} >/dev/null 2>&1; then
  if [ -x "$install_script" ]; then
    "$install_script"
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "loopx is not on PATH; clone the LoopX repo and run scripts/install-local.sh" >&2
    exit 1
  fi
fi
{cli_bin_arg} doctor >/dev/null"""


def render_codex_cli_no_clone_preflight(*, cli_bin: str = "loopx") -> str:
    cli_bin_arg = shell_arg(cli_bin)
    return f"""export PATH="$HOME/.local/bin:$PATH"
if ! command -v {cli_bin_arg} >/dev/null 2>&1; then
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL {NO_CLONE_INSTALL_URL} | bash
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "loopx is not on PATH and curl is unavailable; install curl or use a contributor clone with scripts/install-local.sh" >&2
    exit 1
  fi
fi
{cli_bin_arg} doctor >/dev/null"""


def render_quota_guard_command(goal_id: str, *, cli_bin: str = "loopx", agent_id: str | None = None) -> str:
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    return (
        f"{shell_arg(cli_bin)} --format json "
        f"--registry {SHARED_GLOBAL_REGISTRY} "
        f"quota should-run --goal-id {shell_arg(goal_id)}{agent_arg}"
    )


def render_quota_spend_command(
    goal_id: str,
    *,
    source: str = "adapter",
    cli_bin: str = "loopx",
    agent_id: str | None = None,
) -> str:
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    return (
        f"{shell_arg(cli_bin)} "
        f"--registry {SHARED_GLOBAL_REGISTRY} "
        "quota spend-slot "
        f"--goal-id {shell_arg(goal_id)} "
        f"--slots 1 --source {shell_arg(source)} --execute{agent_arg}"
    )


def render_heartbeat_prompt_command(
    goal_id: str,
    *,
    cli_bin: str = "loopx",
    agent_id: str | None = None,
    agent_scope: str = "Codex CLI /goal visible TUI loop",
    body: str = "thin",
) -> str:
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    scope_arg = f" --agent-scope {shell_arg(agent_scope)}" if agent_id else ""
    return (
        f"{shell_arg(cli_bin)} heartbeat-prompt --{shell_arg(body)} "
        f"--goal-id {shell_arg(goal_id)}{agent_arg}{scope_arg}"
    )


def render_heartbeat_prompt_json_command(
    goal_id: str,
    *,
    cli_bin: str = "loopx",
    agent_id: str | None = None,
    agent_scope: str = "Codex CLI /goal visible TUI loop",
    body: str = "thin",
) -> str:
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    scope_arg = f" --agent-scope {shell_arg(agent_scope)}" if agent_id else ""
    return (
        f"{shell_arg(cli_bin)} --format json heartbeat-prompt --{shell_arg(body)} "
        f"--goal-id {shell_arg(goal_id)}{agent_arg}{scope_arg}"
    )


def render_connect_command(
    *,
    project: str,
    goal_doc: str,
    goal_id: str,
    objective: str,
    domain: str,
    adapter_kind: str,
    adapter_status: str,
    next_probe: str | None,
    spawn_allowed: bool,
    allowed_domains: list[str],
    write_scope: list[str],
    cli_bin: str = "loopx",
) -> str:
    lines = [
        f"cd {shell_arg(project)}",
        f"{shell_arg(cli_bin)} connect \\",
        f"  --goal-id {shell_arg(goal_id)} \\",
        f"  --objective {shell_arg(objective)} \\",
        f"  --domain {shell_arg(domain)} \\",
        f"  --goal-doc {shell_arg(goal_doc)} \\",
        f"  --adapter-kind {shell_arg(adapter_kind)} \\",
        f"  --adapter-status {shell_arg(adapter_status)}",
    ]
    if next_probe:
        lines[-1] += " \\"
        lines.append(f"  --next-probe {shell_arg(next_probe)}")
    if spawn_allowed:
        lines[-1] += " \\"
        lines.append("  --spawn-allowed")
        for allowed_domain in allowed_domains:
            lines[-1] += " \\"
            lines.append(f"  --allowed-domain {shell_arg(allowed_domain)}")
        for scope in write_scope:
            lines[-1] += " \\"
            lines.append(f"  --write-scope {shell_arg(scope)}")
    return "\n".join(lines)


def build_new_project_prompt(
    *,
    project: Path,
    goal_doc: Path,
    goal_id: str | None,
    objective: str | None,
    domain: str | None,
    adapter_kind: str,
    adapter_status: str,
    next_probe: str | None,
    spawn_allowed: bool,
    allowed_domains: list[str] | None,
    write_scope: list[str] | None,
) -> dict[str, Any]:
    project_text = str(project.expanduser())
    goal_doc_text = str(goal_doc.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    resolved_objective = objective or DEFAULT_HANDOFF_OBJECTIVE
    resolved_domain = domain or DEFAULT_HANDOFF_DOMAIN
    resolved_next_probe = next_probe or DEFAULT_HANDOFF_NEXT_PROBE
    allowed_domains = allowed_domains or []
    write_scope = write_scope or []
    connect_command = render_connect_command(
        project=project_text,
        goal_doc=goal_doc_text,
        goal_id=resolved_goal_id,
        objective=resolved_objective,
        domain=resolved_domain,
        adapter_kind=adapter_kind,
        adapter_status=adapter_status,
        next_probe=next_probe,
        spawn_allowed=spawn_allowed,
        allowed_domains=allowed_domains,
        write_scope=write_scope,
        cli_bin="loopx",
    )
    quota_guard_command = render_quota_guard_command(resolved_goal_id)
    quota_spend_command = render_quota_spend_command(resolved_goal_id)
    prompt = render_prompt_text(
        project=project_text,
        goal_doc=goal_doc_text,
        goal_id=resolved_goal_id,
        objective=resolved_objective,
        domain=resolved_domain,
        adapter_kind=adapter_kind,
        adapter_status=adapter_status,
        next_probe=resolved_next_probe,
        cli_preflight=render_cli_preflight(),
        connect_command=connect_command,
        quota_guard_command=quota_guard_command,
        quota_spend_command=quota_spend_command,
        cli_bin="loopx",
        spawn_allowed=spawn_allowed,
        allowed_domains=allowed_domains,
        write_scope=write_scope,
    )
    return {
        "ok": True,
        "project": project_text,
        "goal_doc": goal_doc_text,
        "goal_id": resolved_goal_id,
        "objective": resolved_objective,
        "domain": resolved_domain,
        "adapter_kind": adapter_kind,
        "adapter_status": adapter_status,
        "next_probe": resolved_next_probe,
        "spawn_allowed": spawn_allowed,
        "allowed_domains": allowed_domains,
        "write_scope": write_scope,
        "connect_command": connect_command,
        "quota_guard_command": quota_guard_command,
        "quota_spend_command": quota_spend_command,
        "cli_preflight": render_cli_preflight(),
        "prompt": prompt,
    }


def render_codex_cli_bootstrap_connect_command(
    *,
    project: str,
    goal_id: str,
    cli_bin: str,
) -> str:
    return "\n".join(
        [
            f"cd {shell_arg(project)}",
            f"{shell_arg(cli_bin)} bootstrap \\",
            "  --project . \\",
            f"  --goal-id {shell_arg(goal_id)} \\",
            f"  --adapter-kind {shell_arg(DEFAULT_HANDOFF_ADAPTER_KIND)} \\",
            f"  --adapter-status {shell_arg(DEFAULT_HANDOFF_ADAPTER_STATUS)}",
        ]
    )


def build_codex_cli_bootstrap_message(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
) -> dict[str, Any]:
    resolved_project = str(project.expanduser())
    resolved_goal_id = goal_id or default_goal_id(project)
    connect_command = render_codex_cli_bootstrap_connect_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
    )
    quota_guard_command = render_quota_guard_command(
        resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
    )
    quota_spend_command = render_quota_spend_command(
        resolved_goal_id,
        source="heartbeat",
        cli_bin=cli_bin,
        agent_id=agent_id,
    )
    heartbeat_prompt_command = render_heartbeat_prompt_command(
        resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
    )
    heartbeat_prompt_json_command = render_heartbeat_prompt_json_command(
        resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
    )
    install_repair_command = render_codex_cli_no_clone_preflight(cli_bin=cli_bin)
    refresh_command = f"{shell_arg(cli_bin)} refresh-state --goal-id {shell_arg(resolved_goal_id)}"
    first_run_validation_checklist = [
        f"{cli_bin} doctor passed after no-clone install repair or existing install",
        "repo bootstrap/connect completed conservatively or a concrete install/connect blocker was shown",
        f"thin heartbeat task_body generated from {cli_bin} heartbeat-prompt --thin, not hand-written",
        "current loop surface configured from the thin task_body: Codex CLI /goal or Codex App automation",
        "quota/status guard checked with the registered agent id when available after bootstrap/connect",
        "current goal, concrete user gate or none, top todos, and next safe action shown in the TUI",
        "no raw Codex transcripts, session files, credentials, private paths, stdout, or stderr persisted",
    ]
    message = render_codex_cli_bootstrap_message_text(
        project=resolved_project,
        goal_id=resolved_goal_id,
        agent_id=agent_id,
        cli_preflight=install_repair_command,
        connect_command=connect_command,
        heartbeat_prompt_json_command=heartbeat_prompt_json_command,
        heartbeat_prompt_command=heartbeat_prompt_command,
        quota_guard_command=quota_guard_command,
        refresh_command=refresh_command,
        quota_spend_command=quota_spend_command,
        first_run_validation_checklist=first_run_validation_checklist,
    )
    return {
        "ok": True,
        "schema_version": "codex_cli_bootstrap_message_v1",
        "invocation_mode": "codex_cli_setup_then_goal_mode",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "install_repair_command": install_repair_command,
        "connect_command": connect_command,
        "heartbeat_prompt_command": heartbeat_prompt_command,
        "heartbeat_prompt_json_command": heartbeat_prompt_json_command,
        "codex_cli_goal_prefix": "/goal ",
        "codex_app_loop_surface": "heartbeat automation task_body",
        "quota_guard_command": quota_guard_command,
        "refresh_command": refresh_command,
        "quota_spend_command": quota_spend_command,
        "first_run_validation_checklist": first_run_validation_checklist,
        "message": message,
    }


def build_codex_cli_tui_bootstrap_smoke_bundle(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
) -> dict[str, Any]:
    bootstrap = build_codex_cli_bootstrap_message(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
    )
    resolved_project = str(bootstrap["project"])
    resolved_goal_id = str(bootstrap["goal_id"])
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    message_only_command = (
        f"{shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {shell_arg(resolved_project)} "
        f"--goal-id {shell_arg(resolved_goal_id)}{agent_arg} --message-only"
    )
    review_packet_command = (
        f"{shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {shell_arg(resolved_project)} "
        f"--goal-id {shell_arg(resolved_goal_id)}{agent_arg}"
    )
    boundary = {
        "runs_codex": False,
        "reads_raw_transcripts": False,
        "reads_session_files": False,
        "reads_credentials": False,
        "mutates_codex_session": False,
        "spends_loopx_quota": False,
        "requires_loopx_repo_clone": False,
    }
    validation_checklist = [
        "archive installer works from a temporary GitHub-style tarball or existing install",
        "message-only command prints only the setup paste block, not the Markdown review packet",
        "paste block includes no-clone install repair, project bootstrap/connect, thin heartbeat generation, loop activation, and quota guard",
        "quota spend remains a later post-delivery command inside the paste block, not a setup or smoke side effect",
        "no raw Codex transcripts, session files, credentials, stdout, stderr, or private paths are read",
    ]
    return {
        "ok": True,
        "schema_version": "codex_cli_tui_bootstrap_smoke_bundle_v0",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "install_repair_command": bootstrap["install_repair_command"],
        "review_packet_command": review_packet_command,
        "message_only_command": message_only_command,
        "heartbeat_prompt_command": bootstrap["heartbeat_prompt_command"],
        "heartbeat_prompt_json_command": bootstrap["heartbeat_prompt_json_command"],
        "quota_guard_command": bootstrap["quota_guard_command"],
        "refresh_command": bootstrap["refresh_command"],
        "quota_spend_command": bootstrap["quota_spend_command"],
        "validation_checklist": validation_checklist,
        "boundary": boundary,
    }


def build_codex_cli_exec_handoff(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    codex_bin: str,
) -> dict[str, Any]:
    bootstrap = build_codex_cli_bootstrap_message(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin=cli_bin,
    )
    resolved_project = str(project.expanduser())
    resolved_goal_id = str(bootstrap["goal_id"])
    agent_arg = f" --agent-id {shell_arg(agent_id)}" if agent_id else ""
    message_only_command = (
        f"{shell_arg(cli_bin)} codex-cli-bootstrap-message "
        f"--project {shell_arg(resolved_project)} "
        f"--goal-id {shell_arg(resolved_goal_id)}{agent_arg} --message-only"
    )
    return {
        "ok": True,
        "schema_version": "codex_cli_exec_handoff_v0",
        "mode": "headless_fallback_disabled_for_goal_mode_bootstrap",
        "primary_experience": "codex_cli_tui_goal_bootstrap",
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "cli_bin": cli_bin,
        "codex_bin": codex_bin,
        "disabled_reason": (
            "Default Codex CLI LoopX bootstrap must stay visible in the TUI; "
            "headless codex exec handoff is disabled to avoid accidental hidden execution."
        ),
        "session_probe_command": f"{shell_arg(cli_bin)} codex-cli-session-probe --codex-bin {shell_arg(codex_bin)}",
        "quota_guard_command": bootstrap["quota_guard_command"],
        "quota_spend_command": bootstrap["quota_spend_command"],
        "heartbeat_prompt_json_command": bootstrap["heartbeat_prompt_json_command"],
        "message_only_command": message_only_command,
        "handoff_command": "",
        "boundary": {
            "runs_codex": False,
            "reads_raw_transcripts": False,
            "reads_credentials": False,
            "reads_session_files": False,
            "mutates_codex_session": False,
            "spends_loopx_quota": False,
            "headless_execution_disabled": True,
            "provides_executable_headless_command": False,
        },
    }


def render_codex_cli_bootstrap_message_text(
    *,
    project: str,
    goal_id: str,
    agent_id: str | None,
    cli_preflight: str,
    connect_command: str,
    heartbeat_prompt_json_command: str,
    heartbeat_prompt_command: str,
    quota_guard_command: str,
    refresh_command: str,
    quota_spend_command: str,
    first_run_validation_checklist: list[str],
) -> str:
    agent_line = f"Use registered LoopX agent id `{agent_id}` when claiming or spending." if agent_id else (
        "If this project has registered agents, inspect the registry and use the correct registered agent id before claiming todos."
    )
    checklist = "\n".join(f"- {item}" for item in first_run_validation_checklist)
    return f"""Install and connect LoopX for this repo from this same Codex CLI TUI session.

Goal: one-message setup, then loop activation. Keep this TUI as the visible
place where I can watch, steer, review, and take over. Do not use hidden
headless `codex exec` for this bootstrap path.

This first message is the setup/bootstrap instruction, not the reusable
heartbeat prompt. Complete the setup in order: install or repair LoopX
if needed; bootstrap/connect this project; then configure the current loop
surface from the generated thin heartbeat prompt. For Codex CLI, set the
current TUI goal to `/goal ` plus the thin `task_body`. For Codex App, set or
refresh the heartbeat automation to that same thin `task_body`. If the current
surface cannot be mutated from this session, show the exact pasteable `/goal`
or automation body and report that as a concrete user gate; do not claim setup
success.

Project: `{project}`
Goal id: `{goal_id}`
{agent_line}

Success criteria for this first setup turn:
- I should not need to inspect registry paths, runtime roots, JSON payloads, or
  hidden session files.
- If LoopX is already installed and this repo is already connected,
  reuse the existing install/state and do not reinstall or duplicate bootstrap.
- Configure the loop target after bootstrap: Codex CLI `/goal <thin task_body>`
  or Codex App heartbeat automation `<thin task_body>`.
- Show me the current goal id, concrete user gate if any, top user todo if any,
  top agent todo, and next safe action.
- Do not do longer delivery work in the setup turn unless I explicitly ask; the
  configured thin loop owns later quota/spend delivery turns.

1. Ensure the LoopX CLI works. Prefer the no-clone GitHub archive
installer; do not ask me to clone the LoopX repo just to try the first
run:

```bash
{cli_preflight}
```

2. If this repo is not connected to LoopX yet, connect it conservatively:

```bash
{connect_command}
```

If the connect output includes onboarding candidate todos, summarize them in
this TUI and ask me which ones to accept before starting autonomous delivery.

3. Generate the thin loop prompt after bootstrap/connect, not before. Do not
hand-write or copy an old heartbeat body:

```bash
{heartbeat_prompt_json_command}
```

Read `task_body` from the JSON result. Then configure the current surface:
- Codex CLI TUI: set the current goal to `/goal ` followed by that `task_body`.
- Codex App: set or update the heartbeat automation body to that `task_body`.

For review, the Markdown form is:

```bash
{heartbeat_prompt_command}
```

4. After install/connect and loop activation, run the quota/status guard for
the first control-plane snapshot:

```bash
{quota_guard_command}
```

Follow `interaction_contract` exactly:
- If `user_channel.action_required=true` or open user todos exist, ask only the
  concrete user gate or todo payload.
- If `workspace_guard` blocks delivery, move to an independent worktree and
  rerun the same guard before editing.
- If delivery is allowed, choose one runnable agent todo after a short steering
  audit, preferably a current-agent claimed advancement todo.

5. Report the current goal/gate/todo/next-action snapshot in this TUI. Stop
after setup unless I explicitly asked for delivery in this same turn. Do not
store raw Codex transcripts, credentials, private paths, raw logs, or
production artifacts in public docs or LoopX state.

6. Before writeback, use this transcript-free validation checklist:

{checklist}

7. After setup writeback, refresh state if needed. Do not spend quota for a
setup-only turn. The configured thin loop spends only after a later validated
delivery writeback. If I explicitly asked you to do delivery in this same turn
and you completed a validated delivery segment, spend exactly once:

```bash
{refresh_command}
{quota_spend_command}
```

End with changed files, validation result, current gate/todo state, and next
safe action. Later automation may add visible steering turns to this session
only after public-safe visible proof, runtime idle evidence, a fresh guard, and
explicit execution bounds. Keep optional automation checks such as
local-driver-plan or visible-session-proof as follow-up diagnostics, not
first-run prerequisites.
"""

def render_prompt_text(
    *,
    project: str,
    goal_doc: str,
    goal_id: str,
    objective: str,
    domain: str,
    adapter_kind: str,
    adapter_status: str,
    next_probe: str,
    cli_preflight: str,
    connect_command: str,
    quota_guard_command: str,
    quota_spend_command: str,
    cli_bin: str,
    spawn_allowed: bool,
    allowed_domains: list[str],
    write_scope: list[str],
) -> str:
    spawn_note = "本项目初始不需要主控拆 sub-agent；除非目标文档另有授权，先保持单 controller read-only 接入。"
    if spawn_allowed:
        spawn_note = (
            "本项目允许主控拆 sub-agent；子 agent 只能进入已声明 allowed-domain，"
            "写入范围只能落在已声明 write-scope。"
        )
    allowed_domains_text = ", ".join(allowed_domains) if allowed_domains else "(none)"
    write_scope_text = ", ".join(write_scope) if write_scope else "(none)"
    return f"""我有一个新项目要接入 LoopX。

项目文件夹：
{project}

项目目标文档：
{goal_doc}

请你按下面步骤推进，不要停在方案讨论；如果信息缺失，先从目标文档和项目结构中做保守抽取，并在最后说明假设。
重要：`{cli_bin} connect` 默认会做一次快速 onboarding scan，基于 git status、最近 commit、顶层项目信号生成候选 agent todo。
接入后不要直接开始 delivery；先把候选 todo 展示给我，并问我两件事：
1. 接受、编辑或拒绝哪些候选 agent todo；
2. 是否允许你从接受的 todo 开始自主推进。

0. 先确认当前 shell 能调用 LoopX CLI；如果提示 `loopx` 不在 PATH，运行本机安装脚本再继续：

```bash
{cli_preflight}
```

1. 再只读检查项目文件夹和目标文档，抽取：
   - stable goal id；
   - 一句话 objective；
   - domain；
   - authority sources；
   - work clusters；
   - validation surfaces；
   - private/public boundary；
   - 第一个 recommended_action。
2. 用这些初始参数作为默认值；如果目标文档给出更好的命名或边界，可以修正：
   - stable goal id: `{goal_id}`
   - objective: `{objective}`
   - domain: `{domain}`
   - adapter_kind: `{adapter_kind}`
   - adapter_status: `{adapter_status}`
   - goal_doc: `{goal_doc}`
   - next_probe: `{next_probe}`
   - spawn_allowed: `{spawn_allowed}`
   - allowed_domains: `{allowed_domains_text}`
   - write_scope: `{write_scope_text}`
3. 运行 LoopX 接入命令：

```bash
{connect_command}
```

4. 确认 `.loopx/registry.json` 和 `.codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md` 已创建或更新。
   阅读输出里的 `Onboarding Scan`、`Proposed Onboarding Candidates`、`Accept Candidate Commands`
   和 `Autonomy Choice`。不要让用户手动执行这些命令；你应当用中文简要解释候选 todo，
   然后询问用户：
   - 接受哪些编号，是否需要改写；
   - 是否 `autonomous=yes`，允许你在 quota guard 通过后开始执行第一个接受的 agent todo。
   如果用户接受候选 todo，用输出里的 `{cli_bin} todo add ...` 命令写入 agent todo；
   如果用户允许自主推进，先运行 quota guard，再执行第一个已接受 agent todo。
   如果用户不允许自主推进，只写入接受的 todo 并运行 `{cli_bin} refresh-state --goal-id {goal_id}`，
   然后停下来汇报。
   如果目标状态包含私有证据，把 `.loopx/` 和 `.codex/goals/` 加入该项目 `.gitignore`。
   `{cli_bin} connect` 默认会同步到共享全局 registry；不要手动编辑其他项目的 registry。
   接入后检查 registry 里的 `execution_profile`：它是本项目后续 heartbeat / adapter 的执行画像。
   默认 cadence 是 `bounded_progress_segment`，连续小步达到阈值后，下一轮必须扩展到
   `minimum_scale` 并包含 `must_include` 里的真实 artifact、targeted validation、state writeback；
   如果做不到，先报 blocker，不 append quota spend。
5. 在任何 heartbeat、scheduled tick、long-running adapter 或自主 delivery 前，先问 compute guard：

```bash
{quota_guard_command}
```

   如果返回 `state=operator_gate`，把它当成人/控制器交互，而不是安静 skip：优先读取 payload 里的
   `gate_prompt`、`operator_question`、`recommended_action`、`next_handoff_condition`、`missing_gates`、
   `user_todo_summary` 和 `agent_todo_summary`，用中文主动告诉用户当前卡在哪个 gate、期望怎样回复；
   同时把 `agent_todo_summary` 当作项目 agent 自己的安全后续清单。不要执行任何
   `agent_command`、adapter work、write-control、生产动作或该 gated action。
   如果同一个未决 gate 最近已经问过，且返回 `safe_bypass_allowed=true`，该 gate 只阻塞被 gate 覆盖的
   delivery path；可以从 active state / Priority Stack 里选择一个不依赖该 gate 的 bounded 只读分析、
   steering、文档或 P0/P1 工作。若实际完成 safe-bypass 工作，仍需验证、写回进展，并 append 一次
   quota spend。
   如果 payload 返回 `notify_user_on_open_todo=true`，把开放 user todo 当作 blocker-push，而不是
   静默 skip：用中文最多列 3 个开放项和期望回复格式，并且本轮不做 delivery、不 append quota spend，
   除非同一个 blocker 最近已经问过。
   无论 `should_run` 是 true 还是 false，都先看 `execution_obligation`、
   `effective_action`、`recovery_delivery_allowed`、`safe_bypass_kind` 和
   `heartbeat_recommendation`。`heartbeat_recommendation.notify` 只是用户通知策略，
   不是执行 gate；如果 `execution_obligation.must_attempt_work=true`，即使
   `notify=DONT_NOTIFY` 也要尝试一个 bounded segment，只有
   `must_attempt_work=false` 才能 quiet no-op。
   如果是 `outcome_floor_recovery`，这是 Codex 可执行 recovery turn：只允许做一次所需
   ranker/cross-domain evidence recovery，或写回阻止该 evidence 的具体 blocker；
   不做 surface-only / synthetic-only 循环，验证并写回后才能 append 一次 quota spend。
   如果不是 operator gate / blocker-push / outcome-floor recovery / 明确 safe-bypass，本轮不要做实现或 adapter 工作，
   只记录 public-safe reason；不要执行任何 `agent_command`，即使 status 或 review packet 里提到过命令。
   只有当返回 `should_run=true` 且 payload 里包含 `agent_command` 时，才执行该命令。
   如果 `should_run=true` 但没有 `agent_command`，按
   `execution_obligation` / `recommended_action` / `goal_boundary` 选择下一个
   安全 bounded 动作；只读目标保持只读，delivery 目标按已授权 write scope 执行。
   如果命令非零，fail closed，先修 `{cli_bin} doctor` / `{cli_bin} status`。
   这个 guard 不等于写权限、不绕过 operator gate、也不替代 human reward。
   任何时候，如果你通过 read-only 分析、review doc、gate checklist 或 P0/P1 steering 发现新的
   用户/owner 待办，不要只写在 `Next Action`、外部 review 文档或聊天里。立刻把它写进 active state
   的 user todo 权威区：

```bash
{cli_bin} todo add --goal-id {goal_id} --role user --text "<public-safe user/owner action>"
```

   agent 自己的后续动作写成 `--role agent`。写入后如果 dashboard 需要看到最新状态，运行
   `{cli_bin} refresh-state --goal-id {goal_id}`。
   完整契约见 LoopX 仓库里的 `docs/project-agent-todo-contract.md`。
6. 如果需要把当前 packet 或已批准命令交给项目 agent，优先生成最小 handoff，不要从旧聊天、
   旧 review packet 或 `run_history.latest_runs` 拼当前状态。当前权威状态来自
   `attention_queue.items` / `project_asset`；如果缺少 `project_asset` 或标记为
   `legacy/raw fallback`，不要把 raw queue 字段当作 owner/gate/stop authority：

```bash
{cli_bin} review-packet --goal-id {goal_id} --handoff-only
```

   只把输出的 handoff 交给目标项目 agent；完整 review packet 留给 operator view / evidence drill-down。
7. 如果要给这个项目设置 recurring Codex App heartbeat，不要手抄 guard 和 spend 协议；先生成 task body，再把输出复制进 automation：

```bash
{cli_bin} heartbeat-prompt --goal-id {goal_id} --active-state .codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md
```

8. 生成一个 read-only project map 或 first pre-tick run。不要启动线上任务、不同步外部系统、不要写生产状态，除非目标文档明确授权。通用接入优先跑：

```bash
{cli_bin} read-only-map --goal-id {goal_id}
```

9. 如果本轮只更新了 active state、ledger 或外部规划文档，没有产生新的 adapter run，或者 dashboard 仍显示旧 run，追加一个 state-only refresh run；若本轮实际消耗了 automatic delivery compute，则把这个 refresh 放到 quota spend 之后，避免 state refresh 先关闭 active delivery lane：

```bash
{cli_bin} refresh-state --goal-id {goal_id}
```

这个命令也会自动同步全局 registry。

10. 跑验证：
   - `{cli_bin} registry`
   - `{cli_bin} status`（在没有项目局部 registry 的目录里也应自动读共享全局 registry）
   - `{cli_bin} check --scan-path <PUBLIC_SAFE_FILE_OR_DIR>`
11. 如果本轮实际花了 automatic delivery compute（例如 read-only map、adapter tick、实现推进或验证推进），在 validation / writeback 完成后、任何可能关闭 active delivery lane 的 state-only `refresh-state` 之前，只 append 一次 quota spend；需要 dashboard 或 controller 看到新状态时，再在 spend 后 refresh：

```bash
{quota_spend_command}
```

   不要为 quiet `should_run=false` skip、preflight 失败、或纯 dry-run preview 记账；如果
   `should_run=false` 但实际完成了 `safe_bypass_allowed=true` 的 bounded safe-bypass 工作，要记一次账。
   不要重复执行。
12. 最后用中文汇报：
   - changed files；
   - validation output；
   - 当前 goal 在 dashboard / attention queue 里会怎么显示；
   - next safe action；
   - 如果还不能接入 decision-advisor，明确缺哪些 gates。

并行/权限边界：
{spawn_note}
"""


def render_new_project_prompt_markdown(payload: dict[str, Any]) -> str:
    return f"""# New Project Codex Handoff Prompt

Copy the block below into the Codex session that can access the target project.

````text
{payload.get("prompt", "")}
````

## Generator Inputs

- project: `{payload.get("project")}`
- goal_doc: `{payload.get("goal_doc")}`
- goal_id: `{payload.get("goal_id")}`
- domain: `{payload.get("domain")}`
- adapter: `{payload.get("adapter_kind")}:{payload.get("adapter_status")}`
"""


def render_codex_cli_bootstrap_message_markdown(payload: dict[str, Any]) -> str:
    checklist = "\n".join(
        f"- {item}" for item in payload.get("first_run_validation_checklist", [])
    )
    goal_mode_note = ""
    if payload.get("invocation_mode") == "codex_cli_setup_then_goal_mode":
        goal_mode_note = (
            "\nThe generated block is a setup message, not the reusable heartbeat body. "
            "After install/bootstrap, it tells the agent to set Codex CLI goal mode "
            "to `/goal <thin task_body>` or Codex App automation to `<thin task_body>`.\n"
        )
    return f"""# Codex CLI LoopX Bootstrap Message

Copy the block below into Codex CLI TUI from the project repo.
{goal_mode_note}

````text
{payload.get("message", "")}
````

## Fresh Repo Install Repair

The generated message uses the no-clone GitHub archive installer before asking
for a contributor clone:

```bash
{payload.get("install_repair_command", "")}
```

## Post-Bootstrap Thin Loop Prompt

Generate the thin task body after the project is connected:

```bash
{payload.get("heartbeat_prompt_json_command", "")}
```

- Codex CLI TUI loop: set `/goal <task_body>`.
- Codex App loop: set heartbeat automation body to `<task_body>`.

## Transcript-Free Validation Checklist

{checklist}

## Generator Inputs

- project: `{payload.get("project")}`
- goal_id: `{payload.get("goal_id")}`
- agent_id: `{payload.get("agent_id") or "(not provided)"}`
- cli_bin: `{payload.get("cli_bin")}`
- heartbeat_prompt_drift_check: `{payload.get("heartbeat_prompt_command")}`
"""


def render_codex_cli_tui_bootstrap_smoke_bundle_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") or {}
    checklist = "\n".join(f"- {item}" for item in payload.get("validation_checklist", []))
    return f"""# Codex CLI TUI Bootstrap Smoke Bundle

This packet is for validating the first-run Codex CLI path without launching or
mutating a real Codex session.

## Commands

```bash
{payload.get("message_only_command", "")}
```

- review_packet: `{payload.get("review_packet_command")}`
- heartbeat_prompt: `{payload.get("heartbeat_prompt_command")}`
- heartbeat_prompt_json: `{payload.get("heartbeat_prompt_json_command")}`
- quota_guard: `{payload.get("quota_guard_command")}`
- refresh_state: `{payload.get("refresh_command")}`
- quota_spend_after_validation: `{payload.get("quota_spend_command")}`

## Fresh Repo Install Repair

```bash
{payload.get("install_repair_command", "")}
```

## Transcript-Free Boundary

- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- reads_credentials: `{boundary.get("reads_credentials")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- requires_loopx_repo_clone: `{boundary.get("requires_loopx_repo_clone")}`

## Validation Checklist

{checklist}
"""


def render_codex_cli_exec_handoff_markdown(payload: dict[str, Any]) -> str:
    boundary = payload.get("boundary") or {}
    return f"""# Codex CLI Exec Handoff Disabled

The default Codex CLI LoopX bootstrap is visible setup, then thin
`/goal <task_body>` activation. Headless `codex exec` handoff is disabled here
to avoid accidental hidden execution. Use the message-only command below inside
the visible Codex CLI TUI.

````bash
{payload.get("message_only_command", "")}
````

## Guard Commands

- session_probe: `{payload.get("session_probe_command")}`
- quota_guard: `{payload.get("quota_guard_command")}`
- quota_spend: `{payload.get("quota_spend_command")}`
- disabled_reason: {payload.get("disabled_reason")}

## Boundary

- runs_codex: `{boundary.get("runs_codex")}`
- reads_raw_transcripts: `{boundary.get("reads_raw_transcripts")}`
- reads_credentials: `{boundary.get("reads_credentials")}`
- reads_session_files: `{boundary.get("reads_session_files")}`
- mutates_codex_session: `{boundary.get("mutates_codex_session")}`
- spends_loopx_quota: `{boundary.get("spends_loopx_quota")}`
- headless_execution_disabled: `{boundary.get("headless_execution_disabled")}`
- provides_executable_headless_command: `{boundary.get("provides_executable_headless_command")}`
"""
