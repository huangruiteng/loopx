import type { CapabilityConfigurationCatalog } from "../../data/chat";
import type { WorkspaceLocale } from "./i18n";

type CapabilityDescriptor = CapabilityConfigurationCatalog["capabilities"][number];
type LocalizedCopy = Readonly<{
  description: string;
  displayName: string;
  readOnlyReason?: string;
}>;

type FieldCopy = Record<string, Readonly<{ description?: string; label: string }>>;

const capabilityCopy: Record<WorkspaceLocale, Record<string, LocalizedCopy>> = {
  en: {
    todo_replan_cadence: { displayName: "Goal review cadence", description: "Configures the Goal review cadence." },
    change_quality_qualification: {
      displayName: "Change quality qualification",
      description: "Prepares a provider-neutral review packet, allows at most one policy-authorized safe-fix pass, and can require an exact-diff receipt.",
    },
    explore_graph: {
      displayName: "Explore Graph",
      description: "Organizes bounded exploration as a typed evidence graph so branches, findings, and synthesis remain inspectable.",
    },
    explore_harness: {
      displayName: "Explore Harness",
      description: "Selects a capability-owned planning and research harness profile for bounded multi-step exploration.",
    },
    lark_event_inbox: {
      displayName: "Lark event inbox",
      description: "Receives provider events through a local-private inbox binding before LoopX projects them into governed work.",
      readOnlyReason: "This capability requires a local-private inbox binding. Manage it in Lark settings or through the capability CLI.",
    },
    lark_kanban_heartbeat_sync: {
      displayName: "Lark Kanban heartbeat sync",
      description: "Synchronizes accepted LoopX work state to the configured Lark Kanban heartbeat surface.",
    },
    local_authority_shadow: {
      displayName: "Local authority shadow",
      description: "Observes post-commit Todo and task-lease state through the shared authority contract without taking write authority.",
    },
    multi_subagent: {
      displayName: "Adaptive child capacity",
      description: "Sets bounded child-agent capacity and the public-safe responsibility domains in which parallel work may be delegated.",
    },
    peer_task_coordination: {
      displayName: "Registered-peer task coordination",
      description: "Routes explicitly scoped peer-owned work to one registered coordinator without granting cross-owner mutation authority.",
    },
    periodic_report: {
      displayName: "Periodic reports",
      description: "Turns validated Goal stage progress into a frozen report and automatically delivers it through the configured Goal Channel with exact readback.",
    },
    reward_memory: {
      displayName: "Reward Memory experiment",
      description: "Runs an opt-in, provider-bound retrieval experiment over an explicitly allowlisted memory corpus.",
      readOnlyReason: "This capability requires a reviewed local-private provider binding and an explicit Agent allowlist. Configure it through the capability CLI.",
    },
  },
  "zh-CN": {
    todo_replan_cadence: { displayName: "Goal 复核周期", description: "配置 Goal 的复核周期。" },
    change_quality_qualification: {
      displayName: "变更质量验证",
      description: "生成与 Provider 无关的审阅包，最多允许一次策略授权的安全修复，并可要求精确 diff 回执。",
    },
    explore_graph: {
      displayName: "探索图谱",
      description: "把有界探索组织为 typed 证据图，让探索分支、发现与综合结论都可检查、可追溯。",
    },
    explore_harness: {
      displayName: "探索 Harness",
      description: "为有界的多步探索选择由能力负责的规划与研究 Harness profile。",
    },
    lark_event_inbox: {
      displayName: "飞书事件收件箱",
      description: "通过本机私有收件箱接收 Provider 事件，再由 LoopX 将其投影为受治理的工作。",
      readOnlyReason: "此能力依赖本机私有的收件箱绑定，请在飞书设置或 capability CLI 中管理。",
    },
    lark_kanban_heartbeat_sync: {
      displayName: "飞书看板心跳同步",
      description: "把 LoopX 已接受的工作状态同步到配置好的飞书看板心跳界面。",
    },
    local_authority_shadow: {
      displayName: "本地 Authority 影子观测",
      description: "通过共享 Authority contract 观测提交后的 Todo 与 task lease 状态，但不取得写入权。",
    },
    multi_subagent: {
      displayName: "自适应子 Agent 容量",
      description: "限定子 Agent 容量与可公开的职责域，只有落在这些边界内的工作才能并行委派。",
    },
    peer_task_coordination: {
      displayName: "已注册 Peer 任务协调",
      description: "把明确限定的 Peer 工作路由给一个已注册协调者，不授予跨 Owner 修改权限。",
    },
    periodic_report: {
      displayName: "周期报告",
      description: "把经过验证的 Goal 阶段进展整理为冻结报告，并通过配置的 Goal Channel 自动发送和精确回读。",
    },
    reward_memory: {
      displayName: "Reward Memory 实验",
      description: "在明确 allowlist 的记忆语料上运行可选、Provider 绑定的检索实验。",
      readOnlyReason: "此能力依赖经过审阅的本机私有 Provider 绑定和明确的 Agent allowlist，请通过 capability CLI 配置。",
    },
  },
};

