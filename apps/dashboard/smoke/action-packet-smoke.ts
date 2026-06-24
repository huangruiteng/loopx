import { buildActionPacket, buildApprovedAgentHandoff } from "../src/data/action-packet.js";
// @ts-expect-error The smoke compiler intentionally runs without @types/node.
import { readFileSync } from "node:fs";

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

const packet = buildActionPacket({
  goalId: "showcase-safe-route",
  title: "Review or authorize",
  summary: "production still blocked; owner/SOP snapshot has 9 blockers, but only two user todos are open",
  userTodoText: "Read the public decision memo section 8 first. Focus on 当前结论 and the config diff 快速锚点 / Diff Anchors table.",
  agentTodoText: "Run the read-only map dry-run after the owner todo is resolved; stop before writes.",
  todoBlocksGate: true,
  operatorQuestion: "是否同意 showcase safe route 在 owner/SOP review 后继续推进？",
  suggestedReply: "同意继续 safe-local/offline 路径 / 暂不同意 + 一句话原因。",
  gateFallbackDecision: "同意继续 safe-local/offline 路径；不授权写入或生产动作。",
  boundary: "不要执行配置写入、metadata upsert、workflow creation 或生产状态变化。",
  durableRecordRule: "记录规则：先用 operator-gate dry-run 预览；确认写入时去掉 --dry-run。",
  safePathLabel: "Read-only map dry-run",
  command: "loopx read-only-map --goal-id showcase-safe-route --dry-run",
  quotaShortLine: "Operator gate; 0/1440 slots",
  authorityShortLine: "default entries 10/10; topic 10; materials 6; owner review 1; stale 1; risk medium",
  projectOwner: "user_or_controller",
  projectGate: "owner_sop_review",
  projectNextAction: "Project asset says the owner/SOP review is the current authority.",
  projectStopCondition: "Stop before write-control or production mutation.",
  projectAssetSource: "project_asset",
  handoffReadinessLine: "ready; codex_ready=true; source=project_asset; quota=eligible; failed=none",
});

assert(packet.includes("【GH Packet】"), "missing packet title");
assert(packet.includes("【用户/Gate】"), "missing user action section");
assert(packet.includes("Quota：Operator gate; 0/1440 slots"), "missing compact quota context");
assert(packet.includes("Authority：default entries 10/10; topic 10; materials 6; owner review 1; stale 1; risk medium"), "missing compact authority/material context");
assert(packet.includes("Project Asset：Owner=user_or_controller；Gate=owner_sop_review"), "missing project-asset owner/gate");
assert(packet.includes("Next：Project asset says the owner/SOP review is the current authority."), "missing project-asset next action");
assert(packet.includes("Stop：Stop before write-control or production mutation."), "missing project-asset stop condition");
assert(packet.includes("Handoff：ready; codex_ready=true; source=project_asset; quota=eligible; failed=none"), "missing handoff readiness");
assert(packet.includes("待办：Read the public decision memo section 8 first."), "missing first user todo");
assert(packet.includes("先处理/暂缓再判 gate"), "missing todo-before-gate cue");
assert(packet.includes("Gate：是否同意 showcase safe route"), "missing gate question");
assert(packet.includes("【给项目 Agent】"), "missing project-agent handoff section");
assert(packet.includes("待办：Run the read-only map dry-run after the owner todo is resolved; stop before writes."), "missing first agent todo");
assert(packet.includes("路径：Read-only map dry-run"), "missing safe path");
assert(packet.includes("上下文：只信当前 state/status/history 与命令输出"), "missing agent context rule");
assert(packet.includes("不授权写入或生产动作") || packet.includes("不要执行配置写入"), "missing safety boundary");
assert(packet.length > 600 && packet.length < 1200, `unexpected packet length: ${packet.length}`);
assert(
  packet.indexOf("【用户/Gate】") < packet.indexOf("【给项目 Agent】"),
  "user action section must precede project-agent handoff",
);

const approvedHandoff = buildApprovedAgentHandoff({
  goalId: "planned-main-control",
  command: "loopx read-only-map --goal-id planned-main-control --dry-run --approved",
  agentTodoText: "Run the read-only map dry-run after owner todo resolution.",
  projectNextAction: "Approved project asset next action.",
  projectStopCondition: "Stop if execution needs write authority.",
  projectAssetSource: "project_asset",
});

