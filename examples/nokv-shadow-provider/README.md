# NoKV canonical-coordination provider reference

This directory contains the small, reviewable NoKV reference for
[RFC: LoopX shared control-plane authority and pluggable state providers v0](../../docs/architecture/rfcs/shared-goal-authority-state-provider-v0.md).
It is a contract example, not a shipped LoopX runtime integration or a
production deployment claim.

## Scope

The reference stores one per-goal **canonical coordination aggregate** and
exercises the Stage 3 lifecycle: `claim_work`, `renew_work`, `release_work`,
expired-lease `reclaim_work`, stale-fence rejection, and atomic completion with
continuation/successors. The aggregate carries the current authority revision,
claim/lease/fence state, store-lineage binding, and replayable receipt index.
It remains a coverage-only reference and does not migrate the current LoopX
runtime or promote this provider to the product source of truth.

The following remain outside this head:

- run artifacts and run-history ledgers;
- status and attention projections or caches;
- quota policy, accounting, and enforcement ledgers;
- host-local routes, scheduler state, locks, and runtime bindings;
- raw evidence, transcripts, credentials, and local absolute paths; and
- Agent IM delivery, wake-up, presence, and offline queues.

Those surfaces have separate ownership and synchronization strategies in the
RFC persistence matrix. A provider does not acquire authority over them merely
because they may be visible from a shared goal.

## Atomic aggregate and receipt replay

The current coordination state and the receipt mapping for a newly accepted
operation are published in the **same head CAS**. The reference does not use a
last-envelope shortcut or a separate `pending -> head -> finalize` receipt
protocol.

The one-head CAS is a physical serialization point, not a goal-wide domain
conflict boundary. Commands name the target todo revision and the compact
authorization, dependency, and gate preconditions they actually observed.
After a CAS miss, the authority reloads and checks those facts again. If an
independent todo advanced the head, it rebases and retries internally; if the
target todo or a named precondition changed, it returns a domain conflict.
`authority_revision` remains a goal-wide commit and audit sequence, not a
required client precondition. In this reference, independent claims use
`write_scopes=[]`; non-empty cross-todo scope overlap is not qualified here.
Internal rebase also assumes the publisher never reuses a target-scoped token
for a different authorization, dependency, or gate snapshot. The deterministic
probe uses static bootstrap inputs and does not qualify that dynamic publisher.

This matters for a historical retry:

1. operation A commits and returns receipt A;
2. operation B advances the goal head;
3. the caller retries A after losing its first response; and
4. the provider returns the original receipt A, field for field, without
   applying A again or moving the current head.

Each receipt-index entry binds the stable operation identity to a digest of the
immutable request. Reusing an operation identity with different immutable
inputs fails closed; it is never classified as an idempotent replay.

The provider contract remains storage-only:

```text
load() -> (aggregate | none, provider_generation)
compare_and_put(expected_provider_generation, aggregate)
    -> applied(provider_generation)
     | conflict(current_provider_generation)
     | ambiguous
     | failed
```

`provider_generation` is the opaque storage CAS token. It is distinct from the
aggregate's `authority_revision` and from each todo's lease epoch; none of these
three version domains is derived from another.

The storage provider deterministically serializes and stores the opaque
aggregate and returns CAS outcomes. The production
`loopx.control_plane.coordination` modules (`head` codec plus the
`CoordinationAuthorityExecutor`) are responsible for request validation,
authority revision, claim/lease transitions, request-digest binding, and the
original domain receipt; this directory no longer carries a second reference
authority. The provider must not inspect an operation receipt or invent
lease, gate, quota, or scheduling decisions.

## Files

- `provider.py`: `NoKVCoordinationProvider`, which maps an opaque per-goal
  aggregate to NoKV path generation CAS. It serializes through the
  production canonical head codec, so the adapter cannot fork the
  digest/parity basis.
- `probes.py`: deterministic contract regressions driven by the production
  executor and head codec; every claim/CAS probe round-trips its persisted
  head through the production `validated_head`. Only the checks in the
  [evidence note](../../docs/architecture/rfcs/shared-goal-authority-state-provider-v0-evidence.zh-CN.md)
  are merge evidence for the revised receipt contract.

## Validation boundary

The provider mapping is pinned to NoKV
[`3d75d96965`](https://github.com/NoKV-Lab/NoKV/commit/3d75d96965) (the
0.11.0 line). At that baseline, the Python `publish_bytes` surface accepts
`expected_generation` for create-only or replacement CAS and exposes optional
publication `operation_id` and `artifact_revision_id` inputs; `read` and
`stat` return the path `generation` the adapter treats as
`provider_generation`. Since NoKV 0.11.0 the SDK raises `FileNotFoundError`
for a missing path and `FileExistsError` for a create-only collision; every
other client failure is a `RuntimeError`. The adapter classifies by
exception class only: `FileNotFoundError` is the one missing signal, and any
other client failure on a read path raises the typed
`ProviderUnavailableError` instead of masquerading as an uninitialized goal
or escaping as a bare `RuntimeError`. Error prose is never a channel - real
non-missing failures carry messages such as `invalid root route: root
placement does not exist` - and pre-0.11 SDKs, which signalled missing with
such prose, cannot route the post-#465 control plane and are outside the
pinned baseline. `contract.nokv_adapter_exception_mapping` pins the
classification offline with fake clients that raise the 0.11.0 exception
classes and the real outage message shapes.

