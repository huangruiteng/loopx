# RFC: TypeScript Control-Plane Migration Direction v0

- Status: Accepted, transaction-payoff phase in progress
- Proposed by: LoopX maintainers
- Date: 2026-08-15
- Last revised: 2026-09-09
- Scope: an incremental, replacement-first migration of the LoopX control-plane
  core from Python to TypeScript without maintaining two semantic
  implementations
- Tracking issue: [#3225](https://github.com/huangruiteng/loopx/issues/3225)
- Language note: the
  [Chinese version](./typescript-control-plane-migration-v0.zh-CN.md) and this
  English version are semantic mirrors. A difference between them is a defect.

---

## Current implementation checkpoint

A checked-in generator validates the language-neutral contract and emits
deeply immutable Python/TypeScript bindings, including the native domain and
projection sections. Both runtimes import these bindings; CI checks source
parity and rejects stale generated files. This removes duplicate contract
loaders without changing Todo semantics or promotion policy.

The coordination path uses one language-neutral
`coordination_state_contract_v0.json`. Its native `TodoDomainRecord` keeps task
semantics, including `archive_state`; `TodoProjectionMetadata` contains
`source_section` and optional `index`. The TypeScript reducer and provider-first
collection reader accept the separately versioned native domain manifest;
native creation, archival, receipt replay, and store reopen are tested without
Markdown metadata. Python only adapts the typed read result to the compatibility
summary. This is a contract checkpoint, not a completed CLI lifecycle cutover.

Provider-first `todo update --text/--note` preserves claim-neutral correction:
a registered, non-excluded actor may edit an unclaimed active, non-completed
agent Todo, subject to its agent binding. It must not introduce `claimed_by`.
Another claim owner's Todo remains rejected. Only text/note may be patched or
cleared; governance fields and hard-lease execution authority are not granted.
The TS transaction owns eligibility, CAS, and receipt replay; promotion must
not turn a copy correction into a claim. Provider conformance covers both
native and v0 records, and the production CLI is tested without Markdown.

The default Markdown and explicitly promoted `todo claim` paths now share one
TypeScript claim decision for actor, registration, role, status, archive,
exclusion, and existing-owner checks; the Python legacy writer only commits
that decision while holding its lock. After explicit promotion, claim crosses
once into the same TS-owned
transaction for both native and v0 records. New claims require active, open
Todos and the current actor/lease checks. Exact operation retries recover the
original claim receipt before current-state eligibility; observation time and
current registration facts are not request identity. Replaying a receipt does
not renew a lease or assert current ownership. Successful non-preview
`no_change` also persists a terminal receipt under head CAS: storage revision
may advance, but Todo state, `updated_at`, and domain events do not change.
A structurally valid empty registration list permits historical replay, never
a fresh claim; malformed lists still fail. Preview remains zero-write, and
invalid preview booleans fail before provider access. The CLI still creates a
fresh operation id by default. On an already promoted canonical authority,
callers can opt into cross-invocation retry with
`loopx todo claim --goal-id <goal> --todo-id <todo> --claimed-by <agent> --agent-id <agent> --claim-operation-id <public-safe-id>`.
Reuse the same id and intent after a lost response; changed intent under that
id fails closed. A preview does not consume the id. The option rejects legacy
mode without writing or promoting anything; omit it to retain default behavior.
It grants neither a lease nor current ownership on historical replay. Combined
claim/lease acquisition remains follow-up work.

Promoted `todo add` is a native create
transaction on that same authority owner. Python validates the established CLI
arguments and adapts them once into the versioned domain record; TypeScript
owns duplicate identity, replay, actor/owner eligibility, CAS, receipt, and
projection-outbox mutation. Preview and the real subprocess CLI path are tested
after deleting the Markdown state file, so promotion cannot silently regain a
Markdown write path. Completion-validation argv remains typed data rather than
a shell-encoded compatibility field. Default, unpromoted goals retain their
existing Markdown transaction until their explicit promotion boundary.

The terminal-lifecycle stage package extends that boundary to promoted
`complete`, `supersede`, and role-scoped `archive`. TypeScript owns admission,
claim/lease fencing, successor validation, completion-policy reduction, CAS,
receipts, projection intent, and archive selection. Python projects registry
facts, executes an explicitly declared validation effect between typed
reductions, and drains compatibility projections; it no longer recreates the
terminal state machine for promoted goals. The canonical Todo stores only a
validation-required marker and declaration digest. Raw argv remains in a
0600 host-local sidecar and must match that digest on recovery before the
effect may run. Imported v0 Todos retain legacy `index` archive ordering;
provider-native records use durable completion/update time and Todo identity.
Historical lease files absent from the current Todo graph remain audit history
and are not projected back into the canonical live head.

Every non-preview terminal or archive entrypoint acquires the same per-goal
shadow-maintenance mutex used by bootstrap and rollback, then rechecks the
durable management state before opening the canonical provider. A lifecycle
write therefore cannot overlap a bootstrap/rollback transition or bypass its
write hold. After the durable promotion fence is present, a missing canonical
head is reported as a typed canonical-authority outage with an explicit
restore-before-retry recovery action. It is not relabeled as a legacy-writer
fence, and it never authorizes a Markdown fallback.

This stage is qualified with a three-arm rehearsal from one read-only,
production-complex snapshot: an immutable legacy baseline clone, an isolated
file provider, and an isolated real PostgreSQL provider. The provider heads
must match exactly and the legacy arm must match semantically after normalizing
the declared compatibility projection. For archive, that projection excludes
provider-retained archived records and their historical leases from the legacy
hot view, and ignores absolute imported indexes only after proving identical
per-role relative order. It never normalizes domain fields, archive selection,
active leases, or non-target records; the source snapshot remains unchanged.
The versioned rehearsal command lives in
`examples/control_plane/authority-three-arm-rehearsal.py`. A deterministic
public-safe scale fixture exercises
the same status mix, current/retired leases, standing decisions, validation,
successor, replay, concurrency, archive pressure, and hard-lease fences in every provider suite.
That fixture is durable regression coverage, not a substitute for the current
read-only three-arm rehearsal.

From this checkpoint onward, every pull request that claims progress against
this RFC follows the
[production-scale fixture stewardship contract](../../development/testing-and-quality.md#production-scale-fixture-stewardship--生产规模-fixture-维护契约).
It declares fixture impact, exercises every affected provider arm, and keeps
the read-only three-arm rehearsal as a separate promotion gate.

The old v0 consumer manifest remains readable and retains all existing fields.
Default Markdown capture still emits v0; this PR neither rewrites stored heads
nor auto-promotes a goal. The schema split is not permission to drop v0
provenance or change legacy ordering during a later migration.

### Long-goal persistence is part of the migration payoff

The product target is at least ten elapsed days per goal, not a short-lived
transaction demo. The shared-authority RFC's
[Section 7.2](./shared-goal-authority-state-provider-v0.md#72-ten-day-goals-local-storage-qualification-target-proposal)
owns the workload, performance budgets, retention and actual-soak acceptance;
keep changing capacity numbers there rather than duplicating them here.

Start a cohesive local-persistence slice alongside the provider-first Todo
caller: qualify an embedded transactional store (SQLite first candidate),
bounded live head/receipt lookup, crash-safe checkpoints and exact historical
readback. File-v0 remains the conformance/import baseline. Merely replacing
Python with TypeScript, swapping databases while retaining ever-growing heads,
or passing accelerated volume tests is not ten-day continuity evidence.
Local promotion waits for both volume and elapsed-time qualification; it does
not wait for a PostgreSQL service and never expires receipts at day ten.

### Delivery semantics: correctness before migration

The delivery-history boundary now treats `classification`, `health_check`, and
`recommended_action` as narrative. They cannot create or discharge a
follow-through obligation, prove an outcome, or classify delivery scale.
For example, `unblocked after dependency update` is not a blocker receipt and
`implemented network protocol parser` is not preparation-only evidence.

`control_plane/work_items/delivery_history.ts` now owns the complete delivery
history-to-obligation read projection: outcome, turn kind, scale, consecutive
streaks and follow-through. Status selects one bounded history batch before one
`work_item.delivery_history.project` request; quota's latest-run consumer uses
the same projection with one row. This adds a managed-runtime crossing where
Python previously decided locally, not one request per field or historical row.
The Python bridge sends compact typed facts, never narrative or evidence bodies;
display-only classification is attached after the decision. The replaced
`delivery_signals.py`, `outcome_followthrough.py`, turn-kind inference and status
streak wrappers are deleted. Existing TS blocker binding is reused. Python enum
codecs and the settlement writer predicate still have real callers and remain;
this is not a writer/transaction or provider migration.

The acceptance invariant is **narrative non-interference**: holding typed
fields and configuration fixed, rewriting narrative or adding an unvalidated
`compact_evidence` / `case_result` object cannot change delivery semantics or
its follow-through obligation. Classification remains visible as a history
label; no legacy prediction is retained without a concrete display consumer.

- Valid explicit outcome, turn-kind, and scale fields retain their meanings.
  An explicit blocker kind remains readable. A scoped typed blocked observation
  must pass the existing work-item/evidence binding before it resolves a gap
  into blocker writeback. A bare `outcome_gap` is insufficient.
- Missing or unsupported historical delivery fields remain unknown; unknown
  stops consecutive small-scale/outcome-gap evidence streaks and never counts
  as success or as an inferred failure. Missing outcome with no configured
  floor retains the `not_configured` presentation sentinel.
- New delivery claims use explicit enums through the existing writer APIs
  (for example `refresh-state --delivery-outcome ... --delivery-batch-scale ...`).
  State-only refresh remains legal without a delivery claim; this patch does
  not require every status refresh to declare progress. Existing write-time
  enum rejection, settlement evidence, quota, and gate checks remain in force.
- Follow-up claim validation shares one TS diagnosis with historical projection.
  New writes reject progress paired with preparation-only work, primary outcome
  paired with blocker work/typed blocked observation, and primary outcome paired
  with an explicit follow-through requirement. Historical conflicts remain
  readable as `unknown` plus `delivery_claim_conflicts`; persisted records and
  settled receipts are never rewritten. Partial progress and valid blocker
  writebacks remain legal. This is an intentional authoring/readback behavior
  correction, not a change to small-delivery policy or a new evidence validator.
  Refresh validates individual fields in their established order, then checks
  the normalized claim before registry access or lock creation. Invalid input
  therefore takes precedence over store errors, including in dry-run mode;
  state-dependent admission and writeback still share the same runtime lock.
- Delivery response is a separate typed read decision consumed by quota,
  handoff and work-lane projection. A scoped blocked observation exempts the
  historical outcome floor only while its canonical Todo has a positively
  identified pending resume target. Missing/invalid source, another actor's
  claim, exclusions and unbound legacy blocker labels cannot establish that
  exemption. Other runnable work remains selectable by the canonical planner.
  Unknown refreshes interrupt statistics, not Todo/replan obligations; no new
  persistent delivery ledger is added. Surface-only supervision and the
  independent small-delivery rule remain unchanged.
  This exemption requires the parsed target identity and a supported task class;
  monitor baseline, capability and PR repository/number also bind to the current
  Todo. Missing actors or stale/mismatched conditions cannot relax supervision.
  Incomplete legacy conditions remain readable, but are not positive wait proof.
- Legacy outcome-marker/hint configuration remains readable and preserves
  whether an outcome floor is configured. Its words no longer classify runs.
  No persisted history is rewritten and no new default-off flag restores the
  erroneous behavior. This intentionally changes status, handoff/review, and
  quota decisions previously derived from untyped historical labels.

The migration preserves independently characterized legal typed behavior and
validates real refresh/history/status/quota entrypoints, batch cardinality and
narrative non-interference. One intentional correction is separate from parity:
two invalid work-item identifiers must not compare equal merely because both
normalize to a missing value. Such observations cannot infer blocker writeback
or discharge a follow-through obligation. The remaining Python writer predicate
rejects that case too; no active history is rewritten.

Next, inventory writers still omitting material-result fields and retire obsolete
marker/hint configuration with an explicit compatibility plan. Exact legacy
lifecycle classification codes, history selection and unrelated cadence policies
remain outside this slice. Do not claim all writers migrated or all prose rules
retired. This read-policy closure does not displace the provider-first Todo
sequence below or wait for a provider cutover.

### Legacy field-rule retirement checkpoint

`todos/field_update.ts` now owns the complete metadata intent assembly used by
the legacy `update`, `claim`, `complete`, and `supersede` line writer: status and
completion timestamps, omission versus explicit clears, binding precedence,
removed-policy repair, resume-generation pairing, and completion metadata.
It composes the existing TS completion rule directly. The replaced Python
decision branches and the last-caller `todo.completion_state.metadata_updates`
RPC/facade are removed, not kept as a fallback.

This is a pure plan, not admission or a provider commit. Python still owns
Markdown lookup/encoding, byte-level no-op detection, locking and external
effects. Public role/binding admission and the event writer are not declared
migrated by this slice. Promoted update remains text/note-only; no unsupported
field gains authority, no goal is promoted, and no third storage path appears.
Rejected plans now leave even the caller's in-memory line buffer unchanged;
public rejected transactions were already non-committing.

There is one field-plan crossing per legacy line write. It replaces the former
metadata RPC on ordinary edits; already-finalized completions with an override
gain one planning crossing. Cached codec normalization calls remain. This is
semantic deletion, not a claim of fewer crossings on every command. Retire the
adapter with its final legacy lifecycle caller after full-goal cutover, or fold
it into that caller's coarse transaction when migrating the caller; do not grow
a series of field-level RPCs. Retain Markdown rendering permanently.

### Next delivery sequence

The destination retains Markdown as a **permanent readable projection**, not a
second database. This RFC owns one typed business-rule/transaction owner and
its deletion payoff; the [shared-authority RFC](shared-goal-authority-state-provider-v0.md#next-delivery-and-parallel-provider-work)
owns durable truth, recovery, cutover, and projection delivery. Neither a fully
TypeScript CLI nor `loopxd` is a prerequisite for removing Python decisions.
An input adapter or external-effect executor may remain Python.

The lifecycle-admission slice now uses `todo_lifecycle_decision.ts` for legacy
claim/update admission, delegated action/reason checks, ownership-holder routing,
and the preauthorized terminal fence, alongside native complete/supersede.
`authority_core.py` projects results rather than retaining those decisions.
The terminal wire contract stays terminal-only; mutation admission cannot complete
a Todo, and a standalone fence neither grants actor authority nor completes it.
This deletes duplicate rules now, **not** the complete legacy update writer.
Field patches, omission/clear semantics, monitor/resume effects and validation
still need one complete update transaction before the writer can retire. Legacy
callers still cross the runtime boundary for admission and their locked gate;
this slice reduces semantic owners, not crossing count. Native transactions stay
in-process. Fold the remaining crossings into that complete transaction rather
than extending these adapters field by field.

The waiting/resume planning slice now uses `todos/resume_planning.ts` for the
complete deferred, resume-blocked, monitor-repair and blocked-successor selection.
Quota composes capacity evaluation with these lanes in one request per source summary, reusing the
existing TS resume evaluator in-process; vision-wait, agent-scope, frontier and
replan consumers use the same projection. The old `deferred_resume.py` rule owner
is removed, not retained behind a second implementation. The Python adapter keeps
the reader compatibility boundary, not claim/exclusion selection or wait routing.
Resume, route-continuation and succession-warning share `compact_projection.py`
for field omission and scope normalization; caller-specific text inference and
succession-only fields remain explicit. Priority rank normalization stays in the
resume adapter. This retires
one read-policy family, not the whole quota reducer or the monitor/lease writers.
Equal public sort keys retain source order; full counts precede display limits;
`monitor_changed` is not the legacy `todo_done:<monitor>` repair path. This
read-only result grants neither execution authority nor a lifecycle receipt.
The adapter exits when its callers consume typed Todo records in-process.

Resume condition diagnosis is now shared by the evaluator and planning owner;
agent-scope consumes the selected repair lane rather than reinterpreting target
type/status. Old compact inputs may recover omitted kind/class from typed
`resume_when` and the same snapshot's monitor records, never from narrative.
This refinement includes explicit behavior corrections: self-dependencies and
`todo_done` dependencies on unfinished monitors are `resume_condition_invalid`,
not ordinary pending waits. Completed historical monitor dependencies remain
satisfied; missing completion targets remain pending because absence in a
partial snapshot is not proof of an invalid dependency. Valid generation fences,
claim/exclusion, capacity and PR waits retain their existing semantics. Invalid
conditions cannot become exact blocked-successor waits. Monitor completion
repair stays visible and selectable only in the permitted executor scope.
No automatic conversion to `monitor_changed`, baseline reset, persisted-state
rewrite or new writer admission is implied. General add/update admission and a
generic repair action for every invalid condition remain separate scopes; this
is not a claim of zero behavior change or full Todo writer closure.

#### Execution cards after the current stack

This is a **conditional execution plan**, not a merged-status declaration.
At the 2026-09-09 checkpoint, #4053, #4117, #4129, #4122
(resume diagnosis/planning), #4134 (delivery history) and #4136 (claim diagnosis)
are merged. The canonical delivery-response follow-up targets that landed main.
Check their actual merge commits before starting. #4121 (SQLite candidate)
and #4101 (projection receipt retention) are independent candidates, not
implicit prerequisites or approved defaults.

Execute the first unclosed card below; do not start all cards or rebuild a
completed transaction. Keep the task ledger in LoopX state; this document is
the shared plan, not another per-agent checklist database.

**T0 — reconcile the landed baseline, inside the next implementation PR.**

- Fetch the intended remote base; record its SHA and each dependency's actual
  merged/not-merged status. Compare code, not just PR titles. If a dependency
  is open, use an explicitly selected stacked base or stop that dependent unit.
- Start from `coordination/todo_update.ts`, `todos/field_update.ts`,
  `todos/provider_compatibility_edit.py`, `todos/line_update.py`,
  `scheduler/monitor_poll_writeback.py` and their public callers. These paths
  are under `loopx/control_plane/`. Re-resolve moved symbols instead of
  restoring removed compatibility wrappers.
- Produce a compact caller matrix: public operation, authority source before/
  after promotion, TS owner, external effects, retained legacy caller, and
  exact deletion condition. Update this section's completion facts with the
  implementation; do not deliver an inventory-only framework PR.
- When #4122 and delivery response meet, reconcile pending/invalid condition
  diagnosis in the existing resume owner. A missing target is not proof of a
  valid wait; readable historical pending state is not permission to relax
  supervision. Retire duplicate checks only after both contracts are tested.

**T1 — close the public Todo update transaction.**

- Reuse the current provider text/note transaction, lifecycle admission,
  field-plan and completion rules. Enumerate actual public metadata edits and
  explicit-clear behavior before implementation; this is not permission to
  widen `UPDATE_FIELDS` to every stored field or admit terminal transitions
  through a generic patch.
- Deliver one coarse typed transaction covering admitted intent, actor/claim/
  exclusion/lease checks, field semantics, final validation, CAS and replay.
  Keep external execution/checkpointing outside pure reduction. Monitor effects
  that cannot fit safely remain explicitly unsupported until T2; list them.
- Delete replaced Python update decisions and leaf-RPC orchestration in the
  same PR. Keep the legacy codec/lock and compatibility writer while
  unpromoted callers still need them; do not claim full writer deletion.
- Prove omission versus clear, unclaimed copy correction versus privileged
  metadata, other-owner/lease rejection, no-op, invalid-input no-write,
  competing revisions, retry and lost-response recovery through the public
  command and affected real providers.

**T2 — close monitor writeback and its atomic follow-up.**

- Inventory `monitor_poll_writeback.py` and its event/Todo/lease callers.
  Reuse existing monitor generation, independent-successor and settlement
  owners. Compose one transaction rather than adding a second monitor engine.
- Preserve unchanged polling/reschedule behavior, generation fences,
  material-change successor deduplication and accountable settlement.
  A monitor remains non-executable delivery context; its independent
  advancement Todo is not the monitor itself.
- Delete the replaced Python transition decisions. External polling remains
  an effect adapter. Prove duplicate polls, crash between phases, races,
  failed effects, another actor's claim, and no-change no-delivery semantics.
  If a required command effect is still unsupported, hold whole-Goal promotion;
  never fall back to a Markdown business write.

**T3 — close remaining structured consumers, then remove their old reads.**

- Audit Turn/quota, Dashboard, standing decisions, shared-goal alignment and
  amendment revision inputs. Reuse #4117's canonical source adapter and pass
  one snapshot through a decision; do not build another Todo inventory.
- For each migrated caller, delete its post-promotion Markdown/event fallback in that
  PR. Prove absent/stale/malformed display, empty canonical state, unavailable
  provider, terminal/archive ordering, claim scope and data beyond UI limits.
  Canonical absence must not revive legacy data or become successful completion.
- Keep outcome history supervision, canonical obligations and settlement
  authority separate. Unknown observations cannot settle Todo/replan work.
  Explicitly disclose any semantic correction; do not label it full parity.

**T4 — collect full-writer retirement after durability cutover.**

- Depends on T1–T3 and the shared RFC's [D1–D3](shared-goal-authority-state-provider-v0.md#durability-execution-cards), including owner approval
  and the explicit legacy migration window. Search remaining imports and
  public command routes before deleting old Markdown business writers,
  capture-only adapters and duplicate reference aggregates.
- Keep permanent Markdown rendering, validated import/export and external
  effect adapters. Every retained bridge names its live caller and exit
  condition. No full TS CLI, daemon or remote service is required.

**Validation and stop rules for every card**

Use `tests/fixtures/control_plane/coordination_production_scale_v0.json`,
`tests/control_plane/canonical_authority_fixture.py` and the existing provider
conformance suite when their semantic dimensions are affected. Verify their
current schema before reuse; never silently shrink a complex fixture to pass.
Run `npm run typecheck:control-plane`, `npm run test:control-plane`, the
affected public CLI tests and risk-based canary coverage. Shared transaction
changes require affected File/NoKV arms and an isolated real PostgreSQL run;
new local-store claims require that actual backend, not an in-memory substitute.

Before moving code, assert intended legal and illegal behavior independently.
After moving it, report baseline/head parity, intentional differences,
production versus bridge LOC, and crossings separately from tests/generated
code. Stop on an unknown writer, missing real environment, unexplained
difference, private-data dependency or failed required gate. Do not waive
authority, evidence, fixture or payload budgets to complete a card.
A read-only snapshot or disposable synthetic Goal is allowed; active Goal
promotion, new models/jobs, soak automation, release or merge need their
respective explicit authority.

Stacked schema-identifier cleanup is independent maintenance, not a prerequisite
for this sequence. Absorb a downstream change only when the selected complete
transaction actually needs it; rebase the remaining work after its base merges.

## 0. Decision in one example

During migration, the Python `loopx` CLI sends one coarse typed transaction to
a LoopX-managed TypeScript runtime. For example, Turn settlement first asks
TypeScript to validate the journal and authorize any still-Python providers;
after Python checkpoints those external outcomes, TypeScript performs the final
reduction and returns one typed result. A replay with no pending provider needs
only the reduction call. Python translates the result into the legacy CLI shape.
It does not call a series of TypeScript leaf helpers or retain parallel enums
and reducers.

The same PR must delete the Python semantic path it replaces. A new TypeScript
module is not migration progress by itself: the payoff is fewer semantic
owners, fewer cross-runtime round trips, and a facade with a credible deletion
condition.

After the CLI itself migrates to TypeScript, CLI-only use imports the same
kernel in-process and the Python-to-TypeScript bridge disappears. When the App,
CLI, scheduler, or several hosts need one shared writer, the same kernel may run
inside one optional managed daemon. This is one kernel with two deployment
forms, not one server per control-plane family.

## 1. Problem

LoopX already has TypeScript host and dashboard surfaces. The Effect Program,
Turn-journal effects, several Todo/quota decisions, and scheduler state now
have TypeScript owners, while much of the CLI composition and compatibility
surface remains in Python. A big-bang rewrite is too risky, but continuing to
translate leaf helpers would leave a chatty bridge and duplicate DTO knowledge:
code would move without simplifying the product.

The migration therefore needs intermediate states that satisfy all of these
constraints:

- one semantic owner for every migrated rule;
- no user-visible CLI split and no manual daemon lifecycle;
- real side effects can migrate, not only pure projections;
- correctness is qualified against a pinned pre-migration baseline and
  independently stated invariants;
- latency, packaging, upgrade, rollback, and crash recovery are measured at
  every cutover;
- each PR is a complete, reviewable replacement slice;
- migration economics improve: old semantic code and temporary scaffolding
  leave faster than bridge code accumulates.

## 2. Architecture decision

### 2.1 One TypeScript kernel

`@loopx/control-plane` is the intended semantic kernel. Domain modules own
typed state, interpretation, transition rules, and the internal effects that
belong to those rules. A transport shell must not become a second business
owner.

```text
Python CLI during migration ─┐
LoopX App / scheduler ───────┼─> one typed runtime boundary ─> TS kernel
future TS CLI ───────────────┘
```

The boundary uses coarse, versioned requests such as “settle this Turn” or
“commit this journal”, not chatty property getters. The runtime has a static
typed handler registry. Adding a domain handler does not create another
server.

### 2.2 Two deployment forms, one implementation

| Product topology | Execution form |
| --- | --- |
| CLI-only after the TS CLI cutover | Import and execute the TS kernel in the CLI process; no daemon |
| App-only | Embed the same kernel in the App runtime |
| App + CLI + scheduler, or concurrent clients | One managed local authority daemon; clients connect to the active writer |
| Migration while Python remains the CLI | One idle-exiting loopback runtime bridges Python to the migrated TS kernel |

If an authority daemon owns a registry/workspace, a CLI process must connect
to it instead of opening a second direct writer. Runtime discovery and startup
are automatic; users do not configure ports or supervise processes.

### 2.3 TypeScript owns migrated effects

The target is not “TypeScript decides, Python always executes”. TypeScript may
own internal LoopX effects such as atomic state checkpoints, event appends,
receipt commits, and idempotent reducer writes. Each effect has a typed request,
stable idempotency identity, typed receipt, and retry policy.

Asynchronous execution does not weaken settlement ordering: an effect receipt
is emitted only after the awaited durability boundary succeeds. It does,
however, permit concurrent requests, so the authority that owns a migrated
write must also own its per-key serialization or compare-and-swap contract.
Caller-side locking is acceptable only as an explicitly transitional guard; a
native TypeScript caller must not bypass the invariant after cutover. Retry
identity is operation-specific: when one Turn effect checkpoints several
successive journal states, the broad Turn effect id alone is not proof that two
write payloads are the same operation.

External authorities remain explicit adapters: model calls, human gates, host
schedulers, credentials, and third-party mutations are not hidden behind a
universal executor. Their receipts return to the Effect Program for
settlement.

### 2.4 Replacement, not production dual-running

Characterization may execute the old and new implementations offline against
the same pinned corpus. Production does not keep two rule engines or dual-write
semantic state. Once a slice passes its gates, callers flip to TypeScript and
the replaced Python rule is removed. A narrow compatibility facade may remain
only for a real public import, persisted schema, or unmigrated callback.

### 2.5 Validate once at every trust boundary

TypeScript types are erased at runtime. Network/RPC payloads, parsed JSON,
persisted state, extension input, and adapter responses therefore enter the
system as `unknown`; a static annotation or `as T` assertion does not prove
that those bytes satisfy the contract. Each migrated domain must decode these
values through a typed decoder or an explicit versioned schema parser before a
domain handler or Effect interpreter consumes them.

After successful decoding, the TypeScript kernel owns the typed value and may
rely on the compiler instead of repeating ad hoc field checks throughout the
domain. Transport checks such as framing, authentication, and size limits stay
separate from schema validation and semantic invariants. An unchecked
`JSON.parse(...) as T` must not establish control-plane authority.

`as unknown as T` is permitted only as a named migration seam: its exact call
site, upstream validator, negative boundary coverage, and removal owner must be
visible in the cutover PR. A migrated domain cannot pass its promotion gate
while public, persisted, RPC, or extension input still reaches its semantic
core through an unvalidated assertion. TypeScript complements runtime
validation; it does not replace it.

## 3. Current baseline and phase transition

Effect Program moved first because it joins ordered steps, identity,
short-circuit failure, replay, receipts, and settlement. That architectural
choice is now implemented rather than hypothetical.

### 3.1 Shipped baseline

| Slice | Canonical TypeScript ownership now shipped | Remaining migration debt |
| --- | --- | --- |
| Effect runtime and Turn journal ([#3416](https://github.com/huangruiteng/loopx/pull/3416)) | Effect algebra, settlement rules, runtime lifecycle, typed Turn-journal interpretation, and durable checkpoint effects | Python settlement facades still expose fine-grained calls and duplicate DTO/enum shapes |
| Todo, quota, and scheduler proof slices ([#3431](https://github.com/huangruiteng/loopx/pull/3431)–[#3434](https://github.com/huangruiteng/loopx/pull/3434)) | Completion fence/state, workspace causality, and scheduler transitions each have one TS rule owner | The cuts are mostly leaf-shaped; Python still composes several product transactions |
| Scheduler durable state ([#3440](https://github.com/huangruiteng/loopx/pull/3440)) | State normalization, persistence, replay, and one coarse transition are TS-owned | The Python compatibility path still pays a cross-runtime transport tax |
| Scheduler heartbeat/state transaction | TypeScript owns receipt freshness, ACK and host-failure validation, state construction, failure-cache transitions, replay/CAS fencing, atomic writes, and the public JSON/Markdown projection | Generated, receipt-bound host follow-up runs through the native TS CLI; Python remains only for unbound/manual compatibility calls and external host mutation |
| Quota spend commit transaction | TypeScript owns final spend-transition validation, typed event construction, effect replay/CAS fencing, crash repair, and the JSON/Markdown/index write set | Python still projects `should-run` and settlement readback facts, and holds the legacy cross-writer index lock until the CLI/index writers move in-process |
| Quota void commit transaction | TypeScript owns spend-target resolution, before/after reduction, canonical correction construction, effect replay/index CAS, prepared-receipt repair, and the JSON/Markdown/index write set | Python retains `should-run` facts, clock/effect identity, the legacy cross-writer index lock, one transport call, and compatibility entry points |
| Quota monitor-poll commit transaction | TypeScript owns monitor admission revalidation, target/event/result construction, effect replay/index CAS, provider intent, and repairable JSON/Markdown/index persistence | Python projects compact `should-run` facts, invokes the real Todo provider between at most two reductions, reloads legacy status, and holds the cross-writer index lock |
| Runtime decoders ([#3443](https://github.com/huangruiteng/loopx/pull/3443)) | Stable primitive decoding has one small shared module; domain decoders remain local | No larger schema framework is justified |
| Transaction payoff ([#3464](https://github.com/huangruiteng/loopx/pull/3464), [#3481](https://github.com/huangruiteng/loopx/pull/3481), and Todo completion) | Turn settlement, quota delivery routing, and Todo completion each cross one coarse TS boundary; the Todo transaction owns identity, replay fencing, validation planning/result reduction, continuation/recovery, and completion metadata | Python still executes explicitly external providers and materializes legacy Markdown/event results; other domains still need their own bounded cutovers |
| Promoted-authority Todo claim | TypeScript owns the provider-head read, lifecycle validation, complete-record update, hard-lease check, CAS, receipt, and readback-safe result for claims after authority promotion | Default local Markdown mode remains on the legacy writer; other Todo mutations and Markdown regeneration remain bounded follow-ups |

The scheduler facade exit now includes its first bounded Stage 3 route. A
versioned `heartbeat_followup_cli.ts` accepts bounded compact host facts from
the generated ACK/failure hint, verifies the originating heartbeat receipt,
and runs state validation, replay/CAS fencing, the locked write, and public
JSON/Markdown projection in one Node process. The Unix, Windows, and installed
console launchers select this route only for exact receipt-bound commands, so
the recurring host path no longer starts Python or pays a Python-to-Node
request/response. The deleted Python ACK rule and adapter-only tests no longer
form a second semantic owner. A decision-free Python compatibility adapter
remains for explicit in-process and manually constructed unbound calls. It can
be deleted after those callers consume generated receipt-bound hints. The host
automation adapter and its TOML/SQLite writes intentionally remain Python and
external to this transaction.

These slices proved correctness, packaging, Windows lifecycle, crash recovery,
real TS-owned writes, and acceptable warm primitive-call latency. They also
revealed the migration boundary: leaf-by-leaf translation grows TypeScript,
facades, parity fixtures, and bridge traffic before enough Python composition
can be deleted.

### 3.2 Payoff-phase decision

The migration therefore enters a **transaction-payoff phase**. New leaf
migrations are rejected unless they directly unlock a complete transaction
cutover and deletion in the same PR or the immediately stated bounded follow-up.
The unit of progress is now an operator-visible transaction, not a helper,
enum, dataclass, or source file.

A transaction cutover must:

1. move validation, state transition, migrated internal effects, and result
   construction behind one domain-owned TS request/response boundary;
2. delete the replaced Python rule composition, fine-grained API, duplicate
   enums/dataclasses, and implementation-specific tests;
3. leave Python as transport, legacy response projection, and explicit adapter
   for still-external authorities only;
4. avoid leaf-level bridge chatter. A transaction whose effect providers have
   migrated to TypeScript, or a replay with no pending provider, uses one
   request/response. While a real provider remains in Python, use at most two:
   one fail-closed preflight that authorizes named effects and one final
   reduction over their checkpointed outcomes. A model call, human gate, or
   third-party mutation starts a new receipt-bearing transaction rather than an
   implicit callback tunnel;
5. name the exact condition under which its Python facade and bridge operation
   can be removed.

Domain invariants remain with their bounded owner. “Coarser” does not mean one
universal control-plane command or one mega-reducer.

## 4. Migration sequence

### Stage 0 — Pin behavior and authority (complete, repeated per transaction)

For each selected transaction, record authoritative schemas and independently
reviewed legal/illegal transitions, production callers and side effects,
matched latency/install baselines, and rollback/state-compatibility boundaries.
Characterization fixtures are temporary migration evidence, not permanent
specification.

### Stage 1 — Effect Program and managed runtime foundation (shipped)

The TypeScript Effect algebra, settlement semantics, Turn-journal
interpretation, durable checkpoint effect, runtime lifecycle, packaging,
upgrade fingerprint, and boundary decoder foundation are on `main`. The Stage 1
settlement-facade cleanup is complete: Python fine-grained settlement readers
are removed, while coarse readback/projection remains bounded Stage 2B work.

### Stage 2A — Bounded rule-owner proofs (shipped; do not repeat as a pattern)

Todo completion, quota workspace causality, scheduler transitions, and
scheduler durable state established that a Python caller can safely switch to
a single TS semantic owner. Their characterization and facade layers were
appropriate migration evidence, but copying the same leaf pattern across more
domains would now increase total complexity.

### Stage 2B — Complete transaction cutovers (active)

Select by deletion leverage and runtime traffic, not by ease of translation.
The shipped Turn settlement, quota delivery-routing, Todo-completion,
scheduler-heartbeat, quota-spend commit, quota-void commit, and task-lease acquire cutovers
establish the pattern.
Subsequent candidates must name a remaining transaction and its deletion
leverage; remaining quota settlement readback is eligible only when it can
retire or materially shrink the facade rather than add another leaf handler.

For each completed transaction, replace migration-only characterization workers
and Python implementation fixtures with native TS semantic/invariant tests plus
one durable end-to-end adapter contract. Retain a characterization corpus only
while an old authority remains executable or a versioned compatibility window
requires differential proof; record its deletion trigger when introduced.

Current implementation status: Stage 1, the bounded Stage 2A proofs, and the
shipped Stage 2B cutovers are in place:

- Turn settlement/commit: TypeScript owns preflight authorization,
  ordered-prefix and replay validation, provider failure classification,
  receipt construction, terminal closeout joining, and the canonical result.
  A real Python provider uses two coarse reductions; completed replay uses one.
- Quota delivery routing: TypeScript owns continuity-versus-fallback selection
  and the selected Todo's settlement boundary. The in-flight path moved from
  two cross-runtime calls to one; the empty candidate short circuit remains
  zero.
- Todo completion: TypeScript owns completion identity, terminal replay fence,
  validation declaration/effect planning, validation-receipt reduction,
  continuation/recovery, completion metadata, registered-agent admission,
  successor ownership/exclusion, and existing-successor selection in one
  transaction. Python projects registry and Todo-source facts without deciding
  policy. A Todo without declared validation, including a replay, uses one
  reduction. A real caller-approved validation command remains an explicit
  Python provider between two reductions. Todo and policy-source snapshots are
  compared after the mutation lock so a receipt for one declaration or agent
  registry cannot authorize changed facts. Policy admission failures are
  returned as typed data by that same reduction and consumed only after Python
  actor/lease admission, preserving legacy error priority without a leaf
  runtime call inside the writer critical section. Materialized and
  event-projected writes consume the same typed result.
- Scheduler heartbeat/state: TypeScript owns receipt freshness, ACK and
  host-failure validation, identity-aware progression, failure-cache
  retention/counting, replay and CAS fencing, preview reduction, the locked
  atomic write, and the legacy-compatible JSON/Markdown result. Generated
  receipt-bound ACK/failure hints carry a versioned bounded fact packet and
  enter that transaction directly through the native CLI. Python no longer
  participates in the recurring path. Its decision-free compatibility adapter
  remains only for explicit in-process and unbound manual callers and exits
  when those callers adopt the generated route. Host automation mutation stays
  an external Python effect.
- Quota spend commit: TypeScript revalidates the compact before/after transition,
  constructs the canonical public-safe spend event, fences the effect with a
  locked index CAS, and commits JSON, Markdown, index, and transaction receipt
  as one repairable operation. Same-effect retries are idempotent, cross-effect
  drift conflicts, and a prepared transaction repairs a partial artifact set.
  The receipt binds the pre-append index digest and byte offset, so a retry can
  repair only its own truncated final JSONL row while unrelated corruption
  still fails closed.
  Python retains `should-run`/settlement fact projection plus one coarse
  transport call and the legacy kernel index lock; it no longer constructs or
  writes the spend event.
- Quota void commit: TypeScript finds the referenced spend under the mutation
  lock, reduces the before/after accounting decision, constructs the canonical
  correction, and commits its JSON, Markdown, index row, and prepared receipt
  through the closed spend/void accounting-artifact kernel. Same-effect retry
  replays or repairs one transaction; a fresh CLI invocation remains a fresh
  effect and therefore preserves the existing ability to append another
  correction for the same spend target. Malformed index rows now fail closed
  instead of being skipped. Void artifact names include an effect digest and
  JSONL rows use compact JSON; public payload semantics remain stable. The
  shared kernel also validates persisted receipt/path identity for spend
  recovery. Python retains `should-run` facts, UUID/clock ownership, one coarse
  transport call, and the legacy cross-writer index lock.
- Local task-lease lifecycle: native TypeScript transactions now own acquire,
  renew, transfer, release, terminal verification, holder verification, and
  fence close. They own boundary decode, handoff and owner/Todo eligibility,
  same-Todo and overlapping-write-scope conflicts, compare-and-swap,
  generation/idempotency rules, operation and fence receipts, the per-goal
  mutation lock, atomic lease persistence, and canonical results. Python
  projects compact registry, active-state, event-log, and rollout-log facts
  with before/after source digests, then makes one native transaction call.
  TypeScript revalidates those sources under the lease lock before decisions
  and immediately before writes. Closed fence replay is generation-bound: a
  non-required receipt is reusable only while no lease record exists, a
  committed release must still match the exact retired generation, and an
  aborted close can re-verify only the same active generation under a new lock.
  The provider-neutral coordination executor reaches the same pure TypeScript
  decisions for acquire, renew, transfer, and release through typed Python
  adapters. Shared provider execution, CAS, and authority receipts tracked by
  #3669 remain outside this cutover.
- Quota monitor-poll commit: TypeScript revalidates quiet, due, external, and
  exact-blocked-wait admission; constructs the canonical monitor target and
  event; journals a Todo-provider intent before mutation; and owns effect
  replay, index CAS, artifact-path fencing, and prepared/committed repair. A
  no-Todo poll and every completed replay use one reduction. A real Todo
  writeback remains an explicit idempotent Python provider between one
  preflight and one final reduction. Provider retry is bound to a persisted
  monitor effect identity, and stale older effects cannot overwrite a newer
  observation.
- Task-lease acquire: TypeScript owns identity normalization, settlement-plan
  projection, provider failure classification, ordered receipt construction,
  and the canonical result. Python invokes the existing atomic provider between
  one preflight and one final reduction; the provider retains the per-goal lock,
  owner eligibility, conflict, compare-and-swap, idempotency, and lease-file
  durability checks. Invalid identities stop before the provider, while a
  crash/retry after the provider re-enters its same-key idempotent path.

The quota-accounting cutovers remove the Python spend and void event builders
and their three-file writers. Their bounded facades exit when quota decision
and the top-level CLI execute in-process TypeScript, all run-index writers use
the native lock, and the legacy Python void API compatibility window closes.
Until then Python supplies compact projection facts, clock/effect identity,
result validation, and the shared legacy index lock. The Todo cutover removes
the Python state-evaluation dataclass, local identity
projection, replay helper, and public runtime handlers for those implementation
leaves. The remaining Python Todo facade owns fact projection, transport,
external command execution, source compare-and-swap, legacy response
projection, and the actual Markdown/event write. It exits when those writers
and the CLI move into the native TS transaction. The remaining fine-grained
Turn facade exits after quota and host-adapter callers move to their own coarse
transactions. The
task-lease semantic facade, atomic Python providers, settlement bridge
operation, and lifecycle rule engine are deleted. Python retains compact source
projection, one process transport, context-manager plumbing that carries the
opaque fence token/receipt id, legacy response projection, and compatibility
imports for existing Python callers. Those surfaces exit when the top-level
LoopX CLI, Todo writers, and authority-source adapters call the TypeScript
transactions in-process. The shared Python/TypeScript lock protocol remains for
the Python handoff-mode transition and other cross-runtime holders; it exits
when no Python writer acquires the per-goal lease lock. Vision checkpointing
remains a separate refresh/writeback transaction because it does not share the
delivery-selection lifecycle phase.

Lifecycle receipts recover a completed mutation or a held/closed fence after a
transport response is lost or the owning caller exits. Long-lived fence locks
record the Python caller PID rather than the managed Node server PID, and stale
reclaim uses token claims plus replacement-resistant file identity before
retiring a lock. This is not an exactly-once guarantee for a timed-out handler
that is still executing concurrently inside the same Node process; callers must
not start a second independent operation while that handler may still be live.

#### Quota void commit migration economics

| Field | Receipt |
| --- | --- |
| Canonical owner | Before: Python `slot_accounting.py` owned spend-target lookup, correction reduction, event/result construction, artifact allocation, and JSON/Markdown/index persistence. After: versioned TypeScript `quota.void.commit` owns those semantics plus effect fencing, index CAS, receipts, replay, and repair through the closed spend/void accounting kernel. |
| Legacy semantic code deleted | 212 Python product LOC covering the prior void lookup, transition, event/projection, path-allocation, and JSON/Markdown/index writer path. |
| Bridge code added | 263 Python diff LOC: the 243-line bounded `void_commit.py` transport/compatibility facade plus 20 import, re-export, normalization, and route-wiring lines in `loopx/quota.py` and the legacy `slot_accounting.py` surface. |
| Cross-runtime calls | The public execute and dry-run paths move from zero crossings to one coarse request/response. Exact-effect replay or repair also uses one request/response. Distinct CLI invocations remain distinct effects; the legacy two-step preview-plus-record compatibility surface uses one call per entry point. |
| Product-code net change | Product code is +2,210/−898 LOC, net +1,312. Tests/examples are +1,416/−3, net +1,413; build configuration is +3 and docs are excluded. The production shared kernel is already used by spend and void, replacing 671 lines in `spend_commit.ts` rather than creating a speculative framework. |
| Migration scaffolding | No migration-only worker, parity corpus, or temporary schema framework is added. Native boundary/invariant/replay/CAS/repair tests remain as shipped and persisted contracts; Python bridge tests exit with the compatibility facade. |
| Facade exit | Delete the Python void facade when quota decision and the top-level CLI run in-process TypeScript, all run-index writers use the native lock, and the legacy `build_*void*`/`record_*void*` Python API compatibility window closes. |
| Correctness and performance | Typed-decoder negatives, legacy target compatibility, effect isolation, index CAS, malformed receipts and paths, exact index-row identity, supported duplicate-index repair, concurrent mutation, truncated-tail repair, public CLI behavior, and clean wheel/sdist semantic probes pass. Across 16 cold starts, p50/p95 is 230.88/260.92 ms; 128 warm typed pings are 1.07/1.29 ms and warm void previews are 1.93/2.34 ms. Across 64 durable facade transactions, commit is 30.64/37.49 ms and exact-effect replay is 8.05/9.86 ms. Daemon RSS is 108.38 MiB idle and 109.80 MiB after 256 requests. In 64 interleaved full-CLI pairs, baseline/candidate p50/p95 is 736.51/828.68 versus 779.52/856.49 ms: p95 +27.81 ms (+3.36%). The absolute delta is the measured cost of one new managed-runtime fingerprint/request plus prepared-receipt durability; the percentage stays below the 5% material-regression gate, and Stage 3 removes that crossing. |

#### Task-lease acquire migration economics

| Field | Receipt |
| --- | --- |
| Canonical owner | Before: Python owned the atomic acquire provider and TypeScript reduced settlement around it. After: `task_lease_acquire.ts` owns the complete locked transaction and canonical result. |
| Legacy semantic code deleted | 973 product LOC: the Python provider/acquire composition and conflict path, the Python↔TS settlement bridge/reducer and handler, and legacy CLI settlement projection. |
| Bridge code added | About 641 gross product LOC are bounded compatibility code: compact Python authority projection plus one managed-runtime request, the compatibility import, the shared Python/TypeScript lock protocol, and the typed NoKV/coordination decision adapter. The local projection/import exit with the top-level Node CLI; the dual lock exits with the remaining lease writers and fences; the coordination adapter exits when that executor moves to the native runtime. |
| Cross-runtime calls | Public acquire and replay paths move from two request/response reductions to one native transaction request/response. |
| Product-code net change | Product code is +2,130/−1,122 LOC, net +1,008. Tests and fixtures are reported separately at +898/−1,081; build configuration is +4. |
| Migration scaffolding | The task-lease settlement characterization, fault-matrix, incident-replay, and fixture slices were deleted. Native invariant, crash/retry, direct-CLI, adapter, and cross-runtime lock tests replace them; no migration-only worker remains. |
| Facade exit | The semantic facade, atomic provider, settlement operation, and legacy CLI projection exit in this cutover. Only source/transport compatibility and cross-runtime serialization remain, with the deletion triggers above. |
| Correctness and performance | The public CLI matched the prior implementation in five acquire/replay/failure scenarios; 20 focused native tests, the 207-test Node suite, 4,615 Python tests (12 skipped), crash/retry and packaged-wheel smokes pass. In a matched 16-sample full-CLI run, happy-path p95 moved from 1,593.7 ms to 1,167.8 ms and replay p95 from 513.3 ms to 445.4 ms; medians were 364.6→425.6 ms and 343.3→351.9 ms respectively. |

#### Task-lease lifecycle migration economics

| Field | Receipt |
| --- | --- |
| Canonical owner | Before: Python owned renew, transfer, release, terminal/holder verification, and fence close around the native acquire transaction. After: `task_lease_lifecycle.ts` owns all six operations, their locked persistence, and their canonical receipts/results. |
| Legacy semantic code deleted | The Python lifecycle decision, CAS, lease-write, and in-process fence rule paths are removed; Python keeps only authority/source projection, managed-runtime transport, context-manager adaptation, and legacy public payload projection. |
| Cross-runtime calls | Each lifecycle verb uses one coarse native request/response. A held fence intentionally spans two calls, verify then close, because the caller's Todo mutation occurs between them while the same lock token remains authoritative. |
| Recovery contract | Operation receipts fence retry identity and expected generation. Fence receipts distinguish acquired, held, and closed states; replay revalidates current authority and the current or retired lease generation before returning an idempotent result. |
| Locking debt | PID liveness, token claims, stale reclaim, and replacement-resistant file identity make the shared lock safe across Python and Node. This bounded protocol is deleted after the handoff-mode transition and every remaining Python lease-lock holder move in-process. |
| Out of scope | This cutover shares the ordinary lifecycle decision but does not implement #3669's shared-provider execution, CAS, or authority receipts, and does not promise exactly-once execution for a second request issued while the original Node handler is still running after a client timeout. |

#### Todo terminal lifecycle migration economics

| Field | Receipt |
| --- | --- |
| Canonical owner | Before: Python owned terminal admission, successor derivation, and archive retention, while completion reduction and lease operations crossed narrower TS boundaries. After: `todo_lifecycle_decision.ts`, `todo_successor_derivation.ts`, `todo_terminal_lifecycle.ts`, and `todo_archive_selection.ts` are the typed owners of terminal admission, successor defaults/inheritance/bindings, lease release, completion reduction, CAS, receipt replay, and archive selection. The terminal transaction imports the successor and archive owners directly; legacy Markdown/event writers call their strict wire handlers and only materialize the returned proposal. |
| Legacy semantic code deleted | 284 Python product LOC are removed from semantic ownership: 74 lines for terminal decision plus archive eligibility/order/standing-receipt selection, and 210 lines of duplicated successor priority, capability/binding, exclusion, continuation, and predecessor-link derivation across Markdown complete/supersede and event completion. The remaining Python complete/supersede bodies are unpromoted compatibility writers, not a second terminal decision owner. Other deleted lines are adapter reshaping and moves and are not counted as payoff. |
| Bridge code added | 937 gross product LOC are classified as bounded transport/compatibility: the 538-line `provider_terminal_lifecycle.py`, 135-line successor intent/result adapter, 173-line local TS request decoder/router delta, 33-line legacy archive result adapter, 10 handler-registration lines, 6 projection-settlement lines, and 42 lines that route Turn durable readback to canonical authority after promotion. The 29-line `resolve_todo_state_path` extraction is a move, not payoff. Host-local validation declaration storage/execution is a retained external effect and is not mislabeled as bridge deletion. |
| Successor ownership | The public caller owns requested successor text and options. Python serializes that intent and adapts the typed proposal to the legacy writer. TypeScript alone derives inherited priority, default task class, capability binding, user binding, exclusions, same-agent continuity, and `unblocks_todo_id`; the promoted lifecycle derives and validates these facts inside the same provider transaction before atomically committing the target, successors, lease, and receipt. The legacy and event paths invoke the same pure TS decision through one effect-runtime call. |
| Cross-runtime calls | Measured at the public facade: promoted complete without validation, supersede, and archive use three request/responses (`todo_list`, terminal/archive transaction, projection readback). A validated complete uses four (`todo_list`, terminal preflight, terminal finalization, projection readback) plus one declared host-local validation effect. After an injected post-commit projection crash, the first attempt uses two calls and the receipt replay uses three. The promoted happy path did not exist before this cutover; a legacy terminal call uses the existing TS admission decision and adds one coarse successor-derivation call only when it has generated successor intent. |
| Product-code net change | Final merge-base classification is +4,051/−364 product LOC, net +3,687; tests/fixtures/examples are +3,594/−156, net +3,438; generated contracts are +3/−0 and docs are excluded. The increase delivers a complete provider-neutral transaction, one successor semantic owner, real File/PostgreSQL conformance, public facade parity, and durable mutation gates; it is not counted as deletion payoff. |
| Migration scaffolding | The production-scale fixture, three-arm rehearsal, provider conformance, public legacy/promoted parity matrix, and mutation cases remain because they express durable migration contracts. The compatibility facade and its call-count assertions exit with the facade; provider-neutral transaction and archive-order mutation coverage remain. |
| Facade exit | Retire the legacy successor-derivation/archive-selection crossings and their call-count tests when the last Markdown/event business writer migrates. Remove terminal facade portions as registry/lifecycle inputs and journal consumers converge; a native CLI permits full transport removal but is not required to delete duplicated decisions. Keep only caller-required input, private validation execution and projection-delivery adapters, even if they remain Python. Delete `resolve_todo_state_path` only after its concrete path consumers disappear; keep permanent Markdown rendering and qualified import/export. |
| Correctness evidence | Independent archive-order/standing-receipt semantics kill an oldest-selection mutant; optional `note`/`evidence`/`reason` cover `None`, empty, ordinary, Python-Unicode-whitespace-only, and whitespace compaction before/after promotion. Public-entry tests prove canonical commit followed by Turn-journal crash/retry settles once, logical retry tolerates prose changes but rejects different successor intent, rejected/concurrent/crash-recovered validated create publishes only the accepted digest sidecar, and legacy/promoted illegal actors retain a domain-rejection class. Independent successor tests pin priority, binding, exclusion, continuation, and predecessor-link inheritance. Stage 2C proves provider-first fence routing, live-lease import, orphan-history filtering, management-lock exclusion, replay, and zero-write previews. File and real PostgreSQL providers execute the same terminal conformance, while the independent legacy arm remains mandatory compatibility evidence. |

The monitor-poll cutover removes the Python admission-policy and monitor-target
modules and the Python event/replay/artifact writer. Its bounded facade exits
when quota `should-run`, Todo monitor persistence, status projection, and the
remaining run-index writers execute in the native TypeScript process; until
then it carries compact facts, the named Todo provider, legacy after-projection,
and the shared Python index lock only.

The final merge-base migration economics receipt for this cutover is:

| Field | Evidence |
| --- | --- |
| Canonical owner | Before: Python `monitor_poll.py`, `monitor_poll_policy.py`, and `monitor_target.py`. After: the versioned TypeScript `quota.monitor_poll.commit` transaction owns admission, target/event/result construction, replay/CAS, provider intent, and durable artifacts; Python retains compact fact projection, the named Todo provider, transport, and legacy after-projection only. |
| Legacy semantic code deleted | 826 Python product LOC: 601 replaced lines in `monitor_poll.py`, the 161-line policy module, and the 64-line target module. |
| Bridge code added | 495 Python diff LOC used only by the bounded bridge: 455 lines across `_NativeMonitorPollRejected`, `_mapping`, `_monitor_candidate`, `_due_monitor_candidates`, `_vision_wait_state`, `_registry_due_monitor`, `_decision_packet`, `_observation_packet`, `_index_digest`, `_native_result`, `_request`, `build_quota_monitor_poll_event`, `find_quota_monitor_poll_turn`, `_status_with_monitor_poll`, `_reload_status_after_monitor_writeback`, `_monitor_poll_failure`, `_capability_declaration_retry`, and `record_quota_monitor_poll_for_decision`, plus 40 import/schema wiring lines. The 34-line `_provider_writeback` is excluded because it adapts the retained real provider. |
| Cross-runtime calls | Before: zero because Python owned the whole path. After: one request/response for a no-Todo write, exact replay, or recovery; one preflight plus one final reduction when the real Todo provider runs. |
| Product-code net change | 2,743 added minus 831 deleted product LOC, net +1,912; tests/examples are separately 1,045 added minus 242 deleted, net +803, and docs are excluded. The temporary increase buys one complete transaction and cannot repeat: the next deletion is the 495-line bridge when quota decision, Todo persistence, status projection, and remaining index writers are native. |
| Migration scaffolding | Deleted the 218-line implementation-specific policy smoke and 18 target-helper assertions. No temporary parity harness is committed; typed boundary, public CLI, replay/CAS, malformed-input, provider, and repair tests remain because they express shipped or persisted contracts. |
| Facade exit | The Python facade remains only for compact source facts, the Todo provider, one shared cross-writer lock, transport, and legacy result projection. Delete it when `should-run`, Todo monitor persistence, status projection, and every run-index writer execute in the native TypeScript process. |
| Correctness and performance | Identity/admission, effect isolation, provider fencing, malformed receipts, concurrent CAS, crash repair, packaging, and launcher coverage pass. Managed-runtime cold start is 274.35/450.44 ms p50/p95, warm event 1.13/1.72 ms, durable commit 2.06/2.27 ms, and memory is 126.0 MiB idle/after burst. After replacing the prepared-plus-staged receipt sequence with one conservative prepared WAL that retains the index as commit proof, and skipping Git subprocesses only when a registry is provably outside a worktree, the final 64 interleaved full-CLI pairs report Todo write baseline/candidate p50/p95 of 663.34/971.40 versus 631.96/878.10 ms (candidate p95 -93.31 ms, -9.61%) and replay of 598.23/910.75 versus 580.13/900.69 ms (candidate p95 -10.06 ms, -1.10%). Both p95 deltas stay within the 5% and 25 ms full-CLI limits, resolving the earlier owner-review hold. |

### Stage 3 — CLI and App convergence

Ship a native TS CLI that imports the kernel in-process. Keep one automatically
selected authority path: direct in-process execution for CLI-only use, or the
managed daemon when the App/scheduler already owns the workspace. Remove the
Python bridge and its protocol after no production caller needs them.

The receipt-bound scheduler ACK/failure route is the first bounded native-CLI
slice in this stage. It is an exact launcher dispatch, not a generic Node
router, and leaves `quota should-run`, host automation mutation, and broader
quota policy in their existing owners.

### Stage 4 — Distribution cleanup

Package the kernel for npm and LoopX release artifacts, remove the Python
runtime requirement, and decide whether the optional daemon ships as a normal
Node entry point or a LoopX-built single executable. Do not silently depend on
an unofficial third-party Node wheel.

## 5. Payoff-phase PR contract

Every later migration PR includes a **migration economics receipt** in its
description and validation comment:

| Field | Required evidence |
| --- | --- |
| Canonical owner | Owner before and after the cutover; no ambiguous dual authority |
| Legacy semantic code deleted | Product LOC of replaced Python rules, fine-grained APIs, enums/dataclasses, and implementation-only adapters removed |
| Bridge code added | Product LOC added solely for Python↔TS transport or compatibility |
| Cross-runtime calls | Happy-path and recovery-path request/response counts before and after; target one request/response when effects are TS-owned or no provider is pending, otherwise at most one preflight plus one final reduction while a real Python provider remains |
| Product-code net change | Added minus deleted product LOC, reported separately from tests, fixtures, generated files, and docs |
| Migration scaffolding | Characterization/parity helpers added, retained, or deleted, with a concrete removal trigger |
| Facade exit | Facade deleted now, or the exact remaining caller/compatibility contract and deletion condition |
| Correctness and performance | Invariants, negative cases, matched end-to-end baseline, packaging, crash/retry, and host coverage relevant to the changed transaction |

LOC uses the final merge-base diff and classifies production code separately
from tests, fixtures, generated files, and docs. Moved code counts as deletion
plus addition; bridge LOC must name the functions whose only purpose is
cross-runtime transport or compatibility. Round trips are counted on one named
public happy path and its retry/recovery path, not inferred from handler count.

A PR that only relocates code, adds a handler, or increases bridge surface
without deleting authority does not pass this phase. A temporary net increase
may be accepted for one cohesive transaction only when the receipt shows why
the bridge is bounded and which next deletion realizes the gain. That exception
cannot be chained across open-ended leaf migrations.

Stable primitive decoders may be shared through the existing small runtime
decoder module. Domain decoders stay in their bounded contexts; this RFC does
not authorize a generic schema framework.

## 6. Correctness and performance gates

### Correctness

- Independently stated algebra properties: identity, associativity where
  applicable, ordering, short-circuit, replay, and effect-id isolation.
- Exact output parity for the pinned characterization corpus.
- Negative cases for malformed state, cross-effect overwrite, partial commit,
  cancellation, permission denial, and budget rejection.
- Boundary decoders reject missing fields, wrong types, unsupported schema
  versions, and oversized or malformed payloads before domain dispatch. The
  cutover inventory lists any remaining `as unknown as T` seam and proves that
  it is guarded; promotion requires removing unvalidated assertions from the
  migrated domain's authority inputs.
- Awaited writes emit receipts only after their declared durability point;
  concurrent same-key mutations are serialized or use a tested CAS contract,
  and retry identity distinguishes successive checkpoints within one Turn.
- Process crash and retry cannot duplicate a committed internal effect.
- Wheel and sdist are installed into fresh environments and execute deep
  semantic probes from packaged files.

#### Caller-observable semantic parity is a promotion gate

Every Python-to-TypeScript cutover inventories the behavior of every production
caller branch before implementation. The inventory covers accepted input and
default normalization; supplied, omitted, empty, and explicit-clear arguments;
eligibility and overlapping-rejection precedence; complete diagnostics and
remediation; dispatch-to-persistence readback; authority, ownership, receipt,
and no-effect outcomes; and replay or concurrent updates when the transaction
supports them. Equal reason codes or successful provider conformance do not
establish parity.

The cutover PR records machine-replayable execution receipts for an immutable
baseline revision and the exact reviewed head. Both runs use the same bounded
script, synthetic fixture fingerprint, public production entrypoint, and real
affected backend unless an intentional delta is declared and independently
approved. Each receipt names the revision, command, backend, exit status,
normalized observation fingerprint, and public-safe evidence pointer or inline
observation. Normalization may remove documented nondeterminism such as a
temporary path or timestamp, but never diagnostics, field presence, precedence,
persisted state, identity, ownership, or effects.

The same harness must demonstrate regression sensitivity: it fails an
independently stated invariant on the historical defect or a deliberate
semantic mutation, such as dropping a field or diagnostic detail or adding a
stronger precondition, and passes on the fixed head. A unit test that bypasses
the production entrypoint, or a suite in which every provider already shares
the candidate rule, is supporting coverage rather than baseline/head proof. If
the real backend or immutable baseline cannot be exercised safely, promotion is
held as `not_yet_proven`; prose cannot waive the gap.

This qualification is offline evidence, not a second authority. Production
does not dual-run Python and TypeScript, derive expected results from the
candidate, or retain the legacy rule after cutover. Intentional behavior changes
are separated from parity rows, justified against the public contract, and
approved explicitly. After promotion, only fixtures that express durable public
or persisted semantics remain.

Characterization output is evidence, not specification. If a pinned behavior
contradicts an independently reviewed invariant, the PR must disclose and
separately approve the behavior change. Once the old authority is removed,
promotion also requires deleting characterization machinery that serves only
that implementation comparison; durable regression fixtures may remain when
they express a public or persisted compatibility contract.

### Performance

Measure cold startup separately from steady-state execution. Every transaction
cutover reports:

- managed runtime cold-start p50/p95;
- warm typed request p50/p95;
- representative complete transaction p50/p95 and cross-runtime round trips;
- full CLI p50/p95 versus the pinned Python baseline;
- daemon memory after idle and under a bounded request burst.

The default acceptance target remains warm, non-durable internal transitions
below 2 ms p95 and no material full-CLI regression (greater than 5% or an
unexplained 25 ms additive p95). Durable transactions are compared with a
matched durability baseline rather than the 2 ms kernel budget. A miss, or a
tail regression hidden by a faster microbenchmark, is an owner review gate and
cannot be silently relaxed.

## 7. Install, upgrade, and rollback

The migration must not ask users to manage a service. The Python-transition
release may require Node.js 22.6 or newer, but installer and `loopx doctor`
must detect it before normal control-plane work and provide exact remediation.
The wheel and sdist carry the TS source and versioned schemas.

The runtime is healthy while idle-exited: `stopped` means the next
control-plane request will start it automatically, not that the user must run a
daemon command. CLI and App surfaces consume the same lifecycle projection
(`running`, `stopped`, or `unavailable`) and stable diagnostic code. Raw stderr,
tokens, local paths, and private runtime metadata are not projected.

The runtime fingerprint includes every executed TS module and contract. An
upgrade starts a runtime for the new fingerprint; an old process can finish
in-flight work and exits on idle. Requests carry stable effect identities, so a
transport retry is safe only for handlers that are explicitly idempotent.

Rollback restores the previous artifact and fingerprint. Persisted state is
not rewritten into a TS-only format until a separately qualified state-schema
cutover.

## 8. Non-goals and stop conditions

- No permanent Python and TS semantic twins.
- No server per domain and no generic arbitrary-command executor.
- No big-bang CLI rewrite.
- No dual-write of production semantic state as a migration strategy.
- No performance claim from microbenchmarks alone.
- No more flat migration of leaf helpers merely because the bridge exists.
- No duplicate Python enum/dataclass retained without a named public import,
  persisted wire contract, or unmigrated caller.
- No permanent characterization harness for an implementation that no longer
  exists.

Stop or replan if the bridge becomes user-managed, a migrated rule still has a
Python semantic owner, the handler boundary becomes chatty, two consecutive PRs
increase bridge/scaffolding without retiring a facade, or a transaction cannot
meet its invariant/recovery/performance gates without weakening existing
behavior.