assert(approvedHandoff.includes("目标校验：本段只适用于 goal_id=`planned-main-control`"), "missing target guard");
assert(approvedHandoff.includes("上下文规则：本段只携带最小当前指令"), "missing compact context rule");
assert(approvedHandoff.includes("Project Asset Next：Approved project asset next action."), "missing approved project-asset next action");
assert(approvedHandoff.includes("Project Asset Stop：Stop if execution needs write authority."), "missing approved project-asset stop condition");
assert(approvedHandoff.includes("Agent 待办：Run the read-only map dry-run after owner todo resolution."), "missing approved agent todo");
assert(approvedHandoff.includes("operator gate 已记录为 approve"), "missing approved forwarding condition");
assert(approvedHandoff.includes("只执行下面命令"), "missing execution boundary");
assert(approvedHandoff.includes("loopx read-only-map --goal-id planned-main-control --dry-run --approved"), "missing approved command");
assert(!approvedHandoff.includes("【GH Packet】"), "handoff-only payload must not include packet wrapper");
assert(!approvedHandoff.includes("【用户/Gate】"), "handoff-only payload must not include user gate wrapper");
assert(!approvedHandoff.includes("建议："), "handoff-only payload must not include human suggestion text");

const legacyFallbackPacket = buildActionPacket({
  goalId: "legacy-status-only",
  title: "Legacy status",
  summary: "raw status says continue but no project_asset is present",
  userTodoText: null,
  agentTodoText: "Inspect status only; do not treat raw fields as owner-approved state.",
  todoBlocksGate: false,
  operatorQuestion: null,
  suggestedReply: "保持 status inspection；补 project_asset 后再恢复 delivery。",
  gateFallbackDecision: "保持 status inspection；补 project_asset 后再恢复 delivery。",
  boundary: "This is a legacy/raw fallback; do not infer owner, gate, or stop condition authority.",
  safePathLabel: "Legacy status inspection",
  command: "loopx diagnose --goal-id legacy-status-only --limit 20",
  projectNextAction: "Continue from raw status field.",
  projectStopCondition: "Stop before any delivery claim.",
  projectAssetSource: "legacy_raw_fallback",
});

assert(legacyFallbackPacket.includes("Project Asset：legacy/raw fallback"), "missing legacy/raw fallback source");
assert(legacyFallbackPacket.includes("Owner/Gate/Stop 未确认"), "missing fallback untrusted-owner cue");
assert(legacyFallbackPacket.includes("Fallback Next：Continue from raw status field."), "missing fallback next label");
assert(legacyFallbackPacket.includes("Fallback Stop：Stop before any delivery claim."), "missing fallback stop label");
assert(!legacyFallbackPacket.includes("Project Asset：Owner="), "fallback packet must not claim owner/gate authority");

const focusWaitPacket = buildActionPacket({
  goalId: "focus-wait-owner-blocker",
  title: "Focus wait owner blocker",
  summary: "quiet until owner evidence, a clean baseline, or external eval changes",
  userTodoText: "Provide new owner evidence, a clean baseline, or external eval before delivery resumes.",
  agentTodoText: "只检查当前 state/status/history；保持 focus_wait 并用中文回报仍在等待什么。",
  todoBlocksGate: false,
  operatorQuestion: null,
  suggestedReply: "继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。",
  gateFallbackDecision: "继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。",
  boundary: "这不是 delivery approval；项目 Agent 只做 status/history inspection，不执行交付路径、写入、reward append 或生产动作。",
  safePathLabel: "Status/history inspection only",
  command: "loopx --registry ./examples/registry.example.json --runtime-root ./tmp/runtime diagnose --goal-id focus-wait-owner-blocker --limit 20",
});

assert(focusWaitPacket.includes("目标：focus-wait-owner-blocker"), "missing focus-wait goal id");
assert(focusWaitPacket.includes("待办：Provide new owner evidence"), "missing owner blocker unlock condition");
assert(focusWaitPacket.includes("Gate：无；建议：继续保持 focus wait"), "missing focus-wait fallback decision");
assert(focusWaitPacket.includes("Status/history inspection only"), "missing status/history-only safe path");
assert(focusWaitPacket.includes("保持 focus_wait"), "missing agent focus-wait boundary");
assert(!focusWaitPacket.includes("operator-gate"), "focus-wait packet must not draft an operator gate");
assert(!focusWaitPacket.includes("read-only-map"), "focus-wait packet must not expose a delivery map command");

