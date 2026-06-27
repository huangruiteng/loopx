# 0627: Overnight PR Batch With Reviewable Control

## Summary

LoopX produced an overnight burst of public repository progress without turning
the project into an unreadable pile of agent output. In the ten-hour public Git
window from `2026-06-27 01:29 +08:00` to `2026-06-27 11:29 +08:00`, the public
repository advanced by 22 merged commits touching 60 files, with 6695 insertions
and 223 deletions.

This case is useful because the signal is PR-shaped and reviewable. The work
landed as small slices across docs, state projection, issue-fix workflow,
event-sourced state, benchmark launch contracts, status/quota smokes, and
release/runtime guardrails. LoopX did not make a single giant change that a
maintainer had to trust blindly.

The public case deliberately uses merged Git history as the evidence floor. The
operator-side note also tracked a larger contemporaneous PR queue, but this
page only claims what the public repository can support.

## Public Repository Signal

The evidence window is anchored to public Git history and can be reproduced
locally:

```bash
git log --since="2026-06-27T01:29:00+08:00" \
  --until="2026-06-27T11:29:00+08:00" --oneline

git log --since="2026-06-27T01:29:00+08:00" \
  --until="2026-06-27T11:29:00+08:00" --numstat
```

| Signal | Value |
| --- | --- |
| Public evidence window | 2026-06-27 01:29 +08:00 to 2026-06-27 11:29 +08:00 |
| Merged commits in window | 22 |
| Unique files touched | 60 |
| Public insertions / deletions | 6695 / 223 |
| Commit messages with explicit PR numbers | 10 |
| Evidence floor | Public Git history only |

Representative merged slices in the window included:

- issue-fix workflow planning and command-pack guidance;
- event-sourced LoopX state contracts, API, compaction, and downstream read
  path checks;
- Terminal-Bench and SkillsBench launch or prerequisite contracts;
- status/quota performance budget and projection smokes;
- rollout-state documentation and README workflow refinement;
- agent-scope wait scheduler progression.

## LoopX Behavior

The product behavior was not "make more commits." The useful behavior was that
high-throughput work stayed bounded and reviewable:

- each slice remained small enough to review as a PR or PR-sized commit;
- public docs, examples, and runtime code moved together when the contract
  changed;
- focused smokes validated reusable control-plane behavior instead of
  preserving raw run traces;
- self-merge stayed limited to narrow validated changes;
- broader review gates and handoffs remained visible instead of being hidden
  behind the throughput number;
- public/private boundary checks kept internal screenshots, local state, raw
  logs, and private planning out of the repository.

## User-Facing Value

For an operator, this case shows a different shape of agent productivity:
overnight progress can be high-throughput without becoming high-risk. The user
can wake up to a batch of merged, reviewable public slices, while the control
plane still records what changed, which validations ran, which gates remained,
and which evidence is safe to publish.

For an agent-platform developer, the reusable pattern is a PR-scale work loop:
LoopX keeps each lane tied to todo ownership, validation, review policy, and
public evidence, so a long-running agent team can move quickly without relying
on chat memory or private screenshots.

## Evidence Boundary

This case intentionally excludes private workspace state, internal documents,
screenshots, raw chats, local paths, raw benchmark logs, credentials, and any
unpublished operator notes. The public evidence floor is Git history and the
public repository surfaces it changed.

The 22-commit window is not a universal productivity benchmark. It is a
showcase of reviewable control-plane throughput in one public repository at one
point in time. Future versions can strengthen the case by linking each public
PR number to its validation evidence and review outcome.

## Public Evidence Sequence

1. A long-running LoopX project enters an overnight autonomous work window.
2. Many small slices land across runtime, docs, benchmark contracts, smokes, and
   state projection.
3. LoopX keeps each slice tied to todo ownership, validation, and review policy.
4. The operator sees public Git evidence instead of raw agent logs.
5. The evidence boundary keeps private screenshots and internal planning out of
   the showcase.
