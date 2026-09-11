"""Stable host entrypoints; changing execution policy stays in task_body."""
from __future__ import annotations

import shlex
from pathlib import Path
from types import SimpleNamespace


BOOTSTRAP_INSTRUCTION = (
    "读取完整结果；仅 ok=true 时按本次 task_body 推进，不复用旧指令。"
    "一次操作不代表结束；通知与执行分开，等待按当前调度契约，不反复空查。"
    "入口异常先做权限内恢复；契约仍不可用时不执行任务或记账，并报告阻塞。"
)


def render_bootstrap(command: list[str], *, title: str, entry: str) -> str:
    return f"{title}\n{entry}\n```sh\n{shlex.join(command)}\n```\n{BOOTSTRAP_INSTRUCTION}"


def goal_bootstrap(args, *, registry: Path) -> str:
    """Preserve explicit caller inputs, not yesterday's resolved registry values.

    The loaded command deliberately omits --bootstrap: one load cannot recurse.
    A persistent entrypoint cannot pin an individual settlement identity.
    """
    if args.turn_instance_id:
        raise ValueError("--bootstrap cannot persist a --turn-instance-id; bind each work iteration through quota")
    if args.visible_goal_host == "traex-cli" and args.available_capabilities:
        raise ValueError("TraeX capability declarations require its separate host projection; use the direct Goal body")
    command = [args.cli_bin, "--format", "json", "--registry", str(registry.resolve())]
    if args.runtime_root:
        command += ["--runtime-root", str(Path(args.runtime_root).expanduser().resolve())]
    command += ["heartbeat-prompt", "--goal-id", args.goal_id]
    for field, flag in (
        ("agent_id", "--agent-id"), ("active_state", "--active-state"),
        ("material_rule", "--material-rule"), ("permission_rule", "--permission-rule"),
        ("runtime_profile", "--runtime-profile"), ("visible_goal_host", "--visible-goal-host"),
        ("host_surface", "--host-surface"), ("scheduler_owner", "--scheduler-owner"),
        ("execution_mode", "--execution-mode"),
    ):
        value = getattr(args, field, None)
        if value is not None:
            if field == "active_state":
                value = str(Path(value).expanduser().resolve())
            command += [flag, value]
    for field, flag in (("agent_scopes", "--agent-scope"),
                        ("available_capabilities", "--available-capability")):
        for value in getattr(args, field, None) or []:
            command += [flag, value]
    if args.cli_bin != "loopx":
        command += ["--cli-bin", args.cli_bin]
    if args.codex_app:
        command.append("--codex-app")
    mode = next((mode for mode in ("full", "compact", "brief", "thin") if getattr(args, mode)), "thin")
    command.append("--" + mode)
    return render_bootstrap(command, title="LoopX managed host bootstrap v1",
        entry="每次进入或恢复本 Goal 时先加载当前规则；升级后重新加载，不创建新 Goal、不接管宿主调度：")


def host_bootstrap_binding(prompt: str) -> dict | None:
    """Recognize only a complete, canonical loader, never a matching prefix."""
    if not prompt.startswith("LoopX managed host bootstrap v1\n"):
        return None
    try:
        command = shlex.split(prompt.split("```sh\n", 1)[1].split("\n```", 1)[0])
        if command[1:3] != ["--format", "json"]:
            return None
        values = dict(cli_bin=command[0], turn_instance_id=None, codex_app=False,
                      full=False, compact=False, brief=False, thin=False,
                      visible_goal_host=None, available_capabilities=[], agent_scopes=[],
                      runtime_root=None)
        singles = {"--" + name.replace("_", "-"): name for name in (
            "registry", "runtime_root", "goal_id", "agent_id", "active_state",
            "material_rule", "permission_rule", "runtime_profile", "visible_goal_host",
            "host_surface", "scheduler_owner", "execution_mode", "cli_bin")}
        repeated = {"--agent-scope": "agent_scopes", "--available-capability": "available_capabilities"}
        booleans = {"--" + name.replace("_", "-"): name for name in ("codex_app", "full", "compact", "brief", "thin")}
        index = 3
        while index < len(command):
            token = command[index]
            if token == "heartbeat-prompt":
                index += 1
                continue
            if token in booleans:
                values[booleans[token]] = True
                index += 1
                continue
            if token in repeated:
                values[repeated[token]].append(command[index + 1])
            elif token in singles:
                values[singles[token]] = command[index + 1]
            else:
                return None
            index += 2
        registry = Path(values.pop("registry"))
        expected = goal_bootstrap(SimpleNamespace(**values), registry=registry)
        return {**values, "registry": registry} if prompt == expected else None
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None
