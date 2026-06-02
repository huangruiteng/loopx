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
        "goal-harness \\",
        "  --registry ./examples/registry.example.json \\",
        "  --runtime-root ./tmp/runtime \\",
        "  read-only-map \\",
        f"  --goal-id {goal_id} \\",
        "  --dry-run",
    )
    return "\n".join(
        [
            "【Goal Harness Action】",
            f"目标：{goal_id}",
            "动作：Review controller opt-in",
            "",
            "【请你判断】",
            "是否允许目标项目进入 read-only/controller opt-in？",
            f"建议回复：同意 {goal_id} 先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            f"建议判断：同意 {goal_id} 先做 read-only map dry-run；不授权写入或主控接管。",
            "边界：这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
            "记录规则：如需持久记录本次判断，先用本地 operator-gate dry-run 预览；确认写入时去掉 --dry-run；拒绝/暂缓用 reject/defer + public-safe 原因。",
            "",
            "【当前状态】",
            "摘要：planned opt-in review fixture",
            "下一步：先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run",
            "配额：Operator gate; 0/1440 slots",
            "权威源：default entries 10/10; topic 10; risk medium",
            "",
            "【同意后给项目 Agent】",
            "只允许 safe path：Read-only map dry-run",
            f"命令：{project_agent_command.replace(chr(10), ' ')}",
            "要求：用中文回报 changed files、validation、next safe action；需要写入/生产/进一步授权时停下。",
        ]
    )


def main() -> int:
    source = DASHBOARD_PAGE.read_text(encoding="utf-8")
    contract = STATUS_CONTRACT.read_text(encoding="utf-8")
    controller_contract = source_between(
        contract,
        "For controller opt-in packets",
        "`status=read_only_project_map`",
    )
    assert "the dashboard/operator view owns the human decision" in contract
    assert "the project-agent command is only the after-approval dry-run execution path" in contract
    assert "复制后直接发给对应项目 Agent；人只补一句判断。" not in source
    assert "【Goal Harness Action】" in source
    assert "Copy action packet for" in source
    assert "项目 Agent 只有在 approval 后才回报 changed files、validation 和 next safe action。" in source
    assert "转发条件：只有用户已经明确同意 read-only/controller dry-run 后，才把本段发给项目 Agent。" in source
    assert "执行边界：只执行下面只读或 dry-run 项目路径；不要运行用户本地 Gate 记录草稿。" in source
    assert "停止条件：需要真实 approval、write-control、run history append、生产动作或命令失败时，停下等明确授权。" in source
    assert_order(
        controller_contract,
        [
            "operator question must appear before any",
            "local gate preview must appear before any",
            "project-agent command",
        ],
    )

    packet_builder = source_between(source, "function buildHumanFriendlyActionPacket", "function ReviewLinkPanel")
    assert_order(packet_builder, ["【请你判断】", "【当前状态】", "【同意后给项目 Agent】"])
    assert "operatorGateDraftCommand" not in packet_builder

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
    assert "reject/defer + public-safe 原因" in record_rule
    assert "durableOperatorGateRecordRule(item.kind)" in packet_builder

    gate_builder = source_between(source, "function buildOperatorGateDryRunCommand", "function buildOperatorTransitionPreview")
    assert "operator-gate" in gate_builder
    assert "--decision approve" in gate_builder
    assert "controllerApprovalReason(goalId)" in gate_builder
    assert "--dry-run" in gate_builder

    read_only_builder = source_between(source, "function buildReadOnlyMapDryRunCommand", "function buildRefreshStateDryRunCommand")
    assert "read-only-map" in read_only_builder
    assert "--dry-run" in read_only_builder

    quota_state_labels = source_between(source, "const quotaStateLabel", "function quotaVariant")
    assert "Throttled" in quota_state_labels
    assert "本窗口配额已用完" in quota_state_labels

    user_action_builder = source_between(source, "function buildUserActionSummaryItems", "function UserActionSummary")
    assert "const quota = row.queueItem?.quota ?? row.goal.quota;" in user_action_builder
    assert "const quotaState = quota?.state ?? \"waiting\";" in user_action_builder
    assert "decision.waitingOn === \"codex\" && quotaState === \"throttled\"" in user_action_builder
    assert_order(
        user_action_builder,
        [
            "if (decision.waitingOn === \"external_evidence\")",
            "decision.waitingOn === \"codex\" && quotaState === \"throttled\"",
            "if (decision.waitingOn === \"codex\")",
        ],
    )
    user_action_summary = source_between(source, "function UserActionSummary", "function OperatorDecisionPanel")
    assert "buildHumanFriendlyActionPacket({ item, registry, runtimeRoot })" in user_action_summary
    assert "aria-label={`Copy action packet for ${item.goalId}`}" in user_action_summary
    assert "const primaryOperatorGate" not in user_action_summary
    assert "Needs decision" not in user_action_summary

    packet = build_sanitized_controller_packet()
    assert_order(
        packet,
        [
            "【请你判断】",
            "是否允许目标项目进入 read-only/controller opt-in？",
            "建议回复：同意 planned-main-control 先做 read-only map dry-run / 暂不同意 + 一句话原因。",
            "记录规则：如需持久记录本次判断",
            "【当前状态】",
            "【同意后给项目 Agent】",
            "read-only-map",
            "需要写入/生产/进一步授权时停下",
        ],
    )
    assert "operator-gate dry-run 预览" in packet, packet
    assert "operator-gate \\" not in packet, packet
    assert packet.count("read-only-map") == 1, packet
    assert len(packet.splitlines()) <= 21, packet
    assert "不授权写入或主控接管" in packet
    print("review-packet-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
