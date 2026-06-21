import {
  Activity,
  BarChart3,
  Bot,
  CircleAlert,
  Clock3,
  ExternalLink,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import showcaseCatalog from "../../../../docs/showcases/showcase-catalog.json";
import { frontstageRoute } from "../router";
import {
  GoalChannelProjection,
  GoalChannelTodo,
  sampleGoalChannelProjection,
} from "../data/goal-channel-frontstage";
import { QueueItem, StatusPayload, formatStatusError } from "../data/status";
import {
  LocalDashboardApiCapabilities,
  StatusContractFreshnessIssue,
  fetchFrontstageStatusPayload,
  localDashboardApiCapabilities,
  resolveFrontstageOpsStatusUrl,
  statusContractFreshnessIssue,
} from "../data/local-status-query";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select } from "../components/ui/select";
import { cn } from "../lib/utils";

type BadgeTone = "neutral" | "success" | "warning" | "info" | "danger";
type FrontstageSource = { kind: "demo"; label: string } | { kind: "url"; label: string };
type FrontstageMode = "showcase" | "developer" | "ops";
type TodoLaneFilter = "all" | "user" | "agent";
type NumberRange = { low?: number; high?: number };
type ShowcaseFrontstageCase = {
  id: string;
  title: string;
  status?: string;
  headline?: string;
  domain?: string;
  case_page?: string;
  evidence_boundary?: string;
  feature_points?: string[];
  pattern_tags?: string[];
  frontend_card?: {
    badges?: string[];
    primary_metric_hint?: string;
    story_beats?: string[];
    visual_metaphor?: string;
  };
  workload_signal?: {
    whole_repository?: {
      commit_count?: number;
      files_touched?: number;
    };
    public_window?: {
      calendar_days?: number;
      active_commit_days?: number;
    };
    efficiency_model?: {
      baseline?: string;
      estimated_developer_days?: NumberRange;
      single_engineer_calendar_compression?: NumberRange;
      two_person_team_calendar_compression?: NumberRange;
      claim_boundary?: string;
    };
  };
};

const showcaseCases = (showcaseCatalog as { cases: ShowcaseFrontstageCase[] }).cases;
const selfIterationShowcase = showcaseCases.find(
  (item) => item.id === "2026-06-19-loopx-self-iteration",
);
const frontstageShowcases = showcaseCases.filter((item) => item.frontend_card);

type ProjectionOption = {
  goalId: string;
  projection: GoalChannelProjection;
  queueItem: QueueItem;
};

function boolBadge(value: boolean, trueLabel: string, falseLabel: string) {
  return (
    <Badge variant={value ? "success" : "neutral"}>
      {value ? trueLabel : falseLabel}
    </Badge>
  );
}

function statusTone(value?: string): BadgeTone {
  if (!value) {
    return "neutral";
  }
  if (["done", "closed", "resolved"].includes(value)) {
    return "success";
  }
  if (["blocked", "action_required", "waiting"].includes(value)) {
    return "warning";
  }
  if (["failed", "error"].includes(value)) {
    return "danger";
  }
  return "info";
}

function priorityTone(priority?: string): BadgeTone {
  if (priority === "P0") {
    return "danger";
  }
  if (priority === "P1") {
    return "warning";
  }
  if (priority === "P2") {
    return "info";
  }
  return "neutral";
}

function stringifyScalar(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return String(value);
}

function warningMessage(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return value ?? "compact source warning";
}

function artifactDisplayValue(value: string | number | boolean | null | undefined) {
  const text = stringifyScalar(value);
  return text.length > 96 ? `${text.slice(0, 93)}...` : text;
}

function countOpenTodos(todos: GoalChannelTodo[]) {
  return todos.filter((todo) => todo.status === "open").length;
}

function countClaimedTodos(todos: GoalChannelTodo[]) {
  return todos.filter((todo) => Boolean(todo.claimed_by)).length;
}

