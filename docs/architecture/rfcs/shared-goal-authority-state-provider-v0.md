# RFC: LoopX Shared Control-Plane Authority and Pluggable State Providers (v0)

- Status: Draft, under maintainer review
- Initially proposed by: NoKV Lab
- Widened by: LoopX maintainers
- Date: 2026-08-05; revised 2026-09-05
- Scope: one provider-neutral LoopX authority contract with built-in file,
  optional NoKV, and optional PostgreSQL provider profiles, complementing
  [`host-integration-surface-v0`](../../reference/protocols/host-integration-surface-v0.md)
- Source baseline: LoopX `a0c20f1779d273e7aaa4bd3ea166d145d466e6d5`
- Provider API baseline: NoKV `7bb3ffd6512fd57d9c0f193aa6d9c5b935d77f30`
  (release 0.11.0, Python API 1, Holt pinned to 0.8.6). The Stage 2A executable
  qualification admits only that SDK contract and this checkout's helper. It
  remains candidate evidence, not a merge gate or authority promotion
- PostgreSQL baseline: the TypeScript Stage 2B candidate implements the store
  contract, transaction-local tenant context, forced row-level security, and
  bounded canonical commit admission, and has passed a real PostgreSQL 16
  transaction matrix. No shared authority service, runtime caller, principal
  authentication/tenant authorization, measured capacity/retention profile, or
  authority promotion ships yet
- Language note: the
  [Chinese version](./shared-goal-authority-state-provider-v0.zh-CN.md) and this
  English version are semantic mirrors. A difference between them is a defect.

## Current implementation checkpoint

The machine-owned coordination projection now has one packaged,
provider-neutral record contract shared by Python and TypeScript. File, NoKV,
and PostgreSQL candidates consume the same canonical Todo read shape; a
provider-bound projection rejects an unknown field rather than silently losing
it. Removing a declared field requires explicit compatibility evidence and
maintainer approval, even when the field is stored but not yet read by a
decision path.

The native domain alternative now separates Markdown location metadata while
retaining archival semantics. Appendix C's Todo domain/projection decision
records the compatibility boundary and the next local qualification plan;
the existing v0 capture and persisted heads are not silently migrated.

This does not promote a provider or make the whole active-state Markdown file
generated. Markdown remains canonical in default local mode. In a later,
explicit shared-authority promotion, only sections covered by the typed
contract become deterministic compatibility projections; free-form human
narrative remains outside the coordination head.

## Document map and maintenance contract

This RFC separates durable decisions from delivery evidence:

- Sections 0-10 define the problem, authority contract, provider boundary,
  migration rules, and acceptance criteria.
- Section 11.1 is the normative delivery plan. Section 11.2 is a
  non-normative execution ledger: it records what a dated `main` revision has
  proved, but does not silently amend the contract. Section 11.3 lists the
  remaining qualification and promotion work.
- Section 12 contains unresolved owner decisions. An implementation may not
  infer approval from a proposed answer.
- Appendices A and B retain evidence and decision history; Appendix C contains
  the detailed Stage 2C contract proposed by Section 12. When implementation
  changes, update the ledger; when architecture changes, update the normative
  section and record the decision explicitly.

RFC maturity and delivery maturity are independent. A shipped experiment does
not accept this RFC, and a dated status entry never overrides a normative
invariant. If the execution ledger becomes difficult to review, it moves to a
companion `*-execution.md` document without dropping its evidence links.

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
file into a remote store, and we are not creating three competing semantic
authorities:

1. one goal that explicitly opts into shared mode has one **canonical
   coordination aggregate**;
2. each successful operation's state transition and original receipt land in
   the **same compare-and-set (CAS)**;
3. the LoopX authority makes decisions, while file, NoKV, or PostgreSQL
   providers only persist reviewed transactions reliably;
4. run history, status, quota, scheduler state, host sessions, and evidence
   bodies stay with their existing owners instead of entering this ledger.

NoKV and PostgreSQL are optional providers behind the bookkeeper. Agents do not
connect directly to either provider for controlled writes, and neither provider
becomes the LoopX control-plane authority. The file provider is the first
deterministic/parity backend; the current local file-based control plane remains
the default authority path until a separately reviewed authority-source
promotion.

```text
Agent client
    |
    v
LoopX authority API / embedded authority
    |
    v
typed LoopX transactions
    |
    v
provider-neutral store contract
    |------------|-------------|
    v            v             v
   file         NoKV       PostgreSQL
```

The invariant is one semantic writer regardless of deployment. A shared
service may host the LoopX authority together with authentication, tenancy,
audit, and a PostgreSQL or NoKV provider. Those are deployment concerns: an
Agent still calls LoopX APIs and cannot bypass the authority by writing tables,
documents, or files directly.

The first runnable slice began with one command, `claim_work`. For an existing
eligible todo, it records the soft claim, lease/fence, and receipt together.
Stage 3 extends that reference contract with renew, release, reclaim, and
completion while keeping the modules coverage-only. The initial slice answers
the two questions most likely to cause an incident—who wins when two endpoints
claim at once, and how a lost response recovers its original receipt.

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

The built-in file backend is the first parity implementation; NoKV is the
initial shared-store candidate; PostgreSQL is the planned service-provider
profile. Each must pass the staged qualification below. The LoopX increment is
the semantic authority that turns an opaque provider transaction into a trusted
`claim_work` result and, later, into recoverable execution ownership.
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

Physical co-location is allowed. One deployment bundle may start a NoKV or
PostgreSQL provider, a LoopX authority endpoint, and a Supervisor worker. Here,
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

### 1.3 Prospective license path by distribution boundary

This subsection is non-normative and does not change the license of any current
LoopX source or release. It records the boundary that a future license RFC
should evaluate if the service-grade horizon becomes a separately shipped
product.

| Distribution boundary | Delivery horizon | Recommended path |
| --- | --- | --- |
| RFCs, schemas, typed commands, receipts, provider-neutral decisions, store contracts/codecs, client SDKs, conformance fixtures, and examples | Stages 1-4 | Remain in the Apache-2.0 open core so runtimes and providers can implement one coordination contract without adopting a server distribution |
| Embedded/local authority, file parity backend, and shared-store adapters for NoKV or PostgreSQL | Stages 1-4 | Remain Apache-2.0; an adapter does not acquire LoopX semantic authority, and the underlying provider keeps its own license |
| Test-only shadowing, canary, migration fixtures, and authority-source promotion proof | Stages 3-4 | Remain Apache-2.0 qualification material; evidence that a deployment is correct is not by itself a separately licensed product |
| Independently versioned shared-authority server that owns authentication, tenant isolation, audit, durable receipt service, migration/promotion, capacity controls, recovery, and HA | Stage 5 | May be evaluated for AGPL-3.0 in a separate license RFC once this is more than a thin wrapper around the Apache core |
| Persistent Supervisor/reconciliation worker shipped as part of that server distribution | Stage 5 | May follow the server's AGPL-3.0 candidate terms when it owns restart-safe observation, reclaim, remote-resume orchestration, and wake requests through authority commands |
| Separately delivered managed operations or enterprise-only modules | After a service boundary exists | May use separate commercial terms when they are not included in the Apache or AGPL distribution and their dependency boundary is explicit |

An illustrative package boundary, if these distributions are later created,
is:

```text
loopx/control_plane/coordination/             Apache-2.0
packages/loopx-authority-client/              Apache-2.0
packages/loopx-authority-provider-*/          Apache-2.0
packages/loopx-shared-authority-server/       AGPL-3.0 candidate
packages/loopx-persistent-supervisor/         AGPL-3.0 candidate, or part of the server
```

The names are illustrative rather than a Stage 0 layout requirement. The
dependency direction is the durable rule: an AGPL server distribution may
consume Apache contracts, core logic, and providers; Apache artifacts must not
import, bundle, or require the AGPL server. The NoKV or PostgreSQL server is
not relicensed by a LoopX adapter, and an adapter must not be used as an
artificial license boundary.

Any Stage 5 license proposal must satisfy all of these gates before changing
the current policy:

1. identify one independently deployable and versioned server artifact;
2. show that the artifact owns a real network trust and reconciliation
   boundary rather than only forwarding Apache-core calls;
3. preserve Apache client, protocol, embedded-mode, provider, and conformance
   paths for interoperable adoption;
4. define package metadata, nested license/NOTICE files, SPDX markings, and
   build checks that prevent cross-license bundling;
5. decide the inbound contribution policy before accepting contributions to
   any AGPL component, especially if commercial dual licensing may be needed;
6. apply any change prospectively through an explicit version boundary without
   narrowing rights already granted by MIT or Apache releases.

The current RFC therefore keeps Stages 1-4 under the repository's Apache-2.0
policy. Stage 5 creates a decision point, not an automatic license transition.
No source path becomes AGPL-3.0 merely because it implements a shared-authority
contract or passes a remote-provider canary.

## 2. What We Will Do, and What We Will Not

**What this version will do**

- give one shared goal an online, provider-neutral coordination authority;
- make concurrent claims on the same todo resolve to one accepted owner while
  allowing independent todos to succeed after an internal CAS rebase;
- bind each operation identity to one normalized request digest and reject the
  same id when it is reused with different semantics;
- recover the original receipt after later operations advance the ledger;
- define one semantic authority boundary and the file, NoKV, and PostgreSQL
  provider profiles behind it;
- keep LoopX's default local mode unchanged;
- say how every existing durable state category joins—or stays outside—this
  boundary.

**What this version explicitly will not do**

- build a generic distributed filesystem or database for all LoopX state;
- support offline multi-writer merge or offline controlled writes;
- mix message delivery, wake-up, presence, or an Agent IM protocol into the
  storage contract;
- ship production multi-tenant deployment, authentication, HA, or provider
  failover in the Stage 0 reference slice;
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

One provider key stores one goal's aggregate (head schema v1). The illustrative shape is:

```json
{
  "schema_version": "loopx_coordination_head_v1",
  "goal_id": "shared-rust-review",
  "store_binding": "nokv:wb-goals:1f2e3d4c...",
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

Unknown command types fail closed. Transfer or delegated assignment,
arbitrary todo/gate mutation, quota reservation, and external effects still
require later runtime contracts and qualification. Non-empty write scopes and
cross-todo scope-overlap rejection likewise require a later command contract
and qualification. The recoverable-execution verbs below were called Stage 3
in the historical #3669 implementation sequence. Under the current delivery
sequence in Section 11, that merged work is part of the Stage 0 reference foundation,
not the Stage 3 remote-shadow phase in Section 11. Steps 1 through
4 and 7 through 10 of Section 5 (identity, digest, replay, CAS, reload, rebase,
budget) apply to every verb unchanged, and only the per-verb preconditions and
transition (steps 5 and 6) differ.

### 5.2 `renew_work`

Required fields: `todo_id`, `expected_todo_revision`, `lease_id`,
`expected_lease_epoch`, `lease_ttl_seconds`. The caller presents the fence it
believes it holds; the authority rejects a missing lease, a fence whose
lease id or epoch differs (typed `stale_lease_fence`), a caller that is not
the recorded holder (typed `not_lease_holder`), and a lease the authority's
own clock has already seen expire (typed `lease_not_active`; see Section
6.4). An accepted renewal extends `expires_at` from the authority clock,
keeps the lease id and epoch unchanged, and advances both
`authority_revision` and the target `todo_revision`: the validity interval
is a revision-covered fact, so a reclaim built on pre-renewal observations
conflicts instead of surviving the internal rebase.

### 5.3 `release_work`

Required fields: `todo_id`, `expected_todo_revision`, `lease_id`,
`expected_lease_epoch`. Release is the holder giving up early, so it is
valid only while the lease is still active: the claim is cleared under the
live holder gate and the lease is released in the same transition. The
accepted transition clears `claimed_by`, deletes the lease entry, and
advances both revisions, while the todo's `last_lease_epoch` watermark is
retained unchanged - in the shared aggregate the watermark IS the terminal
record, so the next claim mints strictly above it and release can never
A/B/A. An expired lease is not releasable; its resolution belongs to
reclaim.

### 5.4 `reclaim_work`

Required fields: `todo_id`, `expected_todo_revision`,
`expected_preconditions`, `lease_ttl_seconds`. Reclaim is a standing
delegation to eligible agents: when the authority's own clock has seen the
recorded lease expired for at least the reclaim grace window (Section 6.4),
any agent in the target's `allowed_agent_ids` may take the work over. The
authority adjudicates expiry and synthesizes the delegation; the core then
enforces everything else through the minimal privileged step - clear the
stale claim under the delegation, then run the ordinary claim composition,
so the new lease passes the same holder gate as any first claim. The
accepted transition mints the next lease epoch, sets the reclaiming agent
as claimant, advances both revisions and the watermark, and the receipt
records the superseded owner and epoch. A lease inside its validity or
grace window is typed `lease_not_reclaimable`; an unclaimed todo is typed
`todo_not_claimed` (use `claim_work`).

### 5.5 `complete_work`

Required fields: `todo_id`, `expected_todo_revision`, `lease_id`,
`expected_lease_epoch`, `no_followup`, `successor_todo_ids`, `evidence`.
Completion requires the active lease fence: the core's terminal gate
verifies the caller is the claimant and the holder of the presented fence,
and an expired or superseded fence is typed exactly like every other
stale write. One accepted transition records everything at once: the todo
becomes durably `done` with an explicit `completion_continuation` derived
from the recorded fields (`no_followup` | `successor` | `active_goal`,
with both-set combinations refused exactly like the local write), the
lease retires, declared successors are created as open, unclaimed,
revision-zero todos inheriting the parent's execution context, and the
optional evidence pointer lands on the completed record. Evidence is a
portability boundary, not free text: the `pointer` must use the
provider-neutral `artifact://<public|private>/<opaque-artifact-id>` URI
shape (never a host filesystem path, provider URL, query, or credential),
the URI privacy namespace must equal the sibling `privacy_class`, the
`digest` must be a sha256 content digest, and `privacy_class` is the closed
vocabulary `public | private` - per Section 1.1, never a body. The command
boundary and head validation enforce this through one shared oracle. The
persisted record satisfies the local durable-completion
projection seam field for field, so both worlds read one truth.

