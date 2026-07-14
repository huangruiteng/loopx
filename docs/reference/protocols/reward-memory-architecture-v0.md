# Reward Memory Architecture v0

LoopX separates feedback evidence from durable behavior so a useful judgment
does not silently become a permission, policy, or universal personal profile.
This Stage-0 contract defines five memory classes, their precedence and the
pilot/meta delegation boundary. It does not yet implement a corpus registry,
candidate queue, provider write, cross-module recall, evaluation harness, or
rollout.

The machine-readable contract is available through:

```bash
loopx reward-memory architecture --format json
```

## Five first-class classes

| Class | Source and scope | Authority and use | Lifecycle |
| --- | --- | --- | --- |
| `run_bound_reward` | Explicit human judgment attached to one exact goal/run. | Evidence about that outcome only. It cannot alter future behavior until a later candidate-review stage explicitly promotes a distilled item. | Append-only overlay; corrections and revocations append references instead of rewriting the judged run. |
| `hard_policy` | Explicit user boundary, repository policy, operator gate, or authority checkpoint scoped to a project/goal and action/surface. | Deterministic constraint or veto while active and in scope. It is never inferred from reward, preference, recalled experience, or provider `soul`/boundary text without a canonical policy binding. | Active until explicitly superseded, revoked, or expired; temporary policy requires expiry. |
| `soft_preference` | Explicit feedback, selected options, or later reviewed candidates scoped to a workspace/project and module-owned surface. | Advisory ranking or rewrite only. It cannot grant publish, merge, write, credential, or production authority. | Durable only after explicit review; editable, rejectable, supersedable, revocable, and retireable. |
| `procedural_experience` | Revision-stamped trajectories, distilled experiences, maintainer corrections, accepted/rejected changes, and reviewed architectural learning, with repository/module/revision/applicability scope. | Advisory diagnosis, scope, routing, or validation guidance only after current-artifact verification. A training/evaluation case is evidence, not an executable instruction. Retrieval alone has zero patch authority. | Trajectories may be add-only; distilled or architectural experiences are supersedable. New source truth can stale, quarantine, refute, or retire them. |
| `working_context` | Either fresh execution state (`fresh_execution_context`) or a revisioned session-continuation summary (`session_working_memory`). | Supports only the current execution/session continuation. Neither subtype becomes reusable policy or grants action authority. Fresh source-of-truth reads outrank recalled material. | Fresh context expires quickly; a session summary remains bound to its session/archive revision and becomes stale when a newer completed archive exists. |

Every durable record must name `source`, `scope`, `authority`, `confidence`,
`lifecycle_state`, `supersession`, `revocation`, `expiry`, and `privacy` in
addition to the class. Confidence describes evidence quality; it never
increases authority. Confidence is `low`, `medium`, or `high` with a required
basis; source names kind/ref/actor/time, scope names user/workspace,
project/repository, module/surface, and revision/time boundaries. Lifecycle
records state plus supersession, revocation, expiry, and retirement references.
Privacy names visibility, retention class, and whether raw content was captured.

## Precedence and conflicts

The deterministic order is:

1. explicit action authority and privacy boundaries;
2. active in-scope hard policy;
3. fresh working context and current source of truth;
4. current-artifact-verified procedural experience;
5. active in-scope soft preference;
6. run-bound reward as evidence only.

Reject revoked, expired, out-of-scope, or unverified items before ranking.
Within the same authority class, prefer explicit provenance, narrower scope,
then newer source truth. If a same-authority conflict remains unresolved, do
not apply either item. Raw chat, transcripts, tool logs, credentials, and local
paths are not reward-memory records.

## OpenViking alignment

The five classes are provider-neutral, but the Stage-0 boundary was checked
against OpenViking's current public architecture and code:

- OpenViking is a context database, not an action-authority system. AGFS
  content is its source of truth; the vector index stores retrieval references.
- OpenViking `preferences` can supply reviewed `soft_preference` candidates.
  They never become permission.
- OpenViking `trajectories` are add-only operation contracts distilled from one
  execution. OpenViking `experiences` are upserted, executable-looking
  generalizations that may explicitly `supersede` an older experience. Both map
  to advisory `procedural_experience`, subject to current-revision verification.
