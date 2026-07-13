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
| Runtime connector modes | The connector catalog names Codex App heartbeat, Codex CLI TUI, Claude Code loop, shell worker, HTTP webhook, and worker bridge as first-class modes; thin prompts and TurnEnvelope-style action contracts keep host context bounded. | Make mode selection visible and explicit. TUI, headless, IM/gateway, and hybrid handoffs are all valid product paths when they preserve identity, quota, capabilities, and writeback. |
| Visible governance | Quota, scheduler hints, user gates, peer claims, optional task leases, typed continuation, repository policy, and interface budgets already exist in machine contracts. | Show who can act, who must approve, what budget was spent, and how pause/override/terminate decisions map back to LoopX state without treating claims or leases as a new runtime hierarchy. |
| Domain packs | Domain capability packs default off; ML experiment and scenario/productization work should stay advisory until enabled by registry or owner authority. | Add suggest-only previews or public-safe fixtures before any domain-specific autonomy, launch, or production action. |

## Recent Maintainer Progress

These public milestones changed which tasks are still useful contributor entry
points:

| Area | Landed | Contributor implication |
| --- | --- | --- |
| Issue-fix productization | `b707dda8` added the revision-pinned `issue_fix_outcome_projection_v0`; `d922a98a`, `7c1fc27c`, and `4b1c20fb` then tightened memory/feedback guidance, semantic preferences, and PR closing references. | Do not add another issue ledger or review-routing state machine. Useful slices render the existing outcome projection, add synthetic contributor fixtures, or clarify provider-neutral memory and feedback boundaries. |
| Explore and showcases | `92e297f3` published the Auto Research long-running showcase; `07f8b8ef`, `10f7acbb`, and follow-up fixes added same-source canonical/executive views plus a semantic owner-board renderer. | Extend the shipped story with public fixtures, accessibility and visual-acceptance coverage, or local no-sink walkthroughs. Do not rebuild the README hero or publish private graph sources. |
| Peer coordination | The v0.2 peer runtime keeps claims as routing signals. `d173fee4`, `b45191be`, and `653a75d9` hardened the optional `task_lease_v0` owner/conflict rules and split durable rules into pytest. | Adopt the shipped lease contract in one host or operator view at a time; do not turn leases into hierarchy or make quota enforce an undeclared host capability. |
| CLI/runtime boundaries | `d0d5e5f4`, `143653d7`, `e275f9be`, and `b6c78956` retired duplicate wrappers and added right-sized module, typing, and import-boundary budgets. | Characterize behavior before moving it. Useful follow-ups extract one cohesive ownership seam, keep compatibility only where a public contract needs it, and preserve fast validation. |
| Status, quota, and monitors | `53b44ff3`, `b43b24d0`, and `edc91f4e` made advancement outrank stale monitor pressure, capability-gated due monitors, and future waits quiet while preserving attribution. | Add parity fixtures for specific bad cases or improve compact operator explanations; do not add a second scheduler or let monitor rows hide runnable advancement work. |
| Benchmark boundary | `b4721140`, `61661a59`, `4eb6079e`, and `8eb5bfc9` moved lifecycle, quality, result, and host-probe projections behind bounded benchmark/control-plane owners. | Extend adapters through the shipped lifecycle/reducer seams. Keep raw task text, logs, trajectories, verifier tails, credentials, uploads, and local paths out of public fixtures. |
| Validation | `9241e0b5`, `99990f95`, `3375c905`, and `67df3995` established opt-in pytest, strict typing, Ruff/import boundaries, and native Node 24 workflow checks alongside the full-public smoke gate. | Prefer thin end-to-end smokes over duplicated rule assertions. Good slices migrate stable pure rules into pytest, retain one public behavior seam, and keep CI/runtime budgets explicit. |
| Release and install | The v0.2.1-v0.2.3 releases are documented in `docs/product/release-readiness.md`; `1a86fde3` fixed install freshness provenance and `6f43c3f8` serialized concurrent promotions. | Build on the stable/update/canary model. Helpful work improves failure attribution, concurrency fixtures, and contributor-safe recovery docs without adding a parallel release checklist. |
| Public project docs | `38d1a2d3` established governance/history and `936395a8` added a deterministic update note from public repository evidence. | Keep contributor, release, history, and update-note surfaces concise and linked to public evidence; compress stale truth instead of appending another status narrative. |

### Starter / Good First

