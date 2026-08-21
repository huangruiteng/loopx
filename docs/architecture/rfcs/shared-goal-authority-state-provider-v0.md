# RFC: Shared-Goal Online Authority and Pluggable Coordination Provider (v0)

- Status: Draft, under maintainer review
- Proposed by: NoKV Lab
- Date: 2026-08-05; revised 2026-08-18
- Scope: a separate deployment contract for LoopX shared-goal coordination,
  complementing
  [`host-integration-surface-v0`](../../reference/protocols/host-integration-surface-v0.md)
- Source baseline: LoopX `c6a1da1eaa22962faaeb6d4050d867462e7665ff`
- Provider API baseline: NoKV `3d75d96965` (0.11.0 line). The Python
  `publish_bytes` generation-CAS mapping was exercised once by hand against a
  live NoKV stack at that pin (see the example README); the run is evidence for
  the mapping only, not part of any merge gate
- Language note: the
  [Chinese version](./shared-goal-authority-state-provider-v0.zh-CN.md) and this
  English version are semantic mirrors. A difference between them is a defect.

---

## 0. An Example to Help Everyone Understand

Example 1: a walkthrough of a real machine -> human -> machine handoff, and why
it wastes time

Suppose my agent on the devbox finishes a Rust PR, and the agent on my laptop is
responsible for review. The handoff looks like this:

- **T0**: the devbox agent finishes the change and opens the PR;
- **T1**: the code is delivered at a pinned head SHA. Git already handles this,
  so moving the code is not the problem;
- **T2**: I manually send the PR, source task, and review instructions to the
  laptop agent so that it knows there is work to do;
- **T3**: the laptop agent takes the work, but if its response is lost, I can
  only infer later from its behavior whether the claim actually succeeded.

T2 and T3 are where the time disappears. One machine has already finished, but
the next machine is still waiting for a person to relay the work. Even after it
takes the job, there is no proof that can be recovered after a crash. A faster
harness or model cannot make up for the hours when the human is away.

The full need clearly includes both "tell the next machine" and "prove that it
really took the work." The first RFC should not swallow messaging, scheduling,
quota, run history, and every LoopX file at once. This version starts with the
hardest small piece: when the laptop claims the review todo, only one endpoint
may win, and that winner must be able to replay its original receipt. Delivery
and wake-up remain with the
[`Agent IM, LoopX, And OpenViking Collaboration v0`](./agent-im-openviking-collaboration-v0.md)
delivery plane.

## 1. What This RFC Chooses

Think of the authority as the only bookkeeper. Endpoints never edit the ledger
directly; they submit a request saying, "I want to claim this work." The
bookkeeper checks the target todo, identity, named dependencies, and gates. If
the request passes, the claim, lease, and receipt are written together. If it
fails, the requester gets an explicit reason.

This time the bookkeeper gets one small ledger. We are not moving every LoopX
file into a remote store:

1. one goal that explicitly opts into shared mode has one **canonical
   coordination aggregate**;
2. each successful operation's state transition and original receipt land in
   the **same compare-and-set (CAS)**;
3. the authority makes decisions, while a provider only stores deterministic
   bytes reliably;
4. run history, status, quota, scheduler state, host sessions, and evidence
   bodies stay with their existing owners instead of entering this ledger.

NoKV is an optional provider behind the bookkeeper. Agents do not connect to
NoKV directly for coordination writes, and NoKV does not become the LoopX
control-plane authority.

The first runnable example has only one command, `claim_work`. For an existing
eligible todo, it records the soft claim, lease/fence, and receipt together. It
answers the two questions most likely to cause an incident—who wins when two
endpoints claim at once, and how a lost response recovers its original
receipt—without pretending that the complete lease lifecycle already ships.

The contention unit is `(goal_id, todo_id)` plus the preconditions actually
referenced by that todo, not the whole goal. Two endpoints claiming the same
todo yield one winner. Two endpoints claiming independent todos under one goal,
with unchanged target-scoped authorization, dependency, and gate facts, should
both succeed even if their first writes compete for the same aggregate CAS. The
authority reloads, revalidates, and retries internally instead of exposing an
unrelated provider-head advance as a domain conflict. This preserves the
todo-level concurrency shape in LoopX's current public contract in
[`architecture.md`](../../architecture.md).

Here is the failure sequence that matters most. Operation A succeeds with lease
`L1`, epoch `7`, but its response is lost. Operation B then advances another
independent todo in the same goal; B does not take over A's todo. When A
restarts and retries the same request, it must recover its original receipt
field for field. "This was already applied" plus B's current revision is not
enough: without `L1`, epoch `7`, and its expiry, A still cannot prove that it
was authorized to do the work.

### 1.1 The durable abstraction: storage, semantic authority, and reconciliation

The highest-value boundary is not "the LoopX server" versus "the NoKV server"
as two competing databases. It is three separately owned layers that may be
co-deployed while preserving different correctness contracts:

| Layer | Owns | Must not own |
| --- | --- | --- |
| Storage plane | Durable bytes and artifacts, provider generation CAS, snapshots, and provider recovery | Goal/todo meaning, actor eligibility, leases, or authority receipts |
| Semantic authority | Normalized commands, target-scoped preconditions, claims, lease epochs, fencing, revisions, and original receipts | Raw artifact bodies, provider placement, or background scheduling state |
| Reconciliation layer | Observation, expired-lease recovery, wake-request emission, and continuous Supervisor decisions through the same command contract | Direct head mutation, provider bypass, or a second source of coordination truth |

