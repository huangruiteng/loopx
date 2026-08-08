import { CircleAlert, Clock3, FileSearch, ShieldCheck } from "lucide-react";

import type { PresentationSurface, RunGoal } from "../data/status";
import type { DecisionResearchView } from "../data/decision-research";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

type BadgeVariant = "neutral" | "success" | "warning" | "info" | "danger";

const stateVariant: Record<string, BadgeVariant> = {
  blocked: "danger",
  empty: "neutral",
  failed: "danger",
  insufficient_evidence: "warning",
  invalid: "danger",
  partial: "warning",
  pending: "neutral",
  ready: "success",
  rejected: "danger",
  review_due: "warning",
  selected: "success",
  supported: "success",
  superseded: "neutral",
};

const toneVariant: Record<string, BadgeVariant> = {
  danger: "danger",
  info: "info",
  neutral: "neutral",
  success: "success",
  warning: "warning",
};

function StateBadge({ value }: { value: string }) {
  return <Badge variant={stateVariant[value] ?? "neutral"}>{value}</Badge>;
}

function TextList({ empty, items }: { empty: string; items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-slate-500 dark:text-zinc-400">{empty}</p>;
  }
  return (
    <ul className="space-y-2 text-sm leading-6 text-slate-700 dark:text-zinc-300">
      {items.map((item) => (
        <li
          className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900"
          key={item}
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function ProvenanceCard({ surface }: { surface: PresentationSurface }) {
  if (surface.state !== "ready" && surface.state !== "review_due") {
    return null;
  }
  return (
    <Card data-testid="decision-research-surface-summary">
      <CardHeader>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">{surface.title}</Badge>
            <StateBadge value={surface.state} />
            <Badge variant="neutral">{surface.visibility}</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
            Rendered from the published projection resolved by content-addressed
            reference. Core status remains a compact provider-neutral index.
          </p>
        </div>
        <FileSearch className="h-5 w-5 text-slate-400 dark:text-zinc-500" />
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
              View schema
            </dt>
            <dd className="mt-1 font-mono text-slate-800 dark:text-zinc-200">
              {surface.view_schema}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
              Generated at
            </dt>
            <dd className="mt-1 text-slate-800 dark:text-zinc-200">
              {surface.generated_at}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
              Extension revision
            </dt>
            <dd className="mt-1 font-mono text-slate-800 dark:text-zinc-200">
              {surface.detail_ref.extension_revision}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
              Payload SHA-256
            </dt>
            <dd
              className="mt-1 break-all font-mono text-xs text-slate-800 dark:text-zinc-200"
              data-testid="research-detail-ref-hash"
            >
              {surface.detail_ref.payload_sha256}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

export function DecisionResearchSurface({
  goals,
  surface,
  view = null,
  viewError = null,
  viewLoading = false,
}: {
  goals: RunGoal[];
  surface: PresentationSurface;
  view?: DecisionResearchView | null;
  viewError?: string | null;
  viewLoading?: boolean;
}) {
  if (surface.state === "invalid") {
    return (
      <Card data-testid="decision-research-surface">
        <CardHeader>
          <div>
            <CardTitle>{surface.title}</CardTitle>
            <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
              The active-revision projection failed safe validation.
            </p>
          </div>
          <StateBadge value="invalid" />
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-100">
            <div className="flex items-center gap-2 font-semibold">
              <CircleAlert className="h-4 w-4" />
              Projection unavailable
            </div>
            <p className="mt-2">{surface.diagnostic}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (surface.state === "empty") {
    return (
      <Card data-testid="decision-research-surface">
        <CardHeader>
          <div>
            <CardTitle>{surface.title}</CardTitle>
            <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
              {surface.empty_state_title}
            </p>
          </div>
          <StateBadge value="pending" />
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed border-slate-300 p-5 text-sm leading-6 text-slate-600 dark:border-zinc-700 dark:text-zinc-300">
            {surface.empty_state_detail}
          </div>
        </CardContent>
      </Card>
    );
  }

  const goalIsKnown = goals.some((goal) => goal.id === surface.goal_id);

  return (
    <div className="space-y-5" data-testid="decision-research-surface">
      {surface.state === "review_due" ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
          <div className="flex items-center gap-2 font-semibold">
            <Clock3 className="h-4 w-4" />
            Review due
          </div>
          <p className="mt-1">
            This projection remains published, but its declared review deadline has passed.
          </p>
        </div>
      ) : null}

      {!goalIsKnown ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
          The projection references goal <span className="font-mono">{surface.goal_id}</span>, which is not present in the current status goal list.
        </div>
      ) : null}

      {viewError ? (
        <div
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-100"
          data-testid="research-view-error"
        >
          <div className="flex items-center gap-2 font-semibold">
            <CircleAlert className="h-4 w-4" />
            Could not load the full research view
          </div>
          <p className="mt-1">{viewError}</p>
        </div>
      ) : null}

      {view === null ? (
        <>
          {viewLoading ? (
            <p
              className="text-sm text-slate-500 dark:text-zinc-400"
              data-testid="research-view-loading"
            >
              Loading the full research view…
            </p>
          ) : null}
          <ProvenanceCard surface={surface} />
        </>
      ) : (
        <>
          <section
            className="grid gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-950 shadow-sm dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100 sm:grid-cols-3"
            data-testid="research-first-screen-truth"
          >
            <div className="rounded-md border border-amber-200 bg-white/70 px-3 py-2 dark:border-amber-900 dark:bg-zinc-950/40">
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">
                Current adjudication
              </div>
              <div className="mt-1 text-base font-semibold">{view.adjudication.status}</div>
              <div className="mt-0.5 text-xs text-amber-800 dark:text-amber-200">
                {view.adjudication.label}
              </div>
            </div>
            {view.metrics.slice(0, 2).map((metric) => (
              <div
                className="rounded-md border border-amber-200 bg-white/70 px-3 py-2 dark:border-amber-900 dark:bg-zinc-950/40"
                key={metric.id}
              >
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">
                  {metric.label}
                </div>
                <div className="mt-1 text-base font-semibold">{metric.value}</div>
              </div>
            ))}
          </section>

          <Card id="executive-adjudication">
            <CardContent className="p-5">
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{surface.title}</Badge>
                    <StateBadge value={surface.state} />
                    <Badge variant="neutral">{view.adjudication.confidence} confidence</Badge>
                  </div>
                  <h2 className="mt-4 text-3xl font-semibold tracking-tight">
                    {view.identity.title}
                  </h2>
                  <p className="mt-2 text-base leading-7 text-slate-600 dark:text-zinc-300">
                    {view.identity.subtitle}
                  </p>
                  <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/40">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">
                      Current adjudication
                    </div>
                    <div className="mt-2 text-2xl font-semibold text-amber-950 dark:text-amber-100">
                      {view.adjudication.status}
                    </div>
                    <div className="mt-1 text-sm font-semibold text-amber-900 dark:text-amber-200">
                      {view.adjudication.label}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-amber-900 dark:text-amber-200">
                      {view.adjudication.summary}
                    </p>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500 dark:text-zinc-400">
                    <span>As of {view.identity.as_of}</span>
                    <span>Evidence cutoff {view.identity.evidence_cutoff}</span>
                    <span>Goal {surface.goal_id}</span>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  {view.metrics.map((metric) => (
                    <div
                      className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900"
                      key={metric.id}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold">{metric.label}</span>
                        <Badge variant={toneVariant[metric.tone] ?? "neutral"}>{metric.tone}</Badge>
                      </div>
                      <div className="mt-3 text-3xl font-semibold">{metric.value}</div>
                      <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
                        {metric.detail}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Research layers</CardTitle>
                <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
                  Ordered evidence layers preserve support, counterevidence, and failure conditions.
                </p>
              </div>
              <Badge variant="neutral">{view.layers.length}</Badge>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 lg:grid-cols-2">
                {view.layers.map((layer) => (
                  <article
                    className="rounded-lg border border-slate-200 p-4 dark:border-zinc-800"
                    key={layer.id}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="neutral">{layer.order}</Badge>
                        <h3 className="font-semibold">{layer.label}</h3>
                      </div>
                      <StateBadge value={layer.status} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-zinc-300">
                      {layer.summary}
                    </p>
                    <div className="mt-3">
                      <TextList empty="No compact evidence points." items={layer.evidence_points} />
                    </div>
                  </article>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4" data-testid="research-entities">
            {view.entities.map((entity) => (
              <Card key={entity.entity_id}>
                <CardHeader className="flex-wrap">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle>{entity.display_name}</CardTitle>
                      <Badge variant="neutral">{entity.symbol}</Badge>
                      <Badge variant="info">{entity.classification}</Badge>
                      <StateBadge value={entity.status} />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
                      {entity.inference}
                    </p>
                  </div>
                  <Badge variant="neutral">{entity.confidence} confidence</Badge>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-4 xl:grid-cols-2">
                    <section>
                      <h3 className="text-sm font-semibold">Observations &amp; evidence</h3>
                      <div className="mt-3 space-y-3">
                        {entity.observations.map((observation) => (
                          <div
                            className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800"
                            key={observation.id}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium">{observation.label}</span>
                              <Badge variant="neutral">{observation.kind}</Badge>
                            </div>
                            <div className="mt-2 text-lg font-semibold">{observation.value}</div>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs leading-5 text-slate-500 dark:text-zinc-400">
                              <span>{observation.as_of}</span>
                              <Badge variant="info">{observation.source_type}</Badge>
                              <span>{observation.confidence} confidence</span>
                              <span className="font-mono">evidence: {observation.source_ref}</span>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-rose-700 dark:text-rose-300">
                              Invalidation: {observation.invalidation}
                            </p>
                          </div>
                        ))}
                      </div>
                    </section>
                    <section>
                      <h3 className="text-sm font-semibold">Scenario estimates</h3>
                      <div className="mt-3 space-y-3">
                        {entity.scenario_estimates.map((scenario) => (
                          <div
                            className="rounded-lg border border-slate-200 p-3 dark:border-zinc-800"
                            key={scenario.scenario}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium">{scenario.label}</span>
                              <Badge variant="info">{Math.round(scenario.probability * 100)}%</Badge>
                            </div>
                            <div className="mt-2 text-lg font-semibold">{scenario.value}</div>
                            <div className="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                              Horizon {scenario.horizon}
                            </div>
                            <div className="mt-2">
                              <TextList empty="No assumptions projected." items={scenario.assumptions} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-3">
                    <section>
                      <h3 className="text-sm font-semibold">Counterevidence</h3>
                      <div className="mt-3">
                        <TextList empty="No counterevidence projected." items={entity.counterevidence} />
                      </div>
                    </section>
                    <section>
                      <h3 className="text-sm font-semibold">Thesis breakers</h3>
                      <div className="mt-3">
                        <TextList empty="No thesis breaker projected." items={entity.thesis_breakers} />
                      </div>
                    </section>
                    <section>
                      <h3 className="text-sm font-semibold">Next events</h3>
                      <div className="mt-3">
                        <TextList empty="No next event projected." items={entity.next_events} />
                      </div>
                    </section>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card data-testid="research-ledger">
            <CardHeader>
              <CardTitle>Research ledger</CardTitle>
              <Badge variant="neutral">{view.research_ledger.length}</Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              {view.research_ledger.map((entry) => (
                <article
                  className="rounded-lg border border-slate-200 p-4 dark:border-zinc-800"
                  key={entry.case_id}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-semibold">{entry.label}</h3>
                    <StateBadge value={entry.decision} />
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
                    {entry.summary}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {entry.gate_states.map((gate) => (
                      <Badge
                        key={gate.gate_id}
                        variant={stateVariant[gate.status] ?? "neutral"}
                      >
                        {gate.label}: {gate.status}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-mono text-slate-500 dark:text-zinc-400">
                    {entry.evidence_refs.map((ref) => (
                      <span
                        className="rounded border border-slate-200 px-2 py-1 dark:border-zinc-800"
                        key={ref}
                      >
                        evidence: {ref}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>

          <Card data-testid="research-artifacts">
            <CardHeader>
              <div>
                <CardTitle>Research artifacts</CardTitle>
                <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
                  Published research outputs with compact evidence lineage.
                </p>
              </div>
              <Badge variant="neutral">{view.artifacts.length}</Badge>
            </CardHeader>
            <CardContent>
              {view.artifacts.length ? (
                <div className="grid gap-3 lg:grid-cols-2">
                  {view.artifacts.map((artifact) => (
                    <article
                      className="rounded-lg border border-slate-200 p-4 dark:border-zinc-800"
                      key={artifact.artifact_id}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="font-semibold">{artifact.label}</h3>
                        <Badge variant="info">{artifact.kind}</Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
                        {artifact.summary}
                      </p>
                      <div className="mt-3 break-all rounded border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                        artifact: {artifact.artifact_ref}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 font-mono text-xs text-slate-500 dark:text-zinc-400">
                        {artifact.evidence_refs.map((ref) => (
                          <span
                            className="rounded border border-slate-200 px-2 py-1 dark:border-zinc-800"
                            key={ref}
                          >
                            evidence: {ref}
                          </span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500 dark:text-zinc-400">
                  No research artifact was published with this projection.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Event gates</CardTitle>
              <Badge variant="neutral">{view.event_gates.length}</Badge>
            </CardHeader>
            <CardContent className="grid gap-3 lg:grid-cols-2">
              {view.event_gates.map((event) => (
                <article
                  className="rounded-lg border border-slate-200 p-4 dark:border-zinc-800"
                  key={event.event_id}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="neutral">{event.event_id}</Badge>
                      <h3 className="font-semibold">{event.label}</h3>
                    </div>
                    <StateBadge value={event.status} />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-zinc-300">
                    {event.frozen_hypothesis}
                  </p>
                  <div className="mt-3 text-xs text-slate-500 dark:text-zinc-400">
                    {event.observation_window} · Next review: {event.next_review}
                  </div>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <section>
                      <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
                        Observables
                      </h4>
                      <div className="mt-2">
                        <TextList empty="No observables projected." items={event.observables} />
                      </div>
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
                        Current evidence
                      </h4>
                      <div className="mt-2">
                        <TextList empty="No current evidence yet." items={event.current_evidence} />
                      </div>
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700 dark:text-emerald-300">
                        Supports
                      </h4>
                      <div className="mt-2">
                        <TextList empty="No support condition projected." items={event.supports} />
                      </div>
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-rose-700 dark:text-rose-300">
                        Refutes
                      </h4>
                      <div className="mt-2">
                        <TextList empty="No refutation condition projected." items={event.refutes} />
                      </div>
                    </section>
                  </div>
                  <div className="mt-4">
                    <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-rose-700 dark:text-rose-300">
                      Thesis breakers
                    </h4>
                    <div className="mt-2">
                      <TextList empty="No thesis breaker projected." items={event.thesis_breakers} />
                    </div>
                  </div>
                </article>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSearch className="h-4 w-4" />
                  Method state
                </CardTitle>
                <Badge variant={view.method_state.active_method_changed ? "warning" : "success"}>
                  {view.method_state.lifecycle_state}
                </Badge>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-semibold">{view.method_state.summary}</div>
                <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
                  Revision {view.method_state.revision} · active_method_changed=
                  {String(view.method_state.active_method_changed)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Research boundary
                </CardTitle>
                <Badge variant="success">read-only</Badge>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <span>Research aid only: {String(view.boundary.research_aid_only)}</span>
                  <span>Investment advice: {String(view.boundary.investment_advice)}</span>
                  <span>Trading allowed: {String(view.boundary.trading_allowed)}</span>
                  <span>Private source content read: {String(view.boundary.private_source_content_read)}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <ProvenanceCard surface={surface} />
        </>
      )}
    </div>
  );
}

export function DecisionResearchDashboardSummaries({
  onSelect,
  surfaces,
}: {
  onSelect: (extensionId: string, surfaceId: string) => void;
  surfaces: PresentationSurface[];
}) {
  void onSelect;
  void surfaces;
  return null;
}
