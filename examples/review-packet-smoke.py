#!/usr/bin/env python3
"""Smoke-test the dashboard operator action packet contract.

The dashboard owns the operator-facing packet text. This smoke keeps a
public-safe fixture for the planned opt-in path and checks the source keeps the
copyable packet short and human-facing. The longer local gate dry-run remains
available as an advanced/debug path, not as the default copied packet.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PAGE = REPO_ROOT / "apps/dashboard/src/views/dashboard-page.tsx"
ACTION_PACKET = REPO_ROOT / "apps/dashboard/src/data/action-packet.ts"
STATUS_CONTRACT = REPO_ROOT / "docs/status-data-contract.md"


def command_block(command: str) -> str:
    return "\n".join(["```bash", command, "```"])


def multiline_command(*lines: str) -> str:
    return "\n".join(lines)


def assert_order(text: str, labels: list[str]) -> None:
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions), (labels, positions, text)


def source_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def build_sanitized_controller_packet() -> str:
    goal_id = "planned-main-control"
    project_agent_command = multiline_command(
        "loopx \\",
        "  --registry ./examples/registry.example.json \\",
        "  --runtime-root ./tmp/runtime \\",
        "  read-only-map \\",
        f"  --goal-id {goal_id} \\",
        "  --dry-run",
    )
    return "\n".join(
        [
            "【GH Packet】",
            f"目标：{goal_id}",
            "状态：planned opt-in review fixture",
            "",
            "【用户/Gate】",
            "待办：无",
            "Gate：是否允许目标项目进入 read-only/controller opt-in？",
            f"建议：同意 {goal_id} 先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "边界：这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
            "记录：落盘先 dry-run。",
            "",
            "【给项目 Agent】",
            "待办：Run the read-only map dry-run after the owner todo is resolved.",
            "路径：Read-only map dry-run",
            f"命令：{project_agent_command.replace(chr(10), ' ')}",
            "回报：files / validation / next；需授权则停。",
        ]
    )


def build_sanitized_controller_packet_with_user_todo() -> str:
    goal_id = "planned-main-control"
    project_agent_command = multiline_command(
        "loopx \\",
        "  --registry ./examples/registry.example.json \\",
        "  --runtime-root ./tmp/runtime \\",
        "  read-only-map \\",
        f"  --goal-id {goal_id} \\",
        "  --dry-run",
    )
    return "\n".join(
        [
            "【GH Packet】",
            f"目标：{goal_id}",
            "状态：planned opt-in review fixture",
            "",
            "【用户/Gate】",
            "待办：Read the owner review worksheet first.（先处理/暂缓再判 gate）",
            "Gate：是否允许目标项目进入 read-only/controller opt-in？",
            f"建议：先确认待办；完成后：同意 {goal_id} 先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "边界：这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
            "记录：落盘先 dry-run。",
            "",
            "【给项目 Agent】",
            "路径：Read-only map dry-run",
            f"命令：{project_agent_command.replace(chr(10), ' ')}",
            "回报：files / validation / next；需授权则停。",
        ]
    )


def build_sanitized_approved_command_packet() -> str:
    goal_id = "planned-main-control"
    approved_command = "loopx read-only-map --goal-id planned-main-control --dry-run --approved"
    return "\n".join(
        [
            "【GH Packet】",
            f"目标：{goal_id}",
            "状态：operator gate approved fixture",
            "",
            "【用户/Gate】",
            "待办：无",
            "Gate：无；建议：直接转发给项目 Agent；不追加写权限、主控接管或生产动作授权。",
            "边界：只执行已批准的只读/dry-run agent_command；如需写入或更高权限，项目 Agent 必须再次停下。",
            "",
            "【给项目 Agent】",
            "路径：Approved agent command",
            f"命令：{approved_command}",
            "回报：files / validation / next；需授权则停。",
        ]
    )


def build_sanitized_focus_wait_packet() -> str:
    goal_id = "focus-wait-owner-blocker"
    status_command = (
        "loopx --registry ./examples/registry.example.json "
        "--runtime-root ./tmp/runtime status --goal-id focus-wait-owner-blocker"
    )
    return "\n".join(
        [
            "【GH Packet】",
            f"目标：{goal_id}",
            "状态：quiet until owner evidence, a clean baseline, or external eval changes",
            "",
            "【用户/Gate】",
            "待办：Provide new owner evidence, a clean baseline, or external eval before delivery resumes.",
            "Gate：无；建议：继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。",
            "边界：这不是 delivery approval；项目 Agent 只做 status/history inspection，不执行交付路径、写入、reward append 或生产动作。",
            "",
            "【给项目 Agent】",
            "待办：只检查当前 state/status/history；保持 focus_wait 并用中文回报仍在等待什么。",
            "路径：Status/history inspection only",
            f"命令：{status_command}",
            "回报：files / validation / next；需授权则停。",
        ]
    )


def main() -> int:
    source = DASHBOARD_PAGE.read_text(encoding="utf-8")
    action_packet_source = ACTION_PACKET.read_text(encoding="utf-8")
    contract = STATUS_CONTRACT.read_text(encoding="utf-8")
    controller_contract = source_between(
        contract,
        "For controller opt-in packets",
        "`status=read_only_project_map`",
    )
    assert "the dashboard/operator view owns the human decision" in contract
    assert "the project-agent command is the after-approval dry-run path" in contract
    assert "复制后直接发给对应项目 Agent；人只补一句判断。" not in source
    assert "【GH Packet】" in action_packet_source
    assert "【用户/Gate】" in action_packet_source
    assert "Copy action packet for" in source
    assert "需授权则停" in action_packet_source
    assert "input.command ? `命令：" in action_packet_source
    assert_order(
        controller_contract,
        [
            "operator question must appear before any",
            "local gate preview must appear before any",
            "project-agent command",
        ],
    )

    packet_builder = source_between(source, "function buildHumanFriendlyActionPacket", "function readinessVariant")
    assert "return buildActionPacket({" in packet_builder
    assert "const approvedAgentCommand = item.kind === \"codex\" && Boolean(item.agentCommand);" in packet_builder
    assert "const isFocusWait = isFocusWaitQuota(item.quota);" in packet_builder
    assert "const agentTodo = firstOpenTodo(item.agentTodos);" in packet_builder
    assert "agentTodoText: agentTodo?.text" in packet_builder
    assert "projectAssetSource: item.projectAssetSource" in packet_builder
    assert "Status/history inspection only" in packet_builder
    assert "保持 focus_wait 并用中文回报仍在等待什么" in packet_builder
    assert "不执行交付路径、写入、reward append 或生产动作" in packet_builder
    assert "直接转发给项目 Agent；不追加写权限、主控接管或生产动作授权。" in packet_builder
    assert "只执行已批准的只读/dry-run agent_command" in packet_builder
    assert "Approved agent command" in packet_builder
    assert_order(action_packet_source, ["【GH Packet】", "【用户/Gate】", "【给项目 Agent】"])
    assert "operatorGateDraftCommand" not in packet_builder
    assert "待办：" in action_packet_source
    assert "input.agentTodoText ? `待办：" in action_packet_source
    assert "Gate：" in action_packet_source
    assert "先确认待办" in action_packet_source

    controller_prompt = source_between(source, "if (kind === \"controller\")", "if (kind === \"codex\")")
    assert "是否允许目标项目进入 read-only/controller opt-in？" in controller_prompt
    assert "同意先做 read-only map dry-run / 暂不同意 + 一句话原因。" in controller_prompt
    assert "不写 operator gate、run history、write-control、实验控制或生产动作" in controller_prompt

    controller_reply = source_between(source, "function controllerReplyLine", "function suggestedDecisionLine")
    assert "同意 ${goalId} 先做 read-only map dry-run / 暂不同意 + 一句话原因。" in controller_reply
    assert "同意 ${goalId} 先做 read-only map dry-run，不授权写入或生产动作" in controller_reply
    record_rule = source_between(source, "function durableOperatorGateRecordRule", "function suggestedDecisionLine")
    assert "记录规则：如需持久记录本次判断" in record_rule
    assert "operator-gate dry-run 预览" in record_rule
    assert "operator_gate_resume_contract_v0" in record_rule
    assert "只在该决策点 rebase 当前权威状态" in record_rule
    assert "不回滚或带回整个仓库" in record_rule
    assert "reject/defer + public-safe 原因" in record_rule
    assert "durableOperatorGateRecordRule(item.kind)" in packet_builder

    gate_builder = source_between(source, "function buildOperatorGateDryRunCommand", "function buildOperatorDecision")
    assert "operator-gate" in gate_builder
    assert "--decision approve" in gate_builder
    assert "controllerApprovalReason(goalId)" in gate_builder
    assert "--dry-run" in gate_builder

    read_only_builder = source_between(source, "function buildReadOnlyMapDryRunCommand", "function buildRefreshStateDryRunCommand")
    assert "read-only-map" in read_only_builder
    assert "--dry-run" in read_only_builder

    quota_state_labels = source_between(source, "const quotaStateLabel", "function quotaVariant")
    assert "Focus wait" in quota_state_labels
    assert "等待 owner evidence / clean baseline / external eval" in quota_state_labels
    assert "Throttled" in quota_state_labels
    assert "本窗口配额已用完" in quota_state_labels

    user_action_builder = source_between(source, "function buildUserActionSummaryItems", "function UserActionSummary")
    assert "const projectAsset = row.queueItem?.project_asset;" in user_action_builder
    assert 'const projectAssetSource: ProjectAssetSource = projectAsset ? "project_asset" : "legacy_raw_fallback";' in user_action_builder
    assert "const quota = projectAsset?.quota ?? row.queueItem?.quota ?? row.goal.quota;" in user_action_builder
    assert "todosFromProjectAssetSummary(projectAsset?.user_todos" in user_action_builder
    assert "const nextAction = projectAsset?.next_action ?? decision.action;" in user_action_builder
    assert "const stopCondition = projectAsset?.stop_condition ?? handoffCondition ?? decision.action;" in user_action_builder
    assert "const latestValidation = projectAsset?.latest_validation;" in user_action_builder
    assert "projectAssetSource," in user_action_builder
    assert "const quotaState = quota?.state ?? \"waiting\";" in user_action_builder
    assert "decision.waitingOn === \"codex\" && quotaState === \"focus_wait\"" in user_action_builder
    assert "Focus wait owner blocker" in user_action_builder
    assert "Status/history inspection only" in user_action_builder
    assert "decision.waitingOn === \"codex\" && quotaState === \"throttled\"" in user_action_builder
    assert_order(
        user_action_builder,
        [
            "if (decision.waitingOn === \"external_evidence\")",
            "decision.waitingOn === \"codex\" && quotaState === \"focus_wait\"",
            "decision.waitingOn === \"codex\" && quotaState === \"throttled\"",
            "if (decision.waitingOn === \"codex\")",
        ],
    )
    user_action_surface = source_between(source, "function UserActionSummary", "function buildOperatorActionBridge")
    assert "Legacy/raw fallback" in user_action_surface
    assert "Owner/Gate/Stop are not project_asset-backed" in user_action_surface
    assert "Fallback next:" in user_action_surface
    assert "Fallback stop:" in user_action_surface
    user_action_summary = source_between(source, "function UserActionSummary", "function OperatorDecisionPanel")
    assert "buildHumanFriendlyActionPacket({ item, registry, runtimeRoot })" in user_action_summary
    assert "aria-label={`Copy action packet for ${item.goalId}`}" in user_action_summary
    assert "Copy Focus Packet" in user_action_summary
    assert "const primaryOperatorGate" not in user_action_summary
    assert "Needs decision" not in user_action_summary
    assert "blocksGate={Boolean(item.operatorQuestion && firstOpenTodo(item.userTodos))}" in user_action_summary
    assert "focusWait={isFocusWaitQuota(item.quota)}" in user_action_summary
    assert "formatLatestValidation(item.latestValidation)" in user_action_summary
    assert "const agentTodo = firstOpenTodo(item.agentTodos);" in user_action_summary
    assert "Agent todo" in user_action_summary
    assert "先做用户待办" in source
    assert "完成或明确暂缓这个用户待办后，再审批下面的 gate。" in source
    assert "Owner blocker" in source
    assert "有新 owner evidence、clean baseline 或外部 eval 前保持 focus wait" in source

    packet = build_sanitized_controller_packet()
    assert_order(
        packet,
        [
            "【用户/Gate】",
            "Gate：是否允许目标项目进入 read-only/controller opt-in？",
            "建议：同意 planned-main-control 先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "记录：落盘先 dry-run。",
            "【给项目 Agent】",
            "read-only-map",
            "需授权则停",
        ],
    )
    assert "记录：落盘先 dry-run。" in packet, packet
    assert "operator-gate \\" not in packet, packet
    assert packet.count("read-only-map") == 1, packet
    assert len(packet.splitlines()) <= 18, packet
    assert "不写 operator gate、run history、write-control、实验控制或生产动作" in packet

    packet_with_todo = build_sanitized_controller_packet_with_user_todo()
    assert_order(
        packet_with_todo,
        [
            "【用户/Gate】",
            "待办：",
            "先处理/暂缓再判 gate",
            "Gate：",
            "建议：先确认待办",
            "【给项目 Agent】",
        ],
    )
    assert "Read the owner review worksheet first." in packet_with_todo
    assert "operator-gate \\" not in packet_with_todo, packet_with_todo
    assert len(packet_with_todo.splitlines()) <= 18, packet_with_todo

    approved_packet = build_sanitized_approved_command_packet()
    assert_order(
        approved_packet,
        [
            "【用户/Gate】",
            "Gate：无；建议：直接转发给项目 Agent",
            "只执行已批准的只读/dry-run agent_command",
            "【给项目 Agent】",
            "Approved agent command",
        ],
    )
    assert "同意让 Codex 沿 safe path 继续" not in approved_packet, approved_packet
    assert "如果下一步需要写入、reward append、approval" not in approved_packet, approved_packet
    assert "不追加写权限、主控接管或生产动作授权" in approved_packet, approved_packet
    assert len(approved_packet.splitlines()) <= 18, approved_packet

    focus_wait_packet = build_sanitized_focus_wait_packet()
    assert_order(
        focus_wait_packet,
        [
            "【用户/Gate】",
            "待办：Provide new owner evidence",
            "Gate：无；建议：继续保持 focus wait",
            "【给项目 Agent】",
            "Status/history inspection only",
        ],
    )
    assert "保持 focus_wait" in focus_wait_packet, focus_wait_packet
    assert "read-only-map" not in focus_wait_packet, focus_wait_packet
    assert "operator-gate" not in focus_wait_packet, focus_wait_packet
    assert len(focus_wait_packet.splitlines()) <= 18, focus_wait_packet
    print("review-packet-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
