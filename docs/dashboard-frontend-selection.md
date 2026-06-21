# Dashboard Frontend Selection

LoopX should keep the no-dependency static HTML renderer as a diagnostic
fallback, but the product dashboard should use a real frontend stack.

The target UI is a local control plane for agent goals: status lanes, run
history, contract health, controller handoffs, and drill-down views. It should
feel closer to an observability or orchestration console than to a generated
report.

## Product Benchmarks

The useful reference products cluster around three product surfaces:

- AI observability tools such as Langfuse, LangSmith, and Braintrust emphasize
  trace/session inspection, eval comparison, filters, score summaries, prompt
  linkage, and production-to-eval loops.
- Orchestration tools such as Dagster and Temporal emphasize run lists, run
  detail pages, event histories, lineage, dependency graphs, and replayability.
- Monitoring tools such as Grafana emphasize composable panels, dashboard
  variables, transformations, links, and shareable views.
- Work management tools such as Linear emphasize priority, cycle capacity,
  triage queues, and explicit pause/resume states instead of hiding compute
  allocation inside notification cadence.
- Modern developer products such as Vercel and Linear set the visual bar:
  restrained typography, sharp command surfaces, compact rows, calm contrast,
  strong empty states, and status accents rather than decorative color.
- Observability products such as Datadog and Grafana set the density bar:
  reusable widgets, health panels, filters, dashboard links, and drill-downs
  that turn a first screen into an operator cockpit.
- Multica is a useful near-neighbor for product shape, not for direct cloning:
  its public repo uses a Next.js web app, Go backend, PostgreSQL/pgvector,
  local agent daemon, shared UI package, Base UI/shadcn-style components,
  TanStack Query/Table, resizable panels, command menus, agent boards, agent
  profiles, runtimes, squads, task timelines, and reusable skill surfaces.
  LoopX should borrow the dense agent-board and workspace-member
  grammar while keeping the control-plane source of truth in LoopX
  status/quota/run history rather than in a chat or issue board.

For LoopX, the common lesson is not "more charts." The first screen
needs an action-oriented queue and trustworthy drill-downs:

- at-a-glance health and attention lanes,
- compute quota lanes that show which goals are eligible, throttled, waiting,
  paused, or asking for a burst,
- a human operator view that translates agent-facing status into review,
  approval, waiting, and reward-capture decisions,
- filterable goal and run tables,
- URL-addressable status filters,
- run detail pages with compact JSON/Markdown links,
- event or timeline views for controller/sub-agent work,
- later graph views for goal dependencies and handoffs.

## Decision

Build the official dashboard as `apps/dashboard` with a static-build-first
frontend:

- **Vite + React + TypeScript** for a local-first single-page app that can read
  exported JSON, build to static HTML/assets, and later call a small local API.
- **shadcn/ui + Tailwind CSS + Radix primitives + lucide-react** for a polished,
  accessible, owned component system with good defaults.
- **TanStack Router** for typed routes and URL-backed filters such as selected
  goal, queue lane, severity, and run id.
- **TanStack Table** for attention queues, run history, contract findings, and
  future child-agent tables.
- **TanStack Query** once the dashboard reads from a local HTTP endpoint instead
  of only loading static JSON files.
- **Recharts through shadcn chart patterns** for first-pass trend and summary
  panels.
- **Zod** for validating `loopx --format json status` payloads at the UI
  boundary.
- **Vitest + Playwright** for component and browser-level checks.

This means "static HTML dashboard" should not mean hand-written HTML forever.
The Python renderer remains the no-dependency diagnostic fallback. The product
dashboard should be a Vite static build with owned shadcn-style components and
typed data boundaries.

## Two Frontstage Surfaces

LoopX should keep two product surfaces separate even when they share the
same React app, visual tokens, and small components.

The **public showcase frontstage** is the homepage-style surface. It should be
catalog-driven, polished, animated, and concise. Its data source is
`docs/showcases/showcase-catalog.json` plus generated public-safe fixtures. It
must not read live registry state, local status exports, internal project
labels, raw task ids, raw benchmark material, screenshots from private tools,
or machine-specific paths. This surface can be more aggressive visually because
its job is to help new users feel the product value quickly.

The **real control-plane frontstage** is the user/operator workspace. It should
be denser, calmer, and more conservative: goal header, quota guard, user todo
lane, agent todo lane, claims, gates, artifacts, source warnings, and run
timeline. It may read live status only from relative or loopback URLs and stays
read-only until a separate local write capability is explicitly enabled. This
surface should optimize for correctness, scanability, and repeat use.

Do not blur these surfaces for convenience. A hosted or copied public link
should land in showcase mode. A live ops link should require an explicit
`mode=ops` route and a safe local status source. Shared UI primitives are fine;
shared live data defaults are not.

## Why This Stack

Vite is a better fit than a server-first framework for the next milestone. Goal
Harness is local-first, and the dashboard can start as a static build that
reads JSON. Server rendering, auth, and hosted deployment are not yet product
requirements.

