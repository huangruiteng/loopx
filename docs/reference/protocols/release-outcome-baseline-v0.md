# Release Outcome Baseline v0

`release_outcome_baseline_v0` is the review boundary between fast control-plane
qualification and low-frequency long-running outcome evidence. It compares a
stable baseline and candidate under matched task semantics, runner protocol,
verifier contract, and budget. It never promotes a release automatically.

## Validation Layers

LoopX uses three complementary layers:

1. deterministic fixtures and catalog canaries run on normal pull requests;
2. low-frequency paired model-behavior qualification checks whether an agent
   interprets two control-plane projections equivalently;
3. release outcome baselines compare completed long-running attempts on a small
   representative case set.

The third layer measures what happened, not only whether a packet looked
equivalent. It stays outside ordinary PR smoke because real tasks and model
calls are slower, cost-bearing, and may depend on gated environments.

## Pair Manifest

`release_outcome_pair_manifest_v0` contains:

- public-safe `baseline_ref` and `candidate_ref` identifiers;
- an explicit evidence policy;
- paired compact `benchmark_result_v0` rows.

Every pair has a stable `case_id` and `repeat_index`. The producer must confirm
all four parity checks:

- same task semantics;
- same runner protocol;
- same verifier contract;
- same budget.

Each result must already be an exact compact `benchmark_result_v0`. Unknown
fields fail closed instead of being silently copied into the receipt. The
result must explicitly report terminal state, verifier pass/fail, erroneous
write count, human intervention count, stop-policy correctness, wall time, and
cost. At least two distinct cases and two repetitions per case are required;
the manifest may demand stronger coverage.

## Metrics And Decisions

The reducer reports both arms and their deltas for:

- completion rate;
- verifier pass rate;
- erroneous writes;
- human interventions;
- correct stop-policy rate;
- mean wall time;
- mean cost.

It produces one of three review decisions:

- `insufficient_evidence`: the representative-case or repetition floor is not
  met;
- `hold_regression`: a correctness metric regressed or the declared time/cost
  ratio was exceeded;
- `owner_review_required`: the evidence floor is met and no declared regression
  is present.

`owner_review_required` is not release approval. The receipt always sets
`automatic_release_promotion_allowed=false`. A maintainer still reviews case
representativeness, failure attribution, and any qualitative behavior that the
compact metrics cannot express.

## CLI

The CLI is read-only:

```bash
loopx --format json benchmark release-outcome-baseline \
  --manifest-json release-outcome-pairs.json
```

Add `--require-owner-review-ready` when a scheduled qualification job should
return non-zero for insufficient evidence or a regression. Without that flag,
the command remains advisory and does not slow ordinary iteration.

The command does not read raw task text, trajectories, or verifier output. It
does not invoke a model, execute a benchmark, mutate a release, or persist local
paths. Real runners remain responsible for producing compact result rows under
their own authorization and privacy boundaries.
