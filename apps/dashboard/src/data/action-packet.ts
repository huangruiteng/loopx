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
};

export function buildActionPacket(input: ActionPacketInput) {
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

  return [
    "【GH Packet】",
    `目标：${input.goalId}`,
    `状态：${stateLine}`,
    "",
    "【用户/Gate】",
    ...userActionLines,
    ...gateLines,
    `边界：${compactPacketText(input.boundary, 110)}`,
    input.durableRecordRule ? "记录：落盘先 dry-run。" : null,
    "",
    "【给项目 Agent】",
    input.agentTodoText ? `待办：${compactPacketText(input.agentTodoText, 180)}` : null,
    `路径：${input.safePathLabel}`,
    "上下文：只信当前 state/status/history 与命令输出；勿用旧聊天/旧 packet 拼状态。",
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
