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

## Recent Maintainer Progress

These public milestones changed which tasks are still useful contributor entry
points:

| Area | Landed | Contributor implication |
| --- | --- | --- |
| Benchmark workflow | `939b02c` added ECS bootstrap tooling, Terminal-Bench no-upload smoke tooling, and a compact compose-startup reducer. SkillsBench verifier dependency prewarm now follows the same public-safe plan/smoke shape. | Do not recreate the ECS substrate. Help by extending the same wrapper/reducer shape to ALE, deepening SkillsBench no-upload case launch reducers, or improving route labels and public-safe reducers. |
| Autonomous replan | `d1f955a` made the autonomous-replan obligation smoke run in-process by default, with bounded subprocess coverage. | The broad smoke-performance cleanup is done. Future work should be a narrow regression or timeout guard, not another full rewrite. |
| Product vision | `1813744` added `docs/product/vision.md` and moved the creator-operator case into the public product direction. | Creator/operator work is now a first-class public productization track, not only a local maintainer todo. |
| Multi-agent coordination | `cb9f899`, `0f1ca9b`, `e73f9f1`, and `9acdaa2` landed soft todo claims, identity-aware heartbeat prompts, and side-agent self-merge policy. | Next public slices are agent profiles, side-agent worktree guardrails, and hard per-todo leases. |
| Showcases and README | `a384f41` and `f521471` made the public showcase catalog and README landing clearer. | New narrative work should add cases, visuals, or demo surfaces, not rebuild the landing-page frame. |
| Side-agent worktree guard | `47841a9`, `afc6aa7`, and the contributor-facing contract example made `quota should-run` / `spend-slot` fail closed when a side agent runs from the registered primary checkout. The status contract now also frames `workspace_guard` as an agent-channel repair for dashboard/review-packet consumers. | Do not duplicate the base guard, basic CLI example, or projection copy. Helpful follow-ups are claim-aware selection regressions and real UI rendering. |
| Reward-style replanning | `docs/product/reward-style-replanning.md` defines public-safe `replan_hint_v0` semantics: hints may reorder candidates but cannot override gates, claims, scope, capabilities, or boundaries. | The design note is done. Next slices should preview hints from compact reward/todo evidence and prove the hard-boundary precedence rules. |
| Goal channel projection | `4b5b46c` defined `goal_channel_projection_v0`; `6d37e3f` added the compact projection builder; `38bb58c` rendered it into static read-only frontstage HTML; the status feed now exports the same projection on `attention_queue.items[].goal_channel_projection`; the React `/frontstage` route now renders the projection as a read-only channel board with decision, quota, todo, claim, gate, timeline, warning, and truth-contract lanes. | Do not rebuild the base channel route. Helpful follow-ups are visual-acceptance polish, operator onboarding copy, richer local demo fixtures, and small interaction refinements that keep browser write authority outside the frontstage. |
| Benchmark lifecycle core | `loopx/benchmark_core/lifecycle.py`, `docs/research/long-horizon-agent-benchmarks/benchmark-core-adapter-contract-v0.md`, and `examples/benchmark-core-adapter-contract-smoke.py` define the adapter-neutral `preflight -> launch -> observe -> ingest -> classify -> ledger` contract and canonical lifecycle phases. | Do not recreate GH-C20. Useful follow-ups are GH-C21 accounting split, GH-C22 observable handles, and adapter-specific reducer adoption. |
| Benchmark run permission policy | `loopx/benchmark_core/run_permissions.py` and `examples/benchmark-run-permission-policy-smoke.py` define `run_permission_policy_v0` plus quota projection for local no-upload benchmark runs. | Do not recreate GH-C23. Useful follow-ups are adapter-by-adapter launch packet adoption and UI display of `goal_boundary.run_permission_policy`. |
| Benchmark attempt accounting | `loopx/benchmark_core/attempts.py` and `examples/benchmark-attempt-accounting-smoke.py` define `benchmark_attempt_accounting_v0` with launcher/case/solver/verifier/official-score attempt phases and generic failure classes. | Do not recreate GH-C21. Useful follow-ups are adapter-by-adapter reducer adoption and ledger rendering of the split counts. |