- OpenViking `cases` explicitly define a task and rubric for training or
  evaluation; they are not experience instructions and cannot be injected as
  policy.
- OpenViking Working Memory is a seven-section archive overview used for
  session continuation. It maps to `working_context/session_working_memory`,
  not long-term policy. LoopX's fresh registry/todo/checkout observations map to
  the separate `fresh_execution_context` subtype.
- OpenViking `soul.md` may contain semantic boundary text, but recalled provider
  content is not a LoopX `hard_policy` unless an explicit user, repository, or
  operator source binds it to action authority.
- Account, user, peer, session, and repository-revision boundaries remain part
  of scope and privacy. A peer label does not grant cross-user or cross-agent
  authority.

Provider health is intentionally decomposed into `corpus_present`,
`index_present`, `retrieval_query_succeeded`, `result_readback_verified`, and
`memory_applied_with_receipt`. These states must not be collapsed. In
particular, the current OpenViking Codex auto-recall path configures the
`experiences` quota to zero, so an experience corpus can exist without being
automatically recalled. Stage 1 owns that inventory and health proof; Stage 0
does not claim it.

Grounding references: OpenViking
[architecture](https://docs.openviking.ai/en/concepts/01-architecture),
[session management](https://docs.openviking.ai/en/concepts/08-session),
[multi-tenant and peer isolation](https://docs.openviking.ai/en/concepts/11-multi-tenant),
and source revision
[`ba46491`](https://github.com/volcengine/OpenViking/tree/ba46491af0a79467ea268ef370e35b68f86abf73).

## Pilot/meta delegation

The pilot may take a fix only when behavior is a confirmed bug, scope is one
bounded surface, the change does not alter a semantic contract or place
product-specific policy in a generic boundary, reproduction and validation are
named, edge-case complexity is low or medium, and all relevant evidence is
present. Meta design review is required for by-design or uncertain semantics,
a semantic-contract change, cross-surface change, generic-boundary leakage, or
high edge-case complexity.

Evidence requirements are relevance-gated instead of using a blanket
"core-component" rule: effect evidence is always required; UX evidence is
required for a user-visible behavior change; performance evidence is required
for a hot-path or storage-behavior change; benchmark evidence is required only
when retrieval or memory quality is claimed. Missing required evidence without
a meta trigger produces `hold_for_evidence`. This allows a bounded bug inside a
core module to remain pilot-sized while still escalating a deceptively small
change that alters a public or storage contract.

This is routing, not cross-agent authority. The meta lane does not edit or
claim the pilot's todos, and the pilot cannot bypass the design gate with a
memory hit.

## PR #3237 regression

[OpenViking PR #3237](https://github.com/volcengine/OpenViking/pull/3237) is the
negative regression. It tried to make generic directory listing reflect
session-specific activity across backend and Web Studio surfaces even though
the maintained directory-mtime behavior was by design. The resulting patch
changed a generic filesystem/session contract for one product-specific edge
case, crossed backend and Web Studio surfaces, and added metadata reads on a
listing/storage path. It lacked product-effect, UX, and performance evidence.
Benchmark evidence is not required by this regression because it made no
retrieval or memory-quality claim.

The stable expectation is `meta_design_gate`, not `pilot_fix`. Meta may narrow
the product behavior to a session-specific presentation boundary or close the
change; a prior memory result cannot authorize the generic-layer patch.

```bash
loopx reward-memory route-check --case pr-3237 --format json
```

## Staged ownership

- Stage 0: this classification, precedence, and delegation contract.
- Stage 1: the implemented provider-neutral
  [corpus registry and health contract](reward-memory-corpus-registry-v0.md),
  including ownership, authority, freshness, retirement, scope isolation, and
  retrieval-health distinctions.
- Stage 2: inspectable candidate distillation and explicit human review.
- Stage 3: opt-in cross-module recall and compact application receipts.
- Stage 4: evaluation harness and release gate.
- Stage 5: bounded cross-module dogfood and operator edit/retire controls.

Later stages must extend this contract rather than collapsing these classes or
turning provider availability into a user gate. Stage 1 remains a stateless
read model and performs no provider or external write.