shadcn/ui is preferable to a heavy all-in component library because the
dashboard needs strong defaults but should still own the code. LoopX can
adapt cards, sidebars, tables, command menus, charts, and badges without
fighting a closed design system.

The visual baseline should borrow from Vercel/Linear rather than generic admin
templates: a dark utility rail, quiet white or near-black work surfaces, 8px
cards, monospaced or tabular status values where useful, dense tables, and only
small status color accents.

TanStack Router and Table fit the shape of the data. The core UI states are
filters, search params, sort order, selected rows, and stable drill-down URLs,
not marketing pages.

Recharts is enough for the first dashboard because the immediate visualizations
are counts, history trends, and small comparisons. Custom graph work should be
added only when controller/sub-agent relationships need a dedicated graph view.

## Rejected Options

- **Keep extending the Python static renderer**: good for smoke tests and
  offline diagnostics, but it will become hard to maintain once filters, detail
  views, responsive layout, and accessible interactions matter.
- **Use Grafana directly**: excellent for metrics dashboards, but LoopX
  needs an action queue and goal/run semantics rather than generic data-source
  panels.
- **Use Next.js now**: strong framework, but premature for a local static
  control plane with no server-side auth or hosted product surface.
- **Use Material UI / Ant Design as the primary system**: productive, but the
  defaults are less tailored to a compact agent-control dashboard and harder to
  make feel owned.
- **Build with Tailwind alone**: visually flexible, but slower to reach
  accessible menus, dialogs, tabs, tables, tooltips, and charts.
- **Adopt a prebuilt admin template as the primary product**: fast initially,
  but the generic CRM/SaaS look would fight the LoopX model of queue,
  run history, contract health, and controller handoff.

## UX Direction

The dashboard should be dense, calm, and operational:

- left navigation for goals, queue, runs, contract health, and settings;
- top controls for registry, runtime root, scan scope, and refresh state;
- first-screen lanes for user/controller, Codex-ready, external-watch, and
  blocking health;
- a compact quota strip for compute quota, spent agent turns, and next
  eligible time;
- table-first drill-downs instead of oversized hero sections;
- subdued color with status accents, not a one-hue brand wash;
- light and dark modes from the beginning;
- no raw private evidence in public demo data.

## Current Implementation Segment

The first dashboard scaffold lives in `apps/dashboard`. It uses the selected
stack and renders a real screen from `examples/status.example.json`:

- contract health summary,
- contract health detail for errors, warnings, and successful checks,
- attention queue lanes,
- sortable queue table,
- goal/run counters,
- responsive desktop and mobile layout,
- `npm run build` verification.

Keep `examples/render-status-dashboard.py` as a low-friction fallback for
environments that cannot build the React app.

The first product-path `/frontstage` slice now exists in `apps/dashboard`: it
renders `attention_queue.items[].goal_channel_projection` as a read-only
channel board that makes a single goal feel like a managed workspace lane. It
shows the decision frame, quota guard, user todo lane, agent todo lane, active
claims, open gates, compact timeline, source warnings, URL-backed
selection/filter/search, and truth contract. This route is where Multica-style
agent-board density belongs; the existing Python/HTML renderer should stay a
no-build diagnostic fallback. The next slices should be quality work: visual
acceptance, richer public-safe fixtures, and operator onboarding details rather
than another base renderer.
The durable interaction baseline is tracked in
`docs/product/frontstage-dashboard-interaction-baseline.md`, including the
showcase/homepage versus ops/control-plane split.

## Sources Checked

- Langfuse observability docs: <https://langfuse.com/docs/observability/overview>
- Langfuse sessions docs: <https://langfuse.com/docs/sessions>
- LangSmith observability docs: <https://docs.langchain.com/langsmith/observability>
- LangSmith dashboards docs: <https://docs.langchain.com/langsmith/dashboards>
- Braintrust eval interpretation docs: <https://www.braintrust.dev/docs/guides/evals/interpret>
- Braintrust observability docs: <https://www.braintrust.dev/docs/observe>
- Grafana dashboards docs: <https://grafana.com/docs/grafana/latest/visualizations/dashboards/>
- Grafana dashboard variables docs: <https://grafana.com/docs/grafana/latest/visualizations/dashboards/variables/>
- Dagster docs: <https://docs.dagster.io/>
- Temporal docs: <https://docs.temporal.io/>
- Vite docs: <https://vite.dev/guide/why.html>
- shadcn/ui docs: <https://ui.shadcn.com/docs>
- TanStack Router docs: <https://tanstack.com/router/latest/docs/framework/react/guide/type-safety>
- TanStack Table docs: <https://tanstack.com/table/v7/docs/overview>
- Recharts docs: <https://recharts.github.io/>
- Vercel Geist design system: <https://vercel.com/geist/introduction>
- Linear changelog and interface direction: <https://linear.app/changelog>
- Datadog dashboard widgets docs: <https://docs.datadoghq.com/dashboards/widgets/>
- Multica public repo and README architecture section: <https://github.com/multica-ai/multica>