NoKV's workspace service is the candidate storage-plane implementation mapped
by this RFC; it still requires the staged qualification below. The LoopX
increment is the semantic authority that turns an opaque generation CAS into a
trusted `claim_work` result and, later, into recoverable execution ownership.
The reconciliation layer is a client of that authority, not another writer: a
Supervisor observes projections and issues typed commands such as reclaim or
requests a delivery-plane wake, while its scan cursor and scheduling state
remain outside the coordination head. The delivery plane still owns transport
and endpoint reachability; a delivered wake never proves an authority command
committed.

The same NoKV deployment may serve two intentionally separate paths:

- the **coordination path** stores only the canonical head and is writable only
  through authority-owned credentials;
- the **artifact path** may accept scoped checkpoint or evidence publication
  from a runtime, but only an opaque pointer, digest, and privacy class enter a
  reviewed coordination transition.

A recoverable workflow publishes an immutable checkpoint or evidence artifact
first, then commits its pointer with the relevant coordination transition.
Failure before the second step leaves an unreferenced artifact for independent
retention or collection; it must not leave the head pointing at an object that
was never durably published. Sharing a physical provider therefore does not
merge the two ownership contracts or require a cross-domain transaction.

Physical co-location is allowed. One deployment bundle may start a NoKV
workspace service, a LoopX authority endpoint, and a Supervisor worker. Here,
"separate" means separately owned contracts and credentials; it does not
require a separate repository, process, binary, or license in v0. An embedded
authority is sufficient for trusted local qualification. A shared deployment
needs an online authority boundary so that untrusted or stale clients cannot
publish a forged coordination head even when they legitimately hold scoped
artifact credentials.

### 1.2 Capability horizon and deployable product boundary

The layers above create a staged capability horizon without widening the v0
ledger:

| Horizon | Added capability | Proof required before promotion |
| --- | --- | --- |
| Deterministic shared coordination | Provider-neutral authority, state-plus-receipt CAS, replay, and target-scoped rebase | File-backed conformance and the P0 checks in Section 10 |
| Recoverable execution ownership | Renew, release, expired-lease reclaim, stale-fence rejection, and atomic completion with an accepted continuation/evidence pointer | Crash and clock-boundary tests showing that a superseded executor cannot write back |
| Continuous reconciliation | Supervisor observation, reclaim, delivery-plane wake requests, and remote-resume orchestration through authority commands | Restart-safe reconciliation with no direct provider writes or in-memory correctness dependency |
| Service-grade shared control plane | Authenticated principals, tenant-to-goal isolation, audit, bounded capacity, observability, service recovery, and eventually HA | An explicit deployment and migration contract with no authority bypass or silent local fallback |

This horizon does not move quota accounting, run history, raw evidence,
delivery state, or Supervisor runtime state into the coordination aggregate.
Those capabilities keep the owners and ledgers listed in Section 3 and connect
through typed commands, projections, or opaque pointers.

A thin network wrapper around the Apache coordination core is not by itself a
new product boundary. A separately distributed service becomes meaningful only
when it owns the network trust boundary and material authority/reconciliation
capabilities such as authentication, continuous supervision, remote recovery,
migration, audit, multi-tenancy, or HA. If the project later creates a
separately licensed server distribution, that boundary should follow this
deployable semantic-authority and reconciliation surface, not the NoKV adapter
or provider-neutral core. This RFC neither requires a repository split nor
selects separate license terms; the current policy remains
[`LoopX Licensing`](../../project/licensing.md).

## 2. What We Will Do, and What We Will Not

**What this version will do**

- give one shared goal an online, provider-neutral coordination authority;
- make concurrent claims on the same todo resolve to one accepted owner while
  allowing independent todos to succeed after an internal CAS rebase;
- bind each operation identity to one normalized request digest and reject the
  same id when it is reused with different semantics;
- recover the original receipt after later operations advance the ledger;
- keep LoopX's default local mode unchanged;
- say how every existing durable state category joins—or stays outside—this
  boundary.

**What this version explicitly will not do**

- build a generic distributed filesystem or database for all LoopX state;
- support offline multi-writer merge or offline controlled writes;
- mix message delivery, wake-up, presence, or an Agent IM protocol into the
  storage contract;
- define multi-tenant public deployment, authentication, HA, or provider
  failover;
- move quota, scheduler state, run history, raw evidence, host sessions, or
  extension-owned ledgers into the coordination head;
- automatically promote the current event projection or any provider;
- let an agent or extension bypass the authority and connect to storage.

## 3. What LoopX Stores Today, and How Each Part Connects

The owner's key question was that LoopX state already lives across several
files, and not every durable file belongs in one head. Two machines can both
have a correct local route; status is computed; quota accounting is an
append-style ledger. These are different write models.

The table below therefore lays the ledgers out first: who writes each one
today, how it is written, and where it belongs after shared mode exists. It is
organized by logical state and field group rather than a fixed file count. One
physical file may mix several owners, and a new host or extension may add local
artifacts without changing this RFC.

