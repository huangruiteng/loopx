# 0619: LoopX Public Repo Self-Iteration

## Summary

LoopX was used to improve a fast-moving LoopX repository, not only
one isolated feature. The public repo shows a long-running agent project moving
across benchmark adapters, control-plane correctness, planning lanes, dashboard
surfaces, public docs, smokes, and multi-agent coordination while still keeping
work reviewable.

The case matters because it is public and commit-backed. A reader can inspect
the same Git history that produced the product behavior: the repo records the
workload, the feature chain, the validation surfaces, and the boundaries of
what evidence is safe to publish.

This is not a claim that one side agent authored every commit. The point is
stronger and more product-relevant: LoopX can keep a high-churn,
multi-lane agent engineering project coherent while primary and side work move
in parallel.

## Public Repository Signal

The workload signal is the whole public repository through fixed anchor commit
`86d6d9d` (`docs: sharpen always-on agent team hero copy`). The fixed anchor
avoids letting this documentation update change its own evidence window.

| Signal | Value |
| --- | --- |
| All public commits in the repository | 801 |
| Unique files touched across public history | 570 |
| Cumulative public insertions / deletions | 265703 / 49895 |
| Public commits since 2026-06-18 00:00 +08:00 | 244 |
| Recent unique files touched since 2026-06-18 | 216 |
| Recent cumulative insertions / deletions | 52898 / 20935 |
| Public commits on 2026-06-19 | 74 |
| 2026-06-19 unique files touched | 118 |
| 2026-06-19 cumulative insertions / deletions | 16087 / 1082 |
| Public evidence window | 2026-05-31 22:57 +08:00 to 2026-06-20 12:18 +08:00 |
| Calendar elapsed in public Git window | 19.6 days |
| Days with public commits | 16 |

The repo-scale numbers show the environment LoopX had to manage:
benchmark work, control-plane fixes, public docs, smoke coverage,
dashboard/status contracts, and product positioning all moved in the same short
window.

These are not raw transcript metrics. They are public Git facts that a reader
can inspect locally with commands such as:

```bash
git rev-list --count HEAD
git log --numstat --format=COMMIT:%H
git log --reverse --oneline --since="2026-06-18T00:00:00+08:00"
```

## Efficiency Evidence Model

Commit volume is not itself an efficiency claim. The fair comparison is to
translate the public repository state into product requirements, estimate what
an ordinary AI-coding-assisted product process would schedule for each
requirement, then compare that baseline with the public wall-clock evidence
window.

The baseline below already assumes competent AI coding help. It is not a
"manual developer with no model" comparison. The assumed traditional process is:
scope the requirement, write or review the contract, implement, add focused
validation, document the behavior, review the diff, and merge or release it.
Requirement clusters are discounted when the shipped state is only a prototype,
design note, or partial adapter.

| Product requirement cluster | Public evidence surface | Landing level | Conservative AI-coding-assisted baseline |
| --- | --- | --- | --- |
| Local control-plane kernel: bootstrap/connect, registry, status, history, check, review packet, todo CLI, public boundary scan | `loopx/`, README, status contracts, docs, smokes | shipped core | 11-16 developer-days |
| Gate, quota, heartbeat, reward, blocker, and safe-fallback lifecycle | quota/status modules, heartbeat prompt docs, state interaction docs, regression smokes | shipped core with ongoing hardening | 10-15 developer-days |
| Multi-agent ownership and side-agent delivery discipline | `claimed_by`, registered-agent checks, identity-aware heartbeat prompts, worktree guard, self-merge evidence flag | shipped coordination slice | 5-8 developer-days |
| Benchmark and evaluation control contracts | Terminal-Bench, SkillsBench, ALE, Codex Goal worker contracts, reducers, readiness docs | partial product surface; not full leaderboard automation | 10-16 developer-days |
| Dashboard, frontstage, and projection surfaces | dashboard app, status server, frontstage fixtures, showcase prototype, goal-channel projection | prototype to beta | 5-8 developer-days |
| Public smokes, docs governance, and redaction discipline | `examples/`, showcase catalog checks, boundary checks, docs governance smoke | shipped support system | 8-12 developer-days |
| Product positioning, onboarding, showcases, launch copy, naming, contributor tasks | README, Chinese README, showcases, product vision, outreach drafts | public docs and case surface | 5-8 developer-days |
| Planning, dreaming, server/client product shape | planning lane docs, dreaming notes, server/client shape docs | design/prototype, deliberately low estimate | 2-4 developer-days |
| Packaging, install, skills, contributor workflow | install scripts, global skill docs, contributor contracts | usable but still local-first | 3-5 developer-days |
| **Total conservative baseline** | Whole public repo through `86d6d9d` | mixed maturity | **59-92 developer-days** |

That baseline should be read as a range, not a precision metric. Several
capabilities are deliberately not counted as high-cost production systems:
frontstage is still a prototype, server/client shape is mostly product design,
and benchmark adapters are public contracts plus partial routes rather than a
finished hosted evaluation service.