### 5.6 The stale-fence rule

Every fence-carrying verb presents `(lease_id, expected_lease_epoch)`. A
presented fence that does not match the recorded lease is a terminal typed
rejection - `stale_lease_fence` - and is never retried past by the internal
rebase: a superseded executor's writes stay rejected no matter how many
unrelated commands advance the aggregate. This, plus epoch minting on every
takeover, is the mechanism behind the Stage 3 horizon proof that a
superseded executor cannot write back.

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

#### 6.2.1 Three provider profiles, one authority

| Provider profile | Role in this RFC | Promotion requirement |
| --- | --- | --- |
| file | Built-in deterministic and parity backend. Current Markdown, registry JSON, event JSONL, run files, and task-lease files remain canonical until their owning contracts are explicitly promoted. | Prove parity and crash recovery behind the same typed transaction boundary before any file aggregate becomes canonical. |
| NoKV | Optional shared-store provider for online coordination. It contributes generation CAS and store-lineage primitives, not LoopX semantics. | Close recovery/availability blockers, qualify capacity and HA, then pass shadow parity and the bounded canary. |
| PostgreSQL | Optional provider behind an authenticated LoopX authority service for multi-Agent or private deployments. PostgreSQL tables and roles are service implementation details. | Implement the same conformance contract, transaction isolation, fencing, idempotency, cursor, audit, and fail-closed network behavior; no direct Agent database access. |

Physical database or cluster co-location does not merge ownership. A deployment
should isolate LoopX control-plane records from application-domain records with
separate schemas and roles, and relate them only through opaque identities or
digests. Provider-specific payloads do not enter the provider-neutral LoopX
schema.

#### 6.2.2 Target store contract after the reference CAS slice

The current Stage 2/3 reference implementation deliberately uses the smaller
`load` / `compare_and_put` document seam above. It proves the lifecycle and
receipt invariants needed before widening the persistence boundary; it does not
claim to implement the future service-grade transaction API.

The next LoopX-owned TypeScript boundary should express at least these logical
operations (exact names and wire shapes remain implementation decisions):

```text
load_authority(goal_id)
  -> head + provider_revision + cursor

commit_authority(
  expected_provider_revision,
  operation_id,
  events,
  next_projection,
  receipts
)
  -> applied | conflict | ambiguous | failed

read_receipt(operation_id)
scan_committed(after_cursor, limit)
```

This contract owns atomic event/projection/receipt persistence, opaque provider
revisions, cursors, and durable readback. LoopX still owns operation identity,
request normalization, legal transitions, claim/lease fencing, Turn admission,
quota semantics, settlement idempotency, and receipt meaning. In particular,
an adapter must not reinterpret a provider transaction result as a domain
decision.

The Stage 1 TypeScript contract makes read failure classes explicit. A proven
`missing` head is different from `unavailable` storage, while corrupt bytes or
an invalid lineage are `failed`; only proven absence may authorize bootstrap.
Commit has the closed storage outcomes `applied | conflict | ambiguous |
failed`. `ambiguous` means a publish was attempted but durability cannot be
proved from the response, so the authority must reconcile through
`read_receipt` and a fresh head read. A provider exception or human-readable
error string is never itself commit proof.

The three adapters implement those logical verbs through different native
primitives; the contract does not pretend they are interchangeable databases:

| Concern | File Stage 1 | NoKV Stage 2A | PostgreSQL Stage 2B |
| --- | --- | --- | --- |
| conditional revision | revision chain compared under the cross-process document lock | path `generation` passed to compare-and-publish | per-tenant/per-goal head-row revision, checked under a row lock or conditional update |
| atomic event/projection/receipt commit | one complete journal document, file fsync, atomic rename, directory fsync | one generation-CAS envelope; receipt and scan data remain embedded until a qualified multi-record protocol exists | one SQL transaction updating the head and inserting ordered event/receipt rows |
| operation uniqueness | retained journal rejects duplicate `operation_id` | authority receipt index in the CAS envelope | unique `(tenant_id, goal_id, operation_id)` constraint, used as storage fencing rather than a domain decision |
| cursor | document-local monotonically increasing opaque string | embedded journal cursor, still subject to capacity qualification | per-goal sequence allocated in the same transaction; never a global ordering claim |
| lineage | durable directory `store-identity` | workbench plus never-reused `workspace_incarnation_id` | service-managed database incarnation bound to the provider deployment |
| trust boundary | trusted embedded LoopX process | LoopX-authority-owned NoKV credentials | authenticated tenant-scoped LoopX service role; Agents never receive table credentials |

For PostgreSQL, `commit_authority` is one transaction, not a series of
independent repository calls: lock or conditionally update the scoped head,
verify the expected provider revision, allocate the next scoped cursor, insert
the committed transaction/events/receipts, update the projection head, and
commit. A connection failure before any write is a proved `failed` result; a
connection loss after commit may have started is `ambiguous` and is reconciled
by the unique operation row and receipt read. `READ COMMITTED` plus an explicit
per-head row lock/conditional update can implement this contract; choosing
`SERIALIZABLE` is an adapter decision, not a substitute for LoopX CAS,
operation identity, or lease fencing. Authentication, tenant routing, audit,
pool exhaustion, cancellation, timeout, and failover must all fail closed at
the service boundary.

For NoKV, the existing `load` / `compare_and_put` reference already maps
missing, generation conflict, ambiguous publication, and workbench-incarnation
lineage. It does **not** yet prove the widened event/receipt/cursor service
contract. Until capacity, retention, restart/restore, availability, and HA are
qualified, `read_receipt` and `scan_committed` can only be implemented by
reading the retained journal inside the one CAS envelope; they must not be
silently mapped to an eventually consistent listing API.

The file provider is therefore conformance evidence, not a production-scale
event store. Its retained journal intentionally makes atomicity and historical
receipt replay easy to inspect, at the cost of whole-document growth. That
tradeoff is acceptable for Stage 1 and is explicitly not inherited as the
PostgreSQL physical schema or accepted as NoKV capacity proof.

### 6.3 The three version numbers are not the same thing

| Domain | Owner | Meaning | Consumer |
| --- | --- | --- | --- |
| `provider_generation` | Provider | Opaque token for conditional replacement of stored bytes | Authority/provider seam only |
| `authority_revision` | LoopX authority | Per-goal logical commit sequence after an accepted command | Audit, receipts, and read models; not a shared precondition for every domain command |
| `lease_epoch` | LoopX authority | Per-todo fencing generation for ownership; advances on a new lease generation, not ordinary renewal | Executors and accepted writeback |

A backend may often advance its generation once per accepted command, but
numerical equality is never a contract. Migration, repair, or provider metadata
may change provider generation without granting a new LoopX authority revision.

A provider's document generation or database revision implements
`provider_generation` only. The LoopX authority remains responsible for the
other two domains and for the receipt stored inside the transaction.

### 6.4 Expiry adjudication and the binding fence

Wall-clock facts have exactly one judge: the authority that is applying a
command, reading the loaded head's `expires_at` against its own clock. A
caller's opinion of time is request motivation, never evidence; the core
stays clockless and receives only the adjudicated active/expired verdict.
Renewal, release, and completion require the lease to be active at
adjudication time. Reclaim additionally requires the lease to have been
expired for at least a configurable grace window whose lower bound is the
maximum expected clock skew between endpoints in the deployment; the grace
in force is the executor's declared parameter, and the configuration
boundary is itself fail-closed: only a finite, non-negative number is
accepted, because a NaN, negative, or boolean grace would advance a
takeover instead of delaying it. Correctness never
depends on the grace value - even a holder that believes itself alive is
fenced by the epoch the reclaim minted, so skew can only delay a takeover,
never corrupt one. Because renewal advances `todo_revision` (Section 5.2), the validity
interval is also revision-covered, closing the rebase path a reclaim could
otherwise ride across a concurrent renewal.

The store-lineage binding fence closes the restore hazard measured in the
Stage 2 status: `provider_generation` alone cannot carry lifecycle
identity. The provider contract gains one read-only verb,
`store_identity() -> str`, returning a stable identity for the store
lineage: the NoKV adapter binds `workbench` plus the never-reused
`workspace_incarnation_id` the service mints per workbench incarnation; the
file provider serializes creation under its cross-process lock and publishes a
strictly formatted identity through complete temp write, fsync, atomic rename,
and parent-directory fsync.
`bootstrap` embeds the identity in the head (`store_binding`), and the
authority refuses every command - typed `store_lineage_mismatch` - whenever
the loaded head's binding differs from the provider's identity, re-checking
after every reload. A restore therefore preserves frozen bytes and lineage
without granting live authority, exactly as the Stage 1 boundary requires;
promoting restored state needs an explicit, reviewed re-bootstrap that
mints a new binding. Known residual: a byte-for-byte copy of a file-backed
store directory copies the identity file with it, so the file provider's
fence detects relocation only when the identity file is excluded from the
copy; the NoKV incarnation identity has no such gap and is the
authoritative fence for shared deployments.

Adding the binding is a schema change, not a reinterpretation: heads carry
`loopx_coordination_head_v1`, and a legacy `loopx_coordination_head_v0`
document (the Stage 2 shape without `store_binding`) is classified as
`head_schema_migration_required` - a typed failure, never an unclassified
validation crash, and never silently readable as current. The only upgrade
path is the explicit `migrate_head_v0_to_v1` operation: an operator attests
the reviewed store's own identity (`provider.store_identity()` on the store
they have verified is the authoritative lineage) and writes the migrated
head back through the same CAS. The binding is deliberately never inferred
from whichever provider a head happens to be loaded through - an automatic
binding would let any restored copy of a v0 store authorize itself, which
is the exact capture this fence exists to prevent. Migration recognizes only
the Stage 2 writer's actual output subset: `open` todo records and
`claim_work` receipts with the exact v0 field sets. The old v0 validator did
not close the todo status vocabulary; unknown status values and Stage 3-only
fields under a v0 token are therefore treated as corruption requiring manual
repair, not grandfathered into new authority.

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