Integration classes used below:

- **shared canonical**: authoritative only after explicit shared-mode opt-in;
- **derived**: recompute from its named source; never accept lifecycle writes;
- **synchronized ledger**: replicate or union by stable identity under its own
  append contract, not through the coordination head;
- **host-local**: valid only for one host, runtime, or checkout;
- **independent ledger**: retains its capability or accounting owner;
- **excluded body**: only a redacted digest or pointer may cross the boundary.

| Logical state / current surface | Current owner and write model | v0 integration strategy |
| --- | --- | --- |
| Todo lifecycle, soft claim, dependency, and gate fields in `ACTIVE_GOAL_STATE.md` | Markdown active state remains the current source of truth. Todo commands use a local file lock and whole-document replacement. A state-event projection is used only when an event log already exists. | Only the normalized fields required to validate the P0 commands become **shared canonical** after opt-in. Markdown remains canonical in default mode and becomes a local projection for migrated fields in shared mode. Private prose stays excluded. |
| Optional hard task leases under `goals/<goal>/task-leases/` | Per-todo JSON is atomically replaced under a goal-local lock; release retains an inactive terminal record so version and `lease_epoch` cannot ABA across re-acquire. Lease effectiveness also reads todo status, soft claim, exclusions, and registered agents. | Fold claim, lease, terminal generation, and fence into the same shared aggregate and authority revision. Do not keep an independently writable lease file in shared mode. |
| Applied-operation receipts | LoopX has scoped receipt precedents, including Turn journals and heartbeat receipts, but no durable shared-goal operation-to-receipt index. | Add the replayable receipt index as **shared canonical**, committed in the same CAS as the state transition. |
| Project-registry logical identity, agent profiles, grants, and policy | Project registry is local configuration written as a JSON replacement. These fields are mixed with routes and private references. | The authority consumes an explicitly versioned compact authorization projection or digest. The whole registry is not stored in the coordination head, and registry mutation is not a P0 command. |
| Project/global registry routes: `source_registry`, repo checkout, state file, runtime root | The global registry is a synchronized host-local route projection and records absolute local paths. | **Host-local**. Share stable goal/repository identity where needed, never route paths. |
| Candidate state events in `events.jsonl` | The current migration bridge keeps Markdown authoritative. Event append uses local locking; multi-event append is not a transaction. | Read-only shadow/canary input. This RFC does not promote it or use it to prove atomic completion. |
| Run JSON/Markdown and raw evidence bodies | Run writers reserve local artifact names and then write detailed records. Content and paths may be private. | **Excluded body** or external artifact-store object. The aggregate may carry only an opaque pointer, digest, privacy class, and exact code revision when a later command requires them. |
| `runs/index.jsonl` run history | A mixed append index references run artifacts and may contain absolute paths. It also carries several classifications, including quota accounting rows. | A future **synchronized ledger** needs stable identities, deduplication, and redaction. It is not part of the coordination head. |
| `rollout-event-log.jsonl` | A mixed public-safe diagnostic stream. Core CLI rollout append is intentionally best-effort and happens after the primary command; ordinary todo events are not keyed by the controlled operation identity. | **Derived** observability projection. A failed rollout append cannot invalidate or prove a coordination commit. |
| Status and attention, including `status-projection-cache/*.json` | Status is derived from registry, active state, run history, leases, and other inputs. Its optional cache is a replaceable host-local snapshot whose key includes local route inputs. | **Derived**; cache remains **host-local** and may be discarded. |
| Quota policy | Local policy is configured in registry fields. | Configuration input outside the head. A receipt may reference the policy revision used, but the coordination provider does not own policy. |
| Quota accounting (`quota_slot_spent` / `quota_slot_voided`) | Detailed JSON/Markdown plus `runs/index.jsonl` rows form an append-style accounting history. Current rows have no shared operation identity or cross-artifact transaction. | **Independent ledger**. A distributed implementation needs idempotent debit/void identities and its own retention contract. |
| Quota enforcement and `should-run` decisions | Computed from policy, todo/status projections, run history, scheduler context, and actor scope. A heartbeat receipt is a specialized rollout use. | **Derived decision**. If a future global budget gates claims, it should issue a separate reservation/grant receipt; the head may reference that receipt but must not absorb the quota ledger. |
| Scheduler state, liveness, host backoff, and RRULE observations | Per-goal, per-agent, per-surface JSON reflects the host that owns the scheduler. | **Host-local**. Never resolve two valid host observations by overwriting one global value. |
| Turn journals, `turn-sessions/`, and Pi `.loopx/pi/` bindings | Runtime recovery and session bindings are written for one host/session and may contain local paths or task bodies. | **Host-local**. Turn journals are a receipt-design precedent, not shared coordination state. |
| Supervisor, domain-state, and extension runtime files | Each capability defines its own schema, privacy, append/upsert rules, and effect receipts. | **Independent ledger** or **host-local**, according to that capability contract. No generic import into the head. |