function todoSearchText(todo: GoalChannelTodo) {
  return [
    todo.todo_id,
    todo.priority,
    todo.status,
    todo.title,
    todo.claimed_by,
    todo.task_class,
    todo.action_kind,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function filterTodosByQuery(todos: GoalChannelTodo[], normalizedQuery: string) {
  if (!normalizedQuery) {
    return todos;
  }
  return todos.filter((todo) => todoSearchText(todo).includes(normalizedQuery));
}

function countShowcaseStoryBeats() {
  return frontstageShowcases.reduce(
    (total, item) => total + (item.frontend_card?.story_beats?.length ?? 0),
    0,
  );
}

function uniqueShowcaseDomains() {
  return Array.from(
    new Set(frontstageShowcases.map((item) => item.domain).filter((value): value is string => Boolean(value))),
  ).sort();
}

function showcaseSearchText(item: ShowcaseFrontstageCase) {
  return [
    item.title,
    item.headline,
    item.domain,
    item.status,
    item.evidence_boundary,
    ...(item.feature_points ?? []),
    ...(item.pattern_tags ?? []),
    ...(item.frontend_card?.badges ?? []),
    item.frontend_card?.primary_metric_hint,
    item.frontend_card?.visual_metaphor,
    ...(item.frontend_card?.story_beats ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function showcaseCaseHref(casePage?: string) {
  if (!casePage) {
    return undefined;
  }
  return `https://github.com/huangruiteng/loopx/blob/main/${casePage}`;
}

function uniqueClaimOwners(projection: GoalChannelProjection) {
  return Array.from(
    new Set(
      [
        ...projection.agent_todos.map((todo) => todo.claimed_by),
        ...projection.active_leases.map((lease) => lease.owner_agent),
      ].filter(Boolean),
    ),
  );
}

function formatNumber(value: number | undefined, fallback = "n/a") {
  if (value === undefined) {
    return fallback;
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

function formatRange(range: NumberRange | undefined, suffix = "") {
  if (!range || range.low === undefined || range.high === undefined) {
    return "n/a";
  }
  return `${formatNumber(range.low)}-${formatNumber(range.high)}${suffix}`;
}

function TodoRow({ todo }: { todo: GoalChannelTodo }) {
  return (
    <div className="grid gap-3 border-b border-slate-200 px-3 py-3 last:border-b-0 md:grid-cols-[96px_minmax(0,1fr)_156px]">
      <div className="flex flex-wrap gap-1">
        {todo.priority ? <Badge variant={priorityTone(todo.priority)}>{todo.priority}</Badge> : null}
        <Badge variant={statusTone(todo.status)}>{todo.status}</Badge>
      </div>
      <div className="min-w-0">
        <p className="break-words text-sm font-medium leading-6 text-slate-950">{todo.title}</p>
        <div className="mt-1 flex flex-wrap gap-2 text-[11px] font-medium text-slate-500">
          {todo.todo_id ? <span>{todo.todo_id}</span> : null}
          {todo.action_kind ? <span>{todo.action_kind}</span> : null}
          {todo.task_class ? <span>{todo.task_class}</span> : null}
        </div>
      </div>
      <div className="flex items-start justify-start md:justify-end">
        {todo.claimed_by ? (
          <Badge variant="info">
            <Bot className="h-3 w-3" />
            {todo.claimed_by}
          </Badge>
        ) : (
          <Badge variant="neutral">unclaimed</Badge>
        )}
      </div>
    </div>
  );
}

function TodoLaneEmpty({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-4 py-4 text-sm font-medium leading-6 text-slate-500">
      {children}
    </div>
  );
}

function projectionOptionsFromPayload(payload: StatusPayload): ProjectionOption[] {
  return payload.attention_queue.items.flatMap((item) => {
    if (!item.goal_channel_projection) {
      return [];
    }
    return [{
      goalId: item.goal_id,
      projection: item.goal_channel_projection,
      queueItem: item,
    }];
  });
}

function Panel({
  children,
  className,
  title,
  icon: Icon,
}: {
  children: React.ReactNode;
  className?: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}) {
  return (
    <section className={cn("rounded-lg border border-slate-200 bg-white shadow-sm", className)}>
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <Icon className="h-4 w-4 text-slate-500" />
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function EfficiencyEvidencePanel() {
  const workload = selfIterationShowcase?.workload_signal;
  const model = workload?.efficiency_model;
  if (!selfIterationShowcase || !workload || !model) {
    return null;
  }

  const metrics = [
    {
      label: "public Git facts",
      value: `${formatNumber(workload.whole_repository?.commit_count)} commits`,
      helper: `${formatNumber(workload.whole_repository?.files_touched)} files touched`,
    },
    {
      label: "actual public window",
      value: `${formatNumber(workload.public_window?.calendar_days)} days`,
      helper: `${formatNumber(workload.public_window?.active_commit_days)} active commit days`,
    },
    {
      label: "AI-assisted baseline",
      value: formatRange(model.estimated_developer_days, " days"),
      helper: model.baseline ?? "maturity-adjusted product process",
    },
    {
      label: "single-engineer compression",
      value: formatRange(model.single_engineer_calendar_compression, "x"),
      helper: "directional range, not a precision metric",
    },
  ];
  const featurePoints = selfIterationShowcase.feature_points?.slice(0, 4) ?? [];

  return (
    <Panel icon={BarChart3} title="Efficiency Evidence">
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,420px)]" data-testid="frontstage-efficiency-evidence">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant="success">commit-backed</Badge>
            <Badge variant="info">maturity-adjusted</Badge>
            <Badge variant="neutral">public-safe</Badge>
          </div>
          <h3 className="text-lg font-semibold leading-7 text-slate-950">{selfIterationShowcase.title}</h3>
          <p className="text-sm leading-6 text-slate-600">
            {selfIterationShowcase.frontend_card?.primary_metric_hint}
          </p>
          <p className="text-sm leading-6 text-slate-600">
            The comparison converts public commits into product requirement clusters, discounts prototype-level work, and compares that conservative baseline with the actual public Git window.
          </p>
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium leading-5 text-slate-600">
            {model.claim_boundary ?? selfIterationShowcase.evidence_boundary}
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
          {metrics.map((metric) => (
            <div className="border-l-2 border-emerald-500 bg-emerald-50 px-3 py-2" key={metric.label}>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-emerald-800">{metric.label}</div>
              <div className="mt-1 break-words text-xl font-semibold leading-7 text-slate-950">{metric.value}</div>
              <div className="mt-0.5 break-words text-xs leading-5 text-slate-600">{metric.helper}</div>
            </div>
          ))}
        </div>
        {featurePoints.length ? (
          <div className="border-t border-slate-200 pt-3 lg:col-span-2">
            <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">requirement clusters</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {featurePoints.map((point) => (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium leading-5 text-slate-700" key={point}>
                  {point}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

const showcaseMotionTones = [
  {
    card: "border-emerald-200 bg-emerald-50",
    dot: "border-emerald-300 bg-emerald-600",
    ping: "bg-emerald-400",
    line: "bg-emerald-300",
  },
  {
    card: "border-sky-200 bg-sky-50",
    dot: "border-sky-300 bg-sky-600",
    ping: "bg-sky-400",
    line: "bg-sky-300",
  },
  {
    card: "border-amber-200 bg-amber-50",
    dot: "border-amber-300 bg-amber-600",
    ping: "bg-amber-400",
    line: "bg-amber-300",
  },
  {
    card: "border-rose-200 bg-rose-50",
    dot: "border-rose-300 bg-rose-600",
    ping: "bg-rose-400",
    line: "bg-rose-300",
  },
];

function ShowcaseMotionBoard() {
  const [activeCaseId, setActiveCaseId] = useState(frontstageShowcases[0]?.id ?? "");
  if (!frontstageShowcases.length) {
    return null;
  }

  const activeCase = frontstageShowcases.find((item) => item.id === activeCaseId) ?? frontstageShowcases[0];
  if (!activeCase) {
    return null;
  }
  const activeStoryBeats = activeCase.frontend_card?.story_beats?.slice(0, 5) ?? [];
  const activeFeaturePoints = activeCase.feature_points?.slice(0, 3) ?? [];
  const activeCaseHref = showcaseCaseHref(activeCase.case_page);
  const journeySegments = [
    {
      label: "human judgment",
      value: "visible gates",
      helper: "decisions stay explicit instead of disappearing inside chat logs",
    },
    {
      label: "agent lanes",
      value: "day-night work",
      helper: "safe side paths keep moving while gated decisions wait",
    },
    {
      label: "evidence loop",
      value: `${countShowcaseStoryBeats()} story beats`,
      helper: "each case records blocker, progress, validation, and outcome signals",
    },
    {
      label: "public story",
      value: `${frontstageShowcases.length} cases`,
      helper: "the hosted surface renders public-safe showcase data, not local state",
    },
  ];

  return (
    <Panel icon={Activity} title="Async Work Loop">
      <div className="space-y-4 p-4" data-testid="frontstage-showcase-motion">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">Case-driven motion board</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Public cases become motion: human gates, agent lanes, evidence writeback, and recoverable next turns.
            </p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold leading-5 text-slate-600">
            <span className="text-slate-500">Case source</span>
            <span className="ml-2 text-slate-950">docs/showcases/showcase-catalog.json</span>
          </div>
        </div>
        <div
          className="frontstage-showcase-motion-rail relative overflow-hidden rounded-md border border-slate-800 bg-slate-950 p-3 text-white shadow-sm"
          data-testid="frontstage-showcase-journey-rail"
        >
          <span
            aria-hidden="true"
            className="frontstage-showcase-motion-beam"
            data-testid="frontstage-showcase-motion-beam"
          />
          <div className="relative z-10 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-300">
                Asynchronous agent rhythm
              </div>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-100">
                Agent teams work across turns and off-hours; human judgment stays in the control plane.
              </p>
            </div>
            <Badge variant="neutral">case-first</Badge>
          </div>
          <div className="relative z-10 mt-4 grid gap-2 lg:grid-cols-4">
            {journeySegments.map((segment, index) => (
              <div className="relative rounded-md border border-white/10 bg-white/5 px-3 py-3" key={segment.label}>
                {index < journeySegments.length - 1 ? (
                  <span className="absolute left-[calc(100%-6px)] top-6 hidden h-px w-5 bg-white/30 lg:block" />
                ) : null}
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5 shrink-0">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-300 opacity-30" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cyan-300" />
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-300">
                    {segment.label}
                  </span>
                </div>
                <div className="mt-2 text-sm font-semibold leading-6 text-white">{segment.value}</div>
                <p className="mt-1 text-xs leading-5 text-slate-300">{segment.helper}</p>
              </div>
            ))}
          </div>
        </div>
        <div
          className="grid gap-4 rounded-md border border-slate-200 bg-white p-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,360px)]"
          data-testid="frontstage-showcase-spotlight"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">{activeCase.status ?? "case"}</Badge>
              {activeCase.domain ? <Badge variant="neutral">{activeCase.domain}</Badge> : null}
              <Badge variant="success">public-safe</Badge>
            </div>
            <h3 className="mt-3 text-lg font-semibold leading-7 text-slate-950">{activeCase.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">{activeCase.headline}</p>
            {activeCase.evidence_boundary ? (
              <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium leading-5 text-slate-600">
                <span className="font-semibold text-slate-950">Evidence boundary: </span>
                {activeCase.evidence_boundary}
              </div>
            ) : null}
            {activeCaseHref ? (
              <a
                className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-950 px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-500"
                data-testid="frontstage-showcase-spotlight-case-page"
                href={activeCaseHref}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Open selected case page
              </a>
            ) : null}
          </div>
          <div className="grid gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">story beats</div>
              <ol className="mt-2 space-y-2 text-xs font-medium leading-5 text-slate-700">
                {activeStoryBeats.map((beat, index) => (
                  <li className="flex gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5" key={beat}>
                    <span className="font-mono text-slate-400">{String(index + 1).padStart(2, "0")}</span>
                    <span>{beat}</span>
                  </li>
                ))}
              </ol>
            </div>
            {activeFeaturePoints.length ? (
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">requirement signals</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {activeFeaturePoints.map((point) => (
                    <Badge key={point} variant="neutral">{point}</Badge>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className="grid gap-3 xl:grid-cols-4">
          {frontstageShowcases.map((item, index) => {
            const tone = showcaseMotionTones[index % showcaseMotionTones.length];
            const beats = item.frontend_card?.story_beats?.slice(0, 4) ?? [];
            return (
              <button
                aria-pressed={activeCase.id === item.id}
                className={cn(
                  "rounded-md border p-3 text-left shadow-sm transition duration-300 hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-slate-500",
                  tone.card,
                  activeCase.id === item.id ? "ring-2 ring-slate-900" : "",
                )}
                data-testid="frontstage-showcase-motion-card"
                key={item.id}
                onClick={() => setActiveCaseId(item.id)}
                type="button"
              >
                <div className="flex items-start gap-3">
                  <div className={cn("relative mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-semibold text-white", tone.dot)}>
                    <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-20", tone.ping)} />
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">
                      {item.domain ?? "showcase"}
                    </div>
                    <h4 className="mt-1 text-sm font-semibold leading-6 text-slate-950">{item.title}</h4>
                  </div>
                </div>
                {item.frontend_card?.visual_metaphor ? (
                  <p className="mt-3 text-xs font-medium leading-5 text-slate-600">{item.frontend_card.visual_metaphor}</p>
                ) : null}
                {beats.length ? (
                  <ol className="relative mt-3 space-y-2 pl-4 text-xs font-medium leading-5 text-slate-700">
                    <span className={cn("absolute bottom-2 left-[5px] top-2 w-px", tone.line)} />
                    {beats.map((beat) => (
                      <li className="relative pl-3" key={beat}>
                        <span className={cn("absolute left-[-2px] top-2 h-2 w-2 rounded-full", tone.dot)} />
                        {beat}
                      </li>
                    ))}
                  </ol>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </Panel>
  );
}

function ShowcaseCasePackPanel() {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("all");
  const normalizedQuery = query.trim().toLowerCase();
  const domains = uniqueShowcaseDomains();
  const filteredCases = frontstageShowcases.filter((item) => {
    const matchesDomain = domain === "all" || item.domain === domain;
    const matchesQuery = !normalizedQuery || showcaseSearchText(item).includes(normalizedQuery);
    return matchesDomain && matchesQuery;
  });

  if (!frontstageShowcases.length) {
    return null;
  }

  return (
    <Panel icon={ListChecks} title="Showcase Cases">
      <div className="space-y-3 p-4" data-testid="frontstage-showcase-cases">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">Public-safe case pack</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Rendered from the showcase catalog so the hosted frontstage can tell the product story without scraping Markdown or exposing private sessions.
            </p>
          </div>
          <Badge variant="neutral">{frontstageShowcases.length} cases</Badge>
        </div>
        <div
          className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 lg:grid-cols-[minmax(220px,1fr)_auto]"
          data-testid="frontstage-showcase-discovery"
        >
          <label className="block">
            <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">Search public showcases</span>
            <span className="relative mt-1 block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                aria-label="Search public showcases"
                className="h-9 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400"
                data-testid="frontstage-showcase-search"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search cases, patterns, evidence..."
                value={query}
              />
            </span>
          </label>
          <div className="flex flex-wrap gap-2" data-testid="frontstage-showcase-domain-filter">
            {["all", ...domains].map((value) => (
              <Button
                aria-pressed={domain === value}
                key={value}
                onClick={() => setDomain(value)}
                size="sm"
                variant={domain === value ? "primary" : "secondary"}
              >
                {value === "all" ? "All" : value}
              </Button>
            ))}
          </div>
          <div className="text-xs font-medium leading-5 text-slate-500 lg:col-span-2" data-testid="frontstage-showcase-result-count">
            Showing {filteredCases.length} of {frontstageShowcases.length} public-safe cases from the catalog.
          </div>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {filteredCases.map((item) => {
            const badges = item.frontend_card?.badges?.slice(0, 4) ?? item.pattern_tags?.slice(0, 4) ?? [];
            const caseHref = showcaseCaseHref(item.case_page);
            return (
              <article className="rounded-md border border-slate-200 bg-slate-50 p-3" key={item.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">{item.status ?? "case"}</Badge>
                  {item.domain ? <Badge variant="neutral">{item.domain}</Badge> : null}
                </div>
                <h4 className="mt-3 text-sm font-semibold leading-6 text-slate-950">{item.title}</h4>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.headline}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {badges.map((badge) => (
                    <Badge key={badge} variant="neutral">{badge}</Badge>
                  ))}
                </div>
                {item.frontend_card?.primary_metric_hint ? (
                  <div className="mt-3 border-l-2 border-slate-300 pl-3 text-xs font-medium leading-5 text-slate-600">
                    {item.frontend_card.primary_metric_hint}
                  </div>
                ) : null}
                {caseHref ? (
                  <a
                    className="mt-3 inline-flex text-xs font-semibold text-slate-950 underline underline-offset-4"
                    href={caseHref}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Open case page
                  </a>
                ) : null}
              </article>
            );
          })}
          {!filteredCases.length ? (
            <div className="rounded-md border border-dashed border-slate-300 bg-white px-3 py-6 text-sm font-medium leading-6 text-slate-500 lg:col-span-2">
              No public showcase matched the current filters.
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}

const showcaseStateFlow = [
  {
    icon: Users,
    label: "Gate",
    value: "judgment visible",
  },
  {
    icon: Bot,
    label: "Claim",
    value: "agent lane owned",
  },
  {
    icon: GitBranch,
    label: "Side path",
    value: "safe work moves",
  },
  {
    icon: ShieldCheck,
    label: "Evidence",
    value: "proof written back",
  },
  {
    icon: Activity,
    label: "Next run",
    value: "state resumes",
  },
];

const developerOnboardingSteps = [
  {
    icon: Activity,
    label: "Start",
    title: "Open the project and send one LoopX bootstrap message in Codex CLI.",
    body: "The first response should name the goal, visible gate, current todo, and next safe action before work starts.",
  },
  {
    icon: ShieldCheck,
    label: "Guard",
    title: "Run quota/status before edits, then fail closed on missing identity or wrong worktree.",
    body: "Side agents move to an independent worktree; primary control stays protected from accidental edits.",
  },
  {
    icon: ListChecks,
    label: "Claim",
    title: "Choose from runnable candidates, claim the todo, and keep user decisions explicit.",
    body: "The agent chooses the actual work item; the control plane projects candidate lanes and human todo payloads.",
  },
  {
    icon: GitBranch,
    label: "Prove",
    title: "Validate, write back progress, and spend quota only after a durable state transition.",
    body: "Developer mode is read-only in the browser; LoopX CLI and append-only history remain the source of truth.",
  },
];

function ShowcaseStateFlowHero() {
  return (
    <div
      className="mt-5 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 p-4 text-white shadow-sm"
      data-testid="frontstage-state-flow-hero"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
            State flow control plane
          </div>
          <p className="mt-2 max-w-2xl text-xl font-semibold leading-8 text-white">
            Work keeps moving. Judgment stays in charge.
          </p>
        </div>
        <Badge variant="neutral">showcase-first</Badge>
      </div>
      <div className="relative mt-4">
        <div className="absolute left-4 right-4 top-6 hidden h-px bg-cyan-300/30 lg:block" />
        <div className="grid gap-2 lg:grid-cols-5">
          {showcaseStateFlow.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                className="relative overflow-hidden rounded-md border border-white/10 bg-white/[0.06] px-3 py-3"
                key={item.label}
              >
                <span className="absolute inset-x-0 top-0 h-px bg-cyan-300/50" />
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-normal text-slate-300">
                  <span className="relative flex h-7 w-7 items-center justify-center rounded-md border border-cyan-300/30 bg-cyan-300/10 text-cyan-100">
                    {index === 0 ? (
                      <span className="absolute inline-flex h-5 w-5 animate-ping rounded-md bg-cyan-300/20" />
                    ) : null}
                    <Icon className="relative h-3.5 w-3.5" />
                  </span>
                  {item.label}
                </div>
                <div className="mt-2 text-sm font-semibold leading-6 text-white">{item.value}</div>
              </div>
            );
          })}
        </div>
        <div
          aria-hidden="true"
          className="frontstage-state-flow-track mt-3"
          data-testid="frontstage-state-flow-track"
        >
          <span className="frontstage-state-flow-beam" data-testid="frontstage-state-flow-beam" />
        </div>
      </div>
    </div>
  );
}

function PublicShowcaseBoundaryPanel() {
  return (
    <Panel icon={ShieldCheck} title="Public Boundary">
      <div className="grid gap-3 p-4 md:grid-cols-3" data-testid="frontstage-public-showcase-contract">
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-emerald-800">primary source</div>
          <div className="mt-2 text-sm font-semibold leading-6 text-slate-950">docs/showcases/showcase-catalog.json</div>
          <p className="mt-1 text-xs leading-5 text-slate-600">Renderable public story data, evidence boundaries, and case-page links.</p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">live feeds</div>
          <div className="mt-2 text-sm font-semibold leading-6 text-slate-950">Ops live only</div>
          <p className="mt-1 text-xs leading-5 text-slate-600">Local status URLs stay behind explicit Ops live URLs and are not the public showcase source.</p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">write authority</div>
          <div className="mt-2 text-sm font-semibold leading-6 text-slate-950">None in browser</div>
          <p className="mt-1 text-xs leading-5 text-slate-600">The frontstage explains cases; LoopX CLI and append-only history remain the control plane.</p>
        </div>
      </div>
    </Panel>
  );
}

function DeveloperOnboardingPanel() {
  return (
    <Panel icon={Bot} title="Developer Onboarding">
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_320px]" data-testid="frontstage-developer-onboarding">
        <div className="grid gap-3">
          {developerOnboardingSteps.map((step, index) => {
            const Icon = step.icon;
            return (
              <article
                className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 sm:grid-cols-[44px_minmax(0,1fr)]"
                key={step.label}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 shadow-sm">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{index + 1}</Badge>
                    <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">{step.label}</span>
                  </div>
                  <h3 className="mt-2 text-sm font-semibold leading-6 text-slate-950">{step.title}</h3>
                  <p className="mt-1 text-xs font-medium leading-5 text-slate-600">{step.body}</p>
                </div>
              </article>
            );
          })}
        </div>
        <div className="rounded-md border border-slate-900 bg-slate-950 p-4 text-white shadow-sm">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">Quick checks</div>
          <div className="mt-3 space-y-3">
            {[
              ["identity", "heartbeat uses --agent-id and scoped automation identity"],
              ["health", "quota/status agree on user todos, runnable candidates, and gate state"],
              ["workspace", "workspace_guard blocks side-agent edits in the primary checkout"],
              ["handoff", "TUI steering stays visible while LoopX owns quota/status/writeback"],
            ].map(([label, value]) => (
              <div className="rounded-md border border-white/10 bg-white/[0.06] px-3 py-2" key={label}>
                <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-300">{label}</div>
                <div className="mt-1 text-xs font-semibold leading-5 text-white">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function ShowcaseKineticCaseStrip() {
  if (!frontstageShowcases.length) {
    return null;
  }

  const stripCases = [...frontstageShowcases, ...frontstageShowcases];
  const domains = uniqueShowcaseDomains();

  return (
    <div
      className="mt-5 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
      data-testid="frontstage-showcase-kinetic-strip"
    >
      <div className="grid gap-3 border-b border-slate-200 bg-slate-950 px-4 py-3 text-white md:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
            Multi-agent work rhythm
          </div>
          <p className="mt-1 text-sm font-semibold leading-6 text-white">
            Agent lanes run across turns; the human control plane decides what ships.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="neutral">{frontstageShowcases.length} public cases</Badge>
          <Badge variant="neutral">{domains.length} domains</Badge>
        </div>
      </div>
      <div className="frontstage-showcase-kinetic-viewport" data-testid="frontstage-showcase-kinetic-viewport">
        <div className="frontstage-showcase-kinetic-track" data-testid="frontstage-showcase-kinetic-track">
          {stripCases.map((item, index) => (
            <a
              className="frontstage-showcase-kinetic-card"
              data-testid="frontstage-showcase-kinetic-card"
              href={showcaseCaseHref(item.case_page) ?? "#"}
              key={`${item.id}-${index}`}
              rel="noreferrer"
              target="_blank"
            >
              <span className="frontstage-showcase-kinetic-dot" aria-hidden="true" />
              <span className="min-w-0">
                <span className="block truncate text-xs font-semibold text-slate-950">{item.title}</span>
                <span className="mt-0.5 block truncate text-[11px] font-medium text-slate-500">
                  {item.domain ?? "showcase"} / {item.status ?? "case"}
                </span>
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}

function FrontstageRoute({
  goalOptions,
  hasIgnoredStatusUrl,
  isLoading,
  loadError,
  mode,
  onGoalChange,
  onLoadStatusUrl,
  onResetDemo,
  onTodoLaneChange,
  onTodoQueryChange,
  projection,
  freshnessIssue,
  localApiCapabilities,
  queryStateLabel,
  selectedGoalId,
  source,
  statusUrl,
  setStatusUrl,
  todoLane,
  todoQuery,
}: {
  goalOptions: ProjectionOption[];
  hasIgnoredStatusUrl: boolean;
  isLoading: boolean;
  loadError: string | null;
  mode: FrontstageMode;
  onGoalChange: (goalId: string) => void;
  onLoadStatusUrl: () => void;
  onResetDemo: () => void;
  onTodoLaneChange: (value: TodoLaneFilter) => void;
  onTodoQueryChange: (value: string) => void;
  projection: GoalChannelProjection;
  freshnessIssue: StatusContractFreshnessIssue | null;
  localApiCapabilities: LocalDashboardApiCapabilities | null;
  queryStateLabel: string;
  selectedGoalId: string;
  source: FrontstageSource;
  statusUrl: string;
  setStatusUrl: (value: string) => void;
  todoLane: TodoLaneFilter;
  todoQuery: string;
}) {
  const quotaUsed = `${stringifyScalar(projection.quota.spent_slots)} / ${stringifyScalar(projection.quota.allowed_slots ?? "?")}`;
  const openUserTodos = countOpenTodos(projection.user_todos);
  const openAgentTodos = countOpenTodos(projection.agent_todos);
  const claimedAgentTodos = countClaimedTodos(projection.agent_todos);
  const claimOwners = uniqueClaimOwners(projection);
  const claimOwnerPreview = claimOwners.slice(0, 2).join(", ");
  const isOpsMode = mode === "ops";
  const isDeveloperMode = mode === "developer";
  const isShowcaseMode = mode === "showcase";
  const publicModeLabel = isDeveloperMode ? "developer mode" : "showcase mode";
  const publicSourceLabel = isDeveloperMode ? "developer guide" : "docs/showcases";
  const storyBeatCount = countShowcaseStoryBeats();
  const heroTitle = isOpsMode
    ? projection.display_name
    : isDeveloperMode
      ? "Developer Onboarding Frontstage"
      : "LoopX Showcase Frontstage";
  const heroSubtitle = isOpsMode
    ? "Always-on agent operations, with human judgment kept in the control plane."
    : isDeveloperMode
      ? "Start the loop from one TUI message, then keep every gate visible."
    : "Async agent teams, governed by human judgment.";
  const heroBody = isOpsMode
    ? projection.next_action
    : isDeveloperMode
      ? "A contributor-facing path for install, status health, todo claims, workspace repairs, local server checks, and safe writeback."
    : "Public cases show the operating model: gates stay explicit, safe lanes keep moving, and evidence makes every handoff recoverable.";
  const heroStats = isOpsMode
    ? [
        { label: "open user todos", value: String(openUserTodos) },
        { label: "open agent todos", value: String(openAgentTodos) },
      ]
    : isDeveloperMode
      ? [
          { label: "handoff steps", value: String(developerOnboardingSteps.length) },
          { label: "browser writes", value: "0" },
        ]
    : [
        { label: "public cases", value: String(frontstageShowcases.length) },
        { label: "story beats", value: String(storyBeatCount) },
      ];
  const operationSignals: Array<{ label: string; value: string; tone: BadgeTone }> = isOpsMode
    ? [
        {
          label: "human gate",
          value: projection.decision_frame.user_action_required ? "explicit" : "clear",
          tone: projection.decision_frame.user_action_required ? "warning" : "success",
        },
        {
          label: "agent work",
          value: projection.decision_frame.agent_action_required ? "running" : "idle",
          tone: projection.decision_frame.agent_action_required ? "info" : "neutral",
        },
        {
          label: "claimed lanes",
          value: `${claimedAgentTodos} / ${projection.agent_todos.length}`,
          tone: claimedAgentTodos ? "info" : "neutral",
        },
        {
          label: "evidence loop",
          value: `${projection.recent_events.length} events`,
          tone: projection.recent_events.length ? "success" : "neutral",
        },
      ]
    : isDeveloperMode
      ? [
          { label: "start path", value: "one message", tone: "info" },
          { label: "workspace guard", value: "fail closed", tone: "success" },
          { label: "status health", value: "projected", tone: "success" },
          { label: "live feeds", value: "ops only", tone: "warning" },
        ]
    : [
        { label: "human judgment", value: "governed", tone: "success" },
        { label: "agent teams", value: "always-on", tone: "info" },
        { label: "public cases", value: String(frontstageShowcases.length), tone: "neutral" },
        { label: "live status", value: "ops only", tone: "warning" },
      ] satisfies Array<{ label: string; value: string; tone: BadgeTone }>;
  const roleSignals = [
    {
      label: "owner",
      value: projection.decision_frame.user_action_required ? "decision visible" : "no gate",
      helper: `${openUserTodos} open user todo${openUserTodos === 1 ? "" : "s"}`,
      tone: projection.decision_frame.user_action_required ? "warning" : "success",
    },
    {
      label: "agent lane",
      value: projection.decision_frame.agent_action_required ? "active" : "idle",
      helper: `${openAgentTodos} open agent todo${openAgentTodos === 1 ? "" : "s"}`,
      tone: projection.decision_frame.agent_action_required ? "info" : "neutral",
    },
    {
      label: "claim owners",
      value: claimOwners.length ? `${claimOwners.length} visible` : "none",
      helper: claimOwnerPreview || "no active claim owner",
      tone: claimOwners.length ? "info" : "neutral",
    },
  ] satisfies Array<{ label: string; value: string; helper: string; tone: BadgeTone }>;
  const normalizedTodoQuery = todoQuery.trim().toLowerCase();
  const filteredUserTodos = todoLane === "agent"
    ? []
    : filterTodosByQuery(projection.user_todos, normalizedTodoQuery);
  const filteredAgentTodos = todoLane === "user"
    ? []
    : filterTodosByQuery(projection.agent_todos, normalizedTodoQuery);
  const visibleTodoCount = filteredUserTodos.length + filteredAgentTodos.length;
  const totalTodoCount = projection.user_todos.length + projection.agent_todos.length;

  return (
    <main
      className={cn(
        "min-h-screen bg-[#f7f7f4] px-4 py-4 text-slate-950 sm:px-5",
        isOpsMode ? "frontstage-ops-workspace" : "frontstage-showcase-workspace",
      )}
      data-frontstage-surface={isOpsMode ? "ops-control-plane" : "showcase-homepage"}
      data-mode={projection.mode}
      data-schema={projection.schema_version}
      data-testid="goal-channel-frontstage-route"
    >
      <div
        className="frontstage-workspace-shell mx-auto grid max-w-[1500px] gap-4 xl:grid-cols-[260px_minmax(0,1fr)_320px]"
        data-testid={isOpsMode ? "frontstage-ops-workspace-shell" : "frontstage-showcase-workspace-shell"}
      >
        <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4 xl:self-start">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-950 text-white">
              <GitBranch className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">LoopX</div>
              <div className="text-xs text-slate-500">Frontstage channel</div>
            </div>
          </div>
          <div className="mt-4 grid gap-2">
            <a className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium" href="/">
              <LayoutDashboard className="h-4 w-4" />
              Control home
            </a>
            <a className="flex items-center gap-2 rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white" href="/frontstage">
              <Activity className="h-4 w-4" />
              Channel board
            </a>
            <a className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm font-medium" href="/frontstage/developer">
              <ExternalLink className="h-4 w-4" />
              Developer cockpit
            </a>
          </div>
          <div className="mt-5 space-y-2 text-xs leading-5 text-slate-500">
            <p>Projection is read-only. The append-only LoopX ledger remains the source of truth.</p>
            <p>Inspired by modern agent boards, but scoped to gates, todos, claims, quota, and evidence.</p>
          </div>
          <div className="mt-5 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3" data-testid="frontstage-live-source-panel">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={isOpsMode ? "warning" : "success"}>
                {isOpsMode ? "ops live" : publicModeLabel}
              </Badge>
              <Badge variant={isOpsMode && source.kind === "url" ? "info" : "neutral"}>
                {isOpsMode && source.kind === "url" ? "live status feed" : "bundled fixture"}
              </Badge>
              <Badge variant={isOpsMode && source.kind === "url" ? "success" : "neutral"}>
                {isOpsMode ? queryStateLabel : "static"}
              </Badge>
              <span className="break-words text-xs font-medium text-slate-500">
                {isOpsMode ? source.label : publicSourceLabel}
              </span>
            </div>
            {isOpsMode ? (
              <>
                <input
                  aria-label="Status URL"
                  className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400"
                  data-testid="frontstage-status-url-input"
                  onChange={(event) => setStatusUrl(event.target.value)}
                  placeholder="/status.local.json or http://127.0.0.1:8766/status.json"
                  value={statusUrl}
                />
                <div className="text-[11px] font-medium leading-5 text-slate-500">
                  Ops statusUrl accepts only relative or loopback sources.
                </div>
                <div className="flex gap-2">
                  <Button
                    className="flex-1"
                    data-testid="frontstage-load-status-url"
                    disabled={isLoading}
                    onClick={onLoadStatusUrl}
                    size="sm"
                    variant="primary"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Load
                  </Button>
                  <Button data-testid="frontstage-reset-demo" disabled={isLoading} onClick={onResetDemo} size="sm">
                    Demo
                  </Button>
                </div>
                {goalOptions.length ? (
                  <Select
                    aria-label="Goal channel"
                    className="w-full text-xs"
                    data-testid="frontstage-goal-select"
                    onChange={(event) => onGoalChange(event.target.value)}
                    value={selectedGoalId}
                  >
                    {goalOptions.map((option) => (
                      <option key={option.goalId} value={option.goalId}>
                        {option.projection.display_name}
                      </option>
                    ))}
                  </Select>
                ) : null}
              </>
            ) : (
              <div
                className="space-y-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-950"
                data-testid="frontstage-public-boundary-note"
              >
                <p>
                  {isDeveloperMode
                    ? "Developer mode ignores statusUrl and renders the public onboarding path only. Use an explicit ops URL for local control-plane inspection."
                    : "Showcase mode ignores statusUrl and renders docs/showcases only. Use an explicit ops URL for local control-plane inspection."}
                </p>
                {hasIgnoredStatusUrl ? <Badge variant="warning">statusUrl ignored</Badge> : null}
                <div className="text-[11px] font-semibold text-emerald-800" data-testid="frontstage-ops-entry-hint">
                  Use mode=ops with statusUrl.
                </div>
              </div>
            )}
            {loadError ? (
              <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs leading-5 text-amber-950" data-testid="frontstage-load-error">
                <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{loadError}</span>
              </div>
            ) : null}
            {freshnessIssue ? (
              <div
                className="rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs leading-5 text-amber-950"
                data-testid="frontstage-stale-daemon-repair"
              >
                <div className="flex flex-wrap items-center gap-2 font-semibold">
                  <CircleAlert className="h-3.5 w-3.5" />
                  status service contract stale
                  <Badge variant="warning">schema v{freshnessIssue.schemaVersion}</Badge>
                </div>
                <p className="mt-1">
                  Restart the local status daemon with <span className="font-mono">{freshnessIssue.reloadHint}</span>, then reload this ops feed.
                </p>
              </div>
            ) : null}
            {isOpsMode && localApiCapabilities ? (
              <div
                className="grid gap-2 rounded-md border border-slate-200 bg-white px-2 py-2 text-xs leading-5 text-slate-600"
                data-testid="frontstage-local-api-capabilities"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">TanStack Query</Badge>
                  <Badge variant={localApiCapabilities.readOnlyDefault ? "success" : "warning"}>
                    {localApiCapabilities.readOnlyDefault ? "read-only default" : "write opt-in active"}
                  </Badge>
                  <Badge variant={localApiCapabilities.loopbackOnly ? "success" : "neutral"}>
                    {localApiCapabilities.loopbackOnly ? "loopback source" : "relative source"}
                  </Badge>
                </div>
                <div className="break-words">
                  <span className="font-semibold text-slate-950">local_dashboard_api:</span>{" "}
                  {localApiCapabilities.source}
                </div>
                <div className="grid gap-1">
                  <span>
                    reward dry-run {localApiCapabilities.rewardDryRunUrl ? "advertised" : "not advertised"};
                    append {localApiCapabilities.rewardWriteEnabled ? "enabled by loopback opt-in" : "disabled"}
                  </span>
                  <span>
                    control-plane dry-run {localApiCapabilities.controlPlaneDryRunUrl ? "advertised" : "not advertised"};
                    apply {localApiCapabilities.controlPlaneWriteEnabled ? "enabled by loopback opt-in" : "disabled"}
                  </span>
                  <span>Write affordances require explicit loopback opt-in and preview-locked APIs.</span>
                </div>
              </div>
            ) : null}
          </div>
        </aside>

        <section className={cn("space-y-4", isOpsMode ? "frontstage-ops-main-pane" : "frontstage-showcase-main-pane")}>
          <div className="rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap gap-2">
                  <Badge variant={isOpsMode ? "success" : "info"}>
                    {isOpsMode ? "goal_channel_projection_v0" : isDeveloperMode ? "developer frontstage" : "showcase catalog"}
                  </Badge>
                  <Badge variant="neutral">{isOpsMode ? projection.mode : "public-safe"}</Badge>
                  <Badge variant="info">{isOpsMode ? projection.waiting_on : publicSourceLabel}</Badge>
                  <Badge variant={isOpsMode ? "warning" : "success"}>{isOpsMode ? "ops live" : publicModeLabel}</Badge>
                  <Badge variant={isOpsMode && source.kind === "url" ? "success" : "neutral"}>
                    {isOpsMode && source.kind === "url" ? "url" : "demo"}
                  </Badge>
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-normal text-slate-950">
                  {heroTitle}
                </h1>
                <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-700">
                  {heroSubtitle}
                </p>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{heroBody}</p>
              </div>
              <div className="grid min-w-[220px] grid-cols-2 gap-2 text-center">
                {heroStats.map((stat) => (
                  <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2" key={stat.label}>
                    <div className="text-lg font-semibold">{stat.value}</div>
                    <div className="text-[11px] font-medium text-slate-500">{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
            {isShowcaseMode ? <ShowcaseStateFlowHero /> : null}
            {isShowcaseMode ? <ShowcaseKineticCaseStrip /> : null}
            <div className="mt-5 grid gap-2 border-t border-slate-200 pt-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="frontstage-operations-strip">
              {operationSignals.map((signal) => (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3" key={signal.label}>
                  <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">{signal.label}</div>
                  <div className="mt-2">
                    <Badge variant={signal.tone}>{signal.value}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {!isDeveloperMode ? <EfficiencyEvidencePanel /> : null}

          {!isDeveloperMode ? <ShowcaseMotionBoard /> : null}

          {!isDeveloperMode ? <ShowcaseCasePackPanel /> : null}

          {isDeveloperMode ? <DeveloperOnboardingPanel /> : null}

          {isOpsMode ? (
            <>
              <div className="grid gap-4 lg:grid-cols-3">
                <Panel icon={Users} title="Decision Frame">
                  <div className="grid gap-2 p-4">
                    {boolBadge(projection.decision_frame.user_action_required, "user action", "no user action")}
                    {boolBadge(projection.decision_frame.agent_action_required, "agent action", "no agent action")}
                    {boolBadge(!projection.decision_frame.quiet_noop_allowed, "no quiet noop", "quiet noop ok")}
                  </div>
                </Panel>
                <Panel icon={ShieldCheck} title="Quota Guard">
                  <div className="space-y-2 p-4 text-sm leading-6">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-slate-500">state</span>
                      <Badge variant={statusTone(stringifyScalar(projection.quota.state))}>{stringifyScalar(projection.quota.state)}</Badge>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-slate-500">slots</span>
                      <span className="font-semibold">{quotaUsed}</span>
                    </div>
                    <p className="text-xs text-slate-500">{stringifyScalar(projection.quota.spend_policy)}</p>
                  </div>
                </Panel>
                <Panel icon={Clock3} title="Source Freshness">
                  <div className="space-y-2 p-4 text-xs leading-5 text-slate-600">
                    {Object.entries(projection.source_refs).map(([key, value]) => (
                      <div className="grid gap-1 rounded-md border border-slate-100 bg-slate-50 px-2 py-1.5" key={key}>
                        <span className="font-semibold text-slate-500">{key}</span>
                        <span className="break-words font-medium text-slate-700">{stringifyScalar(value)}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div
                  className="frontstage-ops-command-strip rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:col-span-2"
                  data-testid="frontstage-ops-command-strip"
                >
                  <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_auto]" data-testid="frontstage-todo-discovery">
                    <label className="block">
                      <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">Search todo projection</span>
                      <span className="relative mt-1 block">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                        <input
                          aria-label="Search projected todos"
                          className="h-9 w-full rounded-md border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400"
                          data-testid="frontstage-todo-search"
                          onChange={(event) => onTodoQueryChange(event.target.value)}
                          placeholder="Search title, claim, action kind..."
                          value={todoQuery}
                        />
                      </span>
                    </label>
                    <label className="block">
                      <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">Lane</span>
                      <Select
                        aria-label="Todo lane filter"
                        className="mt-1 w-full text-sm"
                        data-testid="frontstage-todo-lane-filter"
                        onChange={(event) => onTodoLaneChange(event.target.value as TodoLaneFilter)}
                        value={todoLane}
                      >
                        <option value="all">All lanes</option>
                        <option value="user">User todos</option>
                        <option value="agent">Agent todos</option>
                      </Select>
                    </label>
                    <div
                      className="flex min-h-9 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-xs font-semibold leading-5 text-slate-600 lg:self-end"
                      data-testid="frontstage-todo-result-count"
                    >
                      Showing {visibleTodoCount} of {totalTodoCount} projected todos
                    </div>
                  </div>
                </div>
                <Panel icon={Users} title="User Todo Lane">
                  <div data-testid="frontstage-user-todos">
                    {filteredUserTodos.map((todo) => (
                      <TodoRow key={todo.todo_id ?? todo.title} todo={todo} />
                    ))}
                    {!filteredUserTodos.length ? (
                      <TodoLaneEmpty>No user todos match the current filters.</TodoLaneEmpty>
                    ) : null}
                  </div>
                </Panel>
                <Panel icon={Bot} title="Agent Todo Lane">
                  <div data-testid="frontstage-agent-todos">
                    {filteredAgentTodos.map((todo) => (
                      <TodoRow key={todo.todo_id ?? todo.title} todo={todo} />
                    ))}
                    {!filteredAgentTodos.length ? (
                      <TodoLaneEmpty>No agent todos match the current filters.</TodoLaneEmpty>
                    ) : null}
                  </div>
                </Panel>
              </div>

              <Panel icon={Activity} title="Run Timeline">
                <div className="divide-y divide-slate-200" data-testid="frontstage-timeline">
                  {projection.recent_events.map((event, index) => (
                    <div className="grid gap-3 px-4 py-3 md:grid-cols-[190px_180px_minmax(0,1fr)]" key={`${event.generated_at ?? "event"}-${index}`}>
                      <div className="font-mono text-xs text-slate-500">{event.generated_at ?? "n/a"}</div>
                      <Badge variant="neutral">{event.classification ?? "event"}</Badge>
                      <div className="text-sm leading-6 text-slate-700">{event.summary ?? "compact event"}</div>
                    </div>
                  ))}
                </div>
              </Panel>
            </>
          ) : (
            <PublicShowcaseBoundaryPanel />
          )}
        </section>

        <aside className="space-y-4">
          {isOpsMode ? (
            <Panel icon={Users} title="Role Map">
              <div className="space-y-3 p-4" data-testid="frontstage-role-map">
                {roleSignals.map((signal) => (
                  <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2" key={signal.label}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold uppercase tracking-normal text-slate-500">{signal.label}</span>
                      <Badge variant={signal.tone}>{signal.value}</Badge>
                    </div>
                    <div className="mt-2 break-words text-xs font-medium leading-5 text-slate-600">{signal.helper}</div>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}

          {isOpsMode ? (
            <Panel icon={ListChecks} title="Active Claims">
              <div className="divide-y divide-slate-200" data-testid="frontstage-active-claims">
                {projection.active_leases.map((lease, index) => (
                  <div className="px-4 py-3" key={`${lease.todo_id ?? "claim"}-${index}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="info">{lease.owner_agent ?? "unknown"}</Badge>
                      <Badge variant="neutral">{lease.status ?? "claim"}</Badge>
                    </div>
                    <div className="mt-2 break-all text-xs font-medium text-slate-500">{lease.todo_id}</div>
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}

          {isOpsMode ? (
            <Panel icon={CircleAlert} title="Open Gates">
              <div className="divide-y divide-slate-200" data-testid="frontstage-open-gates">
                {projection.open_gates.map((gate) => (
                  <div className="px-4 py-3" key={gate.gate_id}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={statusTone(gate.status)}>{gate.status}</Badge>
                      <Badge variant="neutral">{gate.kind}</Badge>
                    </div>
                    <div className="mt-2 break-all text-xs font-semibold text-slate-600">{gate.gate_id}</div>
                    {gate.blocks?.length ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {gate.blocks.map((blocker) => (
                          <Badge key={blocker} variant="warning">{blocker}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
                {!projection.open_gates.length ? (
                  <div className="px-4 py-4 text-sm font-medium leading-6 text-slate-500">No open gates in this projection.</div>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {isOpsMode ? (
            <Panel icon={ExternalLink} title="Artifacts">
              <div className="divide-y divide-slate-200" data-testid="frontstage-artifacts">
                {projection.artifacts.map((artifact, index) => (
                  <div className="space-y-2 px-4 py-3" key={`${artifact.kind ?? "artifact"}-${index}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="info">{artifactDisplayValue(artifact.kind)}</Badge>
                      {artifact.label ? <Badge variant="neutral">{artifactDisplayValue(artifact.label)}</Badge> : null}
                    </div>
                    {Object.entries(artifact)
                      .filter(([key]) => !["kind", "label"].includes(key))
                      .map(([key, value]) => (
                        <div className="grid gap-1 rounded-md border border-slate-100 bg-slate-50 px-2 py-1.5" key={key}>
                          <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">{key}</span>
                          <span className="break-words text-xs font-medium leading-5 text-slate-700">
                            {artifactDisplayValue(value)}
                          </span>
                        </div>
                      ))}
                  </div>
                ))}
                {!projection.artifacts.length ? (
                  <div className="px-4 py-4 text-sm font-medium leading-6 text-slate-500">No compact artifacts projected.</div>
                ) : null}
              </div>
            </Panel>
          ) : null}

          {isOpsMode ? (
            <Panel icon={ShieldCheck} title="Truth Contract">
              <div className="space-y-3 p-4 text-sm leading-6">
                <div className="flex flex-wrap gap-2">
                  {boolBadge(projection.truth_contract.event_ledger_is_source_of_truth, "ledger truth", "ledger missing")}
                  {boolBadge(!projection.truth_contract.projection_is_writable, "read-only", "writeable")}
                </div>
                <p className="text-slate-600">{projection.truth_contract.recompute_rule}</p>
                <p className="text-xs font-semibold text-slate-500">write authority: {projection.truth_contract.write_authority}</p>
              </div>
            </Panel>
          ) : null}

          <Panel icon={ShieldCheck} title="Boundary Warnings">
            <div className="space-y-3 p-4" data-testid="frontstage-source-warnings">
              {projection.source_warnings.map((warning, index) => (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-950" key={`${warning.kind}-${index}`}>
                  <div className="font-semibold">{warning.kind}</div>
                  <p className="mt-1">{warningMessage(warning.message)}</p>
                </div>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </main>
  );
}

export function FrontstagePage() {
  const search = frontstageRoute.useSearch();
  const navigate = frontstageRoute.useNavigate();
  const [statusUrl, setStatusUrl] = useState(search.statusUrl);
  const [manualLoadError, setManualLoadError] = useState<string | null>(null);
  const mode: FrontstageMode = search.mode === "ops"
    ? "ops"
    : search.mode === "developer"
      ? "developer"
      : "showcase";
  const todoLane: TodoLaneFilter = search.todoLane === "user" || search.todoLane === "agent"
    ? search.todoLane
    : "all";
  const todoQuery = search.todoQuery ?? "";
  const liveMode = mode === "ops";
  const hasIgnoredStatusUrl = !liveMode && Boolean(search.statusUrl);
  const resolvedSearchStatusUrl = useMemo(
    () => (liveMode && search.statusUrl
      ? resolveFrontstageOpsStatusUrl(search.statusUrl, window.location.href)
      : null),
    [liveMode, search.statusUrl],
  );
  const statusQuery = useQuery({
    enabled: Boolean(liveMode && resolvedSearchStatusUrl?.source),
    queryFn: () => fetchFrontstageStatusPayload(resolvedSearchStatusUrl?.source?.url ?? ""),
    queryKey: ["frontstage-ops-status", resolvedSearchStatusUrl?.source?.url ?? ""],
  });
  const payload: StatusPayload | null = liveMode ? statusQuery.data ?? null : null;
  const source: FrontstageSource = liveMode && payload && resolvedSearchStatusUrl?.source
    ? { kind: "url", label: resolvedSearchStatusUrl.source.url }
    : { kind: "demo", label: "bundled fixture" };

  const rawGoalOptions = useMemo(
    () => (payload ? projectionOptionsFromPayload(payload) : []),
    [payload],
  );
  const goalOptions = liveMode ? rawGoalOptions : [];
  const selectedGoalId = goalOptions.some((option) => option.goalId === search.goalId)
    ? search.goalId
    : goalOptions[0]?.goalId ?? sampleGoalChannelProjection.goal_id;
  const selectedProjection = goalOptions.find((option) => option.goalId === selectedGoalId)?.projection
    ?? sampleGoalChannelProjection;
  const freshnessIssue = payload && resolvedSearchStatusUrl?.source
    ? statusContractFreshnessIssue(payload, resolvedSearchStatusUrl.source)
    : null;
  const localApiCapabilities = payload && resolvedSearchStatusUrl?.source
    ? localDashboardApiCapabilities(payload, resolvedSearchStatusUrl.source)
    : null;
  const queryError = statusQuery.error ? formatStatusError(statusQuery.error) : null;
  const projectionError = liveMode && statusQuery.isSuccess && rawGoalOptions.length === 0
    ? "status feed has no goal_channel_projection items; showing demo fixture"
    : null;
  const loadError = manualLoadError
    ?? resolvedSearchStatusUrl?.error
    ?? queryError
    ?? projectionError;
  const queryStateLabel = !liveMode
    ? "static"
    : !resolvedSearchStatusUrl?.source
      ? "query idle"
    : statusQuery.isFetching
      ? "query fetching"
      : statusQuery.isStale
        ? "query stale"
        : "query fresh";

  async function updateSearch(next: {
    goalId?: string;
    mode?: FrontstageMode;
    statusUrl?: string;
    todoLane?: TodoLaneFilter;
    todoQuery?: string;
  }) {
    await navigate({
      search: (current) => ({
        ...current,
        ...next,
      }),
    });
  }

  async function loadSelectedStatusUrl() {
    if (!liveMode) {
      setManualLoadError("statusUrl is ignored in showcase mode; switch to Ops live for local status feeds");
      return;
    }
    const resolvedStatusUrl = resolveFrontstageOpsStatusUrl(statusUrl, window.location.href);
    if (resolvedStatusUrl.error || !resolvedStatusUrl.source) {
      setManualLoadError(resolvedStatusUrl.error ?? "status URL is invalid");
      return;
    }
    setManualLoadError(null);
    setStatusUrl(resolvedStatusUrl.source.url);
    if (search.statusUrl === resolvedStatusUrl.source.url) {
      await statusQuery.refetch();
      return;
    }
    await updateSearch({
      goalId: "",
      mode: "ops",
      statusUrl: resolvedStatusUrl.source.url,
    });
  }

  function resetToDemo() {
    setStatusUrl("");
    setManualLoadError(null);
    void updateSearch({ goalId: "", mode: "showcase", statusUrl: "", todoLane: "all", todoQuery: "" });
  }

  function changeGoal(goalId: string) {
    void updateSearch({ goalId });
  }

  function changeTodoLane(value: TodoLaneFilter) {
    void updateSearch({ todoLane: value });
  }

  function changeTodoQuery(value: string) {
    void updateSearch({ todoQuery: value });
  }

  useEffect(() => {
    setStatusUrl(search.statusUrl);
  }, [search.statusUrl]);

  useEffect(() => {
    if (!goalOptions.length || search.goalId === selectedGoalId) {
      return;
    }
    void updateSearch({ goalId: selectedGoalId });
  }, [goalOptions, search.goalId, selectedGoalId]);

  return (
    <FrontstageRoute
      goalOptions={goalOptions}
      hasIgnoredStatusUrl={hasIgnoredStatusUrl}
      isLoading={statusQuery.isFetching}
      loadError={loadError}
      mode={mode}
      onGoalChange={changeGoal}
      onLoadStatusUrl={() => void loadSelectedStatusUrl()}
      onResetDemo={resetToDemo}
      onTodoLaneChange={changeTodoLane}
      onTodoQueryChange={changeTodoQuery}
      projection={selectedProjection}
      freshnessIssue={freshnessIssue}
      localApiCapabilities={localApiCapabilities}
      queryStateLabel={queryStateLabel}
      selectedGoalId={selectedGoalId}
      setStatusUrl={setStatusUrl}
      source={source}
      statusUrl={statusUrl}
      todoLane={todoLane}
      todoQuery={todoQuery}
    />
  );
}
