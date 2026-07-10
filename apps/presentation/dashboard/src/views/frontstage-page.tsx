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

import showcaseCatalog from "../../../../../docs/showcases/showcase-catalog.json";
import rolloutProjectionFixture from "../../../../../examples/fixtures/frontstage-rollout-projections.public.json";
import rolloutFixture from "../../../../../examples/fixtures/long-horizon-self-iteration-rollout.public.json";
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
  interactive_page?: string;
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

type RolloutLane = {
  lane_id: string;
  agent_id: string;
  agent_model: "peer_v1";
  profile_role: string;
  display_name: string;
};

type RolloutAnimationEvent = {
  animation_event_id: string;
  lane_id: string;
  kind: string;
  title: string;
  source_event_ids: string[];
  state_transition?: {
    from_state?: string;
    to_state?: string;
  };
  human_effect?: {
    decision_id?: string;
    changes?: string[];
  };
  confidence: string;
  display_hint?: string;
  evidence_refs?: string[];
  inference_reason?: string;
};

type LongHorizonRolloutFixture = {
  schema_version: string;
  fixture_id: string;
  lanes: RolloutLane[];
  animation_events: RolloutAnimationEvent[];
  truth_contract: {
    event_ledger_is_source_of_truth: boolean;
    projection_is_writable: boolean;
    write_authority: string;
  };
  frontend_acceptance: {
    must_render: string[];
  };
};

const selfIterationRollout = rolloutFixture as LongHorizonRolloutFixture;

type RolloutProjectionNodeState = "open" | "merged" | "closed" | "done" | "active" | "blocked" | "planned";
type RolloutProjectionTone = BadgeTone;

type RolloutProjectionMetric = {
  helper: string;
  label: string;
  metric_id: string;
  tone: RolloutProjectionTone;
  value: string;
};

type RolloutProjectionMappingLayer = {
  description: string;
  edge_ids: string[];
  input: string;
  label: string;
  layer_id: string;
  node_ids: string[];
  output: string;
  role: string;
  tone: RolloutProjectionTone;
};

type RolloutProjectionFlowSignal = {
  description: string;
  label: string;
  signal_id: string;
  source_node_ids: string[];
  tone: RolloutProjectionTone;
  value: string;
};

type RolloutProjectionRelationshipSummary = {
  count: number;
  description: string;
  kind: string;
  label: string;
};

type RolloutProjectionAttentionHotspot = {
  description: string;
  edge_ids: string[];
  hotspot_id: string;
  label: string;
  node_ids: string[];
  severity: "low" | "medium" | "high";
};

type RolloutTimelineTick = {
  at: string;
  label: string;
  tick_id: string;
};

type RolloutTimeline = {
  axis_kind: string;
  description: string;
  end_at?: string;
  item_node_ids: string[];
  start_at?: string;
  ticks?: RolloutTimelineTick[];
  timeline_id: string;
  time_basis?: string;
  title: string;
  timezone?: string;
  unit_label: string;
  window_label: string;
};

type RolloutSequenceStep = {
  label: string;
  node_ids: string[];
  status: string;
  step_id: string;
};

type RolloutSequenceUnit = {
  lane_id: string;
  node_ids: string[];
  order: number;
  outcome: string;
  requirement: string;
  stage_steps: RolloutSequenceStep[];
  state: RolloutProjectionNodeState;
  triggered_by: string;
  unit_id: string;
  unlocks: string[];
};

type RolloutSequence = {
  description: string;
  sequence_id: string;
  title: string;
  units: RolloutSequenceUnit[];
};

type RolloutProjectionNode = {
  confidence?: string;
  kind: string;
  label: string;
  lane_id: string;
  node_id: string;
  role?: string;
  state: RolloutProjectionNodeState;
  title: string;
  completed_at?: string;
  display_time?: string;
  duration_label?: string;
  occurred_at?: string;
  started_at?: string;
  timezone?: string;
  url?: string;
};

type RolloutTimeMilestone = {
  detail: string;
  id: string;
  label: string;
  time: number | null;
  time_label: string;
};

type RolloutProjectionStage = {
  actor_scope: string;
  confidence: string;
  current: boolean;
  description: string;
  label: string;
  stage_id: string;
};

type RolloutProjectionLane = {
  label: string;
  lane_id: string;
  node_ids: string[];
  role: string;
  summary: string;
};

type RolloutProjectionEdge = {
  confidence: string;
  edge_id: string;
  edge_kind: string;
  from_node_id: string;
  label: string;
  to_node_id: string;
};

type RolloutProjection = {
  attention_hotspots?: RolloutProjectionAttentionHotspot[];
  edges: RolloutProjectionEdge[];
  frontend_acceptance: {
    must_render: string[];
  };
  flow_signals?: RolloutProjectionFlowSignal[];
  lanes: RolloutProjectionLane[];
  mapping_layers?: RolloutProjectionMappingLayer[];
  metrics: RolloutProjectionMetric[];
  nodes: RolloutProjectionNode[];
  projection_id: string;
  projection_kind: string;
  scene: {
    confidence: string;
    explanation: string;
    scene_id: string;
    stage_label: string;
    title: string;
    why_current: string;
  };
  relationship_summaries?: RolloutProjectionRelationshipSummary[];
  rollout_sequence?: RolloutSequence;
  timeline?: RolloutTimeline;
  source_contract: {
    anchor_node_id: string;
    claim_boundary: string;
    next_projection_hint: string;
    sample_window: string;
  };
  stages: RolloutProjectionStage[];
  title: string;
};

type RolloutProjectionBundle = {
  planned_projections?: Array<{
    projection_id: string;
    reason: string;
    status: string;
  }>;
  projection_model: {
    description: string;
    edge_contract: string;
    node_contract: string;
    optional_rich_sections?: string[];
    required_sections: string[];
    schema_version: string;
  };
  projections: RolloutProjection[];
  schema_version: string;
  truth_contract: {
    evidence_floor: string;
    projection_is_writable: boolean;
    recompute_rule: string;
    write_authority: string;
  };
};

const rolloutProjectionBundle = rolloutProjectionFixture as RolloutProjectionBundle;
const overnightPrProjection = rolloutProjectionBundle.projections[0];

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

function showcaseCaseHref(item?: ShowcaseFrontstageCase) {
  if (!item) {
    return undefined;
  }
  if (item.interactive_page) {
    return `https://huangruiteng.github.io/loopx/${item.interactive_page}`;
  }
  if (item.case_page) {
    return `https://github.com/huangruiteng/loopx/blob/main/${item.case_page}`;
  }
  return undefined;
}

