# Contributor Task Board

This board is the public, contributor-facing projection of LoopX work.
It is intentionally different from `.local` active goal state:

- this file lists public work that can be discussed, claimed, reviewed, and
  validated in the repository;
- `.local`, `.loopx`, and live `ACTIVE_GOAL_STATE.md` files remain local
  runtime data for maintainers and automation;
- private benchmark traces, verifier output, raw agent sessions, credentials,
  internal document links, and local machine paths must not be copied here.

The goal is to make important work discoverable without turning the repository
into a mirror of maintainer scratch state.

## Status Legend

| Status | Meaning |
| --- | --- |
| Available | Ready for someone to comment on the linked issue or open a small PR. |
| Claimed | Someone has said they are working on it, or a maintainer assigned it. |
| Maintainer-owned | Active work is happening in maintainer/local automation; ask before touching. |
| Needs design | Discussion is welcome, but implementation needs agreement first. |
| Blocked | Waiting on a decision, dependency, or maintainer writeback. |
| Done | Completed and ready to archive from this board. |

## How To Claim Work

1. Prefer a linked GitHub issue. If there is no issue yet, open one with the
   contributor task template.
2. Comment that you would like to work on the task. Maintainers will mark it
   `claimed` or suggest a smaller slice.
3. For docs-only typo fixes or obviously tiny cleanups, opening a direct PR is
   fine.
4. If a claimed task has no update for 14 days, maintainers may release it back
   to `Available` after one ping.
5. If a task is `Maintainer-owned`, do not duplicate the work. Ask whether
   there is a public helper slice instead.

## Current Public Tasks

Start with **Starter** tasks if this is your first contribution. Choose
**Focused** tasks if you are comfortable running local smokes. Pick **Advanced**
tasks only when you are ready to touch shared state, adapters, or concurrency.
Use **Design/RFC** tasks to shape direction before implementation.

## Product Manager Cut

LoopX is currently converging from a control-plane library into a management
surface for long-running agent work. Product-capability contributions should
prefer slices that make existing kernel objects understandable to users instead
of adding another source of truth.

| Product slice | Current substrate | Contributor-sized next cut |
| --- | --- | --- |
| Management frontstage | Goals, todos, gates, claims, evidence, quota, run history, `goal_channel_projection_v0`, `task_graph_projection_v0`, `issue_fix_outcome_projection_v0`, and same-source Explore views are already compact read models. | Translate these into stable operator concepts such as work item, owner, decision, evidence, budget, risk, and next action; preserve lineage, keep raw machine fields in drill-downs, and do not create a second task or case store. |
| Conversational commands | `global_manager_command_v0` defines read-only commands such as `/loopx-global-summary`, `/loopx-global-gates`, `/loopx-global-todos`, and `/loopx-global-risks`; legacy `/loop-global-*` forms are only migration aliases. | Implement one canonical command at a time with a public-safe smoke and no alias sprawl. Unknown commands should fail closed with help. |
| Runtime connector modes | `host_mode_plan_v0` now selects visible, isolated-headless, gateway, service, and hybrid modes over the connector catalog. Codex App, Codex CLI, Claude Code, shell, webhook, and worker-bridge routes are catalogued; first-class OpenCode goal-mode support has landed but is not yet represented in selector/catalog parity. LoopX Turn remains one isolated request/effect/receipt transaction, not a recurring loop. | Close OpenCode selector/catalog parity, make mode choice and handoff visible, then add the separate provider-neutral Turn Loop Controller. Keep `run-once` atomic; recurring wakeup, typed replan continuation, operator routing, and scheduler-hint execution belong to that separate loop layer. |
| Visible governance | Quota, scheduler hints, authoritative interaction contracts, decision scopes, user gates, peer claims, optional task leases, repository policy, and interface budgets already exist in machine contracts. | Show who can act, who must approve, which decision scope applies, what budget was spent, and how pause/override/terminate decisions map back to LoopX state without treating claims or leases as a new runtime hierarchy. |
| Domain packs | Domain capability packs default off; ML experiment and scenario/productization work should stay advisory until enabled by registry or owner authority. | Add suggest-only previews or public-safe fixtures before any domain-specific autonomy, launch, or production action. |

## Recent Maintainer Progress

These public milestones changed which tasks are still useful contributor entry
points:

