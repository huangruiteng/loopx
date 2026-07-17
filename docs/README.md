# LoopX Documentation

This directory is intentionally split by audience. New contributors should be
able to find the stable product contracts without reading every research note,
incident report, or launch draft.

## Start Here

- [Project README](../README.md): product positioning, showcases, and the
  shortest quick start.
- [User manual (Feishu/Lark)](https://my.feishu.cn/wiki/CaL5wMk9ui17ngkWzeUcMlAYnZg):
  public onboarding guide with Quick Start, product/technical concepts, FAQ,
  and selected cases.
- [Getting started](guides/getting-started.md): agent-first start, manual
  installation, project connection, diagnosis, daily workflow, heartbeats,
  dashboard, development, and command reference.
- [Newcomer command path](guides/newcomer-command-path.md): the minimal product
  path for `/loopx`, `/loopx <goal>`, and one CLI quickstart before the full
  command catalog.
- [Auto-research command path](guides/auto-research-command-path.md): the
  shortest visible route from a clean workspace to an inspectable multi-agent
  auto-research rehearsal with stop and takeover controls.
- [Multi-agent product recipe](guides/multi-agent-product-recipe.md): the
  product-author path for keeping both user config and product presets thin
  while the generic kernel owns runner, TUI, tick, status, and host controls.
- [Product vision](product/vision.md): long-term product direction, Loop Agent
  definition, maintainer-first management surface, and open-source anchor
  strategy.
- [Core control-plane graphs](product/core-control-plane/README.md): the
  interaction catalog lens, state definitions, and state machine in one
  product/runtime map.
- [Public adoption loop](product/public-adoption-loop.md): docs-first issue
  and discussion template copy, triage labels, and lightweight external-attempt
  metrics before any `.github` template write.
- [Codex CLI TUI-first loop](product/codex-cli-tui-loop.md): first-class
  Codex CLI onboarding target where one visible TUI message starts LoopX, with
  session-attached automation as the preferred follow-up.
- [Codex CLI first-run rehearsal](product/codex-cli-first-run-rehearsal.md):
  shortest public route from no-clone install to one-message TUI bootstrap and
  proof-capture fixtures.
- [Architecture](architecture.md): core concepts and control-plane shape.
- [Integration guide](integration.md): how to connect a project to LoopX,
  including public-safe Lark or Feishu reply card payloads.
- [Showcases](showcases/README.md): public-safe cases, reproducible demos, and
  frontend-ready case metadata.
- [Update notes](update-notes/README.md): two-week public progress notes,
  archive governance, and publication automation design.
- [Release readiness](product/release-readiness.md): v0.x install/update paths,
  compatibility smoke gate, release-note checklist, and safe-to-depend-on
  surfaces.
- [Benchmark developer workflow](benchmark-developer-workflow.md): how to run,
  observe, and ingest benchmark slices as a developer-facing product workflow.
- [Developer guide](development/README.md): the contributor entry point for
  architecture, validation, public boundaries, and release contracts.
- [Control-plane developer course](development/control-plane-course/README.md):
  eight Chinese lectures that follow the real CLI, state transitions, core
  functions, smokes, and extension seams from first loop to multi-agent use.
- [Testing and quality](development/testing-and-quality.md): the bilingual
  quality stack from unit contracts and public smokes through canary, CLI
  output budgets, decision replay, low-frequency model behavior, and release
  outcome baselines.
- [State interaction model](state-interaction-model.md): user, agent, and state
  channel flow.
- [Heartbeat automation prompt](heartbeat-automation-prompt.md): current
  heartbeat prompt contract.
- [Runtime connector catalog](runtime-connector-catalog.md): public v0 catalog
  for Codex App, Codex CLI TUI, Claude Code loop, shell, HTTP, and worker
  bridge connectors.
- [Quota allocation](quota-allocation.md): should-run and spend semantics.
- [Dashboard budget governance](dashboard-budget-governance-contract.md):
  operator-facing budget, cadence, controls, and evidence mapping for the ops
  frontstage.
- [Status data contract](status-data-contract.md): dashboard/status payload
  shape.
- [Public/private boundary](public-private-boundary.md): what may be committed,
  published, or retained.
- [Contributor tasks](../CONTRIBUTOR_TASKS.md): visible public work, sorted by
  complexity and ownership.
- [Project governance](../GOVERNANCE.md), [authors and contributors](../AUTHORS.md),
  [project history](project/history.md), and [name and marks](../TRADEMARKS.md):
  maintainer authority, public attribution, evidence-backed milestones, and
  community identity guidance.

## Stable Reference

### Concepts

- [Architecture](architecture.md)
- [Core control-plane graphs](product/core-control-plane/README.md)
- [State interaction model](state-interaction-model.md)
- [Interaction pattern catalog](interaction-pattern-catalog.md)
- [Field-derived patterns](field-derived-patterns.md)
- [Public/private boundary](public-private-boundary.md)

### Operator Workflows

- [Getting started](guides/getting-started.md)
- [Newcomer command path](guides/newcomer-command-path.md)
- [Auto-research command path](guides/auto-research-command-path.md)
- [Multi-agent product recipe](guides/multi-agent-product-recipe.md)
- [Integration guide](integration.md)
- [Benchmark developer workflow](benchmark-developer-workflow.md)
- [Attention queue](attention-queue.md)
- [Project agent todo contract](project-agent-todo-contract.md)
- [Lark Kanban control-plane adapter](lark-kanban-control-plane-adapter.md)
- [Authority source registration](authority-source-registration.md)
- [New-project Codex prompt](new-project-codex-prompt.md)

### Developer Workflows

- [Developer guide](development/README.md)
- [Control-plane developer course](development/control-plane-course/README.md)
- [Testing and quality](development/testing-and-quality.md)
- [Benchmark developer workflow](benchmark-developer-workflow.md)
- [Release readiness](product/release-readiness.md)
- [Interface budget contract](interface-budget-contract.md)
- [Public/private boundary](public-private-boundary.md)

### Contracts

- [Status data contract](status-data-contract.md)
- [Session runtime to LoopX projection v0](reference/protocols/session-runtime-loopx-projection-v0.md)
- [OpenViking session memory adapter v0](reference/protocols/openviking-session-memory-adapter-v0.md)
- [Interface budget contract](interface-budget-contract.md)
- [Host integration surface v0](reference/protocols/host-integration-surface-v0.md)
- [Computer-use runtime connector v0](reference/protocols/computer-use-runtime-connector-v0.md)
- [Host integration plugin plan v0](reference/protocols/host-integration-plugin-plan-v0.md)
- [Codex App host command registry v0](reference/protocols/codex-app-host-command-registry-v0.md)
- [Local agent launch plan v1](reference/protocols/local-agent-launch-plan-v1.md)
- [Multi-agent visible launcher v0](reference/protocols/multi-agent-visible-launcher-v0.md)
- [Goal vision replan contract v0](reference/protocols/goal-vision-replan-contract-v0.md)
- [Runtime connector catalog](runtime-connector-catalog.md)
- [Reward gate direct-write contract](reward-gate-direct-write-contract.md)
- [Worker bridge install contract](worker-bridge-install-contract.md)
- [Lark Kanban control-plane adapter](lark-kanban-control-plane-adapter.md)
- [Dashboard reward write boundary](dashboard-reward-write-boundary.md)
- [Dashboard budget governance](dashboard-budget-governance-contract.md)
- [Complex project read-only adapter](complex-project-readonly-adapter.md)
- [Protocol contracts](reference/protocols/README.md)

### Product Direction

- [Product vision](product/vision.md)
- [Release readiness](product/release-readiness.md)
- [LoopX Turn Codex CLI quickstart](product/loopx-turn-codex-cli-quickstart.md)
- [Public adoption loop](product/public-adoption-loop.md)
- [Codex CLI TUI-first loop](product/codex-cli-tui-loop.md)
- [Reward-style replanning hints](product/reward-style-replanning.md)
- [Frontstage channel and lease roadmap](frontstage-channel-lease-roadmap.md)
- [Non-technical operator status model](product/nontechnical-operator-status-model.md)
- [Long-task cadence hint](long-task-cadence-policy.md)
- [Dreaming exploration lane](dreaming-exploration-lane.md)
- [Session runtime control-plane adapter](session-runtime-control-plane-adapter.md)
- [Codex peer task orchestration](codex-subagent-orchestration.md)
- [Dashboard frontend selection](dashboard-frontend-selection.md)
- [Experiment controller milestone](experiment-controller-milestone.md)

### Project Governance

- [Project governance](../GOVERNANCE.md)
- [Authors and contributors](../AUTHORS.md)
- [Project history](project/history.md)
- [Name and marks](../TRADEMARKS.md)
- [Contributing](../CONTRIBUTING.md)

### Research And Evidence

- [Showcases](showcases/README.md)
- [Long-horizon agent benchmark research](research/long-horizon-agent-benchmarks/README.md)

### Outreach And Narrative Drafts

- [Outreach index](outreach/README.md)
- [Update notes](update-notes/README.md)

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
- Put stable contributor workflows and quality-system guidance under
  `docs/development/`.
- Put machine-facing protocol contracts under `docs/reference/`.
- Every new doc should be linked from this index or from a subdirectory
  `README.md`. If it is not worth indexing, it probably belongs in local notes
  rather than the public repository.
- Prefer concise public summaries over raw logs, private trajectories, internal
  links, credentials, or local filesystem paths.
