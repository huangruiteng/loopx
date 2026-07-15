# Release Outcome Baseline v0

`release_outcome_baseline_v0` is the review boundary between fast control-plane
qualification and low-frequency long-running outcome evidence. It compares a
stable baseline and candidate under matched task semantics, runner protocol,
verifier contract, and budget. It never promotes a release automatically.

## Validation Layers

LoopX uses three complementary layers:

1. deterministic fixtures and catalog canaries run on normal pull requests;
2. low-frequency model-behavior qualification checks whether an agent
   interprets the shipped control-plane behavior correctly; sensitive packet
   changes may add a temporary base/candidate differential run;
3. release outcome baselines compare completed long-running attempts on a small
   representative case set.

The third layer measures what happened, not only whether a packet looked
equivalent. It stays outside ordinary PR smoke because real tasks and model
calls are slower, cost-bearing, and may depend on gated environments.

The second layer follows the same CI boundary. Its durable onboarding contract
runs the current actual default path against an independent semantic oracle,
then checks the healthy postcondition and known-bad repair calibration. Live
provider calls are a low-frequency local/manual release gate for sensitive
agent-facing changes, not a required status check on ordinary pull requests.
CI owns deterministic fixtures and catalog canaries; the live gate adds
repeated behavioral evidence when a maintainer is considering promotion.
Provider unavailability yields insufficient qualification evidence, not a
product-code failure.

## Pair Manifest

`release_outcome_pair_manifest_v0` contains:

- `comparison_kind=stable_release_vs_candidate`;
- public-safe `baseline_ref` and `candidate_ref` identifiers;
- an explicit evidence policy;
- paired compact `benchmark_result_v0` rows.

Every pair has a stable `case_id` and `repeat_index`. The producer must confirm
all four parity checks:

- same task semantics;
- same runner protocol;
- same verifier contract;
- same budget.

The baseline and candidate references must be different immutable identities.
Both arms run the same LoopX product mode; only the stable release and candidate
revision differ. Native-agent-versus-LoopX uplift experiments, treatment-arm
comparisons, and two labels pointing to the same revision are rejected. Their
results may remain useful research evidence, but they are not release
qualification evidence.

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

## Staged Terminal-Bench Profile

The first release profile reuses only the three public task identities from the
existing official hard-case selection: `fix-code-vulnerability`,
`modernize-scientific-stack`, and `llm-inference-batching-scheduler`. It does
not reuse that document's native-agent-versus-LoopX arm semantics.

Run `fix-code-vulnerability` first, twice per arm. Expand to the other two cases
only after all four parity declarations are true and the pilot has no runner or
verifier-contract blocker. The final release receipt requires all three cases
with at least two repetitions per stable-release and candidate arm. A blocked
pilot remains `insufficient_evidence`; it does not silently lower the case
floor, replace the task, or block ordinary pull-request iteration.