| Area | Landed | Contributor implication |
| --- | --- | --- |
| Issue-fix productization | `118d7d3f`, `f2a725c2`, and `bc37dd2e` added opt-in Reward Memory gating and scoped feedback without coupling previews to external sinks; `c26a8a2a` defined provider-neutral static presentation delivery. | Extend the existing outcome and memory projections with synthetic fixtures or one public operator rendering. Keep provider payloads, private notification state, and sink credentials outside the read model. |
| Explore and showcases | `6d8938a3`, `9b34eeee`, and `09336b46` added evidence-stage boards, first-class visual styles, and cross-role integrity checks; `9d88355c` and `6d51032d` moved real long-running trajectory evidence into public entry paths; `bfd71eec` and `6312d06e` shipped provider-neutral periodic reports plus dense reusable HTML. | Add local no-sink walkthroughs, accessibility/readability coverage, or synthetic report/showcase fixtures that preserve decision and evidence lineage. Do not rebuild the README hero, publish private graph sources, or couple a renderer to one delivery provider. |
| Peer coordination | The v0.2 peer runtime keeps claims as routing signals. The optional `task_lease_v0` is shipped, while `df984689` completed approved decision-scope lifecycle resolution and `0e6ee514` kept replans on the causal peer frontier. | Adopt the shipped lease and decision-scope contracts in one host or operator view at a time; do not turn them into hierarchy or infer authority from prose. |
| CLI/runtime boundaries | `d402229b`, `f7372544`, and `8dce0182` shipped resumable LoopX Turn execution, a native Codex CLI host, and explicit host-result contracts; `1a7fc565` added the dry-run host-mode selector, `594fded9` documented a minimal local Turn, and `d0a278fe` added first-class OpenCode goal-mode support. | Close selector/catalog parity before adding another host, or add provider-neutral fake-host examples and compact receipt rendering. Preserve independent validation, keep recurring loops outside `run-once`, and do not expose raw sessions or host-local paths. |
| Status, quota, and monitors | `bd48d71d` made the interaction contract authoritative; `f0d4e8cd` and `aa8a4ef4` bound cadence to the runtime owner and settled scheduler ACK before backoff; `df2f12bb` repaired shared-runtime projection sync. | Add focused parity fixtures or compact operator explanations. Do not add a second scheduler, duplicate runtime projection, or let technical gates hide runnable work. |
| Benchmark boundary | `0d9931ac`, `ba3882e4`, and `8f1fc0a3` qualified the SkillsBench LoopX Turn route and pair-fidelity receipts; `0baf8f0b` connected committed Turn receipts to typed repair; `dcdc4113` added a public-safe SkillsBench runner-readiness contract. | Extend other adapters through the shipped lifecycle, readiness, receipt, and reducer seams. Keep live comparisons maintainer-owned and raw task text, logs, trajectories, verifier tails, credentials, uploads, and local paths out of public fixtures. |
| Validation | `3f6c0c88` and `48051420` established agent-facing CLI output budgets and base/head differential checks; `6e029640` and `65fe3f63` strengthened semantic oracles and documented semantic-first test design; `c7768708` moved capability-gate rules into focused pytest coverage. | Derive expected transitions independently, move stable pure rules into pytest, retain thin public behavior seams, and avoid snapshotting implementation output as the oracle. |
| Release and install | v0.2.4-v0.2.6 are documented in `docs/product/release-readiness.md`; v0.2.7-v0.2.8 are tagged and promoted but not yet summarized there. `13592e16` and `f240f81a` also hardened persisted-Python forwarding during self-update. | Close the v0.2.7-v0.2.8 release-history gap, then improve contributor-safe update recovery and failure attribution without adding a parallel release checklist. |
| Public project docs | `b25d1c4c` refreshed README capability/evidence paths, `65b0cbe3` documented the isolated LoopX Turn route, and `65fe3f63` consolidated developer testing guidance. | Keep contributor, release, protocol, and showcase surfaces concise and linked to public evidence; replace stale truth instead of appending another status narrative. |

## Turn Loop Controller Plan

`loopx turn run-once` remains the atomic governed executor: decide, execute one
bounded host segment, validate independently, write back, spend once, and
project the latest scheduler contract. It must not become a resident scheduler
or an unbounded agent loop. Codex App heartbeat currently supplies recurring
wakeup and prompt-driven replan behavior; headless parity belongs in a separate
provider-neutral outer controller.

