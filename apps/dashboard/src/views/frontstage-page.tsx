import {
  Activity,
  Bot,
  CircleAlert,
  Clock3,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { frontstageRoute } from "../router";
import {
  GoalChannelProjection,
  GoalChannelTodo,
  sampleGoalChannelProjection,
} from "../data/goal-channel-frontstage";
import { QueueItem, StatusPayload, formatStatusError, parseStatusPayload } from "../data/status";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select } from "../components/ui/select";
import { cn } from "../lib/utils";

type BadgeTone = "neutral" | "success" | "warning" | "info" | "danger";
type FrontstageSource = { kind: "demo"; label: string } | { kind: "url"; label: string };

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

function countOpenTodos(todos: GoalChannelTodo[]) {
  return todos.filter((todo) => todo.status === "open").length;
}

function countClaimedTodos(todos: GoalChannelTodo[]) {
  return todos.filter((todo) => Boolean(todo.claimed_by)).length;
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

function FrontstageRoute({
  goalOptions,
  isLoading,
  loadError,
  onGoalChange,
  onLoadStatusUrl,
  onResetDemo,
  projection,
  selectedGoalId,
  source,
  statusUrl,
  setStatusUrl,
}: {
  goalOptions: ProjectionOption[];
  isLoading: boolean;
  loadError: string | null;
  onGoalChange: (goalId: string) => void;
  onLoadStatusUrl: () => void;
  onResetDemo: () => void;
  projection: GoalChannelProjection;
  selectedGoalId: string;
  source: FrontstageSource;
  statusUrl: string;
  setStatusUrl: (value: string) => void;
}) {
  const quotaUsed = `${stringifyScalar(projection.quota.spent_slots)} / ${stringifyScalar(projection.quota.allowed_slots ?? "?")}`;
  const openUserTodos = countOpenTodos(projection.user_todos);
  const openAgentTodos = countOpenTodos(projection.agent_todos);
  const claimedAgentTodos = countClaimedTodos(projection.agent_todos);
  const operationSignals = [
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
  ] satisfies Array<{ label: string; value: string; tone: BadgeTone }>;
  return (
    <main
      className="min-h-screen bg-[#f7f7f4] px-4 py-4 text-slate-950 sm:px-5"
      data-mode={projection.mode}
      data-schema={projection.schema_version}
      data-testid="goal-channel-frontstage-route"
    >
      <div className="mx-auto grid max-w-[1500px] gap-4 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm xl:sticky xl:top-4 xl:self-start">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-950 text-white">
              <GitBranch className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">Goal Harness</div>
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
          </div>
          <div className="mt-5 space-y-2 text-xs leading-5 text-slate-500">
            <p>Projection is read-only. The append-only Goal Harness ledger remains the source of truth.</p>
            <p>Inspired by modern agent boards, but scoped to gates, todos, claims, quota, and evidence.</p>
          </div>
          <div className="mt-5 space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3" data-testid="frontstage-live-source-panel">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={source.kind === "url" ? "success" : "neutral"}>
                {source.kind === "url" ? "live status feed" : "demo fixture"}
              </Badge>
              <span className="text-xs font-medium text-slate-500">{source.label}</span>
            </div>
            <input
              aria-label="Status URL"
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 shadow-sm outline-none focus:ring-2 focus:ring-slate-400"
              data-testid="frontstage-status-url-input"
              onChange={(event) => setStatusUrl(event.target.value)}
              placeholder="/status.local.json"
              value={statusUrl}
            />
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
            {loadError ? (
              <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-xs leading-5 text-amber-950" data-testid="frontstage-load-error">
                <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{loadError}</span>
              </div>
            ) : null}
          </div>
        </aside>

        <section className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="success">goal_channel_projection_v0</Badge>
                  <Badge variant="neutral">{projection.mode}</Badge>
                  <Badge variant="info">{projection.waiting_on}</Badge>
                  <Badge variant={source.kind === "url" ? "success" : "neutral"}>{source.kind}</Badge>
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-normal text-slate-950">
                  {projection.display_name}
                </h1>
                <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-slate-700">
                  Always-on agent operations, with human judgment kept in the control plane.
                </p>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{projection.next_action}</p>
              </div>
              <div className="grid min-w-[220px] grid-cols-2 gap-2 text-center">
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-lg font-semibold">{openUserTodos}</div>
                  <div className="text-[11px] font-medium text-slate-500">open user todos</div>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-lg font-semibold">{openAgentTodos}</div>
                  <div className="text-[11px] font-medium text-slate-500">open agent todos</div>
                </div>
              </div>
            </div>
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
            <Panel icon={Users} title="User Todo Lane">
              <div data-testid="frontstage-user-todos">
                {projection.user_todos.map((todo) => (
                  <TodoRow key={todo.todo_id ?? todo.title} todo={todo} />
                ))}
              </div>
            </Panel>
            <Panel icon={Bot} title="Agent Todo Lane">
              <div data-testid="frontstage-agent-todos">
                {projection.agent_todos.map((todo) => (
                  <TodoRow key={todo.todo_id ?? todo.title} todo={todo} />
                ))}
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
        </section>

        <aside className="space-y-4">
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
  const [payload, setPayload] = useState<StatusPayload | null>(null);
  const [source, setSource] = useState<FrontstageSource>({ kind: "demo", label: "bundled fixture" });
  const [statusUrl, setStatusUrl] = useState(search.statusUrl);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const goalOptions = useMemo(
    () => (payload ? projectionOptionsFromPayload(payload) : []),
    [payload],
  );
  const selectedGoalId = goalOptions.some((option) => option.goalId === search.goalId)
    ? search.goalId
    : goalOptions[0]?.goalId ?? sampleGoalChannelProjection.goal_id;
  const selectedProjection = goalOptions.find((option) => option.goalId === selectedGoalId)?.projection
    ?? sampleGoalChannelProjection;

  async function updateSearch(next: { goalId?: string; statusUrl?: string }) {
    await navigate({
      search: (current) => ({
        ...current,
        ...next,
      }),
    });
  }

  async function loadFromUrl(url: string, updateUrl = true) {
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
      const nextOptions = projectionOptionsFromPayload(nextPayload);
      setPayload(nextPayload);
      setSource({ kind: "url", label: trimmed });
      setStatusUrl(trimmed);
      if (nextOptions.length === 0) {
        setLoadError("status feed has no goal_channel_projection items; showing demo fixture");
      }
      if (updateUrl) {
        await updateSearch({
          goalId: nextOptions[0]?.goalId ?? "",
          statusUrl: trimmed,
        });
      }
    } catch (error) {
      setLoadError(formatStatusError(error));
    } finally {
      setIsLoading(false);
    }
  }

  function resetToDemo() {
    setPayload(null);
    setSource({ kind: "demo", label: "bundled fixture" });
    setStatusUrl("");
    setLoadError(null);
    void updateSearch({ goalId: "", statusUrl: "" });
  }

  function changeGoal(goalId: string) {
    void updateSearch({ goalId });
  }

  useEffect(() => {
    if (search.statusUrl) {
      void loadFromUrl(search.statusUrl, false);
    }
  }, []);

  useEffect(() => {
    if (!goalOptions.length || search.goalId === selectedGoalId) {
      return;
    }
    void updateSearch({ goalId: selectedGoalId });
  }, [goalOptions, search.goalId, selectedGoalId]);

  return (
    <FrontstageRoute
      goalOptions={goalOptions}
      isLoading={isLoading}
      loadError={loadError}
      onGoalChange={changeGoal}
      onLoadStatusUrl={() => void loadFromUrl(statusUrl)}
      onResetDemo={resetToDemo}
      projection={selectedProjection}
      selectedGoalId={selectedGoalId}
      setStatusUrl={setStatusUrl}
      source={source}
      statusUrl={statusUrl}
    />
  );
}
