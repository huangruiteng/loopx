import type {
  AgentManagementProjection,
  GoalChannelNotificationRow,
  QueueItem,
  StatusPayload,
  TodoIndexItem,
} from "./status";

type UsageGoal = NonNullable<StatusPayload["usage_summary"]>["goals"][number];

/**
 * Merge a scoped status snapshot into the current view.
 *
 * The active-first dashboard loads `goal_activation=active` first, then fills in
 * the stopped archive from a second `goal_activation=stopped` request. The two
 * snapshots are taken at different points in time, so a plain array
 * concatenation would silently drop the archive's goal-scoped derived
 * projections (attention queue, todo index, usage summary, agent management,
 * goal channel notifications) and would also duplicate or omit goals when a
 * goal is stopped/resumed between the two requests.
 *
 * This module defines the read-model merge contract as a pure function:
 *
 * - run_history.goals are deduplicated by goal id, with the active snapshot
 *   authoritative first and the stopped snapshot filling in the remainder.
 * - Every goal-scoped derived projection is merged with the same authority
 *   order instead of being discarded.
 * - When both snapshots carry `registry_revision` and they differ (the
 *   registry's goal activation partition changed between requests), the
 *   merged payload stays `complete: false` so the consumer can resync instead
 *   of trusting a concatenated view that may duplicate or omit goals. Missing
 *   revisions preserve compatibility with earlier scoped servers.
 */

type GoalProjectionScope = "active" | "stopped";

function itemMatchesScope(
  goalId: string,
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
  scope: GoalProjectionScope,
) {
  return goalScopes.get(goalId) === scope;
}

function scopedItems<T>(
  items: readonly T[],
  scope: GoalProjectionScope,
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
  goalId: (item: T) => string,
) {
  return items.filter((item) => itemMatchesScope(goalId(item), goalScopes, scope));
}

function mergeByKey<T>(
  primary: readonly T[],
  secondary: readonly T[],
  key: (item: T) => string | null | undefined,
): T[] {
  const seen = new Set<string>();
  const merged: T[] = [];
  for (const item of [...primary, ...secondary]) {
    const k = key(item);
    if (k == null || seen.has(k)) continue;
    seen.add(k);
    merged.push(item);
  }
  return merged;
}

const USAGE_COUNTER_KEYS = [
  "runs_24h",
  "runs_7d",
  "quota_spend_slots_24h",
  "quota_spend_slots_7d",
  "automation_run_count_24h",
  "automation_run_count_7d",
  "progress_signal_run_count_24h",
  "progress_signal_run_count_7d",
] as const;

const USAGE_MEASUREMENT_KEYS = [
  "input_tokens_24h",
  "input_tokens_7d",
  "output_tokens_24h",
  "output_tokens_7d",
  "cache_tokens_24h",
  "cache_tokens_7d",
  "cost_usd_24h",
  "cost_usd_7d",
  "duration_ms_24h",
  "duration_ms_7d",
] as const;

type UsageTotals = NonNullable<StatusPayload["usage_summary"]>["totals"];
type EventLedgerSummary = NonNullable<StatusPayload["event_ledger_summary"]>;
type EventLedgerTotals = EventLedgerSummary["totals"];
type DecisionFreshnessSummary = NonNullable<StatusPayload["decision_freshness_summary"]>;

const EVENT_CLASS_KEYS = ["accounting", "decision", "evidence", "state", "work"] as const;
const emptyEventClassCounts: EventLedgerTotals["by_class_24h"] = {
  accounting: 0,
  decision: 0,
  evidence: 0,
  state: 0,
  work: 0,
};

const emptyUsageTotals: UsageTotals = {
  runs_24h: 0,
  runs_7d: 0,
  quota_spend_slots_24h: 0,
  quota_spend_slots_7d: 0,
  automation_run_count_24h: 0,
  automation_run_count_7d: 0,
  progress_signal_run_count_24h: 0,
  progress_signal_run_count_7d: 0,
};

function addUsageTotals(left: UsageTotals, right: UsageTotals): UsageTotals {
  const merged = { ...left };
  for (const key of USAGE_COUNTER_KEYS) {
    merged[key] = (Number(left[key]) || 0) + (Number(right[key]) || 0);
  }
  for (const key of USAGE_MEASUREMENT_KEYS) {
    if (left[key] === undefined && right[key] === undefined) continue;
    merged[key] = (left[key] ?? 0) + (right[key] ?? 0);
  }
  return merged;
}

function recomputeProjectShare(goals: UsageGoal[], totalRuns24h: number) {
  if (!goals.length || totalRuns24h <= 0) return goals;
  return goals.map((goal) => ({
    ...goal,
    project_share_24h: Math.round((Number(goal.runs_24h) || 0) / totalRuns24h * 1000) / 1000,
  }));
}