| Priority | Planned slice | Required boundary and proof |
| --- | --- | --- |
| P0 | Add a pure Turn Loop Controller transition contract over one Turn receipt plus a fresh quota/scheduler decision. | Return exactly one typed disposition such as `run_now`, `wait`, `user_action_required`, `repair`, `replan`, or `terminal`. The pure transition must not invoke a model, sleep, mutate a host scheduler, write state, or spend quota. |
| P0 | Make `replan_required` a real continuation boundary. | Before another Turn, write a bounded todo or vision delta, obtain a fresh TurnEnvelope, and preserve the causal agent/todo frontier. Never rerun the same stale todo merely because a host session is resumable. Reuse the existing autonomous-replan and two-stall contracts. |
| P1 | Add a scheduler-owner adapter around the transition contract. | Apply `scheduler_hint` wake, backoff, reset, ACK/failure, and terminal-stop actions through the declared runtime owner. Cadence-only transitions spend no quota, and `run-once` remains the only delivery transaction. |
| P1 | Add operator and monitor routing. | Project concrete user actions without inventing gates; keep unchanged monitor waits quiet and no-spend; resume only from a fresh LoopX decision after material state changes. |
| P2 | Qualify parity with Codex App heartbeat. | Use deterministic fixtures across active work, wait, user gate, repair, replan, monitor, and terminal states, followed by one explicit opt-in real-host qualification. Preserve independent validation and exclude raw prompts, transcripts, credentials, and host-local paths. |

The first implementation PR should deliver only the pure transition contract
and its decision table. Scheduler process management, host-specific wake APIs,
and operator presentation should remain later adapters so each slice is
reviewable and reversible.

### Starter / Good First

