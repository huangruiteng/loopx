# Scenario Capability Gap Map

Status: product steering note.

This note compares the bottom-layer LoopX capabilities needed by three
scenario families:

- repo issue-fix loops, including OpenViking/Viking-style issue triage and
  patch delivery;
- creator or self-media operations loops;
- other scenario signals already present in the repository, such as benchmark
  runners, ML experiment advisory, and host integrations.

It is intentionally not a plan to bake these domains into the core runtime.
The core should keep goal state, todos, gates, evidence, quota, validation, and
handoff generic. Scenario-specific behavior should arrive as explicit adapters
or domain packs after the registry or owner records the boundary.

## Common Substrate

All three scenario families need the same control-plane substrate before
domain logic becomes useful:

| Capability | Why It Matters |
| --- | --- |
| `connector_observation_v0` | Pull compact facts from an external source without copying raw/private material into LoopX state. |
| `source_status_v0` | Label each fact as public, private, synthetic, unpublished, needs-review, or forbidden for public surface. |
| `artifact_handle_v0` | Track issues, PRs, CI runs, drafts, articles, benchmark jobs, or metric boards as observable handles with allowed poll actions. |
| `todo_lifecycle_v0` | Turn the scenario into concrete user and agent todos with `todo_id`, owner, validation, and successor work. |
| `capability_gate_v0` | State which tools or domain packs are needed before the agent can execute a todo. |
| `validation_surface_map_v0` | Require each step to name how success is checked: tests, CI, review, source attribution, scoring, or blocker writeback. |
| `review_handoff_v0` | Package the current state, evidence, risk, and next safe action for a human or primary agent. |
| `feedback_writeback_v0` | Convert user reward, corrections, style feedback, or review comments into durable state instead of chat-only memory. |
| `publish_boundary_v0` | Stop public release, platform posting, leaderboard submission, or production action until an explicit gate allows it. |

The current LoopX architecture already has pieces of this substrate: registry
entries, active goal state, todo lifecycle, quota, status, review packets,
public/private scans, and host-integration contracts. The gap is that
connectors, source status, validation maps, and feedback writeback are not yet
first-class enough for these scenarios to feel product-native.

## Incremental State Surfaces

LoopX should not create one product silo per high-frequency scenario. A better
shape is an incremental state surface: a small domain-facing projection layered
above the generic goal/todo/gate/evidence model.

An incremental state surface is useful when a scenario has repeated user
language and repeated decisions, but does not yet justify a custom frontend or
autonomous domain pack. It should include:

- a compact external handle, such as an issue, post, draft, experiment, CI run,
  or metric board;
- source status and freshness;
- the user or owner routing target;
- allowed next action and stop condition;
- validation surface;
- promotion target into a normal LoopX user todo, agent todo, gate, anchor, or
  review event.

The MVP UI can be whatever the host already has: GitHub labels, issue comments,
Lark messages, a CLI review packet, or a static dashboard card. A custom
frontend should come only after the state surface proves that the scenario is
worth keeping.

## Repo Issue-Fix Loop

An issue-fix loop turns a reported problem into a reviewed patch or blocker.
The high-value path is not only "agent writes code"; it is controlled intake,
repro, patch selection, validation, review, and safe publication.

| Stage | LoopX Object | Needed Capability Increment |
| --- | --- | --- |
| Issue intake | artifact handle + source status | Represent issue URL/id, reporter context, public/private boundary, freshness, and whether raw issue text may be read or quoted. |
| Triage | agent todo + validation map | Classify bug, docs gap, feature request, flaky test, dependency break, or insufficient repro; name the first safe validation. |
| Repro plan | result event + blocker lane | Record exact reproducibility status without storing raw logs or private traces. |
| Patch planning | handoff packet | Separate candidate surfaces from raw diffs; keep patch ownership and write scope visible. |
| Implementation | claimed todo + worktree guard | Require an independent worktree for side agents, disjoint write scope, and local validation before review. |
| Validation | validation surface map | Tie tests, lint, CI, fixture smoke, or manual repro to the todo before marking progress. |
| Review handoff | successor handoff todo | Hand unclear or high-risk patch work to the configured handoff owner, primary agent by default, instead of self-merging. |
| Publication | publish boundary | Distinguish local commit/PR from package release, production deploy, or external submission. |
| Feedback | feedback writeback | Convert review comments, failing CI, or maintainer corrections into successor todos and evidence updates. |

For an OpenViking/Viking-style issue-fix case, the first useful adapter should
be read-mostly:

1. ingest public issue and repository metadata as compact handles;
2. project issue-fix stages into LoopX todos;
3. require an execution gate before reading source files or generating patches;
4. write redacted validation and review handoff packets;
5. stop before publish, deploy, or protected branch actions.

