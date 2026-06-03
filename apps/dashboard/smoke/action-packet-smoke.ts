import { buildActionPacket, buildApprovedAgentHandoff } from "../src/data/action-packet.js";

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

const packet = buildActionPacket({
  goalId: "premium-ui-ai-search-rec-migration",
  title: "Review or authorize",
  summary: "production still blocked; owner/SOP snapshot has 9 blockers, but only two user todos are open",
  userTodoText: "Read the core Lark document section 8 first. Focus on 当前结论 and the Nacos diff 快速锚点 / Diff Anchors table.",
  agentTodoText: "Run the read-only map dry-run after the owner todo is resolved; stop before writes.",
  todoBlocksGate: true,
  operatorQuestion: "是否同意 premium-ui 迁移在 owner/SOP review 后继续推进？",
  suggestedReply: "同意继续 safe-local/offline 路径 / 暂不同意 + 一句话原因。",
  gateFallbackDecision: "同意继续 safe-local/offline 路径；不授权写入或生产动作。",
  boundary: "不要执行 Nacos 写入、Prem metadata upsert、workflow creation 或生产状态变化。",
  durableRecordRule: "记录规则：先用 operator-gate dry-run 预览；确认写入时去掉 --dry-run。",
  safePathLabel: "Read-only map dry-run",
  command: "goal-harness read-only-map --goal-id premium-ui-ai-search-rec-migration --dry-run",
  quotaShortLine: "Operator gate; 0/1440 slots",
  authorityShortLine: "default entries 10/10; topic 10; risk medium",
});

assert(packet.includes("【GH Packet】"), "missing packet title");
assert(packet.includes("【用户/Gate】"), "missing user action section");
assert(packet.includes("待办：Read the core Lark document section 8 first."), "missing first user todo");
assert(packet.includes("先处理/暂缓再判 gate"), "missing todo-before-gate cue");
assert(packet.includes("Gate：是否同意 premium-ui 迁移"), "missing gate question");
assert(packet.includes("【给项目 Agent】"), "missing project-agent handoff section");
assert(packet.includes("待办：Run the read-only map dry-run after the owner todo is resolved; stop before writes."), "missing first agent todo");
assert(packet.includes("路径：Read-only map dry-run"), "missing safe path");
assert(packet.includes("上下文：只信当前 state/status/history 与命令输出"), "missing agent context rule");
assert(packet.includes("不授权写入或生产动作") || packet.includes("不要执行 Nacos 写入"), "missing safety boundary");
assert(packet.length > 430 && packet.length < 820, `unexpected packet length: ${packet.length}`);
assert(
  packet.indexOf("【用户/Gate】") < packet.indexOf("【给项目 Agent】"),
  "user action section must precede project-agent handoff",
);

const approvedHandoff = buildApprovedAgentHandoff({
  goalId: "planned-main-control",
  command: "goal-harness read-only-map --goal-id planned-main-control --dry-run --approved",
  agentTodoText: "Run the read-only map dry-run after owner todo resolution.",
});

assert(approvedHandoff.includes("目标校验：本段只适用于 goal_id=`planned-main-control`"), "missing target guard");
assert(approvedHandoff.includes("上下文规则：本段只携带最小当前指令"), "missing compact context rule");
assert(approvedHandoff.includes("Agent 待办：Run the read-only map dry-run after owner todo resolution."), "missing approved agent todo");
assert(approvedHandoff.includes("operator gate 已记录为 approve"), "missing approved forwarding condition");
assert(approvedHandoff.includes("只执行下面命令"), "missing execution boundary");
assert(approvedHandoff.includes("goal-harness read-only-map --goal-id planned-main-control --dry-run --approved"), "missing approved command");
assert(!approvedHandoff.includes("【GH Packet】"), "handoff-only payload must not include packet wrapper");
assert(!approvedHandoff.includes("【用户/Gate】"), "handoff-only payload must not include user gate wrapper");
assert(!approvedHandoff.includes("建议："), "handoff-only payload must not include human suggestion text");

console.log(`action-packet smoke ok (${packet.length} chars, handoff ${approvedHandoff.length} chars)`);
