# RFC: TypeScript Control-Plane Migration Direction v0

- Status: Accepted, transaction-payoff phase in progress
- Proposed by: LoopX maintainers
- Date: 2026-08-15
- Last revised: 2026-09-05
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

The next replacement slice makes promoted `todo add` a native create
transaction on that same authority owner. Python validates the established CLI
arguments and adapts them once into the versioned domain record; TypeScript
owns duplicate identity, replay, actor/owner eligibility, CAS, receipt, and
projection-outbox mutation. Preview and the real subprocess CLI path are tested
after deleting the Markdown state file, so promotion cannot silently regain a
Markdown write path. Completion-validation argv remains typed data rather than
a shell-encoded compatibility field. Default, unpromoted goals retain their
existing Markdown transaction until their explicit promotion boundary.

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

The owning modules remain `control_plane/work_items/delivery_outcome.py`,
`delivery_signals.py`, and `outcome_followthrough.py`. This is a correctness
prerequisite inside the existing owner, not a new capability/provider or a
completed TypeScript transaction migration. It deletes keyword inference and
its status constants without adding a runtime crossing, schema, or service.
The existing typed blocker-settlement predicate is reused rather than copied.

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
- Legacy outcome-marker/hint configuration remains readable and preserves
  whether an outcome floor is configured. Its words no longer classify runs.
  No persisted history is rewritten and no new default-off flag restores the
  erroneous behavior. This intentionally changes status, handoff/review, and
  quota decisions previously derived from untyped historical labels.

Within this delivery domain, the migration unit is the complete
delivery-history-to-obligation projection, including scale/outcome streaks and
its status/quota consumers. This defines the slice boundary without displacing
the provider-first Todo sequence below.
It must cross at most once per bounded history batch, delete the replaced
Python decision path, preserve independently reviewed typed cases, and retain
narrative-mutation regressions through the real CLI. Transport-only golden
parity is insufficient because the old inference was incorrect. Separately
inventory writers still omitting material-result fields and retire obsolete
marker/hint configuration with an explicit compatibility plan. Exact legacy
lifecycle classification codes and unrelated cadence policies are outside this
slice; they must not be reported as migrated or globally free of prose rules.

### Next delivery sequence

1. **One provider-first Todo transaction family.** Route native create, claim,
   update, complete-with-successor, archive, and their lease effects through
   the existing TS authority owner. Deliver coherent vertical slices with the
   real CLI caller, replay/CAS/error tests, and removal of the replaced Python
   decisions. A schema or constants-only PR does not satisfy this exit.
   A single-command slice (for example `todo update --text/--note` through a
   shared compatibility editor) is a validation milestone for synthetic or
   qualification goals, never a real-goal promotion: once a goal is promoted,
   every other legacy writer is still fenced fail-closed. Promoting a live goal
   therefore waits until the write-command family its agents actually use routes
   through the same unified TS commit authority (per-command transaction types
   behind one effect-runtime boundary, not parallel semantic owners) and until capture/projection outbox
   delivery is flushed. The deletion payoff lands only when the in-place
   Markdown editor is replaced by a pure projection renderer behind that one
   entry point.

2. **Qualification before activation.** Join that path with the shared-authority
   RFC's explicit v0 import, consumer parity, writer fencing, capture/projection
   outbox recovery and fenced export. Integrate the local-persistence slice
   above, including historical receipt retention, volume and >=10-day soak
   evidence. File-v0 conformance is insufficient for long-goal promotion. No
   default authority flip or dependency on PostgreSQL service readiness.
3. **Retire the bridge, then converge entrypoints.** Delete the replaced
   reference aggregate and Python facades when their last callers switch;
   reuse the same kernel from native CLI/App and optional daemon. Report
   product LOC removed, bridge LOC added, crossings, and remaining deletion
   conditions per slice. Stop and replan after two scaffolding-only slices.

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
  continuation/recovery, and completion metadata in one transaction. A Todo
  without declared validation, including a replay, uses one reduction. A real
  caller-approved validation command remains an explicit Python provider
  between two reductions. A source snapshot is compared after the mutation
  lock so a receipt for one declaration cannot authorize a changed Todo.
  Materialized and event-projected writes consume the same typed result.
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
leaves. The remaining Python Todo facade owns transport, external command
execution, source compare-and-swap, legacy response projection, and the actual
Markdown/event write. It exits when those writers and the CLI move into the
native TS transaction. The remaining fine-grained Turn facade exits after
quota and host-adapter callers move to their own coarse transactions. The
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
