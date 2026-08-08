# Session Dash Panel Design

Auto-generated single-page control panel that tracks agent session task
progress and result statistics from LoopX public-safe projections.

## Problem

Operators want a compact, copyable web view of **what the fleet is doing
right now**: which sessions (agent runtimes) exist, how many goals each owns,
and what state each goal is in. The existing React dashboard covers this
interactively, but it requires a Node build, a dev server, and browser
tooling. A loopback single-page panel is a lighter surface for quick local
inspection: run one command from the project directory and keep the tab open
while the agents work.

The panel is intentionally **human-focused**. LoopX's internal control
machinery (decision frames, work-lane contracts, quota slot math, truth
contracts, source-warning diagnostics, lease/write-scope bookkeeping) is not
rendered: it is noise to an operator and belongs to the control plane, not the
watch surface. The page shows only the signal that answers "how is the work
going?":

1. **Overview** — sessions, goals, active / needs-you / blocked / done
   buckets, open todos, and run counts (the result statistics).
2. **Sessions** — one card per session, with its state, role, goal count, and
   the goals it owns.
3. **Per goal** — status badge, todo progress bar (done vs open agent/user),
   what it is waiting on, latest run time/classification, and next action.

## Decision

Add a **live single-page panel** (`loopx dash`) that serves the fleet snapshot
from existing public-safe projections:

1. Collect the same inputs the dashboard already consumes: the status contract
   (`attention_queue.items[]`), `run_history.goals[]`, the todo index, the
   agent-management projection (sessions + their `goal_ids`), and the usage
   summary.
2. Fold them through a read-only fleet projection
   (`build_session_dash_projection`, schema `session_dash_projection_v1`) that
   groups goals under sessions and computes the overview buckets.
3. Render a single HTML page with a small no-dependency renderer, reusing the
   patterns in `loopx/presentation/renderers/goal_channel_html.py`.
4. Serve it from a loopback HTTP server (`loopx/dash_server.py`) that also
   exposes a `/panel` fragment and `/status.json` projection; the page
   auto-refreshes in place by polling `/panel`.
5. Keep `loopx dash generate` for a one-shot static HTML snapshot, with the
   existing public/private boundary scan enforced before success.

The React dashboard stays the interactive surface; the loopback panel is the
fast watch surface. They share the same projections and data contract, so the
panel cannot drift into a second source of truth.

## Repository Placement

| Concern | Location | Reason |
| --- | --- | --- |
| Renderer | `loopx/presentation/renderers/session_dash_html.py` | Pure renderer over already-built payloads, per the presentation surface layout. |
| Projection assembly | `loopx/presentation/projections/session_dash.py` | Intermediate public-safe read model (fleet snapshot). Reuse existing builders when possible; do not duplicate contract parsing. |
| Generation command | `loopx/cli_commands/dash.py` + `loopx/dash_server.py` | Operator-facing CLI entry (`loopx dash` serves, `dash generate` exports); reads status/quota/todos exactly like `serve-status` does. |
| Static export | Reuse the boundary scan + `loopx dash generate` | Existing public/private scanner; manifest/revision receipt stays with the static-site pipeline when needed. |
| Docs | `docs/product/surfaces/` + dashboard README | Same documentation home as other presentation surfaces. |
| Validation | `examples/session-dash-panel-smoke.py` | Public-safe fixture smoke, no live state required. |

This is a presentation surface, not a new capability: it does not own state,
quota, gates, or authority. Per the capability placement guide, it stays in the
presentation layer and reuses existing control-plane contracts.

## Data Contract (Inputs)

The projection consumes only public-safe projections:

- `loopx status` JSON, schema_version 2: `attention_queue.items[]` (per-goal
  waiting_on / recommended_action), `run_history.goals[]` (goal status,
  lifecycle phase, latest runs), `todo_index.items[]` (per-goal role/status),
  `agent_management_projection.agents[]` (sessions: state, role, `goal_ids`,
  next action, last activity), and `usage_summary.totals` (runs 24h/7d).
- Public-safe evidence pointers only; never raw transcripts, logs, credentials,
  or local paths.

