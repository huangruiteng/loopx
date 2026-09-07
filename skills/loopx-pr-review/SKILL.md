---
name: loopx-pr-review
description: Use for `/loopx-pr-review` or evidence-backed PR queue review. Run `loopx pr-review` first, execute the capability-owned review plan for each selected exact head, then publish full bilingual PR reviews (complete Chinese five-block review plus one concise English verdict) that match the verified findings. Use `loopx-pr-merge` for approval or merge actions.
---

# LoopX PR Review

This skill is a thin host adapter. The built-in `pull-request-review`
capability owns review depth, evidence requirements, completeness, and verdict
policy through the CLI packet. Do not copy those rules into this skill or
replace them with a host-specific checklist.

## Route

Use this skill for `/loopx-pr-review`, explicit PR reviews, or review queues by
state or time window. Route approval, merge, self-merge, and admin bypass to
`loopx-pr-merge` after the evidence review is complete.

Run the LoopX CLI before ad hoc GitHub reads:

```bash
loopx --format json pr-review --state all
```

Translate only explicit filters:

- `--repo owner/repo`
- `--since ISO`
- `--state open|merged|all`
- `--limit N`

Words such as `today`, `open`, or `merged` are filters, not permission to
return a table only. Stats-only output requires an explicit opt-out such as
`只统计`, `只列出`, `stats only`, or `不要 review`.

## Preserve The Packet

Save the full first JSON packet before printing a compact projection. Keep all
paths named by `agent_response_contract.required_packet_fields_to_preserve`,
especially:

- `agent_response_contract.review_execution_contract`
- `result_completeness`
- `review_groups`
- `pull_requests[].review_plan`
- `pull_requests[].review_template`
- `pull_requests[].evidence_commands`

Do not pipe the only copy through `jq`. When an exhaustive request has
`result_completeness.complete=false`, rerun with its `recommended_limit` before
reviewing.

## Execute One Review Plan

Review `review_groups.unmerged` first, then `review_groups.merged`. For every
selected PR:

1. Record the packet's exact head. Start with the capability's
   `review_execution_contract.decision_procedure`, including on re-review;
   then run `evidence_commands` and relevant repository-native validation.
2. Fill `review_plan.result_template` from the shared execution contract;
   preserve missing evidence as `unverified`. Execute its repository-reuse,
   default-off, authority and real-path counterfactual requirements rather than
   repeating them as prose. Never infer `verified` from metadata or CI.
3. Apply `completion_gate` literally. Save the filled result and check it before
   publication:

   ```bash
   loopx --format json pr-review --check-result review-result.json --packet review-packet.json
   ```

   Fix contradictory verdicts, not evidence labels to obtain a pass. This local
   check cannot verify evidence truth, architecture judgment, or remote freshness.
   Missing material evidence needs a concrete hold/request-changes explanation,
   not an invented bug or approval inherited from the previous round.
4. Render the verified result through `review_template`. The five sections are
   output structure, while the execution contract is the evidence authority.
5. Re-read the remote head immediately before verdict and publication. Restart
   the evidence pass if it changed.

Each PR gets an independent evidence pass and standalone card; a queue table is
only a preface. Finish fewer complete cards rather than metadata-only reviews.

## Publish And Read Back

For an open PR, publish validated actionable findings by default unless the
user explicitly requested local-only/dry-run output or the finding contains
private or security-sensitive material.

- Remaining blocker: formal `REQUEST_CHANGES`; for an author-owned PR, use a
  `COMMENTED` review titled `Request changes conclusion (author-owned PR; GitHub blocks formal self-review)`.
- Non-blocking finding with no blockers: formal `APPROVE`, not a bare comment.
  When the GitHub account is the PR author and GitHub rejects self-approval,
  record the same approval conclusion as a `COMMENTED` review
  titled `Approval conclusion (author-owned PR; GitHub blocks formal self-approval)`
  so the verdict remains public and machine-visible.