Source anchors for the classifications include
[`architecture.md`](../../architecture.md),
[`event-store-migration-bridge-v0`](../../reference/protocols/event-store-migration-bridge-v0.md),
`loopx/control_plane/work_items/task_lease.py`,
`loopx/cli_rollout.py`,
`loopx/control_plane/runtime/status_projection_cache.py`,
`loopx/control_plane/quota/slot_accounting.py`,
`loopx/global_registry.py`, and the host state in
`loopx/control_plane/scheduler/state.py`,
`loopx/control_plane/turn_driver/codex_cli.py`,
and `loopx/pi_goal_mode/pi-goal-loop-runtime.mjs`.

## 4. What Goes Into This Coordination Ledger

One provider key stores one goal's v0 aggregate. The illustrative shape is:

```json
{
  "schema_version": "loopx_coordination_head_v0",
  "goal_id": "shared-rust-review",
  "authority_revision": 43,
  "coordination": {
    "todos": {
      "todo_review": {
        "todo_revision": 9,
        "status": "open",
        "claimed_by": "laptop-reviewer",
        "eligibility": {
          "authorization_projection_revision": 3,
          "authorization_projection_digest": "sha256:...",
          "allowed_agent_ids": ["laptop-reviewer"],
          "dependencies_satisfied": true,
          "dependency_revision": 12,
          "gates_open": true,
          "gate_revision": 5
        },
        "repository": "git:example/repo",
        "code_revision": "0123456789abcdef",
        "last_lease_epoch": 7
      }
    },
    "leases": {
      "todo_review": {
        "lease_id": "lease_...",
        "owner": "laptop-reviewer",
        "lease_epoch": 7,
        "expires_at": "2026-08-06T03:30:00Z",
        "write_scopes": []
      }
    }
  },
  "receipt_index": {
    "op_claim_review_01": {
      "request_digest": "sha256:...",
      "original_receipt": {
        "schema_version": "loopx_authority_receipt_v0",
        "operation_id": "op_claim_review_01",
        "request_digest": "sha256:...",
        "command": "claim_work",
        "actor": {"agent_id": "laptop-reviewer", "device_id": "laptop"},
        "todo_id": "todo_review",
        "accepted_authority_revision": 43,
        "accepted_todo_revision": 9,
        "applied_at": "2026-08-06T03:20:00Z",
        "lease_id": "lease_...",
        "lease_epoch": 7,
        "expires_at": "2026-08-06T03:30:00Z"
      }
    }
  },
  "receipt_retention": {"mode": "retain_all_v0"}
}
```

The schema contains no raw todo body, transcript, credential, absolute path,
or raw evidence. It contains only the facts needed to adjudicate the command
slice and recover its proof. As in current LoopX, a claimed todo remains `open`,
without inventing a `claimed` lifecycle status that local mode does not have.
In the target contract, `claimed_by` carries soft ownership and the lease/fence
carries execution authority. The default `legacy` handoff mode does not honor
this: when the two records diverge, the markdown claimant wins on the write
path. A goal that declares `hard_lease` turns the divergence into a typed
error and requires the key at completion. See Appendix B.

Each eligibility revision or digest is scoped to the snapshot referenced by the
target todo: authorization covers only that todo's actor scope, dependency
covers only its transitive dependency closure, and gate covers only gates that
actually constrain it. These are not goal-wide revisions under new names. The
reference slice fixes `write_scopes=[]`. When non-empty scopes are introduced,
overlap with another active lease is a real cross-todo precondition: an internal
rebase must revalidate it and reject the claim on overlap.

Those target-scoped tokens have a coverage and no-ABA obligation. Any semantic
change to the target's claim state or lease epoch must advance `todo_revision`.
Any change to its allowed actors, dependency closure or satisfaction decision,
or constraining gate set or decision must advance the corresponding revision
and digest where present. A token must never be reused for a different snapshot.
If the authority cannot prove this coverage, it must not internally rebase. The
deterministic reference validates a static bootstrap snapshot; it does not yet
qualify a dynamic publisher for these projections.

The original receipt proves that an operation was accepted at one authority
revision. It does not prove that its lease remains current. A replay response
therefore returns the field-for-field equivalent `original_receipt` plus
separately named current observations such as `observed_authority_revision` and
`authorization_status=active|expired|superseded`.

## 5. How a Command Lands and How a Lost Receipt Comes Back

The request envelope uses `operation_id` to avoid collision with existing CLI
uses of `command_id`:

```json
{
  "schema_version": "loopx_command_v0",
  "operation_id": "op_claim_review_01",
  "actor": {"agent_id": "laptop-reviewer", "device_id": "laptop"},
  "goal_id": "shared-rust-review",
  "command": {
    "type": "claim_work",
    "todo_id": "todo_review",
    "expected_todo_revision": 8,
    "expected_preconditions": {
      "authorization_projection_revision": 3,
      "authorization_projection_digest": "sha256:...",
      "dependency_revision": 12,
      "gate_revision": 5
    },
    "lease_ttl_seconds": 600
  }
}
```

The authority normalizes the complete semantic request and computes
`request_digest`. Actor, goal, command type, target todo revision, named
authorization/dependency/gate preconditions, and command parameters are
covered. Transport retry metadata is not. The goal-wide `authority_revision`
is not a client domain precondition and is not part of the request digest. A
caller may carry a previously observed head revision only as transport
metadata; changing that observation does not create a new semantic operation.

For every request, the authority performs this sequence:

1. load the aggregate and provider generation;
2. look up `operation_id` before applying current-state validation;
3. if the id exists with the same digest, return `already_applied` and the
   stored original receipt without writing;
