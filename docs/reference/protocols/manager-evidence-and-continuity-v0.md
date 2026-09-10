# Manager evidence and continuity v0

Status: proposed staged design. The synchronous manager transport foundation
exists on this change branch; the portfolio, shared request ledger, and
three-goal acceptance below are not yet implemented or qualified end to end.
This document does not introduce a CLI command or enable Decision Context.

## Ownership and defaults

Core retains authoritative Goal, Todo, gate, quota, evidence, and lifecycle
state. The manager observes, explains, and coordinates that state. Decision
Context, when explicitly enabled, combines verified evidence with background
context to make advisory proposals. Neither consumer may store an editable
second version of "real progress" or turn its own chat summary into evidence.

The built-in manager is a stable logical role, separate from a replaceable
executor session. Frontend conversation and an addressed Lark message should
receive a synchronous conversational response within their authorized scope.
Long-running work is assigned to an exact worker and returns a task receipt;
acceptance of work is never reported as completed work.

Live activity labels follow the executor's typed event. Receiving a message,
reasoning, producing an answer, and invoking a tool are different activities.
An unknown item remains generic activity; item completion alone proves neither
a Goal read nor a successful check. Do not expose item bodies or tool inputs in
activity labels. Diagnose response latency using request acceptance, upstream
turn start, first answer, and completion timestamps; a silent upstream interval
does not identify a scheduler delay or prove what the executor was doing.

Reuse the existing [global-manager protocol](global-manager-command-v0.md),
[Decision Context source plane](decision-context-architecture-v0.md), and
[periodic report lifecycle](periodic-report-v0.md). The proposed Goal Portfolio
provider is a read model serving the existing manager outcome, not a new
capability merely to introduce a provider. Core owns typed state semantics;
presentation owns bounded collection and rendering. An optional
`DecisionSourceProvider` adapter can exact-read this same projection without
making Decision Context a prerequisite for basic manager reads.

Manager upgrades retain the existing connection identity, Topic and receipts.
Retiring an async inbox and saving its replacement form one compensated write
operation: hold the binding/source mutation locks, and restore the prior
binding, source registry and affected shared Goal if a write fails. Recovery
must verify those authorities before claiming the old route was preserved;
failed compensation returns `upgrade_recovery_required`. Shared-registry
recovery must retain concurrent updates to other Goals. This exception-recovery
contract does not claim crash-atomic persistence across multiple files.

## A bounded portfolio with explicit coverage

Discover Goals from the authorized registry inventory, including unavailable
registered hosts. Do not infer inventory from recent chats, a limited dashboard
list, or only Goals present in the attention queue. Bind every row to opaque
host, project, Goal, registered Agent, and task references. Missing Agent/task
identity is explicit unknown, never guessed from a display name.

For each discovered Goal, collect compact canonical status, typed Todo/gate
projections, and evidence-backed delivery history. Existing global-todos and
global-risks classification rules remain authoritative at their owning seam;
the portfolio must not duplicate them in prose or an LLM prompt.

The proposed projection records:

| Component | Required meaning |
| --- | --- |
| Identity | Exact host/project/Goal identity and verified Agent/task relations |
| Provenance | Source reference, revision or digest, source observation time, collection time |
| Work | Recent verified deliveries and evidence refs, separately from accounting and liveness |
| Readiness | Typed runnable, awaiting acceptance, dependency blocked, or unknown; explicit source relation |
| Owner attention | Only verified owner actions/gates, with affected scope and why the Agent cannot proceed |
| Quality | Fresh, stale, conflicting, or unreadable facts; affected fields and reason |
| Coverage | Inventory source/revision, discovered, attempted, verified, omitted counts and omission reasons |

Coverage counts apply to the visible authorized inventory. Verification quality
partitions discovered Goals into verified, stale, conflicting, unreadable, and
uninspected categories; readiness is a separate axis. Pagination, time budgets,
unreachable hosts, and permission restrictions remain visible. If discovery
itself fails, the total is unknown, not zero. A verified empty inventory is
distinct from a failed empty response. Hidden Goal identities are not revealed
to an unauthorized audience merely to explain coverage.

A collection is not an atomic cross-host snapshot. Freeze its source revision
vector and time window. If a source changes during collection, boundedly retry
or mark the affected row inconsistent. Older evidence may remain visible with
its timestamp but cannot prove current absence of progress. An unreadable or
stale Goal must say "current progress unknown", not "no progress".

Progress selection uses typed delivery/evidence relations and stable outcome
identities. Select material outcomes before applying the display limit;
quota charges, wake-ups, polling, and report generation belong in supporting
accounting. A newer quota event must not evict an older genuine delivery.
Only a complete, fresh, bounded comparison may assert no new verified delivery
within that observed window; it says nothing about work outside coverage.

## One service, scoped continuity

The durable manager identity is independent of session process lifetime.
Conversations bind an authorization scope, audience policy revision, and
logical conversation ID. Default frontend private and external group scopes
remain separate. Transport membership alone does not grant access to another
Goal, personal financial context, or private company material.

Where an owner has explicitly established equivalent authorization scopes,
both entrypoints may reference the same logical conversation, frozen evidence
packet, request identity, and action receipt. "Synchronous" means a response
in the active conversation and consistent authorized state; it does not mean
mirroring all transcripts between groups. The current audience-hashed session
foundation provides separation, not proof of this cross-entrypoint continuity.