- Non-blocking finding with only P2 suggestions: still `APPROVE`; keep the P2
  items in the review body rather than downgrading the verdict.
- Merged PR: publish a post-merge audit comment only for a new actionable
  finding; avoid duplicating an equivalent exact-head result.

Build public text from the exact reviewed head. Remove local paths, private
context, raw logs, credentials, and internal-only links. Read the published
review back, verify its state and rendered body, and return its URL. Merge
still routes through `loopx-pr-merge`; an `APPROVE` is not merge authority.
Do not leave a public blocker only in chat.

## Full PR Review And Bilingual Format

Every review must cover the whole PR, not only the top finding. Read the full
diff/checks, then explain motivation, architecture, changed files/symbols,
positive and negative paths, risk across the whole diff, validation, and
overall judgment. A findings-only or blocker-only body is incomplete.

Publish two artifacts:

1. **详细中文评审** - a standalone Chinese full-PR review with the exact head
   and five sections: `动机`, `改动思路`, `具体改动`, `对主干的风险`,
   `我的整体评价`. Cover every changed surface and key symbols, not just the
   main finding.
2. **英文简短结论** - start with exactly `English verdict:` and include the
   verdict, exact head, key finding, and validation.

Do not publish before the Chinese section covers the entire PR. Read both
artifacts back.

## Full PR Interpretation Depth

Use the packet's `repository_reuse`, `symbol_map`, `walkthroughs`, and
`validation_matrix` evidence across the whole PR, including unchanged callers
and sibling implementations. Walk one positive path to the observable result.
Walk one negative path and explain its failure owner. Render the verified
evidence in the five sections; do not maintain a second checklist here.

A review that only repeats the PR body, only discusses one blocker, or omits
whole files/modules is incomplete and must be reworked.

## Example / Walkthrough / Smoke-Only PRs

When the review plan marks `smoke_or_example_only`, the `durable_smoke_value`
evidence is mandatory before approval. The essence is real, durable value to
the repository and product: running, deterministic, and public-safe are
necessary but not enough.

1. Name the shipped behavior, boundary, or maintenance cost this artifact
   guards. "Demonstrates something that already works" is not durable value.
2. Scan existing coverage (`rg -l '<behavior|module>' examples tests`) and the
   same-author batch (`gh pr list ... --author <author>` / `gh search prs`);
   flag same-shape batches opened within minutes as PR farming.
3. Apply the repo smoke policy: thin + durable, guard shipped behavior or a
   real boundary, compress rather than append, consolidate same-shape
   walkthroughs into one PR or focused tests.
4. Verdict: `REQUEST_CHANGES` for duplicative, oversized, or value-less
   scaffolding; name the consolidation or thinning repair in the body.
5. Repeat offenders: after a REQUEST_CHANGES warning, further low-value
   same-shape PRs from the same author escalate to a contribution-restriction
   recommendation (owner blocks the account from further PR submissions); the
   warning must name this consequence.

## Autonomous Queue

For recurring observation, keep one ignored checkpoint and use the same capability:

```bash
loopx --format json pr-review --repo owner/repo --state open \
  --autonomous-observation --observation-state-file .local/pr-review-monitor.json \
  [--projected-exact-head NUMBER@HEAD_OID] [--handled-exact-head NUMBER@HEAD_OID]
```

Treat `candidate` as a preview, not a durable projection. Follow this order: durable
Todo target-key readback -> `--projected-exact-head` -> exact-head review/comment
readback -> `--handled-exact-head`. Never send the projection ACK before the Todo
exists, or the handled ACK before readback at that head. Observation states remain literal;
the checkpoint grants no authority. Stateless callers may use `--previous-observation-json` instead.

## Failure

If `loopx pr-review` is unavailable, repair the LoopX install or use the
intended checked-out CLI. Do not reconstruct the queue manually and call it a
successful `/loopx-pr-review` run.