const platformMigrationNoEvidencePacket = buildActionPacket({
  goalId: "platform-migration-material-registry",
  title: "Let Codex continue",
  summary: "Refreshed public-safe no-evidence projection gives Codex a usable next action.",
  userTodoText: "Confirm whether owner review is fresh enough to resume delivery.",
  agentTodoText: "Run read-only map and report material freshness without internal links.",
  todoBlocksGate: false,
  operatorQuestion: null,
  suggestedReply: "继续 no-evidence projection；不授权读取私有证据、写入或生产动作。",
  gateFallbackDecision: "继续 no-evidence projection；不授权读取私有证据、写入或生产动作。",
  boundary: "Use only sanitized status/history/material counts; do not read private evidence, internal links, raw paths, or production state.",
  durableRecordRule: null,
  safePathLabel: "No-evidence status/packet sanity",
  command: "loopx diagnose --goal-id platform-migration-material-registry --limit 20",
  quotaShortLine: "Eligible; 0/1440 slots",
  authorityShortLine: "entries 0/3; topics 3; materials 6; repos 2; owner review 1; stale 1; risk medium",
  projectOwner: "codex",
  projectGate: "none",
  projectNextAction: "Refresh the public-safe material registry summary.",
  projectStopCondition: "stop if the next action needs reward, gate approval, write control, or production access",
  projectAssetSource: "project_asset",
  handoffReadinessLine: "ready; codex_ready=true; source=project_asset; quota=eligible; failed=none",
});

assert(platformMigrationNoEvidencePacket.includes("目标：platform-migration-material-registry"), "missing platform migration target");
assert(platformMigrationNoEvidencePacket.includes("Project Asset：Owner=codex；Gate=none"), "missing platform project asset owner/gate");
assert(platformMigrationNoEvidencePacket.includes("Next：Refresh the public-safe material registry summary."), "missing platform next action");
assert(platformMigrationNoEvidencePacket.includes("Stop：stop if the next action needs reward"), "missing platform stop condition");
assert(platformMigrationNoEvidencePacket.includes("Handoff：ready; codex_ready=true; source=project_asset; quota=eligible; failed=none"), "missing platform handoff readiness");
assert(platformMigrationNoEvidencePacket.includes("Quota：Eligible; 0/1440 slots"), "missing platform quota context");
assert(platformMigrationNoEvidencePacket.includes("Authority：entries 0/3; topics 3; materials 6; repos 2; owner review 1; stale 1; risk medium"), "missing platform material context");
assert(platformMigrationNoEvidencePacket.includes("待办：Confirm whether owner review is fresh enough to resume delivery."), "missing platform user todo");
assert(platformMigrationNoEvidencePacket.includes("待办：Run read-only map and report material freshness without internal links."), "missing platform agent todo");
assert(platformMigrationNoEvidencePacket.includes("Gate：无；建议：继续 no-evidence projection"), "missing no-evidence non-gate cue");
assert(platformMigrationNoEvidencePacket.includes("No-evidence status/packet sanity"), "missing platform safe path");
assert(!platformMigrationNoEvidencePacket.includes("legacy/raw fallback"), "project-asset-backed platform packet must not fall back to raw status");
assert(!platformMigrationNoEvidencePacket.includes("不授权写入或生产动作") || platformMigrationNoEvidencePacket.includes("Gate：无"), "platform safety text must remain non-gated");

const dashboardPageSource = readFileSync("src/views/dashboard-page.tsx", "utf8");
const firstScreenRequiredSource = [
  "const quota = projectAsset?.quota ?? row.queueItem?.quota ?? row.goal.quota",
  "const nextAction = projectAsset?.next_action ?? decision.action",
  "const stopCondition = projectAsset?.stop_condition ?? handoffCondition ?? decision.action",
  "const handoffReadiness = row.queueItem?.handoff_readiness",
  "buildHandoffReadinessView(item.handoffReadiness)",
  "function HandoffReadinessPanel({",
  "data-testid={testId}",
  "testId=\"selected-queue-handoff-readiness\"",
  "goalId={queueItem.goal_id}",
  "const userTodos = todosFromProjectAssetSummary(projectAsset?.user_todos",
  "const agentTodos = todosFromProjectAssetSummary(projectAsset?.agent_todos",
  "<Badge variant=\"neutral\">Project asset</Badge>",
  "Handoff readiness:",
  "Handoff state:",
  "Post-handoff run:",
  "Failed checks:",
  "Owner/Gate/Stop are not project_asset-backed; below uses raw status fallback.",
  "<span className=\"font-medium\">{buildQuotaView(item.quota)?.shortLine}</span>",
];
for (const snippet of firstScreenRequiredSource) {
  assert(dashboardPageSource.includes(snippet), `React User Actions source drifted: ${snippet}`);
}

console.log(`action-packet smoke ok (${packet.length} chars, handoff ${approvedHandoff.length} chars, legacy ${legacyFallbackPacket.length} chars, focus ${focusWaitPacket.length} chars)`);
