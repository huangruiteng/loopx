# RFC: Shared Goal Alignment and Governed Amendment Protocol (v0)

- Status: Draft; under maintainer review
- Tracking issue: [#3836](https://github.com/huangruiteng/loopx/issues/3836)
- Date: 2026-09-02
- Last updated: 2026-09-05
- Scope: peer Agents collaborating around one shared Goal while preserving
  canonical intent, per-Agent execution frontiers, claim/lease ownership, and
  auditable replan/amendment decisions
- Related contracts:
  [Goal Vision and Replan](../../reference/protocols/goal-vision-replan-contract-v0.md),
  [Shared Control-Plane Authority and Pluggable State Providers](./shared-goal-authority-state-provider-v0.md),
  and [Decision Context](../../reference/protocols/decision-context-architecture-v0.md)
- Language note: the
  [Chinese version](./shared-goal-alignment-and-governed-amendment-v0.zh-CN.md)
  and this English version are semantic mirrors. A difference between them is
  a defect.

---

## 1. Summary and decision

LoopX will distinguish four kinds of state that must not collapse into one
mutable plan:

1. a **canonical shared Goal intent envelope**;
2. a **shared eligible work graph**;
3. one **per-Agent frontier** for each registered peer; and
4. **proposal and receipt records** for governed shared amendments.

An Agent may correct its own frontier while remaining inside canonical intent.
It may propose a shared amendment when evidence invalidates shared assumptions.
The proposal does not change the Goal, block unrelated work, or grant the
proposer unilateral commit authority. A shared amendment becomes effective
only after LoopX's `GoalAmendmentAuthority` validates it against the pre-authorized
policy and exact base revision, commits it with compare-and-set (CAS), and
produces a durable receipt. Every Agent then rebinds its frontier to the new
canonical revision.

The normal path is automated. It does not require every peer to vote or a human
to approve routine Goal evolution. `peer_v1` describes equal execution rank,
not universal authority to escape the root user intent or acquire new
permissions. Goal creation freezes a `root_intent` and an amendment-policy
envelope. Inside that envelope, policy checks and, for higher-risk classes, an
independent verifier Agent authorize automatic commit. Outside it, the old Goal
remains effective and the proposal is rejected or structurally blocked; human
escalation occurs only when the Goal explicitly configured it.

```text
canonical shared Goal intent envelope
  (objective, non-goals, acceptance, permissions, stop conditions, revision)
                 |
                 v
shared eligible work graph
                 |
        +--------+--------+
        |                 |
        v                 v
per-Agent frontier A   per-Agent frontier B
        |                 |
claim + lease/fence    claim + lease/fence
        |                 |
bounded evidence       bounded evidence
        +--------+--------+
                 |
       lane replan or amendment proposal
                 |
     automated policy + optional verifier
                 |
       base-revision CAS commit
                 |
 committed shared amendment + receipt
                 |
       every frontier rebases or gates
```

## 2. Problem and current boundary

LoopX already coordinates execution usefully:

- registered peer identities and Agent-scoped Todo lanes;
- visible/selectable unclaimed Todos with claim-before-work guidance;
- soft claims plus hard lease/fence ownership;
- per-Agent vision and checkpoint state;
- typed autonomous-replan obligations and settlement;
- action-scoped cross-owner Todo lifecycle grants; and
- provider-neutral coordination CAS and receipt foundations.

[#3693](https://github.com/huangruiteng/loopx/pull/3693) is a positive bounded
fix in this layer. It prevents shared `Next Action` prose from shadowing an
exact settlement-bound or current-Agent Todo. It does not define shared Goal
alignment or shared semantic amendment authority.

The missing seam appears when multiple Agents independently discover that the
shared plan or acceptance boundary is wrong. Per-Agent vision can remain
internally consistent while the combined work no longer proves the original
Goal. Conversely, letting every Agent rewrite shared prose turns the latest
writer into accidental authority.

No type system can prove that arbitrary natural-language changes preserve the
user's intent. LoopX can instead make silent reinterpretation impossible: an
amendment must name what is retained, changed, and stopped; cite evidence; bind
the exact base revision and digest; pass an explicit authority policy; and
leave a recoverable receipt.

## 3. State partition and invariants

### 3.1 Canonical intent envelope

`shared_goal_intent_v0` contains:

- `goal_id`, `goal_revision`, and `intent_digest`;
- objective and non-goals;
- acceptance conditions;
- permission/write scope;
- stop and terminal conditions; and
- the root intent that Agents cannot amend;
- the authority policy that governs each amendment class; and
- the configured disposition for out-of-policy proposals (`reject`, `block`,
  or explicit `human_escalation`).

This is semantic authority, not a status projection. `Next Action`, Agent
vision, chat messages, scheduler hints, and provider heads cannot overwrite it.

### 3.2 Shared work graph

The shared work graph contains Todos, dependencies, eligibility, blocking
gates, and lifecycle state. It describes candidate work, not who may currently
execute it. Work-graph edits must remain traceable to the canonical intent
revision they are intended to advance.

### 3.3 Per-Agent frontier

Each registered Agent receives a bounded `shared_goal_alignment_v0` projection:

- canonical Goal revision/digest;
- that Agent's frontier and `based_on_goal_revision`;
- its claims and lease/fence facts;
- eligible unclaimed work;
- open lane replan or shared amendment obligations; and
- conflicts or stale-basis facts.

An Agent may replan its own route without a shared amendment when the change
stays within current objective, non-goals, acceptance, permissions, and stop
conditions and does not mutate another Agent's claimed work.

### 3.4 Proposals and receipts

Proposals are advisory, durable inputs. Receipts prove canonical transitions.
Neither is a substitute for the other. A pending or approved proposal has no
effect until a successful commit receipt names the new Goal revision.

### 3.5 Host-session locators and advisory context

A task deep link can make entry into this protocol precise without becoming a
fifth kind of shared state. For Codex, `codex://threads/<thread-id>` identifies
a local chat. LoopX may resolve that locator through the current project
registry and bind the source session to an existing Agent and Goal identity.
The returned provider-neutral `host-session:codex:<thread-id>` scope can then
select that session in an explicitly enabled Decision Context provider.

This is an optional, transient **advisory context input**. It remains outside
`shared_goal_intent_v0`, `goal_amendment_proposal_v0`,
`goal_amendment_receipt_v0`, and the provider CAS head. It helps peers:

- identify the exact task in which a gap or evidence pointer was discovered;
- recall a bounded set of source-task messages while reviewing current facts;
- route an amendment proposal to an independent verifier or affected peer; and
- return to the relevant task after commit for receipt readback and frontier
  reconciliation.

```text
host task deep link -> project-local binding -> normalized host-session scope
        | explicitly configured, read-only ContextProvider
        v
local-private transient recall -> verify against current authority sources
        | explicit promotion to durable typed evidence
        | base Goal revision + intent digest
        v
governed amendment proposal -> authority decision -> canonical receipt
```

The ordering is normative. A deep link is not an `evidence_ref`, a recalled
message is not an amendment decision, and the extension lifecycle revision is
not `base_goal_revision`, `authority_revision`, `provider_generation`, or
`lease_epoch`. Any session-derived conclusion needed by the amendment must
first be checked against current authority and promoted to the existing Todo
evidence, Agent evidence log, or registered material owner. The proposal then
cites those durable typed references and independently binds the current Goal
revision and intent digest.

The locator also grants no read access, permission, claim, lease, lifecycle
authority, verifier independence, or amendment commit authority. If the link is
unresolvable, inaccessible, or its extension is disabled or unavailable, only
the optional context-enrichment step fails open; the canonical Goal and
unrelated work remain valid. Decision Context records the provider degradation
and continues from available authority sources. Receipt recovery uses `operation_id`
and `readReceipt`, so losing a host session cannot make a committed amendment
unrecoverable. A cross-Goal rendezvous may help two peers coordinate, but each
Goal still requires its own proposal, policy decision, CAS commit, and receipt.

Core parses host-specific deep-link syntax exactly once and exposes only the
normalized scope to providers. The optional `loopx-obelisk` extension maps that
scope to Obelisk's public read-only query interface. It does not read Obelisk's
storage schema, build or attune the index, or open, resume, or message a live
task. Other harnesses can implement the same Decision Context provider protocol
without adding host syntax or transcript storage to the Goal authority.

## 4. Authority matrix

### 4.1 What `GoalAmendmentAuthority` means

`GoalAmendmentAuthority` is not a person, a leader Agent, a model, or a storage
service. It is LoopX's single typed write boundary for canonical Goal
amendments. A concrete implementation is expected to separate:

```text
proposal + current Goal + policy + lease impact + optional verifier decision
                                  |
                                  v
                 GoalAmendmentAuthority.decide()
                       reject | needs_rebase | commit
                                  |
                                  v
                  provider CAS + canonical receipt
```

The decision reducer enforces deterministic policy, identities, digests,
revisions, and impact rules. An optional verifier Agent supplies a typed input
for semantic questions, but cannot commit. The transaction executor persists an
accepted decision through the provider-neutral store, but cannot widen it.
Calling this boundary an authority means all canonical writers must pass
through it; it does not mean that one privileged Agent decides for its peers.

### 4.2 Amendment classes

| Amendment class | Example | Proposal authority | Automated commit rule | Default effect while pending |
| --- | --- | --- | --- | --- |
| `lane_route` | reorder one Agent's unclaimed local steps | owning Agent | deterministic lane policy | none outside that lane |
| `shared_work_graph` | add a Todo or dependency that preserves intent | registered Agent | policy validation plus impact check | unrelated work continues |
| `shared_acceptance` | refine an acceptance condition or non-goal inside root intent | registered Agent | policy validation plus independent verifier Agent | affected acceptance path is gated |
| `protected_authority` | acquire new permission or escape root intent | registered Agent | never auto-commit unless the immutable envelope already delegates the exact class | affected work fails closed |

`GoalAmendmentAuthority` is the normal commit boundary. A verifier Agent returns a
typed, evidence-bound decision; it does not become a durable leader and cannot
edit the proposal it verifies. Proposer and verifier identities must differ for
classes whose policy requires independence. Deterministic checks remain the
first gate; model judgment cannot override permissions, scope, stop conditions,
or a stale base.

Being a scheduler, Supervisor, latest writer, lease holder, or provider
operator does not grant semantic commit authority. Out-of-policy proposals are
rejected or left structurally blocked while the old Goal continues. They ask a
human only when `human_escalation` was explicitly enabled, rather than turning
every Goal change into an approval queue.

## 5. Amendment lifecycle: how a proposal becomes effective

```text
draft -> submitted -> admitted -> policy_check -> verified -> committing
  |          |            |             |             |
  +--------> rejected <----+-------------+-------------+
                             stale/conflict -> needs_rebase

committing --CAS success--> committed + receipt -> frontier reconciliation
          \--unknown------> ambiguous -> readReceipt/reconcile
          \--CAS conflict-> needs_rebase
```

The effective path is:

1. **Propose.** Any authorized proposer submits
   `goal_amendment_proposal_v0`, including the base revision/digest, amendment
   class, retained/changed/stopped intent, evidence references, affected Todos,
   and linked replan obligation. An optional host-session rendezvous may help
   discover or review the gap, but only promoted durable evidence enters the
   proposal.
2. **Admit.** LoopX validates schema, actor identity, bounded evidence pointers,
   amendment class, and impact scope. A host locator cannot prove actor identity
   or count as evidence. Admission does not approve or apply the proposal.
3. **Policy decision and optional verification.** LoopX evaluates deterministic
   invariants and the pre-authorized amendment envelope. A higher-risk but
   in-envelope class may invoke an independent verifier Agent that returns a
   typed decision bound to the exact proposal digest. The policy may reject or
   request rebase. A verifier decision cannot be reused for edited content.
4. **Impact decision.** Before commit, the authority decides how in-flight
   claimed/leased Todos are handled: unaffected, allowed to finish under the
   old revision, explicitly cancelled with a new fence epoch, or blocked by
   policy. A semantic amendment cannot silently invalidate work already
   authorized by a lease.
5. **Commit.** The `GoalAmendmentAuthority` transaction submits the policy-authorized digest
   with an `operation_id`, expected `base_goal_revision`, and
   `base_intent_digest`. It revalidates policy and performs one CAS. A stale
   base fails closed. Routine in-envelope amendments do not wait for a human.
6. **Receipt.** The same transaction records the proposal digest, actor,
   authority source, old/new revisions, retained/changed/stopped delta,
   evidence references, affected Todos, lease disposition, and exact replan
   obligation settlement.
7. **Reconcile.** Projections rotate to the new revision. Every Agent either
   rebinds its frontier, opens a lane replan, or is gated if its current work is
   incompatible. Old-revision semantic writes are rejected.

Only step 5 makes the amendment canonical. Step 6 makes that fact recoverable
when a response is lost; step 7 makes it operational for all peers.

## 6. Proposed schemas

Illustrative `goal_amendment_proposal_v0`:

```json
{
  "schema_version": "goal_amendment_proposal_v0",
  "proposal_id": "gap_...",
  "goal_id": "goal-1",
  "proposer_agent_id": "agent-a",
  "amendment_class": "shared_acceptance",
  "base_goal_revision": 17,
  "base_intent_digest": "sha256:...",
  "retained": ["original outcome remains unchanged"],
  "changed": ["acceptance now requires the recovered receipt"],
  "stopped": [],
  "evidence_refs": ["evidence:..."],
  "affected_todo_ids": ["todo-a", "todo-b"],
  "replan_obligation_id": "replan:..."
}
```

Illustrative `goal_amendment_receipt_v0` adds:

```json
{
  "schema_version": "goal_amendment_receipt_v0",
  "operation_id": "op_...",
  "proposal_id": "gap_...",
  "proposal_digest": "sha256:...",
  "decision": "committed",
  "authority_actor_id": "goal-amendment-authority",
  "authority_source": "goal_amendment_policy_v0",
  "verifier_decision_digest": "sha256:...",
  "previous_goal_revision": 17,
  "new_goal_revision": 18,
  "new_intent_digest": "sha256:...",
  "lease_dispositions": [],
  "settled_replan_obligation_id": "replan:..."
}
```

The read-only `shared_goal_alignment_v0` projection must identify pending,
approved, conflicting, and committed proposals without treating any pre-commit
state as canonical intent.

## 7. Concurrency, recovery, and multi-Agent behavior

Multiple proposals from one base may coexist. Policy/verifier decisions and
commit are bound to the exact proposal digest. Canonical commit is serialized by Goal revision:
after one proposal commits, another proposal from the old base becomes
`needs_rebase`; it is never silently merged or applied last-writer-wins.

Independent lane work continues while a proposal is pending unless a typed
impact gate names that Todo or acceptance path. An Agent may claim eligible
unclaimed work only through the existing atomic claim and, when configured,
lease/fence acquisition. Proposal authorship does not reserve a Todo, and Todo
claim ownership does not authorize a Goal amendment.

If provider commit succeeds but the response is lost, the caller does not
blindly retry with a new operation identity. It calls `readReceipt` using the
same `operation_id`. A found receipt proves the canonical revision. An absent
receipt plus a changed head requires reconciliation; ambiguity is not treated
as failure. Provider-specific file, NoKV, or PostgreSQL behavior remains behind
the provider-neutral authority store contract.

## 8. Replan integration

Replan classifies a discovered gap before choosing a writer:

- a route correction wholly inside canonical intent opens or settles an
  Agent-scoped replan obligation;
- a cross-lane dependency/work-graph gap opens a shared amendment obligation;
- evidence that changes acceptance, non-goals, or the operational objective
  inside the root-intent envelope opens an automatically governed amendment
  obligation; and
- a change outside delegated permissions or root intent is rejected or remains
  structurally blocked under the configured escalation disposition.

Each obligation has a stable id. Proposal ACK alone does not settle it.
Settlement requires either a committed receipt for that exact obligation, a
rejected/no-change decision with a structured rationale accepted by policy, or
a superseding obligation that explicitly preserves the causal chain.

After commit, an Agent whose `based_on_goal_revision` is stale may observe but
cannot make controlled semantic writes until it rebases or receives an explicit
grandfathered-work disposition. This connects shared change to existing
per-Agent Goal Vision without turning one Agent's vision into peer authority.

## 9. Provider and projection boundaries

The `GoalAmendmentAuthority` decides whether a proposal is legal and may commit.
File, NoKV, and PostgreSQL providers persist normalized transactions, CAS
heads, and receipts; they do not interpret Goal prose or choose amendment
policy.

This RFC does not expand the current coordination aggregate in its first
implementation slice. The existing shared-authority RFC continues to own
Todo/claim/lease/receipt persistence. Goal semantic amendment first ships as a
read-only projection and proposal contract. Mapping its commit into a
provider-neutral aggregate requires a separate reviewed transaction boundary.

`Next Action` remains compatibility prose and a read projection. It is never a
claim, lease, Goal amendment, replan settlement, or authority decision.

## 10. Staged delivery

1. **Stage 0 — characterization and RFC.** Record own-lane, unclaimed,
   peer-claimed, replan, concurrent proposal, and in-flight lease scenarios.
2. **Stage 1 — read-only alignment.** Add `shared_goal_alignment_v0` with
   canonical revision binding, per-Agent frontier basis, unclaimed work, and
   drift/conflict facts. An optional Decision Context extension may pair an
   exact host-session scope with bounded advisory recall. No writer changes.
3. **Stage 2 — proposal only.** Validate and retain
   `goal_amendment_proposal_v0`; proposals have no canonical effect.
4. **Stage 3 — one bounded commit class.** Implement governed commit for a
   shared work-graph amendment that preserves root intent, including automated
   policy commit, CAS, receipt, replan settlement, and lease impact handling.
5. **Stage 4 — provider-neutral shadow/parity.** Map the reviewed transaction
   to the file reference provider and optional NoKV/PostgreSQL candidates;
   compare projections and recovery without changing default authority.
6. **Stage 5 — TEST ONLY shared canary.** Exercise two peers, concurrent
   proposals, unclaimed claim, response-loss recovery, stale bases, and
   protected changes before any authority-source promotion.

Acceptance and operational-objective commits are not the first runtime slice.
They require demonstrated need and a separately reviewed automated policy and
verifier contract. Permission expansion or escape from root intent cannot be
auto-committed unless Goal creation explicitly delegated that exact class.

## 11. Validation matrix

At minimum, tests must prove:

- own-lane replan cannot change canonical intent;
- unclaimed work is visible but cannot execute before claim/lease;
- a pending proposal does not affect unrelated peers;
- policy and verifier decisions are bound to the exact proposal digest;
- two conflicting proposals from one base yield at most one canonical commit;
- stale revision/digest commits fail closed;
- response-loss recovery returns the original receipt;
- protected changes cannot be committed by proposer, scheduler, lease holder,
  verifier, or provider operator identity alone;
- routine in-envelope amendments complete without human approval, while an
  out-of-policy proposal never silently expands authority;
- in-flight leased work receives an explicit disposition; and
- all Agent projections rotate or gate after a canonical revision changes;
- a host-task locator resolves only through the current project binding and
  grants no claim, lease, lifecycle, verifier, or amendment authority;
- disabling or removing the advisory provider does not block authority-source
  collection, while amendment submission still independently requires the
  current Goal revision and intent digest.

Existing Goal-amendment and authority-store conformance tests remain the owners
of durable proposal, receipt recovery, and cross-Goal commit isolation. The
optional locator/provider tests must not duplicate those state-machine suites.

## 12. Non-goals

This version does not define automatic voting or consensus, CRDT/offline
multi-writer merge, an omniscient planner, a permanent leader, direct Agent
writes to storage providers, broad migration of LoopX state, or autonomous
escape from the immutable root user intent. Human approval is not a required
step in the normal amendment lifecycle. Host-session locators, deep links, and
transcripts are also not part of the Goal aggregate or a durable evidence store.

The smallest useful outcome is a legible, read-only alignment projection and a
proposal that is visibly non-authoritative. Runtime commit follows only after
that boundary proves useful in real multi-Agent work.