### 7.1 Proposed amendment: sealed receipt segments (owner decision, Q5)

`retain_all_v0` in one CAS document cannot reach a multi-agent canary: the
Stage 2 measurements showed ~750 bytes per receipt, a ~7x claim-latency
growth across 120 receipts, and quadratic cumulative republish. Stage 3
adds four more receipt-writing verbs, so the growth rate only worsens. The
sentence above deliberately requires a reviewed amendment before receipts
may leave the single document; this subsection is that amendment, proposed
with evidence and NOT yet in force.

Design (measured against two alternatives on a live NoKV stack, 150
transitions each): the head keeps a bounded receipt window; when the window
fills, the authority seals it into an immutable receipt-segment object at a
sibling path (`goals/<goal>/receipts/segment-<seq>.json`), published
create-only through the artifact path BEFORE the CAS that drops the sealed
receipts from the head and appends `{path, sha256, count}` to a segment
chain - the artifact-first order of Section 1.1, so the head never
references bytes that were not durably published. Every committed receipt
stays verifiable: replay looks in the window first, then dereferences the
chain; a missing or digest-mismatched segment is a provider-protocol
violation and fails closed, the segment-level form of the Section 7
fail-closed rule. NoKV's publication semantics make sealing exactly-once
for free: `operation_id` and `artifact_revision_id` are root-scoped-unique
with immutable-input replay, so a seal retried after a crash between the
segment publish and the head CAS replays idempotently (verified live) -
but both ids MUST derive from workbench, path, and content, or a second
lineage reusing the same derivation is rejected as id reuse.

Measured verdict (debug stack, relative numbers): sealed segments keep the
head 19x smaller (5.8 KiB vs 112 KiB at 150 receipts), publish 7.5x fewer
cumulative bytes, and hold per-transition latency flat where retain_all
grows, for +3% provider round trips; recovering an already-sealed receipt
costs ~160 ms versus ~43 ms in-head. The receipt-per-object alternative is
dominated: it pays an extra object publish on every transition (about 2x
latency throughout) and still grows the head linearly through its pointer
index. Window size is a deployment parameter; 16 was measured.

Until the owner accepts this amendment (Section 12 Q5), `retain_all_v0`
remains in force and the Stage 3 verbs ship on it unchanged.

### 7.2 Ten-day goals: local storage qualification target (proposal)

A supported goal must remain executable for **at least ten elapsed days**, across
process restarts, sleeping hosts, delayed receipts, and binary upgrades, without
manual history truncation or a storage-driven goal reset. Ten days is a minimum
qualification horizon, not a receipt expiry or a maximum goal lifetime. This
amendment sets the product target; no current provider is declared qualified by
this text, and `retain_all_v0` remains the shipped rule until a reviewed cutover.

#### Workload and cost model

Elapsed time alone is not a capacity specification. The initial local qualification
matrix uses the following **proposed workloads**, not measured usage or promises:

| Profile | Workload per goal | Qualification horizon |
| --- | --- | --- |
| Minimum continuity | Three continuously leased Todos, TTL 600 s, renewal every 300 s: 864 renewals/day before other writes | 10 days; 8,640 renewals plus lifecycle/receipt traffic |
| Local design target | Eight registered agents; four concurrent writers on distinct Todos plus same-Todo races; up to 1,000 active Todo/lease/gate records; 10,000 committed transactions/day including renewals, receipts and capture | 10 days; 100,000 commits; 30-day / 300,000-commit headroom run |
| Payload and backlog axes | Live projection 8 KiB, 64 KiB and 1 MiB; new event/receipt payload up to 4 KiB per commit; 5:1 reads/writes; 10 commits/s bursts for 60 s; 24 h of projection-consumer lag | Exercise each axis separately and the combined local target; count retries/conflicts separately from commits |

Each fixture declares active versus archived records, serialized sizes, command
mix, index size, and capture fan-out; a model Turn can cause several commits.
Keep live-state size fixed when isolating history growth, then grow live state
separately. No goal-wide unbounded list of completed Todos or receipts may be
hidden inside the supposedly fixed live projection.

For the current `FileAuthorityStore`, a fixed projection of P bytes retained in
each of N transactions costs approximately P*N final history bytes and
P*N*(N+1)/2 cumulative document-publication bytes, before head, event, receipt,
and envelope overhead. Normal reads also decode and validate the full chain.
With P=15 KiB, the renewal-only case gives about **534 GiB** of cumulative
publication at day 10 and **4.69 TiB** at day 30. The former 380 MiB estimate was
only N*P at day 30, not the cumulative rewrite of retained projections. These
are analytical payload estimates, not physical SSD writes or measured latency;
growing receipt indexes inside every projection can make the model worse.

#### Preferred local direction and compatibility boundary

Qualify an **embedded transactional store, with SQLite as the first candidate**,
behind the existing TypeScript `AuthorityStore` owner. A local goal must not
require a PostgreSQL service. The file-v0 provider remains a conformance/import
baseline; no general-purpose ten-day promotion may rely on its full-history
rewrite. SQLite is a design preference pending durability, dependency/package,
Windows/macOS/Linux and supported Node-version qualification, not a new shipped
provider id or default flip. A segmented file log remains the comparison option;
PostgreSQL remains the independent shared-service path.

A database swap alone is insufficient. The complete slice must:

- Atomically publish current state, operation/digest uniqueness, original
  receipts, ordered cursor, and any projection outbox entry. Use indexed
  operation lookup and cursor paging. Preserve the existing ambiguous-commit,
  CAS, lineage, and domain fencing semantics; storage never decides Todo policy.
- Keep live head independent of total history. Use periodic verified checkpoints
  plus committed state deltas or immutable state blocks; retain original receipts
  outside the hot head. Bound both replay tail and index/root metadata. A head
  containing every sealed-segment pointer is still unbounded, and scanning a
  receipt-segment chain for old retries is not an indexed lookup.
- Preserve the logical `scanCommitted` contract: it currently returns a full
  projection for each transaction. Reconstruct the exact version from checkpoint
  and deltas with bounded paging, or version the contract and migrate every
  consumer explicitly. Do not silently remove historical projections. Existing
  events have not been proven sufficient to reconstruct them; canonical state
  deltas need independent equivalence checks.
- Move the authority's growing in-head receipt index through an explicit versioned
  migration, together with provider storage. Preserve request-digest conflict
  detection and byte-equivalent original receipt fields after checkpointing,
  restart, and later unrelated commits. Caching cannot be the correctness path.

This is one local persistence slice with real CLI callers and consumer readback,
not separate leaf-helper ports or a second semantic kernel. It includes the
capture outbox and paginated archived-Todo/history reads needed by status/quota;
other stores and raw artifacts are measured separately, not claimed fixed by it.

#### Proposed acceptance budgets

On a declared local SSD host, report OS/filesystem, CPU/RAM, Node/database versions,
durability settings, sample count, p50/p95/p99, lock wait, RSS, database/WAL/archive
size, and logical bytes written. Include cold CLI startup separately from warm
store service time; never disable fsync/checkpoint safety to pass.

For the 64 KiB live-state axis at 10,000 versus 100,000 commits:

- Warm head load and indexed original-receipt read p95 <= 50 ms; durable commit
  p95 <= 100 ms. History-growth p95 ratio <= 2 with the same live state and load.
- Warm scan of 100 transactions p95 <= 250 ms; cold open plus first authoritative
  read <= 2 s; bounded crash recovery <= 30 s. Full archive integrity audit is
  separate and may be linear, but normal startup may not require it.
- Storage work adds <= 200 ms p95 to a complete CLI mutation against the matched
  10,000-commit baseline. Measure full status/quota latency too; do not hide a
  history scan in a compatibility consumer or amortize process startup away.
- At fixed live state and delta sizes, cumulative logical writes, retained bytes,
  and recovery work must have declared bounds. From 10,000 to 100,000 commits,
  cumulative bytes written must grow <= 15x, not the roughly 100x quadratic
  rewrite; instrument checkpoint, index, WAL and compaction work. Stable-state
  RSS must not scale with the number of historical transactions. Report the
  1 MiB axis and 300,000-commit headroom separately; failures narrow the supported
  profile rather than disappearing into averaged results.

These thresholds are proposed engineering budgets, not current measurements.
Review them against the first matched baseline before activation; do not relax
correctness, silently change the workload, or advertise an unqualified horizon.

#### Retention, recovery and delivery gates

Ten-day operation does not authorize day-11 deletion. Keep operation identity,
digest and original receipts for the goal lifetime under the initial policy,
including at least the day-1 retry after day 10 and day 30. Physical compaction
may remove redundant encodings only when the retained checkpoint/log/index can
reconstruct every promised historical record. Cold archive must remain
addressable and verified; unavailable proof fails closed, never as a fresh
operation. Any later expiry requires a versioned retention contract and explicit
outside-window response; neither a TTL nor a tombstone permits duplicate effects.

Checkpoint/segment publication must be crash-safe with a durable manifest/root
switch. Reclaim old bytes only after durable replacement and every registered
consumer's persisted cursor or explicit full-resync decision; protect lagging
projection outboxes, exports, and backups. Set byte/lag admission budgets and
surface maintenance/backpressure before disk exhaustion. Admission must reserve
recovery space; ENOSPC or an interrupted commit cannot erase proof or count as a
successful write. Total audit storage may grow linearly with useful history;
only the hot path and maintenance batches are bounded.

Sleeping or restarting a host does not preserve an expired lease: resume must
re-read authority and reacquire through normal epoch fencing. Continuity means
the same durable goal resumes safely, not that a process or lease stays alive.

Qualification has two separate exits: accelerated 100,000/300,000-commit tests
prove volume, while an actual >=10-day synthetic-goal soak proves elapsed-time
continuity. Exercise day-1 historical retries, duplicate/different-digest writes,
concurrent CAS, daily reopen, host sleep, lease expiry, 24 h consumer lag, crashes
around append/checkpoint/index publication, disk-full, backup/restore lineage,
and a supported upgrade/rollback. Compare final state, receipts and cursor scan
to an independent reference; no lost acknowledged commit or repeated effect is
acceptable. Use disposable goals, never active user state. Compressed clocks do
not qualify wall-clock endurance; publishing this RFC starts no soak or monitor.

A code PR can land while soak evidence remains pending, with promotion held.
Promotion requires both exits, explicit import/fencing/export rehearsal and
maintainer review. Publish compact reproducible evidence, not raw private logs.

## 8. Local Mode Stays the Default; Shared Mode Is an Explicit Migration

### Default local mode

- Existing project registry, Markdown active state, run history, optional task
  leases, status, quota, and host behavior remain unchanged.
- Installing a provider does not enable shared authority.
- The current event-store bridge still reports Markdown as source of truth and
  does not allow automatic promotion.

Two deployment shapes share the same semantics:

| Deployment | Authority boundary | Provider |
| --- | --- | --- |
| embedded/local | LoopX authority runs in the trusted local process; existing local writers remain canonical until promotion | file |
| shared service | Agents call an authenticated LoopX authority API; the service owns provider credentials, tenancy, and audit | NoKV or PostgreSQL |

An Agent is an API client in both shapes. Direct provider access never becomes
an alternative shared mode.

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

### 11.1 Normative stage plan

The delivery program has one shared foundation and two provider-specific
tracks. Workstream labels are responsibility boundaries, not authority grants:

| Workstream | Primary responsibility |
| --- | --- |
| LoopX core owner | TypeScript-owned semantic transaction boundary; file-provider parity and promotion; migration, local-writer fencing, projection flip, rollback, and the single authority-source decision |
| NoKV provider owner | NoKV adapter; live recovery, capacity, and HA qualification; feedback into the shared store contract without moving semantics into NoKV |
| PostgreSQL provider owner | Generic PostgreSQL provider/service; transaction isolation, authentication, tenancy, audit, and operational deployment contract |
| Joint qualification | Provider conformance matrix, one-way shadow parity, one-Goal/two-Agent TEST ONLY canary, and promotion evidence |