Low setup, docs-first, or narrow fixture work. These should be good entry
points for contributors who are still learning the repository.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C01 | docs | Add a short "first goal" walkthrough that starts with `loopx demo`, inspects status/history, completes one todo, and shows the next todo. | `loopx check --scan-path README.md --scan-path docs/ --scan-path examples/` |
| GH-C02 | tests | Add or extend a focused smoke test around todo archive/completion behavior. Prefer copying the style of `examples/control_plane/todo-lifecycle-cli-smoke.py`. | `python3 examples/control_plane/todo-lifecycle-cli-smoke.py` and `python3 -m py_compile loopx/*.py` |
| GH-C04 | docs | Refresh install, activation, and recovery guidance through v0.2.8: add concise v0.2.7-v0.2.8 release summaries, preserve stable vs `main` and release-snapshot vs canary distinctions, cover persisted-Python self-update recovery, and keep optional capabilities explicitly activated. | `python3 examples/fresh-clone-quickstart-smoke.py`, `python3 examples/loopx-update-smoke.py`, `python3 examples/release/release-readiness-doc-smoke.py`, `python3 examples/release/release-version-contract-smoke.py`, and `loopx check --scan-path docs/product/release-readiness.md --scan-path CONTRIBUTING.md` |
| GH-C10 | docs | Add a public "what counts as a good smoke" guide using `CONTRIBUTING.md` and recent benchmark-smoke cleanup as source material. | `loopx check --scan-path CONTRIBUTING.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C13 | docs | Expand public/private boundary examples with realistic safe and unsafe snippets for benchmark traces, active state, local paths, credentials, and compact artifacts. | `loopx check --scan-path docs/public-private-boundary.md --scan-path examples/` |
| GH-C30 | docs | Add a shared-runtime project asset explainer showing source runtime, owner, gate, next action, stop condition, last evidence, next safe command, user/agent todos, and projection freshness. Explain healthy, missing, and ambiguous routes without publishing registry paths or local state. | `python3 examples/project/configure-goal-global-sync-smoke.py` and `loopx check --scan-path docs/status-data-contract.md --scan-path docs/` |
| GH-C64 | release docs | Add a contributor-safe atomic-promotion failure matrix around the shipped release lock/concurrency smoke: explain which failures happen before the symlink swap, how a waiter recovers, and when contributors must stop before maintainer-only promotion state. Extend the existing fixture only for a durable missing case. | `python3 examples/release/release-promotion-concurrency-smoke.py`, `python3 examples/release/local-install-promotion-boundary-smoke.py`, and `loopx check --scan-path docs/product/release-readiness.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C57 | docs | Refresh connector repair guidance around the authoritative interaction contract: distinguish user, agent, and CLI actions; explain runtime-owned cadence, ACK-before-backoff, workspace/shared-runtime projection repair, and no-spend transitions without exposing local runtime state. | `python3 examples/control_plane/heartbeat-prompt-smoke.py`, `python3 examples/control_plane/quota-scheduler-state-ack-smoke.py`, and `loopx check --scan-path docs/heartbeat-automation-prompt.md --scan-path docs/runtime-connector-catalog.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C58 | docs | Add a capability-packaging explainer that connects the top-level README, `docs/capabilities/`, packaged install, and the first shipped value connector/Lark capability paths without leaking host-specific setup. | `loopx check --scan-path README.md --scan-path docs/capabilities --scan-path docs/product/codex-cli-packaged-install.md` |

### Focused Implementation

Small-to-medium code changes with a clear validation surface. These are good
for contributors who can run local CLI smokes and keep changes scoped.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C06 | cli | Characterize one remaining oversized CLI ownership seam, then move only a cohesive command or rule group into its bounded module. Preserve public invocations, avoid compatibility wrappers without a real caller, and keep the module-size/import budget honest. | Command-specific smoke, `python3 examples/cli-command-module-size-ownership-command-modularization-smoke.py`, `python3 regression/cli-command-module-contract.py`, and focused pytest if rules move |
| GH-C40 | benchmark | Adopt the bounded benchmark lifecycle/read-model seams in one remaining adapter, preferably ALE: add compact readiness, observable-handle, blocker, and result reducers without moving raw logs, task text, verifier output, or host paths into the public control plane. | `python3 examples/benchmark-developer-workflow-doc-smoke.py`, `python3 examples/benchmark-core-adapter-contract-smoke.py`, and one adapter-focused fake fixture |
| GH-C43 | showcase | Extend the shipped Auto Research long-running showcase with a contributor-safe stop/takeover and state-aware wakeup walkthrough. Reuse the current command path and synthetic/redacted evidence; do not add a second launcher or alter the README first screen without maintainer preview. | `python3 examples/showcase-catalog-smoke.py`, `python3 examples/auto-research-demo-e2e-worker-loop-smoke.py`, `python3 examples/auto-research-visible-worker-hook-smoke.py`, and `loopx check --scan-path docs/showcases --scan-path docs/guides` |
| GH-C49 | dashboard | Polish the shipped `/frontstage` goal-channel board: improve visual acceptance, local demo fixture clarity, and operator onboarding while keeping browser data read-only and making outcome, lease, capability-wait, and workspace-repair states legible. | `npm run smoke:frontstage-route`, `npm run smoke:frontstage-browser`, and `loopx check --scan-path apps/presentation/dashboard --scan-path docs/dashboard-frontend-selection.md` |
| GH-C50 | control plane | Implement the first generic `observable_artifact_handle_v0` slice from `docs/product/domain-capability-packs.md`: compact handle, allowed poll command, artifact refs, terminal markers, and read-boundary flags for long-running work without assuming a benchmark, CI, deployment, or ML experiment adapter. | Focused fixture smoke plus `loopx check --scan-path docs/product/domain-capability-packs.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C73 | reporting showcase | Add a public no-sink periodic-report walkthrough: normalize one synthetic project snapshot, evaluate a material trigger, render the same report as Markdown and dense HTML, prove content parity, and leave publication to an optional adapter. | `python3 examples/periodic-report-smoke.py`, `python3 examples/periodic-report-html-smoke.py`, and `loopx check --scan-path docs/capabilities/periodic-report --scan-path docs/showcases --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C60 | workflow | Add focused connector parity coverage for Codex App heartbeat, Codex CLI TUI, LoopX Turn, Claude Code loop, OpenCode, shell worker, HTTP webhook, and worker bridge. First close OpenCode identity parity across `host_mode_plan_v0` and the runtime connector catalog, then assert authoritative interaction actions, scoped identity, runtime-owned cadence, no-spend transitions, workspace repair, and private-boundary stripping. | `python3 examples/host-mode-plan-smoke.py`, `python3 examples/project/host-mode-plan-cli-smoke.py`, focused OpenCode bridge tests, `python3 -m pytest -q tests/test_loopx_turn_transaction.py`, and `loopx check --scan-path docs/runtime-connector-catalog.md --scan-path docs/reference/protocols/host-mode-plan-v0.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C59 | status | Add a focused hot-path perf smoke for large ignored state trees and a bounded cold-path todo detail contract so `status` / `quota` stay fast without dropping public-safe backlog drill-down. | Focused perf/fixture smoke plus `loopx check --scan-path docs/status-data-contract.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C61 | cli | Implement the next canonical global manager command after `/loopx-global-summary`: choose one of `/loopx-global-gates`, `/loopx-global-todos`, `/loopx-global-risks`, or `/loop-goal-summary`, keep it read-only, source it from compact status/quota/todo/run-history projections, and make unknown aliases fail closed with help instead of broad dumps. | Focused command smoke plus `python3 examples/project/global-manager-command-protocol-smoke.py` and `loopx check --scan-path docs/reference/protocols/global-manager-command-v0.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C62 | governance | Add a visible governance/budget projection slice: show per-goal or per-agent claim, optional task lease, quota state, scheduler hint, applicable decision scopes, approval requirement, and allowed next action in a compact operator-facing shape. Do not add a browser write API, infer scopes from prose, or present lease ownership as runtime authority. | Focused fixture smoke plus `python3 -m pytest -q tests/control_plane/test_todo_decision_scope_lifecycle.py` and `loopx check --scan-path docs/status-data-contract.md --scan-path docs/interface-budget-contract.md --scan-path docs/frontstage-channel-lease-roadmap.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C67 | issue-fix | Render `issue_fix_outcome_projection_v0` in one public operator surface with a synthetic revision-pinned fixture. Show selected issue, stage, validation, PR state, outputs, risks, terminal outcome, and clearly advisory Reward Memory hints without creating another case ledger or exposing provider, sink, or private notification state. | `python3 examples/issue-fix-outcome-projection-smoke.py`, `python3 examples/reward-memory-candidate-review-smoke.py`, the selected surface smoke, and `loopx check --scan-path docs/capabilities/issue-fix --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C68 | validation | Move the stable pure rules from one oversized control-plane smoke, preferably `quota-scheduler-state-ack-smoke.py`, into independently derived pytest decision tables while retaining a thin CLI/public-behavior seam. Add at least one negative or mutation case so current implementation output cannot become the oracle. | Focused pytest, the retained smoke, `python3 examples/full-public-smokes-workflow-smoke.py`, and `git diff --check` |
| GH-C69 | explore | Add a public-safe local fixture and contributor walkthrough for canonical, executive, and semantic owner-board Explore views. Prove decision/evidence lineage and readability without enabling an external sink or depending on local/private graph sources. | `python3 examples/explore-result-layer-smoke.py`, `python3 -m pytest -q tests/test_explore_presentation_views.py`, and `loopx check --scan-path docs/capabilities/explore --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C70 | runtime | Add a provider-neutral fake-host LoopX Turn walkthrough outside SkillsBench. Cover compact request, planned effects, committed receipts, independent validation, resume/recovery, and terminal no-followup behavior without retaining raw sessions or host-local paths. | New focused fake-host smoke, `python3 -m pytest -q tests/test_loopx_turn_driver.py tests/test_loopx_turn_transaction.py`, and `loopx check --scan-path docs/reference/protocols/loopx-turn-v0.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C71 | learning | Add a contributor-safe Reward Memory walkthrough from corpus health and candidate review through opt-in recall/application and scoped feedback. Use synthetic fixtures, keep hints advisory, fail closed without activation, and do not require an external sink or provider payload. | `python3 examples/reward-memory-corpus-registry-smoke.py`, `python3 examples/reward-memory-candidate-review-smoke.py`, `python3 examples/reward-memory-recall-application-smoke.py`, and `loopx check --scan-path docs/reference/protocols/reward-memory-architecture-v0.md --scan-path CONTRIBUTOR_TASKS.md` |

