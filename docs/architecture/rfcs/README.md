# Architecture RFCs

Architecture RFCs are public design proposals. Each RFC should name its
decision boundary, non-goals, smallest useful implementation slice, and
validation criteria. An RFC may describe future work; current behavior is
defined by the implementation and stable reference contracts.

Start new proposals from the [RFC template](TEMPLATE.md). Existing RFCs should
adopt its maintenance contract when substantial revision would otherwise mix
stable design, current progress, and historical evidence.

The [Current Technical Directions](../../project/technical-directions.md) page
maps RFCs to strategic programs, contribution routes, and promotion gates.

## How to read this index

The sections below are technical ownership areas, not maturity levels. Each
primary RFC appears once under its nearest architectural owner even when it
also affects other areas.

Within each entry, RFC maturity and delivery maturity remain separate facts:

- **RFC status** records the decision state written in the RFC. `Draft` work
  remains open to architectural change even when a bounded slice has shipped.
- **Delivery on `main`** records the implementation state audited against the
  repository. A merged experiment does not make its whole RFC accepted, and an
  accepted RFC may still have later adoption work.
- **Current boundary** names what is real now and what is still excluded. It is
  a navigation aid, not a replacement for stable protocol documentation.

Within an RFC, keep the same separation:

- normative sections define the current decision and acceptance contract;
- a dated execution ledger records shipped slices and experiments without
  silently changing that contract;
- a decision log records explicit approval and the sections it changed;
- an evidence registry maps claims to reproducible, public-safe proof.

Do not append progress reports to a normative delivery plan. Move long ledgers
to a linked `*-execution.md` companion. Schema reduction is never an incidental
cleanup: the RFC or PR must name each removed field, document producer/reader/
writer and compatibility research, define migration and rollback, prove the
claimed semantic equivalence, and record explicit maintainer approval.

This index was last audited against `main` on **2026-09-04**. Update an entry
whenever its RFC status, promoted behavior, or meaningful delivery boundary
changes.

## Control-Plane Kernel, State, And Migration

- [Agent Loop Effect Interpreter v0](agent-loop-effect-interpreter-v0.md)
  ([中文版](agent-loop-effect-interpreter-v0.zh-CN.md))
  - **RFC status:** Accepted.
  - **Delivery on `main`:** Core implemented; bounded adoption continues.
  - **Current boundary:** Effect request, interpretation, observation,
    settlement, and typed Effect Program foundations are shipped. Replan
    planning/ACK stays domain-local until a second real lifecycle justifies
    extraction.
- [TypeScript Control-Plane Migration v0](typescript-control-plane-migration-v0.md)
  ([中文版](typescript-control-plane-migration-v0.zh-CN.md))
  - **RFC status:** Accepted; transaction-payoff phase in progress.
  - **Delivery on `main`:** Substantially implemented; active migration.
  - **Current boundary:** Stage 1 and 2A are complete. Stage 2B is cutting over
    whole semantic transactions and retiring Python facades under parity and
    differential gates.
