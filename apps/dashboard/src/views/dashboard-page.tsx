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
  ControllerReadiness,
  GlobalRegistryHealth,
  HumanReward,
  OperatorGate,
  ProjectMap,
  ReviewMaterial,
  RewardDryRunResponse,
  RunGoal,
  RunRecord,
  StatusPayload,
  ProjectAssetTodoSummary,
  TodoGroup,
  exampleStatusPayload,
  formatStatusError,
  parseRewardDryRunResponse,
  parseStatusPayload,
} from "../data/status";
import { buildActionPacket } from "../data/action-packet";
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
const rewardOptions = ["positive", "mixed", "neutral", "negative"] as const;
const inputClassName =
  "h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:ring-zinc-500";

type RewardValue = (typeof rewardOptions)[number];

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
    "goal-harness \\",
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
  return {
    source_section: fallback?.source_section ?? sourceSection,
    total_count: summary.total ?? fallback?.total_count ?? 0,
    open_count: summary.open ?? fallback?.open_count ?? 0,
    done_count: summary.done ?? fallback?.done_count ?? 0,
    items: next
      ? [{
          index: fallbackFirstOpen?.index ?? 1,
          done: false,
          text: next,
          review_materials: fallbackFirstOpen?.review_materials ?? [],
        }]
      : (fallback?.items ?? []),
  };
}

function todoCountLabel(todos?: TodoGroup | null) {
  if (!todos || todos.total_count === 0) {
    return null;
  }
  return `${todos.open_count}/${todos.total_count} open`;
}

