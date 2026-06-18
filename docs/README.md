# Goal Harness Documentation

This directory is intentionally split by audience. New contributors should be
able to find the stable product contracts without reading every research note,
incident report, or launch draft.

## Start Here

- [Project README](../README.md): installation, quick start, smoke tests, and
  command reference.
- [Architecture](architecture.md): core concepts and control-plane shape.
- [Integration guide](integration.md): how to connect a project to Goal
  Harness.
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

- [Integration guide](integration.md)
- [Benchmark developer workflow](benchmark-developer-workflow.md)
- [Attention queue](attention-queue.md)
- [Project agent todo contract](project-agent-todo-contract.md)
- [Authority source registration](authority-source-registration.md)
- [New-project Codex prompt](new-project-codex-prompt.md)

### Contracts

- [Status data contract](status-data-contract.md)
- [Interface budget contract](interface-budget-contract.md)
- [Reward gate direct-write contract](reward-gate-direct-write-contract.md)
- [Worker bridge install contract](worker-bridge-install-contract.md)
- [Dashboard reward write boundary](dashboard-reward-write-boundary.md)
- [Complex project read-only adapter](complex-project-readonly-adapter.md)
- [Protocol contracts](reference/protocols/README.md)

### Product Direction

- [Frontstage channel and lease roadmap](frontstage-channel-lease-roadmap.md)
- [Long-task cadence policy](long-task-cadence-policy.md)
- [Dreaming exploration lane](dreaming-exploration-lane.md)
- [Session runtime control-plane adapter](session-runtime-control-plane-adapter.md)
- [Codex subagent orchestration](codex-subagent-orchestration.md)
- [Dashboard frontend selection](dashboard-frontend-selection.md)
- [Experiment controller milestone](experiment-controller-milestone.md)

### Research And Evidence

- [Long-horizon agent benchmark research](research/long-horizon-agent-benchmarks/README.md)

### Outreach And Narrative Drafts

- [Outreach index](outreach/README.md)

### Archive

- [Archive index](archive/README.md)

## Governance Rules

- Keep the `docs/` root for stable first-line product docs that contributors
  are expected to read or link from public surfaces.
- Put benchmark dossiers, case studies, route packets, and publication planning
  under `docs/research/`.
- Put dated release-readiness packets, incident reports, and superseded
  decision records under `docs/archive/`.
- Put public launch, narrative, demo, and PR copy drafts under `docs/outreach/`.
- Put machine-facing protocol contracts under `docs/reference/`.
- Every new doc should be linked from this index or from a subdirectory
  `README.md`. If it is not worth indexing, it probably belongs in local notes
  rather than the public repository.
- Prefer concise public summaries over raw logs, private trajectories, internal
  links, credentials, or local filesystem paths.
