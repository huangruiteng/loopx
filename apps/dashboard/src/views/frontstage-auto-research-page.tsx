import {
  ArrowRight,
  Bot,
  CheckCircle2,
  GitBranch,
  LayoutDashboard,
  Network,
  ShieldCheck,
  Sparkles,
  Target,
  Trophy,
} from "lucide-react";

import autoResearchBoardData from "../../../../docs/product/auto-research-frontstage-board.public.json";
import { Badge } from "../components/ui/badge";

type BoardTone = "neutral" | "success" | "warning" | "info" | "danger";

type BoardCommand = {
  label: string;
  command: string;
};

type BoardMetric = {
  label: string;
  value: string;
  baseline: string;
  interpretation: string;
  source: string;
};

type BoardLane = {
  role_id: string;
  display_name: string;
  agent_id: string;
  responsibility: string;
  produces: string[];
  does_not_own: string;
};

type BoardFrontierItem = {
  hypothesis_id: string;
  todo_id: string;
  mechanism_family: string;
  next_action?: string;
  allowed_action?: string;
  status?: string;
  why_selected?: string;
  blocked_by?: string;
  operator_value?: string;
};

type BoardEvidenceNode = {
  hypothesis_id: string;
  status: string;
  summary: string;
  best_dev_metric: number | null;
  best_holdout_metric: number | null;
  evidence_boundary: string;
};

type BoardEvidenceEdge = {
  from: string;
  to: string;
  label: string;
};

type BoardDecisionCandidate = {
  hypothesis_id: string;
  todo_id: string;
  decision: string;
  dev_metric?: string;
  holdout_metric?: string;
  requires?: string[];
  reason?: string;
  user_value?: string;
};

type BoardUserGate = {
  gate_id: string;
  decision_owner: string;
  purpose: string;
  trigger: string;
  takeover_action: string;
  public_evidence: string;
};

type BoardClaimBoundary = {
  schema_version: string;
  metric_source_kind: string;
  claim_source: string;
  live_claim_scope: string;
  dev_metric_present: boolean;
  holdout_metric_present: boolean;
  holdout_result_scope: string;
  holdout_claim_allowed: boolean;
  promotion_result_scope: string;
  promotion_claim_allowed: boolean;
  first_screen_claim_allowed: boolean;
  blocked_claims: string[];
};

type AutoResearchBoard = {
  schema_version: "auto_research_frontstage_board_v0";
  generated_at: string;
  surface: {
    id: string;
    title: string;
    subtitle: string;
    stage: string;
    positioning: string;
    public_boundary: string;
  };
  claim_boundary: BoardClaimBoundary;
  research_contract: {
    goal_id: string;
    objective: string;
    editable_scope: string[];
    protected_scope: string[];
    metric: {
      name: string;
      direction: string;
      baseline: string;
    };
    promotion_policy: string;
    commands: BoardCommand[];
  };
  value_metrics: BoardMetric[];
  lane_contract: {
    topology: string;
    anti_pattern: string;
    lanes: BoardLane[];
  };
  frontier: {
    agent_id: string;
    selected: BoardFrontierItem;
    runnable: BoardFrontierItem[];
    blocked: BoardFrontierItem[];
  };
  evidence_graph: {
    schema_version: string;
    goal_id: string;
    metric: {
      name: string;
      direction: string;
      baseline: number;
    };
    best_dev_metric: number | null;
    best_holdout_metric: number | null;
    holdout_improved: boolean;
    source_kind: string;
    nodes: BoardEvidenceNode[];
    edges: BoardEvidenceEdge[];
  };
  decision_candidates: {
    promotion_candidates: BoardDecisionCandidate[];
    retry_candidates: BoardDecisionCandidate[];
    retirement_candidates: BoardDecisionCandidate[];
  };
  user_gates: BoardUserGate[];
  showcase_projection: {
    schema_version: string;
    title: string;
    primary_claim: string;
    audience_takeaway: string;
    public_demo_path: string;
    next_product_step: string;
  };
  quality_gates: string[];
};

