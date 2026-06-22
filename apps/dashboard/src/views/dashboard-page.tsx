import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  CircleAlert,
  Copy,
  Clock3,
  FileCheck2,
  FileJson2,
  FileText,
  Gauge,
  GitBranch,
  History,
  Link2,
  LayoutDashboard,
  Moon,
  Upload,
  Radar,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sun,
  Terminal,
  Users,
} from "lucide-react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";

import { dashboardRoute } from "../router";
import {
  QueueItem,
  AuthorityRegistry,
  ComputeQuota,
  ControlPlanePolicy,
  ControllerReadiness,
  GlobalRegistryHealth,
  HumanReward,
  OperatorGate,
  OperatorGateResumeContract,
  ProjectMap,
  ReviewMaterial,
  RewardDryRunResponse,
  RunGoal,
  RunRecord,
  OrchestrationPolicy,
  StatusPayload,
  ProjectAssetLatestValidation,
  ProjectAssetHandoffReadiness,
  ProjectAssetTodoSummary,
  TodoItem,
  TodoGroup,
  TodoIndexSummary,
  EventLedgerSummary,
  PromotionReadinessSummary,
  PromotionGate,
  DecisionFreshnessItem,
  DecisionFreshnessSummary,
  UsageSummary,
  exampleStatusPayload,
  formatStatusError,
  parseRewardDryRunResponse,
  parseStatusPayload,
} from "../data/status";
import { buildActionPacket, buildApprovedAgentHandoff, ProjectAssetSource } from "../data/action-packet";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select } from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { cn } from "../lib/utils";

type LaneKey = "user" | "codex" | "watch";

type LaneDefinition = {
  key: LaneKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  waitingOn: readonly string[];
  accent: string;
};

const laneConfig: LaneDefinition[] = [
  {
    key: "user",
    label: "User / Controller",
    icon: Users,
    waitingOn: ["user_or_controller", "controller"],
    accent: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100",
  },
  {
    key: "codex",
    label: "Codex Ready",
    icon: Bot,
    waitingOn: ["codex"],
    accent: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
  },
  {
    key: "watch",
    label: "Watching Evidence",
    icon: Radar,
    waitingOn: ["external_evidence"],
    accent: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-100",
  },
];

const severityVariant: Record<string, "neutral" | "success" | "warning" | "info" | "danger"> = {
  high: "danger",
  action: "warning",
  watch: "info",
};

const waitingLabel: Record<string, string> = {
  user_or_controller: "User / Controller",
  controller: "Controller",
  codex: "Codex",
  external_evidence: "Evidence",
};

const lifecycleLabel: Record<string, string> = {
  connected: "Connected",
  mapped: "Mapped",
  refreshed: "Refreshed",
  adapter_inspected: "Adapter inspected",
  reward_judged: "Reward judged",
  operator_approved: "Operator approved",
  operator_gated: "Operator gated",
  controller_gated: "Controller gated",
  controller_ready: "Controller ready",
  registered: "Registered",
  planned: "Planned",
  run_recorded: "Run recorded",
};

const lifecycleVariant: Record<string, "neutral" | "success" | "warning" | "info" | "danger"> = {
  connected: "neutral",
  mapped: "info",
  refreshed: "warning",
  adapter_inspected: "info",
  reward_judged: "success",
  operator_approved: "success",
  operator_gated: "warning",
  controller_gated: "warning",
  controller_ready: "success",
  registered: "neutral",
  planned: "warning",
  run_recorded: "neutral",
};

type DataSource =
  | { kind: "example"; label: "bundled example" }
  | { kind: "url"; label: string }
  | { kind: "file"; label: string };

const defaultLiveStatusUrl = "http://127.0.0.1:8765/status.json";
const defaultGlobalStatusUrl = "http://127.0.0.1:8766/status.json";
const expectedStatusContractSchemaVersion = 2;
const fallbackStatusContractReloadHint = "scripts/macos-dashboard-launchagent.sh restart";
const rewardOptions = ["positive", "mixed", "neutral", "negative"] as const;
const inputClassName =
  "h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:ring-zinc-500";

type RewardValue = (typeof rewardOptions)[number];

function routeViewForUrl(view?: "ops" | "share") {
  return view === "ops" ? "ops" : undefined;
}

function currentRouteView(current: { view?: "ops" | "share" } | {}) {
  return "view" in current ? current.view : undefined;
}

function isLoopbackUrl(value: string) {
  try {
    const url = new URL(value);
    return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname);
  } catch {
    return false;
  }
}

function statusContractFreshnessIssue(payload: StatusPayload, source: DataSource) {
  if (source.kind !== "url" || !isLoopbackUrl(source.label)) {
    return null;
  }
  const schemaVersion = payload.status_contract.schema_version ?? 0;
  if (schemaVersion >= expectedStatusContractSchemaVersion) {
    return null;
  }
  return {
    reloadHint: payload.status_contract.reload_hint || fallbackStatusContractReloadHint,
    schemaVersion,
  };
}

function StatusContractFreshnessWarning({
  payload,
  source,
}: {
  payload: StatusPayload;
  source: DataSource;
}) {
  const issue = statusContractFreshnessIssue(payload, source);
  if (!issue) {
    return null;
  }
  return (
    <div
      className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 shadow-sm dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"
      data-testid="status-contract-freshness-warning"
    >
      <div className="flex flex-wrap items-center gap-2 font-semibold">
        <CircleAlert className="h-4 w-4" />
        状态服务契约过旧
        <Badge variant="warning">schema v{issue.schemaVersion}</Badge>
      </div>
      <p className="mt-1">
        这个 loopback live feed 低于 dashboard 期望的 schema v{expectedStatusContractSchemaVersion}；
        可能是 `127.0.0.1:8766` 仍在运行旧 daemon。演示前运行
        <span className="mx-1 font-mono">{issue.reloadHint}</span>
        后刷新页面。
      </p>
    </div>
  );
}

type RewardRequestBody = {
  goal_id: string;
  run_generated_at: string;
  decision: string;
  reward: RewardValue;
  reason_summary: string;
  follow_up?: string;
  recorded_at?: string;
};

type ReviewMaterialContent = {
  ok: boolean;
  goal_id?: string;
  path?: string;
  resolved_path?: string;
  bytes?: number;
  content?: string;
  error?: string;
};

type GoalDirectoryRow = {
  goal: RunGoal;
  queueItem?: QueueItem;
  latestRun?: RunRecord;
  status: string;
  waitingOn: string;
  severity: string;
  lifecyclePhase: string;
  lifecycleFlags: string[];
};

type TodoFocusItem = {
  goalId: string;
  role: "user" | "agent";
  text: string;
  openCount: number;
  totalCount: number;
  severity: string;
  waitingOn: string;
  phase: string;
  priority: number;
};

type TodoExplorerRole = "user" | "agent";

type TodoExplorerItem = {
  goalId: string;
  role: TodoExplorerRole;
  todo: TodoItem;
  sourceSection: string;
  source: string;
  openCount: number;
  totalCount: number;
  severity: string;
  waitingOn: string;
  phase: string;
  sourceOrder: number;
};

function laneFor(item: QueueItem) {
  return laneConfig.find((lane) => lane.waitingOn.includes(item.waiting_on));
}

function ShortText({ children }: { children: string }) {
  return <span className="line-clamp-2 break-words">{children}</span>;
}

function StatusBadge({ value }: { value: string }) {
  return <Badge variant={severityVariant[value] ?? "neutral"}>{value}</Badge>;
}

function inferLifecyclePhase(status?: string | null, run?: RunRecord) {
  if (run?.controller_readiness?.decision_advisor_ready || run?.controller_readiness?.write_controller_ready) {
    return "controller_ready";
  }
  if (run?.controller_readiness) {
    return "controller_gated";
  }
  if (run?.human_reward) {
    return "reward_judged";
  }
  if (run?.operator_gate?.decision === "approve") {
    return "operator_approved";
  }
  if (run?.operator_gate) {
    return "operator_gated";
  }
  const value = status || run?.classification || "";
  if (value === "connected_without_run") {
    return "connected";
  }
  if (value === "read_only_project_map" || run?.project_map) {
    return "mapped";
  }
  if (value === "state_refreshed") {
    return "refreshed";
  }
  if (value && value !== "no_status") {
    return "adapter_inspected";
  }
  return "registered";
}

function normalizeLifecycle(primary?: string | null, flags?: string[]) {
  const cleanFlags = (flags ?? []).filter(Boolean);
  const phase = primary || cleanFlags[0] || "registered";
  const allFlags = cleanFlags.includes(phase) ? cleanFlags : [phase, ...cleanFlags];
  return {
    phase,
    flags: allFlags,
  };
}

function PhaseBadges({
  phase,
  flags,
  compact = false,
}: {
  phase?: string | null;
  flags?: string[];
  compact?: boolean;
}) {
  const normalized = normalizeLifecycle(phase, flags);
  const shown = compact ? [normalized.phase] : normalized.flags.slice(0, 3);
  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map((flag) => (
        <Badge key={flag} variant={lifecycleVariant[flag] ?? "neutral"}>
          {lifecycleLabel[flag] ?? flag}
        </Badge>
      ))}
      {!compact && normalized.flags.length > shown.length ? (
        <Badge variant="neutral">+{normalized.flags.length - shown.length}</Badge>
      ) : null}
    </div>
  );
}

function QueueGateSummary({ item, compact = false }: { item?: QueueItem; compact?: boolean }) {
  if (!item) {
    return null;
  }
  const gates = item.missing_gates ?? [];
  if (!item.controller_stage && gates.length === 0 && !item.next_handoff_condition) {
    return null;
  }
  return (
    <div className={cn("flex flex-wrap gap-1.5", compact ? "mt-1" : "mt-2")}>
      {item.controller_stage ? <Badge variant="info">{item.controller_stage}</Badge> : null}
      {gates.map((gate) => (
        <Badge key={gate} variant="warning">
          {gate}
        </Badge>
      ))}
      {item.next_handoff_condition && !compact ? (
        <span className="w-full text-xs leading-5 text-slate-500 dark:text-zinc-400">
          {item.next_handoff_condition}
        </span>
      ) : null}
    </div>
  );
}

function shellQuote(value: string) {
  if (/^[A-Za-z0-9_./:=@+-]+$/.test(value)) {
    return value;
  }
  return `'${value.replace(/'/g, "'\"'\"'")}'`;
}

function buildRewardCommand({
  goalId,
  registry,
  runtimeRoot,
  runGeneratedAt,
  decision,
  reward,
  reasonSummary,
  followUp,
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
  runGeneratedAt: string;
  decision: string;
  reward: RewardValue;
  reasonSummary: string;
  followUp: string;
}) {
  const lines = [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  reward \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    `  --run-generated-at ${shellQuote(runGeneratedAt)} \\`,
    `  --decision ${shellQuote(decision || "decision_label")} \\`,
    `  --reward ${shellQuote(reward)} \\`,
    `  --reason-summary ${shellQuote(reasonSummary || "public_safe_reason")} \\`,
  ];
  if (followUp.trim()) {
    lines.push(`  --follow-up ${shellQuote(followUp.trim())} \\`);
  }
  lines.push("  --write-active-state-summary \\");
  lines.push("  --dry-run");
  return lines.join("\n");
}

