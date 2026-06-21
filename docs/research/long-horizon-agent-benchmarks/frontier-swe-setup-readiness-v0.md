# FrontierSWE Setup Readiness v0

Date: 2026-06-20

Purpose: add FrontierSWE to the LoopX benchmark candidate set and decide
whether it should become an execution lane, a readiness lane, or a watchlist
lane.

This note is a setup-readiness scan only. It does not execute a benchmark task,
model agent, verifier, Docker environment, upload, leaderboard path, raw
trajectory, credential read, or paid cloud run.

## Source Pins

- Official benchmark repo:
  [Proximal-Labs/frontier-swe](https://github.com/Proximal-Labs/frontier-swe).
- Public leaderboard:
  [frontierswe.com](https://www.frontierswe.com/).
- Public announcement and framing:
  [Proximal FrontierSWE blog](https://www.proximal.ai/blog/frontierswe).

The public repo exposes an execution-oriented benchmark shape with `tasks/`,
`docker/`, `harbor_ext/`, `pyproject.toml`, and `uv.lock`. The README frames
the benchmark around the hardest ultra-long-horizon technical challenges in
performance engineering, computational science, and machine-learning research.

## Codex Surface Evidence

FrontierSWE has direct Codex leaderboard evidence. The public leaderboard
observed on 2026-06-20 includes GPT-5.5 via Codex and GPT-5.4 via Codex rows.
That means FrontierSWE is not merely an adjacent-agent benchmark; it already
has a public Codex surface that can be compared against a LoopX assisted
Codex route once our execution route is stable.

The evidence class is not the same as SWE-Marathon:

- SWE-Marathon is a low-baseline candidate, with prior setup notes recording
  `Codex CLI + GPT-5.5` at `12.0%` pass@1.
- FrontierSWE is a frontier-stress candidate, with direct Codex leaderboard
  rows but no local LoopX baseline-failure mining pass yet.

## Readiness Verdict

Add FrontierSWE as a `P1` readiness lane, not as the next immediate execution
lane.

Reasons it fits LoopX:

- Horizon is real. Public framing gives agents up to roughly 20 hours per task,
  which is closer to LoopX's long-running state, gate, restart, and
  validation thesis than short issue-fix suites.
- Task domains are control-plane relevant: performance engineering,
  computational science, and machine-learning research tend to expose long
  compile/test loops, resource management, partial progress tracking, and
  self-verification failures.
- The repo includes a Harbor extension surface, which makes it conceptually
  close to the benchmark execution work already done for Terminal-Bench and
  SWE-Marathon.
- Public Codex rows make it a plausible public comparison target once a clean
  Codex goal-mode route is confirmed.

Current blockers before a useful run:

- No local or cloud checkout has been inspected under the LoopX runbook.
- The runner boundary, no-upload flags, artifact paths, and failure-reduction
  schema are not yet documented.
- Task wall-clock budget is high; a first run should not start before the
  dedicated ECS benchmark substrate has produced at least one stable
  Terminal-Bench or SkillsBench no-upload result.
- The benchmark may expect Prime Intellect or Harbor-specific environment
  setup. That route should be mapped before any Docker image build, task start,
  model call, or upload-capable command.

## Proposed First Bounded Step

Produce a no-execution launch packet before any real FrontierSWE run:

1. Clone or inspect the public repo on the benchmark host.
2. Pin the repo commit, runner entrypoints, task inventory, and environment
   assumptions.
3. Identify one CPU-only or otherwise cheap smoke candidate without reading
   hidden references or task solutions.
4. Document the exact no-upload/no-submit command boundary.
5. Define the compact `benchmark_run_v0` reduction fields needed for FrontierSWE
   evidence.
6. Stop before any task container, model call, paid run, upload, or leaderboard
   path.

## Priority Decision

FrontierSWE should sit behind the immediate cloud benchmark substrate work, but
near the front of the strategic long-horizon queue:

1. Finish at least one cloud-host Terminal-Bench or SkillsBench no-upload smoke
   that proves the shared ECS + Codex CLI + Docker + compact reducer route.
2. Refresh SWE-Marathon on the same cloud route because it already has a
   source-pinned readiness note and a low Codex baseline.
3. Add FrontierSWE readiness immediately after or in parallel with the
   SWE-Marathon refresh, but do not start a real FrontierSWE task until the
   no-execution launch packet exists.

## Sources

- https://github.com/Proximal-Labs/frontier-swe
- https://www.frontierswe.com/
- https://www.proximal.ai/blog/frontierswe
