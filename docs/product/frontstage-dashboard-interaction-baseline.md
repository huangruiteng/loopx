# Frontstage Dashboard Interaction Baseline

LoopX has two frontend jobs, and they should not collapse into one
layout.

The showcase surface sells the product model. The ops surface lets real users
work. They can share React components, icons, tokens, and public-safe fixtures,
but they should not share data defaults, information density, or motion rules.

## Surface Split

| Surface | Route posture | Primary job | Data source | Visual rule |
| --- | --- | --- | --- | --- |
| Showcase/homepage | Default `/frontstage` | Make the product feel obvious and compelling | `docs/showcases/showcase-catalog.json` plus sanitized share fixtures | Case-first, concise, animated, public-safe |
| Ops/control-plane | Explicit `mode=ops` | Help an operator scan, decide, and review long-running agent work | Relative or loopback `goal_channel_projection_v0` status feeds | Dense, calm, read-only, repeatable |

The default hosted or copied link must open the showcase surface. Live registry
state requires an explicit ops route and a loopback or relative status source.

## Product Direction

Use the Multica-style agent workspace direction as a product benchmark for
density and interaction grammar: visible agents, claimed work, boards, timelines,
search, filters, compact role state, and reusable workspace primitives. Do not
clone its product model. LoopX still treats quota, status, todos, gates,
leases, run history, and append-only evidence as the control-plane source of
truth.

The current stack is the baseline:

- React, Vite, TypeScript, and TanStack Router for a static-build-first app with
  URL-backed filters.
- TanStack Table when rows need real sorting, grouping, and column control.
- Tailwind plus owned shadcn/Base UI-like primitives for compact controls,
  badges, panels, command surfaces, and accessible interaction states.
- lucide-react for buttons, lane headers, and unfamiliar controls.
- Zod at the status boundary so public fixtures and local live feeds fail
  loudly instead of rendering ambiguous state.

## Showcase Rules

The showcase surface can be fancy because it is not an operator cockpit.

- Lead with public cases and the asynchronous agent operating model.
- Use motion to explain state flow: safe work moving, gates holding, evidence
  closing loops, and multiple agent lanes converging through one shared control
  plane.
- Render only public-safe showcase catalog fields and sanitized share fixtures.
- Keep local status exports, internal project labels, raw task ids, private
  screenshots, benchmark raw logs, and machine paths out of this surface.
- Link deeper reading to public GitHub showcase pages.

## Ops Rules

The ops surface should feel like a working console, not a landing page.

- Keep the first screen scannable: goal header, decision frame, quota guard,
  user todo lane, agent todo lane, claims, gates, artifacts, source warnings,
  and run timeline.
- Prefer rows, strips, filters, and compact panes over large hero sections.
- Preserve URL-backed search and lane filters so a review can reproduce the
  exact projected slice.
- Keep panels at 8px radius or less and avoid nested cards.
- Keep writes out of the route. Browser write authority belongs behind a
  separate local capability gate, not inside the read-only frontstage.
- Optimize for repeated use: stable dimensions, no horizontal overflow,
  responsive constraints, and reduced-motion fallbacks.

## Current Acceptance Anchors

The route currently exposes these durable anchors:

- `data-frontstage-surface="showcase-homepage"` for the public showcase mode.
- `data-frontstage-surface="ops-control-plane"` for the live ops mode.
- `frontstage-ops-workspace-shell` for the dense app shell.
- `frontstage-ops-command-strip` for search/filter/result-count controls.
- `frontstage-todo-search`, `frontstage-todo-lane-filter`, and
  `frontstage-todo-result-count` for reviewable todo projection slices.
- `frontstage-role-map`, `frontstage-active-claims`, `frontstage-open-gates`,
  `frontstage-artifacts`, and `frontstage-timeline` for the operator workspace.

`npm run smoke:frontstage-browser` remains the visual acceptance check for this
surface. It captures desktop and mobile screenshots, checks animated showcase
rails, verifies public/private boundary behavior, and exercises ops search,
lane filtering, goal selection, and loopback-source rejection.

`npm run smoke:frontstage-design-baseline` keeps this document, route anchors,
CSS shell classes, package scripts, and README entry points aligned.
