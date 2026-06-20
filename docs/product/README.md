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
- [Codex CLI automation driver audit](codex-cli-automation-driver.md): the
  current Codex CLI scheduler/session surface audit, with a conservative local
  driver planner that keeps TUI bootstrap primary, composes quota/idle/fallback
  checks, validates visible-session proof fixtures, and treats `codex exec` as
  an explicit fallback.
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