const board = autoResearchBoardData as AutoResearchBoard;

function statusTone(status: string): BoardTone {
  if (["supported", "promote_after_boundary_scan"].includes(status)) {
    return "success";
  }
  if (["active", "retry_with_executor_lane"].includes(status)) {
    return "info";
  }
  if (["contradicted", "retire_until_exactness_proof"].includes(status)) {
    return "warning";
  }
  return "neutral";
}

function metricValue(value: number | null) {
  return value === null ? "not scored" : `${value.toFixed(1)}x`;
}

function BoardPanel({
  children,
  eyebrow,
  title,
}: {
  children: React.ReactNode;
  eyebrow?: string;
  title: string;
}) {
  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950/80 shadow-sm">
      <div className="border-b border-zinc-800 px-5 py-4">
        {eyebrow ? (
          <div className="mb-2 font-mono text-xs font-semibold uppercase tracking-normal text-sky-300">{eyebrow}</div>
        ) : null}
        <h2 className="text-lg font-semibold text-zinc-50">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ValueMetrics() {
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4" data-testid="auto-research-value-metrics">
      {board.value_metrics.map((metric) => (
        <article className="rounded-lg border border-zinc-800 bg-zinc-950 p-4" key={metric.label}>
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-zinc-300">{metric.label}</div>
            <Trophy className="h-4 w-4 text-amber-300" />
          </div>
          <div className="mt-3 text-3xl font-semibold text-zinc-50">{metric.value}</div>
          <div className="mt-1 text-xs text-zinc-500">{metric.baseline}</div>
          <p className="mt-4 text-sm leading-6 text-zinc-400">{metric.interpretation}</p>
          <div className="mt-4 font-mono text-xs text-zinc-500">{metric.source}</div>
        </article>
      ))}
    </section>
  );
}