4. if the id exists with a different digest, return typed
   `operation_identity_mismatch` and do not write;
5. validate actor scope, target todo revision, named preconditions,
   eligibility, claim state, and the empty-scope lease rules implemented by this
   reference slice;
6. compute the next coordination state and original receipt in the authority;
7. add both the transition and receipt-index entry to one deterministic
   envelope and submit one provider CAS;
8. after a conflict or ambiguous provider response, reload and repeat the
   receipt lookup before classifying the result;
9. if no receipt exists and the generation did not advance, fail closed with
   `provider_outcome_unproved`. If the generation advanced, revalidate the
   target todo and named preconditions; when those facts are unchanged, retry
   against the latest head. Receipt absence never proves success: an eventual
   `applied` requires a new successful CAS; and
10. after a CAS miss, stop rebasing when relevant facts no longer permit the
    command. Initial invalid requests still follow ordinary domain validation.
    An unrelated head advance is not a domain conflict. Exhausting the bounded
    contention retry budget returns typed `failed` and creates no receipt.

The API result classes are:

| Result | Meaning |
| --- | --- |
| `applied` | State and original receipt committed together. |
| `already_applied` | The same operation and digest committed earlier; the stored original receipt is returned. |
| `conflict` | No receipt exists for this operation and the target todo or a named precondition is stale. |
| `rejected` | Identity, eligibility, gate, or command validation failed without a state change. |
| `failed` | No accepted result can be proved, or unrelated provider contention exhausted the internal retry budget. Retry only under bounded infrastructure policy. |

`conflict`, `rejected`, and `failed` are not success proofs and do not receive
fabricated applied receipts.

### 5.1 The first command: `claim_work`

- `claim_work`: in one transition, verify an existing runnable todo, set its
  claimant, create a lease, mint the next lease epoch, and store the original
  receipt. Its required fields are `todo_id`, `expected_todo_revision`,
  `expected_preconditions`, and `lease_ttl_seconds`.

An accepted claim advances both `authority_revision` and the target
`todo_revision`. It operates only on a todo installed by explicit
bootstrap/migration and never creates an unknown todo as a side effect. The
deterministic reference eligibility input is the compact tuple
`allowed_agent_ids`, `dependencies_satisfied`, and `gates_open`, bound to the
named authorization, dependency, and gate revisions and digest.

`authority_revision` is the goal-wide commit sequence for accepted commands.
It serves audit, read-model, and receipt ordering; it is not a shared optimistic
concurrency precondition for every command. The aggregate still commits
serially through `provider_generation`. A CAS loser decides whether to rebase
from its target todo and named preconditions, rather than requiring a caller to
mint a new operation merely because an independent todo committed first.

Unknown command types fail closed. `renew_lease`, `release_lease`, expired-lease
reclaim, stale-fence writeback validation, `complete_todo_with_successor`,
transfer or delegated assignment, arbitrary todo/gate mutation, quota
reservation, and external effects require later runtime contracts and
qualification. Renew/release/reclaim and stale-fence validation are required
before production shared-mode operation; their omission here is scope control,
not a claim that a claim-only runtime is complete. Non-empty write scopes and
cross-todo scope-overlap rejection likewise require a later command contract and
qualification. Completion plus successor
creation may join a later slice only when source completion, successor
creation/assignment, evidence pointer, and receipt commit atomically.

## 6. Who Decides and Who Stores

### 6.1 The authority is the bookkeeper

The LoopX authority owns:

- request normalization and digesting;
- actor, todo, dependency, gate, and authorization validation;
- domain-conflict decisions over the target todo and named preconditions, plus
  bounded CAS rebase after unrelated head advances;
- the `authority_revision` commit sequence and todo revision transitions;
- time, lease id, lease epoch, and expiry minting;
- receipt contents and replay classification;
- privacy filtering and command-specific invariants.

### 6.2 The provider keeps the ledger durable

The provider contract is intentionally semantic-free:

```text
load()
  -> (aggregate | none, provider_generation)

compare_and_put(
  expected_provider_generation,
  aggregate
)
  -> applied(new_provider_generation)
   | conflict(current_provider_generation)
   | ambiguous
   | failed
```

The provider must serialize the complete aggregate deterministically and
provide atomic conditional replacement, durable success,
same-key read-after-write reconciliation, and a typed ambiguous result when it
cannot prove whether a write committed. It must not parse LoopX commands, mint
clocks or leases, decide eligibility, or synthesize authority receipts. The
domain `operation_id` and request-digest replay contract exist only in the
authority and its atomically stored receipt index; they are not provider API
arguments. A provider may generate a private publication-attempt identifier,
but that identifier has no LoopX authority meaning.

A provider instance or handle is bound to one `goal_id` and provider key before
these methods are called; omitting `goal_id` from the verbs does not make the
key global.

The receipt index cannot be a separately published document under this
two-verb contract. Publishing receipt first can record success for a transition
that never happened; publishing state first can lose the only proof after a
crash. Splitting it later requires a provider-neutral multi-record transaction
or commit-marker protocol and a new reviewed contract.

### 6.3 The three version numbers are not the same thing

