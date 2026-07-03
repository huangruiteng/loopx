// @ts-expect-error The smoke compiler intentionally runs without @types/node.
import { readFileSync } from "node:fs";

function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

function includes(source: string, snippet: string, label: string) {
  assert(source.includes(snippet), `missing ${label}: ${snippet}`);
}

function excludes(source: string, snippet: string, label: string) {
  assert(!source.includes(snippet), `unexpected ${label}: ${snippet}`);
}

const statusSource = readFileSync("src/data/status.ts", "utf8");
const dashboardSource = readFileSync("src/views/dashboard-page.tsx", "utf8");
const packageSource = readFileSync("package.json", "utf8");
const exampleStatus = readFileSync("../../examples/status.example.json", "utf8");
const promotionGateWarningFixture = readFileSync("../../examples/dashboard-promotion-gate-warning-status.json", "utf8");
const contractSource = readFileSync("../../docs/status-data-contract.md", "utf8");
const promotionGateWarningStatus = JSON.parse(promotionGateWarningFixture);

for (const [field, label] of [
  ["progress_signal_run_count_24h", "24h progress signal field"],
  ["progress_signal_run_count_7d", "7d progress signal field"],
] as const) {
  includes(statusSource, `${field}: z.number().optional().default(0)`, `schema ${label}`);
  includes(statusSource, `${field}: 0`, `default totals ${label}`);
  includes(exampleStatus, `"${field}"`, `example ${label}`);
  includes(contractSource, field, `contract ${label}`);
}

for (const [field, label] of [
  ["status_contract", "status contract payload field"],
  ["schema_version", "status contract schema version"],
  ["reload_hint", "status contract daemon reload hint"],
  ["event_ledger_summary", "event ledger summary payload field"],
  ["by_class_24h", "24h event class counts"],
  ["by_class_7d", "7d event class counts"],
  ["latest_event_class", "latest event class"],
] as const) {
  includes(statusSource, field, `schema ${label}`);
  includes(exampleStatus, `"${field}"`, `example ${label}`);
  includes(contractSource, field, `contract ${label}`);
}

for (const [field, label] of [
  ["decision_freshness_summary", "decision freshness payload field"],
  ["requires_decision_point_rebase", "decision point rebase guard"],
  ["newer_event_count_7d", "newer event count"],
] as const) {
  includes(statusSource, field, `schema ${label}`);
  includes(exampleStatus, `"${field}"`, `example ${label}`);
  includes(contractSource, field, `contract ${label}`);
}

for (const [field, label] of [
  ["promotion_readiness_summary", "promotion readiness payload field"],
  ["promotion_gate", "promotion gate payload field"],
  ["can_promote", "promotion gate promote decision"],
  ["should_warn", "promotion gate warning decision"],
  ["requires_readiness_run", "promotion readiness rerun guard"],
  ["freshness_window_hours", "promotion readiness freshness window"],
] as const) {
  includes(statusSource, field, `schema ${label}`);
  includes(exampleStatus, `"${field}"`, `example ${label}`);
  includes(contractSource, field, `contract ${label}`);
}

assert(
  promotionGateWarningStatus.promotion_gate.gate_state === "warning",
  "promotion gate warning fixture gate_state",
);
assert(
  promotionGateWarningStatus.promotion_gate.can_promote === false,
  "promotion gate warning fixture can_promote",
);
assert(
  promotionGateWarningStatus.promotion_gate.should_warn === true,
  "promotion gate warning fixture should_warn",
);
assert(
  promotionGateWarningStatus.promotion_gate.readiness.freshness_status === "missing",
  "promotion gate warning fixture freshness",
);
includes(
  promotionGateWarningFixture,
  "python3 examples/canary/canary-promotion-readiness-smoke.py",
  "promotion gate warning fixture recommended action",
);

includes(
  packageSource,
  "dashboard-promotion-readiness-browser-smoke.mjs",
  "canonical promotion readiness browser smoke script",
);
excludes(
  packageSource,
  "dashboard-promotion-readiness-smoke.mjs",
  "stale promotion readiness browser smoke script",
);

for (const [snippet, label] of [
  ["<UsageMetric", "usage metric component"],
  ["label=\"Progress\"", "progress metric label"],
  ["value={`${formatUsageCount(totals.progress_signal_run_count_24h)} / ${formatUsageCount(totals.progress_signal_run_count_7d)}`}", "progress metric value"],
  ["xl:grid-cols-5", "five-column metric grid"],
  ["<div className=\"text-right\">Progress</div>", "top-goal progress header"],
  ["goal.progress_signal_run_count_24h", "top-goal 24h progress value"],
  ["grid-cols-[minmax(0,1fr)_70px_70px_80px_80px]", "five-column top-goal grid"],
] as const) {
  includes(dashboardSource, snippet, label);
}

for (const [snippet, label] of [
  ["<EventLedgerSummaryPanel summary={payload.event_ledger_summary} />", "ops event ledger panel"],
  ["<PromotionReadinessSummaryPanel summary={payload.promotion_readiness_summary} />", "ops promotion readiness panel"],
  ["<PromotionGatePanel gate={payload.promotion_gate} />", "ops promotion gate panel"],
  ["<DecisionFreshnessSummaryPanel summary={payload.decision_freshness_summary} />", "ops decision freshness panel"],
  ["function ShareEventLedgerStrip", "share event ledger strip"],
  ["控制面事件账本", "Chinese event ledger title"],
  ["Chat thread 不是 source of truth", "source-of-truth copy"],
  ["eventClassLabel", "event class label map"],
  ["花费记录", "accounting label"],
  ["人类决策", "decision label"],
  ["证据观察", "evidence label"],
  ["状态刷新", "state label"],
  ["实际推进", "work label"],
  ["function ShareDecisionFreshnessWarning", "share decision freshness warning"],
  ["function DecisionFreshnessSummaryPanel", "ops decision freshness component"],
  ["function PromotionReadinessSummaryPanel", "ops promotion readiness component"],
  ["function PromotionGatePanel", "ops promotion gate component"],
  ["Promotion gate", "promotion gate panel title"],
  ["Promotion readiness", "promotion readiness panel title"],
  ["安装器日志都不是 source of truth", "promotion source-of-truth copy"],
  ["决策 freshness", "Chinese decision freshness panel title"],
  ["exact replay 仍回到 append-only run history", "exact replay source-of-truth copy"],
  ["当前样本里没有需要 rebase 的 checkpointed decision", "empty decision freshness copy"],
  ["决策需 rebase", "Chinese decision rebase warning title"],
  ["这不是仓库回滚", "Chinese non-rollback copy"],
  ["shareDecisionFreshnessById(payload.decision_freshness_summary)", "share freshness grouping"],
] as const) {
  includes(dashboardSource, snippet, label);
}

console.log("usage-progress smoke ok");