const fieldCopy: Record<WorkspaceLocale, FieldCopy> = {
  en: {
    allowed_domains: { label: "Allowed responsibility domains", description: "Enter one bounded, public-safe domain per line." },
    coordinator_agent_id: { label: "Coordinator Agent", description: "Use an already registered Agent id; leave blank to disable coordination." },
    enabled: { label: "Enabled" },
    max_children: { label: "Maximum children", description: "Hard upper bound for concurrently delegated child work." },
    profile: { label: "Planner profile", description: "Select one registered Explore Harness profile." },
    profile_preset: { label: "Report profile", description: "Capability-owned report profile, such as weekly-progress." },
    route_ref: { label: "Goal Channel route", description: "Public route alias only; credentials and provider identifiers stay outside this form." },
    safe_fix: { label: "Allow one bounded safe-fix pass" },
    strict_receipt: { label: "Require an exact-diff receipt" },
    timezone: { label: "Timezone", description: "Use an IANA timezone, for example Asia/Shanghai." },
  },
  "zh-CN": {
    allowed_domains: { label: "允许的职责域", description: "每行填写一个有边界、可公开的职责域。" },
    coordinator_agent_id: { label: "协调 Agent", description: "填写一个已经注册的 Agent ID；留空表示关闭协调。" },
    enabled: { label: "启用" },
    max_children: { label: "最大子 Agent 数", description: "可同时委派的子任务硬上限。" },
    profile: { label: "规划 Profile", description: "选择一个已注册的 Explore Harness profile。" },
    profile_preset: { label: "报告 Profile", description: "由该能力管理的报告 profile，例如 weekly-progress。" },
    route_ref: { label: "Goal Channel 路由", description: "只填写公开 route alias；凭据与 Provider 标识不会进入此表单。" },
    safe_fix: { label: "允许一次有界安全修复" },
    strict_receipt: { label: "要求精确 diff 回执" },
    timezone: { label: "时区", description: "使用 IANA 时区，例如 Asia/Shanghai。" },
  },
};

export function localizeCapability(
  capability: CapabilityDescriptor,
  locale: WorkspaceLocale,
): CapabilityDescriptor {
  const copy = capabilityCopy[locale][capability.capability_id];
  if (!copy) return capability;
  return {
    ...capability,
    display_name: copy.displayName,
    description: copy.description,
    configuration_editor: {
      ...capability.configuration_editor,
      ...(copy.readOnlyReason ? { read_only_reason: copy.readOnlyReason } : {}),
    },
  };
}

export function localizedCapabilityFieldCopy(locale: WorkspaceLocale): FieldCopy {
  return fieldCopy[locale];
}

export const localizedCapabilityIds = Object.freeze(Object.keys(capabilityCopy.en).sort());
