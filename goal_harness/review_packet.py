from __future__ import annotations

import shlex
from typing import Any


def command_block(command: str | None) -> str:
    if not command:
        return "（当前没有可执行命令；先读取 status/history。）"
    return "\n".join(["```bash", command, "```"])


def build_status_command(status_payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  --format json \\",
            "  status",
        ]
    )


def build_history_command(status_payload: dict[str, Any], goal_id: str) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  history \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            "  --limit 3",
        ]
    )


def build_read_only_map_command(status_payload: dict[str, Any], goal_id: str) -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  read-only-map \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            "  --dry-run",
        ]
    )


def operator_gate_reason_summary(goal_id: str, decision: str) -> str:
    if decision == "approve":
        return controller_approval_reason(goal_id)
    if decision == "reject":
        return f"暂不同意 {goal_id} 先做 read-only map dry-run，原因：<public-safe-reason>"
    if decision == "defer":
        return f"暂缓 {goal_id} read-only map dry-run，等待：<public-safe-condition>"
    return "<public-safe-reason>"


def build_operator_gate_command(status_payload: dict[str, Any], goal_id: str, *, decision: str = "approve") -> str:
    return "\n".join(
        [
            "goal-harness \\",
            f"  --registry {shlex.quote(str(status_payload.get('registry') or '<registry>'))} \\",
            f"  --runtime-root {shlex.quote(str(status_payload.get('runtime_root') or '<runtime-root>'))} \\",
            "  operator-gate \\",
            f"  --goal-id {shlex.quote(goal_id)} \\",
            f"  --decision {shlex.quote(decision)} \\",
            f"  --reason-summary {shlex.quote(operator_gate_reason_summary(goal_id, decision))} \\",
            "  --dry-run",
        ]
    )


def controller_reply(goal_id: str) -> str:
    return f"同意 {goal_id} 先做 read-only map dry-run / 暂不同意 + 一句话原因。"


def controller_approval_reason(goal_id: str) -> str:
    return f"同意 {goal_id} 先做 read-only map dry-run，不授权写入或生产动作"


def operator_gate_decision_commands(status_payload: dict[str, Any], goal_id: str) -> dict[str, str]:
    return {
        decision: build_operator_gate_command(status_payload, goal_id, decision=decision)
        for decision in ("approve", "reject", "defer")
    }