The shared control plane is a composition of independently owned ledgers, not
one large coordination aggregate. Stage 3/4 qualification must preserve these
ownership and proof boundaries:

| Ledger / decision | Authority and stable identity | Failure boundary | Stage 3/4 proof |
| --- | --- | --- | --- |
| Coordination head, Todo/claim, and lease fence | `AuthorityStore`; `(tenant_id, goal_id)`, `operation_id`, authority revision, and lease epoch | provider CAS/transaction plus operation-receipt readback | provider parity for projection, legal claim/lease transitions, fence, receipt, head, and cursor |
| Turn admission and quota | independent Turn/quota ledgers; obligation, admission, debit, and void receipt identities | their own append/idempotency boundary; never absorbed into a coordination commit | end-to-end observation that admitted work references the accepted coordination head and accounts quota once |
| Delivery, inbox, and external effects | independent delivery/inbox/provider ledgers; event cursor, effect identity, and provider receipt | connector/effect ambiguity is reconciled at its owning ledger | end-to-end observation that steering changes a later decision and an effect is not duplicated |
| Settlement and run history | independent settlement journal and run ledger; settlement/phase receipt and run identity | ordered settlement checkpoints and idempotent replay | end-to-end observation of exactly-once settlement across restart, referenced from rather than stored inside coordination state |

Only the first row qualifies an `AuthorityStore` implementation. The remaining
rows qualify control-plane composition through typed references and receipts;
passing them must not be reported as additional state owned or transacted by
the coordination provider.

The sequence is:

1. **Stage 0 - merge the recoverable reference foundation.** Integrate #3669
   with the native TypeScript task-lease acquire boundary, preserve TypeScript as
   the acquire transaction owner, and close file store-identity publication.
   #3806 completes the local lifecycle transaction cutover and makes renew,
   transfer, and release consume one pure TypeScript decision in both the local
   file executor and provider-neutral coordination; Python is a typed adapter,
   not an alternate authority.
2. **Stage 1 - define the provider-neutral transaction boundary.** Express the
   service-grade contract in LoopX-owned TypeScript and make the file provider
   its first conformance backend. Do not recreate a second Python semantic
   authority.
3. **Stage 2A/2B - implement providers in parallel.** The NoKV owner qualifies
   the NoKV adapter and storage envelope; the PostgreSQL owner implements the
   generic service/provider. Both reuse the same LoopX transition and receipt
   semantics.
4. **Stage 2C - qualify and promote the first canonical profile.** First shadow
   the current Markdown/task-lease writers into `FileAuthorityStore` without
   reading it for decisions. Prove parity, crash recovery, migration, and
   one-command rollback; then, in a separately reviewed promotion, make that
   profile the local coordination authority and fence the legacy writers.
   Markdown and task-lease files become projections only after promotion. The
   state machine, complete field manifest, receipts, and acceptance rows remain
   provider-neutral so NoKV and PostgreSQL can qualify through the same route.
   Projection shape or head-digest parity alone is insufficient: promotion
   must prove complete consumer-visible Todo and lease semantics at the exact
   qualified revision.
5. **Stage 3 - one-way remote shadow parity.** The promoted local
   `FileAuthorityStore` remains the only authority while committed observations
   are projected to a NoKV or PostgreSQL candidate. Provider parity compares
   Todo/claim, lease fence, operation
   receipt, projection head, and cursor. Turn admission, quota, settlement,
   inbox, and run history remain independent ledgers: the shadow records only
   typed references needed to verify their end-to-end composition. Do not
   perform bidirectional synchronization or provider-to-file writes.
6. **Stage 4 - TEST ONLY canary.** One Goal and two Agents must show no duplicate
   claim, correct expiry/fencing, restart resume, and fail-closed coordination
   writes during network failure. The same canary separately observes that no
   external effect is duplicated, inbox steering changes a later decision,
   and settlement is idempotent and exactly-once; those are composition proofs
   over their owning ledgers, not `AuthorityStore` conformance claims.
7. **Stage 5 - flip one authority source.** Only after a reviewed promotion,
   make the shared LoopX service the sole writer. Local `.loopx` state becomes
   cache, offline projection, and diagnostic material. Never keep a long-lived
   dual-write or dual-master mode.

### 11.2 Current implementation and evidence ledger (non-normative)

The dated entries below preserve shipped boundaries, experiments, and review
findings. They are evidence for the stage plan, not additional specification.
Later entries supersede earlier status claims only when they identify the
relevant contract, exact implementation boundary, and validation evidence.

| Ledger entry | What it records |
| --- | --- |
| Stage 2C observation foundation | Default-off post-commit capture and its crash window |
| Implementation prerequisite / Stage 1 Part 2 | Provider-neutral decision extraction and remaining Python/TypeScript ownership boundary |
| Stage 2B PostgreSQL candidate | PostgreSQL store/RLS conformance, without runtime promotion |
| Stage 2C runtime shadow | Parity, read-candidate, bootstrap, rollback, cutover kernel, and writer fence |
| Stage 2 slice | Reference aggregate/provider implementation and initial NoKV evidence |
| Stage 3 slice | Recoverable lifecycle, retention findings, and live provider limits |
| Stage-ladder evidence | Executable stage claims, environment gates, and pending rows |

#### Stage 2C observation foundation: local post-commit capture

The first half of Stage 2C is an explicit, default-off product path. Preview
and enable it with:

```bash
loopx configure-goal --goal-id GOAL --local-authority-shadow-file
loopx configure-goal --goal-id GOAL --local-authority-shadow-file --execute
```

Todo, handoff-mode, follow-up, and task-lease facades sample the full current
local projection after their primary write returns committed, then ask
`FileAuthorityStore` to retain that snapshot. `observation_trigger` records
why sampling began; it is not the primary transaction identity. A concurrent
primary commit may therefore appear in the sampled snapshot. A `captured` or
`replayed` result proves only the candidate-side observation commit. It does
not compare the source and candidate and carries `parity_verdict=not_evaluated`.

Candidate bytes live under
`authority-shadow/file/` outside the legacy per-Goal runtime tree, so state
migration never copies a store identity or revision; an executed migration
seeds a new target lineage from the migrated local state. Candidate failure is
reported as an observation result but never reverses the completed local write.

Disable the observer in one command with
`loopx configure-goal --goal-id GOAL --clear-local-authority-shadow --execute`.
This is rollback of observation only: the local Markdown and task-lease files
remain canonical throughout. The slice does not read the candidate for a
decision, fence a legacy writer, qualify a remote provider, or complete the
second Stage 2C promotion. A process crash after the local commit but before
the observer call may miss that individual observation; a later committed
write or migration seed refreshes the full current projection, but no durable
shadow outbox or transaction-correlated receipt is claimed here. This plumbing
is not parity evidence and cannot by itself support Stage 2C promotion.

#### Implementation prerequisite: put local file mode behind the same coordination contract

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

The provider-neutral pure authority core is merged on `main` through #3410.
This slice is a behavior-preserving extraction of a pure decision core for the
todo lifecycle, task-lease lifecycle, and `handoff_mode` rules that the current
writers already enforce. Markdown goal state and task-lease files remain
canonical. The extraction does not synthesize todo, authorization, dependency,
or gate revisions for domains that have no current revision publisher. It also
does not replace today's separate claim and lease verbs with the atomic
`claim_work` command described above; that command belongs to the future shared
aggregate.

After the task-lease TypeScript cutovers, acquire is owned by
`task_lease_acquire.ts`, while renew, transfer, and release are owned by the
pure seam in `task_lease_lifecycle_decision.ts`. Python `authority_core`
projects normalized snapshots, invokes those decisions, and reconstructs the
provider-neutral `TransitionPlan`. The local lease-file transaction and the
coordination executor therefore consume the same lease decisions; locking,
source revalidation, file persistence, provider CAS, and receipt construction
remain in their respective execution layers. Todo, terminal-fence, and
handoff-mode decisions stay in the Python core until their own reviewed
TypeScript cutovers; local holder/fence-close lock mechanics remain execution
effects rather than provider contracts.

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

#### Stage 2B PostgreSQL candidate status (2026-09-02)

The first PostgreSQL candidate now implements the LoopX-owned TypeScript store
contract instead of introducing a second semantic authority. A store handle is
bound to `(tenant_id, goal_id)` and receives only a service-owned database
pool. Its fixed `loopx_control_plane` schema separates the scoped head,
committed operations, ordered events, and ordered receipts. One SQL transaction
creates or locks the scoped head row, checks the opaque provider revision,
fences `operation_id` with a unique constraint, allocates the per-goal cursor,
inserts the commit/events/receipts, advances the projection head, and commits.
An error before `COMMIT` is rolled back and typed `failed`; an error after the
`COMMIT` attempt starts is typed `ambiguous` and can be reconciled only by
receipt readback. Database-incarnation metadata is installed administratively
and cannot be rebound implicitly.

The database trust-boundary slice now gives each provider operation a
transaction-local `loopx.tenant_id` context and enables plus forces PostgreSQL
row-level security on every tenant-scoped table. Reads use a read-only
transaction and roll it back before returning, so a pooled session cannot
retain a previous tenant context. A missing context sees no scoped rows;
`WITH CHECK` rejects a row for any tenant other than the active context. The
qualified restricted-role profile receives only schema usage, metadata read,
and the minimum scoped table privileges, so it cannot rebind
database-incarnation metadata or install schema policy.

This is defense in depth inside the service, not tenant authentication. The
service still owns the database role and chooses the transaction context after
authenticating a principal and authorizing its tenant. An Agent never receives
that role, and RLS does not make a caller-supplied tenant id trustworthy.

This slice also moves strict JSON validation and commit normalization out of
the file implementation into one TypeScript authority-store codec. File and
PostgreSQL now run the same provider-neutral conformance suite for atomic
projection-plus-receipt commit, CAS contention, historical receipt replay,
operation fencing, ordered cursor scans, isolation of returned values, and
pre-write rejection of malformed JSON.

Promoted `hard_lease` authority also supports one optional ownership
transaction through the existing Todo-claim caller contract. When the caller
supplies a task-lease idempotency key and optional expected version, the
TypeScript owner reads the canonical Todo and its required write scopes,
reuses the typed lease-acquire decision, and commits the lease, claim, and
receipt under one provider CAS. Omitting those fields preserves the existing
claim behavior, and an unpromoted goal rejects the atomic-only options rather
than attempting a legacy write. File, NoKV, and real PostgreSQL conformance
includes competing-owner coverage: exactly one complete claim-plus-lease
tuple wins, the loser receives no receipt, and the winner replays by its exact
operation identity. This is a cohesive promotion of the existing contract,
not a second `claim_work` abstraction.

The PostgreSQL adapter also applies one provider-local resource guard before it
opens a connection: a commit whose canonical envelope exceeds the configured
`max_commit_bytes` is rejected as typed `store_capacity_exhausted`. The default
is 16 MiB and a deployment may lower it. This is an admission ceiling for one
atomic operation, not measured throughput evidence and not a retention or
partitioning design; those promotion holds remain open.

Real PostgreSQL qualification starts here, not at shadow or canary. A
PostgreSQL 16 instance passed the shared conformance matrix, same-head
concurrent CAS, tenant-scoped reuse of the same goal and operation ids,
transaction rollback with no visible head or receipt, receipt recovery after a
committed transaction loses its response, database-incarnation rebind refusal,
and a restricted-role two-tenant RLS matrix. The latter proves that missing
transaction context exposes no scoped row, cross-context writes fail, and the
runtime role cannot mutate administrative metadata. A fake can still exercise
adapter branches, but it cannot prove row locking, unique constraints,
rollback, commit visibility, privileges, or RLS; every later PostgreSQL
provider slice must therefore retain a real-database gate.