Raw-looking keys found in inputs are recorded as boundary warnings without
copying values, matching `goal_channel_projection` behavior.

## Projection Shape

`schema_version: session_dash_projection_v1`, `mode: read_only`:

- `overview` — session/goal/run counts, `goals_by_status` buckets
  (active / needs_user / blocked / done / other), open agent/user todos, done
  todos, runs 24h/7d.
- `sessions[]` — one entry per agent runtime: `session_id`, `role`, `state`,
  `next_action`, `last_activity_at`, `goal_count`, and `goals[]`.
- `goals[]` — `goal_id`, `display_name`, `domain`, `status`, `status_bucket`,
  `waiting_on`, open/done todo counts, latest run time + classification, and
  `next_action`.
- `unassigned_goals[]` — goals no session declares, so nothing silently
  disappears from the operator's view.
- `focus_goal_id` — when `--goal-id` is passed, the snapshot narrows to
  sessions containing that goal.

## Page Layout (Single Page)

The single page renders these sections in order:

1. **Header**: panel title, generated-at time, read-only marker; a focus pill
   when `--goal-id` is set.
2. **Overview strip**: sessions, goals, active, needs-you, blocked, done, open
   todos, runs (24h).
3. **Session cards**: per session, its state badge, role, goal count, last
   activity, and next action; below it, a goal table with status badges,
   todo progress bars, waiting reason, latest run, and next action.
4. **Goals without a session** (when present): same goal table for goals no
   session claims.

All data is rendered from the projections above; the page contains no write
controls and no browser write authority.

## Command Surface

The primary entry point is a live server: run `loopx dash` inside a project
checkout and open the printed loopback URL in a browser. The single page
tracks the fleet's session task progress/status and refreshes itself in place
(default every 10s) by re-fetching the `/panel` fragment, so the operator can
keep the tab open while the agents work.

```bash
loopx dash                # serve the fleet panel at http://127.0.0.1:8767/
loopx dash --goal-id <id> # narrow the panel to one goal
loopx dash --port 9000 --refresh-seconds 5
```

Routes:

- `GET /` — full single-page panel with the in-place auto-refresh script.
- `GET /panel` — fresh `<main>` fragment for the refresh script.
- `GET /status.json` — the compact session dash projection as JSON.
- `GET /healthz` — health probe.

A one-shot static snapshot remains available:

```bash
loopx dash generate [--goal-id <id>] [--out dash.html]
```

- Without `--out`, print the HTML to stdout (or use `--format json` for the
  projection + html payload).
- With `--out`, write the file and run the public boundary scan before
  reporting success.
- The command is read-only: it never mutates todos, quota, gates, or registry.
- The server binds loopback only (`127.0.0.1`); it exposes no write routes.

## Public/Private Boundary

- Inputs are restricted to the status contract and public-safe projections.
- The renderer escapes all text and never inlines raw payload values.
- Static export reuses the existing boundary scanner (absolute local paths,
  private keys, credentials, tokens) before success.
- A negative fixture proves the generated page rejects private material; the
  smoke asserts the boundary, not the exact prose.

## Validation

`examples/session-dash-panel-smoke.py` (Python, no browser required):

1. Builds a public-safe fleet fixture (two goals, one session owning a second
   goal with finished todos).
2. Renders the page and asserts read-only markers, the overview + session
   panels, session -> goal grouping, progress bars, escaped output, the live
   refresh script, and the `/panel` fragment shape.
3. Asserts internal machinery (decision frame, work lane, truth contract,
   source warnings, leases) is absent from the page.
4. Injects synthetic private markers (`GH_FAKE_*` style) and asserts they stay
   out of the rendered page / static export.

## Out Of Scope (For Now)

- Browser write controls: the dashboard remains the only surface that may
  submit reward/control-plane drafts, and only through explicit loopback
  capability gates.
- New capability or provider: none. This is a renderer + CLI presentation
  surface over existing contracts.
- Goal-level drill-down inside the fleet panel: the per-goal channel details
  remain on the React dashboard; the loopback panel is the at-a-glance watch
  surface.