function uniqueClaimOwners(projection: GoalChannelProjection) {
  return Array.from(
    new Set(
      [
        ...projection.agent_todos.map((todo) => todo.claimed_by),
        ...projection.active_leases.map((lease) => lease.owner_agent),
      ].filter((value): value is string => Boolean(value)),
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

type TrajectoryStage = {
  animationEventId: string;
  confidence: string;
  evidenceRefs: string[];
  inferenceReason?: string;
  isCurrent: boolean;
  isSynthetic: boolean;
  kind: string;
  laneLabel: string;
  laneRole: string;
  progress: number;
  sourceEventIds: string[];
  stageLabel: string;
  title: string;
  transitionLabel: string;
};

type TrajectoryEvidenceItem = {
  eventTitle: string;
  kind: "evidence_ref" | "source_event";
  ref: string;
};

function rolloutStageLabel(event: RolloutAnimationEvent) {
  if (event.kind === "deliverable") {
    return "Protocol";
  }
  if (event.kind === "human_gate") {
    return "Gate";
  }
  if (event.kind === "validation") {
    return "Validation";
  }
  if (event.kind === "synthetic_bridge") {
    return "UI bridge";
  }
  if (event.title.toLowerCase().includes("sufficiency")) {
    return "Sufficiency";
  }
  if (event.kind === "handoff") {
    return "Handoff";
  }
  return "State";
}

function trajectoryConfidenceTone(confidence: string): BadgeTone {
  if (confidence === "observed") {
    return "success";
  }
  if (confidence === "observed_public_metadata") {
    return "success";
  }
  if (confidence === "synthetic_bridge") {
    return "warning";
  }
  if (confidence.startsWith("inferred")) {
    return "info";
  }
  return "neutral";
}

function nodeStateTone(state: RolloutProjectionNodeState): BadgeTone {
  if (state === "merged" || state === "done") {
    return "success";
  }
  if (state === "open" || state === "active") {
    return "info";
  }
  if (state === "blocked") {
    return "danger";
  }
  return "warning";
}

function sequenceStepTone(status: string): BadgeTone {
  if (["done", "merged", "validated"].includes(status)) {
    return "success";
  }
  if (["active", "reviewing", "review"].includes(status)) {
    return "warning";
  }
  if (["queued", "planned"].includes(status)) {
    return "neutral";
  }
  return "info";
}

const trajectoryLaneTones = [
  {
    ring: "border-cyan-300/40 bg-cyan-300/10 text-cyan-100",
    card: "border-cyan-200 bg-cyan-50",
    dot: "bg-cyan-300",
    line: "bg-cyan-300/40",
  },
  {
    ring: "border-emerald-300/40 bg-emerald-300/10 text-emerald-100",
    card: "border-emerald-200 bg-emerald-50",
    dot: "bg-emerald-400",
    line: "bg-emerald-300/40",
  },
  {
    ring: "border-amber-300/40 bg-amber-300/10 text-amber-100",
    card: "border-amber-200 bg-amber-50",
    dot: "bg-amber-400",
    line: "bg-amber-300/40",
  },
  {
    ring: "border-rose-300/40 bg-rose-300/10 text-rose-100",
    card: "border-rose-200 bg-rose-50",
    dot: "bg-rose-400",
    line: "bg-rose-300/40",
  },
  {
    ring: "border-violet-300/40 bg-violet-300/10 text-violet-100",
    card: "border-violet-200 bg-violet-50",
    dot: "bg-violet-400",
    line: "bg-violet-300/40",
  },
];

function trajectoryLaneTone(index: number) {
  return trajectoryLaneTones[index % trajectoryLaneTones.length];
}

function nodesById(projection: RolloutProjection) {
  return new Map(projection.nodes.map((item) => [item.node_id, item]));
}

function nodesForLane(projection: RolloutProjection, lane: RolloutProjectionLane) {
  const byId = nodesById(projection);
  return lane.node_ids.map((nodeId) => byId.get(nodeId)).filter((item): item is RolloutProjectionNode => Boolean(item));
}

function prNumberFromNode(node: RolloutProjectionNode) {
  const match = node.node_id.match(/^pr_(\d+)$/);
  return match ? Number(match[1]) : null;
}

function rolloutOrderedNodes(projection: RolloutProjection) {
  const byId = nodesById(projection);
  if (projection.timeline?.item_node_ids.length) {
    return projection.timeline.item_node_ids
      .map((nodeId) => byId.get(nodeId))
      .filter((node): node is RolloutProjectionNode => Boolean(node));
  }

  return projection.nodes
    .filter((node) => node.role !== "anchor" && node.role !== "precursor")
    .sort((left, right) => {
      const leftPr = prNumberFromNode(left);
      const rightPr = prNumberFromNode(right);
      if (leftPr !== null && rightPr !== null) {
        return leftPr - rightPr;
      }
      return left.label.localeCompare(right.label);
    });
}

function parseRolloutTime(value?: string) {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function rolloutNodeTime(node: RolloutProjectionNode) {
  return parseRolloutTime(node.occurred_at) ?? parseRolloutTime(node.started_at) ?? parseRolloutTime(node.completed_at);
}

function rolloutTimelineBounds(projection: RolloutProjection, nodes: RolloutProjectionNode[]) {
  const nodeTimes = nodes.map(rolloutNodeTime).filter((value): value is number => value !== null);
  const completedTimes = nodes
    .map((node) => parseRolloutTime(node.completed_at))
    .filter((value): value is number => value !== null);
  const start = parseRolloutTime(projection.timeline?.start_at) ?? (nodeTimes.length ? Math.min(...nodeTimes) : null);
  const end =
    parseRolloutTime(projection.timeline?.end_at) ??
    (completedTimes.length ? Math.max(...completedTimes) : nodeTimes.length ? Math.max(...nodeTimes) : null);
  if (start === null || end === null || end <= start) {
    return null;
  }
  return { end, start };
}

function rolloutTimeRatio(value: number | null, bounds: { end: number; start: number } | null, fallbackRatio: number) {
  if (value === null || !bounds) {
    return fallbackRatio;
  }
  const ratio = (value - bounds.start) / (bounds.end - bounds.start);
  return Math.min(1, Math.max(0, ratio));
}

function rolloutTimelinePercent(
  node: RolloutProjectionNode,
  bounds: { end: number; start: number } | null,
  index: number,
  total: number,
) {
  const fallback = total > 1 ? index / (total - 1) : 0.5;
  return rolloutTimeRatio(rolloutNodeTime(node), bounds, fallback) * 100;
}

function rolloutTickPercent(tick: RolloutTimelineTick, bounds: { end: number; start: number } | null) {
  return rolloutTimeRatio(parseRolloutTime(tick.at), bounds, 0) * 100;
}

function rolloutNodeTimeLabel(node?: RolloutProjectionNode) {
  return node?.display_time ?? node?.started_at ?? node?.occurred_at ?? "time n/a";
}

function rolloutClockLabel(value?: string) {
  const match = value?.match(/T(\d{2}:\d{2})/);
  return match?.[1] ?? value ?? "n/a";
}

function rolloutNodeStartClock(node?: RolloutProjectionNode) {
  return node?.display_time?.split(" -> ")[0] ?? rolloutClockLabel(node?.started_at ?? node?.occurred_at);
}

function uniqueRolloutMilestones(items: RolloutTimeMilestone[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.label}:${item.detail}:${item.time_label}`;
    if (item.time === null || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function rolloutTimelineMilestones(nodes: RolloutProjectionNode[]): RolloutTimeMilestone[] {
  const timedNodes = nodes
    .map((node) => ({ node, time: rolloutNodeTime(node) }))
    .filter((item): item is { node: RolloutProjectionNode; time: number } => item.time !== null)
    .sort((left, right) => left.time - right.time);
  if (!timedNodes.length) {
    return [];
  }
  const first = timedNodes[0];
  const midpoint = timedNodes[Math.floor((timedNodes.length - 1) / 2)];
  const lastStart = timedNodes[timedNodes.length - 1];
  const latestCompletion = nodes
    .map((node) => ({ node, time: parseRolloutTime(node.completed_at) }))
    .filter((item): item is { node: RolloutProjectionNode; time: number } => item.time !== null)
    .sort((left, right) => right.time - left.time)[0];

  return uniqueRolloutMilestones([
    {
      detail: first.node.label,
      id: "start",
      label: "start",
      time: first.time,
      time_label: rolloutNodeStartClock(first.node),
    },
    {
      detail: midpoint.node.label,
      id: "midpoint",
      label: "midpoint",
      time: midpoint.time,
      time_label: rolloutNodeStartClock(midpoint.node),
    },
    {
      detail: lastStart.node.label,
      id: "last_start",
      label: "last start",
      time: lastStart.time,
      time_label: rolloutNodeStartClock(lastStart.node),
    },
    {
      detail: latestCompletion?.node.label ?? lastStart.node.label,
      id: "tail_done",
      label: "tail done",
      time: latestCompletion?.time ?? null,
      time_label: rolloutClockLabel(latestCompletion?.node.completed_at),
    },
  ]);
}

function RolloutProjectionConstellation({
  bundle,
  projection,
}: {
  bundle: RolloutProjectionBundle;
  projection: RolloutProjection;
}) {
  const visibleNodes = projection.nodes
    .filter((node) => node.role !== "anchor" && node.role !== "precursor")
    .slice(0, 30);

  return (
    <div
      className="frontstage-rollout-projection-constellation relative overflow-hidden rounded-md border border-slate-800 bg-slate-950 p-4 text-white xl:col-span-2"
      data-testid="frontstage-rollout-projection-constellation"
    >
      <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
            Rollout projection
          </div>
          <h3 className="mt-2 max-w-3xl text-lg font-semibold leading-7 text-white">
            {projection.scene.title}
          </h3>
          <p className="mt-2 max-w-4xl text-sm font-medium leading-6 text-slate-300">
            {projection.scene.explanation}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{projection.scene.stage_label}</Badge>
          <Badge variant={trajectoryConfidenceTone(projection.scene.confidence)}>
            {projection.scene.confidence}
          </Badge>
        </div>
      </div>

      <div className="relative z-10 mt-5 grid gap-3 md:grid-cols-4" data-testid="frontstage-rollout-projection-metrics">
        {projection.metrics.map((metric) => (
          <div className="rounded-md border border-white/10 bg-white/[0.06] px-3 py-3" key={metric.metric_id}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">
                {metric.label}
              </span>
              <Badge variant={metric.tone}>{metric.helper}</Badge>
            </div>
            <div className="mt-2 text-2xl font-semibold leading-8 text-white">{metric.value}</div>
          </div>
        ))}
      </div>

      <div
        aria-hidden="true"
        className="frontstage-rollout-node-grid relative z-10 mt-5"
        data-testid="frontstage-rollout-node-particles"
      >
        {visibleNodes.map((node, index) => (
          <span
            className={cn(
              "frontstage-rollout-node-dot h-2.5 rounded-full",
              node.state === "merged" ? "bg-emerald-300" : node.state === "open" ? "bg-cyan-300" : "bg-amber-300",
            )}
            key={node.node_id}
            style={{ animationDelay: `${index * 80}ms` }}
            title={`${node.label} ${node.state}`}
          />
        ))}
      </div>

      <div
        className="relative z-10 mt-4 grid gap-2 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-xs font-medium leading-5 text-slate-300 md:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]"
        data-testid="frontstage-rollout-projection-model-contract"
      >
        <div>
          <span className="font-semibold text-white">Projection model: </span>
          {bundle.projection_model.required_sections.join(" / ")}.
        </div>
        <div>
          <span className="font-semibold text-white">Evidence floor: </span>
          {bundle.truth_contract.evidence_floor}.
        </div>
      </div>
    </div>
  );
}

type PrMeshEdge = {
  edge_id: string;
  edge_kind: "timeline" | "lane" | "explicit";
  from_node_id: string;
  label: string;
  to_node_id: string;
};

function meshEdgeTitle(edge: PrMeshEdge, byId: Map<string, RolloutProjectionNode>) {
  const fromNode = byId.get(edge.from_node_id);
  const toNode = byId.get(edge.to_node_id);
  return `${edge.edge_kind}: ${fromNode?.label ?? edge.from_node_id} -> ${toNode?.label ?? edge.to_node_id}; ${edge.label}`;
}

function RolloutRelationshipMesh({ projection }: { projection: RolloutProjection }) {
  const orderedNodes = rolloutOrderedNodes(projection);
  const byId = new Map(orderedNodes.map((node) => [node.node_id, node]));
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const timelineBounds = rolloutTimelineBounds(projection, orderedNodes);
  const timeTicks = projection.timeline?.ticks ?? [];
  const laneRows = new Map<string, { index: number; y: number }>(
    projection.lanes.map((lane, index) => [lane.lane_id, { index, y: 70 + index * 112 }]),
  );
  const positions = new Map<string, { x: number; y: number }>();

  for (const lane of projection.lanes) {
    const laneNodes = lane.node_ids.map((nodeId) => byId.get(nodeId)).filter((node): node is RolloutProjectionNode => Boolean(node));
    const laneY = laneRows.get(lane.lane_id)?.y ?? 70;
    let lastX = 140;
    laneNodes.forEach((node, index) => {
      const fallback = laneNodes.length > 1 ? index / (laneNodes.length - 1) : 0.5;
      const ratio = rolloutTimeRatio(rolloutNodeTime(node), timelineBounds, fallback);
      const timeX = 190 + ratio * 750;
      const spacedX = Math.max(timeX, lastX + 76);
      const x = Math.min(940, Math.max(190, spacedX));
      lastX = x;
      positions.set(node.node_id, { x, y: laneY });
    });
  }

  const edgeMap = new Map<string, PrMeshEdge>();
  const setEdge = (edge: PrMeshEdge) => {
    const key = `${edge.from_node_id}->${edge.to_node_id}`;
    const current = edgeMap.get(key);
    if (!current || edge.edge_kind === "explicit" || (edge.edge_kind === "lane" && current.edge_kind === "timeline")) {
      edgeMap.set(key, edge);
    }
  };

  orderedNodes.slice(0, -1).forEach((node, index) => {
    const next = orderedNodes[index + 1];
    setEdge({
      edge_id: `timeline_${node.node_id}_${next.node_id}`,
      edge_kind: "timeline",
      from_node_id: node.node_id,
      label: "overnight sequence",
      to_node_id: next.node_id,
    });
  });

  for (const lane of projection.lanes) {
    const laneNodes = lane.node_ids.map((nodeId) => byId.get(nodeId)).filter((node): node is RolloutProjectionNode => Boolean(node));
    laneNodes.slice(0, -1).forEach((node, index) => {
      const next = laneNodes[index + 1];
      setEdge({
        edge_id: `lane_${lane.lane_id}_${node.node_id}_${next.node_id}`,
        edge_kind: "lane",
        from_node_id: node.node_id,
        label: lane.label,
        to_node_id: next.node_id,
      });
    });
  }

  for (const edge of projection.edges) {
    if (positions.has(edge.from_node_id) && positions.has(edge.to_node_id)) {
      setEdge({
        edge_id: edge.edge_id,
        edge_kind: "explicit",
        from_node_id: edge.from_node_id,
        label: edge.label,
        to_node_id: edge.to_node_id,
      });
    }
  }

  const meshEdges = Array.from(edgeMap.values());
  const explicitEdgeCount = meshEdges.filter((edge) => edge.edge_kind === "explicit").length;
  const laneFlowEdgeCount = meshEdges.filter((edge) => edge.edge_kind === "lane").length;
  const timelineEdgeCount = meshEdges.filter((edge) => edge.edge_kind === "timeline").length;
  const hoveredEdge = meshEdges.find((edge) => edge.edge_id === hoveredEdgeId) ?? null;
  const timelineTitle = projection.timeline?.title ?? "Rollout timeline";
  const timelineWindow = projection.timeline?.window_label ?? projection.source_contract.sample_window;
  const timelineUnitLabel = projection.timeline?.unit_label ?? "work nodes";
  const timelineAxis = projection.timeline?.axis_kind ?? "ordered";
  const timelineTimezone = projection.timeline?.timezone ?? "local";
  const timeMilestones = rolloutTimelineMilestones(orderedNodes);

  return (
    <div
      className="frontstage-rollout-pr-mesh relative overflow-hidden rounded-md border border-slate-800 bg-slate-950 p-4 text-white xl:col-span-2"
      data-testid="frontstage-rollout-relationship-mesh"
    >
      <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
            {projection.title}
          </div>
          <h3 className="mt-2 max-w-3xl text-lg font-semibold leading-7 text-white">
            A wall-clock rollout map, all at once
          </h3>
          <p className="mt-2 max-w-4xl text-sm font-medium leading-6 text-slate-300">
            Every work unit in {timelineWindow} is placed on a real time axis. Thin links preserve ordering, lane links
            show parallel workstreams, and bright links mark explicit review or follow-up relationships. Hover nodes or
            lines to inspect time, duration, and relationship details.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="success">{orderedNodes.length} {timelineUnitLabel}</Badge>
          <Badge variant="info">{meshEdges.length} links</Badge>
          <Badge variant="warning">{explicitEdgeCount} explicit</Badge>
          <Badge variant="neutral">{timelineTimezone}</Badge>
        </div>
      </div>

      <div
        className="frontstage-rollout-timeline relative z-10 mt-4 rounded-md border border-white/10 bg-black/20 p-3"
        data-testid="frontstage-rollout-timeline"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">{timelineTitle}</div>
            <div className="mt-1 text-sm font-semibold leading-6 text-white">{timelineWindow}</div>
            <div className="mt-1 text-[11px] font-medium leading-4 text-slate-400">
              {projection.timeline?.time_basis ?? "work-unit order"}
            </div>
          </div>
          <Badge variant="info">{timelineAxis}</Badge>
        </div>
        <div
          className="frontstage-rollout-timeline-track mt-3"
          data-testid="frontstage-rollout-timeline-scale"
        >
          {timeTicks.map((tick) => (
            <span
              className="frontstage-rollout-timeline-tick"
              data-testid="frontstage-rollout-timeline-tick"
              key={tick.tick_id}
              style={{ left: `${rolloutTickPercent(tick, timelineBounds)}%` }}
            >
              {tick.label}
            </span>
          ))}
          {orderedNodes.map((node, index) => (
            <a
              className={cn(
                "frontstage-rollout-timeline-point",
                node.state === "merged"
                  ? "frontstage-rollout-timeline-point-merged"
                  : node.state === "open"
                    ? "frontstage-rollout-timeline-point-open"
                    : "frontstage-rollout-timeline-point-closed",
              )}
              data-node-time={rolloutNodeTimeLabel(node)}
              data-testid="frontstage-rollout-timeline-point"
              href={node.url ?? "#"}
              key={node.node_id}
              rel={node.url ? "noreferrer" : undefined}
              style={{ left: `${rolloutTimelinePercent(node, timelineBounds, index, orderedNodes.length)}%` }}
              target={node.url ? "_blank" : undefined}
              title={`${String(index + 1).padStart(2, "0")} ${node.label}: ${node.title} / ${rolloutNodeTimeLabel(node)}`}
            >
              <span>{node.label.replace("#", "")}</span>
              <small>{node.display_time?.split(" -> ")[0] ?? ""}</small>
            </a>
          ))}
        </div>
        {timeMilestones.length ? (
          <div className="frontstage-rollout-time-milestones" data-testid="frontstage-rollout-time-milestones">
            {timeMilestones.map((milestone) => (
              <span
                className="frontstage-rollout-time-milestone"
                data-testid="frontstage-rollout-time-milestone"
                key={milestone.id}
                style={{ left: `${rolloutTimeRatio(milestone.time, timelineBounds, 0) * 100}%` }}
                title={`${milestone.label}: ${milestone.detail} at ${milestone.time_label}`}
              >
                <strong>{milestone.time_label}</strong>
                <small>
                  {milestone.label} {milestone.detail}
                </small>
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="relative z-10 mt-4 overflow-x-auto rounded-md border border-white/10 bg-black/20">
        <div className="frontstage-rollout-pr-mesh-stage relative">
          <div aria-hidden="true" className="frontstage-rollout-pr-mesh-time-grid">
            {timeTicks.map((tick) => (
              <span
                className="frontstage-rollout-pr-mesh-time-tick"
                data-testid="frontstage-rollout-mesh-time-tick"
                key={`${tick.tick_id}-mesh`}
                style={{ left: `${10 + rolloutTickPercent(tick, timelineBounds) * 0.82}%` }}
              >
                {tick.label}
              </span>
            ))}
          </div>
          <svg
            aria-label="Rollout relationship graph"
            className="frontstage-rollout-pr-mesh-svg"
            preserveAspectRatio="none"
            role="img"
            viewBox="0 0 1000 560"
          >
            {meshEdges.map((edge, index) => {
              const from = positions.get(edge.from_node_id);
              const to = positions.get(edge.to_node_id);
              if (!from || !to) {
                return null;
              }
              const edgeTitle = meshEdgeTitle(edge, byId);
              return (
                <g
                  aria-label={edgeTitle}
                  className="frontstage-rollout-pr-mesh-edge-group"
                  data-edge-kind={edge.edge_kind}
                  data-edge-label={edge.label}
                  data-edge-title={edgeTitle}
                  data-from-node={edge.from_node_id}
                  data-testid="frontstage-rollout-mesh-edge"
                  data-to-node={edge.to_node_id}
                  key={edge.edge_id}
                  onBlur={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                  onFocus={() => setHoveredEdgeId(edge.edge_id)}
                  onMouseEnter={() => setHoveredEdgeId(edge.edge_id)}
                  onMouseLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                  role="listitem"
                  style={{ animationDelay: `${index * 30}ms` }}
                  tabIndex={0}
                >
                  <title>{edgeTitle}</title>
                  <line
                    className="frontstage-rollout-pr-mesh-edge-hit"
                    data-testid="frontstage-rollout-mesh-edge-hit"
                    onMouseEnter={() => setHoveredEdgeId(edge.edge_id)}
                    onMouseLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                    onPointerEnter={() => setHoveredEdgeId(edge.edge_id)}
                    onPointerLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                    x1={from.x}
                    x2={to.x}
                    y1={from.y}
                    y2={to.y}
                  />
                  <line
                    className={cn("frontstage-rollout-pr-mesh-edge", `frontstage-rollout-pr-mesh-edge-${edge.edge_kind}`)}
                    onMouseEnter={() => setHoveredEdgeId(edge.edge_id)}
                    onMouseLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                    onPointerEnter={() => setHoveredEdgeId(edge.edge_id)}
                    onPointerLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                    x1={from.x}
                    x2={to.x}
                    y1={from.y}
                    y2={to.y}
                  />
                </g>
              );
            })}
          </svg>

          {meshEdges.map((edge) => {
            const from = positions.get(edge.from_node_id);
            const to = positions.get(edge.to_node_id);
            if (!from || !to) {
              return null;
            }
            const edgeTitle = meshEdgeTitle(edge, byId);
            return (
              <button
                aria-label={edgeTitle}
                className={cn(
                  "frontstage-rollout-mesh-edge-hotspot",
                  `frontstage-rollout-mesh-edge-hotspot-${edge.edge_kind}`,
                )}
                data-edge-kind={edge.edge_kind}
                data-edge-label={edge.label}
                data-edge-title={edgeTitle}
                data-from-node={edge.from_node_id}
                data-testid="frontstage-rollout-mesh-edge-hotspot"
                data-to-node={edge.to_node_id}
                key={`${edge.edge_id}-hotspot`}
                onBlur={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                onFocus={() => setHoveredEdgeId(edge.edge_id)}
                onMouseEnter={() => setHoveredEdgeId(edge.edge_id)}
                onMouseLeave={() => setHoveredEdgeId((current) => (current === edge.edge_id ? null : current))}
                style={{
                  left: `${(((from.x + to.x) / 2) / 1000) * 100}%`,
                  top: `${(((from.y + to.y) / 2) / 560) * 100}%`,
                }}
                title={edgeTitle}
                type="button"
              />
            );
          })}

          {projection.lanes.map((lane) => {
            const row = laneRows.get(lane.lane_id);
            const laneNodes = lane.node_ids.filter((nodeId) => byId.has(nodeId));
            if (!row || !laneNodes.length) {
              return null;
            }
            return (
              <div
                className="frontstage-rollout-pr-mesh-lane-label"
                data-testid="frontstage-rollout-mesh-lane"
                key={lane.lane_id}
                style={{ top: `${(row.y / 560) * 100}%` }}
              >
                <span>{lane.label}</span>
                <Badge variant="neutral">{laneNodes.length}</Badge>
              </div>
            );
          })}

          {orderedNodes.map((node, index) => {
            const position = positions.get(node.node_id);
            if (!position) {
              return null;
            }
            const lane = projection.lanes.find((item) => item.lane_id === node.lane_id);
            return (
              <a
                className={cn(
                  "frontstage-rollout-pr-mesh-node",
                  node.state === "merged"
                    ? "frontstage-rollout-pr-mesh-node-merged"
                    : node.state === "open"
                      ? "frontstage-rollout-pr-mesh-node-open"
                      : "frontstage-rollout-pr-mesh-node-closed",
                )}
                data-node-lane={lane?.label ?? node.lane_id}
                data-node-state={node.state}
                data-node-time={rolloutNodeTimeLabel(node)}
                data-node-title={node.title}
                data-testid="frontstage-rollout-mesh-node"
                href={node.url ?? "#"}
                key={node.node_id}
                rel={node.url ? "noreferrer" : undefined}
                style={{
                  animationDelay: `${index * 45}ms`,
                  left: `${(position.x / 1000) * 100}%`,
                  top: `${(position.y / 560) * 100}%`,
                }}
                target={node.url ? "_blank" : undefined}
                title={`${node.label} ${node.title} / ${lane?.label ?? node.lane_id}`}
              >
                <span>{node.label}</span>
                <small>{node.state}</small>
                <span className="frontstage-rollout-pr-mesh-node-tooltip" data-testid="frontstage-rollout-mesh-node-tooltip">
                  <strong>{node.label}</strong>
                  <span>{node.title}</span>
                  <span>time: {rolloutNodeTimeLabel(node)}</span>
                  <span>duration: {node.duration_label ?? "n/a"}</span>
                  <span>lane: {lane?.label ?? node.lane_id}</span>
                  <span>state: {node.state}</span>
                </span>
              </a>
            );
          })}

          <div
            className={cn(
              "frontstage-rollout-mesh-edge-hover-card",
              hoveredEdge ? "frontstage-rollout-mesh-edge-hover-card-visible" : "",
            )}
            data-testid="frontstage-rollout-mesh-edge-hover-card"
          >
            {hoveredEdge ? (
              <>
                <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
                  {hoveredEdge.edge_kind} relation
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <Badge variant="info">{byId.get(hoveredEdge.from_node_id)?.label ?? hoveredEdge.from_node_id}</Badge>
                  <span className="text-slate-500">-&gt;</span>
                  <Badge variant="success">{byId.get(hoveredEdge.to_node_id)?.label ?? hoveredEdge.to_node_id}</Badge>
                </div>
                <p className="mt-2 grid gap-1 text-[11px] font-semibold leading-4 text-slate-400">
                  <span>from: {rolloutNodeTimeLabel(byId.get(hoveredEdge.from_node_id))}</span>
                  <span>to: {rolloutNodeTimeLabel(byId.get(hoveredEdge.to_node_id))}</span>
                </p>
                <p className="mt-2 text-xs font-medium leading-5 text-slate-300">{hoveredEdge.label}</p>
              </>
            ) : (
              <>
                <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">Hover a line</div>
                <p className="mt-1 text-xs font-medium leading-5 text-slate-400">
                  Relation details appear here without opening raw logs.
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="relative z-10 mt-3 grid gap-2 md:grid-cols-4">
        <div className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Timeline links</div>
          <div className="mt-1 text-lg font-semibold text-white">{timelineEdgeCount}</div>
        </div>
        <div className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Lane-flow links</div>
          <div className="mt-1 text-lg font-semibold text-white">{laneFlowEdgeCount}</div>
        </div>
        <div className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Explicit review links</div>
          <div className="mt-1 text-lg font-semibold text-white">{explicitEdgeCount}</div>
        </div>
        <div className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2">
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Public boundary</div>
          <div className="mt-1 text-sm font-semibold leading-6 text-slate-200">metadata only</div>
        </div>
      </div>
    </div>
  );
}

function RolloutRequirementSpine({ projection }: { projection: RolloutProjection }) {
  const sequence = projection.rollout_sequence;
  if (!sequence) {
    return null;
  }

  const byId = nodesById(projection);
  const units = [...sequence.units].sort((left, right) => left.order - right.order);
  const unitIds = new Set(units.map((unit) => unit.unit_id));
  const referencedNodeCount = new Set(units.flatMap((unit) => unit.node_ids)).size;

  return (
    <div
      className="frontstage-rollout-requirement-spine relative overflow-hidden rounded-md border border-slate-800 bg-slate-950 p-4 text-white xl:col-span-2"
      data-testid="frontstage-rollout-requirement-spine"
    >
      <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
            Requirement rollout spine
          </div>
          <h3 className="mt-2 max-w-3xl text-lg font-semibold leading-7 text-white">
            One demand unlocks the next
          </h3>
          <p className="mt-2 max-w-4xl text-sm font-medium leading-6 text-slate-300">
            {sequence.description}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info">{units.length} requirements</Badge>
          <Badge variant="success">{referencedNodeCount} public nodes</Badge>
        </div>
      </div>

      <div
        className="frontstage-rollout-spine-ribbon relative z-10 mt-5 grid gap-2 rounded-md border border-white/10 bg-black/25 p-2 lg:grid-cols-7"
        data-testid="frontstage-rollout-sequence-ribbon"
      >
        {units.map((unit, index) => (
          <div
            className="frontstage-rollout-sequence-chip grid min-h-16 grid-cols-[auto_minmax(0,1fr)] items-center gap-2 rounded-md border border-white/10 bg-white/[0.06] px-2 py-2"
            data-testid="frontstage-rollout-sequence-chip"
            key={unit.unit_id}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-cyan-300/30 bg-cyan-300/10 font-mono text-xs font-semibold text-cyan-100">
              {String(unit.order).padStart(2, "0")}
            </span>
            <span className="min-w-0 text-[11px] font-semibold leading-5 text-slate-200">
              {unit.requirement}
              {index < units.length - 1 ? <span className="ml-1 text-cyan-200">-&gt;</span> : null}
            </span>
          </div>
        ))}
      </div>

      <div className="frontstage-rollout-spine-track relative z-10 mt-3 grid gap-3 lg:grid-cols-4 2xl:grid-cols-7">
        {units.map((unit, index) => {
          const lane = projection.lanes.find((item) => item.lane_id === unit.lane_id);
          const nodes = unit.node_ids.map((nodeId) => byId.get(nodeId)).filter((node): node is RolloutProjectionNode => Boolean(node));
          const nextUnits = unit.unlocks.filter((unitId) => unitIds.has(unitId));
          return (
            <article
              className={cn(
                "frontstage-rollout-spine-card relative min-h-80 rounded-md border border-white/10 bg-white/[0.06] px-3 py-3",
                unit.state === "open" ? "ring-1 ring-cyan-300/50" : "",
              )}
              data-testid="frontstage-rollout-requirement-unit"
              key={unit.unit_id}
              style={{ animationDelay: `${index * 90}ms` }}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="frontstage-rollout-spine-order flex h-10 w-10 items-center justify-center rounded-md border border-cyan-300/30 bg-cyan-300/10 font-mono text-sm font-semibold text-cyan-100">
                  {String(unit.order).padStart(2, "0")}
                </span>
                <Badge variant={nodeStateTone(unit.state)}>{unit.state}</Badge>
              </div>
              <h4 className="mt-3 text-sm font-semibold leading-6 text-white">{unit.requirement}</h4>
              <p className="mt-2 text-xs font-medium leading-5 text-slate-400">
                Trigger: <span className="text-slate-200">{unit.triggered_by}</span>
              </p>
              <p className="mt-2 rounded-md border border-white/10 bg-black/20 px-2 py-2 text-xs font-medium leading-5 text-slate-300">
                {unit.outcome}
              </p>
              <div className="mt-3 flex min-h-10 flex-wrap gap-1.5">
                {nodes.map((node) => (
                  <a
                    className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/10 px-2 py-1 text-[11px] font-semibold text-slate-200 transition hover:border-cyan-300/50 hover:text-white"
                    href={node.url}
                    key={node.node_id}
                    rel="noreferrer"
                    target="_blank"
                    title={node.title}
                  >
                    {node.label}
                    <span className={cn("h-1.5 w-1.5 rounded-full", node.state === "merged" ? "bg-emerald-300" : node.state === "open" ? "bg-cyan-300" : "bg-amber-300")} />
                  </a>
                ))}
              </div>
              <div className="mt-3 grid gap-1.5">
                {unit.stage_steps.map((step) => (
                  <div
                    className="frontstage-rollout-spine-step grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-md border border-white/10 bg-black/20 px-2 py-1.5"
                    data-testid="frontstage-rollout-requirement-step"
                    key={step.step_id}
                  >
                    <span className="min-w-0 truncate text-[11px] font-semibold text-slate-300">{step.label}</span>
                    <Badge variant={sequenceStepTone(step.status)}>{step.status}</Badge>
                  </div>
                ))}
              </div>
              <div className="mt-3 grid gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 py-2 text-[11px] font-medium leading-5 text-slate-400">
                <span>
                  lane <span className="text-slate-200">{lane?.label ?? unit.lane_id}</span>
                </span>
                <span>
                  unlocks <span className="text-slate-200">{nextUnits.length ? nextUnits.map((unitId) => unitId.replace(/^req_/, "")).join(", ") : "next projection"}</span>
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function hotspotSeverityTone(severity: RolloutProjectionAttentionHotspot["severity"]): BadgeTone {
  if (severity === "high") {
    return "danger";
  }
  if (severity === "medium") {
    return "warning";
  }
  return "info";
}

function RolloutProjectionCapabilityMap({
  bundle,
  projection,
}: {
  bundle: RolloutProjectionBundle;
  projection: RolloutProjection;
}) {
  const layers = projection.mapping_layers ?? [];
  const signals = projection.flow_signals ?? [];
  const relationshipSummaries = projection.relationship_summaries ?? [];
  const hotspots = projection.attention_hotspots ?? [];

  return (
    <div
      className="frontstage-rollout-capability-map relative overflow-hidden rounded-md border border-slate-800 bg-slate-950 p-4 text-white xl:col-span-2"
      data-testid="frontstage-rollout-capability-map"
    >
      <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-emerald-200">
            Projection capability map
          </div>
          <h3 className="mt-2 max-w-3xl text-lg font-semibold leading-7 text-white">
            Evidence becomes state, lanes, edges, and operator decisions
          </h3>
          <p className="mt-2 max-w-4xl text-sm font-medium leading-6 text-slate-300">
            The renderer reads a generic projection contract, then makes the transformation visible: source facts become
            work nodes, nodes gain lifecycle state, lanes show parallel flow, edges explain why follow-up work exists, and
            hotspots keep review attention from getting lost.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="success">{bundle.projection_model.schema_version}</Badge>
          <Badge variant="info">{bundle.projection_model.optional_rich_sections?.length ?? 0} rich layers</Badge>
        </div>
      </div>

      <div className="frontstage-rollout-layer-rail relative z-10 mt-5 grid gap-3 lg:grid-cols-5">
        {layers.map((layer, index) => (
          <article
            className="frontstage-rollout-layer-card relative min-h-44 rounded-md border border-white/10 bg-white/[0.06] px-3 py-3"
            data-testid="frontstage-rollout-mapping-layer"
            key={layer.layer_id}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] font-semibold text-slate-500">{String(index + 1).padStart(2, "0")}</span>
              <Badge variant={layer.tone}>{layer.output}</Badge>
            </div>
            <h4 className="mt-3 text-sm font-semibold leading-6 text-white">{layer.label}</h4>
            <p className="mt-1 text-xs font-semibold uppercase tracking-normal text-cyan-200">{layer.role}</p>
            <p className="mt-2 text-xs font-medium leading-5 text-slate-300">{layer.description}</p>
            <div className="mt-3 grid gap-1 rounded-md border border-white/10 bg-black/20 px-2 py-2 text-[11px] font-medium leading-5 text-slate-400">
              <span>
                <span className="text-slate-500">in</span> {layer.input}
              </span>
              <span>
                <span className="text-slate-500">refs</span> {layer.node_ids.length} nodes / {layer.edge_ids.length} edges
              </span>
            </div>
          </article>
        ))}
      </div>

      <div className="relative z-10 mt-4 grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="rounded-md border border-white/10 bg-white/[0.04] p-3" data-testid="frontstage-rollout-flow-signals">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Flow signals</div>
            <Badge variant="neutral">{signals.length} signals</Badge>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {signals.map((signal) => (
              <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2" key={signal.signal_id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-white">{signal.label}</span>
                  <Badge variant={signal.tone}>{signal.value}</Badge>
                </div>
                <p className="mt-1 text-[11px] font-medium leading-5 text-slate-400">{signal.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-white/10 bg-white/[0.04] p-3" data-testid="frontstage-rollout-relationship-summaries">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Relationship grammar</div>
              <Badge variant="neutral">{relationshipSummaries.length} kinds</Badge>
            </div>
            <div className="mt-3 space-y-2">
              {relationshipSummaries.map((summary) => (
                <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2" key={summary.kind}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white">{summary.label}</span>
                    <Badge variant="info">{summary.count}</Badge>
                  </div>
                  <p className="mt-1 text-[11px] font-medium leading-5 text-slate-400">{summary.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-white/[0.04] p-3" data-testid="frontstage-rollout-attention-hotspots">
            <div className="flex items-center justify-between gap-2">
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-400">Attention hotspots</div>
              <Badge variant="warning">{hotspots.length} visible</Badge>
            </div>
            <div className="mt-3 space-y-2">
              {hotspots.map((hotspot) => (
                <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2" key={hotspot.hotspot_id}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white">{hotspot.label}</span>
                    <Badge variant={hotspotSeverityTone(hotspot.severity)}>{hotspot.severity}</Badge>
                  </div>
                  <p className="mt-1 text-[11px] font-medium leading-5 text-slate-400">{hotspot.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RolloutProjectionStageFlow({ projection }: { projection: RolloutProjection }) {
  return (
    <div
      className="rounded-md border border-slate-200 bg-white px-3 py-3 xl:col-span-2"
      data-testid="frontstage-rollout-stage-flow"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">
            Actor / state stages
          </div>
          <h3 className="mt-1 text-base font-semibold leading-7 text-slate-950">
            One node can move; many lanes can compose
          </h3>
        </div>
        <Badge variant="neutral">stage projection</Badge>
      </div>
      <div className="frontstage-rollout-stage-flow relative mt-4 grid gap-2 md:grid-cols-6">
        <span aria-hidden="true" className="frontstage-rollout-stage-flow-beam" />
        {projection.stages.map((stage, index) => (
          <div
            className={cn(
              "relative min-h-36 overflow-hidden rounded-md border px-3 py-3",
              stage.current
                ? "border-slate-900 bg-slate-950 text-white shadow-sm"
                : "border-slate-200 bg-slate-50 text-slate-950",
            )}
            data-testid="frontstage-rollout-stage"
            key={stage.stage_id}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md border text-xs font-semibold",
                  stage.current ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100" : "border-slate-200 bg-white text-slate-500",
                )}
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <Badge variant={trajectoryConfidenceTone(stage.confidence)}>{stage.confidence}</Badge>
            </div>
            <div className={cn("mt-3 text-sm font-semibold leading-6", stage.current ? "text-white" : "text-slate-950")}>
              {stage.label}
            </div>
            <p className={cn("mt-1 text-xs font-medium leading-5", stage.current ? "text-slate-300" : "text-slate-600")}>
              {stage.description}
            </p>
            {stage.current ? (
              <div className="mt-3 rounded-md border border-cyan-300/20 bg-cyan-300/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-normal text-cyan-100">
                current scene
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function RolloutProjectionLaneGraph({ projection }: { projection: RolloutProjection }) {
  const byId = nodesById(projection);

  return (
    <div
      className="grid gap-4 rounded-md border border-slate-200 bg-slate-50 p-3 xl:col-span-2 xl:grid-cols-[minmax(0,1fr)_minmax(320px,420px)]"
      data-testid="frontstage-rollout-lane-graph"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">
              Rollout lane graph
            </div>
            <h3 className="mt-1 text-base font-semibold leading-7 text-slate-950">
              Lanes keep throughput reviewable
            </h3>
          </div>
          <Badge variant="info">{projection.lanes.length} lanes</Badge>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {projection.lanes.map((lane, index) => {
            const tone = trajectoryLaneTone(index);
            const nodes = nodesForLane(projection, lane);
            return (
              <article
                className={cn("min-w-0 overflow-hidden rounded-md border px-3 py-3", tone.card)}
                data-testid="frontstage-rollout-lane"
                key={lane.lane_id}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">
                      {lane.role}
                    </div>
                    <h4 className="mt-1 text-sm font-semibold leading-6 text-slate-950">{lane.label}</h4>
                  </div>
                  <Badge variant="neutral">{nodes.length} nodes</Badge>
                </div>
                <p className="mt-2 text-xs font-medium leading-5 text-slate-600">{lane.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {nodes.map((node) => (
                    <a
                      className="inline-flex items-center gap-1 rounded-md border border-white/80 bg-white/80 px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:border-slate-300 hover:text-slate-950"
                      href={node.url}
                      key={node.node_id}
                      rel="noreferrer"
                      target="_blank"
                      title={node.title}
                    >
                      <span>{node.label}</span>
                      <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
                    </a>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </div>

      <div className="min-w-0 rounded-md border border-slate-900 bg-slate-950 p-3 text-white">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
              Review edge mesh
            </div>
            <p className="mt-1 text-sm font-semibold leading-6 text-white">
              Generic edges explain why one node points at another.
            </p>
          </div>
          <Badge variant="neutral">{projection.edges.length} edges</Badge>
        </div>
        <div className="frontstage-rollout-edge-list mt-3 space-y-2" data-testid="frontstage-rollout-edge-list">
          {projection.edges.map((edge, index) => {
            const fromNode = byId.get(edge.from_node_id);
            const toNode = byId.get(edge.to_node_id);
            return (
              <div
                className="frontstage-rollout-edge relative rounded-md border border-white/10 bg-white/[0.06] px-3 py-2"
                data-testid="frontstage-rollout-edge"
                key={edge.edge_id}
                style={{ animationDelay: `${index * 120}ms` }}
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="info">{fromNode?.label ?? edge.from_node_id}</Badge>
                  <span className="text-slate-500">-&gt;</span>
                  <Badge variant={toNode ? nodeStateTone(toNode.state) : "neutral"}>
                    {toNode?.label ?? edge.to_node_id}
                  </Badge>
                  <Badge variant={trajectoryConfidenceTone(edge.confidence)}>{edge.edge_kind}</Badge>
                </div>
                <p className="mt-2 text-xs font-medium leading-5 text-slate-300">{edge.label}</p>
                <div className="mt-1 grid gap-1 text-[11px] leading-5 text-slate-500">
                  <span className="truncate">{fromNode?.title ?? "upstream node"}</span>
                  <span className="truncate">{toNode?.title ?? "downstream node"}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function buildTrajectoryAnalysis(fixture: LongHorizonRolloutFixture) {
  const laneById = new Map(fixture.lanes.map((lane) => [lane.lane_id, lane]));
  const lastIndex = Math.max(1, fixture.animation_events.length - 1);
  const stages: TrajectoryStage[] = fixture.animation_events.map((event, index) => {
    const lane = laneById.get(event.lane_id);
    const transitionLabel = event.state_transition
      ? `${event.state_transition.from_state ?? "n/a"} -> ${event.state_transition.to_state ?? "n/a"}`
      : "state retained";
    return {
      animationEventId: event.animation_event_id,
      confidence: event.confidence,
      evidenceRefs: event.evidence_refs ?? [],
      inferenceReason: event.inference_reason,
      isCurrent: index === fixture.animation_events.length - 1,
      isSynthetic: event.confidence === "synthetic_bridge" || event.display_hint === "dashed_edge",
      kind: event.kind,
      laneLabel: lane?.display_name ?? event.lane_id,
      laneRole: lane?.profile_role ?? "peer",
      progress: Math.round((index / lastIndex) * 100),
      sourceEventIds: event.source_event_ids,
      stageLabel: rolloutStageLabel(event),
      title: event.title,
      transitionLabel,
    };
  });
  const currentStage = stages[stages.length - 1];
  const observedCount = stages.filter((stage) => stage.confidence === "observed").length;
  const syntheticCount = stages.filter((stage) => stage.isSynthetic).length;
  const evidenceItems = stages.flatMap((stage) => {
    const evidenceRefs = stage.evidenceRefs.map((ref) => ({
      eventTitle: stage.title,
      kind: "evidence_ref" as const,
      ref,
    }));
    const sourceEventIds = stage.sourceEventIds.map((ref) => ({
      eventTitle: stage.title,
      kind: "source_event" as const,
      ref,
    }));
    return [...evidenceRefs, ...sourceEventIds];
  });

  return {
    currentStage,
    evidenceItems,
    observedCount,
    stages,
    syntheticCount,
    verdict: syntheticCount
      ? "Projected handoff is visible; the next frontend patch should replace the bridge with commit-backed evidence."
      : "All rendered stages are observed and ready for the next projection-backed iteration.",
  };
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

type ManagementSurfaceCard = {
  body: string;
  icon: React.ComponentType<{ className?: string }>;
  id: string;
  label: string;
  source: string;
  value: string;
};

function FrontstageManagementSurfaceMock({
  claimOwners,
  claimedAgentTodos,
  openAgentTodos,
  openUserTodos,
  projection,
  quotaUsed,
}: {
  claimOwners: string[];
  claimedAgentTodos: number;
  openAgentTodos: number;
  openUserTodos: number;
  projection: GoalChannelProjection;
  quotaUsed: string;
}) {
  const firstGate = projection.open_gates[0];
  const latestEvent = projection.recent_events[0];
  const cards: ManagementSurfaceCard[] = [
    {
      body: projection.next_action,
      icon: LayoutDashboard,
      id: "mission",
      label: "Mission Bar",
      source: "goal_id + next_action",
      value: projection.display_name,
    },
    {
      body: claimOwners.length ? claimOwners.slice(0, 3).join(", ") : "No claimed owner projected.",
      icon: Users,
      id: "team",
      label: "Team Roster",
      source: "active_leases + claimed_by",
      value: `${claimOwners.length} visible agents`,
    },
    {
      body: `${openUserTodos} user todo, ${openAgentTodos} agent todo; ${claimedAgentTodos} claimed.`,
      icon: ListChecks,
      id: "tickets",
      label: "Ticket Board",
      source: "user_todos + agent_todos",
      value: `${openUserTodos + openAgentTodos} open tickets`,
    },
    {
      body: firstGate ? `${firstGate.kind} blocks ${(firstGate.blocks ?? []).join(", ") || "delivery"}.` : "No open gate in this projection.",
      icon: CircleAlert,
      id: "gates",
      label: "Gate Inbox",
      source: "decision_frame + open_gates",
      value: projection.decision_frame.user_action_required ? "decision visible" : "clear",
    },
    {
      body: `${artifactDisplayValue(projection.quota.spend_policy)}; state=${stringifyScalar(projection.quota.state)}.`,
      icon: Clock3,
      id: "cadence",
      label: "Cadence / Budget",
      source: "quota + scheduler hints",
      value: quotaUsed,
    },
    {
      body: latestEvent ? `${latestEvent.classification ?? "event"}: ${latestEvent.summary ?? latestEvent.generated_at ?? "recorded"}` : "No compact event projected.",
      icon: ShieldCheck,
      id: "evidence",
      label: "Evidence Timeline",
      source: "recent_events + artifacts",
      value: `${projection.recent_events.length} events`,
    },
  ];

  return (
    <Panel icon={LayoutDashboard} title="Management Surface Mock">
      <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="frontstage-management-surface-mock">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <section
              className="min-w-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-3"
              data-testid={`frontstage-management-${card.id}`}
              key={card.id}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-950">{card.label}</div>
                    <div className="truncate text-[11px] font-medium text-slate-500">{card.source}</div>
                  </div>
                </div>
                <Badge variant="neutral">kernel</Badge>
              </div>
              <div className="mt-3 break-words text-lg font-semibold leading-7 text-slate-950">{card.value}</div>
              <p className="mt-1 line-clamp-3 break-words text-xs font-medium leading-5 text-slate-600">{card.body}</p>
            </section>
          );
        })}
      </div>
    </Panel>
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

function TrajectoryAnalysisPanel() {
  const projection = overnightPrProjection;
  const nodeMap = nodesById(projection);
  const anchorNode = nodeMap.get(projection.source_contract.anchor_node_id);
  const currentProjectionStage = projection.stages.find((stage) => stage.current) ?? projection.stages.at(-1);
  const plannedProjection = rolloutProjectionBundle.planned_projections?.[0];

  return (
    <Panel icon={Activity} title="Trajectory Analysis">
      <div
        className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,420px)]"
        data-testid="frontstage-trajectory-analysis"
      >
        <RolloutProjectionConstellation bundle={rolloutProjectionBundle} projection={projection} />
        <RolloutRelationshipMesh projection={projection} />
        <RolloutRequirementSpine projection={projection} />
        <RolloutProjectionCapabilityMap bundle={rolloutProjectionBundle} projection={projection} />

        <div
          className="min-w-0 rounded-md border border-slate-900 bg-slate-950 p-4 text-white"
          data-testid="frontstage-trajectory-stage-curve"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
                Stage progress curve
              </div>
              <p className="mt-1 max-w-2xl text-sm font-semibold leading-6 text-white">
                The same projection model maps actor state, lane flow, and review edges without reading raw logs.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">read-only projection</Badge>
              <Badge variant="success">{projection.nodes.length} nodes</Badge>
              <Badge variant="neutral">{projection.edges.length} edges</Badge>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {projection.stages.map((stage, index) => (
              <div
                className="grid gap-2 sm:grid-cols-[104px_minmax(0,1fr)]"
                data-testid="frontstage-trajectory-stage"
                key={stage.stage_id}
              >
                <div className="flex min-h-10 items-center justify-between gap-2 text-xs font-semibold text-slate-300">
                  <span>{stage.actor_scope}</span>
                  <span className="font-mono text-slate-500">{String(index + 1).padStart(2, "0")}</span>
                </div>
                <div
                  className={cn(
                    "relative min-h-10 rounded-md border border-white/10 bg-white/[0.06] px-3 py-2",
                    stage.current ? "ring-1 ring-cyan-300/70" : "",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className="absolute bottom-0 left-0 top-0 rounded-md bg-cyan-300/15"
                    style={{ width: `${Math.max(12, ((index + 1) / projection.stages.length) * 100)}%` }}
                  />
                  <div className="relative z-10 flex min-w-0 flex-wrap items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-sm font-semibold text-white">{stage.label}</span>
                    <span className="flex flex-wrap gap-1.5">
                      <Badge variant={trajectoryConfidenceTone(stage.confidence)}>{stage.confidence}</Badge>
                      {stage.current ? <Badge variant="info">current</Badge> : null}
                    </span>
                  </div>
                  <div className="relative z-10 mt-1 text-xs font-medium leading-5 text-slate-300">
                    {stage.description}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3">
          <div
            className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3"
            data-testid="frontstage-trajectory-current-scene"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">{projection.projection_kind}</Badge>
              <Badge variant={trajectoryConfidenceTone(projection.scene.confidence)}>{projection.scene.confidence}</Badge>
            </div>
            <h3 className="mt-3 text-base font-semibold leading-7 text-slate-950">
              {projection.scene.stage_label}
            </h3>
            <p className="mt-1 text-sm font-medium leading-6 text-slate-700">
              {projection.scene.title}
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              {currentProjectionStage?.label ?? "No current stage"} / {projection.source_contract.sample_window}
            </p>
            <p className="mt-2 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium leading-5 text-slate-600">
              {projection.scene.why_current}
            </p>
          </div>

          <div
            className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-3"
            data-testid="frontstage-trajectory-stage-confidence"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">projection model</Badge>
              <Badge variant={trajectoryConfidenceTone(projection.scene.confidence)}>
                {projection.scene.confidence}
              </Badge>
            </div>
            <h3 className="mt-3 text-base font-semibold leading-7 text-slate-950">
              {projection.scene.stage_label}
            </h3>
            <p className="mt-1 text-sm font-medium leading-6 text-slate-700">
              {projection.scene.why_current}
            </p>
            <p className="mt-2 rounded-md border border-cyan-200 bg-white px-2 py-1.5 text-xs font-medium leading-5 text-slate-600">
              Anchor {anchorNode?.label ?? projection.source_contract.anchor_node_id}: {anchorNode?.role ?? "projection anchor"}.
            </p>
          </div>

          <div
            className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3"
            data-testid="frontstage-trajectory-verdict-card"
          >
            <div className="text-[11px] font-semibold uppercase tracking-normal text-amber-800">
              Verdict
            </div>
            <p className="mt-2 text-sm font-semibold leading-6 text-slate-950">
              {projection.source_contract.next_projection_hint}
            </p>
            <p className="mt-2 text-xs font-medium leading-5 text-amber-950">
              The renderer consumes only the projection bundle. Public GitHub metadata is enough for this batch; raw trajectories and local state stay outside the browser surface.
            </p>
          </div>
        </div>

        <RolloutProjectionStageFlow projection={projection} />
        <RolloutProjectionLaneGraph projection={projection} />

        <div
          className="rounded-md border border-slate-200 bg-white px-3 py-3 xl:col-span-2"
          data-testid="frontstage-trajectory-evidence-drawer"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">
                Evidence drawer
              </div>
              <p className="mt-1 text-xs font-medium leading-5 text-slate-600">
                Edges, model sections, and planned projections keep the rollout display explainable.
              </p>
            </div>
            <Badge variant="neutral">{projection.edges.length} edges</Badge>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {projection.edges.map((edge) => {
              const fromNode = nodeMap.get(edge.from_node_id);
              const toNode = nodeMap.get(edge.to_node_id);
              return (
              <div
                className="min-w-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
                key={edge.edge_id}
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="info">{edge.edge_kind}</Badge>
                  <Badge variant={trajectoryConfidenceTone(edge.confidence)}>{edge.confidence}</Badge>
                  <span className="truncate text-xs font-semibold text-slate-950">{edge.label}</span>
                </div>
                <div className="mt-1 break-words font-mono text-[11px] leading-5 text-slate-600">
                  {fromNode?.label ?? edge.from_node_id} -&gt; {toNode?.label ?? edge.to_node_id}
                </div>
              </div>
              );
            })}
            {plannedProjection ? (
              <div className="min-w-0 rounded-md border border-dashed border-slate-300 bg-white px-3 py-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="neutral">{plannedProjection.status}</Badge>
                  <span className="truncate text-xs font-semibold text-slate-950">{plannedProjection.projection_id}</span>
                </div>
                <div className="mt-1 text-xs font-medium leading-5 text-slate-600">{plannedProjection.reason}</div>
              </div>
            ) : null}
          </div>
        </div>
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

const todayValueWorkflows = [
  {
    workflow: "PR review/comment -> fix loop",
    output: "Branch-ready fix packet with repro, smoke result, and remaining review owner.",
    metric: "Fewer dropped review threads; faster path from comment to validated patch.",
    start: "/loopx fix this PR feedback",
  },
  {
    workflow: "Overnight PR-sized refactor",
    output: "Reviewable slice list, validation notes, successor todo, and merge boundary.",
    metric: "More merged commits without turning the next morning into a giant diff audit.",
    start: "/loopx split this refactor into reviewable slices",
  },
  {
    workflow: "P0 blocked -> safe fallback",
    output: "Kernel projection of the exact user gate, safe fallback todo, quota decision, and evidence boundary.",
    metric: "Less idle agent time while preserving human judgment on the blocked path.",
    start: "Appears inside an active /loopx goal when a concrete P0 gate blocks one lane and safe P1/P2 work remains.",
  },
];

function ExperimentalTodayValuePanel() {
  return (
    <Panel icon={ListChecks} title="Experimental Today Value Path">
      <div className="space-y-4 p-4" data-testid="frontstage-today-value-experiment">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">Pick one capability that earns value today</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              This lower-priority module does not replace the first screen. It gives evaluators three concrete
              LoopX capabilities with expected output and user-facing value metrics.
            </p>
          </div>
          <Badge variant="info">experimental</Badge>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {todayValueWorkflows.map((item) => (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4" key={item.workflow}>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">capability</div>
              <h4 className="mt-2 text-sm font-semibold leading-6 text-slate-950">{item.workflow}</h4>
              <div className="mt-3 space-y-3 text-xs font-medium leading-5 text-slate-600">
                <p>
                  <span className="font-semibold text-slate-950">Output: </span>
                  {item.output}
                </p>
                <p>
                  <span className="font-semibold text-slate-950">Value metric: </span>
                  {item.metric}
                </p>
                <code className="block rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[11px] text-slate-700">
                  {item.start}
                </code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

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
  const activeCaseHref = showcaseCaseHref(activeCase);
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

function rolloutKindTone(kind: string): BadgeTone {
  if (kind === "human_gate") {
    return "warning";
  }
  if (kind === "validation" || kind === "deliverable") {
    return "success";
  }
  if (kind === "handoff") {
    return "info";
  }
  if (kind === "synthetic_bridge") {
    return "neutral";
  }
  return "neutral";
}

function SelfIterationTimelinePanel() {
  const eventsByLane = new Map<string, RolloutAnimationEvent[]>();
  for (const event of selfIterationRollout.animation_events) {
    const laneEvents = eventsByLane.get(event.lane_id) ?? [];
    laneEvents.push(event);
    eventsByLane.set(event.lane_id, laneEvents);
  }

  const acceptance = selfIterationRollout.frontend_acceptance.must_render.slice(0, 4);
  const eventCount = selfIterationRollout.animation_events.length;

  return (
    <Panel icon={GitBranch} title="Self-Iteration Timeline">
      <div className="space-y-4 p-4" data-testid="frontstage-self-iteration-timeline">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-950">Three-lane control-plane story</h3>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              A public fixture turns LoopX self-iteration into visible peer lanes for release, product, and implementation validation, with human gates and evidence writeback kept explicit.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">{selfIterationRollout.lanes.length} agent lanes</Badge>
            <Badge variant="success">{eventCount} timeline events</Badge>
            <Badge variant="neutral">public fixture</Badge>
          </div>
        </div>

        <div className="rounded-md border border-slate-900 bg-slate-950 p-3 text-white">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-normal text-cyan-200">
                Public rollout fixture
              </div>
              <p className="mt-1 text-sm font-semibold leading-6 text-white">
                Human decisions change lane ownership; evidence makes the next run safe to resume.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {acceptance.map((item) => (
                <Badge key={item} variant="neutral">{item}</Badge>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-3">
          {selfIterationRollout.lanes.map((lane) => {
            const events = eventsByLane.get(lane.lane_id) ?? [];
            return (
              <article
                className="min-w-0 rounded-md border border-slate-200 bg-slate-50"
                data-testid="frontstage-self-iteration-lane"
                key={lane.lane_id}
              >
                <div className="border-b border-slate-200 bg-white px-3 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{lane.profile_role}</Badge>
                    <Badge variant="neutral">{lane.lane_id}</Badge>
                  </div>
                  <h4 className="mt-2 text-sm font-semibold leading-6 text-slate-950">{lane.display_name}</h4>
                  <p className="mt-1 break-words text-xs font-medium leading-5 text-slate-500">{lane.agent_id}</p>
                </div>
                <div className="space-y-2 p-3">
                  {events.map((event) => {
                    const isBridge = event.display_hint === "dashed_edge" || event.kind === "synthetic_bridge";
                    return (
                      <div
                        className={cn(
                          "rounded-md border bg-white px-3 py-2",
                          isBridge ? "border-dashed border-slate-300" : "border-slate-200",
                        )}
                        data-testid="frontstage-self-iteration-event"
                        key={event.animation_event_id}
                      >
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge variant={rolloutKindTone(event.kind)}>{event.kind}</Badge>
                          <Badge variant="neutral">{event.confidence}</Badge>
                        </div>
                        <div className="mt-2 text-sm font-semibold leading-6 text-slate-950">{event.title}</div>
                        {event.state_transition ? (
                          <div className="mt-1 text-xs font-medium leading-5 text-slate-600">
                            {event.state_transition.from_state ?? "n/a"} -&gt; {event.state_transition.to_state ?? "n/a"}
                          </div>
                        ) : null}
                        {event.human_effect?.decision_id ? (
                          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs font-medium leading-5 text-amber-950">
                            human gate: {event.human_effect.decision_id}
                          </div>
                        ) : null}
                        {isBridge ? (
                          <div data-testid="frontstage-self-iteration-dashed-bridge" className="mt-2 text-[11px] font-semibold uppercase tracking-normal text-slate-500">
                            inferred display bridge
                          </div>
                        ) : null}
                        {event.evidence_refs?.length ? (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {event.evidence_refs.slice(0, 2).map((ref) => (
                              <Badge key={ref} variant="success">{ref}</Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </div>

        <div
          className="grid gap-3 rounded-md border border-slate-200 bg-white px-3 py-3 text-xs font-medium leading-5 text-slate-600 md:grid-cols-3"
          data-testid="frontstage-self-iteration-truth-contract"
        >
          <div>
            <span className="font-semibold text-slate-950">Truth source: </span>
            {selfIterationRollout.truth_contract.event_ledger_is_source_of_truth ? "event ledger" : "fixture"}
          </div>
          <div>
            <span className="font-semibold text-slate-950">Projection: </span>
            {selfIterationRollout.truth_contract.projection_is_writable ? "writable" : "read-only"}
          </div>
          <div>
            <span className="font-semibold text-slate-950">Write authority: </span>
            {selfIterationRollout.truth_contract.write_authority}
          </div>
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
      <div className="space-y-3 p-4" data-testid="frontstage-showcase-cases" id="frontstage-showcase-cases">
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
            const caseHref = showcaseCaseHref(item);
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
    body: "Repository-writing peers move to independent worktrees so the canonical checkout stays protected from accidental edits.",
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
              ["workspace", "workspace_guard isolates peer writes from the canonical checkout"],
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
              href={showcaseCaseHref(item) ?? "#"}
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
      : "Loop engineering for long-running AI agents";
  const heroSubtitle = isOpsMode
    ? "Always-on agent operations, with human judgment kept in the control plane."
    : isDeveloperMode
      ? "Start the loop from one TUI message, then keep every gate visible."
      : "Public cases first. Live registry state stays behind explicit ops mode.";
  const heroBody = isOpsMode
    ? projection.next_action
    : isDeveloperMode
      ? "A contributor-facing path for install, status health, todo claims, workspace repairs, local server checks, and safe writeback."
      : "See how human gates, scoped agent lanes, and evidence writeback keep long-running work moving without leaking private status feeds.";
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
  const budgetGovernanceRows = [
    {
      label: "budget",
      value: quotaUsed,
      helper: `quota state: ${stringifyScalar(projection.quota.state)}`,
      tone: statusTone(stringifyScalar(projection.quota.state)),
    },
    {
      label: "cadence",
      value: stringifyScalar(projection.quota.scheduler_rrule ?? projection.quota.cadence_class ?? "scheduler hint"),
      helper: `reset token: ${stringifyScalar(projection.quota.scheduler_reset_token ?? "not projected")}`,
      tone: "info",
    },
    {
      label: "spend rule",
      value: stringifyScalar(projection.quota.spend_policy),
      helper: "Watch lanes stay monitor state; cadence changes, final checks, and monitor-only polls are no-spend.",
      tone: "success",
    },
    {
      label: "controls",
      value: stringifyScalar(projection.quota.override_policy ?? "preview gated"),
      helper: stringifyScalar(projection.quota.pause_policy ?? "writes require CLI or loopback opt-in"),
      tone: "warning",
    },
    {
      label: "evidence",
      value: stringifyScalar(projection.quota.latest_evidence_ref ?? projection.source_refs.latest_run_generated_at ?? "run history"),
      helper: "Audit through todo ids, run history, and quota spend events.",
      tone: "neutral",
    },
  ] satisfies Array<{ label: string; value: string; helper: string; tone: BadgeTone }>;

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
        className={cn(
          "frontstage-workspace-shell mx-auto grid gap-4",
          isOpsMode ? "max-w-[1500px] xl:grid-cols-[260px_minmax(0,1fr)_320px]" : "max-w-[1180px]",
        )}
        data-testid={isOpsMode ? "frontstage-ops-workspace-shell" : "frontstage-showcase-workspace-shell"}
      >
        {isOpsMode ? (
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
        ) : null}

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
                {isShowcaseMode ? (
                  <div className="mt-4 flex flex-wrap gap-2" data-testid="frontstage-public-cta-row">
                    <a
                      className="inline-flex items-center gap-2 rounded-md bg-slate-950 px-3 py-2 text-sm font-semibold text-white shadow-sm"
                      href="#frontstage-showcase-cases"
                    >
                      Explore cases
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                    <a
                      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm"
                      href="https://github.com/huangruiteng/loopx#quick-start"
                    >
                      Quick Start
                    </a>
                    <a
                      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm"
                      href="https://github.com/huangruiteng/loopx/issues"
                    >
                      Share feedback
                    </a>
                  </div>
                ) : null}
                {!isOpsMode ? (
                  <div
                    className="mt-4 flex flex-wrap items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium leading-5 text-emerald-950"
                    data-testid="frontstage-public-boundary-note"
                  >
                    <span>
                      {isDeveloperMode
                        ? "Developer mode ignores statusUrl and renders the public onboarding path only."
                        : "Showcase mode ignores statusUrl by design and renders docs/showcases only."}
                    </span>
                    {hasIgnoredStatusUrl ? <Badge variant="warning">statusUrl ignored</Badge> : null}
                    <span className="font-semibold text-emerald-800" data-testid="frontstage-ops-entry-hint">
                      Use mode=ops with statusUrl.
                    </span>
                  </div>
                ) : null}
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

          {isOpsMode ? (
            <FrontstageManagementSurfaceMock
              claimOwners={claimOwners}
              claimedAgentTodos={claimedAgentTodos}
              openAgentTodos={openAgentTodos}
              openUserTodos={openUserTodos}
              projection={projection}
              quotaUsed={quotaUsed}
            />
          ) : null}

          {!isDeveloperMode ? <EfficiencyEvidencePanel /> : null}

          {isShowcaseMode ? <TrajectoryAnalysisPanel /> : null}

          {isShowcaseMode ? <SelfIterationTimelinePanel /> : null}

          {!isDeveloperMode ? <ShowcaseMotionBoard /> : null}

          {!isDeveloperMode ? <ExperimentalTodayValuePanel /> : null}

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

              <Panel icon={BarChart3} title="Budget & Governance">
                <div className="grid gap-2 p-4 sm:grid-cols-2 xl:grid-cols-5" data-testid="frontstage-budget-governance">
                  {budgetGovernanceRows.map((row) => (
                    <div className="min-w-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-3" key={row.label}>
                      <div className="text-[11px] font-semibold uppercase tracking-normal text-slate-500">{row.label}</div>
                      <div className="mt-2 break-words text-sm font-semibold leading-6 text-slate-950">
                        {row.value}
                      </div>
                      <div className="mt-2">
                        <Badge variant={row.tone}>{row.helper}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </Panel>

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

        {isOpsMode ? (
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
        ) : null}
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