| Domain | Owner | Meaning | Consumer |
| --- | --- | --- | --- |
| `provider_generation` | Provider | Opaque token for conditional replacement of stored bytes | Authority/provider seam only |
| `authority_revision` | LoopX authority | Per-goal logical commit sequence after an accepted command | Audit, receipts, and read models; not a shared precondition for every domain command |
| `lease_epoch` | LoopX authority | Per-todo fencing generation for ownership; advances on a new lease generation, not ordinary renewal | Executors and accepted writeback |

A backend may often advance its generation once per accepted command, but
numerical equality is never a contract. Migration, repair, or provider metadata
may change provider generation without granting a new LoopX authority revision.

For NoKV, its document generation implements `provider_generation` only. The
LoopX authority remains responsible for the other two domains and for the
receipt stored inside the document.

## 7. Keep Every Receipt First; Compact Later

v0 uses `retain_all_v0`: no committed receipt-index entry may be garbage
collected, expired, or omitted from a snapshot. This is intentionally a
correctness-first proof boundary, not a production-scale retention claim.

If a receipt-index entry is present but its original receipt is missing or
invalid, the authority fails closed as a provider-protocol violation. It has no
fallback to provider publication history and must not reconstruct a receipt
from the current head.

A bounded retention window, receipt segmentation, or external receipt ledger
requires a later RFC that preserves atomic proof and defines behavior outside
the window. Until then, compaction may rewrite bytes but must carry the complete
receipt index forward.

## 8. Local Mode Stays the Default; Shared Mode Is an Explicit Migration

### Default local mode

- Existing project registry, Markdown active state, run history, optional task
  leases, status, quota, and host behavior remain unchanged.
- Installing a provider does not enable shared authority.
- The current event-store bridge still reports Markdown as source of truth and
  does not allow automatic promotion.

### Shared-authority mode

Shared mode is an explicit per-goal choice. A reviewed implementation must:

1. pin the source registry, active state, and privacy boundary;
2. stop or fence local writers during migration;
3. normalize only the scoped coordination fields into an initial aggregate;
4. validate todo/claim/lease/gate parity and an empty receipt index;
5. record the shared-mode declaration and authority endpoint/provider binding;
6. route every P0 write through the online authority;
7. render Markdown, local lease views, rollout rows, and status only as
   projections for the migrated fields.

Bootstrap is a fenced administrative migration before controlled shared writes,
not a P0 agent command: it may create the initial aggregate with the selected
existing todos and an empty receipt index. Its source digest and mode
declaration must be durable so a restart can distinguish bootstrap from an
uninitialized provider.

Before the first shared write, migration may roll back to the untouched local
source. After a shared write, automatic fallback to local writers is forbidden:
it would create two authorities. Recovery must restore the authority or perform
a separately reviewed, fenced export and mode transition.

Provider shadowing and read-only canaries may collect evidence, but neither
changes the source of truth. Promotion is explicit and must follow the existing
fail-closed migration discipline.

## 9. What Happens Offline and What Must Stay Local

When a shared-mode authority is unavailable:

- cached projections may be read only when marked stale;
- no new controlled write is accepted;
- already authorized local computation may continue only under the existing
  lease and effect boundaries;
- there is no automatic local-file write fallback.

This RFC sets no wake latency or heartbeat topology. Delivery may use pull,
push, or an IM daemon under the Agent IM RFC, but a delivered message is never
proof that a coordination command committed.

The shared aggregate and receipts may contain compact public-safe or explicitly
scoped private metadata: stable ids, credential-free repository identity,
exact code revision, digests, gate/dependency refs, claim and lease fields, and
privacy-classified opaque pointers. They must not contain credentials, raw
evidence, raw todo prose, transcripts, raw logs, or local absolute paths.

## 10. How We Accept the First Stage

All checks are machine-verifiable:

1. two actors claiming the same todo from one provider generation yield exactly
   one `applied`; the loser receives a target-specific `conflict` and no lease;
   the winner's todo remains `open`, with ownership expressed by `claimed_by`
   and its lease;
2. two actors claiming two independent todos in the same goal from one provider
   generation, with `write_scopes=[]` and unchanged target-scoped authorization,
   dependency, and gate facts, both receive `applied`; the first CAS loser
   reloads, revalidates its relevant preconditions, and rebases internally,
   while the goal audit sequence, both todo revisions, and both receipts each
   advance only once;
3. immediate replay with the same operation id and digest returns the original
   receipt without changing state;
4. historical A/B/A replay survives reconstruction of the authority handle
   while the same deterministic provider fake retains its aggregate, and
   returns A's original receipt field for field after B advances the head;
5. the same operation id with a different normalized digest is rejected and
   changes neither state nor receipt index;
6. fault injection around the provider CAS never exposes state without its
   receipt or a receipt without its state;
7. ambiguous provider responses reconcile by reloading the receipt index: a
   stored receipt recovers success, same-generation absence fails unproved, and
   absence after a generation advance can only succeed through a new successful
   CAS after revalidation;
8. claim rejects an unknown, stale target/precondition, ineligible,
   dependency-blocked, or gate-blocked todo without creating state or a receipt;
9. sustained unrelated provider contention that exhausts the internal retry
   budget returns typed `failed`, creates no receipt for the operation, and is
   not mislabeled as a domain conflict;
