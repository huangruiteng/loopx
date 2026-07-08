# Beginner Loop Presets

This note maps lightweight public loop-engineering starter patterns onto
LoopX-native onboarding. The goal is not to copy another starter runtime. The
goal is to give new users a one-command path into the parts of LoopX that are
already valuable: agent-agnostic execution, team-agent lanes, durable todo
state, scheduler and quota guards, compact evidence, and human review gates.

## Product Bet

LoopX should absorb the packaging pattern, not the source of truth.

New users should see a small menu of useful presets. Each preset should compile
to existing LoopX state, todos, scheduler hints, and agent instructions instead
of creating a second `STATE.md` runtime or a separate loop ledger. The first
run should be safe and easy to explain. Advanced presets can be powerful, but
they must be opt-in and visibly gated.

The current thin entry point is:

```bash
loopx preset list
```

For one preset card:

```bash
loopx preset show daily-triage
loopx preset show changelog-draft
loopx preset show pr-watch
```

These commands are read-only. They render `/loopx ...`, `start-goal`,
`quota should-run`, and `heartbeat-prompt` command packets; they do not write
registry state, install automations, edit docs, or create PRs.

To check whether a project is ready for useful recurring loops, use the
read-only score report:

```bash
loopx ready-score --goal-id <goal-id> --agent-id <agent-id>
```

The score aggregates existing `doctor`, `status`, `quota`, scheduler, todo, and
evidence signals. It may render a badge preview, but it does not write README
badges or change project state.

## Recommendation Matrix

| Pattern | User value | LoopX default | Recommendation |
| --- | --- | --- | --- |
| Daily triage | Gives a repo owner a regular project digest without asking them to read every issue, PR, or status file. | L1 report-only. Read status, active todos, open gates, stale signals, and next actions. No code edits. | Absorb now as the first beginner preset. It demonstrates LoopX state, scheduler, quota, and no-surprise writeback with low risk. |
| Changelog draft | Turns recent merged work into a release-note draft and gives maintainers something immediately useful. | L1 draft-only. Produce a human-reviewed release note draft with PR links when available. No publish action. | Absorb now as a low-risk showcase preset. It is easy to demo and helps README readers understand concrete output. |
| PR watch | Keeps a PR from stalling by watching review, CI, and merge blockers. | L1 watch by default; L2 only after explicit opt-in. No auto-merge. | Absorb as an early preset, but present it as review assistance, not autonomous merging. |
| Issue triage | Converts noisy issue queues into priority, labels, and next-response suggestions. | L1 propose-only. Suggest labels, owners, duplicates, and next replies. No external write unless explicitly approved. | Absorb after Daily Triage because it shares most read-only plumbing and is friendly to public OSS repos. |
| CI sweeper | Fixes obvious broken checks and removes boring maintainer toil. | L2 opt-in. Worktree-only patches, verifier required, cost cap required, human review before merge. | Include as a high-value advanced preset. Do not make it a beginner default, but do not bury it; it is one of the clearest ROI stories once gates are visible. |
| Dependency sweeper | Handles safe dependency bumps, patch releases, and recurring update noise. | L2 opt-in. Patch/minor policy, denylist, verifier, cost cap, and human review before merge. | Include as a high-value advanced preset after CI Sweeper. Start with policy design and dry-run/report mode before auto-fix. |
| Post-merge cleanup | Finds follow-up debt after merged work. | L1 scan first; L2 small patch only after explicit scope. | Defer from the first public menu. It is useful, but less legible for new users than CI or release notes. |
| Ready score | Tells users whether their repo is ready to run useful loops. | Read-only report. Derive from existing LoopX signals: install, goal connection, agent identity, scheduler, quota, todos, gates, evidence, and write scope. | Absorb now as a supporting command or section in guided start. Avoid badge writeback until the score model is stable. |
| Cost estimate | Helps users decide cadence and maturity level before enabling automation. | Advisory only. Use static preset assumptions plus live quota/scheduler hints; never claim precise billing. | Absorb with guided presets. Use L1/L2/L3 language, but keep estimates coarse and conservative. |
| Starter templates | Reduces first-run friction. | Generate LoopX-native todos, heartbeat prompt, and first-run command packet. Do not create a parallel source of truth. | Absorb only as thin preset output. Templates should explain the LoopX state kernel rather than hide it. |

## Preset Tiers

### Tier 1: Beginner defaults

These are safe enough for a first public quickstart:

- Daily Triage L1
- Changelog Draft L1
- PR Watch L1

They should be marketed as "turn the loop on, get a useful report, stay in
control." They should not require users to understand worktrees, verifier
agents, or merge policy before seeing value.

### Tier 2: High-value opt-in

These should be visible but not default:

- CI Sweeper L2
- Dependency Sweeper L2

The user-facing promise should be "LoopX can draft bounded fixes when the
guardrails are explicit." The required guardrails are:

- isolated git worktree;
- explicit denylist and allowed update policy;
- verifier or focused smoke before the patch is considered ready;
- token/cadence cap;
- human review before push, merge, publish, or dependency rollout;
- escalation after repeated failure or unchanged error signatures.

### Tier 3: Later expansion

These should wait until the first presets prove the route:

- Post-Merge Cleanup;
- richer starter packs;
- external connector write actions;
- unattended L3 modes.

They are useful, but they raise the support burden before the product has
earned beginner trust.

## README Implication

The README should eventually use a three-layer shape:

1. First screen: one sentence, three beginner presets, and a safety promise.
2. Quickstart: real LoopX commands that create or inspect actual LoopX state.
3. Deep sections: agent-agnostic control plane, team-agent lanes, lightweight
   state kernel, scheduler/quota, evidence gates, and L2 opt-in presets.

This keeps the front door simple without reducing LoopX to a template
collection. README and README.zh-CN first-screen edits should be previewed for
owner review before commit because they change the main public presentation.

## Non-Goals

- Do not copy a separate `STATE.md` source of truth into LoopX onboarding.
- Do not imply auto-fix, auto-merge, publish, or dependency rollout on the
  beginner path.
- Do not hide gates behind friendly copy. The point of LoopX is that gates,
  todos, evidence, and cost stay inspectable.
- Do not add broad starter scaffolding before the thin preset picker proves
  which routes users actually select.