function addEventClassCounts(
  left: EventLedgerTotals["by_class_24h"],
  right: EventLedgerTotals["by_class_24h"],
) {
  const merged = { ...left };
  for (const key of EVENT_CLASS_KEYS) {
    merged[key] = (left[key] ?? 0) + (right[key] ?? 0);
  }
  return merged;
}

function eventTotalsForGoals(
  goals: readonly EventLedgerSummary["goals"][number][],
): EventLedgerTotals {
  const totals: EventLedgerTotals = {
    events_24h: 0,
    events_7d: 0,
    by_class_24h: { ...emptyEventClassCounts },
    by_class_7d: { ...emptyEventClassCounts },
  };
  for (const goal of goals) {
    totals.events_24h += goal.events_24h;
    totals.events_7d += goal.events_7d;
    totals.by_class_24h = addEventClassCounts(
      totals.by_class_24h,
      goal.by_class_24h,
    );
    totals.by_class_7d = addEventClassCounts(
      totals.by_class_7d,
      goal.by_class_7d,
    );
  }
  return totals;
}

function mergeEventLedgerSummary(
  active: StatusPayload["event_ledger_summary"],
  stopped: StatusPayload["event_ledger_summary"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
): EventLedgerSummary | null {
  if (!active && !stopped) return null;
  const activeGoals = scopedItems(
    active?.goals ?? [],
    "active",
    goalScopes,
    (goal) => goal.goal_id,
  );
  const stoppedGoals = scopedItems(
    stopped?.goals ?? [],
    "stopped",
    goalScopes,
    (goal) => goal.goal_id,
  );
  const goals = mergeByKey(activeGoals, stoppedGoals, (goal) => goal.goal_id);
  const activeTotals = eventTotalsForGoals(activeGoals);
  const stoppedTotals = eventTotalsForGoals(stoppedGoals);
  const totals: EventLedgerTotals = {
    events_24h: activeTotals.events_24h + stoppedTotals.events_24h,
    events_7d: activeTotals.events_7d + stoppedTotals.events_7d,
    by_class_24h: addEventClassCounts(
      activeTotals.by_class_24h,
      stoppedTotals.by_class_24h,
    ),
    by_class_7d: addEventClassCounts(
      activeTotals.by_class_7d,
      stoppedTotals.by_class_7d,
    ),
  };
  return {
    ...(active ?? stopped!),
    goals,
    sample_run_count: (active?.sample_run_count ?? 0) + (stopped?.sample_run_count ?? 0),
    totals,
  };
}

function mergeDecisionFreshnessSummary(
  active: StatusPayload["decision_freshness_summary"],
  stopped: StatusPayload["decision_freshness_summary"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
): DecisionFreshnessSummary | null {
  if (!active && !stopped) return null;
  const items = mergeByKey(
    [
      ...scopedItems(active?.items ?? [], "active", goalScopes, (item) => item.goal_id),
      ...scopedItems(stopped?.items ?? [], "stopped", goalScopes, (item) => item.goal_id),
    ],
    [],
    (item) => `${item.goal_id}:${item.decision_kind ?? ""}:${item.decision_at ?? ""}`,
  );
  const summary = {
    decision_count: (active?.summary.decision_count ?? 0)
      + (stopped?.summary.decision_count ?? 0),
    stale_count: items.filter((item) => item.stale_by_age).length,
    rebase_required_count: (active?.summary.rebase_required_count ?? 0)
      + (stopped?.summary.rebase_required_count ?? 0),
    fresh_count: (active?.summary.fresh_count ?? 0)
      + (stopped?.summary.fresh_count ?? 0),
  };
  return {
    ...(active ?? stopped!),
    items,
    sample_run_count: (active?.sample_run_count ?? 0) + (stopped?.sample_run_count ?? 0),
    summary,
  };
}

function mergeRecentRuns(
  active: StatusPayload["run_history"]["recent_runs"],
  stopped: StatusPayload["run_history"]["recent_runs"],
) {
  return mergeByKey(
    [...active, ...stopped]
      .sort((left, right) => right.generated_at.localeCompare(left.generated_at)),
    [],
    (run) => `${run.goal_id}:${run.generated_at}:${run.classification ?? ""}`,
  );
}

function mergeAttentionQueue(
  active: StatusPayload["attention_queue"],
  stopped: StatusPayload["attention_queue"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
) {
  const items = mergeByKey<QueueItem>(
    scopedItems(active.items, "active", goalScopes, (item) => item.goal_id),
    scopedItems(stopped.items, "stopped", goalScopes, (item) => item.goal_id),
    (item) => item.goal_id,
  );
  return {
    ...active,
    item_count: items.length,
    items,
    needs_controller: items.filter((item) => item.waiting_on === "controller").length,
    needs_codex: items.filter((item) => item.waiting_on === "codex").length,
    needs_user_or_controller: items.filter((item) =>
      ["user_or_controller", "controller"].includes(item.waiting_on)).length,
    watching_external_evidence: items.filter((item) =>
      item.waiting_on === "external_evidence").length,
  };
}

function todoIndexKey(item: TodoIndexItem): string {
  const todoId = item.todo_id?.trim() || "";
  if (todoId) return `${item.goal_id}:${todoId}`;
  return `${item.goal_id}:synthetic:${item.role ?? ""}:${item.index ?? ""}:${item.text ?? ""}`;
}

function usageTotalsForGoals(goals: readonly UsageGoal[]): UsageTotals {
  const totals = { ...emptyUsageTotals };
  for (const goal of goals) {
    for (const key of USAGE_COUNTER_KEYS) {
      totals[key] += Number(goal[key]) || 0;
    }
    for (const key of USAGE_MEASUREMENT_KEYS) {
      if (goal[key] === undefined) continue;
      totals[key] = (totals[key] ?? 0) + goal[key];
    }
  }
  return totals;
}

function mergeTodoIndex(
  active: StatusPayload["todo_index"],
  stopped: StatusPayload["todo_index"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
) {
  if (!active && !stopped) return null;
  const activeItems = scopedItems(
    active?.items ?? [],
    "active",
    goalScopes,
    (item) => item.goal_id,
  );
  const stoppedItems = scopedItems(
    stopped?.items ?? [],
    "stopped",
    goalScopes,
    (item) => item.goal_id,
  );
  const items = mergeByKey<TodoIndexItem>(
    activeItems,
    stoppedItems,
    todoIndexKey,
  );
  return {
    ...(active ?? stopped!),
    current_projected_count: activeItems.length + stoppedItems.length,
    items,
    rollout_event_count: items.reduce(
      (total, item) => total + (item.event_count ?? 0),
      0,
    ),
    total_count: items.length,
  };
}

function mergeUsageSummary(
  active: StatusPayload["usage_summary"],
  stopped: StatusPayload["usage_summary"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
) {
  if (!active && !stopped) return null;
  const activeGoals = scopedItems(
    active?.goals ?? [],
    "active",
    goalScopes,
    (goal) => goal.goal_id,
  );
  const stoppedGoals = scopedItems(
    stopped?.goals ?? [],
    "stopped",
    goalScopes,
    (goal) => goal.goal_id,
  );
  const goals = mergeByKey<UsageGoal>(
    activeGoals,
    stoppedGoals,
    (goal) => goal.goal_id,
  );
  const totals = addUsageTotals(
    usageTotalsForGoals(activeGoals),
    usageTotalsForGoals(stoppedGoals),
  );
  return {
    ...(active ?? stopped!),
    goals: recomputeProjectShare(goals, Number(totals.runs_24h) || 0),
    sample_run_count: (active?.sample_run_count ?? 0) + (stopped?.sample_run_count ?? 0),
    totals,
  };
}

function mergeAgentManagementProjection(
  active: StatusPayload["agent_management_projection"],
  stopped: StatusPayload["agent_management_projection"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
): AgentManagementProjection | null {
  if (!active && !stopped) return null;
  const activeAgents = (active?.agents ?? []).filter((agent) =>
    agent.goal_ids.some((goalId) => itemMatchesScope(goalId, goalScopes, "active"))
    || (agent.current_todo?.goal_id
      ? itemMatchesScope(agent.current_todo.goal_id, goalScopes, "active")
      : false));
  const stoppedAgents = (stopped?.agents ?? []).filter((agent) =>
    agent.goal_ids.some((goalId) => itemMatchesScope(goalId, goalScopes, "stopped"))
    || (agent.current_todo?.goal_id
      ? itemMatchesScope(agent.current_todo.goal_id, goalScopes, "stopped")
      : false));
  const agents = mergeByKey(
    activeAgents,
    stoppedAgents,
    (agent) => agent.agent_id,
  ).map((agent) => {
    const stoppedAgent = stoppedAgents.find(
      (other) => other.agent_id === agent.agent_id,
    );
    if (!stoppedAgent) return agent;
    return {
      ...agent,
      goal_ids: Array.from(new Set([...(agent.goal_ids ?? []), ...stoppedAgent.goal_ids])),
    };
  });
  return {
    ...(active ?? stopped!),
    agents,
    source_summary: (active ?? stopped!)?.source_summary
      ? {
        ...(active ?? stopped!)!.source_summary,
        projected_agent_count: agents.length,
        registered_agent_count: new Set(agents.map((agent) => agent.agent_id)).size,
      }
      : (active ?? stopped!)?.source_summary,
  };
}

function mergeGoalChannelNotifications(
  active: StatusPayload["goal_channel_notification_projection"],
  stopped: StatusPayload["goal_channel_notification_projection"],
  goalScopes: ReadonlyMap<string, StatusPayload["run_history"]["goals"][number]["activation_state"]>,
) {
  if (!active && !stopped) return null;
  const goals = mergeByKey<GoalChannelNotificationRow>(
    scopedItems(active?.goals ?? [], "active", goalScopes, (row) => row.goal_id),
    scopedItems(stopped?.goals ?? [], "stopped", goalScopes, (row) => row.goal_id),
    (row) => row.goal_id,
  );
  return { ...(active ?? stopped!), goals };
}

/**
 * Merge `incoming` (a scoped snapshot) into `current` (the already-rendered
 * view) and return the combined `scope: "all"` payload.
 *
 * `incoming` may be either an active or a stopped scope:
 * - active scope: active goals are authoritative (replace), stopped goals are
 *   preserved from `current`.
 * - stopped scope: stopped goals are authoritative (replace), active goals are
 *   preserved from `current`.
 *
 * When `incoming` is not a scoped payload (e.g. a legacy server that ignores
 * the query and returns a full payload without `goal_projection`), it is
 * returned unchanged so the single-request fallback keeps working.
 */
export function mergeScopedStatusProjections(
  current: StatusPayload,
  incoming: StatusPayload,
): StatusPayload {
  const incomingScope = incoming.goal_projection?.scope;
  if (incomingScope !== "active" && incomingScope !== "stopped") {
    return incoming;
  }
  const direction = incomingScope as GoalProjectionScope;
  const authoritativeGoals = incoming.run_history.goals;
  const preservedGoals = current.run_history.goals;

  const activeGoals = direction === "active"
    ? authoritativeGoals
    : preservedGoals.filter((goal) => goal.activation_state !== "stopped");
  const stoppedGoals = direction === "stopped"
    ? authoritativeGoals
    : preservedGoals.filter((goal) => goal.activation_state === "stopped");

  const goals = mergeByKey(activeGoals, stoppedGoals, (goal) => goal.id);
  const goalScopes = new Map(goals.map((goal) => [goal.id, goal.activation_state]));
  const activePayload = direction === "active" ? incoming : current;
  const stoppedPayload = direction === "stopped" ? incoming : current;

  const currentRevision = current.goal_projection?.registry_revision ?? null;
  const incomingRevision = incoming.goal_projection?.registry_revision ?? null;
  const revisionsComparable = currentRevision !== null && incomingRevision !== null;
  const revisionsMatch = !revisionsComparable || currentRevision === incomingRevision;

  return {
    ...current,
    agent_management_projection: mergeAgentManagementProjection(
      activePayload.agent_management_projection,
      stoppedPayload.agent_management_projection,
      goalScopes,
    ),
    attention_queue: mergeAttentionQueue(
      activePayload.attention_queue,
      stoppedPayload.attention_queue,
      goalScopes,
    ),
    decision_freshness_summary: mergeDecisionFreshnessSummary(
      activePayload.decision_freshness_summary,
      stoppedPayload.decision_freshness_summary,
      goalScopes,
    ),
    event_ledger_summary: mergeEventLedgerSummary(
      activePayload.event_ledger_summary,
      stoppedPayload.event_ledger_summary,
      goalScopes,
    ),
    goal_channel_notification_projection: mergeGoalChannelNotifications(
      activePayload.goal_channel_notification_projection,
      stoppedPayload.goal_channel_notification_projection,
      goalScopes,
    ),
    goal_projection: {
      schema_version: "loopx_goal_projection_scope_v0",
      ...incoming.goal_projection,
      complete: revisionsMatch,
      projected_goal_count: goals.length,
      registry_goal_count: incoming.goal_projection?.registry_goal_count ?? 0,
      scope: "all",
    },
    run_history: {
      ...current.run_history,
      goal_count: goals.length,
      goals,
      recent_runs: mergeRecentRuns(
        activePayload.run_history.recent_runs,
        stoppedPayload.run_history.recent_runs,
      ),
      run_count: activePayload.run_history.run_count + stoppedPayload.run_history.run_count,
    },
    todo_index: mergeTodoIndex(
      activePayload.todo_index,
      stoppedPayload.todo_index,
      goalScopes,
    ),
    usage_summary: mergeUsageSummary(
      activePayload.usage_summary,
      stoppedPayload.usage_summary,
      goalScopes,
    ),
  };
}