This resembles the existing AgentIssue-Bench packets, but should be product
oriented rather than benchmark oriented. The benchmark route proves source and
patch boundaries; the product route must add maintainer-facing status,
review handoff, and safe continuation semantics.

### Issue Meta Surface MVP

The top layer should record issues as management signals before they become
agent work. This keeps the v0 product simple: GitHub labels and comments can be
the visible UI, while LoopX owns the compact state projection.

`issue_meta_surface_v0` should be the lightweight record:

| Field | Meaning |
| --- | --- |
| `issue_handle` | Public-safe repo plus issue or PR identifier, not raw body text. |
| `source_status` | Public/private/synthetic/needs-review label and freshness. |
| `label_set` | GitHub tags or host tags used as the MVP display and routing layer. |
| `related_code_hint` | Optional compact path/module/package hint; never a raw diff or private path. |
| `owner_route` | Maintainer, Lark channel, or primary agent that should see the issue. |
| `allowed_action` | Observe, ask owner, reproduce, draft plan, prepare patch, or hand off. |
| `validation_surface` | Test, CI, reproducer, maintainer confirmation, or blocker evidence. |
| `promotion_target` | Agent todo, user todo, review event, anchor candidate, or archive. |

This surface should not require a frontend. The first useful implementation can
be a CLI or host adapter that reads selected GitHub tags, creates compact
issue-meta records, and writes normal LoopX todos only after an explicit routing
decision. A later frontend can render the same records by tag or status.

P0 issue-meta acceptance:

- one issue can be represented without copying raw issue body or raw diff;
- a related-code hint can be stored as a compact, reviewable hint;
- owner routing is explicit enough to avoid "someone should find the owner";
- a selected issue can promote to a concrete agent todo with validation and
  stop condition;
- unselected issues remain signals, not backlog clutter.

### Issue-Fix Gaps

P0 gaps:

- `issue_intake_packet_v0`: compact issue handle, source status, repo anchor,
  permission boundary, and first validation surface.
- `repro_validation_map_v0`: structured repro status, test target, blocked
  reason, and next evidence needed.
- `patch_handoff_packet_v0`: candidate change scope, validation done, residual
  risks, and handoff-owner condition.

P1 gaps:

- claim-aware worktree lease beyond soft `claimed_by`;
- connector support for GitHub-like issue/PR/CI surfaces through a thin host
  adapter or MCP facade;
- frontstage card that explains "ready to patch", "waiting for repro",
  "waiting for review", and "safe side work available" without CLI jargon.

Non-goals:

- do not create a separate core LoopX issue object yet;
- do not store raw issue bodies, raw diffs, test bodies, logs, or private repo
  content in public docs or compact status;
- do not autopush, deploy, or publish without the existing boundary gates.

## Creator And Self-Media Operations Loop

The creator-operator path already has a public-safe case spec and feedback
contract. Its bottleneck is less about patch correctness and more about
source attribution, user taste, no-autopublish gates, and useful drafting
queues.

| Stage | LoopX Object | Needed Capability Increment |
| --- | --- | --- |
| Connector ingestion | connector observation + source status | Distinguish public platform summaries, private chat/material, synthetic demo data, and needs-review sources. |
| Information and hotspot ranking | reward-style hint + validation map | Rank candidates by relevance and evidence quality without claiming trend or performance uplift. |
| Insight extraction | result event | Preserve source attribution and why the item is worth creating from. |
| Draft creation | agent todo + draft queue | Separate outline, draft, rewrite, source-map, and publish-gate states. |
| Scoring and feedback | feedback writeback | Turn "useful", "not my style", "too salesy", or "do not use this source" into durable preferences, todos, or boundary corrections. |
| Rewrite loop | successor todo | Keep revision work executable while publication remains gated. |
| Publish decision | user gate | No autopublish; explicit tone/source/policy approval before external posting. |

Connector examples such as a browser route for public feeds or a local chat
connector for private WeChat-like history should stay adapter-owned. LoopX
should only store compact source labels, evidence summaries, gates, feedback,
and next actions.

### Content-Ops State Surface MVP

The creator path needs a state surface before it needs a publisher. The surface
should make the work queue useful while keeping publication gated and source
boundaries visible.

`content_ops_surface_v0` should include these records:

| Record | Purpose |
| --- | --- |
| `source_item_v0` | Compact observation from a platform, chat, document, or synthetic demo source with source status, freshness, terms note, and allowed quote/use policy. |
| `angle_candidate_v0` | Why the source might matter to this creator: audience, topic, novelty, user preference fit, evidence quality, and rejection reason if ignored. |
| `draft_item_v0` | Outline/draft/rewrite/source-map state, linked to source items and explicit user preference hints. |
| `feedback_signal_v0` | Useful/not useful, style correction, source rejection, publish approval/denial, or preference note. |
| `publish_gate_v0` | Human approval record for external posting; no autopublish from draft existence. |
| `material_memory_v0` | Durable source-safe library entry with attribution, rejected angles, and reuse boundary. |

