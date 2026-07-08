# Product Direction

This folder keeps stable product-direction notes that are broader than one
runtime contract, benchmark route, or launch draft.

- [Product vision](vision.md): how LoopX grows from an engineering
  control plane into a human-friendly dynamic goal control plane for
  long-running agent work, centered on Loop Agents, maintainer-first management,
  Agent Work Feed review, performance review, high-value open-source anchors,
  and office-operations connector showcases.
- [Core control-plane graphs](core-control-plane/README.md): the paired
  interaction catalog lens, state definitions, and state machine that keep
  product explanation, runtime projection, and validation aligned.
- [Decentralized auto-research showcase blueprint](decentralized-auto-research-showcase.md):
  Arbor-inspired but LoopX-native design for turning research hypotheses into
  todo-linked, agent-scoped, evidence-backed work without adding a single
  leader agent.
- [Auto-research command path](../guides/auto-research-command-path.md): the
  operator-facing path from a clean workspace to an inspectable visible
  multi-agent rehearsal, including artifacts, digital employees, progress
  checks, stop, and takeover controls.
- [Auto-research product metrics](auto-research-product-metrics.md):
  user-facing value metrics for auto research, including time to first scored
  attempt, useful hypotheses per day, held-out lift, negative-evidence reuse,
  retry recovery, and human promotion decisions required.
- [Server-client product shape](server-client-product-shape.md): the medium-term
  product model where the server owns durable state, signal inbox, selected
  anchors, delivery/planning queue boundaries, performance-review summaries,
  and governed proposal promotion, the client acts as the maintainer proxy, and
  executor loops perform bounded work with evidence writeback.
- [Codex CLI TUI-first LoopX loop](codex-cli-tui-loop.md): the
  first-class Codex CLI product contract where one TUI message starts the Goal
  Harness loop, later automation tries to steer the same visible session, and
  headless `codex exec` remains an explicit fallback rather than the default
  user experience.
- [Codex CLI packaged install path](codex-cli-packaged-install.md): the
  no-clone install/update/start route for Codex CLI users, with clone-plus-canary
  reserved for contributors.
- [Codex CLI first-run rehearsal](codex-cli-first-run-rehearsal.md): the concise
  fresh-user route that connects no-clone install, one-message TUI bootstrap,
  and proof-capture fixtures while keeping later same-TUI automation optional
  until visible proof passes.
- [Codex CLI live TUI first-message pilot](codex-cli-live-tui-first-message-pilot.md):
  the first real TUI launch attempt for the generated start message, recording
  why manual paste remains primary until a bounded visible completion proof
  exists.
- Codex CLI bounded visible pilot adapter: the public-safe packet command and
  `examples/codex-cli-bounded-visible-pilot-adapter-smoke.py` that validate
  first-response and runtime-idle fixtures before a live TUI bootstrap can be
  counted as successful.
- Codex CLI visible first-response capture plan: the copy-first packet command
  and `examples/codex-cli-visible-first-response-capture-plan-smoke.py` that
  tell an operator how to produce `public-first-response.json` and
  `public-runtime-idle.json` without argv prompt leakage or raw transcript
  reads.
- [Codex CLI no-clone release verification](codex-cli-no-clone-release-verification.md):
  the compact release note and smoke contract that prove the packaged installer,
  fresh-project bootstrap message, bootstrap bundle, and proof fixtures stay
  aligned before no-clone install is advertised as the default user path.
- [Release readiness](release-readiness.md): the v0.x maintainer mental model
  for install/update paths, compatibility smoke gates, release-note checklist,
  and safe-to-depend-on surfaces.
- [Public adoption loop](public-adoption-loop.md): a docs-first public feedback
  loop with issue/discussion template copy, triage labels, and lightweight
  external-attempt metrics before any `.github` template write scope is needed.
- [Frontstage dashboard interaction baseline](frontstage-dashboard-interaction-baseline.md):
  the two-surface frontend rule for keeping public showcase/homepage work fancy
  and case-driven while the real ops control-plane route stays dense, calm,
  read-only, and reviewable.
- [Frontend kernel-to-mental-model map](frontend-kernel-mental-model-map.md):
  interaction contract for compressing kernel concepts such as goals, gates,
  todos, claims, scope, evidence, run history, quota, and handoff into five
  user-facing concepts on the ops surface.
- [Codex CLI automation driver audit](codex-cli-automation-driver.md): the
  current Codex CLI scheduler/session surface audit, with a conservative local
  driver planner that keeps TUI bootstrap primary, composes quota/idle/fallback
  checks, validates visible-session proof fixtures, and treats `codex exec` as
  an explicit fallback.
- [Codex CLI visible proof capture protocol](codex-cli-visible-proof-capture-protocol.md):
  the opt-in public-safe procedure for turning `resume` / `remote-control`
  signals into evidence, with stop conditions that keep one-message TUI
  bootstrap primary until same-TUI visibility is proven.
- [Codex App control-plane hook/cache](codex-app-control-plane-hook-cache.md):
  experimental, default-off design boundary for a possible low-token Codex App
  control-plane snapshot, including freshness, privacy, evidence, rollout, and
  CLI fallback gates.