function buildRewardApiUrls(source: DataSource) {
  if (source.kind !== "url" || !/^https?:\/\//i.test(source.label)) {
    return { dryRunUrl: null, appendUrl: null };
  }
  try {
    const url = new URL(source.label);
    const isLoopback = ["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname);
    return isLoopback
      ? { dryRunUrl: `${url.origin}/reward/dry-run`, appendUrl: `${url.origin}/reward/append` }
      : { dryRunUrl: null, appendUrl: null };
  } catch {
    return { dryRunUrl: null, appendUrl: null };
  }
}

function localApiUrl(source: DataSource, path: string | null | undefined) {
  if (!path || source.kind !== "url" || !/^https?:\/\//i.test(source.label)) {
    return null;
  }
  try {
    const sourceUrl = new URL(source.label);
    const targetUrl = new URL(path, sourceUrl.origin);
    const isLoopback = ["127.0.0.1", "localhost", "::1", "[::1]"].includes(targetUrl.hostname);
    return isLoopback ? targetUrl.toString() : null;
  } catch {
    return null;
  }
}

function buildControlPlaneApiUrls(source: DataSource, payload?: StatusPayload) {
  const localApi = payload?.local_dashboard_api;
  if (localApi) {
    return {
      dryRunUrl: localApiUrl(source, localApi.configure_goal_dry_run_url),
      applyUrl: localApiUrl(source, localApi.configure_goal_apply_url),
      writeEnabled: Boolean(localApi.control_plane_write_enabled),
    };
  }
  if (source.kind !== "url" || !/^https?:\/\//i.test(source.label)) {
    return { dryRunUrl: null, applyUrl: null, writeEnabled: null };
  }
  try {
    const url = new URL(source.label);
    const isLoopback = ["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname);
    return isLoopback
      ? {
          dryRunUrl: `${url.origin}/control-plane/configure-goal/dry-run`,
          applyUrl: `${url.origin}/control-plane/configure-goal/apply`,
          writeEnabled: null,
        }
      : { dryRunUrl: null, applyUrl: null, writeEnabled: null };
  } catch {
    return { dryRunUrl: null, applyUrl: null, writeEnabled: null };
  }
}

function buildReviewMaterialUrl(source: DataSource, goalId: string, material: ReviewMaterial) {
  if (source.kind !== "url" || !/^https?:\/\//i.test(source.label) || !material.path) {
    return null;
  }
  try {
    const url = new URL(source.label);
    const isLoopback = ["127.0.0.1", "localhost", "::1", "[::1]"].includes(url.hostname);
    if (!isLoopback) {
      return null;
    }
    const materialUrl = new URL("/review-material", url.origin);
    materialUrl.searchParams.set("goal_id", goalId);
    materialUrl.searchParams.set("path", material.path);
    return materialUrl.toString();
  } catch {
    return null;
  }
}

function latestRunSortValue(run?: RunRecord) {
  return run?.generated_at ? Date.parse(run.generated_at) || 0 : 0;
}

function buildGoalDirectoryRows(goals: RunGoal[], queueItems: QueueItem[]) {
  const queueByGoal = new Map(queueItems.map((item) => [item.goal_id, item]));
  const seen = new Set<string>();
  const rows: GoalDirectoryRow[] = goals.map((goal) => {
    seen.add(goal.id);
    const queueItem = queueByGoal.get(goal.id);
    const latestRun = goal.latest_runs[0];
    const phase = queueItem?.lifecycle_phase
      ?? goal.lifecycle_phase
      ?? latestRun?.lifecycle_phase
      ?? inferLifecyclePhase(queueItem?.status ?? latestRun?.classification ?? goal.status, latestRun);
    const flags = queueItem?.lifecycle_flags?.length
      ? queueItem.lifecycle_flags
      : goal.lifecycle_flags?.length
        ? goal.lifecycle_flags
        : latestRun?.lifecycle_flags?.length
          ? latestRun.lifecycle_flags
          : [phase];
    return {
      goal,
      queueItem,
      latestRun,
      status: queueItem?.status ?? latestRun?.classification ?? goal.status ?? "no_status",
      waitingOn: queueItem?.waiting_on ?? "clear",
      severity: queueItem?.severity ?? "clear",
      lifecyclePhase: phase,
      lifecycleFlags: flags,
    };
  });

  for (const item of queueItems) {
    if (seen.has(item.goal_id)) {
      continue;
    }
    rows.push({
      goal: {
        id: item.goal_id,
        status: item.status,
        lifecycle_phase: item.lifecycle_phase ?? inferLifecyclePhase(item.status),
        lifecycle_flags: item.lifecycle_flags?.length ? item.lifecycle_flags : [item.lifecycle_phase ?? inferLifecyclePhase(item.status)],
        registry_member: false,
        legacy_runtime_goal: false,
        adapter_kind: null,
        adapter_status: null,
        index_exists: false,
        raw_index_records: 0,
        unique_runs: 0,
        latest_runs: [],
      },
      queueItem: item,
      status: item.status,
      waitingOn: item.waiting_on,
      severity: item.severity,
      lifecyclePhase: item.lifecycle_phase ?? inferLifecyclePhase(item.status),
      lifecycleFlags: item.lifecycle_flags?.length ? item.lifecycle_flags : [item.lifecycle_phase ?? inferLifecyclePhase(item.status)],
    });
  }

  const severityOrder: Record<string, number> = {
    high: 0,
    action: 1,
    watch: 2,
    clear: 3,
  };
  return rows.sort((a, b) => {
    const severityDelta = (severityOrder[a.severity] ?? 4) - (severityOrder[b.severity] ?? 4);
    if (severityDelta !== 0) {
      return severityDelta;
    }
    return latestRunSortValue(b.latestRun) - latestRunSortValue(a.latestRun);
  });
}

function GoalDirectory({
  rows,
  selectedGoalId,
  onSelectGoal,
}: {
  rows: GoalDirectoryRow[];
  selectedGoalId: string;
  onSelectGoal: (goalId: string) => void;
}) {
  const actionCount = rows.filter((row) => row.queueItem && row.waitingOn !== "external_evidence").length;
  const watchCount = rows.filter((row) => row.waitingOn === "external_evidence").length;
  const clearCount = rows.length - actionCount - watchCount;

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Goal Directory
          </CardTitle>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="warning">{actionCount} action</Badge>
          <Badge variant="info">{watchCount} watch</Badge>
          <Badge variant="success">{clearCount} clear</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
          <div className="divide-y divide-slate-200 dark:divide-zinc-800">
            {rows.map((row) => (
              <button
                className={cn(
                  "grid w-full gap-3 px-4 py-3 text-left transition hover:bg-slate-50 dark:hover:bg-zinc-900 md:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)_minmax(180px,0.7fr)]",
                  row.goal.id === selectedGoalId && "bg-slate-100 dark:bg-zinc-900",
                )}
                key={row.goal.id}
                onClick={() => onSelectGoal(row.goal.id)}
                type="button"
              >
                <div className="min-w-0">
                  <div className="break-all text-sm font-semibold text-slate-950 dark:text-zinc-50">{row.goal.id}</div>
                  <div className="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-zinc-400">
                    {row.goal.domain ?? "No domain"}
                  </div>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{row.status}</Badge>
                    {row.severity === "clear" ? <Badge variant="success">Clear</Badge> : <StatusBadge value={row.severity} />}
                    <QuotaChip quota={row.queueItem?.quota ?? row.goal.quota} />
                  </div>
                  <div className="mt-1">
                    <PhaseBadges compact flags={row.lifecycleFlags} phase={row.lifecyclePhase} />
                  </div>
                  <div className="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-zinc-400">
                    {row.waitingOn === "clear" ? "No attention item" : waitingLabel[row.waitingOn] ?? row.waitingOn}
                  </div>
                  <QueueGateSummary compact item={row.queueItem} />
                </div>
                <div className="min-w-0 md:text-right">
                  <div className="text-xs font-medium text-slate-500 dark:text-zinc-400">
                    {row.goal.unique_runs} runs · {row.goal.raw_index_records} records
                  </div>
                  <div className="mt-1 break-all text-xs text-slate-500 dark:text-zinc-400">
                    {row.latestRun?.generated_at ?? "No run yet"}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function QueueTable({
  items,
  selectedGoalId,
  onSelectGoal,
}: {
  items: QueueItem[];
  selectedGoalId: string;
  onSelectGoal: (goalId: string) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const columns = useMemo<ColumnDef<QueueItem>[]>(
    () => [
      {
        accessorKey: "goal_id",
        header: "Goal",
        cell: ({ row }) => (
          <button
            className="text-left font-medium text-slate-900 underline-offset-4 hover:underline dark:text-zinc-100"
            onClick={() => onSelectGoal(row.original.goal_id)}
            type="button"
          >
            {row.original.goal_id}
          </button>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <Badge>{row.original.status}</Badge>,
      },
      {
        accessorKey: "lifecycle_phase",
        header: "Phase",
        cell: ({ row }) => (
          <PhaseBadges
            compact
            flags={row.original.lifecycle_flags}
            phase={row.original.lifecycle_phase ?? inferLifecyclePhase(row.original.status)}
          />
        ),
      },
      {
        accessorKey: "waiting_on",
        header: "Waiting",
        cell: ({ row }) => waitingLabel[row.original.waiting_on] ?? row.original.waiting_on,
      },
      {
        accessorKey: "severity",
        header: "Severity",
        cell: ({ row }) => <StatusBadge value={row.original.severity} />,
      },
      {
        accessorKey: "quota",
        header: "Quota",
        cell: ({ row }) => <QuotaChip quota={row.original.quota} />,
      },
      {
        accessorKey: "recommended_action",
        header: "Action",
        cell: ({ row }) => (
          <div className="min-w-0">
            <ShortText>{row.original.recommended_action}</ShortText>
            <QueueGateSummary compact item={row.original} />
          </div>
        ),
      },
    ],
    [],
  );
  const table = useReactTable({
    data: items,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder ? null : (
                    <button
                      className="flex items-center gap-1 text-left"
                      onClick={header.column.getToggleSortingHandler()}
                      type="button"
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </button>
                  )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow
              className={cn(
                "cursor-pointer",
                row.original.goal_id === selectedGoalId && "bg-slate-100 dark:bg-zinc-900",
              )}
              key={row.id}
              onClick={() => onSelectGoal(row.original.goal_id)}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function formatNullable(value: unknown, fallback = "None") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function artifactVariant(value?: boolean) {
  return value ? "success" : "neutral";
}

function rewardVariant(value?: string | null): "success" | "danger" | "warning" | "info" {
  if (value === "positive") {
    return "success";
  }
  if (value === "negative") {
    return "danger";
  }
  if (value === "mixed") {
    return "warning";
  }
  return "info";
}

type BadgeVariant = "neutral" | "success" | "warning" | "info" | "danger";

type OperatorActionBridgeItem = {
  label: string;
  body: string;
  command?: string;
  variant?: BadgeVariant;
};

type OperatorActionBridge = {
  title: string;
  badge: string;
  variant: BadgeVariant;
  body: string;
  items: OperatorActionBridgeItem[];
};

type OperatorDecision = {
  title: string;
  badge: string;
  variant: BadgeVariant;
  action: string;
  reason: string;
  needs: string[];
  phase: string;
  waitingOn: string;
};

type RewardDraftDefaults = {
  decision: string;
  reward: RewardValue;
  reasonSummary: string;
  followUp: string;
  label: string;
};

type UserActionKind = "reward" | "controller" | "codex" | "evidence" | "health";
type UserActionFilter = "all" | UserActionKind;

type UserActionSummaryItem = {
  goalId: string;
  kind: UserActionKind;
  title: string;
  badge: string;
  variant: BadgeVariant;
  summary: string;
  detail: string;
  operatorQuestion?: string;
  agentCommand?: string;
  safePathLabel: string;
  safePathCommand?: string;
  rewardHint: string;
  authorityCoverage?: AuthorityCoverage;
  quota?: ComputeQuota | null;
  userTodos?: TodoGroup | null;
  agentTodos?: TodoGroup | null;
  latestValidation?: ProjectAssetLatestValidation | null;
  projectOwner?: string | null;
  projectGate?: string | null;
  projectNextAction?: string | null;
  projectStopCondition?: string | null;
  projectAssetSource: ProjectAssetSource;
  handoffReadiness?: ProjectAssetHandoffReadiness | null;
  phase: string;
  waitingOn: string;
  draftLabel?: string;
  priority: number;
};

const userActionKindOrder: UserActionKind[] = ["reward", "controller", "codex", "evidence", "health"];
const userActionKindConfig: Record<UserActionKind, { label: string; variant: BadgeVariant }> = {
  reward: { label: "Reward", variant: "warning" },
  controller: { label: "Controller", variant: "warning" },
  codex: { label: "Codex", variant: "success" },
  evidence: { label: "Evidence", variant: "info" },
  health: { label: "Health", variant: "danger" },
};

function firstOpenTodo(todos?: TodoGroup | null) {
  return todos?.items.find((item) => !item.done);
}

function todosFromProjectAssetSummary(
  summary?: ProjectAssetTodoSummary | null,
  fallback?: TodoGroup | null,
  sourceSection = "project_asset",
): TodoGroup | null {
  if (!summary) {
    return fallback ?? null;
  }
  const next = summary.next?.trim();
  const fallbackFirstOpen = firstOpenTodo(fallback);
  const summaryItems = (summary.items ?? []).filter((item) => !item.done && item.text?.trim());
  return {
    source_section: summary.source_section ?? fallback?.source_section ?? sourceSection,
    total_count: summary.total ?? fallback?.total_count ?? 0,
    open_count: summary.open ?? fallback?.open_count ?? 0,
    done_count: summary.done ?? fallback?.done_count ?? 0,
    items: fallback?.items?.length
      ? fallback.items
      : summaryItems.length
        ? summaryItems
      : (next
          ? [{
              index: summary.next_index ?? fallbackFirstOpen?.index ?? 1,
              done: false,
              text: next,
              review_materials: fallbackFirstOpen?.review_materials ?? [],
            }]
          : []),
  };
}

function todoCountLabel(todos?: TodoGroup | null) {
  if (!todos || todos.total_count === 0) {
    return null;
  }
  return `${todos.open_count}/${todos.total_count} open`;
}

type HandoffReadinessView = {
  ready: boolean;
  shortLine: string;
  stateLine: string;
  latestRunLine?: string | null;
  recentRunLine?: string | null;
  failedLabel: string;
  probe?: string | null;
  variant: BadgeVariant;
};

function buildHandoffReadinessView(readiness?: ProjectAssetHandoffReadiness | null): HandoffReadinessView | null {
  if (!readiness) {
    return null;
  }
  const checks = readiness.checks ?? {};
  const failed = Object.entries(checks)
    .filter(([, value]) => value === false)
    .map(([key]) => humanizeIdentifier(key));
  const failedLabel = failed.length ? failed.join(", ") : "none";
  const ready = Boolean(readiness.ready);
  const postRunSeen = Boolean(readiness.post_handoff_run_seen);
  const handoffStatus = readiness.handoff_status ?? (ready ? "ready_waiting_for_run" : "not_ready");
  const latestRun = readiness.post_handoff_latest_run;
  const recentScales = (readiness.post_handoff_recent_runs ?? [])
    .map((run) => run.delivery_batch_scale)
    .filter((scale): scale is string => Boolean(scale));
  return {
    ready,
    shortLine: [
      ready ? "ready" : "not ready",
      `codex_ready=${Boolean(readiness.codex_ready)}`,
      `source=${readiness.source ?? "unknown"}`,
      `quota=${readiness.quota_state ?? "unknown"}`,
      `failed=${failedLabel}`,
    ].join("; "),
    stateLine: [
      `status=${handoffStatus}`,
      `post_handoff_run_seen=${postRunSeen}`,
      readiness.handoff_ready_at ? `ready_at=${readiness.handoff_ready_at}` : null,
    ].filter(Boolean).join("; "),
    latestRunLine: latestRun
      ? [
        latestRun.classification ?? "unknown",
        latestRun.generated_at ? `at=${latestRun.generated_at}` : null,
        latestRun.delivery_batch_scale ? `scale=${latestRun.delivery_batch_scale}` : null,
        latestRun.json_exists !== undefined ? `json=${Boolean(latestRun.json_exists)}` : null,
        latestRun.markdown_exists !== undefined ? `markdown=${Boolean(latestRun.markdown_exists)}` : null,
      ].filter(Boolean).join("; ")
      : null,
    recentRunLine: recentScales.length
      ? [
        recentScales.join(","),
        `small_streak=${readiness.post_handoff_small_scale_streak ?? 0}`,
      ].join("; ")
      : null,
    failedLabel,
    probe: readiness.next_probe,
    variant: postRunSeen ? "info" : ready ? "success" : "warning",
  };
}

function HandoffReadinessPanel({
  goalId,
  readiness,
  testId = "handoff-readiness-panel",
}: {
  goalId?: string;
  readiness?: ProjectAssetHandoffReadiness | null;
  testId?: string;
}) {
  const view = buildHandoffReadinessView(readiness);
  if (!view) {
    return null;
  }
  return (
    <div
      className={cn(
        "mt-3 rounded-lg border p-3 text-xs leading-5",
        view.ready
          ? "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100"
          : "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100",
      )}
      data-goal-id={goalId}
      data-testid={testId}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={view.variant}>{view.ready ? "Handoff ready" : "Handoff blocked"}</Badge>
        <span className="break-words font-medium">{view.shortLine}</span>
      </div>
      <p className="mt-2 break-words">
        <span className="font-medium">Failed checks:</span> {view.failedLabel}
      </p>
      <p className="mt-1 break-words">
        <span className="font-medium">Handoff state:</span> {view.stateLine}
      </p>
      {view.latestRunLine ? (
        <p className="mt-1 break-words">
          <span className="font-medium">Post-handoff run:</span> {view.latestRunLine}
        </p>
      ) : null}
      {view.recentRunLine ? (
        <p className="mt-1 break-words">
          <span className="font-medium">Recent scales:</span> {view.recentRunLine}
        </p>
      ) : null}
      {view.probe ? (
        <p className="mt-1 break-words">
          <span className="font-medium">Probe:</span> {view.probe}
        </p>
      ) : null}
    </div>
  );
}

function todoFocusPriority({
  role,
  severity,
  waitingOn,
  phase,
}: {
  role: TodoFocusItem["role"];
  severity: string;
  waitingOn: string;
  phase: string;
}) {
  const severityRank: Record<string, number> = {
    high: 0,
    action: 1,
    watch: 2,
    clear: 3,
  };
  const waitingRank: Record<string, number> = role === "user"
    ? {
        user_or_controller: 0,
        controller: 1,
        external_evidence: 2,
        codex: 3,
        clear: 4,
      }
    : {
        codex: 0,
        user_or_controller: 1,
        controller: 2,
        external_evidence: 3,
        clear: 4,
      };
  const phaseRank = phase === "controller_gated" || phase === "operator_gated"
    ? 0
    : phase === "mapped" || phase === "refreshed"
      ? 1
      : 2;
  return ((severityRank[severity] ?? 4) * 100) + ((waitingRank[waitingOn] ?? 5) * 10) + phaseRank;
}

function buildTodoFocusItems(rows: GoalDirectoryRow[]): TodoFocusItem[] {
  const items: TodoFocusItem[] = [];

  for (const row of rows) {
    const projectAsset = row.queueItem?.project_asset;
    const userTodos = todosFromProjectAssetSummary(projectAsset?.user_todos, row.queueItem?.user_todos, "project_asset.user_todos");
    const agentTodos = todosFromProjectAssetSummary(projectAsset?.agent_todos, row.queueItem?.agent_todos, "project_asset.agent_todos");
    for (const [role, todos] of [
      ["user", userTodos],
      ["agent", agentTodos],
    ] as const) {
      const todo = firstOpenTodo(todos);
      if (!todo) {
        continue;
      }
      items.push({
        goalId: row.goal.id,
        role,
        text: todo.text,
        openCount: todos?.open_count ?? 1,
        totalCount: todos?.total_count ?? 1,
        severity: row.severity,
        waitingOn: row.waitingOn,
        phase: row.lifecyclePhase,
        priority: todoFocusPriority({
          role,
          severity: row.severity,
          waitingOn: row.waitingOn,
          phase: row.lifecyclePhase,
        }),
      });
    }
  }

  return items.sort((a, b) => a.priority - b.priority || a.goalId.localeCompare(b.goalId));
}

function todoDisplayTitle(todo: TodoItem) {
  return todo.title?.trim() || todo.text;
}

function todoDisplayStatus(todo: TodoItem) {
  return todo.status?.trim() || (todo.done ? "done" : "open");
}

function todoExplorerStatusVariant(item: TodoExplorerItem): BadgeVariant {
  const todo = item.todo;
  const status = todoDisplayStatus(todo);
  if (status === "done") {
    return "success";
  }
  if (status === "blocked") {
    return "danger";
  }
  if (status === "deferred") {
    return "neutral";
  }
  return item.role === "user" ? "warning" : "info";
}

function todoRoleLabel(role: TodoExplorerRole) {
  return role === "user" ? "User" : "Agent";
}

function collectTodoExplorerItems(rows: GoalDirectoryRow[], todoIndex?: TodoIndexSummary | null): TodoExplorerItem[] {
  const items: TodoExplorerItem[] = [];
  const seenKeys = new Set<string>();

  for (const row of rows) {
    const projectAsset = row.queueItem?.project_asset;
    const groups: Array<[TodoExplorerRole, TodoGroup | null]> = [
      ["user", todosFromProjectAssetSummary(projectAsset?.user_todos, row.queueItem?.user_todos, "project_asset.user_todos")],
      ["agent", todosFromProjectAssetSummary(projectAsset?.agent_todos, row.queueItem?.agent_todos, "project_asset.agent_todos")],
    ];
    for (const [role, group] of groups) {
      for (const [sourceOrder, todo] of (group?.items ?? []).entries()) {
        items.push({
          goalId: row.goal.id,
          role,
          todo,
          sourceSection: todo.source_section ?? group?.source_section ?? `${role}_todos`,
          source: "attention_queue",
          openCount: group?.open_count ?? 0,
          totalCount: group?.total_count ?? 0,
          severity: row.severity,
          waitingOn: row.waitingOn,
          phase: row.lifecyclePhase,
          sourceOrder,
        });
        seenKeys.add(`${row.goal.id}:${role}:${todo.todo_id ?? todo.index}:${todo.text}`);
      }
    }
  }

  const rowByGoal = new Map(rows.map((row) => [row.goal.id, row]));
  for (const [sourceOrder, todo] of (todoIndex?.items ?? []).entries()) {
    const goalId = todo.goal_id;
    const rawRole = todo.role === "user" || todo.role === "agent" ? todo.role : "agent";
    const key = `${goalId}:${rawRole}:${todo.todo_id ?? todo.index}:${todo.text}`;
    if (seenKeys.has(key)) {
      continue;
    }
    const row = rowByGoal.get(goalId);
    items.push({
      goalId,
      role: rawRole,
      todo,
      sourceSection: todo.source_section ?? todo.source ?? "todo_index",
      source: todo.source ?? "todo_index",
      openCount: 0,
      totalCount: 0,
      severity: row?.severity ?? "watch",
      waitingOn: row?.waitingOn ?? "codex",
      phase: row?.lifecyclePhase ?? "indexed",
      sourceOrder: sourceOrder + 10_000,
    });
    seenKeys.add(key);
  }

  return items.sort((left, right) => {
    const leftDone = left.todo.done ? 1 : 0;
    const rightDone = right.todo.done ? 1 : 0;
    return leftDone - rightDone
      || left.goalId.localeCompare(right.goalId)
      || left.role.localeCompare(right.role)
      || left.todo.index - right.todo.index
      || left.sourceOrder - right.sourceOrder;
  });
}

function todoExplorerHaystack(item: TodoExplorerItem) {
  const todo = item.todo;
  return [
    item.goalId,
    item.role,
    item.sourceSection,
    item.severity,
    item.waitingOn,
    item.phase,
    todo.todo_id,
    todo.priority,
    todo.status,
    todo.title,
    todo.text,
    todo.task_class,
    todo.action_kind,
    todo.claimed_by,
    todo.archive_state,
    todo.note,
    todo.evidence,
    item.source,
    (todo as { latest_event_kind?: string | null }).latest_event_kind,
    (todo as { latest_event_at?: string | null }).latest_event_at,
    (todo as { agent_id?: string | null }).agent_id,
    String(todo.index),
    ...(todo.required_capabilities ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function todoExplorerProjectOptions(items: TodoExplorerItem[]) {
  return Array.from(new Set(items.map((item) => item.goalId)))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
}

function ProjectTodoExplorer({
  onProjectChange,
  onQueryChange,
  onRoleChange,
  onSelectGoal,
  onStatusChange,
  query,
  role,
  rows,
  selectedTodoGoalId,
  selectedGoalId,
  status,
  todoIndex,
}: {
  onProjectChange: (goalId: string) => void;
  onQueryChange: (query: string) => void;
  onRoleChange: (role: "all" | TodoExplorerRole) => void;
  onSelectGoal: (goalId: string) => void;
  onStatusChange: (status: "all" | "open" | "done" | "blocked" | "deferred") => void;
  query: string;
  role: "all" | TodoExplorerRole;
  rows: GoalDirectoryRow[];
  selectedTodoGoalId: string;
  selectedGoalId: string;
  status: "all" | "open" | "done" | "blocked" | "deferred";
  todoIndex?: TodoIndexSummary | null;
}) {
  const allItems = useMemo(() => collectTodoExplorerItems(rows, todoIndex), [rows, todoIndex]);
  const projectOptions = useMemo(() => todoExplorerProjectOptions(allItems), [allItems]);
  const selectedProject = selectedTodoGoalId === "all" || projectOptions.includes(selectedTodoGoalId)
    ? selectedTodoGoalId
    : "all";
  const normalizedQuery = query.trim().toLowerCase();
  const filteredItems = allItems.filter((item) => {
    const projectMatches = selectedProject === "all" || item.goalId === selectedProject;
    const roleMatches = role === "all" || item.role === role;
    const itemStatus = todoDisplayStatus(item.todo);
    const statusMatches = status === "all" || itemStatus === status;
    const queryMatches = !normalizedQuery || todoExplorerHaystack(item).includes(normalizedQuery);
    return projectMatches && roleMatches && statusMatches && queryMatches;
  });
  const openCount = allItems.filter((item) => !item.todo.done).length;
  const agentCount = allItems.filter((item) => item.role === "agent").length;
  const visibleItems = filteredItems.slice(0, 80);

  return (
    <Card data-testid="project-todo-explorer">
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            Project Todo Explorer
          </CardTitle>
          <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
            Search current projected and indexed todos by project, id, text, owner, action kind, or claimed agent.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{filteredItems.length}/{allItems.length} shown</Badge>
          <Badge variant="neutral">{projectOptions.length} projects</Badge>
          <Badge variant={openCount > 0 ? "warning" : "success"}>{openCount} open</Badge>
          <Badge variant="neutral">{agentCount} agent</Badge>
          {todoIndex ? <Badge variant="neutral">{todoIndex.rollout_event_count} events</Badge> : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(180px,260px)_148px_148px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400 dark:text-zinc-500" />
            <input
              aria-label="Search project todos"
              className={cn(inputClassName, "pl-9")}
              data-testid="project-todo-search-input"
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="todo_f2760d7e328f, benchmark, claimed_by, action_kind..."
              value={query}
            />
          </div>
          <Select
            aria-label="Todo project"
            onChange={(event) => onProjectChange(event.target.value)}
            value={selectedProject}
          >
            <option value="all">All projects</option>
            {projectOptions.map((goalId) => (
              <option key={goalId} value={goalId}>
                {goalId}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Todo role"
            onChange={(event) => onRoleChange(event.target.value as "all" | TodoExplorerRole)}
            value={role}
          >
            <option value="all">All roles</option>
            <option value="user">User todos</option>
            <option value="agent">Agent todos</option>
          </Select>
          <Select
            aria-label="Todo status"
            onChange={(event) => onStatusChange(event.target.value as "all" | "open" | "done" | "blocked" | "deferred")}
            value={status}
          >
            <option value="all">All status</option>
            <option value="open">Open</option>
            <option value="blocked">Blocked</option>
            <option value="deferred">Deferred</option>
            <option value="done">Done</option>
          </Select>
        </div>

        {visibleItems.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-zinc-400">
            No projected todo matches {query ? <span className="font-mono">{query}</span> : "the current filters"}.
          </div>
        ) : (
          <div className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 dark:divide-zinc-800 dark:border-zinc-800">
            {visibleItems.map((item) => {
              const todo = item.todo;
              const statusLabel = todoDisplayStatus(todo);
              const todoEventFields = todo as unknown as { latest_event_kind?: unknown };
              const latestEventKind = typeof todoEventFields.latest_event_kind === "string"
                ? todoEventFields.latest_event_kind
                : "";
              return (
                <button
                  className={cn(
                    "w-full bg-white px-4 py-3 text-left transition hover:bg-slate-50 dark:bg-zinc-950 dark:hover:bg-zinc-900",
                    item.goalId === selectedGoalId && "bg-slate-50 dark:bg-zinc-900",
                  )}
                  data-testid="project-todo-result"
                  key={`${item.goalId}-${item.role}-${todo.todo_id ?? todo.index}-${item.sourceOrder}`}
                  onClick={() => onSelectGoal(item.goalId)}
                  type="button"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={item.role === "user" ? "warning" : "info"}>{todoRoleLabel(item.role)}</Badge>
                    <Badge variant={todoExplorerStatusVariant(item)}>{statusLabel}</Badge>
                    {todo.priority ? <Badge variant={todo.priority === "P0" ? "danger" : "neutral"}>{todo.priority}</Badge> : null}
                    <span className="break-all text-xs font-medium text-slate-500 dark:text-zinc-400">{item.goalId}</span>
                    {todo.todo_id ? (
                      <span
                        className="break-all rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-zinc-900 dark:text-zinc-300"
                        data-testid="project-todo-id"
                      >
                        {todo.todo_id}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400 dark:text-zinc-500">#{todo.index}</span>
                    )}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-800 dark:text-zinc-200">
                    {todoDisplayTitle(todo)}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                    <span>{item.sourceSection}</span>
                    {item.source ? <span>source={item.source}</span> : null}
                    {todo.action_kind ? <span>action={todo.action_kind}</span> : null}
                    {todo.task_class ? <span>class={todo.task_class}</span> : null}
                    {todo.claimed_by ? <span>claimed_by={todo.claimed_by}</span> : null}
                    {latestEventKind ? <span>event={latestEventKind}</span> : null}
                    {todo.updated_at ? <span>updated={todo.updated_at}</span> : null}
                  </div>
                  {todo.note ? (
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">{todo.note}</p>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}

        {filteredItems.length > visibleItems.length ? (
          <p className="text-xs text-slate-500 dark:text-zinc-400">
            Showing first {visibleItems.length} matches. Narrow the search to inspect the rest.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TodoFocusColumn({
  icon: Icon,
  items,
  onSelectGoal,
  selectedGoalId,
  title,
  variant,
}: {
  icon: React.ComponentType<{ className?: string }>;
  items: TodoFocusItem[];
  onSelectGoal: (goalId: string) => void;
  selectedGoalId: string;
  title: string;
  variant: BadgeVariant;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex min-h-12 items-center justify-between gap-3 border-b border-slate-200 px-3 py-2 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
          <h3 className="text-sm font-semibold text-slate-950 dark:text-zinc-50">{title}</h3>
        </div>
        <Badge variant={items.length > 0 ? variant : "success"}>{items.length}</Badge>
      </div>
      {items.length === 0 ? (
        <div className="p-3 text-sm text-slate-500 dark:text-zinc-400">No open todo.</div>
      ) : (
        <div className="divide-y divide-slate-200 dark:divide-zinc-800">
          {items.slice(0, 5).map((item) => (
            <button
              className={cn(
                "grid w-full gap-2 px-3 py-3 text-left transition hover:bg-slate-50 dark:hover:bg-zinc-900",
                item.goalId === selectedGoalId && "bg-slate-100 dark:bg-zinc-900",
              )}
              key={`${item.role}-${item.goalId}-${item.text}`}
              onClick={() => onSelectGoal(item.goalId)}
              type="button"
            >
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <Badge variant="neutral">Goal</Badge>
                <span className="break-all text-sm font-semibold text-slate-950 dark:text-zinc-50">{item.goalId}</span>
              </div>
              <p className="line-clamp-2 break-words text-sm leading-6 text-slate-700 dark:text-zinc-300">{item.text}</p>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                <Badge variant={severityVariant[item.severity] ?? "neutral"}>{item.severity}</Badge>
                <Badge variant="neutral">{waitingLabel[item.waitingOn] ?? item.waitingOn}</Badge>
                <Badge variant="info">{item.openCount}/{item.totalCount} open</Badge>
                <PhaseBadges compact phase={item.phase} />
              </div>
            </button>
          ))}
          {items.length > 5 ? (
            <div className="px-3 py-2 text-xs font-medium text-slate-500 dark:text-zinc-400">
              +{items.length - 5} more
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function TodoFocusPanel({
  rows,
  selectedGoalId,
  onSelectGoal,
}: {
  rows: GoalDirectoryRow[];
  selectedGoalId: string;
  onSelectGoal: (goalId: string) => void;
}) {
  const items = useMemo(() => buildTodoFocusItems(rows), [rows]);
  const userItems = items.filter((item) => item.role === "user");
  const agentItems = items.filter((item) => item.role === "agent");

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          Todo Focus
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant={userItems.length > 0 ? "warning" : "success"}>{userItems.length} user</Badge>
          <Badge variant={agentItems.length > 0 ? "info" : "success"}>{agentItems.length} agent</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 lg:grid-cols-2">
          <TodoFocusColumn
            icon={Users}
            items={userItems}
            onSelectGoal={onSelectGoal}
            selectedGoalId={selectedGoalId}
            title="User Todo"
            variant="warning"
          />
          <TodoFocusColumn
            icon={Bot}
            items={agentItems}
            onSelectGoal={onSelectGoal}
            selectedGoalId={selectedGoalId}
            title="Agent Priority Todo"
            variant="info"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function UserTodoCallout({
  blocksGate,
  focusWait,
  goalId,
  source,
  todos,
}: {
  blocksGate?: boolean;
  focusWait?: boolean;
  goalId: string;
  source: DataSource;
  todos?: TodoGroup | null;
}) {
  const todo = firstOpenTodo(todos);
  const count = todoCountLabel(todos);
  const materials = todo?.review_materials ?? [];
  const [activeMaterial, setActiveMaterial] = useState<ReviewMaterial | null>(null);
  const [materialContent, setMaterialContent] = useState<ReviewMaterialContent | null>(null);
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [isReadingMaterial, setIsReadingMaterial] = useState(false);
  if (!todo) {
    return null;
  }

  async function readMaterial(material: ReviewMaterial) {
    const url = buildReviewMaterialUrl(source, goalId, material);
    if (!url) {
      setMaterialError("Review material reader is only available for loopback live status URLs.");
      setActiveMaterial(material);
      setMaterialContent(null);
      return;
    }
    setIsReadingMaterial(true);
    setActiveMaterial(material);
    setMaterialError(null);
    setMaterialContent(null);
    try {
      const response = await fetch(url, { cache: "no-store" });
      const payload = await response.json() as ReviewMaterialContent;
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setMaterialContent(payload);
    } catch (error) {
      setMaterialError(formatStatusError(error));
    } finally {
      setIsReadingMaterial(false);
    }
  }

  return (
    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-2 dark:border-emerald-900/60 dark:bg-emerald-950/30">
      <div className="flex flex-wrap items-center gap-2">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 dark:text-emerald-300" />
        <Badge variant="success">{blocksGate ? "先做用户待办" : focusWait ? "Owner blocker" : "Next user todo"}</Badge>
        {count ? <Badge variant="neutral">{count}</Badge> : null}
      </div>
      <p className="mt-2 line-clamp-3 break-words text-sm font-medium leading-6 text-emerald-950 dark:text-emerald-100">
        {todo.text}
      </p>
      {blocksGate ? (
        <p className="mt-1 text-xs font-medium leading-5 text-emerald-800 dark:text-emerald-200">
          完成或明确暂缓这个用户待办后，再审批下面的 gate。
        </p>
      ) : null}
      {focusWait ? (
        <p className="mt-1 text-xs font-medium leading-5 text-emerald-800 dark:text-emerald-200">
          有新 owner evidence、clean baseline 或外部 eval 前保持 focus wait，不恢复 delivery。
        </p>
      ) : null}
      {materials.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge variant="info">Review material</Badge>
          {materials.map((material) => {
            const label = material.label || material.path;
            const canRead = Boolean(material.exists && buildReviewMaterialUrl(source, goalId, material));
            return (
              <Button
                disabled={!material.exists || isReadingMaterial}
                key={`${material.path}-${material.anchor ?? ""}`}
                onClick={() => void readMaterial(material)}
                size="sm"
                variant={canRead ? "secondary" : "ghost"}
              >
                <FileText className="h-4 w-4" />
                {label}
              </Button>
            );
          })}
        </div>
      ) : null}
      {activeMaterial || materialError || materialContent ? (
        <div className="mt-3 rounded-md border border-emerald-200 bg-white/70 p-2 dark:border-emerald-900 dark:bg-zinc-950/60">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="break-all text-xs font-semibold text-emerald-950 dark:text-emerald-100">
                {activeMaterial?.label || activeMaterial?.path || "Review material"}
              </div>
              {materialContent?.bytes ? (
                <div className="text-[11px] text-emerald-800 dark:text-emerald-200">{materialContent.bytes} bytes</div>
              ) : null}
            </div>
            <Button
              onClick={() => {
                setActiveMaterial(null);
                setMaterialContent(null);
                setMaterialError(null);
              }}
              size="sm"
              variant="ghost"
            >
              Close
            </Button>
          </div>
          {isReadingMaterial ? (
            <p className="mt-2 text-xs text-emerald-800 dark:text-emerald-200">Loading review material...</p>
          ) : null}
          {materialError ? <Badge variant="danger">{materialError.slice(0, 120)}</Badge> : null}
          {materialContent?.content ? (
            <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded border border-emerald-100 bg-white p-3 text-xs leading-5 text-slate-800 dark:border-emerald-900 dark:bg-zinc-950 dark:text-zinc-100">
              {materialContent.content}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

type CopyState = "idle" | "copied" | "failed";

type AuthorityCoverage = {
  badge: string;
  reviewLine: string;
  shortLine: string;
  variant: BadgeVariant;
};

type QuotaView = {
  label: string;
  reviewLine: string;
  shortLine: string;
  variant: BadgeVariant;
};

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the legacy path for local HTTP previews.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    return document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }
}

function humanReviewPrompt(kind?: UserActionKind) {
  if (kind === "reward") {
    return {
      question: "是否把这次判断记录为 run-bound human_reward？",
      reply: "同意记录 / 暂不同意 + 一句话原因。",
      boundary: "只有去掉 --dry-run 才会写 human_reward 和 active-state 摘要；这不是 write-control、controller opt-in 或生产动作授权。",
    };
  }
  if (kind === "controller") {
    return {
      question: "是否允许目标项目进入 read-only/controller opt-in？",
      reply: "同意先做 read-only map dry-run / 暂不同意 + 一句话原因。",
      boundary: "这只授权项目 Agent 预览 dry-run 路径；不写 operator gate、run history、write-control、实验控制或生产动作。",
    };
  }
  if (kind === "codex") {
    return {
      question: "是否让项目 Agent 沿 safe local path 继续？",
      reply: "同意继续 / 暂不同意 + 一句话原因。",
      boundary: "如果下一步需要写入、reward append、approval 或 write-control，项目 Agent 必须先停下等明确授权。",
    };
  }
  if (kind === "evidence") {
    return {
      question: "是否继续等待外部证据，而不升级成决策建议？",
      reply: "继续等待 / 不继续等待 + 一句话原因。",
      boundary: "观察状态不是 reward、approval 或 controller opt-in。",
    };
  }
  if (kind === "health") {
    return {
      question: "是否先修健康阻塞，再讨论 reward/controller/codex handoff？",
      reply: "先修阻塞 / 暂不处理 + 一句话原因。",
      boundary: "健康修复不等于授权 reward append、approval 或 write-control。",
    };
  }
  return {
    question: "当前是否需要转给项目 Agent 继续处理？",
    reply: "继续 / 不继续 / 继续观察 + 一句话原因。",
    boundary: "本回复不自动写 reward、approval、controller opt-in 或 write-control。",
  };
}

function controllerReplyLine(goalId: string) {
  return `同意 ${goalId} 先做 read-only map dry-run / 暂不同意 + 一句话原因。`;
}

function controllerApprovalReason(goalId: string) {
  return `同意 ${goalId} 先做 read-only map dry-run，不授权写入或生产动作`;
}

function durableOperatorGateRecordRule(kind?: UserActionKind) {
  if (kind !== "controller") {
    return null;
  }
  return "记录规则：如需持久记录本次判断，先用本地 operator-gate dry-run 预览；确认写入时去掉 --dry-run；写入会生成 operator_gate_resume_contract_v0，只在该决策点 rebase 当前权威状态，不回滚或带回整个仓库；拒绝/暂缓用 reject/defer + public-safe 原因。";
}

function suggestedDecisionLine(kind?: UserActionKind, item?: UserActionSummaryItem, goalId?: string) {
  if (kind === "controller") {
    if (item?.operatorQuestion && firstOpenTodo(item.userTodos)) {
      return "先完成/确认用户待办，再判断是否同意 gate；不授权写入或生产动作。";
    }
    const targetGoalId = goalId ?? item?.goalId;
    const lead = targetGoalId ? `同意 ${targetGoalId} 先做` : "同意先做";
    const question = item?.operatorQuestion ?? "";
    if (question.includes("read-only map")) {
      return `${lead} read-only map dry-run；不授权写入或生产动作。`;
    }
    return `${lead}只读 controller dry-run；不授权写入或生产动作。`;
  }
  if (kind === "reward") {
    return "同意记录这次 human reward / 暂不同意，原因是...";
  }
  if (kind === "codex") {
    return "同意让 Codex 沿 safe path 继续；如需写入再单独请求授权。";
  }
  if (kind === "evidence") {
    return "继续等待外部证据；暂不升级成决策建议。";
  }
  if (kind === "health") {
    return "先修健康阻塞；暂不处理 reward/controller/codex handoff。";
  }
  return "继续 / 不继续 / 继续观察，并补一句原因。";
}

function normalizeConflictRisk(value?: string | null) {
  return (value || "unknown").toLowerCase();
}

function authorityCoverageVariant({
  declared,
  conflictRisk,
  deprecatedCount,
  materialOwnerReviewCount,
  materialStaleCount,
  present,
  total,
}: {
  declared: boolean;
  conflictRisk?: string | null;
  deprecatedCount: number;
  materialOwnerReviewCount?: number;
  materialStaleCount?: number;
  present: number;
  total: number;
}): BadgeVariant {
  if (!declared) {
    return "neutral";
  }
  const risk = normalizeConflictRisk(conflictRisk);
  if (
    risk === "high" ||
    deprecatedCount > 0 ||
    (materialOwnerReviewCount ?? 0) > 0 ||
    (materialStaleCount ?? 0) > 0 ||
    (total > 0 && present < total)
  ) {
    return "warning";
  }
  if (risk === "medium") {
    return "warning";
  }
  return "success";
}

function buildAuthorityCoverageFromCounts({
  declared,
  pathExists,
  present,
  total,
  topics,
  materialTotal,
  materialRepositories,
  materialOwnerReviewRequired,
  materialStale,
  materialCurrentAuthority,
  deprecatedCount,
  conflictRisk,
}: {
  declared?: boolean | null;
  pathExists?: boolean | null;
  present?: number | null;
  total?: number | null;
  topics?: number | null;
  materialTotal?: number | null;
  materialRepositories?: number | null;
  materialOwnerReviewRequired?: number | null;
  materialStale?: number | null;
  materialCurrentAuthority?: number | null;
  deprecatedCount?: number | null;
  conflictRisk?: string | null;
}): AuthorityCoverage | undefined {
  const isDeclared = Boolean(declared);
  if (!isDeclared && !total && !topics && !materialTotal) {
    return undefined;
  }
  const presentCount = present ?? 0;
  const totalCount = total ?? 0;
  const topicCount = topics ?? 0;
  const materialCount = materialTotal ?? 0;
  const materialRepoCount = materialRepositories ?? 0;
  const materialOwnerReviewCount = materialOwnerReviewRequired ?? 0;
  const materialStaleCount = materialStale ?? 0;
  const materialCurrentAuthorityCount = materialCurrentAuthority ?? 0;
  const deprecated = deprecatedCount ?? 0;
  const risk = normalizeConflictRisk(conflictRisk);
  const pathText = pathExists == null ? "path unchecked" : pathExists ? "path ok" : "path missing";
  const entryText = totalCount > 0 ? `default entries ${presentCount}/${totalCount}` : "default entries not declared";
  const riskText = risk === "unknown" ? "risk unknown" : `risk ${risk}`;
  const materialText =
    materialCount > 0
      ? `materials ${materialCount}; repos ${materialRepoCount}; owner review ${materialOwnerReviewCount}; stale ${materialStaleCount}; current ${materialCurrentAuthorityCount}`
      : "";
  const badge = !isDeclared
    ? "No registry"
    : risk === "high" ||
        risk === "medium" ||
        deprecated > 0 ||
        materialOwnerReviewCount > 0 ||
        materialStaleCount > 0 ||
        (totalCount > 0 && presentCount < totalCount)
      ? "Needs review"
      : "Covered";
  return {
    badge,
    reviewLine: isDeclared
      ? `权威源：已声明；${pathText}；${entryText}；topic ${topicCount}；${riskText}${materialText ? `；${materialText}` : ""}${deprecated ? `；deprecated ${deprecated}` : ""}。`
      : "权威源：未声明 authority registry；只能看到普通 authority sources。",
    shortLine: isDeclared
      ? `${entryText}; topic ${topicCount}; ${materialText ? `${materialText}; ` : ""}${riskText}`
      : "authority registry not declared",
    variant: authorityCoverageVariant({
      declared: isDeclared,
      conflictRisk: risk,
      deprecatedCount: deprecated,
      materialOwnerReviewCount,
      materialStaleCount,
      present: presentCount,
      total: totalCount,
    }),
  };
}

function buildAuthorityCoverage({
  goal,
  run,
}: {
  goal?: RunGoal;
  run?: RunRecord;
}): AuthorityCoverage | undefined {
  const projectMap = run?.project_map;
  if (projectMap?.authority_registry_declared != null || projectMap?.authority_registry_default_entry_count != null) {
    return buildAuthorityCoverageFromCounts({
      declared: projectMap.authority_registry_declared,
      pathExists: projectMap.authority_registry_path_exists,
      present: projectMap.authority_registry_default_entries_present,
      total: projectMap.authority_registry_default_entry_count,
      topics: projectMap.topic_authority_count,
      materialTotal: projectMap.project_material_count,
      materialRepositories: projectMap.project_material_repository_count,
      materialOwnerReviewRequired: projectMap.project_material_owner_review_required_count,
      materialStale: projectMap.project_material_stale_count,
      materialCurrentAuthority: projectMap.project_material_current_authority_count,
      conflictRisk: projectMap.authority_registry_conflict_risk,
    });
  }
  const registry: AuthorityRegistry | null | undefined = goal?.authority_registry;
  if (!registry) {
    return undefined;
  }
  return buildAuthorityCoverageFromCounts({
    declared: registry.declared,
    pathExists: registry.path_exists,
    present: registry.default_entries_present,
    total: registry.default_entry_count,
    topics: registry.topic_authority_count,
    materialTotal: registry.project_material_count,
    materialRepositories: registry.project_material_repository_count,
    materialOwnerReviewRequired: registry.project_material_owner_review_required_count,
    materialStale: registry.project_material_stale_count,
    materialCurrentAuthority: registry.project_material_current_authority_count,
    deprecatedCount: registry.deprecated_source_count,
    conflictRisk: registry.conflict_risk,
  });
}

function buildAuthorityCoverageFromProjectMap(projectMap: ProjectMap): AuthorityCoverage | undefined {
  return buildAuthorityCoverageFromCounts({
    declared: projectMap.authority_registry_declared,
    pathExists: projectMap.authority_registry_path_exists,
    present: projectMap.authority_registry_default_entries_present,
    total: projectMap.authority_registry_default_entry_count,
    topics: projectMap.topic_authority_count,
    materialTotal: projectMap.project_material_count,
    materialRepositories: projectMap.project_material_repository_count,
    materialOwnerReviewRequired: projectMap.project_material_owner_review_required_count,
    materialStale: projectMap.project_material_stale_count,
    materialCurrentAuthority: projectMap.project_material_current_authority_count,
    conflictRisk: projectMap.authority_registry_conflict_risk,
  });
}

const quotaStateLabel: Record<string, string> = {
  blocked_health: "Health blocked",
  eligible: "Eligible",
  focus_wait: "Focus wait",
  operator_gate: "Operator gate",
  paused: "Paused",
  throttled: "Throttled",
  waiting: "Waiting",
};

const quotaStateReviewLabel: Record<string, string> = {
  blocked_health: "先修健康阻塞",
  eligible: "可自动推进",
  focus_wait: "等待 owner evidence / clean baseline / external eval",
  operator_gate: "等待人或控制器决策",
  paused: "自动 compute 已暂停",
  throttled: "本窗口配额已用完",
  waiting: "等待证据或下一步",
};

function quotaVariant(state?: string | null): BadgeVariant {
  if (state === "eligible") {
    return "success";
  }
  if (state === "paused") {
    return "neutral";
  }
  if (state === "blocked_health") {
    return "danger";
  }
  if (state === "operator_gate" || state === "throttled") {
    return "warning";
  }
  return "info";
}

function formatQuotaCompute(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function buildQuotaView(quota?: ComputeQuota | null): QuotaView | undefined {
  if (!quota) {
    return undefined;
  }
  const state = quota.state || "waiting";
  const compute = quota.compute ?? 1;
  const spent = quota.spent_slots ?? 0;
  const allowed = quota.allowed_slots ?? 0;
  const computeText = formatQuotaCompute(compute);
  const recovery = isOutcomeFloorRecoveryQuota(quota);
  const stateLabel = recovery ? "Recovery allowed" : quotaStateLabel[state] ?? state;
  const reviewState = recovery
    ? `需要 Codex 做一次 ${recoveryEvidenceLabel(quota)} recovery`
    : quotaStateReviewLabel[state] ?? state;
  return {
    label: `Quota ${computeText}`,
    shortLine: `${stateLabel}; ${spent}/${allowed} slots`,
    reviewLine: `配额：compute ${computeText}；${reviewState}；${spent}/${allowed} slots。`,
    variant: quotaVariant(state),
  };
}

function isFocusWaitQuota(quota?: ComputeQuota | null) {
  return (quota?.state ?? "") === "focus_wait";
}

function isOutcomeFloorRecoveryQuota(quota?: ComputeQuota | null) {
  return Boolean(
    quota
      && quota.state === "focus_wait"
      && quota.handoff_outcome_floor_block
      && quota.safe_bypass_allowed
      && quota.safe_bypass_kind === "outcome_floor_recovery",
  );
}

function recoveryEvidenceLabel(quota?: ComputeQuota | null) {
  const targets = quota?.must_advance ?? [];
  if (targets.some((target) => target === "ranker_or_cross_domain_evidence")) {
    return "排序器 / 跨域证据";
  }
  if (targets.length > 0) {
    return targets.map(shareMachineLabel).join(" / ");
  }
  return "结果级证据";
}

function formatLatestValidation(validation?: ProjectAssetLatestValidation | null) {
  if (!validation) {
    return null;
  }
  return [
    validation.classification,
    validation.summary,
  ].filter(Boolean).join("; ") || null;
}

function QuotaChip({ quota }: { quota?: ComputeQuota | null }) {
  const view = buildQuotaView(quota);
  if (!view) {
    return null;
  }
  return <Badge variant={view.variant}>{view.label}</Badge>;
}

function controlPlaneForTarget(goal?: RunGoal, queueItem?: QueueItem): ControlPlanePolicy | null {
  return queueItem?.control_plane ?? queueItem?.project_asset?.control_plane ?? goal?.control_plane ?? null;
}

function orchestrationForTarget(goal?: RunGoal, queueItem?: QueueItem): OrchestrationPolicy | null {
  return queueItem?.project_asset?.orchestration ?? goal?.orchestration ?? goal?.spawn_policy ?? null;
}

function flagValue(value?: boolean | null) {
  return value ? "on" : "off";
}

function orchestrationMode(policy?: OrchestrationPolicy | null) {
  if (!policy) {
    return "default";
  }
  const spawnAllowed = Boolean(policy.spawn_allowed || policy.allowed);
  const maxChildren = policy.max_children ?? 0;
  const explicitMode = policy.mode || policy.orchestration_mode || "";
  if ((!explicitMode || explicitMode === "default") && spawnAllowed && maxChildren > 0) {
    return "multi_subagent";
  }
  return explicitMode || "default";
}

function shellArg(value: string) {
  if (/^[A-Za-z0-9_./:=@,+-]+$/.test(value)) {
    return value;
  }
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function buildHeartbeatInstallView(goal?: RunGoal, queueItem?: QueueItem): {
  badge: string;
  detail: string;
  variant: BadgeVariant;
} {
  const status = [queueItem?.status, goal?.status, goal?.adapter_status].filter(Boolean).join(" ").toLowerCase();
  if (status.includes("not_installed")) {
    return {
      badge: "not installed",
      detail: "status includes not_installed",
      variant: "warning",
    };
  }
  if (status.includes("paused")) {
    return {
      badge: "paused",
      detail: "status includes paused",
      variant: "neutral",
    };
  }
  if (status.includes("stage_deferred") || status.includes("deferred")) {
    return {
      badge: "deferred",
      detail: "status includes deferred",
      variant: "warning",
    };
  }
  if (queueItem || goal?.registry_member) {
    return {
      badge: "observed",
      detail: queueItem?.source ? `queue source=${queueItem.source}` : "registry member observed in live status",
      variant: "success",
    };
  }
  return {
    badge: "unknown",
    detail: "no queue or registry heartbeat signal",
    variant: "neutral",
  };
}

function ControlPlaneSettingRow({
  badge,
  detail,
  icon: Icon,
  label,
  variant,
}: {
  badge: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  variant: BadgeVariant;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-slate-500 dark:text-zinc-400" />
          <span className="text-sm font-semibold text-slate-900 dark:text-zinc-100">{label}</span>
        </div>
        <Badge variant={variant}>{badge}</Badge>
      </div>
      <div className="mt-2 break-words text-xs leading-5 text-slate-500 dark:text-zinc-400">{detail}</div>
    </div>
  );
}

type ControlPlaneSettingsDraft = {
  quotaCompute: string;
  quotaWindowHours: string;
  selfRepairEnabled: boolean;
  selfRepairHealth: boolean;
  selfRepairWaitingProjection: boolean;
  orchestrationMode: "default" | "multi_subagent";
  spawnAllowed: boolean;
  maxChildren: string;
  allowedDomains: string;
};

type ConfigureGoalRequestBody = {
  allowed_domains: string[];
  clear_allowed_domains: boolean;
  goal_id: string;
  max_children: number;
  orchestration_mode: "default" | "multi_subagent";
  quota_compute: number;
  quota_window_hours: number;
  self_repair_enabled: boolean;
  self_repair_health: boolean;
  self_repair_waiting_projection: boolean;
  spawn_allowed: boolean;
};

type ConfigureGoalApiResponse = {
  ok: boolean;
  dry_run?: boolean;
  execute?: boolean;
  written?: boolean;
  changed?: boolean;
  goal_id?: string;
  changed_fields?: string[];
  preview_id?: string;
  control_plane_summary?: string;
  orchestration_summary?: string;
  error?: string;
};

function buildControlPlaneSettingsDraft(goal?: RunGoal, queueItem?: QueueItem): ControlPlaneSettingsDraft {
  const quota = queueItem?.quota ?? queueItem?.project_asset?.quota ?? goal?.quota;
  const controlPlane = controlPlaneForTarget(goal, queueItem);
  const selfRepair = controlPlane?.self_repair;
  const orchestration = orchestrationForTarget(goal, queueItem);
  const mode = orchestrationMode(orchestration);
  return {
    quotaCompute: String(quota?.compute ?? 1),
    quotaWindowHours: String(quota?.window_hours ?? 24),
    selfRepairEnabled: Boolean(selfRepair?.enabled),
    selfRepairHealth: Boolean(selfRepair?.allow_health_blocker_repair),
    selfRepairWaitingProjection: Boolean(selfRepair?.allow_waiting_projection_repair),
    orchestrationMode: mode === "multi_subagent" ? "multi_subagent" : "default",
    spawnAllowed: Boolean(orchestration?.spawn_allowed || orchestration?.allowed),
    maxChildren: String(orchestration?.max_children ?? 0),
    allowedDomains: orchestration?.allowed_domains?.length ? orchestration.allowed_domains.join(", ") : "",
  };
}

function validDraftNumber(value: string, { min }: { min: number }) {
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) && parsed >= min;
}

function buildConfigureGoalRequestBody(draft: ControlPlaneSettingsDraft, goalId?: string): ConfigureGoalRequestBody | null {
  if (!goalId || !validDraftNumber(draft.quotaCompute, { min: 0.000001 }) || !validDraftNumber(draft.quotaWindowHours, { min: 0.000001 }) || !validDraftNumber(draft.maxChildren, { min: 0 })) {
    return null;
  }
  const domains = normalizedDomainList(draft.allowedDomains);
  return {
    allowed_domains: domains,
    clear_allowed_domains: domains.length === 0,
    goal_id: goalId,
    max_children: Number(draft.maxChildren.trim()),
    orchestration_mode: draft.orchestrationMode,
    quota_compute: Number(draft.quotaCompute.trim()),
    quota_window_hours: Number(draft.quotaWindowHours.trim()),
    self_repair_enabled: draft.selfRepairEnabled,
    self_repair_health: draft.selfRepairHealth,
    self_repair_waiting_projection: draft.selfRepairWaitingProjection,
    spawn_allowed: draft.spawnAllowed,
  };
}

function booleanFlag(enabled: boolean, positive: string) {
  return enabled ? `--${positive}` : `--no-${positive}`;
}

function normalizedDomainList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function buildConfigureGoalCommand({
  draft,
  execute,
  goalId,
  registry,
}: {
  draft: ControlPlaneSettingsDraft;
  execute: boolean;
  goalId?: string;
  registry: string;
}) {
  if (!goalId) {
    return "";
  }
  const registryArg = registry ? shellArg(registry) : "$HOME/.codex/loopx/registry.global.json";
  const parts = [
    "loopx",
    "--registry",
    registryArg,
    "configure-goal",
    "--goal-id",
    shellArg(goalId),
    "--quota-compute",
    shellArg(draft.quotaCompute.trim() || "1"),
    "--quota-window-hours",
    shellArg(draft.quotaWindowHours.trim() || "24"),
    booleanFlag(draft.selfRepairEnabled, "self-repair-enabled"),
    booleanFlag(draft.selfRepairHealth, "self-repair-health"),
    booleanFlag(draft.selfRepairWaitingProjection, "self-repair-waiting-projection"),
    "--orchestration-mode",
    draft.orchestrationMode,
    booleanFlag(draft.spawnAllowed, "spawn-allowed"),
    "--max-children",
    shellArg(draft.maxChildren.trim() || "0"),
  ];
  for (const domain of normalizedDomainList(draft.allowedDomains)) {
    parts.push("--allowed-domain", shellArg(domain));
  }
  if (!normalizedDomainList(draft.allowedDomains).length) {
    parts.push("--clear-allowed-domains");
  }
  if (execute) {
    parts.push("--execute");
  }
  return parts.join(" ");
}

function ControlPlaneSettingsPanel({
  applyUrl,
  dryRunUrl,
  goal,
  onStatusRefresh,
  queueItem,
  registry,
  writeEnabled,
}: {
  applyUrl: string | null;
  dryRunUrl: string | null;
  goal?: RunGoal;
  onStatusRefresh: () => Promise<void>;
  queueItem?: QueueItem;
  registry: string;
  writeEnabled: boolean | null;
}) {
  const quota = queueItem?.quota ?? queueItem?.project_asset?.quota ?? goal?.quota;
  const quotaView = buildQuotaView(quota);
  const controlPlane = controlPlaneForTarget(goal, queueItem);
  const selfRepair = controlPlane?.self_repair;
  const heartbeat = buildHeartbeatInstallView(goal, queueItem);
  const orchestration = orchestrationForTarget(goal, queueItem);
  const mode = orchestrationMode(orchestration);
  const domains = orchestration?.allowed_domains?.length ? `; domains=${orchestration.allowed_domains.join(",")}` : "";

  const selfRepairEnabled = Boolean(selfRepair?.enabled);
  const selfRepairBadge = selfRepair ? `self_repair ${selfRepairEnabled ? "on" : "off"}` : "self_repair default_off";
  const selfRepairDetail = selfRepair
    ? `health=${flagValue(selfRepair.allow_health_blocker_repair)}; waiting_projection=${flagValue(selfRepair.allow_waiting_projection_repair)}`
    : "no per-goal self-repair override";
  const orchestrationVariant: BadgeVariant = mode === "multi_subagent" ? "info" : "neutral";
  const currentDraft = useMemo(
    () => buildControlPlaneSettingsDraft(goal, queueItem),
    [
      goal?.id,
      goal?.quota,
      goal?.control_plane,
      goal?.orchestration,
      goal?.spawn_policy,
      queueItem?.goal_id,
      queueItem?.quota,
      queueItem?.control_plane,
      queueItem?.project_asset?.quota,
      queueItem?.project_asset?.control_plane,
      queueItem?.project_asset?.orchestration,
    ],
  );
  const [draft, setDraft] = useState(currentDraft);
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [dryRunResult, setDryRunResult] = useState<ConfigureGoalApiResponse | null>(null);
  const [dryRunBody, setDryRunBody] = useState<ConfigureGoalRequestBody | null>(null);
  const [applyResult, setApplyResult] = useState<ConfigureGoalApiResponse | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(currentDraft);
  const goalId = goal?.id ?? queueItem?.goal_id;
  const dryRunCommand = buildConfigureGoalCommand({ draft, execute: false, goalId, registry });
  const applyCommand = buildConfigureGoalCommand({ draft, execute: true, goalId, registry });
  const requestBody = buildConfigureGoalRequestBody(draft, goalId);
  const canCopy = Boolean(goalId && dirty);
  const canDryRun = Boolean(dryRunUrl && dirty && requestBody);
  const canApply = Boolean(applyUrl && dryRunBody && dryRunResult?.ok && dryRunResult.preview_id && !applyResult?.written);
  const writeApiLabel = writeEnabled === true ? "write API on" : writeEnabled === false ? "write API off" : "write API unknown";
  const writeApiVariant: BadgeVariant = writeEnabled === true ? "success" : writeEnabled === false ? "warning" : "neutral";

  useEffect(() => {
    setDraft(currentDraft);
    setCopyState("idle");
    setDryRunResult(null);
    setDryRunBody(null);
    setApplyResult(null);
    setDryRunError(null);
    setApplyError(null);
  }, [currentDraft]);

  useEffect(() => {
    if (copyState === "idle") {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => setCopyState("idle"), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [copyState]);

  async function copyCommand(command: string) {
    if (!command) {
      return;
    }
    setCopyState((await copyTextToClipboard(command)) ? "copied" : "failed");
  }

  async function runDryRunCheck() {
    if (!dryRunUrl || !requestBody) {
      return;
    }
    setIsDryRunning(true);
    setDryRunError(null);
    setDryRunResult(null);
    setDryRunBody(null);
    setApplyResult(null);
    setApplyError(null);
    try {
      const response = await fetch(dryRunUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const payload = await response.json() as ConfigureGoalApiResponse;
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setDryRunResult(payload);
      setDryRunBody(requestBody);
    } catch (error) {
      setDryRunError(formatStatusError(error));
    } finally {
      setIsDryRunning(false);
    }
  }

  async function applySettings() {
    if (!applyUrl || !dryRunBody || !dryRunResult?.preview_id) {
      return;
    }
    setIsApplying(true);
    setApplyError(null);
    try {
      const response = await fetch(applyUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...dryRunBody, preview_id: dryRunResult.preview_id }),
      });
      const payload = await response.json() as ConfigureGoalApiResponse;
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setApplyResult(payload);
      setDryRunResult(payload);
      await onStatusRefresh();
    } catch (error) {
      setApplyError(formatStatusError(error));
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <div
      className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-900"
      data-testid="control-plane-settings-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-slate-600 dark:text-zinc-300" />
          <h3 className="text-sm font-semibold text-slate-950 dark:text-zinc-50">Control Plane Settings</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={selfRepairEnabled ? "success" : "neutral"}>{selfRepairEnabled ? "repair enabled" : "repair off"}</Badge>
          <Badge variant={orchestrationVariant}>{mode}</Badge>
          <Badge variant={dirty ? "warning" : "success"}>{dirty ? "dirty" : "clean"}</Badge>
          <Badge variant={dryRunUrl ? "info" : "neutral"}>{dryRunUrl ? "local API" : "copy only"}</Badge>
          <Badge variant={writeApiVariant}>{writeApiLabel}</Badge>
          {applyResult?.written ? <Badge variant="success">applied</Badge> : null}
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <ControlPlaneSettingRow
          badge={quotaView?.label ?? "quota unknown"}
          detail={quotaView?.shortLine ?? "quota not projected"}
          icon={Gauge}
          label="Compute quota"
          variant={quotaView?.variant ?? "neutral"}
        />
        <ControlPlaneSettingRow
          badge={selfRepairBadge}
          detail={selfRepairDetail}
          icon={ShieldCheck}
          label="Self repair"
          variant={selfRepairEnabled ? "success" : "neutral"}
        />
        <ControlPlaneSettingRow
          badge={heartbeat.badge}
          detail={heartbeat.detail}
          icon={Terminal}
          label="Heartbeat install"
          variant={heartbeat.variant}
        />
        <ControlPlaneSettingRow
          badge={mode}
          detail={`spawn_allowed=${flagValue(Boolean(orchestration?.spawn_allowed || orchestration?.allowed))}; max_children=${orchestration?.max_children ?? 0}${domains}`}
          icon={Bot}
          label="Orchestration"
          variant={orchestrationVariant}
        />
      </div>
      <div className="mt-3 grid gap-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950 lg:grid-cols-2">
        <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
          <span>Quota compute</span>
          <input
            className={inputClassName}
            data-testid="control-plane-quota-compute"
            inputMode="decimal"
            onChange={(event) => setDraft((value) => ({ ...value, quotaCompute: event.target.value }))}
            value={draft.quotaCompute}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
          <span>Quota window hours</span>
          <input
            className={inputClassName}
            inputMode="decimal"
            onChange={(event) => setDraft((value) => ({ ...value, quotaWindowHours: event.target.value }))}
            value={draft.quotaWindowHours}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
          <span>Orchestration mode</span>
          <Select
            className="w-full"
            data-testid="control-plane-orchestration-mode"
            onChange={(event) =>
              setDraft((value) => ({
                ...value,
                orchestrationMode: event.target.value === "multi_subagent" ? "multi_subagent" : "default",
              }))
            }
            value={draft.orchestrationMode}
          >
            <option value="default">default</option>
            <option value="multi_subagent">multi_subagent</option>
          </Select>
        </label>
        <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
          <span>Max children</span>
          <input
            className={inputClassName}
            inputMode="numeric"
            onChange={(event) => setDraft((value) => ({ ...value, maxChildren: event.target.value }))}
            value={draft.maxChildren}
          />
        </label>
        <label className="block space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400 lg:col-span-2">
          <span>Allowed domains</span>
          <input
            className={inputClassName}
            onChange={(event) => setDraft((value) => ({ ...value, allowedDomains: event.target.value }))}
            value={draft.allowedDomains}
          />
        </label>
        <div className="flex flex-wrap gap-3 text-xs font-medium text-slate-600 dark:text-zinc-300 lg:col-span-2">
          <label className="inline-flex items-center gap-2">
            <input
              checked={draft.selfRepairEnabled}
              onChange={(event) => setDraft((value) => ({ ...value, selfRepairEnabled: event.target.checked }))}
              type="checkbox"
            />
            self repair
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              checked={draft.selfRepairHealth}
              onChange={(event) => setDraft((value) => ({ ...value, selfRepairHealth: event.target.checked }))}
              type="checkbox"
            />
            health repair
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              checked={draft.selfRepairWaitingProjection}
              onChange={(event) => setDraft((value) => ({ ...value, selfRepairWaitingProjection: event.target.checked }))}
              type="checkbox"
            />
            waiting projection
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              checked={draft.spawnAllowed}
              onChange={(event) => setDraft((value) => ({ ...value, spawnAllowed: event.target.checked }))}
              type="checkbox"
            />
            spawn allowed
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:col-span-2">
          <Button disabled={!dirty} onClick={() => setDraft(currentDraft)} size="sm" variant="ghost">
            <RotateCcw className="h-4 w-4" />
            Reset
          </Button>
          <Button disabled={!canDryRun || isDryRunning} onClick={() => void runDryRunCheck()} size="sm">
            {isDryRunning ? <RefreshCw className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
            Dry-run Check
          </Button>
          <Button disabled={!canApply || isApplying} onClick={() => void applySettings()} size="sm" variant="primary">
            {isApplying ? <RefreshCw className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            Apply registry settings
          </Button>
          <Button disabled={!canCopy} onClick={() => void copyCommand(dryRunCommand)} size="sm">
            <Copy className="h-4 w-4" />
            Copy dry-run
          </Button>
          <Button disabled={!canCopy} onClick={() => void copyCommand(applyCommand)} size="sm" variant="primary">
            <Copy className="h-4 w-4" />
            Copy apply
          </Button>
          {copyState === "copied" ? <Badge variant="success">copied</Badge> : null}
          {copyState === "failed" ? <Badge variant="danger">copy failed</Badge> : null}
          {dryRunError ? <Badge variant="danger">{dryRunError.slice(0, 96)}</Badge> : null}
          {applyError ? <Badge variant="danger">{applyError.slice(0, 96)}</Badge> : null}
        </div>
        {dryRunResult?.ok ? (
          <div
            className="space-y-1 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100 lg:col-span-2"
            data-testid="control-plane-settings-dry-run-result"
          >
            <div>
              changed={String(Boolean(dryRunResult.changed))} · written={String(Boolean(dryRunResult.written))}
              {dryRunResult.preview_id ? ` · preview=${dryRunResult.preview_id}` : ""}
            </div>
            {dryRunResult.changed_fields?.length ? <div>fields={dryRunResult.changed_fields.join(", ")}</div> : null}
            {dryRunResult.control_plane_summary ? <div>{dryRunResult.control_plane_summary}</div> : null}
            {dryRunResult.orchestration_summary ? <div>{dryRunResult.orchestration_summary}</div> : null}
          </div>
        ) : null}
        <pre
          className="overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-950 p-3 text-xs leading-5 text-slate-50 dark:border-zinc-800 lg:col-span-2"
          data-testid="control-plane-settings-command-preview"
        >
          {dryRunCommand || "select a goal"}
        </pre>
      </div>
    </div>
  );
}

type ShareGoalSpec = {
  id: string;
  label: string;
  subtitle: string;
  emphasis: string;
  accent: string;
  icon: React.ComponentType<{ className?: string }>;
};

type EventLedgerClass = keyof EventLedgerSummary["totals"]["by_class_24h"];

type ShareGoalView = {
  agentTodos: TodoGroup | null;
  decisionFreshnessWarnings: DecisionFreshnessItem[];
  eventLedger?: EventLedgerSummary["goals"][number];
  row?: GoalDirectoryRow;
  spec: ShareGoalSpec;
  usage?: UsageSummary["goals"][number];
  userTodos: TodoGroup | null;
};

const shareGoalSpecs: ShareGoalSpec[] = [
  {
    id: "showcase-user-gate-safe-side-path",
    label: "0617 User Gate",
    subtitle: "公开 showcase / safe side path",
    emphasis: "把用户决策、Agent 待办和安全侧路拆开管理：该等人的地方明确等人。",
    accent: "border-t-emerald-500",
    icon: GitBranch,
  },
  {
    id: "showcase-creator-operator",
    label: "Creator Operator",
    subtitle: "合成案例 / 长程内容运营",
    emphasis: "让多个 Agent 围绕热点、素材、洞察和创作 backlog 持续推进，但只展示脱敏 showcase 数据。",
    accent: "border-t-amber-500",
    icon: Gauge,
  },
  {
    id: "showcase-side-agent-self-iteration",
    label: "Side Agent 自迭代",
    subtitle: "公开 repo 事实 / 旁路产品化",
    emphasis: "主控聚焦高风险主线，旁路 Agent 在独立 worktree 中推进产品化、文档和展示。",
    accent: "border-t-rose-500",
    icon: ShieldCheck,
  },
  {
    id: "loopx-meta",
    label: "LoopX Meta",
    subtitle: "控制面自举与稳定性",
    emphasis: "把观察循环转成状态、配额、active-state 的可验证产品改动。",
    accent: "border-t-sky-500",
    icon: Radar,
  },
];

const shareStatusLabel: Record<string, string> = {
  dashboard_home_control_plane_promotion: "主屏已提升",
  dashboard_home_docs_contract_alignment: "主屏文档合约已对齐",
  dashboard_home_route_smoke_contract: "主屏路由合约已验证",
  state_refreshed: "状态已刷新",
  quota_slot_spent: "已记录配额",
  side_bypass_tau2_non_category_profile_admission_sweep: "旁路证据扫描",
};

const shareDeliveryScaleLabel: Record<string, string> = {
  coherent_batch: "成组交付",
  implementation: "实现改动",
  multi_surface: "多面改动",
  single_surface: "单面改动",
  test_only: "仅测试合约",
};

const shareDeliveryOutcomeLabel: Record<string, string> = {
  outcome_gap: "产出差距",
  primary_goal_outcome: "主目标进展",
  surface_only: "仅表层进展",
};

const shareQuotaLabel: Record<string, string> = {
  blocked_health: "健康阻塞",
  eligible: "可自动推进",
  focus_wait: "暂缓不花配额",
  operator_gate: "等待用户决策",
  paused: "已暂停",
  throttled: "quota 已满",
  waiting: "等待下一步",
};

const shareWaitingLabel: Record<string, string> = {
  clear: "无需关注",
  codex: "Agent 可处理",
  controller: "控制器待确认",
  external_evidence: "等待外部证据",
  user_or_controller: "用户待确认",
};

const eventClassLabel: Record<string, string> = {
  accounting: "花费记录",
  decision: "人类决策",
  evidence: "证据观察",
  state: "状态刷新",
  work: "实际推进",
};

const eventClassOrder = ["work", "evidence", "decision", "accounting", "state"] as const;

function cleanShareText(value?: string | null) {
  return (value ?? "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\/Users\/[^\s，。；,;)]+/g, "[local]")
    .replace(/\s+/g, " ")
    .trim();
}

function compactShareText(value?: string | null, limit = 132) {
  const text = cleanShareText(value);
  if (!text) {
    return "暂无";
  }
  return text.length > limit ? `${text.slice(0, limit - 3).trimEnd()}...` : text;
}

function shareMachineLabel(value?: string | null) {
  const raw = value ?? "";
  if (!raw) {
    return "";
  }
  return shareStatusLabel[raw]
    ?? shareDeliveryScaleLabel[raw]
    ?? shareDeliveryOutcomeLabel[raw]
    ?? shareQuotaLabel[raw]
    ?? raw
      .replace(/_/g, " ")
      .replace(/\bquota\b/g, "配额")
      .replace(/\bguard\b/g, "守卫")
      .replace(/\bhandoff\b/g, "交接")
      .replace(/\bstate\b/g, "状态");
}

function shareRowById(rows: GoalDirectoryRow[]) {
  return new Map(rows.map((row) => [row.goal.id, row]));
}

function shareUsageById(usage?: UsageSummary | null) {
  return new Map((usage?.goals ?? []).map((goal) => [goal.goal_id, goal]));
}

function shareEventLedgerById(summary?: EventLedgerSummary | null) {
  return new Map((summary?.goals ?? []).map((goal) => [goal.goal_id, goal]));
}

function shareDecisionFreshnessById(summary?: DecisionFreshnessSummary | null) {
  const grouped = new Map<string, DecisionFreshnessItem[]>();
  for (const item of summary?.items ?? []) {
    if (!item.requires_decision_point_rebase) {
      continue;
    }
    const current = grouped.get(item.goal_id) ?? [];
    current.push(item);
    grouped.set(item.goal_id, current);
  }
  return grouped;
}

function shareDecisionKindLabel(kind?: string | null) {
  if (kind === "human_reward") {
    return "reward";
  }
  if (kind === "operator_gate") {
    return "gate";
  }
  if (kind === "operator_gate_resume_contract") {
    return "resume contract";
  }
  return kind ? shareMachineLabel(kind) : "decision";
}

function shareDecisionFreshnessStateLabel(state?: string | null) {
  if (state === "stale_rebase_required") {
    return "已过期，需 rebase";
  }
  if (state === "rebase_required") {
    return "有后续事件，需 rebase";
  }
  return shareMachineLabel(state) || "需 rebase";
}

function getShareTodos(row: GoalDirectoryRow | undefined, role: "user" | "agent") {
  if (!row) {
    return null;
  }
  const projectAsset = row.queueItem?.project_asset;
  return role === "user"
    ? todosFromProjectAssetSummary(projectAsset?.user_todos, row.queueItem?.user_todos, "project_asset.user_todos")
    : todosFromProjectAssetSummary(projectAsset?.agent_todos, row.queueItem?.agent_todos, "project_asset.agent_todos");
}

function shareTodoCount(todos?: TodoGroup | null) {
  if (!todos || todos.total_count === 0) {
    return "0/0";
  }
  return `${todos.open_count}/${todos.total_count}`;
}

type ShareTodoRole = "user" | "agent";

type ShareTopTodoItem = {
  done: boolean;
  index: number;
  role: ShareTodoRole;
  sourceOrder: number;
  text: string;
};

function shareTodoRoleLabel(role: ShareTodoRole) {
  return role === "user" ? "用户" : "Agent";
}

function shareTodoStatusLabel(todo: ShareTopTodoItem) {
  if (todo.done) {
    return "已完成";
  }
  return todo.role === "user" ? "待用户" : "待 Agent";
}

function shareTodoStatusVariant(todo: ShareTopTodoItem): BadgeVariant {
  if (todo.done) {
    return "success";
  }
  return todo.role === "user" ? "warning" : "info";
}

function shareTopTodoItems(view: ShareGoalView, limit = 4): ShareTopTodoItem[] {
  const groups: Array<[ShareTodoRole, TodoGroup | null]> = [
    ["user", view.userTodos],
    ["agent", view.agentTodos],
  ];
  return groups
    .flatMap(([role, group]) => (group?.items ?? []).map((todo, sourceOrder) => ({
      done: todo.done,
      index: todo.index,
      role,
      sourceOrder,
      text: todo.text,
    })))
    .sort((left, right) => {
      const leftPriority = (left.done ? 2 : 0) + (left.role === "agent" ? 1 : 0);
      const rightPriority = (right.done ? 2 : 0) + (right.role === "agent" ? 1 : 0);
      return leftPriority - rightPriority
        || left.sourceOrder - right.sourceOrder
        || left.index - right.index;
    })
    .slice(0, limit);
}

function ShareTopTodoList({
  className,
  compact = false,
  view,
}: {
  className?: string;
  compact?: boolean;
  view: ShareGoalView;
}) {
  const todos = shareTopTodoItems(view);
  if (todos.length === 0) {
    return (
      <div className={cn("rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500", className)}>
        当前没有可展示的项目 todo。
      </div>
    );
  }
  return (
    <div className={cn("space-y-2", className)} data-testid={`share-top-todos-${view.spec.id}`}>
      {todos.map((todo, itemIndex) => {
        const StatusIcon = todo.done ? CheckCircle2 : Clock3;
        return (
          <div
            className={cn(
              "rounded-md border px-3 py-2",
              todo.done ? "border-emerald-200 bg-emerald-50/70" : "border-slate-200 bg-white",
            )}
            key={`${todo.role}-${todo.index}-${itemIndex}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={todo.role === "user" ? "warning" : "info"}>{shareTodoRoleLabel(todo.role)}</Badge>
              <Badge variant={shareTodoStatusVariant(todo)}>
                <StatusIcon className="h-3 w-3" />
                {shareTodoStatusLabel(todo)}
              </Badge>
              <span className="text-[11px] font-medium text-slate-500">#{todo.index}</span>
            </div>
            <p className={cn("mt-1 break-words text-sm leading-6 text-slate-700", compact ? "line-clamp-2" : "line-clamp-3")}>
              {compactShareText(todo.text, compact ? 112 : 152)}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function ShareDependencyBlockerList({
  className,
  compact = false,
  view,
}: {
  className?: string;
  compact?: boolean;
  view: ShareGoalView;
}) {
  const blockers = view.row?.queueItem?.dependency_blockers;
  const items = blockers?.items ?? [];
  if (!blockers || blockers.open_count === 0 || items.length === 0) {
    return null;
  }
  return (
    <div className={cn("space-y-2", className)} data-testid={`share-dependency-blockers-${view.spec.id}`}>
      {items.slice(0, compact ? 2 : 4).map((blocker, itemIndex) => (
        <div
          className="rounded-md border border-amber-200 bg-amber-50/70 px-3 py-2"
          key={`${blocker.goal_id}-${blocker.index ?? itemIndex}`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="warning">依赖阻塞</Badge>
            <span className="break-all text-[11px] font-semibold text-amber-700">{blocker.goal_id}</span>
            {blocker.waiting_on ? (
              <span className="text-[11px] font-medium text-amber-700">
                {shareWaitingLabel[blocker.waiting_on] ?? shareMachineLabel(blocker.waiting_on)}
              </span>
            ) : null}
          </div>
          <p className={cn("mt-1 break-words text-sm leading-6 text-amber-950", compact ? "line-clamp-2" : "line-clamp-3")}>
            {compactShareText(blocker.text, compact ? 108 : 148)}
          </p>
        </div>
      ))}
      {blockers.open_count > items.length ? (
        <div className="text-[11px] font-medium text-amber-700">
          另有 {blockers.open_count - items.length} 项依赖阻塞未展开。
        </div>
      ) : null}
    </div>
  );
}

function ShareDecisionFreshnessWarning({
  className,
  compact = false,
  view,
}: {
  className?: string;
  compact?: boolean;
  view: ShareGoalView;
}) {
  const items = view.decisionFreshnessWarnings;
  if (items.length === 0) {
    return null;
  }
  const visible = items.slice(0, compact ? 1 : 2);
  return (
    <div className={cn("space-y-2", className)} data-testid={`share-decision-freshness-${view.spec.id}`}>
      {visible.map((item, itemIndex) => (
        <div
          className="rounded-md border border-amber-200 bg-amber-50/80 px-3 py-2"
          key={`${item.decision_kind ?? "decision"}-${item.decision_at ?? itemIndex}`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="warning">决策需 rebase</Badge>
            <span className="text-[11px] font-semibold text-amber-700">
              {shareDecisionKindLabel(item.decision_kind)}
            </span>
            <span className="text-[11px] font-medium text-amber-700">
              {shareDecisionFreshnessStateLabel(item.freshness_state)}
            </span>
          </div>
          <p className={cn("mt-1 break-words text-sm leading-6 text-amber-950", compact ? "line-clamp-2" : "line-clamp-3")}>
            {compact
              ? "审批或转交前先重读当前控制面状态；这不是仓库回滚。"
              : "审批或转交前先重读 registry / active state / quota / run status；旧聊天或旧 gate 不能直接当当前授权，这不是仓库回滚。"}
          </p>
          <div className="mt-1 flex flex-wrap gap-2 text-[11px] font-medium text-amber-700">
            <span>7d 新事件 {item.newer_event_count_7d ?? 0}</span>
            {item.age_days != null ? <span>决策年龄 {Math.round(item.age_days)}d</span> : null}
          </div>
        </div>
      ))}
      {items.length > visible.length ? (
        <div className="text-[11px] font-medium text-amber-700">
          另有 {items.length - visible.length} 个旧决策需要 rebase。
        </div>
      ) : null}
    </div>
  );
}

function shareOpenTotal(views: ShareGoalView[], role: "user" | "agent") {
  return views.reduce(
    (total, view) => {
      const todos = role === "user" ? view.userTodos : view.agentTodos;
      return {
        open: total.open + (todos?.open_count ?? 0),
        total: total.total + (todos?.total_count ?? 0),
      };
    },
    { open: 0, total: 0 },
  );
}

function quotaStateForShare(row?: GoalDirectoryRow) {
  return row?.queueItem?.project_asset?.quota?.state ?? row?.queueItem?.quota?.state ?? row?.goal.quota?.state ?? "waiting";
}

function quotaForShare(row?: GoalDirectoryRow) {
  return row?.queueItem?.project_asset?.quota ?? row?.queueItem?.quota ?? row?.goal.quota;
}

function shareStatusForGoal(view: ShareGoalView): { label: string; summary: string; variant: BadgeVariant } {
  const quota = quotaForShare(view.row);
  const quotaState = quota?.state ?? "waiting";
  if (!view.row) {
    return {
      label: "未接入",
      summary: "全局状态里还没有这个目标的 current projection。",
      variant: "neutral",
    };
  }
  if (isOutcomeFloorRecoveryQuota(quota)) {
    const gap = view.row.queueItem?.handoff_readiness?.post_handoff_outcome_gap_streak ?? quota?.post_handoff_outcome_gap_streak ?? 0;
    return {
      label: "需要 Codex recovery",
      summary: `连续 ${gap || 1} 次产出差距；下一步只做 ${recoveryEvidenceLabel(quota)}，或写回具体阻塞。`,
      variant: "warning",
    };
  }
  if (view.spec.id === "showcase-user-gate-safe-side-path" && (view.userTodos?.open_count ?? 0) > 0) {
    return {
      label: "用户待办已捕获",
      summary: "用户决策被单独留给 owner；Agent 只推进与该决策独立的安全侧路。",
      variant: "warning",
    };
  }
  if (view.spec.id === "showcase-creator-operator") {
    return {
      label: "合成场景主动推进",
      summary: "创作运营 backlog 可持续推进，但前台只呈现公开 showcase 和合成数据。",
      variant: "info",
    };
  }
  if (view.spec.id === "loopx-meta") {
    return {
      label: "控制面健康",
      summary: "全局注册表、配额守卫、active-state 刷新处于可观测闭环。",
      variant: "success",
    };
  }
  if (quotaState === "eligible") {
    return {
      label: "可自动推进",
      summary: "当前没有用户闸门，Agent 可做一个有边界、有验证、有写回的小段推进。",
      variant: "success",
    };
  }
  return {
    label: shareQuotaLabel[quotaState] ?? shareMachineLabel(quotaState),
    summary: compactShareText(quota?.reason ?? view.row.queueItem?.recommended_action, 118),
    variant: quotaVariant(quotaState),
  };
}

function ShareDecisionFrame({
  status,
  view,
}: {
  status: ReturnType<typeof shareStatusForGoal>;
  view: ShareGoalView;
}) {
  const projectAsset = view.row?.queueItem?.project_asset;
  const waitingOwnerRaw = projectAsset?.owner ?? view.row?.waitingOn ?? "clear";
  const waitingOwner = shareWaitingLabel[waitingOwnerRaw] ?? (shareMachineLabel(waitingOwnerRaw) || waitingOwnerRaw);
  const recommendedAction = projectAsset?.next_action ?? view.row?.queueItem?.recommended_action ?? status.summary;
  const safetyBoundary = projectAsset?.stop_condition
    ?? view.row?.queueItem?.next_handoff_condition
    ?? "未显式授权写入或生产动作；只按当前 quota / handoff 边界推进。";
  const firstUserTodo = firstOpenTodo(view.userTodos);
  const firstAgentTodo = firstOpenTodo(view.agentTodos);
  const missingTodoRoles = projectAsset?.todo_projection_gap?.missing_roles?.length
    ? projectAsset.todo_projection_gap.missing_roles.join(", ")
    : null;

  const rows: Array<readonly [string, string]> = [
    ["等待方", waitingOwner],
    ["推荐动作", compactShareText(recommendedAction, 108)],
    ["安全边界", compactShareText(safetyBoundary, 108)],
    ["首个用户 Todo", compactShareText(firstUserTodo?.text, 108)],
    ["最高优 Agent Todo", compactShareText(firstAgentTodo?.text, 108)],
  ];
  if (missingTodoRoles) {
    rows.push(["Todo 投影缺口", `missing roles: ${missingTodoRoles}`]);
  }

  return (
    <div
      className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3"
      data-testid={`share-decision-frame-${view.spec.id}`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge variant="neutral">第一屏决策帧</Badge>
        <span className="text-[11px] font-medium text-slate-500">先看等谁、能否推进、边界和下一步。</span>
      </div>
      <div className="grid gap-2 text-xs leading-5">
        {rows.map(([label, value]) => (
          <div className="grid grid-cols-[92px_minmax(0,1fr)] gap-2" key={label}>
            <div className="font-semibold text-slate-500">{label}</div>
            <div className="line-clamp-2 break-words font-medium text-slate-800">{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function shareStatusText(row?: GoalDirectoryRow) {
  if (!row) {
    return "未接入";
  }
  return shareMachineLabel(row.status);
}

function ShareKpi({
  icon: Icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  tone?: "neutral" | "success" | "warning" | "info" | "danger";
}) {
  const toneClass = {
    neutral: "border-slate-200 bg-white text-slate-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-950",
    warning: "border-amber-200 bg-amber-50 text-amber-950",
    info: "border-sky-200 bg-sky-50 text-sky-950",
    danger: "border-rose-200 bg-rose-50 text-rose-950",
  }[tone];
  return (
    <div className={cn("min-h-28 rounded-lg border px-4 py-3", toneClass)}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-current/70">{label}</div>
        <Icon className="h-4 w-4 text-current/60" />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-normal">{value}</div>
      <div className="mt-1 text-xs leading-5 text-current/70">{detail}</div>
    </div>
  );
}

function ShareProjectCard({ view }: { view: ShareGoalView }) {
  const Icon = view.spec.icon;
  const status = shareStatusForGoal(view);
  const quota = quotaForShare(view.row);
  const usage = view.usage;
  const dependencyBlockers = view.row?.queueItem?.dependency_blockers;
  const readiness = view.row?.queueItem?.handoff_readiness;
  const latest = readiness?.post_handoff_latest_run;
  const lastEvidence = latest
    ? [
      shareMachineLabel(latest.classification),
      latest.delivery_batch_scale ? `规模 ${shareMachineLabel(latest.delivery_batch_scale)}` : null,
      latest.delivery_outcome ? `结果 ${shareMachineLabel(latest.delivery_outcome)}` : null,
    ].filter(Boolean).join(" · ")
    : shareStatusText(view.row);

  return (
    <article
      className={cn(
        "grid min-h-[520px] content-between rounded-lg border border-slate-200 bg-white p-4 shadow-sm",
        "border-t-4",
        view.spec.accent,
      )}
      data-goal-id={view.spec.id}
    >
      <div className="min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Icon className="h-4 w-4 text-slate-600" />
              <h3 className="text-xl font-semibold tracking-normal text-slate-950">{view.spec.label}</h3>
            </div>
            <p className="mt-1 text-sm font-medium text-slate-500">{view.spec.subtitle}</p>
          </div>
          <Badge variant={status.variant}>{status.label}</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-700">{view.spec.emphasis}</p>
        <ShareDecisionFrame status={status} view={view} />

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2">
            <div className="text-lg font-semibold text-slate-950">{shareTodoCount(view.userTodos)}</div>
            <div className="text-[11px] font-medium text-slate-500">用户待办</div>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2">
            <div className="text-lg font-semibold text-slate-950">{shareTodoCount(view.agentTodos)}</div>
            <div className="text-[11px] font-medium text-slate-500">Agent 待办</div>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2">
            <div className="text-lg font-semibold text-slate-950">{usage?.progress_signal_run_count_24h ?? 0}</div>
            <div className="text-[11px] font-medium text-slate-500">24h 进展</div>
          </div>
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-xs font-semibold text-slate-500">Top-4 Todo</div>
            <div className="flex flex-wrap gap-1">
              <Badge variant="warning">待用户</Badge>
              <Badge variant="info">待 Agent</Badge>
              <Badge variant="success">已完成</Badge>
              {dependencyBlockers?.open_count ? <Badge variant="warning">依赖 {dependencyBlockers.open_count}</Badge> : null}
            </div>
          </div>
          <ShareTopTodoList view={view} />
          <ShareDependencyBlockerList className="mt-2" view={view} />
          <ShareDecisionFreshnessWarning className="mt-2" view={view} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3">
        <Badge variant={quotaVariant(quota?.state)}>{shareQuotaLabel[quota?.state ?? "waiting"] ?? (shareMachineLabel(quota?.state) || "等待下一步")}</Badge>
        <Badge variant="neutral">{shareWaitingLabel[view.row?.waitingOn ?? "clear"] ?? shareMachineLabel(view.row?.waitingOn)}</Badge>
        <Badge variant={view.row?.queueItem?.handoff_readiness?.ready ? "success" : "warning"}>
          {view.row?.queueItem?.handoff_readiness?.ready ? "handoff 可执行" : "handoff 受控"}
        </Badge>
        <span className="line-clamp-1 min-w-0 flex-1 text-xs text-slate-500">{lastEvidence}</span>
      </div>
    </article>
  );
}

function ShareTodoMatrix({ views }: { views: ShareGoalView[] }) {
  return (
    <section
      className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm"
      data-testid="share-todo-matrix"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-normal text-slate-950">Todo 责任矩阵</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            重点不是把所有项目都自动化掉，而是把“该人判断”和“该 Agent 推进”分清楚。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="warning">待用户</Badge>
          <Badge variant="info">待 Agent</Badge>
          <Badge variant="success">已完成</Badge>
        </div>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border border-slate-200">
        <div className="grid grid-cols-[170px_minmax(0,1fr)_220px] gap-0 bg-slate-50 text-xs font-semibold text-slate-500">
          <div className="px-3 py-2">项目</div>
          <div className="px-3 py-2">Top-4 Todo（含状态）</div>
          <div className="px-3 py-2 text-right">控制状态</div>
        </div>
        <div className="divide-y divide-slate-200">
          {views.map((view) => {
            const status = shareStatusForGoal(view);
            const dependencyOpen = view.row?.queueItem?.dependency_blockers?.open_count ?? 0;
            return (
              <div
                className="grid min-h-[180px] grid-cols-[170px_minmax(0,1fr)_220px] gap-0 bg-white"
                key={view.spec.id}
              >
                <div className="px-3 py-3">
                  <div className="text-sm font-semibold text-slate-950">{view.spec.label}</div>
                  <div className="mt-1 text-[11px] leading-4 text-slate-500">{view.spec.subtitle}</div>
                </div>
                <div className="border-l border-slate-200 px-3 py-3">
                  <ShareTopTodoList compact view={view} />
                  <div className="mt-2 flex flex-wrap gap-2 text-xs font-medium">
                    <span className="text-amber-700">用户 {shareTodoCount(view.userTodos)}</span>
                    <span className="text-sky-700">Agent {shareTodoCount(view.agentTodos)}</span>
                    {dependencyOpen > 0 ? <span className="text-amber-700">依赖阻塞 {dependencyOpen}</span> : null}
                  </div>
                  <ShareDependencyBlockerList className="mt-2" compact view={view} />
                  <ShareDecisionFreshnessWarning className="mt-2" compact view={view} />
                </div>
                <div className="border-l border-slate-200 px-3 py-3 text-right">
                  <Badge variant={status.variant}>{status.label}</Badge>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-500">{status.summary}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

type ShareSignalTone = "rose" | "amber" | "emerald";

function ShareSignalCard({
  body,
  icon: Icon,
  metrics,
  status,
  steps,
  title,
  tone,
}: {
  body: string;
  icon: React.ComponentType<{ className?: string }>;
  metrics: { label: string; value: string }[];
  status: { label: string; variant: BadgeVariant };
  steps: { label: string; value: string }[];
  title: string;
  tone: ShareSignalTone;
}) {
  const toneClass = {
    rose: {
      border: "border-rose-200",
      header: "bg-rose-50 text-rose-950",
      icon: "bg-rose-100 text-rose-700",
      rule: "border-rose-200",
      text: "text-rose-950",
    },
    amber: {
      border: "border-amber-200",
      header: "bg-amber-50 text-amber-950",
      icon: "bg-amber-100 text-amber-700",
      rule: "border-amber-200",
      text: "text-amber-950",
    },
    emerald: {
      border: "border-emerald-200",
      header: "bg-emerald-50 text-emerald-950",
      icon: "bg-emerald-100 text-emerald-700",
      rule: "border-emerald-200",
      text: "text-emerald-950",
    },
  }[tone];

  return (
    <article className={cn("overflow-hidden rounded-xl border bg-white shadow-sm", toneClass.border)}>
      <div className={cn("flex min-h-[82px] items-start justify-between gap-3 px-5 py-4", toneClass.header)}>
        <div className="flex min-w-0 items-start gap-3">
          <div className={cn("mt-0.5 rounded-lg p-2", toneClass.icon)}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold tracking-normal">{title}</h2>
            <p className={cn("mt-1 text-sm leading-6", toneClass.text)}>{body}</p>
          </div>
        </div>
        <Badge variant={status.variant}>{status.label}</Badge>
      </div>

      <div className="px-5 py-4">
        <div className="grid grid-cols-3 gap-2">
          {metrics.map((metric) => (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" key={metric.label}>
              <div className="text-[11px] font-medium text-slate-500">{metric.label}</div>
              <div className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-slate-950">{metric.value}</div>
            </div>
          ))}
        </div>
        <div className={cn("mt-4 grid grid-cols-3 gap-0 overflow-hidden rounded-lg border", toneClass.rule)}>
          {steps.map((step, index) => (
            <div
              className={cn(
                "bg-white px-3 py-3",
                index > 0 && "border-l",
                toneClass.rule,
              )}
              key={step.label}
            >
              <div className="text-[11px] font-semibold text-slate-500">{step.label}</div>
              <div className="mt-1 text-sm font-medium leading-5 text-slate-800">{step.value}</div>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

function ShareGuardEvidence({
  payload,
  views,
}: {
  payload: StatusPayload;
  views: ShareGoalView[];
}) {
  const side = views.find((view) => view.spec.id === "showcase-side-agent-self-iteration");
  const creator = views.find((view) => view.spec.id === "showcase-creator-operator");
  const meta = views.find((view) => view.spec.id === "loopx-meta");
  const gate = views.find((view) => view.spec.id === "showcase-user-gate-safe-side-path");
  const sideGap = side?.row?.queueItem?.handoff_readiness?.post_handoff_outcome_gap_streak
    ?? side?.row?.queueItem?.quota?.post_handoff_outcome_gap_streak
    ?? 0;
  const creatorUsage = creator?.usage;
  const metaUsage = meta?.usage;

  return (
    <section
      className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm"
      data-testid="share-guard-evidence"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-normal text-slate-950">Guard / Evidence 控制信号</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            控制面的价值不是继续制造 todo，而是把何时停、何时推进、何时写回变成同一套证据。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="warning">配额守卫</Badge>
          <Badge variant="info">证据等待</Badge>
          <Badge variant="success">状态写回</Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
        <ShareSignalCard
          body={`连续 ${sideGap || 3} 次产出差距后，控制面暂停自动消耗；没有排序器 / 跨域证据，只能给阻塞说明。`}
          icon={ShieldCheck}
          metrics={[
            { label: "触发阈值", value: `${sideGap || 3} 次产出差距` },
            { label: "禁止路径", value: "单面改动" },
            { label: "允许输出", value: "阻塞说明" },
          ]}
          status={{ label: "no-spend 暂缓", variant: "warning" }}
          steps={[
            { label: "触发", value: "表层小步重复" },
            { label: "控制", value: "暂缓不花 quota" },
            { label: "写回", value: "证据或 blocker" },
          ]}
          title="旁路：防止重复小步"
          tone="rose"
        />

        <ShareSignalCard
          body={`24h 已花 ${creatorUsage?.quota_spend_slots_24h ?? 0} 个配额槽，进展信号 ${creatorUsage?.progress_signal_run_count_24h ?? 0}；创作运营推进必须落到任务、证据、回顾或可展示产物。`}
          icon={Gauge}
          metrics={[
            { label: "24h quota", value: `${creatorUsage?.quota_spend_slots_24h ?? 0} slots` },
            { label: "素材 backlog", value: "热点 / 洞察 / 语料" },
            { label: "展示边界", value: "synthetic-only" },
          ]}
          status={{ label: "主动推进", variant: "info" }}
          steps={[
            { label: "触发", value: "长期创作目标" },
            { label: "控制", value: "配额 + 证据边界" },
            { label: "写回", value: "showcase + backlog" },
          ]}
          title="Creator Operator：昼夜不断的合成运营队列"
          tone="amber"
        />

        <ShareSignalCard
          body={`User-gate showcase 保留 ${gate?.userTodos?.open_count ?? 0} 个 owner 决策；Meta 24h 进展信号 ${metaUsage?.progress_signal_run_count_24h ?? 0}，当前合约错误 ${payload.contract.summary.errors}。`}
          icon={FileCheck2}
          metrics={[
            { label: "公开 user gate", value: `${gate?.userTodos?.open_count ?? 0} open` },
            { label: "Meta 进展", value: `${metaUsage?.progress_signal_run_count_24h ?? 0} signals` },
            { label: "全局发现", value: `${payload.global_registry.summary.findings} findings` },
          ]}
          status={{ label: "已验证", variant: "success" }}
          steps={[
            { label: "触发", value: "状态刷新" },
            { label: "控制", value: "registry 真相源" },
            { label: "写回", value: "active-state 写回" },
          ]}
          title="Showcase + Meta：状态真相"
          tone="emerald"
        />
      </div>
    </section>
  );
}

function ShareAutonomousBacklog({
  summary,
}: {
  summary?: StatusPayload["attention_queue"]["autonomous_backlog_candidates"];
}) {
  const items = summary?.items ?? [];
  if (!summary || summary.open_count === 0 || items.length === 0) {
    return null;
  }
  return (
    <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3" data-testid="share-autonomous-backlog">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-sky-700" />
          <div className="text-sm font-semibold text-sky-950">可自动推进候选</div>
        </div>
        <Badge variant="info">{summary.open_count}</Badge>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {items.slice(0, 3).map((candidate, index) => (
          <div className="rounded-md border border-sky-200 bg-white px-3 py-2" key={`${candidate.goal_id}-${candidate.todo_index ?? index}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="break-all text-[11px] font-semibold text-sky-700">{candidate.goal_id}</span>
              {candidate.priority ? <Badge variant="info">{candidate.priority}</Badge> : null}
            </div>
            <p className="mt-1 line-clamp-2 break-words text-sm leading-6 text-slate-700">
              {compactShareText(candidate.text, 118)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function eventClassCount(
  counts: EventLedgerSummary["totals"]["by_class_24h"] | EventLedgerSummary["totals"]["by_class_7d"] | undefined,
  eventClass: EventLedgerClass,
) {
  return counts?.[eventClass] ?? 0;
}

function EventClassPill({
  counts,
  eventClass,
}: {
  counts?: EventLedgerSummary["totals"]["by_class_24h"] | EventLedgerSummary["totals"]["by_class_7d"];
  eventClass: EventLedgerClass;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-center shadow-sm">
      <div className="text-lg font-semibold text-slate-950">{eventClassCount(counts, eventClass)}</div>
      <div className="mt-0.5 text-[11px] font-medium text-slate-500">{eventClassLabel[eventClass]}</div>
    </div>
  );
}

function ShareEventLedgerStrip({ summary }: { summary?: EventLedgerSummary | null }) {
  if (!summary?.available) {
    return null;
  }
  const totals = summary.totals;
  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3" data-testid="share-event-ledger">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-slate-700" />
          <div>
            <div className="text-sm font-semibold text-slate-950">控制面事件账本投影</div>
            <p className="mt-0.5 text-xs leading-5 text-slate-500">
              Chat thread 只是 worker；这里展示的是 run history 的 compact 事件投影。
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="neutral">{summary.source}</Badge>
          <Badge variant="info">{summary.sample_run_count} samples</Badge>
          <Badge variant="success">24h {totals.events_24h}</Badge>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-5">
        {eventClassOrder.map((eventClass) => (
          <EventClassPill counts={totals.by_class_24h} eventClass={eventClass} key={eventClass} />
        ))}
      </div>
    </div>
  );
}

function ShareEvidenceView({
  isLoading,
  onRefresh,
  payload,
  rows,
  source,
  theme,
  toggleTheme,
}: {
  isLoading: boolean;
  onRefresh: () => void;
  payload: StatusPayload;
  rows: GoalDirectoryRow[];
  source: DataSource;
  theme: "light" | "dark";
  toggleTheme: () => void;
}) {
  const rowById = shareRowById(rows);
  const eventLedgerById = shareEventLedgerById(payload.event_ledger_summary);
  const decisionFreshnessById = shareDecisionFreshnessById(payload.decision_freshness_summary);
  const usageById = shareUsageById(payload.usage_summary);
  const views = shareGoalSpecs.map((spec): ShareGoalView => {
    const row = rowById.get(spec.id);
    return {
      agentTodos: getShareTodos(row, "agent"),
      decisionFreshnessWarnings: decisionFreshnessById.get(spec.id) ?? [],
      eventLedger: eventLedgerById.get(spec.id),
      row,
      spec,
      usage: usageById.get(spec.id),
      userTodos: getShareTodos(row, "user"),
    };
  });
  const userOpenTotal = shareOpenTotal(views, "user");
  const agentOpenTotal = shareOpenTotal(views, "agent");
  const blockedCount = views.filter((view) => shareStatusForGoal(view).label.includes("暂缓")).length;
  const automation = payload.usage_summary?.totals.automation_run_count_24h ?? 0;
  const ledgerTotals = payload.event_ledger_summary?.totals;
  const progress = payload.usage_summary?.totals.progress_signal_run_count_24h ?? 0;
  const ledgerWork = eventClassCount(ledgerTotals?.by_class_24h, "work");
  const ledgerEvidence = eventClassCount(ledgerTotals?.by_class_24h, "evidence");

  return (
    <div className={theme === "dark" ? "dark" : ""}>
      <main className="min-h-screen bg-[#f7f7f4] text-slate-950">
        <div className="mx-auto max-w-[1500px] space-y-5 px-5 py-5">
          <section
            className="rounded-2xl border border-slate-200 bg-white px-4 py-5 shadow-sm sm:px-6 sm:py-6"
            data-testid="share-overview"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-3xl">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success">LoopX 控制面</Badge>
                  <Badge variant="neutral">公开 showcase</Badge>
                  <Badge variant={payload.ok ? "success" : "danger"}>{payload.ok ? "状态健康" : "健康阻塞"}</Badge>
                </div>
                <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-normal text-slate-950 sm:text-4xl sm:leading-tight">
                  把多项目 Agent 工作变成可管理的 Todo、证据和配额
                </h1>
                <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
                  这个看板只展示公开 showcases：user gate、side-agent 自迭代、creator operator 和 LoopX Meta 统一到同一套控制面。
                  用户待办单独挂起，Agent 高优任务继续推进，配额守卫和交接合约负责防止重复空转。
                </p>
              </div>
              <div className="flex gap-2">
                <Button disabled={isLoading} onClick={toggleTheme} variant="secondary">
                  {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                  主题
                </Button>
                <Button disabled={isLoading} onClick={onRefresh} variant="primary">
                  <RefreshCw className="h-4 w-4" />
                  刷新证据
                </Button>
              </div>
            </div>

            <div className="mt-4">
              <StatusContractFreshnessWarning payload={payload} source={source} />
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <ShareKpi
                detail="分享重点项目"
                icon={GitBranch}
                label="覆盖项目"
                value={String(views.length)}
              />
              <ShareKpi
                detail="打开 / 总数"
                icon={Users}
                label="用户待办"
                tone={userOpenTotal.open > 0 ? "warning" : "success"}
                value={`${userOpenTotal.open}/${userOpenTotal.total}`}
              />
              <ShareKpi
                detail="打开 / 总数"
                icon={Bot}
                label="Agent 待办"
                tone={agentOpenTotal.open > 0 ? "info" : "success"}
                value={`${agentOpenTotal.open}/${agentOpenTotal.total}`}
              />
              <ShareKpi
                detail={`${progress} 个进展信号；ledger work ${ledgerWork}`}
                icon={Gauge}
                label="24h 自动回合"
                tone="info"
                value={String(automation)}
              />
              <ShareKpi
                detail={`${ledgerEvidence} 个证据观察；重复小步会被拦住`}
                icon={ShieldCheck}
                label="暂缓不花配额"
                tone={blockedCount > 0 ? "warning" : "success"}
                value={String(blockedCount)}
              />
            </div>

            <ShareAutonomousBacklog summary={payload.attention_queue.autonomous_backlog_candidates} />
            <ShareEventLedgerStrip summary={payload.event_ledger_summary} />

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              {views.map((view) => (
                <ShareProjectCard key={view.spec.id} view={view} />
              ))}
            </div>
          </section>

          <ShareTodoMatrix views={views} />
          <ShareGuardEvidence payload={payload} views={views} />
        </div>
      </main>
    </div>
  );
}

function buildHumanFriendlyActionPacket({
  item,
  registry,
  runtimeRoot,
}: {
  item: UserActionSummaryItem;
  registry: string;
  runtimeRoot: string;
}) {
  const prompt = humanReviewPrompt(item.kind);
  const quotaView = buildQuotaView(item.quota);
  const handoffReadiness = buildHandoffReadinessView(item.handoffReadiness);
  const todo = firstOpenTodo(item.userTodos);
  const agentTodo = firstOpenTodo(item.agentTodos);
  const approvedAgentCommand = item.kind === "codex" && Boolean(item.agentCommand);
  const isFocusWait = isFocusWaitQuota(item.quota);
  const isRecoveryFocusWait = isOutcomeFloorRecoveryQuota(item.quota);
  const command = isFocusWait
    ? buildStatusCommand({ registry, runtimeRoot })
    : item.safePathCommand ?? item.agentCommand ?? buildStatusCommand({ registry, runtimeRoot });
  if (isRecoveryFocusWait) {
    const evidenceLabel = recoveryEvidenceLabel(item.quota);
    return buildActionPacket({
      goalId: item.goalId,
      title: item.title,
      summary: item.summary,
      userTodoText: todo?.text,
      agentTodoText: agentTodo?.text ?? `只做一次 ${evidenceLabel} recovery；如果证据范围不可用，写回具体 blocker 后停止。`,
      todoBlocksGate: false,
      operatorQuestion: null,
      suggestedReply: `执行一次 outcome-floor recovery：只做 ${evidenceLabel} 或具体 blocker 写回；完成验证和状态写回后再记一次 quota。`,
      gateFallbackDecision: `执行一次 outcome-floor recovery：只做 ${evidenceLabel} 或具体 blocker 写回。`,
      boundary: "普通 delivery 仍被 outcome floor 阻塞；不要继续 summary/queue/contract 等表层传播，也不要做 synthetic-only 测试链。",
      durableRecordRule: "记录规则：validated evidence/blocker -> refresh-state/run event -> quota spend once；没有完成 recovery artifact 就不 spend。",
      safePathLabel: item.safePathLabel || "Recovery handoff",
      command: item.safePathCommand ?? command,
      quotaShortLine: quotaView?.shortLine,
      authorityShortLine: item.authorityCoverage?.shortLine,
      projectOwner: item.projectOwner,
      projectGate: item.projectGate,
      projectNextAction: item.projectNextAction,
      projectStopCondition: item.projectStopCondition,
      projectAssetSource: item.projectAssetSource,
      handoffReadinessLine: handoffReadiness?.shortLine,
    });
  }
  if (isFocusWait) {
    return buildActionPacket({
      goalId: item.goalId,
      title: item.title,
      summary: item.summary,
      userTodoText: todo?.text,
      agentTodoText: agentTodo?.text ?? "只检查当前 state/status/history；保持 focus_wait 并用中文回报仍在等待什么。",
      todoBlocksGate: false,
      operatorQuestion: null,
      suggestedReply: "继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。",
      gateFallbackDecision: "继续保持 focus wait；有新 owner evidence、clean baseline 或外部 eval 后再恢复 delivery。",
      boundary: "这不是 delivery approval；项目 Agent 只做 status/history inspection，不执行交付路径、写入、reward append 或生产动作。",
      durableRecordRule: null,
      safePathLabel: "Status/history inspection only",
      command,
      quotaShortLine: quotaView?.shortLine,
      authorityShortLine: item.authorityCoverage?.shortLine,
      projectOwner: item.projectOwner,
      projectGate: item.projectGate,
      projectNextAction: item.projectNextAction,
      projectStopCondition: item.projectStopCondition,
      projectAssetSource: item.projectAssetSource,
      handoffReadinessLine: handoffReadiness?.shortLine,
    });
  }
  if (approvedAgentCommand && item.agentCommand) {
    return buildApprovedAgentHandoff({
      goalId: item.goalId,
      command: item.agentCommand,
      agentTodoText: agentTodo?.text,
      projectNextAction: item.projectNextAction,
      projectStopCondition: item.projectStopCondition,
      projectAssetSource: item.projectAssetSource,
    });
  }
  const reply = item.kind === "controller"
    ? controllerReplyLine(item.goalId)
    : approvedAgentCommand
      ? "转发下方【给项目 Agent】即可。"
      : prompt.reply;
  const todoBlocksGate = Boolean(todo && item.operatorQuestion);
  return buildActionPacket({
    goalId: item.goalId,
    title: item.title,
    summary: item.summary,
    userTodoText: todo?.text,
    agentTodoText: agentTodo?.text,
    todoBlocksGate,
    operatorQuestion: item.operatorQuestion,
    suggestedReply: reply,
    gateFallbackDecision: approvedAgentCommand
      ? "直接转发给项目 Agent；不追加写权限、主控接管或生产动作授权。"
      : suggestedDecisionLine(item.kind, item, item.goalId),
    boundary: approvedAgentCommand
      ? "只执行已批准的只读/dry-run agent_command；如需写入或更高权限，项目 Agent 必须再次停下。"
      : prompt.boundary,
    durableRecordRule: durableOperatorGateRecordRule(item.kind),
    safePathLabel: approvedAgentCommand ? "Approved agent command" : item.safePathLabel,
    command,
    quotaShortLine: quotaView?.shortLine,
    authorityShortLine: item.authorityCoverage?.shortLine,
    projectOwner: item.projectOwner,
    projectGate: item.projectGate,
    projectNextAction: item.projectNextAction,
    projectStopCondition: item.projectStopCondition,
    projectAssetSource: item.projectAssetSource,
    handoffReadinessLine: handoffReadiness?.shortLine,
  });
}

function readinessVariant(readiness: ControllerReadiness): "success" | "warning" | "info" {
  if (readiness.decision_advisor_ready) {
    return "success";
  }
  if (readiness.read_only_observer_ready) {
    return "info";
  }
  return "warning";
}

function humanizeIdentifier(value: string) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function gateLabel(value: string) {
  const labels: Record<string, string> = {
    human_reward_capture: "Record human reward",
    aligned_eval_decision_evidence: "Wait for comparable evidence",
    durable_goal_context: "Keep durable goal context",
  };
  return labels[value] ?? humanizeIdentifier(value);
}

function buildStatusCommand({
  registry,
  runtimeRoot,
}: {
  registry: string;
  runtimeRoot: string;
}) {
  return [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  --format json \\",
    "  status",
  ].join("\n");
}

function buildHistoryCommand({
  goalId,
  registry,
  runtimeRoot,
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
}) {
  return [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  history \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    "  --limit 3",
  ].join("\n");
}

function buildReadOnlyMapDryRunCommand({
  goalId,
  registry,
  runtimeRoot,
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
}) {
  return [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  read-only-map \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    "  --dry-run",
  ].join("\n");
}

function buildRefreshStateDryRunCommand({
  goalId,
  registry,
  runtimeRoot,
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
}) {
  return [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  refresh-state \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    "  --dry-run",
  ].join("\n");
}

function buildOperatorGateDryRunCommand({
  goalId,
  registry,
  runtimeRoot,
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
}) {
  return [
    "loopx \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  operator-gate \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    "  --decision approve \\",
    `  --reason-summary ${shellQuote(controllerApprovalReason(goalId))} \\`,
    "  --dry-run",
  ].join("\n");
}

function buildOperatorDecision({
  goal,
  queueItem,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
}): OperatorDecision {
  const latestRun = goal?.latest_runs[0];
  const phase = goal?.lifecycle_phase
    ?? queueItem?.lifecycle_phase
    ?? latestRun?.lifecycle_phase
    ?? inferLifecyclePhase(queueItem?.status ?? goal?.status, latestRun);
  const waitingOn = queueItem?.waiting_on ?? "clear";
  const quota = queueItem?.project_asset?.quota ?? queueItem?.quota ?? goal?.quota;
  const missingGates = queueItem?.missing_gates ?? latestRun?.controller_readiness?.missing_gates ?? [];
  const action = queueItem?.recommended_action
    ?? latestRun?.recommended_action
    ?? "No immediate operator action.";

  if (queueItem?.severity === "high") {
    return {
      title: "Fix health first",
      badge: "Blocking",
      variant: "danger" as BadgeVariant,
      action,
      reason: "A high-severity status item is active, so other decisions should wait.",
      needs: missingGates.map(gateLabel),
      phase,
      waitingOn,
    };
  }

  if (waitingOn === "external_evidence") {
    return {
      title: "Wait for evidence",
      badge: phase === "controller_gated" ? "Gate missing" : "Watching",
      variant: "info" as BadgeVariant,
      action,
      reason: phase === "controller_gated"
        ? "Controller evidence exists, but the goal is still missing a decision gate."
        : "The next useful signal is outside the agent loop.",
      needs: missingGates.map(gateLabel),
      phase,
      waitingOn,
    };
  }

  if (waitingOn === "user_or_controller" || waitingOn === "controller") {
    const controllerCopy = phase === "planned"
      ? {
          title: "Review controller opt-in",
          badge: "Needs approval",
          reason: "The goal is known, but controller connection has not been authorized yet.",
        }
      : {
          title: "Review or authorize",
          badge: "User decision",
          reason: "A human or target controller decision is the next gate.",
        };
    return {
      ...controllerCopy,
      variant: "warning" as BadgeVariant,
      action,
      needs: missingGates.map(gateLabel),
      phase,
      waitingOn,
    };
  }

  if (waitingOn === "codex") {
    if (isOutcomeFloorRecoveryQuota(quota)) {
      return {
        title: "Run recovery evidence",
        badge: "Codex recovery",
        variant: "warning" as BadgeVariant,
        action,
        reason: `Outcome floor blocks ordinary delivery; Codex should do one bounded ${recoveryEvidenceLabel(quota)} recovery or write back the concrete blocker.`,
        needs: missingGates.map(gateLabel),
        phase,
        waitingOn,
      };
    }
    const codexCopy = queueItem?.agent_command
      ? {
          title: "Run approved agent command",
          badge: "Approved handoff",
          reason: "quota should-run can expose this agent command because an operator gate was approved.",
        }
      : phase === "mapped"
      ? {
          title: "Let Codex use the map",
          badge: "Codex can continue",
          reason: "The project has a read-only map; the next agent turn can choose the handoff.",
        }
      : phase === "refreshed"
        ? {
            title: "Let Codex continue",
            badge: "State refreshed",
            reason: "Goal state changed and the agent can resume from the refreshed action.",
          }
        : phase === "connected"
          ? {
              title: "Let Codex create the first run",
              badge: "Needs first run",
              reason: "The goal is connected but has not produced a compact run yet.",
            }
          : {
              title: "Let Codex continue",
              badge: "Codex can act",
              reason: "No human decision gate is active for this goal.",
            };
    return {
      ...codexCopy,
      variant: "success" as BadgeVariant,
      action,
      needs: missingGates.map(gateLabel),
      phase,
      waitingOn,
    };
  }

  if (phase === "reward_judged") {
    return {
      title: "Reward captured",
      badge: "Judged",
      variant: "success" as BadgeVariant,
      action,
      reason: "Human feedback is attached to the latest run.",
      needs: missingGates.map(gateLabel),
      phase,
      waitingOn,
    };
  }

  return {
    title: "No immediate user action",
    badge: "Clear",
    variant: "neutral" as BadgeVariant,
    action,
    reason: "The selected goal has no active attention item.",
    needs: missingGates.map(gateLabel),
    phase,
    waitingOn,
  };
}

function existingRewardValue(reward?: HumanReward | null): RewardValue {
  const value = reward?.reward;
  return rewardOptions.includes(value as RewardValue) ? value as RewardValue : "neutral";
}

function buildRewardDraftDefaults({
  goal,
  queueItem,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
}): RewardDraftDefaults {
  const latestRun = goal?.latest_runs[0];
  const operatorDecision = buildOperatorDecision({ goal, queueItem });
  const missingGates = new Set(queueItem?.missing_gates ?? latestRun?.controller_readiness?.missing_gates ?? []);
  const handoffCondition = queueItem?.next_handoff_condition
    ?? latestRun?.controller_readiness?.next_handoff_condition
    ?? "";

  if (latestRun?.human_reward) {
    return {
      decision: "review_existing_reward",
      reward: existingRewardValue(latestRun.human_reward),
      reasonSummary: "Human reward already exists; review it before adding another overlay.",
      followUp: "Use the latest rewarded run as the next agent-facing context.",
      label: "existing reward",
    };
  }

  if (queueItem?.severity === "high") {
    return {
      decision: "fix_health_first",
      reward: "negative",
      reasonSummary: "Blocking health issue prevents approval or handoff.",
      followUp: "Fix the blocking status item before recording approval or launching follow-up work.",
      label: "blocking status",
    };
  }

  if (operatorDecision.waitingOn === "external_evidence") {
    const needsReward = missingGates.has("human_reward_capture");
    return {
      decision: needsReward ? "record_human_reward_gate" : "watch_external_evidence",
      reward: "neutral",
      reasonSummary: needsReward
        ? "Operator judgment is required before controller decision advice."
        : "External evidence is still pending; no approval is implied.",
      followUp: handoffCondition || "Wait for comparable evidence before decision advice or write control.",
      label: needsReward ? "reward gate" : "evidence watch",
    };
  }

  if (operatorDecision.waitingOn === "controller" || operatorDecision.waitingOn === "user_or_controller") {
    return {
      decision: operatorDecision.phase === "planned" ? "review_controller_opt_in" : "review_or_authorize",
      reward: "neutral",
      reasonSummary: "Operator is reviewing a controller gate; reward does not grant write approval.",
      followUp: "Run the safe dry-run path before appending controller or write-control state.",
      label: operatorDecision.phase === "planned" ? "controller opt-in" : "operator gate",
    };
  }

  if (operatorDecision.waitingOn === "codex") {
    if (queueItem?.agent_command) {
      return {
        decision: "run_approved_agent_command",
        reward: "positive",
        reasonSummary: "Operator gate is approved; Codex can use the approved agent command.",
        followUp: "Execute only the approved read-only or dry-run command; stop before writes or higher permissions.",
        label: "approved command",
      };
    }
    if (operatorDecision.phase === "mapped") {
      return {
        decision: "use_read_only_map",
        reward: "positive",
        reasonSummary: "Read-only map is useful enough for the next Codex handoff.",
        followUp: "Let Codex use the latest map and history; keep writes separately approved.",
        label: "map handoff",
      };
    }
    if (operatorDecision.phase === "refreshed") {
      return {
        decision: "continue_from_refreshed_state",
        reward: "positive",
        reasonSummary: "Refreshed goal state gives Codex a usable next action.",
        followUp: "Let Codex continue from the refreshed state before asking for approval.",
        label: "state refresh",
      };
    }
    return {
      decision: "continue_codex_action",
      reward: "neutral",
      reasonSummary: "Codex can continue, but this reward is only a dry-run draft.",
      followUp: "Use the safe CLI path as the next agent-facing context.",
      label: "codex handoff",
    };
  }

  return {
    decision: "review_latest_run",
    reward: "neutral",
    reasonSummary: operatorDecision.reason,
    followUp: "Inspect status before recording a real reward.",
    label: "operator default",
  };
}

function buildUserActionSummaryItems({
  rows,
  registry,
  runtimeRoot,
}: {
  rows: GoalDirectoryRow[];
  registry: string;
  runtimeRoot: string;
}): UserActionSummaryItem[] {
  const items = rows.flatMap((row): UserActionSummaryItem[] => {
    const decision = buildOperatorDecision({ goal: row.goal, queueItem: row.queueItem });
    const draftDefaults = buildRewardDraftDefaults({ goal: row.goal, queueItem: row.queueItem });
    const bridge = buildOperatorActionBridge({
      goal: row.goal,
      queueItem: row.queueItem,
      registry,
      runtimeRoot,
    });
    const bridgeItem = bridge?.items.find((item) => item.command) ?? bridge?.items[0];
    const latestRun = row.latestRun;
    const authorityCoverage = buildAuthorityCoverage({ goal: row.goal, run: latestRun });
    const missingGates = new Set(row.queueItem?.missing_gates ?? latestRun?.controller_readiness?.missing_gates ?? []);
    const handoffCondition = row.queueItem?.next_handoff_condition
      ?? latestRun?.controller_readiness?.next_handoff_condition
      ?? "";
    const projectAsset = row.queueItem?.project_asset;
    const projectAssetSource: ProjectAssetSource = projectAsset ? "project_asset" : "legacy_raw_fallback";
    const quota = projectAsset?.quota ?? row.queueItem?.quota ?? row.goal.quota;
    const quotaState = quota?.state ?? "waiting";
    const userTodos = todosFromProjectAssetSummary(projectAsset?.user_todos, row.queueItem?.user_todos, "project_asset.user_todos");
    const agentTodos = todosFromProjectAssetSummary(projectAsset?.agent_todos, row.queueItem?.agent_todos, "project_asset.agent_todos");
    const nextAction = projectAsset?.next_action ?? decision.action;
    const stopCondition = projectAsset?.stop_condition ?? handoffCondition ?? decision.action;
    const latestValidation = projectAsset?.latest_validation;
    const handoffReadiness = row.queueItem?.handoff_readiness;
    const base = {
      goalId: row.goal.id,
      phase: decision.phase,
      waitingOn: decision.waitingOn,
      operatorQuestion: row.queueItem?.operator_question ?? undefined,
      agentCommand: row.queueItem?.agent_command ?? undefined,
      safePathLabel: bridgeItem?.label ?? bridge?.badge ?? "Inspect status",
      safePathCommand: bridgeItem?.command,
      rewardHint: latestRun
        ? `${draftDefaults.decision} / ${draftDefaults.reward}`
        : `${draftDefaults.label} / needs run`,
      authorityCoverage,
      quota,
      userTodos,
      agentTodos,
      latestValidation,
      projectOwner: projectAsset?.owner,
      projectGate: projectAsset?.gate,
      projectNextAction: nextAction,
      projectStopCondition: stopCondition,
      projectAssetSource,
      handoffReadiness,
    };

    if (row.severity === "high") {
      return [{
        ...base,
        kind: "health",
        title: "Fix health first",
        badge: "Blocking",
        variant: "danger",
        summary: nextAction,
        detail: decision.reason,
        priority: 0,
      }];
    }

    if (missingGates.has("human_reward_capture")) {
      return [{
        ...base,
        kind: "reward",
        title: "Record human reward",
        badge: "Reward gate",
        variant: "warning",
        summary: draftDefaults.reasonSummary,
        detail: draftDefaults.followUp || stopCondition,
        draftLabel: draftDefaults.label,
        priority: 1,
      }];
    }

    if (decision.waitingOn === "controller" || decision.waitingOn === "user_or_controller") {
      return [{
        ...base,
        kind: "controller",
        title: decision.title,
        badge: decision.badge,
        variant: decision.variant,
        summary: row.queueItem?.operator_question ?? decision.reason,
        detail: stopCondition,
        draftLabel: draftDefaults.label,
        priority: 2,
      }];
    }

    if (decision.waitingOn === "external_evidence") {
      return [{
        ...base,
        kind: "evidence",
        title: "Watch evidence",
        badge: decision.badge,
        variant: "info",
        summary: decision.reason,
        detail: stopCondition,
        draftLabel: draftDefaults.label,
        priority: 3,
      }];
    }

    if (decision.waitingOn === "codex" && quotaState === "focus_wait") {
      if (isOutcomeFloorRecoveryQuota(quota)) {
        const evidenceLabel = recoveryEvidenceLabel(quota);
        return [{
          ...base,
          kind: "codex",
          title: "Run Codex recovery",
          badge: "Recovery",
          variant: "warning",
          summary: `普通 delivery 被 outcome floor 阻塞；下一步只做一次 ${evidenceLabel}，或写回具体 blocker。`,
          detail: quota?.safe_bypass_policy ?? stopCondition,
          safePathLabel: "Recovery handoff",
          safePathCommand: buildHistoryCommand({ goalId: row.goal.id, registry, runtimeRoot }),
          draftLabel: "outcome recovery",
          priority: 3,
        }];
      }
      const ownerTodo = firstOpenTodo(userTodos);
      return [{
        ...base,
        kind: "evidence",
        title: "Focus wait owner blocker",
        badge: "Focus wait",
        variant: "info",
        summary: ownerTodo
          ? `Waiting on owner blocker: ${ownerTodo.text}`
          : "Waiting for owner evidence, a clean baseline, or external eval before delivery resumes.",
        detail: stopCondition,
        safePathLabel: "Status/history inspection only",
        safePathCommand: buildStatusCommand({ registry, runtimeRoot }),
        draftLabel: "focus wait",
        priority: 3,
      }];
    }

    if (decision.waitingOn === "codex" && quotaState === "throttled") {
      return [];
    }

    if (decision.waitingOn === "codex") {
      return [{
        ...base,
        kind: "codex",
        title: decision.title,
        badge: decision.badge,
        variant: "success",
        summary: draftDefaults.reasonSummary,
        detail: draftDefaults.followUp || stopCondition,
        draftLabel: draftDefaults.label,
        priority: 4,
      }];
    }

    if (decision.phase === "reward_judged") {
      return [{
        ...base,
        kind: "reward",
        title: "Reward captured",
        badge: "Judged",
        variant: "success",
        summary: decision.reason,
        detail: draftDefaults.followUp || stopCondition,
        draftLabel: draftDefaults.label,
        priority: 5,
      }];
    }

    return [];
  });

  return items.sort((a, b) => a.priority - b.priority || a.goalId.localeCompare(b.goalId));
}

function UserActionSummary({
  rows,
  selectedGoalId,
  onSelectGoal,
  selectedKind,
  onSelectKind,
  registry,
  runtimeRoot,
  source,
}: {
  rows: GoalDirectoryRow[];
  selectedGoalId: string;
  onSelectGoal: (goalId: string) => void;
  selectedKind: UserActionFilter;
  onSelectKind: (kind: UserActionFilter) => void;
  registry: string;
  runtimeRoot: string;
  source: DataSource;
}) {
  const items = buildUserActionSummaryItems({ rows, registry, runtimeRoot });
  const kindCounts = items.reduce<Record<UserActionKind, number>>((counts, item) => {
    counts[item.kind] += 1;
    return counts;
  }, {
    codex: 0,
    controller: 0,
    evidence: 0,
    health: 0,
    reward: 0,
  });
  const selectedKindCount = selectedKind === "all" ? items.length : kindCounts[selectedKind];
  const kindOptions = userActionKindOrder.filter((kind) => kindCounts[kind] > 0 || kind === selectedKind);
  const visibleItems = selectedKind === "all" ? items : items.filter((item) => item.kind === selectedKind);
  const showAllForEmptyFilter = selectedKind !== "all" && selectedKindCount === 0 && items.length > 0;
  const displayedItems = showAllForEmptyFilter ? items : visibleItems;
  const selectedKindLabel = selectedKind === "all" ? "All" : userActionKindConfig[selectedKind].label;
  const [actionCopyState, setActionCopyState] = useState<{ key: string; state: CopyState } | null>(null);

  useEffect(() => {
    if (!actionCopyState || actionCopyState.state === "idle") {
      return;
    }
    const timeoutId = window.setTimeout(() => setActionCopyState(null), 1800);
    return () => window.clearTimeout(timeoutId);
  }, [actionCopyState]);

  async function copyActionPacket(item: UserActionSummaryItem) {
    const key = `${item.goalId}-${item.kind}-${item.title}`;
    const packet = buildHumanFriendlyActionPacket({ item, registry, runtimeRoot });
    setActionCopyState({ key, state: (await copyTextToClipboard(packet)) ? "copied" : "failed" });
  }

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            User Actions
          </CardTitle>
          <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
            First-screen operator actions derived from status, gates, and reward defaults.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={items.length > 0 ? "warning" : "success"}>{items.length} actions</Badge>
          {selectedKind !== "all" ? (
            <Badge variant={userActionKindConfig[selectedKind].variant}>{userActionKindConfig[selectedKind].label}</Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
            No user-facing action is active.
          </div>
        ) : (
          <div className="space-y-3">
            <div aria-label="User action kind filter" className="flex flex-wrap gap-2">
              <Button
                aria-pressed={selectedKind === "all"}
                onClick={() => onSelectKind("all")}
                size="sm"
                variant={selectedKind === "all" ? "primary" : "secondary"}
              >
                All
                <Badge variant="neutral">{items.length}</Badge>
              </Button>
              {kindOptions.map((kind) => (
                <Button
                  aria-pressed={selectedKind === kind}
                  key={kind}
                  onClick={() => onSelectKind(kind)}
                  size="sm"
                  variant={selectedKind === kind ? "primary" : "secondary"}
                >
                  {userActionKindConfig[kind].label}
                  <Badge variant={userActionKindConfig[kind].variant}>{kindCounts[kind]}</Badge>
                </Button>
              ))}
            </div>
            {showAllForEmptyFilter ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                No {selectedKindLabel.toLowerCase()} action is active; showing all active actions.
              </div>
            ) : null}
            {displayedItems.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
                No {selectedKindLabel.toLowerCase()} action is active for this status source.
              </div>
            ) : (
              <div className="grid gap-3 xl:grid-cols-2">
                {displayedItems.map((item) => {
                  const actionKey = `${item.goalId}-${item.kind}-${item.title}`;
                  const copyState = actionCopyState?.key === actionKey ? actionCopyState.state : "idle";
                  const isGateAction = item.kind === "controller" || item.waitingOn === "user_or_controller" || item.waitingOn === "controller";
                  const handoffReadiness = buildHandoffReadinessView(item.handoffReadiness);
                  const copyLabel = copyState === "copied"
                    ? "Copied"
                    : item.kind === "codex" && item.agentCommand
                      ? "Copy Handoff"
                      : isFocusWaitQuota(item.quota)
                        ? "Copy Focus Packet"
                      : "Copy";
                  const agentTodo = firstOpenTodo(item.agentTodos);
                  return (
                  <article
                    className={cn(
                      "min-w-0 rounded-lg border p-3 text-left transition",
                      isGateAction
                        ? "border-amber-300 bg-amber-50/70 dark:border-amber-900/70 dark:bg-amber-950/30"
                        : "border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950",
                      item.goalId === selectedGoalId && "ring-2 ring-slate-300 dark:ring-zinc-700",
                    )}
                    key={actionKey}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <button
                        className="min-w-0 flex-1 text-left"
                        onClick={() => onSelectGoal(item.goalId)}
                        type="button"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="neutral">Project</Badge>
                          {item.goalId === selectedGoalId ? <Badge variant="success">Selected</Badge> : null}
                        </div>
                        <div className="mt-1 break-all text-base font-semibold leading-6 text-slate-950 dark:text-zinc-50">{item.goalId}</div>
                        <div className="mt-1 break-words text-sm font-medium text-slate-600 dark:text-zinc-300">{item.title}</div>
                      </button>
                      <div className="flex flex-wrap items-center gap-2">
                        {copyState === "failed" ? <Badge variant="danger">Copy failed</Badge> : null}
                        <Button
                          aria-label={`Copy action packet for ${item.goalId}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            void copyActionPacket(item);
                          }}
                          size="sm"
                          variant="secondary"
                        >
                          {copyState === "copied" ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                          {copyLabel}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant={userActionKindConfig[item.kind].variant}>{userActionKindConfig[item.kind].label}</Badge>
                      <Badge variant={item.variant}>{item.badge}</Badge>
                      <PhaseBadges compact phase={item.phase} />
                      {item.waitingOn !== "clear" ? (
                        <Badge variant="neutral">{waitingLabel[item.waitingOn] ?? item.waitingOn}</Badge>
                      ) : null}
                      <QuotaChip quota={item.quota} />
                      {handoffReadiness ? (
                        <Badge variant={handoffReadiness.variant}>
                          {handoffReadiness.ready ? "Handoff ready" : "Handoff blocked"}
                        </Badge>
                      ) : null}
                      {item.draftLabel ? <Badge variant="info">{item.draftLabel}</Badge> : null}
                    </div>
                    {(item.projectAssetSource === "legacy_raw_fallback" || item.projectOwner || item.projectGate || item.projectNextAction || item.projectStopCondition || handoffReadiness) ? (
                      <div className="mt-3 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-600 dark:border-zinc-800 dark:text-zinc-300">
                        <div className="flex flex-wrap items-center gap-2">
                          {item.projectAssetSource === "legacy_raw_fallback" ? (
                            <Badge variant="warning">Legacy/raw fallback</Badge>
                          ) : (
                            <Badge variant="neutral">Project asset</Badge>
                          )}
                          {item.projectAssetSource !== "legacy_raw_fallback" && item.projectOwner ? <Badge variant="info">Owner {item.projectOwner}</Badge> : null}
                          {item.projectAssetSource !== "legacy_raw_fallback" && item.projectGate ? <Badge variant="warning">Gate {item.projectGate}</Badge> : null}
                        </div>
                        {item.projectAssetSource === "legacy_raw_fallback" ? (
                          <p className="mt-2 break-words font-medium text-amber-700 dark:text-amber-200">
                            Owner/Gate/Stop are not project_asset-backed; below uses raw status fallback.
                          </p>
                        ) : null}
                        {item.projectNextAction ? (
                          <p className="mt-2 line-clamp-2 break-words">
                            <span className="font-medium">{item.projectAssetSource === "legacy_raw_fallback" ? "Fallback next:" : "Next:"}</span> {item.projectNextAction}
                          </p>
                        ) : null}
                        {item.projectStopCondition ? (
                          <p className="mt-1 line-clamp-2 break-words">
                            <span className="font-medium">{item.projectAssetSource === "legacy_raw_fallback" ? "Fallback stop:" : "Stop:"}</span> {item.projectStopCondition}
                          </p>
                        ) : null}
                        {handoffReadiness ? (
                          <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs leading-5 dark:border-zinc-800 dark:bg-zinc-900">
                            <p className="break-words">
                              <span className="font-medium">Handoff readiness:</span> {handoffReadiness.shortLine}
                            </p>
                            <p className="mt-1 break-words">
                              <span className="font-medium">Handoff state:</span> {handoffReadiness.stateLine}
                            </p>
                            {handoffReadiness.latestRunLine ? (
                              <p className="mt-1 break-words">
                                <span className="font-medium">Post-handoff run:</span> {handoffReadiness.latestRunLine}
                              </p>
                            ) : null}
                            {handoffReadiness.probe ? (
                              <p className="mt-1 break-words">
                                <span className="font-medium">Probe:</span> {handoffReadiness.probe}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    <UserTodoCallout
                      blocksGate={Boolean(item.operatorQuestion && firstOpenTodo(item.userTodos))}
                      focusWait={isFocusWaitQuota(item.quota)}
                      goalId={item.goalId}
                      source={source}
                      todos={item.userTodos}
                    />
                    {item.operatorQuestion ? (
                      <div className="mt-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <CircleAlert className="h-3.5 w-3.5 text-amber-700 dark:text-amber-300" />
                          <Badge variant="warning">Operator question</Badge>
                        </div>
                        <p className="mt-2 line-clamp-3 break-words text-sm font-medium leading-6 text-amber-950 dark:text-amber-100">
                          {item.operatorQuestion}
                        </p>
                      </div>
                    ) : (
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-700 dark:text-zinc-300">{item.summary}</p>
                    )}
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">{item.detail}</p>
                    {item.agentCommand ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                        <Badge variant="info">{item.operatorQuestion ? "Agent command ready after approval" : "Approved agent command"}</Badge>
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3 text-xs text-slate-600 dark:border-zinc-800 dark:text-zinc-300">
                      <Badge variant="neutral">Safe path</Badge>
                      <span className="line-clamp-1 break-words font-medium">{item.safePathLabel}</span>
                      <Badge variant="info">Reward</Badge>
                      <span className="font-medium">{item.rewardHint}</span>
                      {item.authorityCoverage ? (
                        <>
                          <Badge variant={item.authorityCoverage.variant}>Authority</Badge>
                          <span className="line-clamp-1 break-words font-medium">{item.authorityCoverage.shortLine}</span>
                        </>
                      ) : null}
                      {buildQuotaView(item.quota) ? (
                        <>
                          <Gauge className="h-3.5 w-3.5 text-slate-500 dark:text-zinc-400" />
                          <Badge variant={buildQuotaView(item.quota)?.variant}>Quota</Badge>
                          <span className="font-medium">{buildQuotaView(item.quota)?.shortLine}</span>
                        </>
                      ) : null}
                      {formatLatestValidation(item.latestValidation) ? (
                        <>
                          <FileCheck2 className="h-3.5 w-3.5 text-slate-500 dark:text-zinc-400" />
                          <Badge variant="neutral">Validation</Badge>
                          <span className="line-clamp-1 break-words font-medium">
                            {formatLatestValidation(item.latestValidation)}
                          </span>
                        </>
                      ) : null}
                      {agentTodo ? (
                        <>
                          <Bot className="h-3.5 w-3.5 text-slate-500 dark:text-zinc-400" />
                          <Badge variant="info">Agent todo</Badge>
                          <span className="line-clamp-1 break-words font-medium">{agentTodo.text}</span>
                        </>
                      ) : null}
                    </div>
                  </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function buildOperatorActionBridge({
  goal,
  queueItem,
  registry,
  runtimeRoot,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
}): OperatorActionBridge | null {
  const goalId = goal?.id ?? queueItem?.goal_id;
  if (!goalId) {
    return null;
  }
  const latestRun = goal?.latest_runs[0];
  const phase = goal?.lifecycle_phase
    ?? queueItem?.lifecycle_phase
    ?? latestRun?.lifecycle_phase
    ?? inferLifecyclePhase(queueItem?.status ?? goal?.status, latestRun);
  const waitingOn = queueItem?.waiting_on ?? "clear";
  const missingGates = new Set(queueItem?.missing_gates ?? latestRun?.controller_readiness?.missing_gates ?? []);
  const statusCommand = buildStatusCommand({ registry, runtimeRoot });

  if (queueItem?.severity === "high") {
    return {
      title: "Safe CLI Path",
      badge: "inspect",
      variant: "danger",
      body: "Resolve the blocking health item before rewarding, approving, or handing off this goal.",
      items: [
        {
          label: "Inspect status",
          body: "Use the machine-readable status contract to identify the active blocker.",
          command: statusCommand,
          variant: "danger",
        },
      ],
    };
  }

  if (waitingOn === "external_evidence") {
    const items: OperatorActionBridgeItem[] = [
      {
        label: "Watch gate",
        body: "Keep this goal in observation until comparable evidence arrives.",
        command: statusCommand,
        variant: "info",
      },
    ];
    if (missingGates.has("human_reward_capture")) {
      items.push({
        label: "Reward gate",
        body: "Use the Reward CLI Draft below after judging the selected run; keep the draft in dry-run until the operator intentionally records it.",
        variant: "warning",
      });
    }
    if (queueItem?.next_handoff_condition) {
      items.push({
        label: "Handoff condition",
        body: queueItem.next_handoff_condition,
        variant: "neutral",
      });
    }
    return {
      title: "Safe CLI Path",
      badge: "watch",
      variant: "info",
      body: "The dashboard can validate the next reward draft, but it should not turn missing evidence into approval.",
      items,
    };
  }

  if (waitingOn === "user_or_controller" || waitingOn === "controller") {
    const command = queueItem?.agent_command
      ?? buildReadOnlyMapDryRunCommand({ goalId, registry, runtimeRoot });
    const gateDraftCommand = buildOperatorGateDryRunCommand({ goalId, registry, runtimeRoot });
    return {
      title: "Safe CLI Path",
      badge: phase === "planned" ? "opt-in" : "approval",
      variant: "warning",
      body: "Approval remains a human/controller decision outside the browser; the safe local command is a dry-run.",
      items: [
        {
          label: "Read-only map dry-run",
          body: "Preview the controller handoff surface before any run is appended.",
          command,
          variant: "warning",
        },
        {
          label: "Operator gate dry-run draft",
          body: "User-owned preview after the human approves; keep --dry-run until intentionally recording the gate.",
          command: gateDraftCommand,
          variant: "neutral",
        },
        {
          label: "Approval boundary",
          body: "A reward signal or dashboard review does not grant write control by itself.",
          variant: "neutral",
        },
      ],
    };
  }

  if (waitingOn === "codex") {
    const fallbackCommand = phase === "refreshed"
      ? buildRefreshStateDryRunCommand({ goalId, registry, runtimeRoot })
      : phase === "connected"
        ? buildReadOnlyMapDryRunCommand({ goalId, registry, runtimeRoot })
        : buildHistoryCommand({ goalId, registry, runtimeRoot });
    const command = queueItem?.agent_command
      ?? fallbackCommand;
    const commandIsGateApproved = Boolean(queueItem?.agent_command);
    return {
      title: "Safe CLI Path",
      badge: "handoff",
      variant: "success",
      body: "This goal is ready for an agent turn; the dashboard should hand off context, not perform the agent step.",
      items: [
        {
          label: commandIsGateApproved ? "Approved agent command" : phase === "mapped" ? "Read latest map" : "Preview next run",
          body: commandIsGateApproved
            ? "This command is valid because the operator gate was recorded as approved."
            : phase === "mapped"
            ? "Use the compact map and recent history as the agent-facing context."
            : "Dry-run the next state or map command before appending a run.",
          command,
          variant: "success",
        },
      ],
    };
  }

  if (phase === "reward_judged") {
    return {
      title: "Safe CLI Path",
      badge: "recorded",
      variant: "success",
      body: "The selected run already has a compact human reward overlay.",
      items: [
        {
          label: "Review history",
          body: "Use recent history as the next agent-facing context.",
          command: buildHistoryCommand({ goalId, registry, runtimeRoot }),
          variant: "success",
        },
      ],
    };
  }

  return {
    title: "Safe CLI Path",
    badge: "status",
    variant: "neutral",
    body: "No direct user action is active; keep the current status contract as the source for agents.",
    items: [
      {
        label: "Inspect status",
        body: "Read the compact agent-facing status before starting a new action.",
        command: statusCommand,
        variant: "neutral",
      },
    ],
  };
}

function OperatorDecisionPanel({
  goal,
  queueItem,
  registry,
  runtimeRoot,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
}) {
  const decision = buildOperatorDecision({ goal, queueItem });
  const bridge = buildOperatorActionBridge({ goal, queueItem, registry, runtimeRoot });
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase text-slate-500 dark:text-zinc-400">Operator Decision</div>
          <div className="mt-1 text-base font-semibold text-slate-950 dark:text-zinc-50">{decision.title}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={decision.variant}>{decision.badge}</Badge>
          <PhaseBadges compact phase={decision.phase} />
          {decision.waitingOn !== "clear" ? (
            <Badge variant="neutral">{waitingLabel[decision.waitingOn] ?? decision.waitingOn}</Badge>
          ) : null}
        </div>
      </div>
      <p className="mt-3 leading-6 text-slate-700 dark:text-zinc-300">{decision.action}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">{decision.reason}</p>
      {decision.needs.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {decision.needs.map((need) => (
            <Badge key={need} variant="warning">
              {need}
            </Badge>
          ))}
        </div>
      ) : null}
      {bridge ? (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-zinc-400" />
            <span className="font-medium text-slate-950 dark:text-zinc-50">{bridge.title}</span>
            <Badge variant={bridge.variant}>{bridge.badge}</Badge>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">{bridge.body}</p>
          <div className="mt-3 space-y-2">
            {bridge.items.map((item) => (
              <div className="rounded-md border border-slate-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950" key={`${item.label}-${item.command ?? item.body}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={item.variant ?? "neutral"}>{item.label}</Badge>
                  {item.command ? <Badge variant="info">dry path</Badge> : null}
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">{item.body}</p>
                {item.command ? (
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-950 p-3 text-xs leading-5 text-slate-50 dark:border-zinc-800">
                    {item.command}
                  </pre>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function HumanRewardSummary({ reward }: { reward: HumanReward }) {
  return (
    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={rewardVariant(reward.reward)}>Human reward</Badge>
        {reward.decision ? <span className="font-medium text-emerald-950 dark:text-emerald-100">{reward.decision}</span> : null}
        {reward.recorded_at ? <span className="text-xs text-emerald-700 dark:text-emerald-300">{reward.recorded_at}</span> : null}
      </div>
      {reward.reason_summary ? (
        <p className="mt-2 leading-6 text-emerald-900 dark:text-emerald-100">{reward.reason_summary}</p>
      ) : null}
      {reward.follow_up ? (
        <p className="mt-1 text-xs leading-5 text-emerald-800 dark:text-emerald-200">{reward.follow_up}</p>
      ) : null}
    </div>
  );
}

function operatorGateVariant(gate: OperatorGate): BadgeVariant {
  if (gate.decision === "approve") {
    return "success";
  }
  if (gate.decision === "reject") {
    return "danger";
  }
  return "warning";
}

function OperatorGateSummary({ gate }: { gate: OperatorGate }) {
  return (
    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900/60 dark:bg-amber-950/30">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={operatorGateVariant(gate)}>Operator gate</Badge>
        {gate.gate ? <span className="font-medium text-amber-950 dark:text-amber-100">{gate.gate}</span> : null}
        {gate.decision ? <Badge variant={operatorGateVariant(gate)}>{gate.decision}</Badge> : null}
        {gate.recorded_at ? <Badge variant="neutral">{gate.recorded_at}</Badge> : null}
      </div>
      {gate.operator_question ? (
        <p className="mt-2 leading-6 text-amber-950 dark:text-amber-100">{gate.operator_question}</p>
      ) : null}
      {gate.reason_summary ? (
        <p className="mt-1 text-xs leading-5 text-amber-900 dark:text-amber-100">{gate.reason_summary}</p>
      ) : null}
      {gate.follow_up ? (
        <p className="mt-1 text-xs leading-5 text-amber-800 dark:text-amber-200">{gate.follow_up}</p>
      ) : null}
      {gate.agent_command ? (
        <code className="mt-2 block overflow-x-auto whitespace-pre-wrap rounded-md bg-slate-950 p-2 text-xs leading-5 text-slate-50">
          {gate.agent_command}
        </code>
      ) : null}
    </div>
  );
}

function OperatorGateResumeContractSummary({ contract }: { contract: OperatorGateResumeContract }) {
  const checks = [
    contract.freshness_check,
    contract.precondition_check,
    contract.migration_or_rebase_result,
    contract.validation_after_resume,
  ].filter(Boolean);
  return (
    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-900/60 dark:bg-emerald-950/30">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="success">Checkpointed resume</Badge>
        {contract.version ? <Badge variant="neutral">{contract.version}</Badge> : null}
        {contract.gate_id ? <span className="font-medium text-emerald-950 dark:text-emerald-100">{contract.gate_id}</span> : null}
        {contract.operator_decision ? <Badge variant="success">{contract.operator_decision}</Badge> : null}
      </div>
      {contract.latest_state_ref ? (
        <p className="mt-2 text-xs leading-5 text-emerald-900 dark:text-emerald-100">{contract.latest_state_ref}</p>
      ) : null}
      {checks.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs leading-5 text-emerald-800 dark:text-emerald-200">
          {checks.map((check) => (
            <li key={check}>{check}</li>
          ))}
        </ul>
      ) : null}
      {contract.resulting_action ? (
        <p className="mt-2 text-xs leading-5 text-emerald-950 dark:text-emerald-100">{contract.resulting_action}</p>
      ) : null}
    </div>
  );
}

function ControllerReadinessSummary({ readiness }: { readiness: ControllerReadiness }) {
  const missing = readiness.missing_gates ?? [];
  return (
    <div className="mt-3 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm dark:border-sky-900 dark:bg-sky-950">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={readinessVariant(readiness)}>Controller readiness</Badge>
        {readiness.classification ? <span className="font-medium text-sky-950 dark:text-sky-100">{readiness.classification}</span> : null}
        {missing.length > 0 ? <Badge variant="warning">{missing.length} missing</Badge> : <Badge variant="success">gates clear</Badge>}
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        <Badge variant={readiness.read_only_observer_ready ? "success" : "neutral"}>Observer</Badge>
        <Badge variant={readiness.decision_advisor_ready ? "success" : "neutral"}>Decision</Badge>
        <Badge variant={readiness.write_controller_ready ? "success" : "neutral"}>Write</Badge>
      </div>
      {readiness.review_judgment ? (
        <p className="mt-2 leading-6 text-sky-900 dark:text-sky-100">{readiness.review_judgment}</p>
      ) : null}
      {readiness.next_handoff_condition ? (
        <p className="mt-1 text-xs leading-5 text-sky-800 dark:text-sky-200">{readiness.next_handoff_condition}</p>
      ) : null}
      {readiness.gates.length > 0 ? (
        <div className="mt-3 space-y-1">
          {readiness.gates.map((gate) => (
            <div className="flex gap-2 text-xs leading-5 text-sky-900 dark:text-sky-100" key={`${gate.id}-${gate.ok}`}>
              <Badge variant={gate.ok ? "success" : "warning"}>{gate.ok ? "PASS" : "MISS"}</Badge>
              <span className="break-words">
                {gate.id}
                {gate.review ? `: ${gate.review}` : ""}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ProjectMapSummary({ projectMap }: { projectMap: ProjectMap }) {
  const sections = `${projectMap.sections_found ?? 0}/${projectMap.sections_checked ?? 0}`;
  const files = `${projectMap.files_present ?? 0}/${projectMap.files_checked ?? 0}`;
  const authorityCoverage = buildAuthorityCoverageFromProjectMap(projectMap);
  return (
    <div className="mt-3 rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm dark:border-indigo-900 dark:bg-indigo-950">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="info">Project map</Badge>
        {projectMap.adapter_kind ? (
          <span className="font-medium text-indigo-950 dark:text-indigo-100">{projectMap.adapter_kind}</span>
        ) : null}
        {projectMap.adapter_status ? <Badge variant="neutral">{projectMap.adapter_status}</Badge> : null}
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        <Badge variant="neutral">sources {projectMap.authority_source_count ?? 0}</Badge>
        {authorityCoverage ? <Badge variant={authorityCoverage.variant}>{authorityCoverage.badge}</Badge> : null}
        <Badge variant="neutral">guards {projectMap.guard_count ?? 0}</Badge>
        <Badge variant="info">sections {sections}</Badge>
        <Badge variant="info">files {files}</Badge>
      </div>
      {authorityCoverage ? (
        <p className="mt-2 text-xs leading-5 text-indigo-900 dark:text-indigo-100">{authorityCoverage.reviewLine}</p>
      ) : null}
    </div>
  );
}

function LatestRun({ run }: { run: RunRecord }) {
  const lifecyclePhase = run.lifecycle_phase ?? inferLifecyclePhase(run.classification, run);
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-500 dark:text-zinc-400">{run.generated_at}</span>
        <Badge variant="info">{formatNullable(run.classification, "unclassified")}</Badge>
        <PhaseBadges compact flags={run.lifecycle_flags} phase={lifecyclePhase} />
        {run.health_check ? <Badge variant="success">{run.health_check}</Badge> : null}
        {run.human_reward ? <Badge variant={rewardVariant(run.human_reward.reward)}>Reward</Badge> : null}
        {run.operator_gate ? <Badge variant={operatorGateVariant(run.operator_gate)}>Gate</Badge> : null}
        {run.operator_gate_resume_contract ? <Badge variant="success">Resume contract</Badge> : null}
        {run.controller_readiness ? <Badge variant={readinessVariant(run.controller_readiness)}>Readiness</Badge> : null}
        <Badge variant={artifactVariant(run.json_exists)}>JSON</Badge>
        <Badge variant={artifactVariant(run.markdown_exists)}>Markdown</Badge>
      </div>
      {run.recommended_action ? (
        <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-zinc-300">{run.recommended_action}</p>
      ) : null}
      {run.controller_readiness ? <ControllerReadinessSummary readiness={run.controller_readiness} /> : null}
      {run.human_reward ? <HumanRewardSummary reward={run.human_reward} /> : null}
      {run.operator_gate ? <OperatorGateSummary gate={run.operator_gate} /> : null}
      {run.operator_gate_resume_contract ? (
        <OperatorGateResumeContractSummary contract={run.operator_gate_resume_contract} />
      ) : null}
      {run.project_map ? <ProjectMapSummary projectMap={run.project_map} /> : null}
    </div>
  );
}

function RewardCommandDraft({
  goal,
  queueItem,
  registry,
  runtimeRoot,
  dryRunUrl,
  appendUrl,
  onStatusRefresh,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
  dryRunUrl: string | null;
  appendUrl: string | null;
  onStatusRefresh: () => Promise<void>;
}) {
  const latestRun = goal?.latest_runs[0];
  const missingGateKey = (queueItem?.missing_gates ?? latestRun?.controller_readiness?.missing_gates ?? []).join("|");
  const draftDefaults = useMemo(
    () => buildRewardDraftDefaults({ goal, queueItem }),
    [
      goal?.id,
      goal?.status,
      goal?.lifecycle_phase,
      latestRun?.generated_at,
      latestRun?.classification,
      latestRun?.lifecycle_phase,
      latestRun?.human_reward?.recorded_at,
      latestRun?.human_reward?.decision,
      latestRun?.human_reward?.reward,
      latestRun?.controller_readiness?.classification,
      latestRun?.controller_readiness?.next_handoff_condition,
      queueItem?.status,
      queueItem?.waiting_on,
      queueItem?.severity,
      queueItem?.recommended_action,
      queueItem?.lifecycle_phase,
      queueItem?.next_handoff_condition,
      missingGateKey,
    ],
  );
  const [decision, setDecision] = useState(draftDefaults.decision);
  const [reward, setReward] = useState<RewardValue>(draftDefaults.reward);
  const [reasonSummary, setReasonSummary] = useState(draftDefaults.reasonSummary);
  const [followUp, setFollowUp] = useState(draftDefaults.followUp);
  const [dryRunResult, setDryRunResult] = useState<RewardDryRunResponse | null>(null);
  const [dryRunRequestBody, setDryRunRequestBody] = useState<RewardRequestBody | null>(null);
  const [appendResult, setAppendResult] = useState<RewardDryRunResponse | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [appendError, setAppendError] = useState<string | null>(null);
  const [isAppending, setIsAppending] = useState(false);
  const command = goal && latestRun
    ? buildRewardCommand({
        goalId: goal.id,
        registry,
        runtimeRoot,
        runGeneratedAt: latestRun.generated_at,
        decision,
        reward,
        reasonSummary,
        followUp,
      })
    : "";
  const canDryRun = Boolean(command && dryRunUrl && decision.trim() && reasonSummary.trim());
  const canAppend = Boolean(
    appendUrl
    && dryRunRequestBody
    && dryRunResult?.ok
    && dryRunResult.preview_id
    && !dryRunResult.appended
    && !appendResult?.appended,
  );

  useEffect(() => {
    setDecision(draftDefaults.decision);
    setReward(draftDefaults.reward);
    setReasonSummary(draftDefaults.reasonSummary);
    setFollowUp(draftDefaults.followUp);
    setDryRunResult(null);
    setDryRunRequestBody(null);
    setAppendResult(null);
    setDryRunError(null);
    setAppendError(null);
  }, [
    draftDefaults.decision,
    draftDefaults.reward,
    draftDefaults.reasonSummary,
    draftDefaults.followUp,
    goal?.id,
    latestRun?.generated_at,
  ]);

  function rewardRequestBody(): RewardRequestBody | null {
    if (!goal || !latestRun) {
      return null;
    }
    return {
      goal_id: goal.id,
      run_generated_at: latestRun.generated_at,
      decision,
      reward,
      reason_summary: reasonSummary,
      follow_up: followUp.trim() || undefined,
    };
  }

  async function runDryRunCheck() {
    if (!goal || !latestRun || !dryRunUrl) {
      return;
    }
    setIsDryRunning(true);
    setDryRunError(null);
    setDryRunResult(null);
    setDryRunRequestBody(null);
    setAppendResult(null);
    setAppendError(null);
    try {
      const requestBody = rewardRequestBody();
      if (!requestBody) {
        return;
      }
      const response = await fetch(dryRunUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const payload = parseRewardDryRunResponse(await response.json());
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      const recordedAt = payload.human_reward?.recorded_at;
      setDryRunRequestBody(recordedAt ? { ...requestBody, recorded_at: recordedAt } : requestBody);
      setDryRunResult(payload);
    } catch (error) {
      setDryRunError(formatStatusError(error));
    } finally {
      setIsDryRunning(false);
    }
  }

  async function appendRewardOverlay() {
    const requestBody = dryRunRequestBody;
    if (!appendUrl || !requestBody || !dryRunResult?.preview_id) {
      return;
    }
    setIsAppending(true);
    setAppendError(null);
    try {
      const response = await fetch(appendUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...requestBody,
          preview_id: dryRunResult.preview_id,
          write_active_state_summary: true,
        }),
      });
      const payload = parseRewardDryRunResponse(await response.json());
      if (!response.ok || !payload.ok || !payload.appended) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setAppendResult(payload);
      setDryRunResult(payload);
      await onStatusRefresh();
    } catch (error) {
      setAppendError(formatStatusError(error));
    } finally {
      setIsAppending(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center gap-2">
        <Terminal className="h-4 w-4 text-slate-500 dark:text-zinc-400" />
        <span className="font-medium">Reward CLI Draft</span>
        <Badge variant="info">local-only</Badge>
        <Badge variant={command ? "warning" : "neutral"}>{command ? "dry-run" : "needs run"}</Badge>
        <Badge variant="neutral">{draftDefaults.label}</Badge>
        {dryRunResult?.ok ? <Badge variant="success">validated</Badge> : null}
      </div>
      {command ? (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
            <span>Defaults derive from the selected Operator Decision and missing gates.</span>
            <Button
              onClick={() => {
                setDecision(draftDefaults.decision);
                setReward(draftDefaults.reward);
                setReasonSummary(draftDefaults.reasonSummary);
                setFollowUp(draftDefaults.followUp);
                setDryRunResult(null);
                setDryRunRequestBody(null);
                setAppendResult(null);
                setDryRunError(null);
                setAppendError(null);
              }}
              size="sm"
              variant="ghost"
            >
              Reset defaults
            </Button>
          </div>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_160px]">
            <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
              <span>Decision</span>
              <input className={inputClassName} onChange={(event) => setDecision(event.target.value)} value={decision} />
            </label>
            <label className="space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
              <span>Reward</span>
              <Select className="w-full" value={reward} onChange={(event) => setReward(event.target.value as RewardValue)}>
                {rewardOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </label>
          </div>
          <label className="block space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
            <span>Reason summary</span>
            <input className={inputClassName} onChange={(event) => setReasonSummary(event.target.value)} value={reasonSummary} />
          </label>
          <label className="block space-y-1 text-xs font-medium text-slate-500 dark:text-zinc-400">
            <span>Follow-up</span>
            <input className={inputClassName} onChange={(event) => setFollowUp(event.target.value)} value={followUp} />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={!canDryRun || isDryRunning} onClick={() => void runDryRunCheck()} size="sm">
              {isDryRunning ? <RefreshCw className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
              Dry-run Check
            </Button>
            <Badge variant={dryRunUrl ? "info" : "neutral"}>{dryRunUrl ? "local API" : "manual CLI"}</Badge>
            <Badge variant={appendUrl ? "warning" : "neutral"}>{appendUrl ? "append API" : "copy/CLI only"}</Badge>
            {dryRunError ? <Badge variant="danger">{dryRunError.slice(0, 96)}</Badge> : null}
            {appendError ? <Badge variant="danger">{appendError.slice(0, 96)}</Badge> : null}
          </div>
          {dryRunResult?.ok ? (
            <div className="space-y-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100">
              <div>
                {dryRunResult.goal_id} · {dryRunResult.selected_run?.generated_at} · appended={String(dryRunResult.appended)}
              </div>
              {dryRunResult.active_state_summary ? (
                <p>{dryRunResult.active_state_summary}</p>
              ) : null}
              {dryRunResult.project_agent_visibility?.history_command ? (
                <code className="block rounded border border-emerald-200 bg-white/60 p-2 text-[11px] leading-4 dark:border-emerald-900 dark:bg-zinc-950/50">
                  {dryRunResult.project_agent_visibility.history_command}
                </code>
              ) : null}
              {dryRunResult.preview_id && !appendResult?.appended ? (
                <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-emerald-200 bg-white/70 p-2 dark:border-emerald-900 dark:bg-zinc-950/50">
                  <span>Preview locked to this goal/run/reward payload. Append writes one run-bound human_reward overlay.</span>
                  <Button disabled={!canAppend || isAppending} onClick={() => void appendRewardOverlay()} size="sm">
                    {isAppending ? <RefreshCw className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                    Append reward overlay
                  </Button>
                </div>
              ) : null}
              {appendResult?.appended ? (
                <div className="rounded border border-emerald-300 bg-emerald-100 p-2 font-medium dark:border-emerald-800 dark:bg-emerald-900">
                  Reward appended and status refreshed. The next agent run can read it from run history.
                </div>
              ) : null}
            </div>
          ) : null}
          <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-950 p-3 text-xs leading-5 text-slate-50 dark:border-zinc-800">
            {command}
          </pre>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500 dark:text-zinc-400">No compact run record to reward.</p>
      )}
    </div>
  );
}

function RunHistoryPanel({
  controlPlaneApplyUrl,
  controlPlaneDryRunUrl,
  controlPlaneWriteEnabled,
  goal,
  onStatusRefresh,
  queueItem,
  registry,
  runtimeRoot,
  rewardDryRunUrl,
  rewardAppendUrl,
}: {
  controlPlaneApplyUrl: string | null;
  controlPlaneDryRunUrl: string | null;
  controlPlaneWriteEnabled: boolean | null;
  goal?: RunGoal;
  onStatusRefresh: () => Promise<void>;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
  rewardDryRunUrl: string | null;
  rewardAppendUrl: string | null;
}) {
  const latestRuns = goal?.latest_runs ?? [];
  const authorityCoverage = buildAuthorityCoverage({ goal, run: latestRuns[0] });
  const artifactReady = latestRuns.filter((run) => run.json_exists && run.markdown_exists).length;
  const rewardReady = latestRuns.filter((run) => Boolean(run.human_reward)).length;
  const readinessReady = latestRuns.filter((run) => Boolean(run.controller_readiness)).length;
  const lifecyclePhase = goal?.lifecycle_phase ?? queueItem?.lifecycle_phase ?? inferLifecyclePhase(queueItem?.status, latestRuns[0]);
  const lifecycleFlags = goal?.lifecycle_flags?.length ? goal.lifecycle_flags : queueItem?.lifecycle_flags ?? [];
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Run History
          </CardTitle>
        </div>
        {queueItem ? <StatusBadge value={queueItem.severity} /> : null}
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <div className="break-all text-sm font-semibold">{goal?.id ?? queueItem?.goal_id ?? "No goal selected"}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {goal?.status ? <Badge>{goal.status}</Badge> : null}
              {goal?.adapter_kind ? <Badge variant="neutral">{goal.adapter_kind}</Badge> : null}
              {goal?.adapter_status ? <Badge variant="info">{goal.adapter_status}</Badge> : null}
              {goal?.legacy_runtime_goal ? <Badge variant="warning">Legacy runtime</Badge> : null}
            </div>
            <div className="mt-2">
              <PhaseBadges flags={lifecycleFlags} phase={lifecyclePhase} />
            </div>
            {authorityCoverage ? (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={authorityCoverage.variant}>Authority coverage</Badge>
                  <span className="text-xs font-medium text-slate-700 dark:text-zinc-300">{authorityCoverage.shortLine}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-zinc-300">{authorityCoverage.reviewLine}</p>
              </div>
            ) : null}
          </div>

          <OperatorDecisionPanel
            goal={goal}
            queueItem={queueItem}
            registry={registry}
            runtimeRoot={runtimeRoot}
          />

          <ControlPlaneSettingsPanel
            applyUrl={controlPlaneApplyUrl}
            dryRunUrl={controlPlaneDryRunUrl}
            goal={goal}
            onStatusRefresh={onStatusRefresh}
            queueItem={queueItem}
            registry={registry}
            writeEnabled={controlPlaneWriteEnabled}
          />

          <div className="grid gap-2 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
              <div className="text-xs text-slate-500 dark:text-zinc-400">Records</div>
              <div className="mt-1 text-lg font-semibold">{goal?.raw_index_records ?? 0}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
              <div className="text-xs text-slate-500 dark:text-zinc-400">Unique Runs</div>
              <div className="mt-1 text-lg font-semibold">{goal?.unique_runs ?? 0}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
              <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-zinc-400">
                <FileCheck2 className="h-3.5 w-3.5" />
                Artifacts
              </div>
              <div className="mt-1 text-lg font-semibold">{artifactReady}/{latestRuns.length}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
              <div className="text-xs text-slate-500 dark:text-zinc-400">Readiness</div>
              <div className="mt-1 text-lg font-semibold">{readinessReady}/{latestRuns.length}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800 sm:col-span-4">
              <div className="text-xs text-slate-500 dark:text-zinc-400">Human Reward</div>
              <div className="mt-1 text-lg font-semibold">{rewardReady}/{latestRuns.length}</div>
            </div>
          </div>

          {queueItem ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="font-medium">Queue action</div>
              <p className="mt-1 leading-6 text-slate-700 dark:text-zinc-300">{queueItem.recommended_action}</p>
              {queueItem.operator_question ? (
                <div className="mt-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                    Operator gate
                  </div>
                  <p className="mt-1 leading-6 text-slate-800 dark:text-zinc-200">{queueItem.operator_question}</p>
                </div>
              ) : null}
              {queueItem.agent_command ? (
                <div className="mt-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                    Agent command
                  </div>
                  <code className="mt-1 block overflow-x-auto whitespace-pre rounded-md bg-white px-2 py-1.5 text-xs text-slate-700 dark:bg-zinc-950 dark:text-zinc-300">
                    {queueItem.agent_command}
                  </code>
                </div>
              ) : null}
              <QueueGateSummary item={queueItem} />
              <HandoffReadinessPanel
                goalId={queueItem.goal_id}
                readiness={queueItem.handoff_readiness}
                testId="selected-queue-handoff-readiness"
              />
            </div>
          ) : null}

          <RewardCommandDraft
            appendUrl={rewardAppendUrl}
            dryRunUrl={rewardDryRunUrl}
            goal={goal}
            onStatusRefresh={onStatusRefresh}
            queueItem={queueItem}
            registry={registry}
            runtimeRoot={runtimeRoot}
          />

          <div className="space-y-2">
            {latestRuns.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-zinc-400">
                No compact run record yet.
              </div>
            ) : (
              latestRuns.map((run) => <LatestRun key={`${run.goal_id}-${run.generated_at}`} run={run} />)
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HealthFindingList({
  title,
  items,
  emptyLabel,
  variant,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
  variant: "success" | "warning" | "danger" | "info";
}) {
  return (
    <div className="min-w-0 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase text-slate-500 dark:text-zinc-500">{title}</h3>
        <Badge variant={items.length > 0 ? variant : "neutral"}>{items.length}</Badge>
      </div>
      <div className="mt-3 space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-zinc-400">{emptyLabel}</p>
        ) : (
          items.map((item) => (
            <div className="text-sm leading-6 text-slate-700 dark:text-zinc-300" key={item}>
              {item}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ContractHealthPanel({ contract }: { contract: StatusPayload["contract"] }) {
  const checks = contract.checks ?? [];
  return (
    <Card className={cn(!contract.ok && "border-rose-200 dark:border-rose-900")}>
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Contract Health
          </CardTitle>
          <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
            {contract.ok ? "Public boundary clear" : "Blocking contract issue"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={contract.ok ? "success" : "danger"}>{contract.ok ? "Healthy" : "Blocked"}</Badge>
          <Badge variant={contract.errors.length > 0 ? "danger" : "neutral"}>
            {contract.summary.errors} errors
          </Badge>
          <Badge variant={contract.warnings.length > 0 ? "warning" : "neutral"}>
            {contract.summary.warnings} warnings
          </Badge>
          <Badge variant="info">{contract.summary.checks} checks</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-slate-200 dark:divide-zinc-800 lg:grid lg:grid-cols-3 lg:divide-x lg:divide-y-0">
          <HealthFindingList emptyLabel="No blocking errors" items={contract.errors} title="Errors" variant="danger" />
          <HealthFindingList emptyLabel="No warnings" items={contract.warnings} title="Warnings" variant="warning" />
          <HealthFindingList emptyLabel="No recent checks" items={checks} title="Checks" variant="info" />
        </div>
      </CardContent>
    </Card>
  );
}

function GlobalRegistryHealthPanel({ health }: { health: GlobalRegistryHealth }) {
  const summary = health.summary;
  const findings = health.findings ?? [];
  const checks = health.checks ?? [];
  const hasFindings = findings.length > 0;

  return (
    <Card className={cn(!health.ok && "border-rose-200 dark:border-rose-900")}>
      <CardHeader className="flex-wrap">
        <div>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Global Registry
          </CardTitle>
          <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
            {health.available ? "Shared multi-project registry health" : "Global registry not found"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant={health.ok ? "success" : "danger"}>{health.ok ? "Healthy" : "Blocked"}</Badge>
          <Badge variant="info">{health.global_goal_count} goals</Badge>
          <Badge variant={summary.action > 0 ? "warning" : "neutral"}>{summary.action} actions</Badge>
          <Badge variant={summary.high > 0 ? "danger" : "neutral"}>{summary.high} high</Badge>
          <Badge variant="neutral">{summary.info} info</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 text-sm md:grid-cols-3">
          <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
            <div className="text-xs text-slate-500 dark:text-zinc-400">Registry Scope</div>
            <div className="mt-1 font-medium">
              {health.current_registry_is_global ? "Global" : "Project-local"}
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
            <div className="text-xs text-slate-500 dark:text-zinc-400">Source Registries</div>
            <div className="mt-1 font-medium">{health.source_registry_count}</div>
          </div>
          <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
            <div className="text-xs text-slate-500 dark:text-zinc-400">Checks</div>
            <div className="mt-1 font-medium">{summary.checks}</div>
          </div>
        </div>

        {hasFindings ? (
          <div className="space-y-2">
            {findings.map((finding) => (
              <div
                className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900"
                key={`${finding.kind}-${finding.goal_id ?? finding.goal_ids.join(",")}-${finding.message}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={severityVariant[finding.severity] ?? "info"}>{finding.severity}</Badge>
                  <span className="font-medium">{finding.kind}</span>
                  {finding.goal_id ? <span className="break-all text-slate-500 dark:text-zinc-400">{finding.goal_id}</span> : null}
                </div>
                <p className="mt-2 leading-6 text-slate-700 dark:text-zinc-300">{finding.message}</p>
                {finding.goal_ids.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {finding.goal_ids.map((goalId) => (
                      <Badge key={goalId} variant="neutral">
                        {goalId}
                      </Badge>
                    ))}
                  </div>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                  {finding.recommended_action}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 dark:text-zinc-400">No stale source registry, missing state file, or duplicate goal id found.</p>
        )}

        {checks.length > 0 ? (
          <div className="space-y-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">
            {checks.map((check) => (
              <div key={check}>{check}</div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const search = dashboardRoute.useSearch();
  const navigate = dashboardRoute.useNavigate();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [payload, setPayload] = useState<StatusPayload>(exampleStatusPayload);
  const [source, setSource] = useState<DataSource>({ kind: "example", label: "bundled example" });
  const [statusUrl, setStatusUrl] = useState(search.statusUrl);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const queue = payload.attention_queue;
  const runHistory = payload.run_history;
  const goalRows = useMemo(
    () => buildGoalDirectoryRows(runHistory.goals, queue.items),
    [runHistory.goals, queue.items],
  );
  const rewardApiUrls = useMemo(() => buildRewardApiUrls(source), [source]);
  const controlPlaneApiUrls = useMemo(() => buildControlPlaneApiUrls(source, payload), [payload, source]);

  async function loadFromUrl(url: string) {
    const trimmed = url.trim();
    if (!trimmed) {
      setLoadError("status URL is empty");
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const response = await fetch(trimmed, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} while loading ${trimmed}`);
      }
      const nextPayload = parseStatusPayload(await response.json());
      setPayload(nextPayload);
      setSource({ kind: "url", label: trimmed });
      setStatusUrl(trimmed);
      await navigate({
        search: (current) => ({
          ...current,
          statusUrl: trimmed,
          view: routeViewForUrl(currentRouteView(current)),
        }),
      });
    } catch (error) {
      setLoadError(formatStatusError(error));
    } finally {
      setIsLoading(false);
    }
  }

  async function loadFromFile(file: File) {
    setIsLoading(true);
    setLoadError(null);
    try {
      const nextPayload = parseStatusPayload(JSON.parse(await file.text()));
      setPayload(nextPayload);
      setSource({ kind: "file", label: file.name });
    } catch (error) {
      setLoadError(formatStatusError(error));
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function resetToExample() {
    setPayload(exampleStatusPayload);
    setSource({ kind: "example", label: "bundled example" });
    setStatusUrl("");
    setLoadError(null);
    void navigate({
      search: (current) => ({
        ...current,
        statusUrl: "",
        view: routeViewForUrl(currentRouteView(current)),
      }),
    });
  }

  useEffect(() => {
    const trimmedStatusUrl = search.statusUrl.trim();
    if (trimmedStatusUrl) {
      if (source.kind !== "url" || source.label !== trimmedStatusUrl) {
        void loadFromUrl(trimmedStatusUrl);
      }
      return;
    }
    if (search.view !== "ops" && source.kind === "example") {
      void loadFromUrl(defaultGlobalStatusUrl);
    }
  }, [search.statusUrl, search.view, source.kind, source.label]);

  useEffect(() => {
    if (search.statusUrl && source.kind === "example") {
      return;
    }
    const goalIds = new Set(goalRows.map((row) => row.goal.id));
    if (goalRows.length === 0) {
      if (search.goalId) {
        void navigate({
          search: (current) => ({
            ...current,
            goalId: "",
          }),
        });
      }
      return;
    }
    if (search.goalId && !goalIds.has(search.goalId)) {
      void navigate({
        search: (current) => ({
          ...current,
          goalId: "",
        }),
      });
    }
  }, [goalRows, navigate, search.goalId, search.statusUrl, source.kind]);

  const filteredItems = queue.items.filter((item) => {
    const lane = laneFor(item)?.key ?? "all";
    const laneMatches = search.lane === "all" || search.lane === lane;
    const severityMatches = search.severity === "all" || search.severity === item.severity;
    return laneMatches && severityMatches;
  });
  const runHistoryOptions = goalRows.map((row) => row.goal.id);
  const selectedGoalId = runHistoryOptions.includes(search.goalId)
    ? search.goalId
    : runHistoryOptions[0] ?? "";
  const selectedGoal = runHistory.goals.find((goal) => goal.id === selectedGoalId);
  const selectedQueueItem = queue.items.find((item) => item.goal_id === selectedGoalId);
  const userActionItems = useMemo(
    () => buildUserActionSummaryItems({
      registry: payload.registry,
      rows: goalRows,
      runtimeRoot: payload.runtime_root,
    }),
    [goalRows, payload.registry, payload.runtime_root],
  );
  const selectedActionItem = useMemo(() => {
    const focusedItems = search.actionKind === "all"
      ? userActionItems
      : userActionItems.filter((item) => item.kind === search.actionKind);
    return (search.goalId ? focusedItems.find((item) => item.goalId === selectedGoalId) : undefined)
      ?? focusedItems[0]
      ?? (search.goalId ? userActionItems.find((item) => item.goalId === selectedGoalId) : undefined)
      ?? userActionItems[0];
  }, [search.actionKind, search.goalId, selectedGoalId, userActionItems]);
  const selectedReviewGoalId = selectedActionItem?.goalId ?? selectedGoalId;

  function selectGoal(goalId: string) {
    void navigate({
      search: (current) => ({
        ...current,
        goalId,
      }),
    });
  }

  if (search.view !== "ops") {
    return (
      <ShareEvidenceView
        isLoading={isLoading}
        onRefresh={() => void loadFromUrl(source.kind === "url" ? source.label : (statusUrl || defaultGlobalStatusUrl))}
        payload={payload}
        rows={goalRows}
        source={source}
        theme={theme}
        toggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
      />
    );
  }

  return (
    <div className={theme === "dark" ? "dark" : ""}>
      <div className="min-h-screen bg-[#f6f7f9] text-slate-950 dark:bg-[#09090b] dark:text-zinc-50">
        <div className="grid min-h-screen lg:grid-cols-[240px_1fr]">
          <aside className="border-b border-black/10 bg-[#0b0d12] text-white lg:border-b-0 lg:border-r dark:border-zinc-800">
            <div className="flex h-16 items-center gap-3 px-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white text-slate-950">
                <GitBranch className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-semibold">LoopX</div>
                <div className="text-xs text-zinc-400">Local control plane</div>
              </div>
            </div>
            <nav className="flex gap-1 px-3 pb-3 lg:block lg:space-y-1 lg:pb-0">
              <a className="flex items-center gap-2 rounded-md bg-white/10 px-3 py-2 text-sm font-medium text-white" href="/">
                <LayoutDashboard className="h-4 w-4" />
                Dashboard
              </a>
            </nav>
          </aside>

          <main className="min-w-0">
            <header className="sticky top-0 z-10 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90 sm:px-6">
              <div>
                <h1 className="text-2xl font-semibold">Goal Operations</h1>
                <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">
                  {payload.registry} · {payload.runtime_root}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button size="icon" variant="secondary" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme">
                  {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>
                <Button
                  disabled={isLoading}
                  onClick={() => (source.kind === "url" ? void loadFromUrl(source.label) : resetToExample())}
                  variant="primary"
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </Button>
              </div>
            </header>

            <div className="space-y-5 p-4 sm:p-6">
              <StatusContractFreshnessWarning payload={payload} source={source} />

              <section>
                <TodoFocusPanel rows={goalRows} onSelectGoal={selectGoal} selectedGoalId={selectedReviewGoalId} />
              </section>

              <section>
                <ProjectTodoExplorer
                  onProjectChange={(todoGoalId) =>
                    navigate({
                      search: (current) => ({
                        ...current,
                        todoGoalId,
                      }),
                    })
                  }
                  onQueryChange={(todoQuery) =>
                    navigate({
                      search: (current) => ({
                        ...current,
                        todoQuery,
                      }),
                    })
                  }
                  onRoleChange={(todoRole) =>
                    navigate({
                      search: (current) => ({
                        ...current,
                        todoRole,
                      }),
                    })
                  }
                  onSelectGoal={selectGoal}
                  onStatusChange={(todoStatus) =>
                    navigate({
                      search: (current) => ({
                        ...current,
                        todoStatus,
                      }),
                    })
                  }
                  query={search.todoQuery}
                  role={search.todoRole}
                  rows={goalRows}
                  selectedTodoGoalId={search.todoGoalId}
                  selectedGoalId={selectedGoalId}
                  status={search.todoStatus}
                  todoIndex={payload.todo_index}
                />
              </section>

              <section>
                <UserActionSummary
                  selectedKind={search.actionKind}
                  onSelectKind={(actionKind) =>
                    navigate({
                      search: (current) => ({
                        ...current,
                        actionKind,
                      }),
                    })
	                  }
	                  registry={payload.registry}
                  rows={goalRows}
                  runtimeRoot={payload.runtime_root}
                  onSelectGoal={selectGoal}
                  selectedGoalId={selectedReviewGoalId}
                  source={source}
                />
              </section>

              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard icon={payload.ok ? CheckCircle2 : CircleAlert} label="Status" value={payload.ok ? "Healthy" : "Blocked"} tone={payload.ok ? "success" : "danger"} />
                <MetricCard icon={GitBranch} label="Goals" value={String(payload.goal_count)} tone="neutral" />
                <MetricCard icon={Clock3} label="Runs" value={String(payload.run_count)} tone="info" />
                <MetricCard icon={FileJson2} label="Queue" value={String(queue.item_count)} tone="warning" />
              </section>

              <div className="grid gap-4 xl:grid-cols-4">
                <UsageStatsPanel usage={payload.usage_summary} />
                <EventLedgerSummaryPanel summary={payload.event_ledger_summary} />
                <PromotionReadinessSummaryPanel summary={payload.promotion_readiness_summary} />
                <PromotionGatePanel gate={payload.promotion_gate} />
                <DecisionFreshnessSummaryPanel summary={payload.decision_freshness_summary} />
              </div>

              <GoalDirectory rows={goalRows} onSelectGoal={selectGoal} selectedGoalId={selectedGoalId} />

              <GlobalRegistryHealthPanel health={payload.global_registry} />

              <ContractHealthPanel contract={payload.contract} />

              <Card>
                <CardContent className="pt-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={source.kind === "example" ? "neutral" : "success"}>Source</Badge>
                      <span className="break-all text-sm font-medium">{source.label}</span>
                      {loadError ? <Badge variant="danger">{loadError.slice(0, 120)}</Badge> : null}
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
                      <input
                        aria-label="Status URL"
                        className="h-9 min-w-0 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:ring-zinc-500 sm:min-w-72 sm:flex-1 lg:w-80 lg:flex-none"
                        onChange={(event) => setStatusUrl(event.target.value)}
                        placeholder={defaultLiveStatusUrl}
                        value={statusUrl}
                      />
                      <Button disabled={isLoading} onClick={() => void loadFromUrl(statusUrl)}>
                        <Link2 className="h-4 w-4" />
                        Load URL
                      </Button>
                      <input
                        accept="application/json,.json"
                        className="hidden"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) {
                            void loadFromFile(file);
                          }
                        }}
                        ref={fileInputRef}
                        type="file"
                      />
                      <Button disabled={isLoading} onClick={() => fileInputRef.current?.click()}>
                        <Upload className="h-4 w-4" />
                        Import JSON
                      </Button>
                      <Button disabled={isLoading} onClick={resetToExample} variant="ghost">
                        Example
                      </Button>
                      <Button disabled={isLoading} onClick={() => void loadFromUrl(defaultLiveStatusUrl)} variant="ghost">
                        Live
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div>
                    <CardTitle>Attention Lanes</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3 lg:grid-cols-3">
                    {laneConfig.map((lane) => {
                      const Icon = lane.icon;
                      const items = queue.items.filter((item) => lane.waitingOn.includes(item.waiting_on));
                      return (
                        <div className={cn("min-h-52 rounded-lg border p-3", lane.accent)} key={lane.key}>
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-sm font-semibold">
                              <Icon className="h-4 w-4" />
                              {lane.label}
                            </div>
                            <Badge>{items.length}</Badge>
                          </div>
                          <div className="mt-3 space-y-2">
                            {items.length === 0 ? (
                              <p className="text-sm opacity-70">Clear</p>
                            ) : (
                              items.map((item) => (
                                <button
                                  className="w-full rounded-md border border-current/15 bg-white/65 p-3 text-left text-sm transition hover:bg-white dark:bg-zinc-950/55 dark:hover:bg-zinc-950"
                                  key={item.goal_id}
                                  onClick={() => selectGoal(item.goal_id)}
                                  type="button"
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="break-all font-medium">{item.goal_id}</span>
                                    <StatusBadge value={item.severity} />
                                  </div>
                                  <p className="mt-2 text-xs leading-5 opacity-80">{item.recommended_action}</p>
                                  <QueueGateSummary compact item={item} />
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                <Card>
                  <CardHeader className="flex-wrap">
                    <div>
                      <CardTitle>Attention Queue</CardTitle>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Select
                        aria-label="Lane filter"
                        value={search.lane}
                        onChange={(event) =>
                          navigate({
                            search: (current) => ({
                              ...current,
                              lane: event.target.value as typeof search.lane,
                            }),
                          })
                        }
                      >
                        <option value="all">All lanes</option>
                        <option value="user">User / Controller</option>
                        <option value="codex">Codex Ready</option>
                        <option value="watch">Watching Evidence</option>
                      </Select>
                      <Select
                        aria-label="Severity filter"
                        value={search.severity}
                        onChange={(event) =>
                          navigate({
                            search: (current) => ({
                              ...current,
                              severity: event.target.value as typeof search.severity,
                            }),
                          })
                        }
                      >
                        <option value="all">All severity</option>
                        <option value="high">High</option>
                        <option value="action">Action</option>
                        <option value="watch">Watch</option>
                      </Select>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <QueueTable items={filteredItems} onSelectGoal={selectGoal} selectedGoalId={selectedGoalId} />
                  </CardContent>
                </Card>

                <div className="space-y-3">
                  {runHistoryOptions.length > 0 ? (
                    <Select aria-label="Run history goal" onChange={(event) => selectGoal(event.target.value)} value={selectedGoalId}>
                      {runHistoryOptions.map((goalId) => (
                        <option key={goalId} value={goalId}>
                          {goalId}
                        </option>
                      ))}
                    </Select>
                  ) : null}
                  <RunHistoryPanel
                    controlPlaneApplyUrl={controlPlaneApiUrls.applyUrl}
                    controlPlaneDryRunUrl={controlPlaneApiUrls.dryRunUrl}
                    controlPlaneWriteEnabled={controlPlaneApiUrls.writeEnabled}
                    goal={selectedGoal}
                    onStatusRefresh={async () => {
                      if (source.kind === "url") {
                        await loadFromUrl(source.label);
                      }
                    }}
                    queueItem={selectedQueueItem}
                    registry={payload.registry}
                    rewardAppendUrl={rewardApiUrls.appendUrl}
                    rewardDryRunUrl={rewardApiUrls.dryRunUrl}
                    runtimeRoot={payload.runtime_root}
                  />
                </div>
              </section>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function formatUsageCount(value?: number | null) {
  return String(value ?? 0);
}

function formatUsageShare(value?: number | null) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function UsageMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-h-20 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs font-medium uppercase text-slate-500 dark:text-zinc-400">{label}</div>
      <div className="mt-2 break-words text-2xl font-semibold text-slate-950 dark:text-zinc-50">{value}</div>
    </div>
  );
}

function EventLedgerSummaryPanel({ summary }: { summary?: EventLedgerSummary | null }) {
  if (!summary?.available) {
    return null;
  }
  const totals = summary.totals;
  const topGoals = summary.goals.slice(0, 5);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <History className="h-4 w-4" />
          控制面事件账本
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{summary.source}</Badge>
          <Badge variant="neutral">{summary.sample_run_count} samples</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
          Chat thread 不是 source of truth；这里是 run history 的 compact 投影，用来判断最近事实是推进、证据、决策、状态还是花费。
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {eventClassOrder.map((eventClass) => (
            <UsageMetric
              key={eventClass}
              label={eventClassLabel[eventClass]}
              value={`${eventClassCount(totals.by_class_24h, eventClass)} / ${eventClassCount(totals.by_class_7d, eventClass)}`}
            />
          ))}
        </div>
        {topGoals.length ? (
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 dark:border-zinc-800">
            <div className="grid grid-cols-[minmax(0,1fr)_72px_72px_92px] gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <div>Goal</div>
              <div className="text-right">24h</div>
              <div className="text-right">7d</div>
              <div className="text-right">Latest</div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-zinc-800">
              {topGoals.map((goal) => (
                <div
                  className="grid grid-cols-[minmax(0,1fr)_72px_72px_92px] gap-2 px-3 py-2 text-sm"
                  key={goal.goal_id}
                >
                  <div className="min-w-0 break-all font-medium text-slate-900 dark:text-zinc-100">{goal.goal_id}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{goal.events_24h}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{goal.events_7d}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{eventClassLabel[goal.latest_event_class as EventLedgerClass] ?? goal.latest_event_class ?? "unknown"}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {summary.proxy_note ? (
          <div className="mt-3 text-xs text-slate-500 dark:text-zinc-400">{summary.proxy_note}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function promotionReadinessVariant(summary: PromotionReadinessSummary): "success" | "warning" | "danger" {
  if (summary.is_fresh && !summary.requires_readiness_run) {
    return "success";
  }
  if (summary.freshness_status === "missing" || summary.freshness_status === "unknown") {
    return "danger";
  }
  return "warning";
}

function promotionGateVariant(gate: PromotionGate): "success" | "warning" | "danger" {
  if (gate.can_promote && !gate.should_warn) {
    return "success";
  }
  if (gate.gate_state === "warning") {
    return "warning";
  }
  return "danger";
}

function PromotionReadinessSummaryPanel({ summary }: { summary?: PromotionReadinessSummary | null }) {
  if (!summary) {
    return null;
  }
  const variant = promotionReadinessVariant(summary);
  const status = summary.freshness_status ?? "unknown";
  const age = summary.age_hours == null ? "n/a" : `${summary.age_hours}h`;
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4" />
          Promotion readiness
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant={variant}>{status}</Badge>
          <Badge variant={summary.requires_readiness_run ? "warning" : "success"}>
            {summary.requires_readiness_run ? "rerun needed" : "ready"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
          这里从同一份 append-only run history 观察 canary promotion readiness；chat thread 和安装器日志都不是 source of truth。
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <UsageMetric label="Freshness" value={status} />
          <UsageMetric label="Age" value={age} />
          <UsageMetric label="Samples" value={formatUsageCount(summary.sample_run_count)} />
        </div>
        <div className="mt-4 space-y-1 text-xs text-slate-500 dark:text-zinc-400">
          <div className="break-all">goal={summary.goal_id ?? "none"}</div>
          <div>window={summary.freshness_window_hours ?? 24}h · artifacts={String(Boolean(summary.json_exists))}/{String(Boolean(summary.markdown_exists))}</div>
          {summary.generated_at ? <div>generated_at={summary.generated_at}</div> : null}
          {summary.reason ? <div>{summary.reason}</div> : null}
          {summary.proxy_note ? <div>{summary.proxy_note}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function PromotionGatePanel({ gate }: { gate?: PromotionGate | null }) {
  if (!gate) {
    return null;
  }
  const readiness = gate.readiness;
  const variant = promotionGateVariant(gate);
  const freshness = readiness?.freshness_status ?? "unknown";
  const age = readiness?.age_hours == null ? "n/a" : `${readiness.age_hours}h`;
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4" />
          Promotion gate
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant={variant}>{gate.gate_state ?? "unknown"}</Badge>
          <Badge variant={gate.can_promote ? "success" : "warning"}>
            {gate.can_promote ? "promote ok" : "check first"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <UsageMetric label="Can promote" value={gate.can_promote ? "yes" : "no"} />
          <UsageMetric label="Freshness" value={freshness} />
          <UsageMetric label="Age" value={age} />
        </div>
        <div className="mt-4 space-y-1 text-xs text-slate-500 dark:text-zinc-400">
          <div>should_warn={String(gate.should_warn)} · non_blocking={String(gate.non_blocking)}</div>
          {readiness?.generated_at ? <div>generated_at={readiness.generated_at}</div> : null}
          {gate.recommended_action ? <div className="break-words">action={gate.recommended_action}</div> : null}
          {gate.warning_message ? <div className="break-words text-amber-700 dark:text-amber-300">{gate.warning_message}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function DecisionFreshnessSummaryPanel({ summary }: { summary?: DecisionFreshnessSummary | null }) {
  if (!summary?.available) {
    return null;
  }
  const counts = summary.summary;
  const topItems = summary.items
    .filter((item) => item.requires_decision_point_rebase || item.freshness_state !== "fresh")
    .sort((left, right) => {
      const leftStale = left.requires_decision_point_rebase ? 0 : 1;
      const rightStale = right.requires_decision_point_rebase ? 0 : 1;
      return leftStale - rightStale
        || (right.newer_event_count_7d ?? 0) - (left.newer_event_count_7d ?? 0)
        || (right.age_days ?? 0) - (left.age_days ?? 0);
    })
    .slice(0, 5);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <RotateCcw className="h-4 w-4" />
          决策 freshness
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant={counts.rebase_required_count > 0 ? "warning" : "success"}>
            rebase {counts.rebase_required_count}
          </Badge>
          <Badge variant="neutral">{summary.window_days}d window</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
          这里看旧 reward / gate 是否需要在审批或转交前重读当前控制面状态；exact replay 仍回到 append-only run history。
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <UsageMetric label="Decisions" value={formatUsageCount(counts.decision_count)} />
          <UsageMetric label="Stale" value={formatUsageCount(counts.stale_count)} />
          <UsageMetric label="Rebase" value={formatUsageCount(counts.rebase_required_count)} />
          <UsageMetric label="Fresh" value={formatUsageCount(counts.fresh_count)} />
        </div>
        {topItems.length ? (
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 dark:border-zinc-800">
            <div className="grid grid-cols-[minmax(0,1fr)_92px_72px_72px] gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <div>Goal</div>
              <div className="text-right">State</div>
              <div className="text-right">Events</div>
              <div className="text-right">Age</div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-zinc-800">
              {topItems.map((item, index) => (
                <div
                  className="grid grid-cols-[minmax(0,1fr)_92px_72px_72px] gap-2 px-3 py-2 text-sm"
                  key={`${item.goal_id}-${item.decision_at ?? index}`}
                >
                  <div className="min-w-0">
                    <div className="break-all font-medium text-slate-900 dark:text-zinc-100">{item.goal_id}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500 dark:text-zinc-400">
                      {shareDecisionKindLabel(item.decision_kind)}
                    </div>
                  </div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">
                    {shareDecisionFreshnessStateLabel(item.freshness_state)}
                  </div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{item.newer_event_count_7d ?? 0}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">
                    {item.age_days != null ? `${Math.round(item.age_days)}d` : "-"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100">
            当前样本里没有需要 rebase 的 checkpointed decision。
          </div>
        )}
        {summary.proxy_note ? (
          <div className="mt-3 text-xs text-slate-500 dark:text-zinc-400">{summary.proxy_note}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function UsageStatsPanel({ usage }: { usage?: UsageSummary | null }) {
  if (!usage?.available) {
    return null;
  }
  const totals = usage.totals;
  const topGoals = usage.goals.slice(0, 5);
  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-4 w-4" />
          Usage Snapshot
        </CardTitle>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{usage.source}</Badge>
          <Badge variant="neutral">{usage.sample_run_count} samples</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <UsageMetric label="24h turns" value={formatUsageCount(totals.runs_24h)} />
          <UsageMetric label="7d turns" value={formatUsageCount(totals.runs_7d)} />
          <UsageMetric
            label="Quota slots"
            value={`${formatUsageCount(totals.quota_spend_slots_24h)} / ${formatUsageCount(totals.quota_spend_slots_7d)}`}
          />
          <UsageMetric
            label="Automation"
            value={`${formatUsageCount(totals.automation_run_count_24h)} / ${formatUsageCount(totals.automation_run_count_7d)}`}
          />
          <UsageMetric
            label="Progress"
            value={`${formatUsageCount(totals.progress_signal_run_count_24h)} / ${formatUsageCount(totals.progress_signal_run_count_7d)}`}
          />
        </div>
        {topGoals.length ? (
          <div className="mt-4 overflow-hidden rounded-lg border border-slate-200 dark:border-zinc-800">
            <div className="grid grid-cols-[minmax(0,1fr)_70px_70px_80px_80px] gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <div>Goal</div>
              <div className="text-right">24h</div>
              <div className="text-right">7d</div>
              <div className="text-right">Progress</div>
              <div className="text-right">Share</div>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-zinc-800">
              {topGoals.map((goal) => (
                <div
                  className="grid grid-cols-[minmax(0,1fr)_70px_70px_80px_80px] gap-2 px-3 py-2 text-sm"
                  key={goal.goal_id}
                >
                  <div className="min-w-0 break-all font-medium text-slate-900 dark:text-zinc-100">{goal.goal_id}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{goal.runs_24h}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{goal.runs_7d}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{goal.progress_signal_run_count_24h}</div>
                  <div className="text-right text-slate-600 dark:text-zinc-300">{formatUsageShare(goal.project_share_24h)}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {usage.proxy_note ? (
          <div className="mt-3 text-xs text-slate-500 dark:text-zinc-400">{usage.proxy_note}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone: "neutral" | "success" | "warning" | "info" | "danger";
}) {
  const toneClass = {
    neutral: "text-slate-700 dark:text-zinc-300",
    success: "text-emerald-700 dark:text-emerald-300",
    warning: "text-amber-700 dark:text-amber-300",
    info: "text-sky-700 dark:text-sky-300",
    danger: "text-rose-700 dark:text-rose-300",
  }[tone];
  return (
    <Card className="min-h-32">
      <CardHeader>
        <div>
          <CardTitle>{label}</CardTitle>
          <div className="mt-3 text-3xl font-semibold">{value}</div>
        </div>
        <Icon className={cn("h-5 w-5", toneClass)} />
      </CardHeader>
    </Card>
  );
}
