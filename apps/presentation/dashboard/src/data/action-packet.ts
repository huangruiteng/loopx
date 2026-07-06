export type ProjectAssetSource = "project_asset" | "legacy_raw_fallback";

export type ActionPacketInput = {
  goalId: string;
  title: string;
  summary: string;
  userTodoText?: string | null;
  agentTodoText?: string | null;
  todoBlocksGate?: boolean;
  operatorQuestion?: string | null;
  suggestedReply: string;
  gateFallbackDecision: string;
  boundary: string;
  durableRecordRule?: string | null;
  safePathLabel: string;
  command?: string | null;
  quotaShortLine?: string | null;
  authorityShortLine?: string | null;
  projectOwner?: string | null;
  projectGate?: string | null;
  projectNextAction?: string | null;
  projectStopCondition?: string | null;
  projectAssetSource?: ProjectAssetSource | null;
  handoffReadinessLine?: string | null;
};

export type ApprovedAgentHandoffInput = {
  goalId: string;
  command: string;
  agentTodoText?: string | null;
  projectNextAction?: string | null;
  projectStopCondition?: string | null;
  projectAssetSource?: ProjectAssetSource | null;
};

export function buildApprovedAgentHandoff(input: ApprovedAgentHandoffInput) {
  const command = input.command.replace(/\s+/g, " ").trim();
  const isFallback = input.projectAssetSource === "legacy_raw_fallback";
  const nextLabel = isFallback ? "Fallback Next" : "Project Asset Next";
  const stopLabel = isFallback ? "Fallback Stop" : "Project Asset Stop";
  return [
    `目标校验：本段只适用于 goal_id=\`${input.goalId}\`；如果与你当前 active goal 或 registry entry 不一致，停止并回报目标不匹配。`,
    "上下文规则：本段只携带最小当前指令；不要从旧聊天或旧 packet 拼当前状态。需要更多上下文时，先读当前 active state、status、history 和命令输出。",
    isFallback ? "Project Asset Source：legacy/raw fallback；未收到 project_asset，Next/Stop 来自 raw status 降级判断。" : null,
    input.projectNextAction ? `${nextLabel}：${compactPacketText(input.projectNextAction, 180)}` : null,
    input.projectStopCondition ? `${stopLabel}：${compactPacketText(input.projectStopCondition, 180)}` : null,
    input.agentTodoText ? `Agent 待办：${compactPacketText(input.agentTodoText, 220)}` : null,
    "转发条件：operator gate 已记录为 approve；本段只用于把已批准的 agent_command 交给目标项目 Agent。",
    "执行边界：只执行下面命令；这是只读/dry-run 执行，不是写权限、主控接管或生产动作授权。",
    "停止条件：命令失败，或需要写入、run history append、生产动作、更高权限时，停下并用中文回报结果。",
    "",
    "```bash",
    command,
    "```",
  ].filter(Boolean).join("\n");
}

export function buildActionPacket(input: ActionPacketInput) {
  const isFallback = input.projectAssetSource === "legacy_raw_fallback";
  const needsTodoFirst = Boolean(input.userTodoText && input.todoBlocksGate);
  const userActionLines = input.userTodoText
    ? [
      `待办：${compactPacketText(input.userTodoText, 180)}${needsTodoFirst ? "（先处理/暂缓再判 gate）" : ""}`,
    ]
    : [
      "待办：无",
    ];
  const gateLines = input.operatorQuestion
    ? [
      `Gate：${compactPacketText(input.operatorQuestion, 160)}`,
      `建议：${needsTodoFirst ? `先确认待办；完成后：${input.suggestedReply}` : input.suggestedReply}`,
    ]
    : [
      `Gate：无；建议：${input.gateFallbackDecision}`,
    ];
  const stateLine = [
    compactPacketText(input.summary, 110),
  ].filter(Boolean).join("；");
  const compactContextLines = [
    input.quotaShortLine ? `Quota：${compactPacketText(input.quotaShortLine, 80)}` : null,
    input.authorityShortLine ? `Authority：${compactPacketText(input.authorityShortLine, 110)}` : null,
  ];
  const projectAssetLines = [
    isFallback
      ? "Project Asset：legacy/raw fallback；未收到 project_asset，Owner/Gate/Stop 未确认。"
      : input.projectOwner || input.projectGate
      ? `Project Asset：Owner=${compactPacketText(input.projectOwner ?? "unknown", 70)}；Gate=${compactPacketText(input.projectGate ?? "unknown", 70)}`
      : null,
    input.projectNextAction ? `${isFallback ? "Fallback Next" : "Next"}：${compactPacketText(input.projectNextAction, 160)}` : null,
    input.projectStopCondition ? `${isFallback ? "Fallback Stop" : "Stop"}：${compactPacketText(input.projectStopCondition, 160)}` : null,
    input.handoffReadinessLine ? `Handoff：${compactPacketText(input.handoffReadinessLine, 140)}` : null,
  ];

  return [
    "【GH Packet】",
    `目标：${input.goalId}`,
    `状态：${stateLine}`,
    ...projectAssetLines,
    ...compactContextLines,
    "",
    "【用户/Gate】",
    ...userActionLines,
    ...gateLines,
    `边界：${compactPacketText(input.boundary, 110)}`,
    input.durableRecordRule ? `记录：${compactPacketText(input.durableRecordRule, 180)}` : null,
    "",
    "【给项目 Agent】",
    input.agentTodoText ? `待办：${compactPacketText(input.agentTodoText, 180)}` : null,
    `路径：${input.safePathLabel}`,
    "上下文：只信当前 state/status/history 与命令输出；勿拼旧状态。",
    input.command ? `命令：${input.command.replace(/\s+/g, " ").trim()}` : null,
    "回报：files / validation / next；需授权则停。",
  ].filter(Boolean).join("\n");
}

export function compactPacketText(value: string, maxLength = 260) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) {
    return compact;
  }
  return `${compact.slice(0, maxLength - 1)}…`;
}