A fresh coordination-provider handle must be admitted with
`open_nokv_coordination_provider(...)`. NoKV performs route admission while
constructing `Client`, before an ordinary provider constructor could classify
the failure. The adapter-owned helper maps that eager failure to the same
`ProviderUnavailableError`, performs no coordination write, and never falls
back to the file provider. The live matrix uses this path for every fresh
provider handle. Separate clients used only to provision test workspaces and
snapshots are outside this provider contract and cannot execute authority
commands. The
`contract.nokv_fresh_client_failure_is_typed` guards both construction-time and
post-construction outages.

The mapping was exercised once by hand against a live NoKV stack at that
pin (etcd, an S3-compatible object store, `nokv serve`, and `nokv-python`
built from the same commit): the adapter verbs and the Section 10 checks
1 to 9 passed with two independent client handles. That run is recorded
here as evidence for the mapping only; it is not part of the merge gate,
and it does not qualify restart, recovery, HA, or performance. SDKs built
before NoKV 0.11.0 cannot decode a 0.11.0 control-plane routing record, so
the earlier `90883d13539e31185f0d78131989fb51912dbd7e` audit baseline is no
longer a usable pin.

The live qualification is scripted and repeatable: `live_e2e.py` runs twelve
shared lifecycle scenarios (including renew, reclaim after grace, stale-fence
rejection, atomic completion/successor, competition, replay, lost response,
retention, and revision advancement) through the production
`CoordinationAuthorityExecutor` against the file-backed control provider and,
when `NOKV_COORDINATION_LIVE=1`, the stack variables and exactly one routing
group are set (`NOKV_SEEDS` for a seed-routed owner, or `NOKV_ETCD` plus
`NOKV_ETCD_PREFIX` for the 0.11.0 etcd control path), this NoKV provider. A
routing kind the installed `nokv` wheel cannot build, or both groups set at
once, is reported as a typed unverified reason, not as a failed row. One NoKV-only row performs a real commit/snapshot/restore and proves
the restored lineage fails closed as `store_lineage_mismatch`. Without a
reachable stack the NoKV rows report unverified and the script stays green, so
it is evidence tooling, not a merge gate.

```bash
python3 examples/nokv-shadow-provider/live_e2e.py
```

Run the merge-relevant deterministic regression from the repository root with:

```bash
python3 examples/nokv-shadow-provider/probes.py contract
```

It must prove all of the following:

- only an explicitly bootstrapped, runnable todo can be claimed;
- A applies, B advances the head, and a reconstructed authority replays A;
- replay returns A's original authority receipt field for field;
- replay leaves the current revision and aggregate unchanged;
- the same operation identity with a different semantic request is rejected;
- transport-only retry metadata does not change operation identity;
- competing claims on the same todo have one winner;
- concurrent claims on independent todos both succeed after internal CAS
  revalidation and rebase, within the reference's empty-write-scope boundary;
- stale target or named preconditions return a domain conflict;
- bounded unrelated contention fails without creating a receipt or pretending
  that the target todo conflicted;
- pre/post-CAS faults and ambiguous results recover success only from a stored
  receipt or a later successful CAS after target revalidation; same-generation
  receipt absence fails unproved;
- the NoKV adapter maps every SDK outcome it can observe (missing head,
  create-only collision, stale generation, pre-publish failure) onto the typed
  provider verbs and never leaks an SDK exception class into the authority;
- a hand-evolved post-completion head read back through the provider byte-CAS
  projects to the same typed continuation outcomes (`successor | no_followup |
  active_goal`) as the LoopX durable-completion seam, failing closed on a
  contradictory record (both `no_followup` and successors), on a dangling
  declared successor, on an explicit `completion_continuation` that
  contradicts the recorded fields, and on a done record that omits its
  explicit continuation, with replay-stable projections.

The durable-completion probes remain the offline read-side comparison. The
Stage 3 focused tests and live matrix qualify the matching atomic completion
write side at the reference boundary.

The nine current result tags are
`contract.bootstrap_and_preconditions`,
`contract.a_success_b_advance_replay_a`, `contract.operation_identity`,
`contract.competing_claims`, `contract.crash_windows_and_ambiguity`,
`contract.version_domains_and_retain_all`,
`contract.nokv_adapter_exception_mapping`,
`contract.durable_completion_projection`, and
`contract.durable_completion_fail_closed`.

`probes.py` deliberately remains offline; use `live_e2e.py` for the real stack.
The reference still does not establish multi-host wake delivery, automatic
provider promotion, HA/failover, receipt compaction or GC, production
performance, a dynamic eligibility-projection publisher, non-empty write-scope
overlap enforcement, or a full LoopX state migration. The NoKV storage-plane
issues linked from the RFC remain production-canary holds; a green ordered
single-node exercise does not erase them.
