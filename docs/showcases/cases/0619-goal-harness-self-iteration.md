# 0619: Goal Harness Public Repo Self-Iteration

## Summary

Goal Harness was used to improve a fast-moving Goal Harness repository, not only
one isolated feature. The public repo shows a long-running agent project moving
across benchmark adapters, control-plane correctness, planning lanes, dashboard
surfaces, public docs, smokes, and multi-agent coordination while still keeping
work reviewable.

The case matters because it is public and commit-backed. A reader can inspect
the same Git history that produced the product behavior: the repo records the
workload, the feature chain, the validation surfaces, and the boundaries of
what evidence is safe to publish.

This is not a claim that one side agent authored every commit. The point is
stronger and more product-relevant: Goal Harness can keep a high-churn,
multi-lane agent engineering project coherent while primary and side work move
in parallel.

## Public Repository Signal

The workload signal is the whole public repository through fixed anchor commit
`0510dda` (`Project outcome-floor blocker noop state`). The fixed anchor avoids
letting this documentation update change its own evidence window.

| Signal | Value |
| --- | --- |
| All public commits in the repository | 736 |
| Unique files touched across public history | 547 |
| Cumulative public insertions / deletions | 254763 / 48601 |
| Public commits since 2026-06-18 00:00 +08:00 | 179 |
| Recent unique files touched since 2026-06-18 | 189 |
| Recent cumulative insertions / deletions | 41958 / 19641 |
| Public commits on 2026-06-19 | 71 |
| 2026-06-19 unique files touched | 114 |
| 2026-06-19 cumulative insertions / deletions | 15181 / 957 |

Inside that repo-scale activity, the side-agent coordination slice from
`32b466d^..0510dda` is the productization lane that made multi-agent ownership
visible:

| Signal | Value |
| --- | --- |
| Commits | 14 |
| Unique files touched | 45 |
| Cumulative insertions / deletions | 3248 / 165 |
| Main side-agent surfaces | CLI, todo metadata, quota/status/review projection, heartbeat prompt, docs, smokes, showcases |

The repo-scale numbers show the environment Goal Harness had to manage:
benchmark work, control-plane fixes, public docs, smoke coverage,
dashboard/status contracts, and product positioning all moved in the same short
window.

These are not raw transcript metrics. They are public Git facts that a reader
can inspect locally with commands such as:

```bash
git rev-list --count HEAD
git log --numstat --format=COMMIT:%H
git log --reverse --oneline --since="2026-06-18T00:00:00+08:00"
git log --reverse --oneline 32b466d^..0510dda
```

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

## Goal Harness Behavior

Goal Harness made the full loop durable in several places:

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

For an operator, this case shows how Goal Harness reduces coordination load:

- the primary agent can keep focus on a high-priority benchmark lane;
- side agents can improve product, docs, and control-plane surfaces without
  silently racing the primary agent;
- user gates remain explicit instead of turning into hidden idle time;
- safe fallback or side work can continue when the gated path is blocked;
- small validated side changes do not become primary-agent queue pressure;
- larger or riskier side work still flows through primary review.

For a potential user, the reusable pattern is this: Goal Harness lets a project
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
2. Goal Harness keeps the whole project legible through durable goals, todos,
   gates, quota, evidence, and run history.
3. A side-agent lane is introduced so productization and coordination work can
   progress beside the primary benchmark lane.
4. The side lane ships ownership, identity-aware prompts, showcase material,
   self-merge policy, and outcome-floor projection with focused validation.
5. Public docs and smokes turn the experience into a reusable case without
   publishing private chat, internal docs, or raw benchmark evidence.