Low setup, docs-first, or narrow fixture work. These should be good entry
points for contributors who are still learning the repository.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C01 | docs | Add a short "first goal" walkthrough that starts with `loopx demo`, inspects status/history, completes one todo, and shows the next todo. | `loopx check --scan-path README.md --scan-path docs/ --scan-path examples/` |
| GH-C02 | tests | Add or extend a focused smoke test around todo archive/completion behavior. Prefer copying the style of `examples/control_plane/todo-lifecycle-cli-smoke.py`. | `python3 examples/control_plane/todo-lifecycle-cli-smoke.py` and `python3 -m py_compile loopx/*.py` |
| GH-C04 | docs | Improve v0.2 install and recovery troubleshooting: stable vs `main`, `loopx update` vs curl repair, release snapshot vs canary, `loopx doctor` source/freshness output, and safe recovery from an interrupted promotion. | `python3 examples/fresh-clone-quickstart-smoke.py`, `python3 examples/loopx-update-smoke.py`, and `loopx check --scan-path README.md --scan-path docs/product/release-readiness.md --scan-path CONTRIBUTING.md` |
| GH-C10 | docs | Add a public "what counts as a good smoke" guide using `CONTRIBUTING.md` and recent benchmark-smoke cleanup as source material. | `loopx check --scan-path CONTRIBUTING.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C13 | docs | Expand public/private boundary examples with realistic safe and unsafe snippets for benchmark traces, active state, local paths, credentials, and compact artifacts. | `loopx check --scan-path docs/public-private-boundary.md --scan-path examples/` |
| GH-C30 | docs | Add a "project asset contract" explainer showing owner, gate, next action, stop condition, last evidence, next safe command, user todo, agent todo, support mode, and fresh status projection. | `loopx check --scan-path docs/ --scan-path README.md` |
| GH-C64 | release docs | Add a contributor-safe atomic-promotion failure matrix around the shipped release lock/concurrency smoke: explain which failures happen before the symlink swap, how a waiter recovers, and when contributors must stop before maintainer-only promotion state. Extend the existing fixture only for a durable missing case. | `python3 examples/release/release-promotion-concurrency-smoke.py`, `python3 examples/release/local-install-promotion-boundary-smoke.py`, and `loopx check --scan-path docs/product/release-readiness.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C57 | docs | Refresh the heartbeat repair guide for the thin prompt default: when to regenerate with `--agent-id --agent-scope`, how stale unscoped prompts fail, and how capability-preserving scheduler ACK, workspace repair, and no-spend cadence fit together without touching local runtime state. | `python3 examples/control_plane/heartbeat-prompt-smoke.py` and `loopx check --scan-path docs/heartbeat-automation-prompt.md --scan-path docs/runtime-connector-catalog.md --scan-path CONTRIBUTOR_TASKS.md` |
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
| GH-C56 | workflow | Design the first default workflow planner for development-host LoopX usage: model visible TUI, headless runtime, IM/gateway intake, shell/service timer, and hybrid handoff as peer modes, then generate the right scoped workflow from user intent and host capabilities. The planner should cover agent identity, heartbeat/monitor guard, no-spend quiet skip, readiness verification, and explicit transitions such as visible bootstrap -> headless continuation or headless event -> visible TUI escalation. Keep it adapter-neutral and public-safe; do not bake in one chat platform, private host, or project layout. | Design note or fixture plus `loopx check --scan-path docs/ --scan-path CONTRIBUTOR_TASKS.md`; if code is added, include a focused smoke proving the generated workflow carries `--agent-id`, preserves no-spend monitor behavior, and distinguishes TUI, headless, IM/gateway, shell/service, and hybrid runtime choices |
| GH-C60 | workflow | Add focused connector parity coverage for Codex App heartbeat, Codex CLI TUI, Claude Code loop, shell worker, HTTP webhook, and worker bridge. Assert thin-context action contracts, scoped identity, capability-preserving scheduler ACK, no-spend cadence, workspace repair, and private-boundary stripping. | Focused smoke(s) plus `python3 examples/control_plane/heartbeat-prompt-smoke.py` and `loopx check --scan-path docs/runtime-connector-catalog.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C59 | status | Add a focused hot-path perf smoke for large ignored state trees and a bounded cold-path todo detail contract so `status` / `quota` stay fast without dropping public-safe backlog drill-down. | Focused perf/fixture smoke plus `loopx check --scan-path docs/status-data-contract.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C61 | cli | Implement the next canonical global manager command after `/loopx-global-summary`: choose one of `/loopx-global-gates`, `/loopx-global-todos`, `/loopx-global-risks`, or `/loop-goal-summary`, keep it read-only, source it from compact status/quota/todo/run-history projections, and make unknown aliases fail closed with help instead of broad dumps. | Focused command smoke plus `python3 examples/project/global-manager-command-protocol-smoke.py` and `loopx check --scan-path docs/reference/protocols/global-manager-command-v0.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C62 | governance | Add a visible governance/budget projection slice: show per-goal or per-agent claim, optional task lease, quota state, scheduler hint, approval requirement, and allowed next action in a compact operator-facing shape. Do not add a browser write API or present lease ownership as runtime authority. | Focused fixture smoke plus `loopx check --scan-path docs/status-data-contract.md --scan-path docs/interface-budget-contract.md --scan-path docs/frontstage-channel-lease-roadmap.md --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C63 | value connectors | Implement the first dry-run-only `finance_market_snapshot` canary from `docs/capabilities/value-connectors/finance-market-snapshot-probe.md`: tiny symbol allowlist, public Eastmoney quote endpoint, compact field allowlist, `source_unverified` labels, and no raw provider payload retention. It must fail closed for Futu/OpenD, account, private portfolio, paid data, trading, captcha, and credential paths. | `python3 examples/value-connectors-finance-probe-doc-smoke.py`, a new focused canary smoke if code is added, and `loopx check --scan-path docs/capabilities/value-connectors --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C67 | issue-fix | Render `issue_fix_outcome_projection_v0` in one public operator surface with a synthetic revision-pinned fixture. Show selected issue, stage, validation, PR state, outputs, risks, and terminal outcome without creating another case ledger or exposing provider/private notification state. | `python3 examples/issue-fix-outcome-projection-smoke.py`, the selected surface smoke, and `loopx check --scan-path docs/capabilities/issue-fix --scan-path CONTRIBUTOR_TASKS.md` |
| GH-C68 | validation | Move the stable pure rules from one oversized control-plane smoke, preferably `quota-scheduler-state-ack-smoke.py`, into focused pytest cases while retaining a thin CLI/public-behavior seam. Do not broaden the runtime contract during the test move. | Focused pytest, the retained smoke, `python3 examples/full-public-smokes-workflow-smoke.py`, and `git diff --check` |
| GH-C69 | explore | Add a public-safe local fixture and contributor walkthrough for canonical, executive, and semantic owner-board Explore views. Prove decision/evidence lineage and readability without enabling an external sink or depending on local/private graph sources. | `python3 examples/explore-result-layer-smoke.py`, `python3 -m pytest -q tests/test_explore_presentation_views.py`, and `loopx check --scan-path docs/capabilities/explore --scan-path CONTRIBUTOR_TASKS.md` |

### Advanced Implementation

Shared-state, adapter, or benchmark-control changes. Please open an issue first
and keep the first PR as a narrow slice.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C07 | state | Add structured-state write serialization for todo/refresh/history writers using a per-goal lock or optimistic revision guard. Include a concurrent todo add/update regression. | New concurrency regression plus `python3 -m py_compile loopx/*.py` |
| GH-C15 | benchmark | Implement benchmark ledger drift warning: when compact run history has a benchmark result but `benchmark-run-ledger.json/md` lacks the row, status should warn or closeout should auto-upsert. Keep raw task/log/trajectory material out. | `python3 examples/benchmark-run-ledger-smoke.py` |
| GH-C16 | benchmark | Add a public-safe trajectory-summary contract for non-SkillsBench adapters so Terminal-Bench/SWE/ALE can expose comparable counters without raw task text, logs, verifier output, or trajectory bodies. | New unit/fake fixture smoke |
| GH-C47 | state | Adopt the shipped optional `task_lease_v0` in one real host integration: advertise the capability explicitly, preserve soft-claim routing, expose acquire/renew/transfer/release outcomes, and prove overlapping write scopes fail without making `quota should-run` enforce undeclared lease authority. | `python3 examples/control_plane/task-lease-runtime-smoke.py`, `python3 -m pytest -q tests/control_plane/test_task_lease.py`, and a host-focused fake fixture |

### Design / RFC

Direction-setting work. These tasks should usually produce a doc or issue
before implementation.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C32 | learning | Implement the first read-only reward-style hint preview from `docs/product/reward-style-replanning.md`: derive compact candidate-ranking hints from public-safe reward/todo evidence without writing durable hints yet. | Preview smoke proving hints can reorder safe candidates but cannot override user gates, claims, scopes, capability gates, or workspace guards |
| GH-C35 | integration | Design a session-runtime control-plane adapter: read compact session/event/outcome/approval summaries from an external agent host, project LoopX attention items, and keep raw transcripts, credentials, billing, permissions, and product frontstage outside LoopX. | Design note with adapter-neutral smoke plan |
| GH-C37 | interaction model | Curate the interaction pattern catalog with one new public-safe good/bad case, including trigger signals, user channel, agent channel, state contract, bad smell, and validation reference. Do not copy raw chat, private benchmark artifacts, or internal links. | `loopx check --scan-path docs/interaction-pattern-catalog.md` |
| GH-C39 | interaction model | Design explicit `decision_scope` / `required_decision_scopes` metadata for user gates and agent todos so scoped fallback does not rely on prompt memory or text inference. | RFC update to `docs/interaction-pattern-catalog.md` plus one projection fixture |

### Maintainer-Owned / Coordination Required

Visible work that should not be duplicated. Ask for a public helper slice
instead of launching private runs or broad product changes.

| ID | Area | Task | Validation |
| --- | --- | --- | --- |
| GH-C18 | benchmark | Long-horizon benchmark evidence program, including live local no-upload cases, runner contracts, trace retention, score accounting, and good/bad case attribution. Do not duplicate live runs or inspect private artifacts unless maintainers split out a public helper issue. | Maintainer-run benchmark ledger and public/private scan |
| GH-C19 | benchmark | Main-table SkillsBench product-mode comparison: raw Codex autonomous max5 versus LoopX state/todo/replan/CLI, no verifier feedback to either arm, stop on reward 1 or declared done. This lane remains maintainer-owned while goal-start verifier/bootstrap preflight is still being repaired. External contributors can help with schema/docs/smokes only. | Maintainer-run compact ledger, case-analysis update, and public verifier-bootstrap scan |

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
