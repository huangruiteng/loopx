# SkillsBench Goal Baseline Comparison Incident

Date: 2026-07-11

Audience: LoopX benchmark maintainers, Codex Goal integration owners, reducer
owners, and benchmark evidence reviewers.

## Summary

An early SkillsBench comparison suggested that Codex TUI `/goal` with xhigh
reasoning scored below the bare Codex CLI xhigh baseline. That broad conclusion
was not supported by a matched experiment. The observed aggregate combined
historical runs with different prompt delivery, retry histories, runner
versions, countability rules, and failure-replay selection.

The investigation found multiple benchmark-harness defects that could turn a
valid result into an uncountable failure, import unrelated historical rows, or
attribute a later transport warning over an already completed official score.
After the fixes, one historical Goal zero became a clean official pass without
changing the task prompt or Goal objective. Matched reruns also reproduced
several supposed Goal regressions as equal bare-CLI failures.

One case still showed a matched score gap, but its two routes did not receive
the task with equivalent prompt delivery. A file-objective parity probe was
attempted before assigning that gap to the native `/goal` lifecycle, but the
probe hit a pre-task capacity failure and produced no countable result.

This incident is public-safe. It excludes raw task text, trajectories, verifier
tails, credentials, private launch material, and local artifact paths.

## Baseline Semantics

The bare Codex and native `/goal` arms are product baselines. They are not
case-local LoopX treatment arms. Therefore these observations are expected and
must not be treated as evidence that `/goal` failed to activate:

- no case-local LoopX state;
- no case-local LoopX todo;
- no LoopX quota, status, or spend lifecycle;
- no `app_server_goal_followup` controller rounds;
- no benchmark reward feedback forwarded into LoopX.

Native Goal activation should instead be established from the Codex Goal
lifecycle itself: goal creation or update, active execution, token and elapsed
time tracking, and terminal completion or blocked state.

## Comparison Confounds

The original aggregate was not a causal A/B test:

1. **Prompt delivery differed.** Bare CLI received the task instruction in its
   initial request. TUI `/goal` received a compact stable objective and read the
   full task packet from a workspace file after activation.
2. **Controller behavior differed.** Some bare runs could receive fresh
   scheduled `codex exec` follow-ups. Native `/goal` used its own lifecycle.
3. **Historical retries differed.** The canonical Goal ledger retained the
   best countable result after failed-case repair reruns, while historical CLI
   rows came from different attempts and runner generations.
4. **Runner defects differed over time.** Output-path, dependency bootstrap,
   mount attribution, sandbox forwarding, ledger catch-up, and post-score
   transport behavior changed during the campaign.
5. **The aggregate was selected on failures.** Replaying only zero or
   uncountable Goal cases can improve a best-of ledger, but it cannot estimate
   the treatment effect of `/goal` against bare CLI.

## Durable Harness Findings

The investigation produced the following public fixes:

| PR | Surface | Effect |
| --- | --- | --- |
| #1825 | result paths | normalize output lookup across remote workspaces |
| #1826 | aggregate and ledger coherence | prevent stale aggregate reads after ledger updates |
| #1829 | dependency bootstrap | invoke pip through the selected virtual environment |
| #1830 | failure attribution | avoid classifying task-facing execution as a mount-only failure |
| #1831 | launcher sandbox forwarding | preserve the requested Codex sandbox contract |
| #1833 | ledger catch-up scope | isolate matched probe ledgers from historical Goal rows |
| #1834 | post-score countability | preserve a completed numeric official score after a later host transport warning |

PR #1834 changes score-countability precedence and remains subject to
independent review. It must not be treated as merged behavior until that review
is complete.

## Matched Evidence

The matched reruns narrowed the apparent regression set:

| Case | Goal xhigh | matched bare CLI xhigh | Supported conclusion |
| --- | ---: | ---: | --- |
| `flink-query` | 0.0 | 0.0 | historical bare pass did not reproduce |
| `pddl-airport-planning` | 0.0 | 0.0 | both routes reached the same normalized verifier failure class |
| `react-performance-debugging` | 0.0 | 0.0 | historical bare pass did not reproduce |
| `multilingual-video-dubbing` | 1.0 after runner repair | not required | historical Goal zero was a harness artifact |
| `debug-trl-grpo` | 0.25 | 0.60 | real observed gap, but prompt delivery was not yet matched |

The `debug-trl-grpo` trajectories explain the score difference at the solution
layer: the Goal run repaired one defect and stopped, while the bare run repaired
two scored defects in its first round. That observation does not by itself say
why the model selected different scopes. The initial instruction channel still
differed between the two routes.

## File-Objective Parity Probe

The probe wrapped bare `codex exec` so it received the same compact objective
as the Goal route and had to read the same workspace task packet before acting.
This removed the largest known prompt-delivery difference without adding
LoopX treatment state.

The first probe exposed a wrapper protocol error and was discarded before
task execution. After that error was repaired, a direct reverse-tunnel startup
probe confirmed that Codex could create a thread and start a turn, but the
subscription capacity limit fired before any task-facing action. The case-level
retry reproduced that same pre-task exit. Neither attempt reached the solver or
official verifier, so both are uncountable infrastructure/capacity outcomes.

The parity question therefore remains open for `debug-trl-grpo`. It should be
rerun after capacity is available, with the same objective digest and no change
to the official task or verifier. Until then, the observed 0.25 versus 0.60
difference is a case-level result under unequal prompt delivery, not evidence
of a native `/goal` regression.

## Responsibility

The broad score-regression claim was primarily a benchmark methodology and
harness problem, not evidence of a general native `/goal` defect:

- **LoopX benchmark harness:** several setup, attribution, ledger, and
  countability defects materially distorted the observed results.
- **Experiment design:** the compared routes did not have prompt-delivery or
  retry-history parity.
- **Agent analysis:** the early interpretation incorrectly treated absent
  case-local LoopX lifecycle fields as negative evidence for a baseline that
  was never supposed to create those fields.
- **Native Codex `/goal`:** Goal lifecycle activation was observed. A remaining
  case-level quality difference requires a prompt-parity rerun or a fresh
  matched campaign before it can be attributed to `/goal`.

## Required Comparison Contract

A future causal comparison should use a fresh, single-attempt matched campaign:

```text
same case set and order
same Codex model and reasoning effort
same task packet and instruction channel
same sandbox and network policy
same wall-clock and token budget
same runner and reducer commit
same official verifier closeout contract
no best-of replacement across retries
infra failures excluded symmetrically
```

The primary report should include paired case deltas and confidence intervals,
not only separate means. Failed-case repair reruns should be reported as a
recovery ledger, not merged into the causal comparison arm.

## Follow-Up Contracts

### P0: Finish Countability Review

Independently review #1834. A completed numeric official verifier result with
task-facing activity should remain countable even if a later host transport
warning occurs; a zero-activity numeric artifact must remain uncountable.

### P0: Replay Remaining Uncountable Goal Cases

After the reducer contract is accepted, replay the remaining uncountable Goal
cases with exact-run ledger isolation and required task-facing activity. Keep
setup, capacity, auth, and transport failures out of the score aggregate.

### P1: Run A Fresh Matched Campaign

If the product question is whether `/goal` improves or harms solution quality,
run both routes from a clean case set under the comparison contract above.
Do not answer that question from the repaired best-of canonical Goal ledger.

### P1: Preserve Prompt-Parity Evidence

Benchmark compact artifacts should record the public-safe prompt-delivery mode
and objective digest for each route. They should not store raw task text.