### Advanced Implementation

Shared-state, adapter, or benchmark-control changes. Please open an issue first
and keep the first PR as a narrow slice.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C07 | state | Add structured-state write serialization for todo/refresh/history writers using a per-goal lock or optimistic revision guard. Include a concurrent todo add/update regression. | New concurrency regression plus `python3 -m py_compile loopx/*.py` |
| GH-C15 | benchmark | Implement benchmark ledger drift warning: when compact run history has a benchmark result but `benchmark-run-ledger.json/md` lacks the row, status should warn or closeout should auto-upsert. Keep raw task/log/trajectory material out. | `python3 examples/benchmark-run-ledger-smoke.py` |
| GH-C16 | benchmark | Add a public-safe trajectory-summary contract for non-SkillsBench adapters so Terminal-Bench/SWE/ALE can expose comparable counters without raw task text, logs, verifier output, or trajectory bodies. | New unit/fake fixture smoke |
| GH-C47 | state | Adopt the shipped optional `task_lease_v0` in one real host integration: advertise the capability explicitly, preserve soft-claim routing, expose acquire/renew/transfer/release outcomes, and prove overlapping write scopes fail without making `quota should-run` enforce undeclared lease authority. | `python3 examples/control_plane/task-lease-runtime-smoke.py`, `python3 -m pytest -q tests/control_plane/test_task_lease.py`, and a host-focused fake fixture |
| GH-C72 | workflow runtime | Implement the P0 pure Turn Loop Controller transition contract above. Consume one Turn receipt plus a fresh quota/scheduler decision and return one typed next disposition without launching a host, sleeping, writing state, or spending quota. Cover replan with a required todo/vision delta before any successor Turn. | Focused decision-table pytest plus `python -m pytest -q tests/test_loopx_turn_driver.py tests/test_loopx_turn_executor.py tests/test_loopx_turn_transaction.py`, `python examples/autonomous-replan-obligation-smoke.py`, and `loopx check --scan-path CONTRIBUTOR_TASKS.md --scan-path CONTRIBUTING.md` |

