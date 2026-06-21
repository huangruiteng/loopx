# Product Direction

This folder keeps stable product-direction notes that are broader than one
runtime contract, benchmark route, or launch draft.

- [Product vision](vision.md): how LoopX grows from an engineering
  control plane into a human-friendly dynamic goal control plane for
  long-running agent work, including the creator-operator productization case.
- [Server-client product shape](server-client-product-shape.md): the medium-term
  product model where the server owns durable state, delivery/planning queue
  boundaries, and governed proposal promotion, the client acts as the user's
  intent proxy, and executor loops perform bounded work with evidence writeback.
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
- [Frontstage dashboard interaction baseline](frontstage-dashboard-interaction-baseline.md):
  the two-surface frontend rule for keeping public showcase/homepage work fancy
  and case-driven while the real ops control-plane route stays dense, calm,
  read-only, and reviewable.
- [Codex CLI automation driver audit](codex-cli-automation-driver.md): the
  current Codex CLI scheduler/session surface audit, with a conservative local
  driver planner that keeps TUI bootstrap primary, composes quota/idle/fallback
  checks, validates visible-session proof fixtures, and treats `codex exec` as
  an explicit fallback.
- [Codex CLI visible proof capture protocol](codex-cli-visible-proof-capture-protocol.md):
  the opt-in public-safe procedure for turning `resume` / `remote-control`
  signals into evidence, with stop conditions that keep one-message TUI
  bootstrap primary until same-TUI visibility is proven.
- [Codex CLI proof-capture demo](codex-cli-proof-capture-demo.md): public-safe
  sample fixtures and acceptance decisions for rehearsing the visible proof
  path without running Codex or reading session material.
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
  first-screen card model for people who need to understand agent progress,
  blockers, next moves, and feedback paths without reading logs or CLI output.
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
- [Naming decision packet](naming-decision-packet.md): historical naming
  context before the LoopX rename.
