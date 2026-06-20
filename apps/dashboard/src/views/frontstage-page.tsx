import {
  Activity,
  Bot,
  Clock3,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  ShieldCheck,
  Users,
} from "lucide-react";

import {
  GoalChannelProjection,
  GoalChannelTodo,
  sampleGoalChannelProjection,
} from "../data/goal-channel-frontstage";
import { Badge } from "../components/ui/badge";
import { cn } from "../lib/utils";

type BadgeTone = "neutral" | "success" | "warning" | "info" | "danger";

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

function FrontstageRoute({ projection }: { projection: GoalChannelProjection }) {
  const quotaUsed = `${projection.quota.spent_slots ?? "0"} / ${projection.quota.allowed_slots ?? "?"}`;
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
        </aside>

        <section className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="success">goal_channel_projection_v0</Badge>
                  <Badge variant="neutral">{projection.mode}</Badge>
                  <Badge variant="info">{projection.waiting_on}</Badge>
                </div>
                <h1 className="mt-3 text-3xl font-semibold tracking-normal text-slate-950">
                  {projection.display_name}
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{projection.next_action}</p>
              </div>
              <div className="grid min-w-[220px] grid-cols-2 gap-2 text-center">
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-lg font-semibold">{projection.user_todos.length}</div>
                  <div className="text-[11px] font-medium text-slate-500">user todos</div>
                </div>
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <div className="text-lg font-semibold">{projection.agent_todos.length}</div>
                  <div className="text-[11px] font-medium text-slate-500">agent todos</div>
                </div>
              </div>
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
                  <Badge variant={statusTone(projection.quota.state)}>{projection.quota.state}</Badge>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">slots</span>
                  <span className="font-semibold">{quotaUsed}</span>
                </div>
                <p className="text-xs text-slate-500">{projection.quota.spend_policy}</p>
              </div>
            </Panel>
            <Panel icon={Clock3} title="Source Freshness">
              <div className="space-y-2 p-4 text-xs leading-5 text-slate-600">
                {Object.entries(projection.source_refs).map(([key, value]) => (
                  <div className="grid grid-cols-[118px_minmax(0,1fr)] gap-2" key={key}>
                    <span className="font-semibold text-slate-500">{key}</span>
                    <span className="break-words">{value ?? "n/a"}</span>
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
                  <p className="mt-1">{warning.message}</p>
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
  return <FrontstageRoute projection={sampleGoalChannelProjection} />;
}
