# LoopX Documentation

This directory is intentionally split by audience. New contributors should be
able to find the stable product contracts without reading every research note,
incident report, or launch draft.

## Start Here

- [Project README](../README.md): product positioning, showcases, and the
  shortest quick start.
- [Getting started](guides/getting-started.md): agent-first start, manual
  installation, project connection, diagnosis, daily workflow, heartbeats,
  dashboard, development, and command reference.
- [Product vision](product/vision.md): long-term product direction and the
  creator-operator medium-term case.
- [Codex CLI TUI-first loop](product/codex-cli-tui-loop.md): first-class
  Codex CLI onboarding target where one visible TUI message starts Goal
  Harness, with session-attached automation as the preferred follow-up.
- [Codex CLI first-run rehearsal](product/codex-cli-first-run-rehearsal.md):
  shortest public route from no-clone install to one-message TUI bootstrap and
  proof-capture fixtures.
- [Architecture](architecture.md): core concepts and control-plane shape.
- [Integration guide](integration.md): how to connect a project to Goal
  Harness.
- [Showcases](showcases/README.md): public-safe cases, reproducible demos, and
  frontend-ready case metadata.
- [Benchmark developer workflow](benchmark-developer-workflow.md): how to run,
  observe, and ingest benchmark slices as a developer-facing product workflow.
- [State interaction model](state-interaction-model.md): user, agent, and state
  channel flow.
- [Heartbeat automation prompt](heartbeat-automation-prompt.md): current
  heartbeat prompt contract.
- [Quota allocation](quota-allocation.md): should-run and spend semantics.
- [Status data contract](status-data-contract.md): dashboard/status payload
  shape.
- [Public/private boundary](public-private-boundary.md): what may be committed,
  published, or retained.
- [Contributor tasks](../CONTRIBUTOR_TASKS.md): visible public work, sorted by
  complexity and ownership.

## Stable Reference

### Concepts

- [Architecture](architecture.md)
- [State interaction model](state-interaction-model.md)
- [Interaction pattern catalog](interaction-pattern-catalog.md)
- [Field-derived patterns](field-derived-patterns.md)
- [Public/private boundary](public-private-boundary.md)

### Operator Workflows

- [Getting started](guides/getting-started.md)
- [Integration guide](integration.md)
- [Benchmark developer workflow](benchmark-developer-workflow.md)
- [Attention queue](attention-queue.md)
- [Project agent todo contract](project-agent-todo-contract.md)
- [Authority source registration](authority-source-registration.md)
- [New-project Codex prompt](new-project-codex-prompt.md)

### Contracts

- [Status data contract](status-data-contract.md)
- [Interface budget contract](interface-budget-contract.md)
- [Host integration surface v0](reference/protocols/host-integration-surface-v0.md)
- [Reward gate direct-write contract](reward-gate-direct-write-contract.md)
- [Worker bridge install contract](worker-bridge-install-contract.md)
- [Dashboard reward write boundary](dashboard-reward-write-boundary.md)
- [Complex project read-only adapter](complex-project-readonly-adapter.md)
- [Protocol contracts](reference/protocols/README.md)

### Product Direction

- [Product vision](product/vision.md)
- [Codex CLI TUI-first loop](product/codex-cli-tui-loop.md)
- [Reward-style replanning hints](product/reward-style-replanning.md)
- [Frontstage channel and lease roadmap](frontstage-channel-lease-roadmap.md)
- [Long-task cadence policy](long-task-cadence-policy.md)
- [Dreaming exploration lane](dreaming-exploration-lane.md)
- [Session runtime control-plane adapter](session-runtime-control-plane-adapter.md)
- [Codex subagent orchestration](codex-subagent-orchestration.md)
- [Dashboard frontend selection](dashboard-frontend-selection.md)
- [Experiment controller milestone](experiment-controller-milestone.md)

### Research And Evidence

- [Showcases](showcases/README.md)
- [Long-horizon agent benchmark research](research/long-horizon-agent-benchmarks/README.md)

### Outreach And Narrative Drafts

- [Outreach index](outreach/README.md)

### Archive

- [Archive index](archive/README.md)

## Governance Rules

- Keep the `docs/` root for stable first-line product docs that contributors
  are expected to read or link from public surfaces.
- Put public-safe showcase cases, reproducible demos, and frontend-ready case
  metadata under `docs/showcases/`.
- Put benchmark dossiers, route packets, and publication planning under
  `docs/research/`.
- Put dated release-readiness packets, incident reports, and superseded
  decision records under `docs/archive/`.
- Put public launch, narrative, demo, and PR copy drafts under `docs/outreach/`.
- Put stable product-direction notes that cross individual contracts under
  `docs/product/`.
- Put machine-facing protocol contracts under `docs/reference/`.
- Every new doc should be linked from this index or from a subdirectory
  `README.md`. If it is not worth indexing, it probably belongs in local notes
  rather than the public repository.
- Prefer concise public summaries over raw logs, private trajectories, internal
  links, credentials, or local filesystem paths.