The candidate remains coverage-only. No production LoopX entry point constructs
it, local mode remains unchanged, and Agents cannot receive the injected pool.
The database runtime-role and RLS behavior within the service trust boundary is
now implemented and qualified. Service API authentication,
principal-to-tenant authorization, the production runtime caller,
restore-incarnation rotation, pool
exhaustion/cancellation/failover, retention/partitioning/measured capacity,
one-way shadow parity, the TEST ONLY canary, and authority-source promotion
remain explicit holds. The next PostgreSQL slice must qualify the authenticated
service/deployment and failure boundary; it must not treat database RLS or the
single-commit admission ceiling as those missing service and capacity layers.

The file-backed provider contract and executor are Stage 2; their first slice
is merged on `main` through #3529, and the evidence behind it is recorded in
the Stage 2 status subsection below. That slice proves the aggregate and
provider boundary, but it is not the Stage 2C production runtime shadow: it
does not hook the legacy Todo or task-lease writers.

#### Stage 2C post-commit runtime-shadow status (2026-09-03)

The first production-path shadow slice is implemented behind this exact,
default-off goal configuration:

```json
{
  "coordination": {
    "runtime_shadow": {
      "enabled": true,
      "schema_version": "loopx_coordination_runtime_shadow_config_v0",
      "provider": "file_v0"
    }
  }
}
```

Activation requires all three values. An absent, disabled, malformed, or
unsupported configuration preserves the legacy result and returns typed
disabled evidence. When enabled, the runtime obeys the following boundary:

- the legacy Markdown Todo writer or task-lease writer commits first and
  remains canonical; only a successful primary mutation dispatches the
  shadow;
- the Python adapter projects the committed Todo view through the same shared
  canonical read-record contract used by `todo list`, retains every
  consumer-visible identity, text, priority, filtering, continuation, resume,
  scheduling, archival, completion, note, and evidence field, sorts records by
  stable Todo identity, and sends that view plus compact leases through the
  existing TypeScript effect runtime;
- the TypeScript owner writes that projection and its operation receipt in one
  `AuthorityStore` transaction. It checks an existing receipt before writing,
  rejects reuse of an operation id with different normalized content, retries
  provider-revision contention only within a fixed bound, and reconciles an
  ambiguous commit only by reading the exact durable receipt;
- an applied result reads the receipt back and verifies the current provider
  head when it has not already been superseded. Every result states
  `decision_read_from_shadow=false`; a disabled, failed, conflicting, or
  ambiguous shadow result cannot reject, roll back, or rewrite the committed
  primary result.

Cross-runtime tests exercise the real Python -> TypeScript ->
`FileAuthorityStore` path from both Todo and task-lease hooks, including
default-off behavior, stable replay, content-drift rejection, ambiguous-commit
recovery, projection read-back, and shadow-failure isolation. This closes the
first runtime-shadow slice. A follow-up typed inspection seam now compares the
current compact legacy projection with the file head and reports `missing`,
`matched`, or `drifted` plus both content digests. It is default-off,
read-only, and always returns `decision_read_from_shadow=false`; this provides
the reusable baseline/parity observation needed by migration without turning
an observation into authority.

The next migration primitive is now also present behind the same explicit
opt-in. `coordination.runtime_shadow.bootstrap` installs one normalized legacy
projection only when the file shadow is uninitialized. Its first committed
event durably binds the source version, source projection digest, and
`legacy_canonical_shadow` mode declaration; it deliberately carries an empty
receipt payload because no agent operation has run. Exact replay is recovered
from that first transaction, including an ambiguous lost response, while a
different existing lineage fails closed. This is the provider-owned bootstrap
effect needed by a later administrative migration command; it still cannot
promote the shadow or make a coordination decision.

The administrative caller is explicit and preview-first:

```bash
loopx coordination-shadow inspect --goal-id <goal-id>
loopx coordination-shadow bootstrap --goal-id <goal-id>
loopx coordination-shadow bootstrap --goal-id <goal-id> --execute
loopx coordination-shadow qualify --goal-id <goal-id> \
  --minimum-operations 3 \
  --require-event-kind todo_claim \
  --require-event-kind task_lease_acquire
loopx coordination-shadow rollback --goal-id <goal-id> \
  --provider-revision <revision-from-inspect> --execute
```

It derives the compact projection from the current canonical Todo and
task-lease views, reports only counts and digests, and requires `--execute`
before invoking bootstrap. A successful write is immediately read back through
the typed parity inspection. The command remains unavailable unless the exact
goal-level `file_v0` shadow opt-in is active.

Pre-promotion rollback is revision-fenced and non-destructive. TypeScript moves
the exact active file-shadow lineage into a durable quarantine archive; exact
retries replay that archive receipt, revision drift fails closed, and the
legacy Todo/task-lease source remains canonical throughout. A later bootstrap
may therefore reconstruct a fresh shadow without restoring or trusting the
retired lineage.

The read-only `qualify` action turns one-point inspection into a typed sustained
parity report. Its coverage-based policy requires a caller-selected number of
distinct committed operations and any explicitly named Todo/lease mutation
kinds. TypeScript scans the complete bounded lineage, verifies the bootstrap,
every event/receipt/projection identity, the current legacy/file head digest,
and reports `qualified`, `insufficient_evidence`, or `drifted`. Replays do not
increase the operation count, missing coverage fails the gate, and every result
continues to declare `decision_read_from_shadow=false`.

Structural parity is not consumer semantic parity. A promotable projection
therefore also carries a versioned Todo read-model receipt containing the exact
field contract, record count, and canonical record digest. TypeScript validates
that receipt against deterministic provider records during qualification,
promotion, and every provider-first collection read; a missing schema, stale
digest, truncated field contract, count mismatch, or unstable order fails
closed. Provider-first mutations regenerate the receipt atomically with the
head. Adding a Todo consumer field is a contract change and requires a new
qualification rather than a permissive fallback.

Before any real Goal is promoted, qualification must additionally execute the
existing consumer pipeline on both the legacy source and the provider
round-trip at the same revision. The semantic matrix covers user and agent
roles; open, done, blocked, and deferred status; priority and ordering; claim,
exclusion, bound-agent, and global-gate filtering; resume conditions;
successor/continuation behavior; continuous-monitor cadence, due time,
watch-only and material-generation state; notes, evidence, completion, and
archival; and provider-only reads after the Markdown file is unavailable. Any
difference blocks promotion and leaves legacy authority in place. Synthetic
stubs remain useful unit tests but cannot substitute for this real complex-Goal
qualification. Real Goal content stays local; public evidence contains only
redacted coverage, counts, exact revision identifiers, and digests.

The next read-only seam exercises the provider shape needed by the future
read flip without granting it authority:

```bash
loopx coordination-shadow read-candidate \
  --goal-id <goal-id> \
  --todo-id <todo-id>
```

TypeScript loads the file head, requires its digest to match the complete
current legacy coordination projection, validates unique Todo identities, and
returns the exact compact Todo plus the provider revision and cursor. Missing,
drifted, malformed, or duplicate state fails closed. The result deliberately
keeps `decision_read_from_shadow=false`: it proves that a parity-matched
provider can answer an exact Todo read, but no lifecycle or settlement caller
uses that answer yet. Promotion still requires an atomic provider-first read
flip together with legacy-writer fencing; a fallback to Markdown after that
flip would recreate split authority and is forbidden.

The provider-first read flip and fencing every legacy coordination writer
remain mandatory evidence for the separately reviewed local canonical
promotion. Remote NoKV/PostgreSQL shadowing therefore remains Stage 3 and
cannot use this default-off hook as authority.

The next Stage 2C implementation slice adds the TypeScript cutover kernel but
does not yet change the default runtime. One pure reducer now derives the
Todo/lease projection, event, and receipt from the same mutation. An explicit
promotion operation requires a qualified shadow at one exact provider revision
and digest, plus an independently persisted legacy-writer fence bound to that
same revision. The fence has a shared fail-closed write-check hook; promotion
is replayable through its operation receipt, and provider-first reads and
mutations never fall back to Markdown. Until the Python Todo and task-lease
entry points call that hook and select the promoted mode, these surfaces remain
cutover machinery rather than a production authority flip. The follow-up must
wire every legacy writer, make configuration and rollback explicit, and prove
default legacy compatibility before the local promotion can be enabled.

The first production fencing integration now closes the write side of that
follow-up. Every Python Todo mutation checks the TypeScript-owned durable fence
while holding the existing active-state mutation lock, and native TypeScript
task-lease acquire/renew/transfer/release check the same fence while holding the
lease lock. The absent-fence path remains a zero-runtime-call compatibility
path; a present, unreadable, or invalid fence fails closed. The promotion
orchestrator must acquire those same two legacy locks before engaging the fence,
so no legacy write can pass its check and commit after cutover. Provider-first
CLI routing and the lock-owning promotion operation remain the next slice; until
they land, this integration deliberately blocks split-brain writes rather than
silently falling back.

The Todo collection-read slice routes `loopx todo list` to `FileAuthorityStore`
only after the durable fence exists. It reuses the same filtering, ordering,
resume, and summary pipeline as the legacy path, permits provider-only reads
when Markdown is absent, and carries an authority receipt in the response.
Provider missing, corruption, protocol drift, or Todo read-model semantic drift
all fail closed; no post-cutover Markdown fallback is permitted.

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

#### Stage 2 slice status (2026-08-23)

The first Stage 2 slice is merged on `main` through #3529, additively:

- `loopx.control_plane.coordination.head`: the `loopx_coordination_head_v0`
  aggregate codec. Validation is closed-set and fail-closed for every field
  the executor later dereferences: todos, lease records, and each
  receipt-index entry (entry shape, digest form, receipt schema, operation
  identity, todo membership, revisions, epochs, and timezone-aware UTC
  timestamps: a naive timestamp reads differently under each host's
  local timezone, so it fails closed),
  including bool-disguised integers; `handoff_mode` is a recorded head
  field, pinned to `hard_lease` in v0 (a `soft_claim` goal fails bootstrap
  closed instead of having its declared semantics silently inverted).
  Canonical bytes are defined as sorted-key, minimal-separator UTF-8 JSON
  with non-finite numbers rejected; digests and provider byte parity are
  defined against exactly that encoding, so "deterministic serialization"
  is a contract term here, not an implementation accident. The Markdown
  shadow constructor lives in its own bridge module
  (`goal_state_shadow`), keeping the codec's import closure inside the
  repository's strict type gate.
- `loopx.control_plane.coordination.file_provider`: one goal, one document.
  Locking goes through `loopx.file_lock`, the repository's one
  cross-platform lock owner, with its bounded deadline (a lock that cannot
  be acquired in time is a typed `failed` because no write was attempted).
  Durability is a fixed commit sequence: write-all of the canonical bytes
  (short writes are continued, never ignored), file fsync, atomic rename,
  then parent-directory fsync on POSIX; `applied` is returned only after
  the whole sequence converges, and any storage fault inside it reports
  `ambiguous`. A head with no faithful strict-JSON form reports typed
  `failed` before any write reaches disk.
- `loopx.control_plane.coordination.executor`: Section 5 steps 1-10 for
  `claim_work`. Every domain decision is delegated to the Stage 1 core; lease
  acquire reaches its canonical TypeScript decision through the typed Python
  adapter, while the claim decision remains in the Python core. The
  composition is lease acquire followed by the hard-lease-gated claim,
  because a claim-first or legacy-mode composition silently bypasses the
  Appendix B holder gate (the tests pin this). `lease_ttl_seconds` is
  bounded by the local task-lease authority's own ceiling, so the shared
  envelope cannot mint a lease the local contract would refuse and an
  unbounded caller value cannot escape as timestamp-arithmetic overflow. A
  provider `failed` verdict is verified against the reloaded receipt index
  rather than trusted, so a provider that misreports a landed write cannot
  manufacture a claim whose caller was told it failed.

Design selection was comparative: three executor candidates (core-delegating,
inline-rules reference, journal-style receipt log inside the same document)
ran one scenario battery. Only core-delegating candidates follow a flipped
core rule without local edits, and the journal codec saves no meaningful
bytes under `retain_all_v0`; the shipped executor is the core-delegating
candidate.