The public Git window is 19.6 calendar days, with 16 days containing public
commits. Compared with a single AI-coding-assisted product engineer, the
conservative requirement estimate suggests roughly **3.0x-4.7x calendar
compression**. Compared with a small two-person AI-coding team, the claim
should be weaker: roughly **1.8x-3.2x calendar compression**, depending on how
much of the work could truly run in parallel after product review, validation,
and merge sequencing.

The stronger product claim is not the exact multiplier. It is that Goal
Harness made the compression governable: multiple lanes moved in the same
short window while the project still kept goals, gates, todos, ownership,
evidence, boundary checks, and merge policy visible. Without that control
plane, the same velocity would be much harder to review, hand off, or trust.

This efficiency model is intentionally conservative and public-safe. It does
not use private chat logs, local active-state bodies, raw agent sessions, or
unpublished benchmark artifacts. Future versions can make it more rigorous by
keeping the requirement clusters in a machine-readable fixture and asking two
human reviewers to independently score landing level and baseline effort.

## Feature Chain

The public repository history shows a connected long-horizon feature chain, not
only a todo/claim feature:

1. **Benchmark and adapter maturation**: Terminal-Bench, ALE, SkillsBench, and
   split-control execution routes gained public contracts, readiness probes,
   compact reducers, cloud-host guidance, and benchmark workflow docs.
2. **Control-plane correctness**: quota routing, scoped gates, action scopes,
   active-state write locks, todo projection gaps, project-asset handoffs, and
   outcome-floor blocker/no-op states were tightened so automation does not
   confuse surface progress with real progress.
3. **Planning and dreaming lanes**: autonomous replanning, advisory dreaming,
   server-managed planning proposals, and dreaming lane badges were separated
   so background thinking can propose work without silently becoming executable
   project truth.
4. **User/operator surfaces**: lifetime-goal language, agent-led diagnostics,
   dashboard first-screen decision framing, onboarding todo candidates,
   quickstart clarity, and showcase-first README material made the control
   plane easier for humans and future agents to understand.
5. **Multi-agent ownership**: the repo added registered todo ownership,
   `claimed_by`, registered-agent checks, identity-aware heartbeat prompts,
   side-agent scope rules, and independent worktree policy.
6. **Side-agent self-merge discipline**: small validated side-agent work can be
   completed with `--side-agent-self-merged --evidence`, while broad, risky, or
   unclear work still routes to primary review.
7. **Evidence and public-boundary discipline**: public smokes, regression
   wrappers, docs governance, showcase catalog checks, and public/private
   boundary scans keep the case reproducible without exposing private chats,
   raw trajectories, internal docs, or benchmark logs.

That chain matters because it converts a fuzzy collaboration problem into
product behavior:

- What is the durable goal?
- Which lane owns the next bounded move?
- Which agent has claimed a todo?
- Which gate is waiting for a human?
- What can safely continue while another path is gated?
- Which validation or public evidence proves the move happened?
- Which work can self-merge, and which work must go to primary review?

## LoopX Behavior

LoopX made the full loop durable in several places:

- the registry and prompt contracts named primary and side-agent identities
  instead of relying on chat memory;
- active todos separated benchmark, productization, documentation, planning,
  and follow-up work into reviewable obligations;
- quota and status projection kept executable work, monitor work, user gates,
  and blockers distinct;
- side-agent scope stayed in the agent prompt and handoff, while todo metadata
  kept a simple `claimed_by` owner;
- completion evidence recorded self-merge and validation outcomes instead of
  leaving them only in conversation;
- public docs and smokes turned reusable lessons into repository artifacts;
- public/private boundary checks kept showcase material free of internal
  links, raw benchmark evidence, credentials, and machine-local state.

The product value is not that an agent wrote many files. The value is that a
high-churn, multi-lane repository stayed legible: a future agent can recover
the goal, ownership, gates, validation, evidence, and remaining follow-up work
from public project surfaces.

## User-Facing Value

For an operator, this case shows how LoopX reduces coordination load:

- the primary agent can keep focus on a high-priority benchmark lane;
- side agents can improve product, docs, and control-plane surfaces without
  silently racing the primary agent;
- user gates remain explicit instead of turning into hidden idle time;
- safe fallback or side work can continue when the gated path is blocked;
- small validated side changes do not become primary-agent queue pressure;
- larger or riskier side work still flows through primary review.

For a potential user, the reusable pattern is this: LoopX lets a project
delegate bounded improvement lanes to agents without losing ownership, evidence,
gate discipline, or merge discipline.

## Evidence Boundary

This case intentionally uses only public repository evidence: commit ids, file
counts, public docs, public CLI behavior, public smokes, and public boundary
checks. It excludes private thread text, local active-state bodies, internal
document links, screenshots, raw benchmark material, credentials, and
machine-specific paths.

## Website Story Beats

1. A long-running agent engineering repo is moving quickly across benchmark,
   runtime, docs, dashboard, planning, and smoke surfaces.
2. LoopX keeps the whole project legible through durable goals, todos,
   gates, quota, evidence, and run history.
3. A side-agent lane is introduced so productization and coordination work can
   progress beside the primary benchmark lane.
4. The side lane ships ownership, identity-aware prompts, showcase material,
   self-merge policy, and outcome-floor projection with focused validation.
5. Public docs and smokes turn the experience into a reusable case without
   publishing private chat, internal docs, or raw benchmark evidence.
