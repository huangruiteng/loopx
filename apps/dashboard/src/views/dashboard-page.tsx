import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileCheck2,
  FileJson2,
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
  ControllerReadiness,
  HumanReward,
  RunGoal,
  RunRecord,
  StatusPayload,
  exampleStatusPayload,
  formatStatusError,
  parseStatusPayload,
} from "../data/status";
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

type DataSource =
  | { kind: "example"; label: "bundled example" }
  | { kind: "url"; label: string }
  | { kind: "file"; label: string };

const defaultLiveStatusUrl = "http://127.0.0.1:8765/status.json";

type GoalDirectoryRow = {
  goal: RunGoal;
  queueItem?: QueueItem;
  latestRun?: RunRecord;
  status: string;
  waitingOn: string;
  severity: string;
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
}: {
  goalId: string;
  registry: string;
  runtimeRoot: string;
  runGeneratedAt: string;
}) {
  return [
    "goal-harness \\",
    `  --registry ${shellQuote(registry)} \\`,
    `  --runtime-root ${shellQuote(runtimeRoot)} \\`,
    "  reward \\",
    `  --goal-id ${shellQuote(goalId)} \\`,
    `  --run-generated-at ${shellQuote(runGeneratedAt)} \\`,
    "  --decision '<decision_label>' \\",
    "  --reward positive \\",
    "  --reason-summary '<public_safe_reason>' \\",
    "  --follow-up '<next_condition>' \\",
    "  --dry-run",
  ].join("\n");
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
    return {
      goal,
      queueItem,
      latestRun,
      status: queueItem?.status ?? latestRun?.classification ?? goal.status ?? "no_status",
      waitingOn: queueItem?.waiting_on ?? "clear",
      severity: queueItem?.severity ?? "clear",
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
                  </div>
                  <div className="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-zinc-400">
                    {row.waitingOn === "clear" ? "No attention item" : waitingLabel[row.waitingOn] ?? row.waitingOn}
                  </div>
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
        accessorKey: "recommended_action",
        header: "Action",
        cell: ({ row }) => <ShortText>{row.original.recommended_action}</ShortText>,
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

function readinessVariant(readiness: ControllerReadiness): "success" | "warning" | "info" {
  if (readiness.decision_advisor_ready) {
    return "success";
  }
  if (readiness.read_only_observer_ready) {
    return "info";
  }
  return "warning";
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

function LatestRun({ run }: { run: RunRecord }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-500 dark:text-zinc-400">{run.generated_at}</span>
        <Badge variant="info">{formatNullable(run.classification, "unclassified")}</Badge>
        {run.health_check ? <Badge variant="success">{run.health_check}</Badge> : null}
        {run.human_reward ? <Badge variant={rewardVariant(run.human_reward.reward)}>Reward</Badge> : null}
        {run.controller_readiness ? <Badge variant={readinessVariant(run.controller_readiness)}>Readiness</Badge> : null}
        <Badge variant={artifactVariant(run.json_exists)}>JSON</Badge>
        <Badge variant={artifactVariant(run.markdown_exists)}>Markdown</Badge>
      </div>
      {run.recommended_action ? (
        <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-zinc-300">{run.recommended_action}</p>
      ) : null}
      {run.controller_readiness ? <ControllerReadinessSummary readiness={run.controller_readiness} /> : null}
      {run.human_reward ? <HumanRewardSummary reward={run.human_reward} /> : null}
    </div>
  );
}

function RewardCommandDraft({
  goal,
  registry,
  runtimeRoot,
}: {
  goal?: RunGoal;
  registry: string;
  runtimeRoot: string;
}) {
  const latestRun = goal?.latest_runs[0];
  const command = goal && latestRun
    ? buildRewardCommand({
        goalId: goal.id,
        registry,
        runtimeRoot,
        runGeneratedAt: latestRun.generated_at,
      })
    : "";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center gap-2">
        <Terminal className="h-4 w-4 text-slate-500 dark:text-zinc-400" />
        <span className="font-medium">Reward CLI Draft</span>
        <Badge variant="info">local-only</Badge>
        <Badge variant={command ? "warning" : "neutral"}>{command ? "dry-run" : "needs run"}</Badge>
      </div>
      {command ? (
        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-950 p-3 text-xs leading-5 text-slate-50 dark:border-zinc-800">
          {command}
        </pre>
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
}: {
  goal?: RunGoal;
  queueItem?: QueueItem;
  registry: string;
  runtimeRoot: string;
}) {
  const latestRuns = goal?.latest_runs ?? [];
  const artifactReady = latestRuns.filter((run) => run.json_exists && run.markdown_exists).length;
  const rewardReady = latestRuns.filter((run) => Boolean(run.human_reward)).length;
  const readinessReady = latestRuns.filter((run) => Boolean(run.controller_readiness)).length;
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
          </div>

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
            </div>
          ) : null}

          <RewardCommandDraft goal={goal} registry={registry} runtimeRoot={runtimeRoot} />

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

export function DashboardPage() {
  const search = dashboardRoute.useSearch();
  const navigate = dashboardRoute.useNavigate();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [payload, setPayload] = useState<StatusPayload>(exampleStatusPayload);
  const [source, setSource] = useState<DataSource>({ kind: "example", label: "bundled example" });
  const [statusUrl, setStatusUrl] = useState(search.statusUrl);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedGoalId, setSelectedGoalId] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const queue = payload.attention_queue;
  const runHistory = payload.run_history;
  const goalRows = useMemo(
    () => buildGoalDirectoryRows(runHistory.goals, queue.items),
    [runHistory.goals, queue.items],
  );

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
    const goalIds = new Set(goalRows.map((row) => row.goal.id));
    if (!selectedGoalId || !goalIds.has(selectedGoalId)) {
      setSelectedGoalId(goalRows[0]?.goal.id ?? "");
    }
  }, [goalRows, selectedGoalId]);

  const filteredItems = queue.items.filter((item) => {
    const lane = laneFor(item)?.key ?? "all";
    const laneMatches = search.lane === "all" || search.lane === lane;
    const severityMatches = search.severity === "all" || search.severity === item.severity;
    return laneMatches && severityMatches;
  });
  const selectedGoal = runHistory.goals.find((goal) => goal.id === selectedGoalId);
  const selectedQueueItem = queue.items.find((item) => item.goal_id === selectedGoalId);
  const runHistoryOptions = goalRows.map((row) => row.goal.id);

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

              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard icon={payload.ok ? CheckCircle2 : CircleAlert} label="Status" value={payload.ok ? "Healthy" : "Blocked"} tone={payload.ok ? "success" : "danger"} />
                <MetricCard icon={GitBranch} label="Goals" value={String(payload.goal_count)} tone="neutral" />
                <MetricCard icon={Clock3} label="Runs" value={String(payload.run_count)} tone="info" />
                <MetricCard icon={FileJson2} label="Queue" value={String(queue.item_count)} tone="warning" />
              </section>

              <GoalDirectory rows={goalRows} onSelectGoal={setSelectedGoalId} selectedGoalId={selectedGoalId} />

              <ContractHealthPanel contract={payload.contract} />

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
                                  onClick={() => setSelectedGoalId(item.goal_id)}
                                  type="button"
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="break-all font-medium">{item.goal_id}</span>
                                    <StatusBadge value={item.severity} />
                                  </div>
                                  <p className="mt-2 text-xs leading-5 opacity-80">{item.recommended_action}</p>
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
                    <QueueTable items={filteredItems} onSelectGoal={setSelectedGoalId} selectedGoalId={selectedGoalId} />
                  </CardContent>
                </Card>

                <div className="space-y-3">
                  {runHistoryOptions.length > 0 ? (
                    <Select aria-label="Run history goal" onChange={(event) => setSelectedGoalId(event.target.value)} value={selectedGoalId}>
                      {runHistoryOptions.map((goalId) => (
                        <option key={goalId} value={goalId}>
                          {goalId}
                        </option>
                      ))}
                    </Select>
                  ) : null}
                  <RunHistoryPanel
                    goal={selectedGoal}
                    queueItem={selectedQueueItem}
                    registry={payload.registry}
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
