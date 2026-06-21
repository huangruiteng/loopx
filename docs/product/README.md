# Product Direction

This folder keeps stable product-direction notes that are broader than one
runtime contract, benchmark route, or launch draft.

- [Product vision](vision.md): how Goal Harness grows from an engineering
  control plane into a human-friendly dynamic goal control plane for
  long-running agent work, including the creator-operator productization case.
- [Server-client product shape](server-client-product-shape.md): the medium-term
  product model where the server owns durable state, delivery/planning queue
  boundaries, and governed proposal promotion, the client acts as the user's
  intent proxy, and executor loops perform bounded work with evidence writeback.
- [Codex CLI TUI-first Goal Harness loop](codex-cli-tui-loop.md): the
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
- [Codex CLI no-clone release verification](codex-cli-no-clone-release-verification.md):
  the compact release note and smoke contract that prove the packaged installer,
  fresh-project bootstrap message, bootstrap bundle, and proof fixtures stay
  aligned before no-clone install is advertised as the default user path.
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
- [Agent profile contract](agent-profile-contract.md): the registry-owned
  identity/scope contract for primary and side agents, including worktree and
  review handoff policy, while keeping todo ownership in `claimed_by` and future
  leases.
- [Non-technical operator status model](nontechnical-operator-status-model.md):
  first-screen card model for people who need to understand agent progress,
  blockers, next moves, and feedback paths without reading logs or CLI output.
- [Reward-style replanning hints](reward-style-replanning.md): public-safe
  design for turning explicit reward, corrections, and steering feedback into
  compact candidate-ranking hints without raw chat, hidden profiling, or hard
  gate semantics.
- [Naming decision packet](naming-decision-packet.md): why the project should
  keep `Goal Harness` as the brand while testing `dynamic goal control plane`
  as category/tagline language.