- [Shared-goal Online Authority and Pluggable Coordination Provider v0](shared-goal-authority-state-provider-v0.md)
  ([中文版](shared-goal-authority-state-provider-v0.zh-CN.md),
  [validation boundary](shared-goal-authority-state-provider-v0-evidence.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Foundation, provider-contract, and local promotion
    preparation slices implemented.
  - **Current boundary:** Recoverable shared-authority foundations, the
    file-backed reference path, NoKV shadow/recovery evidence, the TypeScript
    store contract, PostgreSQL candidate/conformance coverage, and the
    default-off local shadow/cutover foundations are on `main`
    ([#3529](https://github.com/huangruiteng/loopx/pull/3529),
    [#3669](https://github.com/huangruiteng/loopx/pull/3669),
    [#3798](https://github.com/huangruiteng/loopx/pull/3798)). No provider-first
    runtime promotion or remote shared-authority service has shipped.
- [Shared Goal Alignment and Governed Amendment Protocol v0](shared-goal-alignment-and-governed-amendment-v0.md)
  ([中文版](shared-goal-alignment-and-governed-amendment-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** Existing peer lanes, unclaimed work, claims/leases,
    Agent-scoped Goal Vision/Replan, and provider-neutral authority are inputs.
    A read-only shared-alignment projection, automated amendment policy,
    verifier boundary, and canonical Goal-amendment transaction have not
    shipped.
- [Goal Direction Baseline v0](goal-direction-baseline-v0.md)
  ([中文版](goal-direction-baseline-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** A provider-neutral, Agent-scoped read model and
    synthetic drift fixture plan are proposed. No direction declaration,
    reducer, runtime consumer, Vision writer, scheduler effect, or provider
    integration has shipped.
- [Goal Artifact Lifecycle Projection v0](goal-artifact-lifecycle-projection-v0.md)
  ([中文版](goal-artifact-lifecycle-projection-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** Milestones, blocking guards, and legal transitions are
    specified as a read-only projection; no canonical lifecycle projection has
    shipped.

## Planning, Research, And Adaptive Intelligence

- [Research Exploration Control Plane v0](research-exploration-control-plane-v0.md)
  ([中文版](research-exploration-control-plane-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Partially implemented.
  - **Current boundary:** The explicit composition projection and successor
    binding from M2 shipped in
    [#3173](https://github.com/huangruiteng/loopx/pull/3173). The canonical
    observation contract, shared write-time gate, model selection, and inferred
    triggers have not been promoted.
- [Hierarchical Agent Stride Control v0](hierarchical-agent-stride-control-v0.md)
  ([中文版](hierarchical-agent-stride-control-v0.zh-CN.md))
  - **RFC status:** Draft, research proposal.
  - **Delivery on `main`:** M1 observation slice implemented.
  - **Current boundary:** Read-only stride observation and its synthetic
    boundary fixture shipped in
    [#3207](https://github.com/huangruiteng/loopx/pull/3207) and
    [#3290](https://github.com/huangruiteng/loopx/pull/3290). Adaptive effect,
    delivery, and authority stride selection remains research-only.
- [Post-Outcome Memory Utility Attribution v0](post-outcome-memory-utility-attribution-v0.md)
  ([中文版](post-outcome-memory-utility-attribution-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Stage 1 implemented.
  - **Current boundary:**
    [#3280](https://github.com/huangruiteng/loopx/pull/3280) binds utility
    observations to verified outcomes without changing retrieval ranking.
    Reducer/read projection, provider readback, ranking influence, and pilot
    promotion remain open.
- [Obelisk Session Evidence Provider v0](obelisk-session-evidence-provider-v0.md)
  ([中文版](obelisk-session-evidence-provider-v0.zh-CN.md))
  - **RFC status:** Draft integration proposal.
  - **Delivery on `main`:** Evaluation only.
  - **Current boundary:** The default-off, read-only evidence-provider boundary
    is documented. Obelisk is not installed, promoted, or authoritative for
    Replan settlement, memory, or action selection.

## Runtime, Capability, And Collaboration Integration

- [Single-Owner Local Daemon v0](single-owner-local-daemon-v0.md)
  - **RFC status:** Draft.
  - **Delivery on `main`:** Proposal only; existing Desktop ownership repair is shipped.
  - **Current boundary:** Service-profile identity, component readiness, supervised
    composition, and recoverable migration are proposed for #3930. A unified
    `loopxd` service has not shipped.
- [Provider-Neutral Turn-Start Inbox Hook v0](provider-neutral-turn-start-inbox-hook-v0.md)
  - **RFC status:** Implemented behind explicit provider configuration.
  - **Delivery on `main`:** Implemented, opt-in.
  - **Current boundary:** The provider-neutral turn-start read contract and
    Lark ACK/replay path shipped in
    [#3678](https://github.com/huangruiteng/loopx/pull/3678) and
    [#3733](https://github.com/huangruiteng/loopx/pull/3733); no provider is
    enabled implicitly.
- [Provider-Neutral Post-Writeback Capability Hooks v0](provider-neutral-post-writeback-capability-hooks-v0.md)
  ([中文版](provider-neutral-post-writeback-capability-hooks-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** First end-to-end vertical implemented.
  - **Current boundary:** The periodic-report producer, durable intent
    lifecycle, terminal closeout dispatch, consumer, and approved Goal Channel
    delivery shipped through
    [#3691](https://github.com/huangruiteng/loopx/pull/3691),
    [#3748](https://github.com/huangruiteng/loopx/pull/3748),
    [#3749](https://github.com/huangruiteng/loopx/pull/3749), and
    [#3755](https://github.com/huangruiteng/loopx/pull/3755). General
    multi-capability promotion remains under review.
- [LoopX Desktop Execution Frontends v0](desktop-execution-frontends-v0.md)
  ([中文版](desktop-execution-frontends-v0.zh-CN.md))
  - **RFC status:** Draft.
  - **Delivery on `main`:** Supporting foundations implemented.
  - **Current boundary:** Attached and managed runtime, desktop, and connector
    pieces exist, but the unified execution-frontend/session-ownership contract
    and cross-transport convergence are not accepted as one shipped product
    boundary.
- [Goal Channel Collaboration v0](goal-channel-collaboration-v0.md)
  ([中文版](goal-channel-collaboration-v0.zh-CN.md))
  - **RFC status:** Draft.
  - **Delivery on `main`:** Lark vertical implemented.
  - **Current boundary:** Goal-bound Lark groups, Kanban, gate notifications,
    shared targets, and Bot runtime integration are shipped. The
    provider-neutral multi-surface model remains draft, and interactive
    transport is refined by the Desktop Frontends RFC.
- [Agent IM, LoopX, and OpenViking Collaboration v0](agent-im-openviking-collaboration-v0.md)
  - **RFC status:** Draft.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** LoopX, IM, and OpenViking have adjacent
    implementations, but this three-owner collaboration contract has not
    shipped as an integrated path.

## Operator Experience And Observability

- [Per-Goal Usage, Token, and Cost Surfacing v0](goal-usage-token-cost-v0.md)
  - **RFC status:** Draft.
  - **Delivery on `main`:** Core slice implemented.
  - **Current boundary:** Codex usage capture, normalized aggregation, and
    dashboard surfacing shipped in
    [#3117](https://github.com/huangruiteng/loopx/pull/3117); broader
    runtime/provider coverage and cost semantics remain incomplete.
- [Intelligent Review and Dynamic Presentation Surfaces v0](intelligent-review-presentation-surfaces-v0.md)
  ([中文版](intelligent-review-presentation-surfaces-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** Existing typed proposals, gates, planning projections,
    receipts, and direct reversible-action UX are inputs. The shared
    `action_review_plan_v0` compiler and dynamic card/report/wiki presentation
    contract have not shipped.
- [Human Attention Wishlist v0](human-attention-wishlist-v0.md)
  ([中文版](human-attention-wishlist-v0.zh-CN.md))
  - **RFC status:** Draft, under maintainer review.
  - **Delivery on `main`:** Intentionally deferred.
  - **Current boundary:** The RFC remains a discussion contract. Runtime work is
    held until repeated real usage demonstrates a second need without weakening
    non-blocking authority boundaries.

## Benchmark And Reliability Engineering

- [Benchmark Study Upload and Dashboard Projection v0](benchmark-study-upload-dashboard-v0.md)
  - **RFC status:** Draft integration proposal.
  - **Delivery on `main`:** Proposal only.
  - **Current boundary:** Experiment-board rows and benchmark-native scores
    remain authoritative; the study manifest, upload/readback envelope, and
    campaign-to-run dashboard projection are proposed but not implemented.
- [Long-Horizon Harness Benchmark and Research Program v0](long-horizon-harness-benchmark-research-program-v0.md)
  ([中文版](long-horizon-harness-benchmark-research-program-v0.zh-CN.md))
  - **RFC status:** Draft, research program.
  - **Delivery on `main`:** Active research and engineering program.
  - **Current boundary:** ALE, LHTB, and DeepSWE form the external-validity
    portfolio; benchmark infrastructure and evidence workflows are being built
    without treating the research program as a runtime protocol.
- [Long-Running Agent Reliability Diagnostics and Governed Delivery v0](long-running-agent-reliability-diagnostics-governed-delivery-v0.md)
  ([中文版](long-running-agent-reliability-diagnostics-governed-delivery-v0.zh-CN.md))
  - **RFC status:** Draft, product direction and delivery contract.
  - **Delivery on `main`:** Direction only.
  - **Current boundary:** The observer-first adoption path, matched benchmark
    qualification, and governed delivery package are proposed; no unified
    product contract has been promoted.

RFCs must not contain internal conversations, private links, local filesystem
paths, credentials, raw transcripts, or non-public organizational context.