The first public-safe implementation is now anchored by
`loopx/capabilities/content_ops/surface.py`, `docs/reference/protocols/content-ops-surface-v0.md`,
and `examples/content-ops-surface-fixture-smoke.py`. This keeps the MVP as a
state-surface contract: source/draft/feedback/gate facts can promote into
normal LoopX todos, but the projection itself is read-only and has no publish
authority.

The state flow should stay deliberately boring:

```text
connector observation
  -> source_item_v0
  -> angle_candidate_v0
  -> user/agent todo for draft or rejection
  -> draft_item_v0
  -> feedback_signal_v0
  -> rewrite todo or publish_gate_v0
  -> optional material_memory_v0
```

This differs from an ordinary content pipeline in three ways:

- the unit of work is not "post more"; it is "select, justify, draft, review,
  and learn";
- the success signal is accepted signal or accepted draft quality, not raw
  article count;
- feedback changes durable preferences and source boundaries instead of only
  improving the current draft.

P0 content-ops acceptance:

- every item has source status and freshness before becoming a draft;
- a draft carries a source map and publish gate;
- user feedback writes to one of: preference hint, source boundary correction,
  rewrite todo, or publish decision;
- the operator can see "waiting for source review", "ready to draft",
  "waiting for feedback", "ready to publish decision", and "safe side work
  available";
- no connector, browser, or chat adapter writes raw private material into
  public LoopX state.
- the public fixture and projection smoke pass before a connector or frontend
  treats the surface as stable.

### Creator-Ops Gaps

P0 gaps:

- `source_status_v0` as a reusable field on insights, drafts, and material
  library items;
- `feedback_writeback_v0` that maps style feedback, reward, todo update, and
  boundary correction into explicit state;
- a no-autopublish gate rendered in the first-screen operator model.

P1 gaps:

- connector freshness and terms-of-use metadata;
- material-library schema with attribution, rejected angles, and source status;
- draft queue projection for frontend and review packets.

## Other Repository Scenario Signals

The repository already records several scenario classes that should inform the
generic substrate:

| Scenario Signal | Existing Surface | Capability Lesson |
| --- | --- | --- |
| Long-horizon benchmarks | `docs/research/long-horizon-agent-benchmarks/` | Needs artifact handles, result reducers, score-claim boundaries, and no-raw-log public evidence. |
| ML experiment advisory | `docs/product/domain-capability-packs.md` | Domain packs should be default-off and explicit about autonomy, primary metrics, and launch authority. |
| Host integration | `docs/reference/protocols/host-integration-surface-v0.md` | Hooks, MCP, and loopback APIs must remain thin facades over CLI-equivalent lifecycle reads and writes. |
| Non-technical operator UI | `docs/product/nontechnical-operator-status-model.md` | First-screen copy needs plain-language state, blockers, user actions, validation, and feedback paths. |
| Creator-operator showcase | `docs/showcases/cases/0620-creator-operator-case-spec.md` | Public demos need synthetic data, source-status rules, and visible feedback effects. |

These should not become separate control planes. They should pressure the same
LoopX primitives until the primitives are strong enough to support multiple
domains.

### Repository Scenario Inventory

The README and product docs already name more scenario pressure than the first
two examples. The useful product move is to rank the substrate each scenario
needs, not to start one adapter per scenario.

