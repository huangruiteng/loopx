# Goal Harness Showcases

This directory collects public-safe examples that explain where Goal Harness
helps and how the behavior can be reproduced or visualized.

Showcases are not raw run logs. Each case should reduce a real collaboration
into a reusable control-plane pattern:

- the situation before Goal Harness was useful;
- the Goal Harness behavior that changed the work loop;
- the user-facing value in plain language;
- the evidence boundary, including what must stay private;
- a reproducible demo or the reason a demo is still pending;
- optional data that a future website can render as a visual story.

The machine-readable catalog lives in
[showcase-catalog.json](showcase-catalog.json). Public docs and future frontend
surfaces should consume that file instead of scraping prose.
The first frontend surface contract lives in
[frontend-surface.md](frontend-surface.md).

The first static visual asset is the public-safe
[control-plane board](../assets/control-plane-board.svg), which shows a user
gate staying visible while a scoped side path continues through claimed todo,
quota guard, run history, and evidence writeback.
The first creator-operator storyboard is
[creator-ops-fake-data-storyboard.md](creator-ops-fake-data-storyboard.md).
Its feedback and source-status contract is
[creator-ops-feedback-boundary-contract.md](creator-ops-feedback-boundary-contract.md).
The first static frontstage prototype is generated from the catalog with
`python3 examples/showcase-frontstage-prototype.py --output /tmp/goal-harness-showcases.html`.

The dashboard frontstage now has a separate public-safe share-bundle path for
showing a live-looking control-plane board without exposing local state:

```bash
cd apps/dashboard
npm run export:frontstage-share
```

This writes `/tmp/goal-harness-frontstage-share-bundle` with the compiled
dashboard, a sanitized `goal_channel_projection_v0` status fixture, direct
`/frontstage/` static-route support, and a manifest. It is the foundation for a
future GitHub Pages showcase: Pages should publish this generated artifact, not
live registry files or local status exports.
Once repository Pages is enabled for GitHub Actions, the same generated bundle
is available as the
[hosted frontstage](https://huangruiteng.github.io/goal-harness/frontstage/).
That hosted route is intentionally case-first. It should help a new user or
developer understand the showcased patterns before reading CLI output: public
cases, efficiency evidence, and the public boundary come from this directory;
live local `statusUrl` feeds belong only to explicit ops-mode inspection.
For a short external walkthrough, use the
[frontstage demo script](../outreach/frontstage-demo-script.md).
For animated outreach assets, start from the
[showcase animation skill spike](../outreach/showcase-animation-skill-spike.md)
and the
[public storyboard artifact](showcase-animation-storyboard.json). Keep
`showcase-catalog.json` as the only case data source.

![Hosted Goal Harness frontstage showing public-safe showcase cases](../assets/frontstage-showcase-first-screen.png)

## Current Cases

| Case | Pattern | Status | Public Surface |
| --- | --- | --- | --- |
| [0617 blocked P0 with safe P1/P2 rotation](cases/0617-blocked-p0-safe-rotation.md) | Blocked priority fallback, concrete user gate, quota discipline | Reproducible synthetic demo | `python3 examples/showcase-0617-blocked-p0-safe-rotation-smoke.py` |
| [0619 dynamic workflow for hardware-agent development](cases/0619-dynamic-workflow-hardware-agent.md) | Dynamic workflow, multi-agent convergence, shared control plane | Redacted stub pending contributor detail | Public-safe narrative only |
| [0619 Goal Harness self-iteration loop](cases/0619-goal-harness-self-iteration.md) | Self-iteration, side-agent scope, evidence writeback | Public Git evidence case | Commit-backed narrative and workload signal |
| [0620 creator-operator long-running agent case](cases/0620-creator-operator-case-spec.md) | Creator-operator workflow, user gate, feedback capture, material library | Synthetic product case spec | [Fake-data storyboard](creator-ops-fake-data-storyboard.md), [feedback contract](creator-ops-feedback-boundary-contract.md) |

## Case Lifecycle

1. **Captured**: a real project shows a durable behavior pattern. Keep raw
   screenshots, private chats, and internal links outside this repo.
2. **Sanitized**: write a public-safe case card with the domain generalized,
   the evidence boundary explicit, and no private source material.
3. **Reproducible**: add a small synthetic demo or smoke that proves the
   reusable Goal Harness behavior without depending on private artifacts.
4. **Frontend-ready**: add or update the catalog fields needed for a visual
   website card, such as story beats, pattern tags, and suggested visual
   layout.

Cases can enter the catalog before they have a runnable demo, but their status
must say so clearly. A redacted stub should make a modest claim and name the
missing public evidence instead of filling gaps with speculation.

## Redaction Rules

Do not commit:

- private document or chat URLs;
- raw screenshots from internal tools;
- names of non-public users, teams, customers, or proprietary projects;
- local filesystem paths, task ids, credentials, raw traces, benchmark task
  text, or verifier output;
- claims about benchmark performance that are not backed by public compact
  evidence.

Do commit:

- generalized domain labels, such as `hardware-agent-development` or
  `benchmark-rotation`;
- reusable control-plane patterns, such as `concrete_user_gate`,
  `blocked_priority_fallback`, or `dynamic_workflow`;
- synthetic demos that exercise public Goal Harness contracts;
- explicit `evidence_boundary` notes that keep future authors honest.

## Future Frontend Shape

The catalog is intentionally small enough for a static website to render.
A good first website view would show:

- a card grid of cases grouped by pattern family;
- a visual timeline for each case: trigger, Goal Harness state, agent action,
  user decision, and outcome;
- a "try the demo" command when a case has a synthetic reproduction;
- a redaction badge when a case is a stub awaiting contributor details.

The frontend should use the catalog as the source of truth and link back to the
human-readable case pages for narrative context.