Live qualification ran against a single-node NoKV dev stack at the 0.11.0
tag through its Python SDK: the eight-scenario invariant matrix in
`examples/nokv-shadow-provider/live_e2e.py` passes identically for the file
provider and the NoKV provider (same-todo race with one winner,
independent-todo progress, exact replay, identity mismatch, stale-revision
conflict, lost-response recovery through the receipt index, receipt
retention, authority-revision advancement), and a SIGKILL of the serving
owner followed by an operator-style reopen preserved the head byte for
byte, replayed the original receipt exactly through a fresh executor, and
resumed CAS across all three version domains. Renew/release/reclaim,
retention policy, HA, and multi-node deployments remain unexercised, as the
Later-qualification list already states.

Measured boundaries Stage 3 must respect rather than rediscover:

- `retain_all_v0` costs roughly 750 bytes per receipt inside the one CAS
  document; on the dev stack, claim latency grew about sevenfold across the
  first 120 receipts, and cumulative republish bytes grow quadratically
  (about 84x the final head size after 120 claims). The Section 12 retention
  decision is load-bearing before any production canary.
- Under 12 concurrent independent-todo claims, the internal rebase budget
  admitted 8 and the rest returned typed failures. The Section 1
  independence promise holds at two endpoints and degrades beyond that; the
  supported concurrency envelope and retry budget belong in the acceptance
  checks once a multi-agent canary is scoped.
- The NoKV document generation restarts after remove/recreate and after
  restore into a new workbench lineage. A conditional replace carrying a
  stale generation observation was observed to succeed on a recreated path,
  and a restored line re-reaches generation numbers whose receipts differ
  from the original line. This confirms the boundary sentence above:
  `provider_generation` alone cannot carry restore or lifecycle identity;
  the lineage/binding fence needs an explicit provider-contract field in the
  next stage.
- `provider_outcome_unproved` is a real terminal state in live runs, observed
  without fault injection. Replay through the receipt index makes
  re-submission idempotent, so a bounded re-attempt at the same generation
  would be safe; whether v0 adopts that liveness amendment is an owner
  decision recorded here, not silently implemented.

#### Stage 3 slice status (2026-08-26)

The recoverable-execution horizon row exists on this branch, additively:
the four verbs of Sections 5.2-5.5 with the stale-fence rule of 5.6, the
expiry adjudication and store-lineage binding fence of 6.4, per-verb
receipt schemas, conditional completion validation in the head codec
(status vocabulary pinned to open|done, previously unvalidated), and the
holder gate that refuses a correct fence in the wrong hands. Every domain
decision remains delegated to the Stage 1 core; the reclaim composition
was selected by a three-way battery against the real core (the naive
acquire-first composition dies on owner_conflicts_with_claim; the chosen
form does the minimal delegated unclaim and then the ordinary claim
composition, so the new lease passes the true holder gate).

Live qualification (single-node NoKV dev stack, 0.11.0 release wheel):
twelve shared scenario rows identical across the file and NoKV providers,
including renew, grace-window reclaim with the superseded owner recorded,
the superseded executor's writes terminally fenced, and completion
creating a claimable successor atomically; one NoKV-specific row proves
the binding fence against a REAL commit/snapshot/restore - the restored
workbench refuses every command with store_lineage_mismatch while the
original keeps serving. A SIGKILL of the serving owner mid-lifecycle
recovered in ~61 s (60 s session lease drain): the head byte-identical,
the renewal receipt replayed exactly through a fresh executor, and the
post-crash reclaim/fence/completion chain completed on the reopened
store. Clock-boundary tests pin the grace window edge for edge.

Measured gates, updated:

- Concurrency envelope (grown from the Stage 2 numbers): K independent
  claims all succeed through K=8 on this stack (p50 2.8 s / 10.2 s /
  50.7 s at K=2/4/8); K=16 admits 8 and fails the rest typed on the
  8-attempt budget with ~150 s tails. The supported envelope declaration
  for a canary is K<=8 with the measured latency curve.
- Retention: the Section 7.1 sealed-segment amendment is proposed with
  live comparative evidence (19x smaller head, 7.5x less republish, flat
  latency, +3% round trips, ~160 ms sealed-receipt recovery); the slice
  itself ships on retain_all_v0 until the owner decides Q5.
- Two NoKV storage-plane defects surfaced by the independent reruns and
  are reported upstream rather than worked around silently: (a) reopen
  thrash can wedge logical-shard recovery publication at a dead lease's
  epoch, leaving every later takeover attempt rejected with "stale
  lease" until operator intervention; (b) a SIGKILL landing inside the
  metadata write window can corrupt the store manifest
  (FileBlobStore duplicate slot) so no reopen ever succeeds - the
  coordination layer above stays correct in both cases (no false
  authority), but availability depends on these fixes before any
  production canary.

Review-driven hardening (2026-08-27): the reclaim grace configuration
boundary is fail-closed (Section 6.4; a NaN or negative grace could
previously take an active lease), evidence uses a privacy-bound
`artifact://` URI with a closed vocabulary
(Section 5.5; a host path or privacy mismatch could previously persist into
the shared head), and the head schema is versioned as
`loopx_coordination_head_v1` with the explicit v0 migration path
(Section 6.4; a Stage 2 head previously failed unclassified).
That migration now reconstructs the Stage 2 single-command history from its
retain-all receipts: a live claim must match the retained actor, todo revision,
lease id, epoch, expiry, and contiguous authority revision sequence. A partial
or edited v0 head therefore fails as corruption instead of gaining a new store
binding, reusing an epoch, or authorizing an unproved holder.

Delivery boundary, stated explicitly and accepted by the owner on 2026-09-01:
this slice is the RFC's reference implementation with deterministic and
live-example evidence. No LoopX production entry point constructs the executor
yet - the modules are coverage-only in the visible governance ledger. This
acceptance allows the cohesive reference-contract slice to merge after its
correctness, rebase, and review gates pass; it does not promote it to a shipped
capability. A real caller requires the reviewed shared-mode migration,
local-writer fence, authorization publisher, provider binding, projection
flip, rollback, and retention decisions below - not a diagnostic CLI that
creates a second writer. This status section claims proven contracts, not a
shipped production capability.

#### Stage-ladder end-to-end evidence (2026-09-03)

What exists on this branch is one incremental end-to-end "stage ladder" that
exercises every completed stage claim of this RFC through the real
`python -m loopx.cli` and reports a machine-checkable verdict per row:
`loopx/control_plane/testing/authority_e2e_ladder.py` (row registry, runners,
the `loopx_shared_goal_authority_e2e_report_v0` JSON report, exit policy, and
privacy scan), `loopx/control_plane/testing/authority_e2e_fixtures.py` (goal
workspaces, CLI runners, the observation-lock window, candidate read-back), the
read-only TypeScript probe
`tests/control_plane_ts/authority_store_readback_probe.ts`, the pytest
projection `tests/control_plane/test_shared_goal_authority_e2e.py`, and the
entry point `examples/shared-goal-authority-e2e/ladder.py`.

Per stage, this increment implements:

- Stage 0: `s0.file_matrix_twelve_rows` runs the retained live matrix script
  and requires exactly the twelve shared scenario rows to be true on the file
  provider; `s0.nokv_live_matrix` requires the same rows plus
  `restored_lineage_fails_closed` and identical file/NoKV outcomes on a live
  NoKV stack.
- Stage 1: `s1.cli_document_decodes_through_ts_store` writes three
  observations through the product CLI (`todo add`, `task-lease acquire`,
  `todo update`) and reads them back through `FileAuthorityStore` with
  `loadAuthority`, paged `scanCommitted`, and `readReceipt`: cursor `3`, the
  three operation ids in order, and the first receipt found.
- Stage 2A: `s2a.nokv_live_qualification` runs the merged live qualification
  probe (`examples/nokv-authority-store/live-qualification.ts --execute-live`)
  against an existing workbench with a fresh tenant/goal pair and requires
  `ok=true`, the single-node store-conformance scope, every check passed, NoKV
  SDK `0.11.0` / API `1`, and no promotion or availability claim.
- Stage 2B: `s2b.postgresql_conformance_live` runs the PostgreSQL integration
  test file under node's TAP reporter and requires at least nine passes, zero
  failures, and zero skips.
- Stage 2C observation foundation: seven `s2c1.*` rows port the local-shadow CLI
  E2E and migration assertions and pin the single-lineage guarantee. The configure round trip previews, enables,
  reads back, and disables the observer; every writer family (handoff-mode,
  todo add/update/complete/supersede/capture-followups/archive-completed,
  task-lease acquire/renew/transfer) captures with
  `primary_writeback_preserved`, `provider_to_local_writes=false`, and
  `candidate_read_for_decision=false`, while an idempotent re-acquire does not
  observe; default-off goals stay isolated; candidate failure preserves the
  primary commit; a POSIX SIGKILL in the crash gap loses only that
  observation; a `--runtime-root` override that differs from
  `common_runtime_root` keeps todo add, task-lease acquire, todo update,
  follow-up capture, and a leased completion in one store identity while the
  registry root gains neither a candidate lineage nor lease state; and
  `migrate-state` seeds a fresh lineage without legacy bytes.

Live rows are environment-gated (`LOOPX_TEST_POSTGRES_URL`;
`NOKV_COORDINATION_LIVE=1` plus the `NOKV_*` stack variables;
`LOOPX_NOKV_AUTHORITY_LIVE=1` plus the `LOOPX_NOKV_AUTHORITY_*` inputs).
Without a stack they report `unverified`, and the ladder exits non-zero unless
`--allow-unverified` is passed; an unverified row is never counted as green.
A pending row is an unmet obligation as well: selecting one exits non-zero
unless `--allow-pending` is passed, so a report cannot read as green while it
executed nothing.
The report binds the LoopX commit, tree dirtiness, probe digests, and hashed
connection facts, and its privacy scan turns any leak of a temporary root,
home directory, connection URL, or configuration path into
`fail/privacy_violation`; a leak confined to the bindings block is redacted
and still fails the run through `summary.privacy_violations`, which no flag
relaxes.

Delivery boundary: test-only. No production entry point constructs any store;
the ladder adds no product path and reads the candidate only through the
retained TypeScript store. The Stage 2C parity half
(`s2c2.*`: outbox entries, idempotent drain, SIGKILL before and during drain,
rollback with pending entries, parity equal and divergent,
migration seed-and-drain, growth measurement) are declared as pending rows,
not claimed. This subsection records executable evidence for the stages above;
it does not promote any provider or complete the Stage 2C promotion.

### 11.3 Remaining qualification and promotion plan

#### P0: contract and deterministic proof

- this ownership matrix and explicit shared-mode boundary;
- deterministic `loopx_command_v0` normalization and request digest;
- the `claim_work` authority transition over explicitly bootstrapped todos;
- one-head state-plus-receipt CAS;
- target/precondition-scoped conflicts and internal CAS rebase after unrelated
  head advances;
- deterministic and NoKV provider candidates behind the same seam;
- A/B/A, identity-mismatch, crash-window, eligibility, privacy, and no-GC
  checks within the stated evidence boundary.

#### Later runtime promotion and reviewed slices

- the LoopX-owned TypeScript transaction/store boundary and file-provider
  conformance described in Section 6.2;
- NoKV qualification and the remaining PostgreSQL service, failure, and
  promotion holds behind that boundary;
- one-way shadow parity, the one-Goal/two-Agent TEST ONLY canary, and a
  single-source authority flip with no long-lived dual-write or dual-master;
- an explicit shared-mode migration and rollback/export operation, local
  writer fencing, provider binding, a production authorization-projection
  publisher, and provider-first status/completion projections;
- transfer and restricted delegated assignment;
- delivery/wake integration through Agent IM;
- independent run-history synchronization and artifact storage;
- distributed quota reservation/accounting;
- provider promotion, authentication, service recovery, HA, and multi-tenancy;
- receipt retention or segmentation beyond `retain_all_v0`.

#### TypeScript-first burden-reduction order

Prefer preparatory TypeScript work when it removes authority that the next
shared-authority stage would otherwise have to migrate under provider pressure.
The order is deliberately narrow:

1. characterize the caller-observable Python behavior and illegal transitions;
2. move one already-shipped ownership transaction at a time into the existing
   TypeScript boundary, starting with atomic claim-plus-lease, followed by
   completion-plus-successor and the remaining lease lifecycle decisions;
3. qualify that exact transaction against file, NoKV, and a real isolated
   PostgreSQL server before changing provider selection;
4. only then advance binding, migration, canary, and production promotion.

This is not permission for a broad framework rewrite. A preparatory refactor
belongs in this sequence only when the next RFC stage consumes it directly, it
removes duplicate decision authority, and caller-visible parity plus rollback
remain reviewable in the same bounded slice.

## 12. What the Owner Still Needs to Decide

1. Should the next runtime slice first close renew/release/reclaim and stale
   fencing, or qualify that lifecycle together with atomic
   complete-with-successor? *Proposed answer (Stage 3 slice): together,
   sequenced internally - the lifecycle verbs land first in the command
   surface and completion reuses their fence machinery unchanged; the
   completed record must satisfy the local durable-completion projection
   seam, which is already the reviewed contract on the local side.*
2. Which compact project-registry authorization fields form the versioned
   authority input, and who may publish a new authorization projection?
3. What is the reviewed rollback/export procedure after the first shared-mode
   write?
4. Which provider and deployment qualify for the first bounded shared-mode
   canary? Provider selection does not change the authority contract.
5. Before production use, what retention and capacity policy replaces or
   operationalizes `retain_all_v0` without losing historical proof?
6. Does the Stage 4 canary require Host lease liveness before admission, or
   is that a Stage 5 promotion hold? Section 11 asks the canary to observe
   that no external effect is duplicated, but a Host whose runtime exceeds the
   lease TTL can keep producing effects after another Agent reclaims the Todo,
   and a settlement rejected afterwards cannot undo them. The review of #3820
   treated this as a Stage 4 precondition; the RFC must say which mechanism
   is required and where: renewing the lease while the Host runs plus
   cancelling the Host when the fence is lost, an effect-owning fenced commit
   inside the recoverable protocol, or a hard Host duration bound below the
   TTL. *Proposed answer: any canary that runs a real Host must renew during
   Host execution and cancel on fence loss, and its acceptance must include
   the long-Host expiry/reclaim negative test; a bounded fake Host is not
   evidence for this row.*
7. How is the canary's authority provider bound to a Goal? A CLI argument
   that names an arbitrary guard command is a test-harness convenience, not a
   product authority selector. *Proposed answer: the binding is a
   goal-level registry record published by the same owner as the
   authorization projection in question 2, naming the provider kind, the
   store identity or lineage, and an explicit TEST ONLY canary marker; a Goal
   without that marker cannot be admitted by a shared-authority guard, and
   the runtime resolves the provider from the record rather than from argv.*
8. Which head shape does promotion commit, and which fields does the aggregate
   own? `main` now defines `loopx_todo_canonical_read_record_v0` as a versioned,
   complete Todo read-record manifest and makes the TypeScript projection
   reject an upsert that omits fields already present on the stored record.
   *Proposed answer: the promoted head stores the complete normalized Todo and
   lease records, flattened enough for a provider-independent readback. Every
   field that has legally entered a canonical record remains present, including
   `updated_at`, routing, capability, decision, dependency, resume, monitor,
   completion, note/evidence, and archival fields. Omission is never a delete;
   mutation must clear a field explicitly under its schema rule. A new field
   must enter the versioned manifest before qualification, otherwise promotion
   fails closed. "Complete" does not mean copying raw Markdown, host-local
   paths, credentials, the whole registry, or data owned by another ledger.*

   *A later field reduction is a governed schema change even when the field is
   stored but has no known runtime reader. Its PR must include a field inventory,
   producer/reader/writer and static-reference research, historical and external
   compatibility findings, migration and rollback, and proof that behavior is
   preserved. The maintainer must approve the named removal explicitly in the
   RFC decision log or PR review; absence of a discovered consumer is not
   approval.*
9. Does v0 promotion cover only `hard_lease` goals? *Proposed answer: yes. A
   `legacy` or `soft_claim` goal first switches mode under the Appendix B
   quiescence rule; promotion never changes the mode implicitly.*
10. After the provider-first read flip, Markdown and lease files are
    projections and the kernel forbids fallback to them. Which data belongs in
    the head, and how are compatibility views rendered? *Proposed answer:
    every field in the canonical Todo/lease manifests, including monitor,
    dependency, resume, decision, completion, text, note, evidence references,
    and any feedback field admitted by the manifest, persists in the head. A
    transaction-bound projection
    outbox only renders Markdown and lease-file compatibility views; it is not
    a second persistence path for omitted authority fields. Readers compare the
    projection watermark with the head revision and replay the outbox when
    behind. Rendering lag may make a view stale, but must not change a decision.*
11. What declares a promoted goal, and who may write that declaration? The
    merged TypeScript-owned file fence is the first local implementation,
    bound to a fence id, source version, and qualified shadow revision; current
    Todo and task-lease writers check it under their mutation locks. *Proposed
    answer: define one provider-neutral authority binding containing provider
    profile, store identity and lineage, schema manifest, `promoted_at`,
    promotion operation id, source digest, and optional `rolled_back_from`.
    Only the promotion orchestrator and rollback operation may change it. The
    file profile realizes the binding with the durable local fence and registry
    discovery copy; NoKV and PostgreSQL must realize the same logical fence,
    CAS/transaction precondition, and readback receipt in their qualified store
    contract. A provider-specific path or table name is not part of the
    authority protocol. `configure-goal` refuses to edit the binding and
    bootstrap refuses a promoted goal. An endpoint that cannot validate the
    active binding fails closed rather than writing a legacy projection.*
12. Which retention, fast-path, and capacity rules gate promotion, and may a
    retained transaction replace its projection with a digest? *Proposed
    answer: the logical contract is common to file, NoKV, and PostgreSQL: the
    latest complete head, ordered cursor, original operation receipt, segment
    or row-chain integrity, deterministic scan, and recovery readback remain
    available under a declared retention version. A digest may replace an old
    transaction's duplicated projection only when the complete canonical head
    and every field required by replay, audit, parity, and migration remain
    reconstructable and the conformance matrix proves equivalence. Physical
    policy is provider-specific: Section 7.2 prefers an embedded transactional
    local store with segmented files as a comparison candidate; NoKV needs a
    qualified document/segment strategy, and PostgreSQL needs append rows with
    reviewed indexing/partitioning. Section 7.2 also owns the minimum ten-day
    qualification gate; the earlier file-v0 proof is insufficient. Each profile declares measured limits
    and fails closed with `store_capacity_exhausted`; one file-size constant is
    not a cross-provider contract. Host renewals remain authority transactions
    because their rate drives every profile's retention envelope.*
13. What happens to the Python reference executor (`executor.py`,
    `file_provider.py`, `head.py`, `goal_state_shadow.py`)? *Proposed answer:
    keep it coverage-only until the kernel's mutation path is routed from the
    CLI, port its scenario batteries to TypeScript tests, then delete it in
    the promotion PR; two local aggregate formats cannot both be canonical.
    Flipping the file profile's `qualification_holds` to `[]` and its `stage`
    literal happens only inside that PR.*
14. `main` now carries two default-off shadow lineages for the same writers:
    the observation capture of #3818 (`coordination.authority_shadow`,
    `authority-shadow/file/<goal>`, projection v0) and the runtime shadow
    (`coordination.runtime_shadow`, `authority-shadow/file-v0`, projection v0
    with `inspect`, `qualify`, `bootstrap`, `rollback`, and `read-candidate`).
    Both re-sample the source after the primary commit, so both share the
    concurrent-writer and commit-to-dispatch loss windows that the review of
    #3818 named. Which lineage is Stage 2C's, and what closes those windows?
    *Proposed answer: the runtime shadow is the lineage, because the parity
    report, bootstrap, quarantine rollback, read shape, and promotion kernel
    already bind to it. The transaction-bound outbox of the parity half
    (prepared entry inside the writer's own lock, committed marker after the
    primary write, bounded drain with `operation_id = entry id`) becomes the
    durable capture that feeds `coordination.runtime_shadow.commit`, and the
    #3818 observation path retires once that capture is wired. The RFC must
    not keep two shadow record formats.*

---

## Appendix A: What This Evidence Proves

The reference provider and probes live in
`examples/nokv-shadow-provider/`,
with a companion
[`evidence document`](./shared-goal-authority-state-provider-v0-evidence.zh-CN.md).
The deterministic candidate in this PR proves the claim/receipt core plus the
Stage 3 reference lifecycle: same-CAS state plus receipt, competing claims,
A/B/A original-receipt replay, renew/release/expired reclaim, stale-fence
writeback rejection, atomic completion/continuation, request-digest mismatch,
clock boundaries, lineage binding, and distinct version domains. The stated
single-node live scope additionally qualifies file/NoKV parity, restart receipt
replay, and a real restore-lineage fence. It does not implement or qualify a
production authorization-projection publisher, receipt-preserving compaction,
default-mode parity, product shared-mode migration/promotion, service recovery,
or HA. Passing
`python3 examples/nokv-shadow-provider/probes.py contract` is therefore not a
claim that the complete P0 acceptance gate above passes. Historical latency or
fault results are informative only; they are not a durability, recovery, HA,
or production qualification claim.

The additional TEST ONLY Stage 2A probe in
`examples/nokv-authority-store/` opens three independent SDK helper processes
and checks fresh create, exact generation update, reconciliation after an
applied CAS response is deliberately lost, a one-winner/two-contender CAS,
winner/loser receipt behavior, and fresh-process receipt/history readback. Its
executable fixes argv to one absolute Python executable, the interpreter
isolation flag `-I`, and this checkout's reviewed helper, so `PYTHONPATH`
cannot substitute the `nokv` module; the helper fails closed unless the SDK
reports NoKV 0.11.0 and Python API 1, and the report repeats those two
admission constants rather than server-observed values. It validates read metadata against the current workbench
incarnation and validates publish responses against the requested workbench,
path, operation, revision, and generation. The AuthorityStore accepts even a
successful publish response only after a fresh read proves the exact persisted
transaction under the current workbench incarnation. This closes false success
at the LoopX boundary, but NoKV's current Python API does not atomically bind an
expected workspace incarnation into `publish_bytes`; preventing a write after a
concurrent remove/recreate remains an explicit provider-contract hold.
Only a successful live JSON report is evidence for that single-node Stage 2A
store-conformance run; deterministic tests are sequence tests only. This
LoopX-only candidate changes neither NoKV source nor its workbench/artifact data
model, and it does not prove runtime shadow parity, a multi-Agent canary,
authority-source promotion, HA, restart recovery, capacity, or production
routing.

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
resetting it to `legacy`. The Stage 2 provider contract and file backend have
since landed, and the first Stage 2C post-commit runtime shadow now exists
behind an explicit default-off configuration. Local canonical promotion has
not started: the runtime still never reads the shadow for decisions, and the
migration, rollback, parity, read-flip, and legacy-writer fencing gates above
remain open.

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


## Appendix C: Stage 2C Promotion Design (proposal, 2026-09-04)

This appendix resolves questions 8 to 14 as a provider-neutral promotion
contract. It distinguishes logical authority semantics from each provider's
physical retention strategy. Nothing below is implemented by this document;
the unresolved gates remain prerequisites for a real promotion.

### Decision summary

1. Stage 2C promotes one canonical coordination head, not a file format.
   File, NoKV, and PostgreSQL implement the same `AuthorityStore` semantics.
2. Canonical Todo and lease state is complete by default. Promotion may not
   reduce it to the fields currently used by a known consumer.
3. Any later field removal requires field-level compatibility research,
   migration and rollback evidence, and explicit maintainer approval.
4. Markdown and lease files become rendered projections after read flip. They
   never supply missing decision state.
5. Retention is logically common and physically provider-specific. A provider
   may segment or normalize history without changing head/readback semantics.

### Shipped on `main` (2026-09-03)