- [Codex CLI proof-capture demo](codex-cli-proof-capture-demo.md): public-safe
  sample fixtures and acceptance decisions for rehearsing the visible proof
  path without running Codex or reading session material.
- [Cross-runtime implement/review demo](cross-runtime-impl-review-demo.md):
  LoopX-native contract for a Claude Code implementation plus Codex review demo
  that maps implementer, reviewer, verifier, gates, evidence, and handoff onto
  normal LoopX todos and review packets.
- [Codex CLI TUI continuation priority](codex-cli-tui-continuation-priority.md):
  the current scheduling guard that keeps same-open-TUI continuation ahead of
  frontstage/showcase polish when both are runnable.
- [LoopX rename migration](loopx-rename-migration.md): the compatibility-first
  plan for moving product, CLI, install, docs, state paths, and GitHub repo
  naming from LoopX to LoopX.
- [Codex CLI same-open-TUI continuation observation](codex-cli-same-open-tui-continuation-observation.md):
  the live-session observation that one-message TUI bootstrap can continue
  visibly through the first guard and steering decision, while scheduled
  same-TUI attach stays blocked until proof and idle evidence pass.
- [Agent profile contract](agent-profile-contract.md): the registry-owned
  identity/scope contract for primary and side agents, including worktree and
  review handoff policy, while keeping todo ownership in `claimed_by` and future
  leases.
- [Non-technical operator status model](nontechnical-operator-status-model.md):
  first-screen Agent Work Feed and card model for people who need to review
  agent outputs, progress, blockers, next moves, signal inbox, anchor
  selection, performance review, and feedback paths without reading logs or CLI
  output.
- [Intelligent management surface](intelligent-management-surface.md):
  maintainer-first product design for signal inbox, selected anchors, agent
  lanes, review feed, and performance review so long-running Loop Agents can be
  evaluated by value, quality, cost, and user attention.
- [Presentation surface layout](presentation-surface-layout.md):
  repository boundary for frontend apps, display projections, renderers, sinks,
  capability facades, and value-connector separation.
- [Agent management observability MVP](agent-management-observability-mvp.md):
  read-only ops dashboard slice for registered agents, claimed todos, state
  badges, evidence/handoff links, quota/cadence hints, and workspace hints
  without introducing a dispatcher or second task runtime.
- [Complex request planning intake](complex-request-planning-intake.md):
  bounded intake pattern for turning a large mixed strategy request into a
  small typed todo batch with claim decisions, safe summaries, and a visible
  next proof slice.
- [Project-level reward model](project-level-reward-model.md): conservative
  value model for Loop Agents that separates quantity, quality, token cost, and
  user attention cost without turning one benchmark score into a universal
  product claim.
- [Loop Engineering principles and pitfalls](loop-engineering-principles-and-pitfalls.md):
  short public-safe digest of the operating rules behind source of truth, human
  gates, safe fallback, feedback, compact evidence, quota, and performance
  review. A Chinese version is available at
  [Loop Engineering 原则与常见坑](loop-engineering-principles-and-pitfalls.zh.md).
- [Beginner loop presets](beginner-loop-presets.md): recommendation matrix for
  turning lightweight loop-engineering starter patterns into LoopX-native
  beginner presets, opt-in L2 sweepers, readiness score, and README structure
  without adding a second state runtime.
- [Frontstage two-surface strategy](frontstage-two-surface-strategy.md): route,
  data-source, visual-freedom, validation, and roadmap boundaries between the
  public showcase/homepage surface and the real local ops control-plane
  surface.
- [Reward-style replanning hints](reward-style-replanning.md): public-safe
  design for turning explicit reward, corrections, and steering feedback into
  compact candidate-ranking hints without raw chat, hidden profiling, or hard
  gate semantics.
- [Domain capability packs](domain-capability-packs.md): why LoopX
  stays a generic control plane by default, how domain packs such as
  `ml_experiment` are detected but default-off, and which evidence/result
  protocols belong in the default surface versus an explicit pack.
- [Scenario capability gap map](scenario-capability-gap-map.md): compares the
  bottom-layer LoopX capability increments needed by repo issue-fix loops,
  creator/self-media operations, and other repository scenario signals before
  domain-specific adapters are built.
- [Office operations connector showcase](office-operations-connector-showcase.md):
  public-safe showcase design for connector observations, signal inbox,
  selected anchors, human review, gated external actions, and value metrics
  beyond raw content or draft count.
- [Issue/PR solver maintainer intake](issue-pr-solver-maintainer-intake.md):
  public-safe packet for deciding whether a repository issue or PR solver
  opportunity should become a high-value anchor, including repo fit, allowed
  actions, owner routing, evidence boundary, stop conditions, and showcase
  consent.
- [Issue/PR solver anchor coordination](issue-pr-solver-anchor-coordination.md):
  follow-up protocol for selected public issue/PR anchors, covering owner split,
  solver handoff, metric board, human gates, compact evidence, and showcase
  graduation.
- [content_ops_surface_v0](../reference/protocols/content-ops-surface-v0.md):
  compact creator/self-media operations state surface with source items,
  angle candidates, draft items, feedback signals, publish gates, material
  memory, and a public-safe projection/smoke contract.
- [Naming decision packet](naming-decision-packet.md): historical naming
  context before the LoopX rename.
