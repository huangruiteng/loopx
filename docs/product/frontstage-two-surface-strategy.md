# Frontstage Two-Surface Strategy

LoopX frontstage work has two different products sharing some dashboard
code. Treating them as one surface makes the next UI pass ambiguous: public
showcase pages want visual storytelling, while the real operator control plane
wants dense, local, stateful inspection. This note is the route and validation
contract to keep those jobs separate before more large UI changes.

## Decision

The frontstage family has two first-class surfaces:

| Surface | Job | Primary routes | Owner |
| --- | --- | --- | --- |
| Public showcase and homepage | Explain LoopX through public-safe cases, demos, animation, and product narrative. | `/frontstage`, hosted `/frontstage/`, future homepage entry points. | Product, outreach, and frontstage showcase work. |
| Real ops control plane | Help the operator inspect current goals, gates, todos, claims, quota, run history, and safe local actions. | `/`, `?view=ops`, `/frontstage?mode=ops&statusUrl=<relative-or-loopback>`. | Runtime, status contract, dashboard, and control-plane work. |

The public surface is the default when a URL can be copied or hosted. The ops
surface is explicit, local, and read-only unless a loopback server advertises a
separate capability such as reward dry-run or append preview.

## Route Ownership

`/frontstage` without `mode=ops` belongs to the public showcase surface. It
must ignore `statusUrl`, render bundled demo or showcase material, and remain
safe for GitHub Pages, Lark shares, screenshots, and public demos.

`/frontstage?mode=ops&statusUrl=...` belongs to local ops inspection. The
`statusUrl` must be relative or loopback. This route may read
`goal_channel_projection_v0` from a local `loopx serve-status` feed, but
it is not a public link and must not be used as hosted showcase material.

`/` is the operator home. It should answer the first-screen operational
questions for the shared LoopX registry: current goal, concrete user
gate, top user todo, top agent todo, quota or guard judgment, and recent
evidence. `?view=ops` remains the detailed workbench for debugging status
contracts, reward previews, and individual queue items.

`/frontstage/developer` is a read-only contributor cockpit. It belongs to the
frontstage developer-extension lane rather than the public homepage or live ops
surface: it renders static public contracts, projection diffing, fixture rules,
smoke checklists, and component examples so contributors can add projections
without mining the large dashboard page.

Compatibility aliases such as `view=share` may exist only as routing bridges.
They do not define a third product surface.

## Data Sources

The public showcase surface may read:

- `docs/showcases/showcase-catalog.json`;
- public case pages under `docs/showcases/`;
- public storyboards, animation prototypes, and generated static bundles;
- public assets that reveal the product model or a sanitized case.

The public showcase surface must not read:

- `.codex/goals`, `.loopx`, or `registry.global.json`;
- live `loopx status` exports;
- loopback `serve-status` feeds;
- raw run logs, transcripts, benchmark task text, trajectories, verifier tails,
  credentials, internal links, local paths, or unpublished project evidence.

The ops control-plane surface may read:

- `loopx --format json status`;
- `loopx serve-status --global-registry` or project-local
  `serve-status`;
- `goal_channel_projection_v0` and other versioned projections;
- run-bound reward preview data when the local server explicitly exposes it.

The ops surface should still default to read-only. Browser writes require a
loopback capability flag, dry-run validation first, and a local CLI-equivalent
contract. Public hosted bundles must not contain those capabilities.

## Visual Freedom

The public showcase surface can be expressive. It may use case-first
composition, kinetic lanes, motion, public product imagery, generated bitmap
assets, and strong narrative hierarchy. It should optimize for understanding:
what LoopX is, why long-running agent work needs a control plane, and
which public cases prove reusable behavior.

The ops surface should be quieter and denser. It should optimize for scanning,
comparison, repeated action, stale-daemon repair, and clear local boundaries.
It can still be polished, but decorative motion must not hide gate, quota,
todo, claim, or evidence state.

Public visual experiments must not depend on live state. Ops widgets must not
be promoted to public homepage content unless they have a sanitized fixture and
a public/private boundary check.

## Validation Boundaries

Public showcase changes should validate:

- catalog shape and case claims with `examples/showcase-catalog-smoke.py`;
- static prototype or animation contracts when changed;
- share/export privacy with `npm run smoke:frontstage-share-bundle`;
- Pages workflow safety with `examples/frontstage-pages-workflow-smoke.py`;
- public boundary scans with `loopx check` over changed docs/examples.

Ops control-plane changes should validate:

- status contract parsing and projection semantics;
- route gating with `npm run smoke:frontstage-route`;
- local server behavior when `serve-status` or reward preview APIs change;
- loopback-only status source rules;
- read-only defaults and explicit capability flags for any browser-triggered
  dry-run or append path.

Cross-surface changes must prove both sides when they touch shared code. The
minimum check is that showcase mode ignores `statusUrl`, ops mode accepts only
relative or loopback feeds, and exported public bundles do not carry live
registry state. Use
`examples/fixtures/frontstage-private-status-trap.public.json` as the
synthetic negative fixture: public showcase URLs and share bundles must not
render its `GH_FAKE_*` markers, while explicit ops-mode statusUrl loading may
render them during local inspection.

## Phased Roadmap

Phase 0, current foundation: keep `/frontstage` defaulting to public showcase
mode, keep ops mode explicit, and keep the operator home separate from hosted
showcase links.

Phase 1, public showcase polish: improve public case discovery, homepage
entry, animation/storytelling, share bundles, and visual assets from
`docs/showcases/showcase-catalog.json`. Do not add live status dependencies.

Phase 2, local ops data layer: graduate ops views toward a TanStack Query layer
over `serve-status`, with schema-version freshness checks, stale-daemon repair
copy, local capability projection, and relative or loopback source rules.

Phase 3, controlled local write affordances: add browser-assisted dry-run
previews only after the local server advertises a capability. Writes stay
loopback-only, preview-locked, CLI-equivalent, and opt-in.

Phase 4, optional separation: split routing or packages only if shared code
starts making ownership, bundle privacy, or validation boundaries harder to
maintain. Until then, one dashboard app can host both surfaces if this contract
stays enforced.

## Non-Goals

This strategy does not authorize a remote live status service, public ops-mode
URLs, hidden session reads, browser write authority by default, or marketing
claims without public evidence. It also does not change the Codex CLI/TUI loop
priority: the TUI bootstrap and visible continuation rules remain their own
product contract.
