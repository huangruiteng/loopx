# Dashboard Frontend Selection

Goal Harness should keep the no-dependency static HTML renderer as a diagnostic
fallback, but the product dashboard should use a real frontend stack.

The target UI is a local control plane for agent goals: status lanes, run
history, contract health, controller handoffs, and drill-down views. It should
feel closer to an observability or orchestration console than to a generated
report.

## Product Benchmarks

The useful reference products cluster around five capabilities:

- AI observability tools such as Langfuse, LangSmith, and Braintrust emphasize
  trace/session inspection, eval comparison, filters, score summaries, prompt
  linkage, and production-to-eval loops.
- Orchestration tools such as Dagster and Temporal emphasize run lists, run
  detail pages, event histories, lineage, dependency graphs, and replayability.
- Monitoring tools such as Grafana emphasize composable panels, dashboard
  variables, transformations, links, and shareable views.

For Goal Harness, the common lesson is not "more charts." The first screen
needs an action-oriented queue and trustworthy drill-downs:

- at-a-glance health and attention lanes,
- filterable goal and run tables,
- URL-addressable status filters,
- run detail pages with compact JSON/Markdown links,
- event or timeline views for controller/sub-agent work,
- later graph views for goal dependencies and handoffs.

## Decision

Build the official dashboard as `apps/dashboard` with:

- **Vite + React + TypeScript** for a local-first single-page app that can read
  exported JSON and later call a small local API.
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
- **Zod** for validating `goal-harness --format json status` payloads at the UI
  boundary.
- **Vitest + Playwright** for component and browser-level checks.

The first implementation should load `examples/status.example.json`, render the
same data contract as the current static renderer, and prove the stack with a
real build. A later CLI command can serve or export the built dashboard.

## Why This Stack

Vite is a better fit than a server-first framework for the next milestone. Goal
Harness is local-first, and the dashboard can start as a static build that
reads JSON. Server rendering, auth, and hosted deployment are not yet product
requirements.

shadcn/ui is preferable to a heavy all-in component library because the
dashboard needs strong defaults but should still own the code. Goal Harness can
adapt cards, sidebars, tables, command menus, charts, and badges without
fighting a closed design system.

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
- **Use Grafana directly**: excellent for metrics dashboards, but Goal Harness
  needs an action queue and goal/run semantics rather than generic data-source
  panels.
- **Use Next.js now**: strong framework, but premature for a local static
  control plane with no server-side auth or hosted product surface.
- **Use Material UI / Ant Design as the primary system**: productive, but the
  defaults are less tailored to a compact agent-control dashboard and harder to
  make feel owned.
- **Build with Tailwind alone**: visually flexible, but slower to reach
  accessible menus, dialogs, tabs, tables, tooltips, and charts.

## UX Direction

The dashboard should be dense, calm, and operational:

- left navigation for goals, queue, runs, contract health, and settings;
- top controls for registry, runtime root, scan scope, and refresh state;
- first-screen lanes for user/controller, Codex-ready, external-watch, and
  blocking health;
- table-first drill-downs instead of oversized hero sections;
- subdued color with status accents, not a one-hue brand wash;
- light and dark modes from the beginning;
- no raw private evidence in public demo data.

## Next Implementation Segment

Scaffold `apps/dashboard` with the selected stack and render a first real
screen from `examples/status.example.json`:

- contract health summary,
- attention queue lanes,
- sortable queue table,
- goal/run counters,
- responsive desktop and mobile layout,
- `npm run build` and Playwright screenshot verification.

Keep `examples/render-status-dashboard.py` as a low-friction fallback until the
React dashboard can be built and opened in one command.

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