function ResearchContractPanel() {
  return (
    <BoardPanel eyebrow={board.research_contract.goal_id} title="Research Contract">
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-base leading-7 text-zinc-300">{board.research_contract.objective}</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-zinc-800 bg-zinc-900/70 p-3">
              <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Metric</div>
              <div className="mt-2 text-sm font-semibold text-zinc-100">{board.research_contract.metric.name}</div>
              <div className="mt-1 text-xs text-zinc-500">
                {board.research_contract.metric.direction} from {board.research_contract.metric.baseline}
              </div>
            </div>
            <div className="rounded-md border border-emerald-900/80 bg-emerald-950/20 p-3">
              <div className="text-xs font-semibold uppercase tracking-normal text-emerald-300">Editable</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {board.research_contract.editable_scope.map((item) => (
                  <Badge key={item} variant="success">{item}</Badge>
                ))}
              </div>
            </div>
            <div className="rounded-md border border-rose-900/80 bg-rose-950/20 p-3">
              <div className="text-xs font-semibold uppercase tracking-normal text-rose-300">Protected</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {board.research_contract.protected_scope.map((item) => (
                  <Badge key={item} variant="danger">{item}</Badge>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/60 p-3 text-sm leading-6 text-zinc-300">
            <span className="font-semibold text-zinc-100">Promotion policy: </span>
            {board.research_contract.promotion_policy}
          </div>
        </div>
        <div className="space-y-3" data-testid="auto-research-contract-commands">
          {board.research_contract.commands.map((command) => (
            <div className="rounded-md border border-zinc-800 bg-black/40 p-3" key={command.label}>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-normal text-sky-300">
                <Target className="h-3.5 w-3.5" />
                {command.label}
              </div>
              <code className="block whitespace-pre-wrap break-words font-mono text-xs leading-5 text-zinc-300">
                {command.command}
              </code>
            </div>
          ))}
        </div>
      </div>
    </BoardPanel>
  );
}

function LaneContractPanel() {
  return (
    <BoardPanel eyebrow={board.lane_contract.topology} title="Decentralized Lane Contract">
      <div className="mb-4 rounded-md border border-zinc-800 bg-zinc-900/70 p-3 text-sm leading-6 text-zinc-300">
        <span className="font-semibold text-zinc-100">Avoid: </span>
        {board.lane_contract.anti_pattern}
      </div>
      <div className="grid gap-3 lg:grid-cols-5" data-testid="auto-research-lane-contract">
        {board.lane_contract.lanes.map((lane) => (
          <article className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4" key={lane.role_id}>
            <div className="flex items-center justify-between gap-2">
              <Badge variant="info">{lane.role_id}</Badge>
              <Bot className="h-4 w-4 text-zinc-500" />
            </div>
            <h3 className="mt-3 text-base font-semibold text-zinc-50">{lane.display_name}</h3>
            <div className="mt-1 font-mono text-xs text-zinc-500">{lane.agent_id}</div>
            <p className="mt-3 text-sm leading-6 text-zinc-400">{lane.responsibility}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {lane.produces.map((item) => (
                <Badge key={item} variant="neutral">{item}</Badge>
              ))}
            </div>
            <p className="mt-4 text-xs leading-5 text-zinc-500">
              <span className="font-semibold text-zinc-400">Does not own: </span>
              {lane.does_not_own}
            </p>
          </article>
        ))}
      </div>
    </BoardPanel>
  );
}

function FrontierCard({ item, tone }: { item: BoardFrontierItem; tone: BoardTone }) {
  return (
    <article className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={tone}>{item.hypothesis_id}</Badge>
        <Badge variant="neutral">{item.todo_id}</Badge>
      </div>
      <div className="mt-3 text-sm font-semibold text-zinc-100">{item.mechanism_family}</div>
      <p className="mt-2 text-sm leading-6 text-zinc-400">
        {item.why_selected ?? item.next_action ?? item.operator_value ?? item.allowed_action ?? item.blocked_by}
      </p>
      {item.blocked_by ? (
        <div className="mt-3 font-mono text-xs text-amber-300">blocked_by={item.blocked_by}</div>
      ) : null}
    </article>
  );
}

function FrontierPanel() {
  return (
    <BoardPanel eyebrow={`agent ${board.frontier.agent_id}`} title="Per-Agent Frontier">
      <div className="grid gap-4 lg:grid-cols-3" data-testid="auto-research-frontier">
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <Sparkles className="h-4 w-4 text-sky-300" />
            Selected
          </div>
          <FrontierCard item={board.frontier.selected} tone="success" />
        </div>
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            Runnable
          </div>
          <div className="space-y-3">
            {board.frontier.runnable.map((item) => (
              <FrontierCard item={item} key={item.hypothesis_id} tone="info" />
            ))}
          </div>
        </div>
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-200">
            <ShieldCheck className="h-4 w-4 text-amber-300" />
            Blocked Or Claimed Elsewhere
          </div>
          <div className="space-y-3">
            {board.frontier.blocked.map((item) => (
              <FrontierCard item={item} key={item.hypothesis_id} tone="warning" />
            ))}
          </div>
        </div>
      </div>
    </BoardPanel>
  );
}

function EvidenceGraphPanel() {
  return (
    <BoardPanel eyebrow={board.evidence_graph.schema_version} title="Evidence Graph">
      <div className="mb-5 grid gap-3 md:grid-cols-3" data-testid="auto-research-evidence-summary">
        <div className="rounded-md border border-zinc-800 bg-zinc-900/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Best dev</div>
          <div className="mt-2 text-2xl font-semibold text-zinc-50">{metricValue(board.evidence_graph.best_dev_metric)}</div>
        </div>
        <div className="rounded-md border border-zinc-800 bg-zinc-900/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Best holdout</div>
          <div className="mt-2 text-2xl font-semibold text-zinc-50">
            {metricValue(board.evidence_graph.best_holdout_metric)}
          </div>
        </div>
        <div className="rounded-md border border-zinc-800 bg-zinc-900/70 p-3">
          <div className="text-xs font-semibold uppercase tracking-normal text-zinc-500">Source kind</div>
          <div className="mt-2 font-mono text-sm text-zinc-300">{board.evidence_graph.source_kind}</div>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-4" data-testid="auto-research-evidence-graph">
        {board.evidence_graph.nodes.map((node) => (
          <article className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4" key={node.hypothesis_id}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={statusTone(node.status)}>{node.status}</Badge>
              <Badge variant="neutral">{node.hypothesis_id}</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-zinc-300">{node.summary}</p>
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-md border border-zinc-800 bg-black/30 p-2">
                <div className="text-zinc-500">dev</div>
                <div className="mt-1 font-semibold text-zinc-100">{metricValue(node.best_dev_metric)}</div>
              </div>
              <div className="rounded-md border border-zinc-800 bg-black/30 p-2">
                <div className="text-zinc-500">holdout</div>
                <div className="mt-1 font-semibold text-zinc-100">{metricValue(node.best_holdout_metric)}</div>
              </div>
            </div>
            <p className="mt-4 text-xs leading-5 text-zinc-500">{node.evidence_boundary}</p>
          </article>
        ))}
      </div>
      <div className="mt-5 grid gap-2 md:grid-cols-2 xl:grid-cols-4" data-testid="auto-research-evidence-edges">
        {board.evidence_graph.edges.map((edge) => (
          <div className="flex items-center gap-2 rounded-md border border-zinc-800 bg-black/30 p-3" key={`${edge.from}-${edge.to}`}>
            <GitBranch className="h-4 w-4 shrink-0 text-zinc-500" />
            <div className="min-w-0 text-xs text-zinc-400">
              <span className="font-mono text-zinc-300">{edge.from}</span>
              <ArrowRight className="mx-1 inline h-3 w-3" />
              <span className="font-mono text-zinc-300">{edge.to}</span>
              <div className="mt-1">{edge.label}</div>
            </div>
          </div>
        ))}
      </div>
    </BoardPanel>
  );
}

function DecisionColumn({
  candidates,
  title,
}: {
  candidates: BoardDecisionCandidate[];
  title: string;
}) {
  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold text-zinc-200">{title}</div>
      {candidates.map((candidate) => (
        <article className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4" key={candidate.hypothesis_id}>
          <div className="flex flex-wrap gap-2">
            <Badge variant={statusTone(candidate.decision)}>{candidate.decision}</Badge>
            <Badge variant="neutral">{candidate.hypothesis_id}</Badge>
          </div>
          <div className="mt-3 font-mono text-xs text-zinc-500">{candidate.todo_id}</div>
          {candidate.dev_metric || candidate.holdout_metric ? (
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-md border border-zinc-800 bg-black/30 p-2">
                <div className="text-zinc-500">dev</div>
                <div className="mt-1 font-semibold text-zinc-100">{candidate.dev_metric ?? "not scored"}</div>
              </div>
              <div className="rounded-md border border-zinc-800 bg-black/30 p-2">
                <div className="text-zinc-500">holdout</div>
                <div className="mt-1 font-semibold text-zinc-100">{candidate.holdout_metric ?? "not scored"}</div>
              </div>
            </div>
          ) : null}
          <p className="mt-4 text-sm leading-6 text-zinc-400">{candidate.user_value ?? candidate.reason}</p>
          {candidate.requires ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {candidate.requires.map((item) => (
                <Badge key={item} variant="success">{item}</Badge>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function DecisionCandidatesPanel() {
  return (
    <BoardPanel eyebrow="promotion policy" title="Decision Candidates">
      <div className="grid gap-4 lg:grid-cols-3" data-testid="auto-research-decision-candidates">
        <DecisionColumn candidates={board.decision_candidates.promotion_candidates} title="Promotion" />
        <DecisionColumn candidates={board.decision_candidates.retry_candidates} title="Retry" />
        <DecisionColumn candidates={board.decision_candidates.retirement_candidates} title="Retire" />
      </div>
    </BoardPanel>
  );
}

function UserGatesPanel() {
  return (
    <BoardPanel eyebrow="human takeover" title="User Gates">
      <div className="grid gap-3 lg:grid-cols-4" data-testid="auto-research-user-gates">
        {board.user_gates.map((gate) => (
          <article className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4" key={gate.gate_id}>
            <div className="flex items-center justify-between gap-3">
              <Badge variant="warning">{gate.gate_id}</Badge>
              <ShieldCheck className="h-4 w-4 text-amber-300" />
            </div>
            <div className="mt-3 font-mono text-xs text-zinc-500">{gate.decision_owner}</div>
            <p className="mt-3 text-sm leading-6 text-zinc-300">{gate.purpose}</p>
            <div className="mt-4 rounded-md border border-zinc-800 bg-black/30 p-3 text-xs leading-5 text-zinc-400">
              <span className="font-semibold text-zinc-200">Trigger: </span>
              {gate.trigger}
            </div>
            <div className="mt-3 text-sm leading-6 text-zinc-400">
              <span className="font-semibold text-zinc-200">Takeover: </span>
              {gate.takeover_action}
            </div>
            <div className="mt-4 font-mono text-xs text-zinc-500">{gate.public_evidence}</div>
          </article>
        ))}
      </div>
    </BoardPanel>
  );
}

function ShowcaseProjectionPanel() {
  return (
    <BoardPanel eyebrow={board.showcase_projection.schema_version} title={board.showcase_projection.title}>
      <div className="grid gap-5 lg:grid-cols-[1fr_0.8fr]" data-testid="auto-research-showcase-projection">
        <div className="space-y-4">
          <p className="text-lg leading-8 text-zinc-200">{board.showcase_projection.primary_claim}</p>
          <p className="text-sm leading-6 text-zinc-400">{board.showcase_projection.audience_takeaway}</p>
          <div className="rounded-md border border-zinc-800 bg-black/30 p-3 text-sm leading-6 text-zinc-300">
            <span className="font-semibold text-zinc-100">Demo path: </span>
            {board.showcase_projection.public_demo_path}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <Network className="h-4 w-4 text-sky-300" />
            Quality Gates
          </div>
          <ul className="space-y-3">
            {board.quality_gates.map((gate) => (
              <li className="flex items-start gap-3 text-sm leading-6 text-zinc-400" key={gate}>
                <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-300" />
                {gate}
              </li>
            ))}
          </ul>
          <div className="mt-5 rounded-md border border-zinc-800 bg-black/30 p-3 text-sm leading-6 text-zinc-300">
            <span className="font-semibold text-zinc-100">Next: </span>
            {board.showcase_projection.next_product_step}
          </div>
        </div>
      </div>
    </BoardPanel>
  );
}

export function FrontstageAutoResearchPage() {
  return (
    <main className="min-h-screen bg-[#07080a] px-4 py-5 text-zinc-100 sm:px-6" data-testid="frontstage-auto-research-board">
      <div className="mx-auto grid max-w-[1500px] gap-5">
        <section className="rounded-xl border border-zinc-800 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.16),_transparent_34%),#0b0d12] p-5 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{board.surface.stage}</Badge>
            <Badge variant="neutral">{board.schema_version}</Badge>
            <Badge variant="success">public-safe projection</Badge>
          </div>
          <div className="mt-6 grid gap-5 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
            <div>
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-normal text-sky-300">
                <LayoutDashboard className="h-4 w-4" />
                Auto Research Frontstage
              </div>
              <h1 className="max-w-4xl text-4xl font-semibold leading-tight text-zinc-50 md:text-5xl">
                {board.surface.title}
              </h1>
              <p className="mt-4 max-w-4xl text-lg leading-8 text-zinc-300">{board.surface.positioning}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-black/30 p-4 text-sm leading-6 text-zinc-400">
              <div className="mb-2 flex items-center gap-2 font-semibold text-zinc-100">
                <ShieldCheck className="h-4 w-4 text-emerald-300" />
                Boundary
              </div>
              {board.surface.public_boundary}
            </div>
          </div>
        </section>

        <ValueMetrics />
        <ResearchContractPanel />
        <LaneContractPanel />
        <FrontierPanel />
        <EvidenceGraphPanel />
        <DecisionCandidatesPanel />
        <UserGatesPanel />
        <ShowcaseProjectionPanel />
      </div>
    </main>
  );
}