- The default-off runtime shadow: one `AuthorityStore` transaction per
  committed Todo or task-lease mutation, keyed by the mutation's rollout event
  id and `updated_at`, with receipt replay, content-drift rejection,
  ambiguous-commit reconciliation, and read-back.
- `loopx coordination-shadow inspect | qualify | read-candidate | bootstrap |
  rollback`: typed one-point parity (`missing | matched | drifted` with both
  digests), a coverage-based sustained parity report, the provider-first read
  shape (still `decision_read_from_shadow=false`), the bootstrap of an empty
  shadow from the legacy projection, and a revision-fenced quarantine rollback
  of a pre-promotion lineage.
- The cutover kernel: a pure reducer from mutation to projection, event, and
  receipt; `coordination.local_authority.promote` requiring a qualified shadow
  at one exact revision and digest plus an independently persisted legacy
  writer fence bound to that revision; provider-first `mutate` and
  `todo_read` that never fall back to Markdown.
- The fence integration: every Python Todo mutation and every native task-lease
  acquire, renew, transfer, and release checks the durable fence while holding
  its own lock; an absent fence costs no runtime call; a present, unreadable,
  or invalid fence fails closed.
- The complete Todo read model: `loopx_todo_canonical_read_record_v0` publishes
  a versioned field manifest, and the TypeScript projection rejects a
  replacement that drops fields already present on a stored record.

### Normative promotion contract

The promotion state machine is independent of provider kind:

1. Resolve a reviewed goal-level authority binding to a qualified
   `AuthorityStore` profile and exact store lineage.
2. Under the legacy Todo and lease locks, verify sustained parity at one source
   revision, projection digest, field-manifest version, and provider cursor.
3. Engage the provider profile's durable writer fence, then commit the complete
   canonical head and promotion receipt with a compare-and-set or transaction
   precondition. A file marker, NoKV document identity, or PostgreSQL row/table
   layout is an implementation detail.
4. Read back the binding, head, receipt, cursor, manifest, and digest before
   allowing provider-first decisions. Any mismatch fails closed.
5. Render compatibility projections through the transaction-bound outbox. A
   stale projection is repaired from the head; it is never consulted to fill a
   missing canonical field.

The canonical head preserves every field legally present in the normalized
Todo and lease records. The field manifest is part of qualification and parity.
An upsert carries a complete replacement or uses a typed patch whose clear
operations are explicit. Unknown additions fail closed until the manifest is
versioned. A removal proposal must enumerate the field and all producers,
readers, writers, persisted fixtures, static references, historical versions,
and known external consumers; state the migration, downgrade, rollback, and
semantic-equivalence argument; and receive explicit maintainer approval. A
field is not removable merely because code search found no current reader.

This completeness boundary excludes raw Markdown formatting, credentials,
host-local paths, whole registry documents, raw evidence bodies, and state
owned by quota, run-history, settlement, inbox, scheduler, or another ledger.
Those remain references governed by their own contracts.

The common retention contract keeps the latest complete head, ordered cursor,
original operation receipt, integrity chain, deterministic scan, and recovery
readback. Physical profiles may differ:

- **file:** create-only sealed history segments plus a bounded head document;
- **NoKV:** a qualified document/segment layout with lineage-bound conditional
  publication and recovery readback;
- **PostgreSQL:** transactionally appended history/receipt rows plus a current
  head, with reviewed indexes, partitioning, RLS, and tenant context.

All profiles expose the same logical result and field manifest. Each publishes
measured capacity limits and returns typed `store_capacity_exhausted` before a
write that cannot preserve the contract.

### Still missing before promotion

- Provider-first CLI routing and the lock-owning promotion orchestrator (the
  kernel's own next slice): take the Todo and lease legacy locks, require
  `qualify` to be `qualified` at the current revision and digest, engage the
  fence, run `promote`, render the projections, and record the declaration of
  question 11; refuse a rerun whose source digest changed unless the abandoned
  store is explicitly discarded.
- Full transaction-capture qualification (question 14): Todo add, update,
  complete, supersede, and archive plus native lease acquire, renew, transfer,
  release, auto-acquire, and fence-close now emit prepared/committed outbox
  entries around their primary write. The bounded drain commits complete
  versioned records into the existing `coordination.runtime_shadow` file-v0
  lineage; it does not create the former second local-shadow candidate. Before
  promotion, add sustained mixed-writer parity runs, event-only Todo coverage,
  and the selected provider profile's recovery/capacity evidence.
- Completion of the compatibility projection outbox and conformance rows for
  file, NoKV, and PostgreSQL. The first provider-first slice now reuses the
  committed authority journal as the durable intent for native Todo create,
  claim, and narrow update, then renders native active/archive records into
  machine-owned Markdown regions with idempotent replay. Remaining native Todo
  mutations, lease-file projection, backlog/status readback, and provider-
  neutral authority binding still need the same contract. Providers do not
  promote together; each profile must pass it before it is eligible.
- Retention, fast path, and measured capacity for the selected first-promotion
  profile; the reference executor's removal and status flips (question 13).
- Post-promotion rollback: the shipped rollback quarantines a pre-promotion
  lineage. After the first authority write (`authority_revision > 0`) the
  return path is question 3's reviewed fenced export: quiescence, an empty
  projection outbox, export of the head into the Markdown coordination fields
  and the final lease records, an `equal` verify, removal of the watermark and
  fence, and retirement of the lineage; never automatic, never during an
  active lease.

### Growth is a promotion prerequisite

The minimum supported horizon is ten elapsed days. The workload, corrected
whole-history cost model, local storage direction and qualification budgets are
owned by [Section 7.2](#72-ten-day-goals-local-storage-qualification-target-proposal).
File-v0 remains a bounded conformance/bootstrap profile; neither successful
bootstrap nor a short microbenchmark proves long-goal capacity. First local
promotion requires a qualified bounded-history hot path and elapsed-time soak,
without waiting for PostgreSQL service readiness.

### Todo domain / projection decision (2026-09-05)

The long-term boundary is semantic, not based on where a field was first
parsed. `TodoDomainRecord` owns identity, role, status, text, task semantics,
and **`archive_state: active | archive`**. Archival is independent of completion:
the handoff gate and succession-tracked completion checks exclude archived
records. `deferred` is a status, not an archive state. A renderer must not invent
or change that decision by moving a heading.

`TodoProjectionMetadata` owns `source_section` and optional `index`. The Markdown
adapter derives them when rendering native records. An imported section name
may be retained as compatibility provenance, but cannot become required input
to provider-origin creation. One caveat is load-bearing: legacy `index` also
breaks priority ties in the consumer pipeline. A migration must preserve that
ordering through an explicit domain ordering policy or qualified compatibility
provenance; deleting it and silently switching to identity order is not parity.
Fresh native collections use deterministic Todo-id order before the existing
priority projection; their display indexes are allocated by the adapter.

The implementation checkpoint introduces the separate
`loopx_todo_domain_read_record_v0` manifest and `todo_domain_record_v0` items.
The existing reducer, file-store mutation path, and collection reader validate
this shape without Markdown fields. Tests cover native insertion, archival,
exact replay, reopen, and rejection of renderer metadata and incomplete
replacement. This proves the storage/read boundary, not an authorized CLI
creation or complete lifecycle transaction.

Compatibility is explicit: `loopx_todo_canonical_read_record_v0` and its
`todo_item_v0` records are unchanged. Existing heads, receipts, field manifests,
and default Markdown capture retain every legal v0 field. No implicit conversion
occurs in reads, mutations, or startup. Mixed native/legacy records under one
manifest fail closed. Downgrading a native head to an older binary fails closed
on its unknown manifest; rollback requires the reviewed export below, not
merely installing the old binary. Historical operation receipts are never
rewritten by a schema upgrade.

Field inventory for this split: `active_state_todo_parser.py` produces section
and index metadata and maps section membership into archival state;
`todo_summary.py`, `handoff_gate.py`, and resume/continuation projections consume
archival state; `todos/projection.py` consumes index for ordering. Existing
runtime-shadow fixtures and the legacy TS insert fixture retain v0 provenance.
The native contract adds an alternative; it removes no persisted v0 field and
makes no claim that unknown external consumers have migrated. A future v0 import
must inventory those consumers and prove render/export/rollback and selection
parity at the same revision before changing a binding or manifest. Questions 8
and 10's completeness rule applies to domain facts and retained compatibility
provenance; it does not require native callers to manufacture Markdown addresses.

### Next delivery and parallel provider work

The immediate kernel sequence is: (1) a real provider-first Todo lifecycle caller
with the replaced Python decisions removed; (2) explicit v0 import plus sustained
consumer/capture/recovery qualification; (3) reviewed promotion with fenced
export and cleanup. Each slice must prove an end-to-end transaction, not merely
another schema identifier consolidation. Native contract acceptance alone is
not permission to bypass any promotion hold.

The first replacement-first `claim` slice routes both the default Markdown
writer and the promoted provider transaction through one TypeScript decision.
Python's default path retains only locked commit and existing projection-
compatibility duties. This closes duplicate claim policy; it neither promotes
Markdown to authority nor replaces the remaining unified
create/update/complete/archive transactions and projection outbox.

The following `create` slice routes promoted `todo add` through a native
provider transaction. The legacy CLI surface remains, but after argument
validation it performs one typed crossing; TypeScript owns semantic duplicate
resolution, actor/owner eligibility, CAS, replay receipts, and the projection
outbox mutation. A deleted Markdown state file stays absent in real subprocess
CLI preview and apply tests. This removes Markdown commit authority for create
on promoted goals without claiming that update/complete/archive are ready for
live promotion; those commands remain fenced until their own transaction
types land behind the same runtime boundary.

Use file-v0 for bounded conformance and import rehearsal only. Start the
Section 7.2 embedded-store slice alongside the provider-first Todo caller; both
converge before long-goal local qualification and promotion. PostgreSQL
service/deployment work remains parallel; it is not a local-promotion dependency. NoKV remains independently gated by its own lineage and recovery
qualification. The shared authority owns decisions and receipts; providers own
durable CAS/transactions, never a second Todo state machine.

### Parallel delivery plan

| Lane | May start | Scope and exit condition | Dependency |
| --- | --- | --- | --- |
| L. Long-goal local persistence | Now, alongside the Todo caller | Section 7.2: embedded-store candidate, bounded live head and receipt index, historical scan compatibility, crash-safe checkpoints, real CLI readback, accelerated capacity and >=10-day soak. | Reuses the TS authority owner; required for local long-goal promotion, independent of P. |
| P. PostgreSQL provider plane | Now, from current `main` | Keep the existing `AuthorityStore` contract; finish schema migration/install ownership, authenticated service and tenant authorization, restore-incarnation rotation, pool/cancellation/failover behavior, and reviewed indexes, partitioning, retention, and measured capacity. Live PostgreSQL conformance remains mandatory. | Does not depend on #3870 and must not stack on its branch. This lane alone creates no runtime caller or promotion claim. |
| C. Canonical transaction capture | In implementation, based on #3870 | Transaction-bound outbox capture now targets the one `coordination.runtime_shadow` lineage and retains complete versioned Todo/lease records. Finish sustained mixed-writer parity, explicit-clear/omission coverage, and event-only Todo recovery evidence. | Can run in parallel with P, but both C and the selected provider profile must finish before parity or promotion integration. |
| I. Binding and qualification integration | After C and the selected profile's qualification | Bind one exact provider lineage, field manifest, source revision, digest, and cursor; qualify explicit v0 import, ordering/archival/consumer parity, and recovery/capacity without consulting legacy state for missing fields. | Long-goal local integration requires L and does not wait for P. PostgreSQL joins only when its own P holds pass. |
| F. Promotion and cleanup | After I and explicit maintainer approval | Complete provider-first CLI routing, the lock-owning promotion orchestrator, compatibility projection outbox, post-promotion fenced export/rollback, then delete duplicate reference aggregates and flip the reviewed stage/hold declarations. | Each profile must pass C, I, and its own provider qualification; long-goal local promotion additionally requires L, and PostgreSQL requires P. |
