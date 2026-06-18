# Benchmark Developer Workflow

Goal Harness treats benchmark execution as a developer workflow, not only as a
research activity. A benchmark runner should be something a contributor can
inspect, dry-run, diagnose, and improve without reading maintainer `.local`
state or raw benchmark trajectories.

This document is the stable product entry point for benchmark work. Research
packets and dated route notes still live under
`docs/research/long-horizon-agent-benchmarks/`, but reusable runner behavior
belongs in `goal_harness/`, `examples/`, and this guide.

## Product Shape

The benchmark workflow has four layers:

1. **Select** a benchmark family, task, and arm without exposing private task
   text or reward leakage.
2. **Launch** through an explicit route contract: local agent, local Goal
   Harness state, and a local model invocation boundary; optional remote
   execution substrate for Docker, runner dependencies, task data, and compact
   reduction.
3. **Observe** the run through compact handles: pid or job state, readiness
   re-check, materialization, result or blocker, and cleanup state.
4. **Ingest** only public-safe evidence into Goal Harness history, ledger, and
   case analysis.

The user-facing product promise is simple: a developer should be able to tell
what ran, why it was allowed, what blocked it, and what can be tried next,
without seeing credentials, raw logs, raw trajectories, or local machine paths.

## Golden Path

From a fresh checkout:

```bash
python3 -m py_compile goal_harness/*.py goal_harness/benchmark_core/*.py
python3 examples/benchmark-split-control-remote-executor-smoke.py
goal-harness benchmark --help
```

For a real benchmark slice, use this sequence:

1. Run a source and boundary preflight for the target benchmark.
2. Build or inspect the split-control readiness payload.
3. Produce a launch plan or runner batch only after a fresh readiness re-check.
4. Run the smallest no-upload dry-run or mini-pair that can answer the current
   product question.
5. Ingest a compact result or precise blocker.
6. Update Goal Harness todo/state so the next developer sees the current route.

Do not start from a raw shell command hidden in a local note. If a benchmark
cannot be launched through a documented route, the next product task is to
build that route, not to keep a one-off script alive.

## Capture The Process While Running

Do not wait for a benchmark family to be fully solved before documenting how it
runs. Each real run should improve the developer workflow in the same batch as
the result or blocker:

1. Before launch, write down the intended route, boundary, command shape,
   expected compact artifacts, and stop conditions.
2. During launch, preserve only observable handles that another developer can
   use: pid or job basename, readiness state, poll command, cleanup state, and
   compact artifact refs.
3. After launch, update the workflow or adapter notes with what changed:
   product-path pass, precise blocker, cleanup rule, or stale assumption.
4. If the run required a private local script, turn the reusable part into a
   public command, fixture, or adapter contract before relying on it again.

The goal is a living runner guide. Repeated benchmark attempts should make the
next attempt easier to launch and debug, not only add more private evidence.

## Split-Control Route

Docker-heavy benchmarks should use the split-control route unless a narrower
local-only route is explicitly safer:

| Owner | Responsibility |
| --- | --- |
| Local agent | Codex CLI, auth, model invocation, planning, patch generation, Goal Harness state, quota, todo, and evidence filtering. |
| Remote executor | Docker runtime, runner dependencies, task-data or image staging, bounded command/file execution, and compact result reduction. |

The remote executor is not an agent-auth environment. Missing remote Codex,
Codex ACP, or model credentials is not a benchmark blocker. Real blockers are
things like missing split-control adapter, missing runner tooling, missing task
data or images, missing remote node runtime when a specific runner requires it,
or a failed cleanup/readiness check.

See
[`benchmark-split-control-remote-executor-v0.md`](research/long-horizon-agent-benchmarks/benchmark-split-control-remote-executor-v0.md)
for the current machine contract.

## Current Benchmark Families

| Family | Product-path target | Current maturity |
| --- | --- | --- |
| Terminal-Bench | Local Codex/Goal Harness controls the attempt; remote executor provides Docker or runner substrate and compact result ingestion. | Needs a real remote-executor launch seam before the local launcher can count as product-path evidence. |
| SkillsBench | Local Codex/Goal Harness controls state, prompt, and writeback; remote executor stages task files and runs Docker-bound worker surfaces. | Needs remote task staging plus remote Docker execution instead of local-only BenchFlow assumptions. |
| Agents' Last Exam | Local Codex/Goal Harness controls the agent; remote Docker/CUA provides the sandbox; compact result or blocker is ingested locally. | A demo/tool-smoke style split-control surface is product-path proven; formal task runs still need task-data and public-claim gates. |

This table is intentionally about runner maturity, not leaderboard score.
Score claims require separate public-safe result ingestion and review.

## Evidence Contract

Benchmark evidence may include:

- benchmark id, task id or public-safe case id;
- arm or mode label;
- readiness gate result;
- process or job handle basename;
- compact result fields such as `score`, `best_score`, `final_score`,
  `first_success_round`, `duration_s`, and `blocker`;
- cleanup state;
- links to public docs or compact JSON/Markdown artifacts.

Benchmark evidence must not include:

- raw task text, hidden task files, verifier body output, or solution material;
- raw trajectories, transcripts, screenshots, stdout, stderr, or shell argv;
- credentials, tokens, local absolute paths, remote absolute paths, or private
  hostnames;
- uploads, submit paths, or leaderboard claims unless a specific public release
  gate has approved them.

## Developer Checklist

Before a PR that changes benchmark behavior:

- Name which layer changed: selection, launch, observe, ingest, scoring, or
  docs.
- Keep benchmark-specific runner details inside the adapter.
- Preserve the split-control boundary when a remote executor is involved.
- Add or update a focused smoke for the durable contract.
- Run `goal-harness check --scan-path <changed-public-path>` for public docs or
  examples.
- Do not commit `.local`, raw logs, private run directories, active state, or
  local runner configs.

## Roadmap

Near-term work should make the benchmark workflow feel like a small product:

- expose a single developer-facing command path for readiness and runner batch
  planning;
- add observable launch handles so long runs can be polled without chat memory;
- align Terminal-Bench, SkillsBench, and Agents' Last Exam on the same
  launch/observe/ingest lifecycle;
- document the no-upload dry-run path before chasing broad score matrices;
- make compact blockers first-class, so a failed launch still teaches the next
  developer exactly what to repair.
