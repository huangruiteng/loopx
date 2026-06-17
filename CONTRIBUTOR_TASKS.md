# Contributor Task Board

This board is the public, contributor-facing projection of Goal Harness work.
It is intentionally different from `.local` active goal state:

- this file lists public work that can be discussed, claimed, reviewed, and
  validated in the repository;
- `.local`, `.goal-harness`, and live `ACTIVE_GOAL_STATE.md` files remain local
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

### Starter / Good First

Low setup, docs-first, or narrow fixture work. These should be good entry
points for contributors who are still learning the repository.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C01 | docs | Add a short "first goal" walkthrough that starts with `goal-harness demo`, inspects status/history, completes one todo, and shows the next todo. | `goal-harness check --scan-path README.md --scan-path docs/ --scan-path examples/` |
| GH-C02 | tests | Add or extend a focused smoke test around todo archive/completion behavior. Prefer copying the style of `examples/todo-lifecycle-cli-smoke.py`. | `python3 examples/todo-lifecycle-cli-smoke.py` and `python3 -m py_compile goal_harness/*.py` |
| GH-C04 | docs | Improve README troubleshooting for install, PATH setup, canary/default wrappers, and `goal-harness doctor`. | `goal-harness check --scan-path README.md --scan-path CONTRIBUTING.md` |
| GH-C09 | diagnostics | Inspect duplicate run-history index rows with `history inspect-index-duplicates`, then document the current repair path. This is docs-first; code fix can be a follow-up. | `goal-harness check --scan-path docs/ --scan-path README.md` |
| GH-C10 | docs | Add a public "what counts as a good smoke" guide using `CONTRIBUTING.md` and recent benchmark-smoke cleanup as source material. | `goal-harness check --scan-path CONTRIBUTING.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C13 | docs | Expand public/private boundary examples with realistic safe and unsafe snippets for benchmark traces, active state, local paths, credentials, and compact artifacts. | `goal-harness check --scan-path docs/public-private-boundary.md --scan-path examples/` |
| GH-C30 | docs | Add a "project asset contract" explainer showing owner, gate, next action, stop condition, last evidence, next safe command, user todo, agent todo, support mode, and fresh status projection. | `goal-harness check --scan-path docs/ --scan-path README.md` |

### Focused Implementation

Small-to-medium code changes with a clear validation surface. These are good
for contributors who can run local CLI smokes and keep changes scoped.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C03 | diagnostics | Improve duplicate run-history index diagnostics so `goal-harness check` gives the next repair action, not only a warning. Include a small fixture or smoke path if practical. | `goal-harness check --scan-root .` plus focused smoke if added |
| GH-C05 | regression | Create the first `regression/` case for a previously observed control-plane stall, such as external-evidence waits, P0-blocked/P1 fallback, compact blocker writeback, or no-progress self-repair. | Focused regression command plus `python3 -m py_compile goal_harness/*.py` |
| GH-C06 | cli | Start CLI modularization by defining a `goal_harness/cli_commands/` command-module contract and migrating one low-risk command group while preserving old invocations. | Old command smoke plus `python3 -m py_compile goal_harness/*.py` |
| GH-C08 | status | Improve agent todo projection so `status` / `quota should-run` can expose a broader priority-sorted backlog without letting monitor items hide executable work. | `goal-harness --format json status` fixture or focused smoke |
| GH-C11 | fresh clone | Harden the fresh-clone public user path: install wrapper, PATH, `doctor`, `demo`, `status`, dashboard status export, and project skill install/update. | Fresh checkout notes plus runnable smoke or checklist |
| GH-C12 | dashboard | Add a first-screen status/dashboard acceptance smoke that verifies goal name, waiting owner, recommended action, safety boundary, first user todo, and highest-priority agent todo appear before raw run-history drilldown. | Dashboard/status smoke or fixture |
| GH-C14 | protocol | Add a focused regression for protocol action packet output so future Codex CLI wrappers cannot accidentally invoke model APIs or runner adapters from the decision-only path. | `python3 examples/protocol-action-packet-smoke.py` or new focused smoke |
| GH-C22 | benchmark | Add launch artifact observable handles: pid/process state, job basename, compact artifact refs, allowed poll command, and read-boundary flags so heartbeat observation does not depend on chat memory. | Focused fake launch artifact smoke |
| GH-C27 | planning | Add a contract regression separating autonomous replan from dreaming: autonomous replan is must-attempt bounded delivery/control-plane repair; dreaming is advisory, operator-gated, and must not emit `agent_command`. | Focused quota/status smoke |
| GH-C28 | planning | Implement local-only dry-run proposal generation for dreaming: read public-safe run history/project state and emit proposal records without mutating project truth. | Dry-run smoke with fake project state |

### Advanced Implementation

Shared-state, adapter, or benchmark-control changes. Please open an issue first
and keep the first PR as a narrow slice.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C07 | state | Add structured-state write serialization for todo/refresh/history writers using a per-goal lock or optimistic revision guard. Include a concurrent todo add/update regression. | New concurrency regression plus `python3 -m py_compile goal_harness/*.py` |
| GH-C15 | benchmark | Implement benchmark ledger drift warning: when compact run history has a benchmark result but `benchmark-run-ledger.json/md` lacks the row, status should warn or closeout should auto-upsert. Keep raw task/log/trajectory material out. | `python3 examples/benchmark-run-ledger-smoke.py` |
| GH-C16 | benchmark | Add a public-safe trajectory-summary contract for non-SkillsBench adapters so Terminal-Bench/SWE/ALE can expose comparable counters without raw task text, logs, verifier output, or trajectory bodies. | New unit/fake fixture smoke |

### Design / RFC

Direction-setting work. These tasks should usually produce a doc or issue
before implementation.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C17 | benchmark | Design per-round artifact snapshot/restore for blind-loop benchmark runs so `best_score` can become an executable final-selection policy, not only an offline metric. | Design note with stop conditions and public/private boundary |
| GH-C20 | benchmark | Define runner-agnostic benchmark lifecycle schema: `launch -> observe -> ingest -> classify -> ledger`, with stages such as process started, job materialized, trial started, worker started, result written, verifier scored. | Design doc plus one adapter-neutral fixture |
| GH-C21 | benchmark | Split benchmark accounting into launcher attempt, case attempt, solver attempt, verifier attempt, and official-score attempt. Launcher/materialization failures must not count as case failures. | Design doc or focused ledger fixture |
| GH-C23 | policy | Replace narrative benchmark authorization with `run_permission_policy_v0`: allowed local no-upload model/Docker/Harbor actions, forbidden upload/leaderboard/public claim/production/cloud actions, timeout budget, and compact-only observation. | Schema note plus projection smoke |
| GH-C24 | adapters | Plan adapter lifecycle rollout from Terminal-Bench to SkillsBench, SWE, and ALE using the same lifecycle/failure schema while keeping benchmark-specific runner details inside adapters. | Design note accepted by maintainers |
| GH-C25 | server | Implement the first server-roadmap slice from `docs/architecture.md`: file-backed per-goal writer serialization plus idempotency keys for one narrow write path, with CLI-only fallback preserved. | Concurrency regression plus `python3 -m py_compile goal_harness/*.py` |
| GH-C26 | planning | Define server-managed dreaming/planning semantics: background planning may propose ranked todos and evidence probes but must not execute protected work or spend delivery quota. | Design note plus no-execution fixture |
| GH-C29 | dashboard | Add dashboard/status design for a separate Dreaming lane or badge beside delivery and operator gates, so exploration proposals do not interrupt active project agents. | Dashboard design note or fixture |
| GH-C31 | project intake | Prepare a read-only observer / authority-map intake for a complex open-source project. It should produce only a compact project map and missing-gate list before any write-control or private material access. | Design note plus dry-run map fixture |
| GH-C32 | learning | Design public-safe reward-style learning for replanning: turn explicit reward/corrections into compact ranking hints without storing raw private chat or treating inferred preferences as hard gates. | Design note with privacy constraints |
| GH-C33 | resource sync | After server/daemon design lands, define periodic Resource-to-Todo sync that compares repo docs, roadmap/status contracts, and authority commitments against active todos, then proposes updates through structured lifecycle APIs. | Design note; implementation blocked on server lane |
| GH-C34 | orchestration | Design `task_graph_projection_v0` as an optional derived view over todos, gates, leases, run ids, and event-ledger state. It must help multi-stage repair/verification without making graph files a second truth source. | Design note plus one status/review-packet fixture |
| GH-C35 | integration | Design a host integration surface for Goal Harness hook/MCP/server adapters: hook activation, lifecycle reads, todo/gate/lease writes, and compact status projection, while keeping CLI compatibility and public/private boundaries. | Design note with adapter-neutral smoke plan |
| GH-C36 | narrative | Prepare a public-safe blocked-priority fallback demo: a fake benchmark rotation where one lane is user-gated and the harness continues a safe fallback while preserving the blocked gate, quota decision, and evidence boundary. Do not use private raw benchmark artifacts. | Demo fixture or doc plus `goal-harness check --scan-path README.md --scan-path docs/outreach/xiaohongshu-launch-draft.md` |
| GH-C37 | interaction model | Curate the interaction pattern catalog with one new public-safe good/bad case, including trigger signals, user channel, agent channel, state contract, bad smell, and validation reference. Do not copy raw chat, private benchmark artifacts, or internal links. | `goal-harness check --scan-path docs/interaction-pattern-catalog.md` |
| GH-C38 | narrative | Create a public-safe visual or short animated demo storyboard for one interaction pattern, starting with blocked-priority fallback. Use fake data, show user/agent/Goal Harness channels, and keep raw benchmark evidence out. | Storyboard, Mermaid/SVG, or video script plus `goal-harness check --scan-path docs/interaction-pattern-catalog.md` |

### Maintainer-Owned / Coordination Required

Visible work that should not be duplicated. Ask for a public helper slice
instead of launching private runs or broad product changes.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C18 | benchmark | Long-horizon benchmark evidence program, including live local no-upload cases, runner contracts, trace retention, score accounting, and good/bad case attribution. Do not duplicate live runs or inspect private artifacts unless maintainers split out a public helper issue. | Maintainer-run benchmark ledger and public/private scan |
| GH-C19 | benchmark | Main-table SkillsBench product-mode comparison: raw Codex autonomous max5 versus Goal Harness state/todo/replan/CLI, no verifier feedback to either arm, stop on reward 1 or declared done. External contributors can help with schema/docs/smokes only. | Maintainer-run compact ledger and case-analysis update |

## Projection Sources

This board is maintained from public-safe projections of:

- the local `goal-harness-meta` Agent Todo list;
- public docs under `docs/`, especially the state interaction model, status
  data contract, quota allocation, integration guide, and benchmark research
  docs;
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