10. retained receipts survive reload fixtures with no receipt GC;
11. provider generation, authority revision, and lease epoch are tested as
   distinct domains;
12. privacy scans find no credential, raw body, transcript, or absolute path;
13. default local mode remains behaviorally unchanged, and shared mode never
    falls back to an unfenced local writer.

The companion provider probes are evidence for a candidate implementation, not
permission to weaken these normative checks. Performance measurements and a
particular deployment topology are deliberately non-normative.

## 11. Staged Delivery

### Implementation prerequisite: put local file mode behind the same coordination contract

Before wiring a live NoKV or another remote provider, the runtime should first
extract the domain decisions in the current todo/lease write paths into a
provider-neutral coordination core and qualify a file-backed provider against
the same commands, preconditions, receipts, and typed outcomes. That refactor
must begin as a shadow of the current Markdown active state and task-lease
files, proving read/write parity, idempotency, CAS conflicts, crash recovery,
and one-command rollback. Only a separately reviewed promotion may make the
file aggregate locally canonical and turn Markdown/lease files into
projections. NoKV then reuses the same authority and contract while replacing
only the `load` / `compare_and_put` provider. This prerequisite does not create
a generic storage abstraction over registry, run history, quota, scheduler, or
evidence; those ledgers retain the owners defined in Section 3.

#### Stage 1 Part 2 boundary

This slice is a behavior-preserving extraction of a pure decision core for the
todo lifecycle, task-lease lifecycle, and `handoff_mode` rules that the current
writers already enforce. Markdown goal state and task-lease files remain
canonical. The extraction does not synthesize todo, authorization, dependency,
or gate revisions for domains that have no current revision publisher. It also
does not replace today's separate claim and lease verbs with the atomic
`claim_work` command described above; that command belongs to the future shared
aggregate.

Keep three layers distinct as the provider work proceeds:

1. `DomainDecision` is the pure apply/reject/no-change judgment over an explicit
   coordination snapshot and command.
2. Authority execution and its result own locking, revalidation, committing the
   decision, and eventually the durable semantic receipt.
3. The provider result reports storage observations such as
   `loaded | missing | conflict | unavailable | failed` and an opaque provider
   generation; it is not a domain decision or a semantic receipt.

Stage 1 Part 2 does not claim durable semantic receipts or A/B/A replay. Those
require the Stage 2 aggregate and provider shadow. That aggregate must treat
`handoff_mode` as a real, revision-covered decision input. Its provider
contract must never collapse `missing` into `unavailable` or `failed`.
`provider_generation`, `authority_revision`, and `lease_epoch` remain three
independent version domains. Likewise, a restore may preserve frozen bytes and
lineage without granting current authority: promoting restored state to the
live authority head requires an explicit lineage and binding fence.

The file-backed provider shadow is Stage 2. It has not started in this slice.

Durable completion continuation read-back
(`durable_completion.py`: `read_persisted_todo_record` /
`project_durable_completion_outcome`) is a provider read point: it re-reads
the persisted lifecycle record (Markdown first, event projection fallback)
after the completion write and before settlement. The persisted record
carries an explicit `completion_continuation`; the seam fails closed when a
done record omits it or when it contradicts the recorded successor or
no-follow-up fields, so a provider that holds completion state must store
that field byte for byte. Once a remote provider becomes canonical, this seam
flips to provider-first without changing the typed outcome contract below.

### P0: contract and deterministic proof

- this ownership matrix and explicit shared-mode boundary;
- deterministic `loopx_command_v0` normalization and request digest;
- the `claim_work` authority transition over explicitly bootstrapped todos;
- one-head state-plus-receipt CAS;
- target/precondition-scoped conflicts and internal CAS rebase after unrelated
  head advances;
- deterministic and NoKV provider candidates behind the same seam;
- A/B/A, identity-mismatch, crash-window, eligibility, privacy, and no-GC
  checks within the stated evidence boundary.

### Later runtime qualification and reviewed slices

- lease renewal, explicit release, expired-lease reclaim, and stale-fence
  writeback rejection, all required before production shared mode;
- durable completion continuation projection
  (`successor | no_followup | active_goal`) with fail-closed contradiction
  rules (`no_followup` + successors, dangling declared successor), reproduced
  by the provider with identical semantics;
- atomic `complete_todo_with_successor` and accepted evidence pointers;
- transfer and restricted delegated assignment;
- delivery/wake integration through Agent IM;
- independent run-history synchronization and artifact storage;
- distributed quota reservation/accounting;
- provider promotion, authentication, service recovery, HA, and multi-tenancy;
- receipt retention or segmentation beyond `retain_all_v0`.

## 12. What the Owner Still Needs to Decide

1. Should the next runtime slice first close renew/release/reclaim and stale
   fencing, or qualify that lifecycle together with atomic
   complete-with-successor?
2. Which compact project-registry authorization fields form the versioned
   authority input, and who may publish a new authorization projection?
3. What is the reviewed rollback/export procedure after the first shared-mode
   write?
4. Which provider and deployment qualify for the first bounded shared-mode
   canary? Provider selection does not change the authority contract.
5. Before production use, what retention and capacity policy replaces or
   operationalizes `retain_all_v0` without losing historical proof?

---

## Appendix A: What This Evidence Proves