def find_goal(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    run_history = status_payload.get("run_history")
    if not isinstance(run_history, dict):
        return None
    for goal in run_history.get("goals") or []:
        if isinstance(goal, dict) and goal.get("id") == goal_id:
            return goal
    return None


def find_queue_item(status_payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    attention_queue = status_payload.get("attention_queue")
    if not isinstance(attention_queue, dict):
        return None
    for item in attention_queue.get("items") or []:
        if isinstance(item, dict) and item.get("goal_id") == goal_id:
            return item
    return None


def latest_run(goal: dict[str, Any] | None) -> dict[str, Any] | None:
    runs = goal.get("latest_runs") if isinstance(goal, dict) else None
    if isinstance(runs, list) and runs and isinstance(runs[0], dict):
        return runs[0]
    return None


def infer_action_kind(item: dict[str, Any] | None, goal: dict[str, Any] | None) -> str:
    run = latest_run(goal)
    missing_gates = item.get("missing_gates") if isinstance(item, dict) else None
    if not isinstance(missing_gates, list) and isinstance(run, dict):
        readiness = run.get("controller_readiness")
        missing_gates = readiness.get("missing_gates") if isinstance(readiness, dict) else None
    missing_gate_set = {str(gate) for gate in missing_gates or [] if gate}
    if isinstance(item, dict) and item.get("severity") == "high":
        return "health"
    if "human_reward_capture" in missing_gate_set:
        return "reward"
    waiting_on = str(item.get("waiting_on") if isinstance(item, dict) else "")
    if waiting_on in {"controller", "user_or_controller"}:
        return "controller"
    if waiting_on == "external_evidence":
        return "evidence"
    if waiting_on == "codex":
        return "codex"
    return "status"


def human_prompt(kind: str) -> dict[str, str]:
    if kind == "reward":
        return {
            "question": "是否把这次判断记录为 run-bound human_reward？",
            "reply": "同意记录 / 暂不同意 + 一句话原因。",
            "boundary": "只有去掉 --dry-run 才会写 human_reward 和 active-state 摘要；这不是 write-control、controller opt-in 或生产动作授权。",
        }
    if kind == "controller":
        return {
            "question": "是否允许目标项目进入 read-only/controller opt-in？",
            "reply": "同意先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "boundary": "这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
        }
    if kind == "codex":
        return {
            "question": "是否让项目 Agent 沿 safe local path 继续？",
            "reply": "同意继续 / 暂不同意 + 一句话原因。",
            "boundary": "如果下一步需要写入、reward append、approval 或 write-control，项目 Agent 必须先停下等明确授权。",
        }
    if kind == "evidence":
        return {
            "question": "是否继续等待外部证据，而不升级成决策建议？",
            "reply": "继续等待 / 不继续等待 + 一句话原因。",
            "boundary": "观察状态不是 reward、approval 或 controller opt-in。",
        }
    if kind == "health":
        return {
            "question": "是否先修健康阻塞，再讨论 reward/controller/codex handoff？",
            "reply": "先修阻塞 / 暂不处理 + 一句话原因。",
            "boundary": "健康修复不等于授权 reward append、approval 或 write-control。",
        }
    return {
        "question": "当前是否需要转给项目 Agent 继续处理？",
        "reply": "继续 / 不继续 / 继续观察 + 一句话原因。",
        "boundary": "本回复不自动写 reward、approval、controller opt-in 或 write-control。",
    }


def suggested_decision(kind: str, item: dict[str, Any] | None, goal_id: str | None = None) -> str:
    if kind == "controller":
        lead = f"同意 {goal_id} 先做" if goal_id else "同意先做"
        question = str(item.get("operator_question") if isinstance(item, dict) else "")
        if "read-only map" in question:
            return f"{lead} read-only map dry-run；不授权写入或生产动作。"
        return f"{lead}只读 controller dry-run；不授权写入或生产动作。"
    if kind == "reward":
        return "同意记录这次 human reward / 暂不同意，原因是..."
    if kind == "codex":
        return "同意让 Codex 沿 safe path 继续；如需写入再单独请求授权。"
    if kind == "evidence":
        return "继续等待外部证据；暂不升级成决策建议。"
    if kind == "health":
        return "先修健康阻塞；暂不处理 reward/controller/codex handoff。"
    return "继续 / 不继续 / 继续观察，并补一句原因。"


def project_agent_command(status_payload: dict[str, Any], goal_id: str, kind: str, item: dict[str, Any] | None) -> str:
    if kind == "reward":
        return build_history_command(status_payload, goal_id)
    if isinstance(item, dict) and item.get("agent_command") and kind in {"controller", "codex"}:
        return str(item.get("agent_command"))
    if kind == "controller":
        return build_read_only_map_command(status_payload, goal_id)
    if kind == "codex":
        return build_history_command(status_payload, goal_id)
    return build_status_command(status_payload)


def target_goal_guard(goal_id: str) -> str:
    return (
        f"目标校验：本段只适用于 goal_id=`{goal_id}`；如果与你当前 active goal "
        "或 registry entry 不一致，停止并回报目标不匹配。"
    )


def project_agent_section(kind: str, command: str, goal_id: str) -> str:
    goal_guard = target_goal_guard(goal_id)
    if kind == "reward":
        lines = [
            goal_guard,
            "转发条件：只有用户已经真实记录 run-bound human_reward 后，才把本段发给项目 Agent。",
            "执行边界：不要替用户写 reward；active state 只做摘要，reward 的权威来源是 run-bound human_reward overlay。",
            "停止条件：如果 reward 还停留在 dry-run / 草稿 / 口头判断，停下等待用户记录；如果已经记录，只用下面 history 路径读取。",
            "",
            command_block(command),
        ]
    elif kind == "controller":
        lines = [
            goal_guard,
            "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。",
            "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。",
            "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。",
            "",
            command_block(command),
        ]
    else:
        lines = [
            goal_guard,
            "转发条件：只有用户已经同意 safe local path 后，才把本段发给项目 Agent。",
            "执行边界：读取本项目 status/history 后，只执行下面只读或 dry-run 路径。",
            "停止条件：需要真实写 reward、approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。",
            "",
            command_block(command),
        ]
    return "\n".join(lines)


def build_review_packet(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    action_kind: str | None = None,
    review_url: str | None = None,
) -> dict[str, Any]:
    item = find_queue_item(status_payload, goal_id)
    goal = find_goal(status_payload, goal_id)
    if item is None and goal is None:
        return {
            "ok": False,
            "goal_id": goal_id,
            "error": f"goal not found in status payload: {goal_id}",
        }

    kind = action_kind or infer_action_kind(item, goal)
    prompt = human_prompt(kind)
    question = str(item.get("operator_question") or prompt["question"]) if isinstance(item, dict) else prompt["question"]
    summary = str(item.get("recommended_action") or "当前状态源没有对应的 action card。") if isinstance(item, dict) else "当前状态源没有对应的 action card。"
    command = project_agent_command(status_payload, goal_id, kind, item)
    gate_commands = operator_gate_decision_commands(status_payload, goal_id) if kind == "controller" else {}
    gate_command = gate_commands.get("approve") if gate_commands else None
    decision = suggested_decision(kind, item, goal_id)
    reply = controller_reply(goal_id) if kind == "controller" else prompt["reply"]
    agent_text = project_agent_section(kind, command, goal_id)
    type_label = {
        "reward": "Reward",
        "controller": "Controller",
        "codex": "Codex",
        "evidence": "Evidence",
        "health": "Health",
    }.get(kind, "Status")
    lines = [
        "【Goal Harness Review Packet】",
        f"目标：{goal_id}",
        f"类型：{type_label}",
        f"链接：{review_url or 'CLI generated packet; no dashboard URL provided.'}",
        f"摘要：{summary}",
        "",
        "【人只需判断】",
        f"问题：{question}",
        f"建议判断：{decision}",
        f"回复：{reply}",
        f"边界：{prompt['boundary']}",
    ]
    if gate_command:
        lines.extend(
            [
                "",
                "【用户本地 Gate 记录草稿】",
                "用途：人确认后，由用户或主控先 dry-run 预览 durable operator gate；不要把它当作项目 Agent 执行命令。",
                "记录规则：保留 --dry-run 只预览；确认写入 durable operator gate 时再删除 --dry-run。若拒绝或暂缓，只把 --decision 和 --reason-summary 改成 reject / defer 与一句 public-safe 原因。",
                command_block(gate_command),
            ]
        )
    lines.extend(
        [
            "",
            "【给项目 Agent】",
            agent_text,
            "",
            "回报：用中文说明 changed files、validation 和 next safe action。",
        ]
    )
    return {
        "ok": True,
        "goal_id": goal_id,
        "kind": kind,
        "waiting_on": item.get("waiting_on") if isinstance(item, dict) else None,
        "status": item.get("status") if isinstance(item, dict) else goal.get("status") if isinstance(goal, dict) else None,
        "review_url": review_url,
        "question": question,
        "suggested_decision": decision,
        "project_agent_command": command,
        "operator_gate_dry_run_command": gate_command,
        "operator_gate_decision_commands": gate_commands,
        "packet": "\n".join(lines),
    }


def render_review_packet_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return "\n".join(
            [
                "# Goal Harness Review Packet",
                "",
                f"- ok: `{payload.get('ok')}`",
                f"- goal_id: `{payload.get('goal_id')}`",
                f"- error: {payload.get('error')}",
            ]
        )
    return str(payload.get("packet") or "")