### Starter / Good First

Low setup, docs-first, or narrow fixture work. These should be good entry
points for contributors who are still learning the repository.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C01 | docs | Add a short "first goal" walkthrough that starts with `loopx demo`, inspects status/history, completes one todo, and shows the next todo. | `loopx check --scan-path README.md --scan-path docs/ --scan-path examples/` |
| GH-C02 | tests | Add or extend a focused smoke test around todo archive/completion behavior. Prefer copying the style of `examples/todo-lifecycle-cli-smoke.py`. | `python3 examples/todo-lifecycle-cli-smoke.py` and `python3 -m py_compile loopx/*.py` |
| GH-C04 | docs | Improve README troubleshooting for install, PATH setup, canary/default wrappers, and `loopx doctor`. | `loopx check --scan-path README.md --scan-path CONTRIBUTING.md` |
| GH-C09 | diagnostics | Inspect duplicate run-history index rows with `history inspect-index-duplicates`, then document the current repair path. This is docs-first; code fix can be a follow-up. | `loopx check --scan-path docs/ --scan-path README.md` |
| GH-C10 | docs | Add a public "what counts as a good smoke" guide using `CONTRIBUTING.md` and recent benchmark-smoke cleanup as source material. | `loopx check --scan-path CONTRIBUTING.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C13 | docs | Expand public/private boundary examples with realistic safe and unsafe snippets for benchmark traces, active state, local paths, credentials, and compact artifacts. | `loopx check --scan-path docs/public-private-boundary.md --scan-path examples/` |
| GH-C30 | docs | Add a "project asset contract" explainer showing owner, gate, next action, stop condition, last evidence, next safe command, user todo, agent todo, support mode, and fresh status projection. | `loopx check --scan-path docs/ --scan-path README.md` |

### Focused Implementation

Small-to-medium code changes with a clear validation surface. These are good
for contributors who can run local CLI smokes and keep changes scoped.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C03 | diagnostics | Improve duplicate run-history index diagnostics so `loopx check` gives the next repair action, not only a warning. Include a small fixture or smoke path if practical. | `loopx check --scan-root .` plus focused smoke if added |
| GH-C05 | regression | Create the first `regression/` case for a previously observed control-plane stall, such as external-evidence waits, P0-blocked/P1 fallback, compact blocker writeback, or no-progress self-repair. | Focused regression command plus `python3 -m py_compile loopx/*.py` |
| GH-C06 | cli | Start CLI modularization by defining a `loopx/cli_commands/` command-module contract and migrating one low-risk command group while preserving old invocations. | Old command smoke plus `python3 -m py_compile loopx/*.py` |
| GH-C08 | status | Improve agent todo projection so `status` / `quota should-run` can expose a broader priority-sorted backlog without letting monitor items hide executable work. | `loopx --format json status` fixture or focused smoke |
| GH-C14 | protocol | Add a focused regression for protocol action packet output so future Codex CLI wrappers cannot accidentally invoke model APIs or runner adapters from the decision-only path. | `python3 examples/protocol-action-packet-smoke.py` or new focused smoke |
| GH-C22 | benchmark | Add launch artifact observable handles: pid/process state, job basename, compact artifact refs, allowed poll command, and read-boundary flags so heartbeat observation does not depend on chat memory. | Focused fake launch artifact smoke |
| GH-C40 | benchmark | Extend the benchmark developer workflow product path after the ECS tooling landed: add ALE compact readiness/blocker commands and deepen SkillsBench no-upload case-launch reducers that follow the same wrapper/reducer shape without launching private benchmark jobs or copying raw artifacts. | `python3 examples/benchmark-developer-workflow-doc-smoke.py`, `python3 examples/benchmark-ecs-developer-tooling-smoke.py`, and a new focused smoke if code is added |
| GH-C41 | benchmark | Add an explicit benchmark route label/policy that separates `cloud_codex_default`, `split_control_fallback`, and `upstream_adapter_branch`, so legacy bridge probes and benchmark-fork patches cannot be mistaken for clean product-path evidence. | Policy fixture plus `python3 examples/benchmark-developer-workflow-doc-smoke.py` |
| GH-C42 | benchmark | Retire split-control from the main benchmark attention path after the first cloud-host smoke succeeds or reaches a concrete gate: keep durable contracts/reducers, move new local-Codex/remote-executor experiments to a labeled experimental branch, and delete or defer bridge code that the cloud route no longer needs. | Inventory note plus `python3 examples/benchmark-developer-workflow-doc-smoke.py` |
| GH-C28 | planning | Implement local-only dry-run proposal generation for dreaming: read public-safe run history/project state and emit proposal records without mutating project truth. | Dry-run smoke with fake project state |
| GH-C43 | product docs | Turn `docs/product/vision.md` into a public-safe creator-operator showcase skeleton under `docs/showcases/`, using only synthetic/redacted evidence and no private platform data. | `python3 examples/showcase-catalog-smoke.py` plus `loopx check --scan-path docs/product --scan-path docs/showcases` |
| GH-C44 | dashboard | Draft the non-technical operator status model: map LoopX status fields to plain-language cards such as "what happened", "what is blocked", "what comes next", and "what feedback would change". | `loopx check --scan-path docs/product --scan-path docs/status-data-contract.md --scan-path docs/dashboard-frontend-selection.md`; dashboard fixture if added |
| GH-C45 | coordination | Add a claim-aware selection regression for side agents after the `workspace_guard` projection copy: side agents should see why a primary-owned todo is skipped, then pick an in-scope unclaimed/side-agent todo or create a primary review successor. | Focused smoke around `workspace_guard`, `claimed_by`, side-agent identity, and handoff surfaces |
| GH-C49 | dashboard | Polish the shipped `/frontstage` goal-channel board: improve visual acceptance coverage, local demo fixture clarity, and operator onboarding affordances while keeping `attention_queue.items[].goal_channel_projection` read-only browser data. | `npm run smoke:frontstage-route`, `npm run smoke:frontstage-browser`, and `loopx check --scan-path apps/dashboard --scan-path docs/dashboard-frontend-selection.md` |
| GH-C50 | control plane | Implement the first generic `observable_artifact_handle_v0` slice from `docs/product/domain-capability-packs.md`: compact handle, allowed poll command, artifact refs, terminal markers, and read-boundary flags for long-running work without assuming a benchmark, CI, deployment, or ML experiment adapter. | Focused fixture smoke plus `loopx check --scan-path docs/product/domain-capability-packs.md --scan-path CONTRIBUTOR_TASKS.md` |

### Advanced Implementation

Shared-state, adapter, or benchmark-control changes. Please open an issue first
and keep the first PR as a narrow slice.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C07 | state | Add structured-state write serialization for todo/refresh/history writers using a per-goal lock or optimistic revision guard. Include a concurrent todo add/update regression. | New concurrency regression plus `python3 -m py_compile loopx/*.py` |
| GH-C15 | benchmark | Implement benchmark ledger drift warning: when compact run history has a benchmark result but `benchmark-run-ledger.json/md` lacks the row, status should warn or closeout should auto-upsert. Keep raw task/log/trajectory material out. | `python3 examples/benchmark-run-ledger-smoke.py` |
| GH-C16 | benchmark | Add a public-safe trajectory-summary contract for non-SkillsBench adapters so Terminal-Bench/SWE/ALE can expose comparable counters without raw task text, logs, verifier output, or trajectory bodies. | New unit/fake fixture smoke |
| GH-C46 | coordination | Implement the `agent_profile_v0` contract from `docs/product/agent-profile-contract.md`: registry validation, `heartbeat-prompt --agent-id` profile resolution without repeated `--agent-scope`, and read-only `agent_member_v0` status/review projection. | Configure/heartbeat prompt smokes, status/review projection smoke, plus `python3 -m py_compile loopx/*.py` |
| GH-C47 | state | Promote soft todo claims toward `task_lease_v0`: per-`(goal_id, todo_id)` lease key, TTL, idempotency key, write-scope conflict policy, renew/transfer semantics, and status/quota projection. | Concurrent todo/lease smoke plus `python3 -m py_compile loopx/*.py` |

### Design / RFC

Direction-setting work. These tasks should usually produce a doc or issue
before implementation.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C25 | server | Implement the first server-roadmap slice from `docs/architecture.md`: file-backed per-goal writer serialization plus idempotency keys for one narrow write path, with CLI-only fallback preserved. | Concurrency regression plus `python3 -m py_compile loopx/*.py` |
| GH-C32 | learning | Implement the first read-only reward-style hint preview from `docs/product/reward-style-replanning.md`: derive compact candidate-ranking hints from public-safe reward/todo evidence without writing durable hints yet. | Preview smoke proving hints can reorder safe candidates but cannot override user gates, claims, scopes, capability gates, or workspace guards |
| GH-C33 | resource sync | After server/daemon design lands, define periodic Resource-to-Todo sync as a planning-queue producer: compare repo docs, roadmap/status contracts, and authority commitments against active todos, then propose updates through structured lifecycle APIs before promotion. | Design note; implementation blocked on server lane |
| GH-C35 | integration | Design a session-runtime control-plane adapter: read compact session/event/outcome/approval summaries from an external agent host, project LoopX attention items, and keep raw transcripts, credentials, billing, permissions, and product frontstage outside LoopX. | Design note with adapter-neutral smoke plan |
| GH-C37 | interaction model | Curate the interaction pattern catalog with one new public-safe good/bad case, including trigger signals, user channel, agent channel, state contract, bad smell, and validation reference. Do not copy raw chat, private benchmark artifacts, or internal links. | `loopx check --scan-path docs/interaction-pattern-catalog.md` |
| GH-C39 | interaction model | Design explicit `decision_scope` / `required_decision_scopes` metadata for user gates and agent todos so scoped fallback does not rely on prompt memory or text inference. | RFC update to `docs/interaction-pattern-catalog.md` plus one projection fixture |
| GH-C48 | product | Design the creator-ops fake-data demo storyboard: trend discovery -> preference map -> insight board -> draft queue -> material library -> human feedback -> controlled replan. Use synthetic/public-safe data only. | Storyboard doc under `docs/product/` or `docs/showcases/` plus `loopx check --scan-path docs/product --scan-path docs/showcases` |
| GH-C49 | policy | Define the creator-ops feedback and boundary contract: how non-technical user feedback becomes gates, preferences, todo updates, or product-improvement notes while preserving source attribution, platform terms, no-autopublish gates, and private creative-material boundaries. | Contract/RFC under `docs/product/` plus `loopx check --scan-path docs/product --scan-path docs/public-private-boundary.md` |
| GH-C51 | capability packs | Design `domain_pack_contract_v0` and suggest-only `domain_pack_detection_v0`: packs default off, detection recommends enablement without writing domain conclusions, and first enablement requires registry or owner authority. | RFC update plus `loopx check --scan-path docs/product/domain-capability-packs.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C52 | ML experiment pack | Draft the read-only/advisory `ml_experiment` pack contract: `ml_experiment_result_v0`, `dataset_window_contract_v0`, `hypothesis_ledger_v0`, and `experiment_replan_preview`, with launch/stop/restart explicitly excluded until delivery mode is authorized. | Design note or fixture under `docs/product/` or `docs/reference/protocols/` plus public/private scan |

### Maintainer-Owned / Coordination Required

Visible work that should not be duplicated. Ask for a public helper slice
instead of launching private runs or broad product changes.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C18 | benchmark | Long-horizon benchmark evidence program, including live local no-upload cases, runner contracts, trace retention, score accounting, and good/bad case attribution. Do not duplicate live runs or inspect private artifacts unless maintainers split out a public helper issue. | Maintainer-run benchmark ledger and public/private scan |
| GH-C19 | benchmark | Main-table SkillsBench product-mode comparison: raw Codex autonomous max5 versus LoopX state/todo/replan/CLI, no verifier feedback to either arm, stop on reward 1 or declared done. External contributors can help with schema/docs/smokes only. | Maintainer-run compact ledger and case-analysis update |

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