| Rank | Scenario Signal | Evidence In Repo | Bottom-Layer Increment To Build First |
| --- | --- | --- | --- |
| P0 | Maintainer management and multi-agent lanes | `docs/product/intelligent-management-surface.md`, `docs/product/nontechnical-operator-status-model.md` | `signal_v0`, `anchor_v0`, `management_projection_v0`, and lane-level `performance_review_v0` so a maintainer can review value, quality, cost, and attention before more automation is trusted. |
| P0 | Repo issue-fix and PR-led growth | `docs/product/intelligent-management-surface.md`, `docs/project-agent-todo-contract.md` | `issue_meta_surface_v0`, `issue_intake_packet_v0`, and `patch_handoff_packet_v0` so issue signals can stay visible without becoming raw backlog or unsafe patch authority. |
| P0 | Creator and self-media operations | `README.md`, `README.zh-CN.md`, `docs/product/vision.md` | `content_ops_surface_v0`, source-aware draft queues, and durable `feedback_signal_v0` so source boundaries, taste feedback, and no-autopublish gates survive turns. |
| P0 | Benchmark developer workflow | `docs/benchmark-developer-workflow.md`, `docs/research/long-horizon-agent-benchmarks/` | `observable_artifact_handle_v0`, compact result/blocker reducers, and score-claim boundary checks so real runs can be observed without raw task text, trajectories, logs, or host paths. |
| P1 | Codex CLI TUI onboarding and continuation | `README.md`, `docs/product/codex-cli-tui-loop.md`, `docs/product/codex-cli-automation-driver.md` | `host_session_handle_v0`, visible-session proof, idle/fallback state, and prompt-upgrade detection so one-message bootstrap and same-TUI continuation are legible and recoverable. |
| P1 | ML experiment advisory | `docs/product/domain-capability-packs.md`, `docs/experiment-controller-milestone.md` | `domain_pack_detection_v0`, `domain_pack_contract_v0`, and advisory `ml_experiment_result_v0` so experiment-shaped goals can be recognized without silently enabling launch or route decisions. |
| P1 | Host integration and local dashboard APIs | `docs/reference/protocols/host-integration-surface-v0.md`, `docs/integration.md` | `host_integration_surface_v0` plus CLI-equivalent dry-run/writeback contracts so browser, MCP, and loopback surfaces remain facades rather than new authorities. |
| P1 | Research and material registry loops | `docs/authority-source-registration.md`, `docs/research/` | `authority_source_v0`, compact source contracts, and freshness checks so durable materials can guide routing without copying source bodies or private links. |
| P2 | Public frontstage/showcase adoption | `docs/product/frontstage-two-surface-strategy.md`, `docs/showcases/README.md` | `showcase_case_v0` and public-safe synthetic fixtures so demos explain LoopX without leaking live control state or turning showcase UI into control authority. |
| P2 | Office operations and partner connectors | `docs/product/intelligent-management-surface.md` | Generic `connector_observation_v0`, `signal_v0`, and review-feed cards so partner tools can send compact work signals before LoopX owns any domain executor. |

The ranking says which substrate should be reusable first:

1. **P0: signal-to-anchor pipeline.** The management surface, issue loop, and
   creator loop all need `signal_v0` with source status, freshness, suggested
   effect, and explicit promotion to todo, gate, review event, or anchor.
2. **P0: compact artifact handles and validation surfaces.** Issue repro,
   benchmark runs, Codex sessions, experiment jobs, and content drafts all need
   observable handles with allowed poll/read actions, validation status, and
   no-raw-material evidence rules.
3. **P0: feedback writeback as typed state.** Review feed scores, user style
   feedback, maintainer corrections, and benchmark route judgments must become
   `feedback_signal_v0`, reward overlays, todo updates, boundary corrections, or
   performance review notes.
4. **P1: domain-pack detection without permission escalation.** ML experiments,
   office ops, issue solvers, and content connectors can be detected as
   scenario-shaped, but only registry or owner boundary records can enable
   advisory or delivery autonomy.
5. **P1: host facade discipline.** Browser, MCP, dashboard, Codex CLI,
   benchmark host, and connector surfaces should expose the same dry-run,
   validation, writeback, and stop-condition lifecycle as the CLI.
6. **P2: scenario-specific frontends and adapters.** Build custom cards,
   publisher queues, experiment panels, or issue dashboards only after their
   compact state surface has proved useful in plain LoopX status and review
   packets.

## Priority Stack

P0: make issue-fix loops product-native.

1. Define `issue_intake_packet_v0`, `repro_validation_map_v0`, and
   `patch_handoff_packet_v0`.
2. Define `issue_meta_surface_v0` as the management layer above GitHub tags,
   owner routing, related-code hints, and todo promotion.
3. Add a public-safe issue-fix fixture using compact public metadata only.
4. Project the issue-fix fixture into todos and a review handoff without
   reading raw source files or generating patches.

P0: make creator-ops feedback durable.

5. Defined `content_ops_surface_v0` over source items, angle candidates,
   drafts, feedback signals, publish gates, and material memory, with a
   public-safe fixture/projection helper and smoke.
6. Promote `source_status_v0` and `feedback_writeback_v0` into reusable
   product contracts.
7. Keep no-autopublish gates visible in status and frontend demo data.

P1: scan and rank remaining scenario signals.

8. Completed the first repository scenario inventory across maintainer
   management, issue-fix, creator ops, benchmarks, Codex CLI, ML experiments,
   host integrations, research materials, frontstage, and partner connectors.
9. Promote the reusable P0 substrate from that scan: signal-to-anchor,
   artifact-handle/validation, and feedback-writeback contracts.
10. Avoid adding a domain pack until the registry boundary explicitly enables
    it.

## Acceptance Criteria

A scenario capability map is useful when it lets a maintainer answer:

- which external facts are compact handles versus raw material;
- which work item is executable by the agent and which is a user gate;
- what validation would prove progress;
- where side-agent work must hand off to the primary agent;
- what can continue safely while a gate waits;
- what must never be published or treated as public evidence.

When those answers are visible in LoopX state, a scenario is ready for a thin
adapter or demo. When they are only in prose or chat, the next product step is
to add the missing control-plane capability first.
