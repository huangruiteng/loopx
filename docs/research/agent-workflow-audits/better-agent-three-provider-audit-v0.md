# Better Agent Three-Provider Workflow Audit v0

## Decision

**Run provider-specific inspection in parallel, but serialize any shared-tree
implementation behind a parent review gate. Stop a specialist lane when it no
longer contributes provider-specific evidence.**

This is a metadata-only audit design for the synthetic workflow proposed in
[LoopX issue #670](https://github.com/huangruiteng/loopx/issues/670). It is not
evidence that a Better Agent run has already exhibited duplicate work, stale
state, or conflicting changes.

## Workflow

[Better Agent](https://github.com/ofekron/better-agent) describes one local
workspace for Claude, Codex, and Gemini, with session forking, delegation,
parallel execution, and headless SDK/CLI control. Its maintainer proposed this
synthetic task:

1. three specialist lanes inspect Codex, Claude, and Gemini integrations;
2. each lane returns findings and validation evidence;
3. a parent reconciles the findings into one shared implementation;
4. the parent decides whether to keep, stop, or serialize lanes.

The audit unit is one parent task plus its three child lanes. Prompts, message
bodies, credentials, raw logs, and private session content are out of scope.

## Minimum Metadata

| Field | Purpose |
| --- | --- |
| `parent_run_id` and `lane_id` | Keep lineage explicit without copying session content. |
| `provider` and `scope_summary` | Show the intended unique contribution of each lane. |
| `base_revision` and `observed_at` | Detect findings produced from stale shared-tree state. |
| `inspected_paths` | Measure exploration overlap without retaining file contents. |
| `proposed_write_scopes` | Detect implementation conflicts before writes begin. |
| `validation_receipts` | Distinguish checked evidence from narrative success claims. |
| `finding_keys` and `recommendation` | Compare conclusions without storing full transcripts. |
| `parent_decision` and `decision_reason_codes` | Preserve the keep, stop, or serialize outcome. |

Path lists should be repository-relative. Validation receipts should retain a
command or check identifier, status, revision, and timestamp, but not raw
output.

## Signals

The following signals are derived from metadata. They are not inferred from
agent confidence or a generic "success" label.

| Signal | Evidence | Interpretation |
| --- | --- | --- |
| Duplicate exploration | High overlap in `inspected_paths` and `finding_keys`, with no provider-specific result. | One lane may be redundant. |
| Stale shared state | A lane's `base_revision` differs from the parent integration revision when its recommendation is reviewed. | Rebase or re-inspect before accepting the result. |
| Conflicting implementation | Overlapping `proposed_write_scopes` plus incompatible recommendations. | Do not let lanes write concurrently. |
| Superficial success | Lane-local checks pass, but no parent integration receipt covers the combined change. | The workflow is not yet validated. |
| Unique provider value | A lane finds a provider-specific contract, failure, or check that no other lane covers. | Keep that lane active. |

Overlap is a review cue, not an automatic stop. Two lanes may inspect the same
adapter for different provider contracts. The parent must record whether the
second lane added unique evidence.

## Decision Rules

### Keep all lanes

Keep the three inspection lanes while each has a distinct provider scope and
continues to add unique findings or validation receipts. Shared read-only
inspection is allowed even when paths overlap.

### Stop a redundant lane

Stop a lane when all of these are true:

- its current scope substantially overlaps another live lane;
- it has not added a unique finding or validation receipt since the last
  parent review;
- stopping it does not remove provider-specific coverage.

Record the stopped lane, retained lane, overlap evidence, and parent decision.
Do not estimate saved cost unless lane duration or token/cost metadata exists.

### Serialize implementation

Serialize the final implementation when any lane proposes overlapping write
scopes, works from a stale base revision, or recommends a change incompatible
with another lane. The parent first selects one implementation todo and one
base revision. Other lanes become reviewers or validators; they do not keep
writing the same shared tree.

The implementation may return to parallel work only after write scopes are
disjoint and the parent records the split.

## Trust Ranking

1. **High:** repository revisions, relative path sets, todo or lease identity,
   commit receipts, and reproducible validation status.
2. **Medium:** compact finding keys and parent-authored reason codes linked to
   high-trust evidence.
3. **Low:** free-form recommendations, self-reported completion, or lane-local
   success without an integration receipt.

The parent decision should cite high-trust evidence for any stop or merge
choice. Low-trust evidence can trigger review, but cannot close it.

## Measures

Use measured counters only:

- parent review latency from last lane receipt to recorded decision;
- number of lanes stopped for proven redundancy;
- duplicate inspected-path count at the parent review point;
- overlapping write-scope conflicts caught before implementation;
- integration validation reruns before one accepted receipt;
- lane minutes or provider cost avoided after an explicit stop decision, when
  those values are available.

The audit is useful if it shortens a real parent decision or catches one
conflict before duplicated implementation. It must not claim savings from this
synthetic design alone.

## Fit And Kill Criteria

Proceed with one synthetic replay if Better Agent can export the minimum
metadata above without prompts, raw logs, credentials, or private session
content. The replay passes when it produces one explainable parent decision and
one integration validation receipt.

Stop this audit route if the workflow cannot expose base revisions, relative
path scopes, and validation receipts independently of private traces. Also stop
if all three lanes are only a narrative scenario and no bounded synthetic run
can produce observable metadata.

## Next Bounded Step

Run one synthetic provider-parity task on a disposable public fixture. Capture
only the minimum metadata, then apply the rules above. The parent should choose
exactly one outcome:

- keep all inspection lanes because each added unique provider evidence;
- stop at least one redundant lane with measured overlap evidence; or
- serialize implementation behind one shared-state review gate.

No issue comment, repository mutation in Better Agent, production access, or
private material is required for that replay.
