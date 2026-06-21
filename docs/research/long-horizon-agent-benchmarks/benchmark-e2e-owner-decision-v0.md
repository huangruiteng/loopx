# Benchmark E2E Owner Decision v0

Date: 2026-06-12

Status: execution scope approved for the next bounded pilot; no benchmark run
started by this packet.

## Scope

This packet records the owner decision that unblocks the next real benchmark
e2e pilot route. It does not read raw task material, invoke Codex or model
APIs, generate patches, pull or run Docker images, start remote workloads,
evaluate submissions, upload, submit, touch public ranking paths, read
credentials, copy Codex auth, inspect raw trajectories, or open screenshots.

## Owner Decision

The owner approved the next benchmark e2e route under these constraints:

- continue toward a real e2e benchmark case instead of leaving the lane paused;
- local Docker and the shared remote GPU development host are both acceptable
  provider surfaces;
- Codex should choose the safer credential strategy;
- small public context reads and public benchmark-source choices do not require
  repeated owner approval;
- credential values, Codex auth/session state, private material, destructive
  git, production actions, uploads, submits, public ranking paths, and public
  benchmark claims remain stop conditions.

## Selected Route Policy

The selected first route remains the SWE-Bench Pro one-instance pilot because
the route-selection packet already ranked it ahead of TheAgentCompany on
current integration surface.

Provider policy:

- prefer the local trusted host for Codex CLI/auth-sensitive patch generation;
- allow local Docker when capacity and platform constraints are satisfied;
- allow Route B on the shared remote GPU host for isolated helper execution,
  public-source sync, and non-auth runner plumbing;
- do not copy local `~/.codex`, API keys, shell history, local runtime history,
  or credential files to the shared host;
- keep remote work inside the isolated workspace and temporary
  registry/runtime surfaces already proven by the Route B sync/install and
  runner-plumbing preflights.

## Execution Boundary

The approval authorizes the next worker to prepare and launch one bounded
SWE-Bench Pro e2e pilot only if the launch step preserves all of these
boundaries:

- no upload;
- no submit;
- no public ranking path;
- no public leaderboard or official-score claim before local evaluator output
  is reduced into compact evidence;
- raw problem statements, gold patches, test patches, test lists, generated
  patch content, raw logs, screenshots, trajectories, local paths, and
  credentials remain private;
- remote host receives no Codex auth/session state and no credential values;
- any model/Codex invocation uses the trusted local credential boundary unless
  a separate isolated credential is explicitly provided later.

If those conditions cannot be met, the worker should write a compact blocker
instead of starting the run.

## Next Worker Contract

The next bounded batch should choose one of these actions:

1. Launch the SWE-Bench Pro one-instance pilot locally if capacity, image
   platform, private sample reduction, local Codex patch generation, and local
   evaluator setup are all ready.
2. Use Route B only for remote no-auth provider or helper plumbing needed by
   the pilot, preserving the no-Codex-auth-sync boundary.
3. If either route fails before task execution, reduce the failure into compact
   `benchmark_run_v0` / `benchmark_result_v0` blocker evidence instead of
   spending more turns on new benchmark scouting.

## Executable Fixture

The deterministic fixture is:

```bash
python3 examples/benchmark-e2e-owner-decision-smoke.py
```

It emits `benchmark_e2e_owner_decision_v0` and asserts:

- execution scope is now approved for one bounded pilot;
- SWE-Bench Pro remains the first route;
- local Docker and Route B are both allowed provider surfaces;
- remote Codex auth sync remains forbidden;
- no benchmark, Docker run, Codex/model invocation, private material read,
  upload, submit, or public ranking path happens in this packet.

## Validation

Targeted validation:

```bash
python3 examples/benchmark-e2e-owner-decision-smoke.py
python3 -m py_compile examples/benchmark-e2e-owner-decision-smoke.py
loopx check \
  --scan-path examples/benchmark-e2e-owner-decision-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/benchmark-e2e-owner-decision-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

## Claim Boundary

This packet is not benchmark performance evidence. It may claim only that the
operator gate for the selected next e2e route has been resolved under a
credential-isolated local/remote policy. It must not be used to claim Goal
Harness improves SWE-Bench Pro, that a selected instance is solved, or that any
official/leaderboard score exists.
