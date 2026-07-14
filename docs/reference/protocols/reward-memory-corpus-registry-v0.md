# Reward Memory Corpus Registry v0

Stage 1 turns the five Stage-0 reward-memory classes into a provider-neutral
corpus inventory and health contract. The registry is a stateless read model;
it does not mirror provider content, become a second memory store, or grant an
agent permission to write or apply recalled material.

```bash
loopx reward-memory corpus-registry --format json
loopx reward-memory health-check --case wrong-project --format json
```

## Corpus declaration

Every corpus declares:

- `corpus_id`, Stage-0 `class_id`, `provider_id`, and `owner_ref`;
- the canonical `source_of_truth`;
- separate read and write authority;
- workspace, project, module surface, and optional user, peer, or session scope;
- freshness mode and optional source revision or maximum age;
- active, superseded, or retired lifecycle plus lineage;
- whether an index, result readback, and application receipt are required;
- writeback triggers, closure policy, and retirement authority;
- privacy visibility and the invariant that raw content is absent.

The reference registry covers all five classes through seven corpus families:

| Corpus family | Class | Source and lifecycle |
| --- | --- | --- |
| `run_reward_overlays` | `run_bound_reward` | LoopX human-reward event ledger; append-only exact goal/run overlay. |
| `authority_policy_sources` | `hard_policy` | Explicit or verified-contributor-derived policy content, always bound to independently verified user/repository/operator authority scope. |
| `scoped_preferences` | `soft_preference` | Provider-managed, explicitly reviewed feedback for module-owned surfaces. |
| `execution_trajectories` | `procedural_experience` | Revision-stamped execution evidence. |
| `distilled_experiences` | `procedural_experience` | Reviewed and supersedable procedural or architectural learning. |
| `session_working_memory` | `working_context` | Session/archive-revision-bound continuation context. |
| `fresh_execution_context` | `working_context` | Current registry, todo, checkout, and bounded tool observation. |

These reference entries are declarative families, not claims that a live
provider or corpus is configured. A live module builds a `registered` packet
from its provider-owned inventory. The existing semantic-preference provider
inventory can be bridged without exposing its raw scope URI; the generic
registry retains only a digest and the explicit project and surface scope.

## Authority and maintenance

Read and write authority remain separate. A module-scoped read does not grant a
provider write, a provider-managed write does not grant repository publication,
and neither grants patch authority. Corpus maintenance follows these rules:

1. inventory is owned by the provider or canonical source owner;
2. writes use only the declared write authority;
3. source revision, archive revision, or freshness window is verified before use;
4. superseded and retired corpora remain in compact lineage but stop influencing recall;
5. project or surface mismatch fails closed;
6. retirement keeps a compact reason, never raw memory content.

Policy content may be derived from a verified owner or core contributor's
rewards, preferences, current-artifact-verified experience, selections, and
accepted/rejected outcomes. The registry records this as a maintenance trigger
only after actor identity and repository/action scope are independently
verified; inference cannot create a new write, publish, production, cross-user,
or cross-repository authority scope, and cannot fabricate the current state of
a concrete gate. Confidence is intentionally absent from the health promotion
path because it cannot widen authority.

## Health states

`reward_memory_corpus_health_v0` keeps inventory, retrieval, readback, and use
as distinct observations. The classifier applies this precedence:

| State | Meaning |
| --- | --- |
| `wrong_project` | The requested project differs from the corpus scope. |
| `wrong_surface` | The consuming module surface is not registered. |
| `unavailable` | The provider cannot be reached or the declared corpus is absent. |
| `empty` | The corpus exists and is readable but contains no records. |
| `stale` | Lifecycle, source revision, archive revision, or freshness evidence is not current. |
| `index_unavailable` | A required derived index is absent even though the corpus exists. |
| `retrieval_failed` | The scoped query failed or has not run. |
| `readback_unverified` | Retrieval returned but the selected result was not read back. |
| `retrieval_verified` | A current in-scope result was read back but has no application receipt. |
| `applied_verified` | A verified result also has a compact application receipt. |

The output always preserves the individual pipeline fields:

- `provider_available`;
- `corpus_present` and `record_count`;
- `index_required` and `index_present`;
- `retrieval_query_succeeded`;
- `result_readback_verified`;
- `memory_applied_with_receipt`.

An empty corpus is therefore not reported as unavailable. An existing index is
not proof that the content corpus exists. Retrieval success is not proof that a
result was expanded and verified, and verified readback is not proof that the
memory influenced an artifact.

Contradictory observations fail validation: application requires readback,
readback requires retrieval, and retrieval requires an available present
corpus. A healthy result can make memory eligible for advisory use, but still
returns `memory_patch_authority=false` and
`external_write_authorized=false`.

## OpenViking alignment

For OpenViking, AGFS content remains the source of truth and the vector index
is a derived retrieval reference. Preferences map to scoped preferences,
trajectories and experiences map to the two procedural corpus families, and a
completed Working Memory archive maps to session working context. Cases remain
training and evaluation fixtures and are not registered as executable memory.

The `fresh_execution_context` corpus family is an inventory view over LoopX's
already complete registry, active-state, todo/quota, checkout, and bounded tool
observations. Stage 2 does not add another context store or retrieval path.

Account, user, peer, session, project, surface, and repository revision remain
independent scope dimensions. In particular, a project-peer preference corpus
cannot be reused for another project or surface merely because the provider
returned a high-scoring match.

OpenViking's default type-quota recall currently allows an experience corpus to
exist while the experiences quota is zero. The registry therefore never
derives retrieval health from corpus or index presence.

## Stage boundary

Stage 1 implements corpus declarations, the semantic-preference inventory
bridge, maintenance invariants, and deterministic health classification. It
does not perform provider writes, persist a second registry, read raw memory,
distill candidates, enable cross-module recall, or promote a release.

Stage 2 owns one thin candidate and activation-decision seam. It may derive
policy content from verified contributor signals but does not create authority,
add a second store or scheduler, perform provider writes, or enable automatic
recall. Issue Fix consumes the same generic seam rather than a parallel design.
Stage 3 owns reasoning-mediated cross-module recall and application receipts;
deterministic code remains limited to scope, authority, privacy, freshness, and
conflict guards. Stage 4 owns evaluation and the release gate; Stage 5 owns
bounded dogfood and operator edit or retirement controls.