function UserTodoCallout({
  blocksGate,
  goalId,
  source,
  todos,
}: {
  blocksGate?: boolean;
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
        <Badge variant="success">{blocksGate ? "先做用户待办" : "Next user todo"}</Badge>
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
  return "记录规则：如需持久记录本次判断，先用本地 operator-gate dry-run 预览；确认写入时去掉 --dry-run；拒绝/暂缓用 reject/defer + public-safe 原因。";
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
  present,
  total,
}: {
  declared: boolean;
  conflictRisk?: string | null;
  deprecatedCount: number;
  present: number;
  total: number;
}): BadgeVariant {
  if (!declared) {
    return "neutral";
  }
  const risk = normalizeConflictRisk(conflictRisk);
  if (risk === "high" || deprecatedCount > 0 || (total > 0 && present < total)) {
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
  deprecatedCount,
  conflictRisk,
}: {
  declared?: boolean | null;
  pathExists?: boolean | null;
  present?: number | null;
  total?: number | null;
  topics?: number | null;
  deprecatedCount?: number | null;
  conflictRisk?: string | null;
}): AuthorityCoverage | undefined {
  const isDeclared = Boolean(declared);
  if (!isDeclared && !total && !topics) {
    return undefined;
  }
  const presentCount = present ?? 0;
  const totalCount = total ?? 0;
  const topicCount = topics ?? 0;
  const deprecated = deprecatedCount ?? 0;
  const risk = normalizeConflictRisk(conflictRisk);
  const pathText = pathExists == null ? "path unchecked" : pathExists ? "path ok" : "path missing";
  const entryText = totalCount > 0 ? `default entries ${presentCount}/${totalCount}` : "default entries not declared";
  const riskText = risk === "unknown" ? "risk unknown" : `risk ${risk}`;
  const badge = !isDeclared
    ? "No registry"
    : risk === "high" || risk === "medium" || deprecated > 0 || (totalCount > 0 && presentCount < totalCount)
      ? "Needs review"
      : "Covered";
  return {
    badge,
    reviewLine: isDeclared
      ? `权威源：已声明；${pathText}；${entryText}；topic ${topicCount}；${riskText}${deprecated ? `；deprecated ${deprecated}` : ""}。`
      : "权威源：未声明 authority registry；只能看到普通 authority sources。",
    shortLine: isDeclared
      ? `${entryText}; topic ${topicCount}; ${riskText}`
      : "authority registry not declared",
    variant: authorityCoverageVariant({
      declared: isDeclared,
      conflictRisk: risk,
      deprecatedCount: deprecated,
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
    conflictRisk: projectMap.authority_registry_conflict_risk,
  });
}

const quotaStateLabel: Record<string, string> = {
  blocked_health: "Health blocked",
  eligible: "Eligible",
  operator_gate: "Operator gate",
  paused: "Paused",
  throttled: "Throttled",
  waiting: "Waiting",
};

const quotaStateReviewLabel: Record<string, string> = {
  blocked_health: "先修健康阻塞",
  eligible: "可自动推进",
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
  const stateLabel = quotaStateLabel[state] ?? state;
  const reviewState = quotaStateReviewLabel[state] ?? state;
  return {
    label: `Quota ${computeText}`,
    shortLine: `${stateLabel}; ${spent}/${allowed} slots`,
    reviewLine: `配额：compute ${computeText}；${reviewState}；${spent}/${allowed} slots。`,
    variant: quotaVariant(state),
  };
}

function QuotaChip({ quota }: { quota?: ComputeQuota | null }) {
  const view = buildQuotaView(quota);
  if (!view) {
    return null;
  }
  return <Badge variant={view.variant}>{view.label}</Badge>;
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
  const todo = firstOpenTodo(item.userTodos);
  const reply = item.kind === "controller" ? controllerReplyLine(item.goalId) : prompt.reply;
  const command = item.safePathCommand ?? buildStatusCommand({ registry, runtimeRoot });
  const todoBlocksGate = Boolean(todo && item.operatorQuestion);
  return buildActionPacket({
    goalId: item.goalId,
    title: item.title,
    summary: item.summary,
    userTodoText: todo?.text,
    todoBlocksGate,
    operatorQuestion: item.operatorQuestion,
    suggestedReply: reply,
    gateFallbackDecision: suggestedDecisionLine(item.kind, item, item.goalId),
    boundary: prompt.boundary,
    durableRecordRule: durableOperatorGateRecordRule(item.kind),
    safePathLabel: item.safePathLabel,
    command,
    quotaShortLine: quotaView?.shortLine,
    authorityShortLine: item.authorityCoverage?.shortLine,
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
    "goal-harness \\",
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
    "goal-harness \\",
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
    "goal-harness \\",
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
    "goal-harness \\",
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
    "goal-harness \\",
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
    const quota = projectAsset?.quota ?? row.queueItem?.quota ?? row.goal.quota;
    const quotaState = quota?.state ?? "waiting";
    const userTodos = todosFromProjectAssetSummary(projectAsset?.user_todos, row.queueItem?.user_todos, "project_asset.user_todos");
    const agentTodos = todosFromProjectAssetSummary(projectAsset?.agent_todos, row.queueItem?.agent_todos, "project_asset.agent_todos");
    const nextAction = projectAsset?.next_action ?? decision.action;
    const stopCondition = projectAsset?.stop_condition ?? handoffCondition ?? decision.action;
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
                          {copyState === "copied" ? "Copied" : "Copy"}
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
                      {item.draftLabel ? <Badge variant="info">{item.draftLabel}</Badge> : null}
                    </div>
                    <UserTodoCallout
                      blocksGate={Boolean(item.operatorQuestion && firstOpenTodo(item.userTodos))}
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
  goal,
  queueItem,
  registry,
  runtimeRoot,
  rewardDryRunUrl,
  rewardAppendUrl,
  onStatusRefresh,
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
  rewardDryRunUrl: string | null;
  rewardAppendUrl: string | null;
  onStatusRefresh: () => Promise<void>;
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
      }),
    });
  }

  useEffect(() => {
    if (search.statusUrl) {
      void loadFromUrl(search.statusUrl);
    }
  }, []);

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
                <div className="text-sm font-semibold">Goal Harness</div>
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