### Design / RFC

Direction-setting work. These tasks should usually produce a doc or issue
before implementation.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C35 | integration | Design a provider-neutral external-host adapter on top of LoopX Turn and TurnEnvelope: map compact session events into requests, planned effects, committed receipts, independent validation, recovery, and attention items while keeping raw transcripts, credentials, billing, permissions, and product frontstage outside LoopX. | Design note with adapter-neutral fake-host smoke plan |
| GH-C37 | interaction model | Curate the interaction pattern catalog with one new public-safe good/bad case, including trigger signals, user channel, agent channel, state contract, bad smell, and validation reference. Do not copy raw chat, private benchmark artifacts, or internal links. | `loopx check --scan-path docs/interaction-pattern-catalog.md` |

### Maintainer-Owned / Coordination Required

Visible work that should not be duplicated. Ask for a public helper slice
instead of launching private runs or broad product changes.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C18 | benchmark | Long-horizon benchmark evidence program, including live local no-upload cases, runner contracts, trace retention, score accounting, and good/bad case attribution. Do not duplicate live runs or inspect private artifacts unless maintainers split out a public helper issue. | Maintainer-run benchmark ledger and public/private scan |
| GH-C19 | benchmark | Main-table SkillsBench product-mode comparison: raw Codex autonomous max5 versus the qualified LoopX Turn route, no verifier feedback to either arm, stop on reward 1 or declared done. Live matched pairs and official/countable receipt review remain maintainer-owned; external contributors can help with synthetic schema, docs, reducers, and smokes only. | Maintainer-run compact ledger, case-analysis update, and public receipt/boundary scan |

## Projection Sources

This board is maintained from public-safe projections of:

- the local `loopx-meta` Agent Todo list;
- public docs under `docs/`, especially the state interaction model, status
  data contract, quota allocation, integration guide, product vision, and
  benchmark research docs;
- recent maintainer review of which work is externally claimable versus
  maintainer-owned live automation.

Projection rules:

- copy the task intent, not private evidence details;
- convert private benchmark runs into public helper slices unless maintainers
  explicitly publish a runnable issue;
- mark live benchmark, release, and automation lanes as `Maintainer-owned`
  when duplicate work would waste compute or weaken evidence;
- prefer tasks that name likely files and validation, so contributors can start
  without reading local active state.

## Suggested Labels

Use these labels on GitHub issues when possible:

- `good first issue`: small, well-scoped, low setup, with files and validation
  called out.
- `help wanted`: useful public task where the approach is clear enough for an
  external contributor.
- `claimed`: someone is actively working on the issue.
- `maintainer-owned`: visible work that should not be duplicated.
- `needs design`: implementation is not ready until the design is agreed.
- `blocked`: waiting on a decision, dependency, or maintainer action.
- Area labels such as `area: docs`, `area: cli`, `area: status`,
  `area: benchmark`, `area: dashboard`, and `area: tests`.

## Maintainer Update Rules

- Keep this board curated. If it grows beyond roughly 35 open rows, move older
  or lower-priority work into GitHub issues and keep only the best entry points
  here.
- Every public task should include a scope, expected validation, and owner
  state.
- Do not publish private/local state. Summarize it into a public task only when
  the work is safe for the repository.
- After a meaningful internal milestone, update this board manually if there is
  a new contributor-sized slice.
- Remove or refresh stale tasks instead of leaving obsolete "good first issue"
  entries in place.