The reference provider and probes live in
`examples/nokv-shadow-provider/`,
with a companion
[`evidence document`](./shared-goal-authority-state-provider-v0-evidence.zh-CN.md).
The deterministic candidate in this PR proves only the claim/receipt core:
same-CAS state plus receipt, competing claims, A/B/A original-receipt replay,
request-digest mismatch, crash-boundary recovery, and distinct version-domain
examples. It does not implement or qualify lease renewal/release/reclaim,
stale-fence writeback, a production authorization-projection publisher,
receipt-preserving compaction, default-mode parity, shared-mode migration, or
live NoKV restart/recovery. Passing
`python3 examples/nokv-shadow-provider/probes.py contract` is therefore not a
claim that the complete P0 acceptance gate above passes. Historical latency or
fault results are informative only; they are not a durability, recovery, HA,
or production qualification claim.

## Appendix B: Handoff-Mode Decision Record (2026-08-10)

This appendix writes down a direction already agreed during the PR #2787
review, as part of the implementation prerequisite. It changes documentation
only; no runtime behavior changes.

### Why

Live CLI verification reproduced a fact: the two claim records can disagree.
One agent acquires a hard lease on a todo; another agent can still soft-claim
the same todo afterwards, and both succeed. What happens after the divergence
matters more:

- The later soft claim invalidates the earlier active lease outright: the
  holder's renew and re-acquire are rejected;
- The completion fence disarms itself in exactly this conflicted state: the
  soft claimant completes without any key;
- The lease holder cannot complete at all: authorization checks the soft
  claim first, so the lease credentials are never even evaluated.

In short, once the two records diverge today, the soft claimant wins
everywhere; the lease does not carry execution authority on its own. The
sentence in section 4 ("the lease/fence carries execution authority")
describes the target contract; the body text has been corrected in this
revision.

### Decision

Do not synchronize the two records against each other. Instead, each goal
declares a handoff mode (`handoff_mode`) that separates the two ways of
taking work. The field lives in the goal state file's front matter for now,
traveling with the file across endpoints; once shared mode ships, the shared
authority owns it. Three values:

- absent or `legacy`: exactly today's behavior, both paths open. The
  divergence hole remains in this mode; that is a deliberate default, not an
  oversight.
- `soft_claim`: this goal uses soft claims only. acquire/renew/transfer are
  rejected; release and inspect remain available to clean up and view
  leftover leases.
- `hard_lease`: changing the claim on an existing todo requires holding its
  active lease; every transition that retires an existing todo as done
  (`complete` and `supersede`) requires the key; the self-disarm-on-conflict
  behavior becomes a loud error. Assigning a claimant at todo creation stays
  allowed: a fresh todo cannot have a lease yet. One harness-owned case keeps
  the keyed invariant without making the presenter hold the lease across a
  human wait: completing a user-role `user_gate` todo without explicit lease
  credentials lets the completion fence mint the key itself under the same
  per-goal lease lock, verify it, and release it on commit; an existing
  time-active lease is never displaced.

Companion rules:

1. Default is `legacy`; existing goals see zero behavior change. The hole
   stays open there, and the implementation PR must say so plainly.
2. Field placement as above; the registry and lease files are per-host, only
   the goal state file travels across endpoints.
3. Cross-endpoint window: the mode propagates by file sync, so two endpoints
   can briefly see different values. Today this can only converge, not be
   eliminated; state it honestly. Shared mode closes it.
4. `hard_lease` keeps one door: the existing delegated authority
   (todo_lifecycle_authority, with a stated reason) may change claims
   without holding the lease, with an explicit, auditable override marker in
   the result. No new bypass switches.
5. Switching modes requires quiescence: refuse while the goal still has open
   claims or active leases, and list what blocks it. No forced switch in v0.

### Status (2026-08-18)

The gate shipped as the `handoff_mode` front-matter field with the
`legacy | soft_claim | hard_lease` semantics above, the quiescence-only
`loopx handoff-mode show|set` switch, and the delegated-authority door with
its `handoff_gate_overridden` marker; the user-gate key minting above landed
as a follow-up. `legacy` remains the default and keeps the divergence hole by
design. Two side doors found after the gate landed are closed alongside this
revision: `supersede` crosses the same lease fence as `complete`, and a forced
state rebuild (`bootstrap --force`) carries the declared mode instead of
resetting it to `legacy`. The next stage, a file-backed provider shadow behind
the coordination contract of Section 11, has not started.

### Relation to Staged Delivery

Mapped to the five-stage plan from the #2787 review: the characterization
stage first records today's actual behavior (including the three divergence
facts above) as fixtures; the gate itself is an explicitly declared behavior
change, landing as its own PR before the file provider shadow so divergent
data does not pollute the shadow parity baseline; once local canonical
promotion folds claim and lease into one ledger, this class of divergence
becomes structurally impossible and the gate is absorbed. The read-surface
and hygiene fixes (status showing real leases; releasing the verified lease
on completion) touch no decision semantics and were submitted ahead of this
record.

The characterization stage's negative cases extend the original list: a soft
claim overriding an active lease; the completion fence disarming in the
conflicted state; authorization running before the lease fence; claim-change
entry points not yet gated; the window between the lease acquire's projection
read and the state-file lock.