Evidence selection and audience filtering occur before model context and
rendering. Frontend and Lark views of the same snapshot and scope must agree on
facts, evidence, coverage, and uncertainty; wording may differ. Different
scopes may reveal different subsets and must not imply equal coverage. Caches
are disposable derived views keyed by source revisions and audience policy,
never lifecycle authorities.

## Requests, authority, and recovery

Reuse Core typed preview/apply commands and existing connector receipts.
Extend their owning boundary with a durable request envelope only where a
real cross-entrypoint call site needs it. Its identity binds an origin request,
logical conversation, verified requester/scope, exact target tuple, action,
payload digest, authorization reference, and expected target revision.

Transport event identity deduplicates transport retries. Explicit forwarding
or handoff carries the same origin request ID across entrypoints. Independently
typed similar messages are not safely deduplicated by text or time heuristics;
without shared identity, propose and confirm the intended action rather than
guess that a second execution was authorized. Changed payload with a reused
request ID is rejected. Recheck current scope and target revision before apply.

The action lifecycle distinguishes proposed, authorized, dispatched, confirmed,
failed, and outcome-unknown. Persist the dispatch intent before its effect and
bind the resulting receipt to the exact target. Replays return that receipt
without reapplying. After a crash with an uncertain external effect, reconcile
by provider idempotency/readback before retry; if the provider cannot prove the
result, retain outcome-unknown. Do not promise universal exactly-once effects.

Default manager duties allow authorized reads and summaries; reminders use an
existing authorized destination/subscription. Goal changes, steering,
cross-Goal dispatch, pause/resume, publishing, and trading keep their existing
operation-specific authority. A special role grants no extra permissions.
No new confirmation is needed where a valid standing grant already covers the
exact action. Missing grants or ambiguous targets never cause broadcast.

Periodic report persistence stays in `periodic_report`: freeze the evidence
snapshot and period, retain per-audience/sink delivery status, and commit the
publication cursor only after required delivery readback. Keep source scan,
decision review, report generation, and publication cursors distinct. A failed
optional sink does not erase a successful required-sink receipt. Restart resumes
pending delivery with the original report identity and reconciles uncertain
sends. Late-arriving material evidence remains eligible for the next report.

## Five acceptance scenarios

Use three owner-authorized real Goals from different projects. Keep actual
identities, source payloads, and receipts in ignored private qualification
state; public fixtures use synthetic peers. Never corrupt a live Goal to
simulate staleness or failures.

| Scenario | Required evidence |
| --- | --- |
| Ask what advanced today through both entrypoints | Same authorized frozen snapshot: matching material outcomes, evidence refs, coverage and uncertainty; exact channel readback |
| Material work followed by many accounting events | Real delivery retained after ranking and truncation; quota entries identified only as supporting accounting |
| One stale/unreadable Goal | Named authorized coverage gap and unknown current progress; no healthy/unchanged inference; controlled replay plus actual source observation |
| One authorized steering forwarded across entrypoints | One exact target transition; shared request ID and receipt; duplicate replay, wrong target, changed payload and revoked grant rejection |
| Restart after report dispatch | Resume from persisted per-sink receipt; no duplicate confirmed send; uncertain send reconciled; late major evidence included subsequently |

Mocks and transport tests support these checks but do not replace real source,
session, routing, and delivery qualification. Keep each scenario pending until
its evidence is recorded. Frontend/Lark equality is assessed only within the
same authorized scope; denied content must never reach model context.

## Delivery sequence and separate accounting

Host automations are generated by `loopx heartbeat-prompt --thin`. They bind
execution identity and wake the host; they do not contain domain priorities,
report calendars, source lists, strategy rules, or a private dispatch loop.
Goals and typed Todos own work and dependencies; capability profiles own
specialized behavior; providers and hooks execute their declared contracts.
The existing generator binds one Goal/Agent. A host allowing only one heartbeat
per conversation therefore needs a generic, explicit multi-Goal dispatch
contract before that one heartbeat can claim to drive a portfolio. Do not
silently drop a Goal, concatenate conflicting per-Goal lifecycle prompts, or
create a shadow scheduler to disguise the missing contract. Qualification must
prove authorized bindings, isolated quota/receipts, bounded selection and
fairness, and that one Goal's pause hint cannot stop other eligible work.

1. Finish the synchronous manager/worker default and in-place connection
   migration foundation. Qualify installed session routing; do not label it
   complete portfolio or reporting support.
2. Implement the bounded portfolio at the existing manager read boundary;
   prove coverage, evidence selection, freshness, and failure semantics first.
3. Feed the frozen projection to frontend and Lark, and optionally the existing
   Decision Context source interface; verify scoped consistency.
4. Close cross-entrypoint request identity and exact-target steering recovery
   through existing typed control contracts.
5. Extend existing periodic report recovery and complete all five real-goal
   acceptance scenarios before claiming reduced operator attention.

Track domain research outcomes, manager attention reduction, and reusable
product delivery separately, each with its own Goal, budget, evidence, and
next action. One delivery spends once against its accountable Goal; another
Goal may reference the evidence without claiming a second outcome. Protect a
recurring domain-validation slot in the owner's plan. Infrastructure progress
does not prove a research hypothesis or improve an investment result.
