# Benchmark Rotation Product-Mode Protocol 2026-06-17

This note updates the active benchmark-routing policy after Agents' Last Exam
PR #8 merged a Local Docker provider for the Linux subset. It is a
public-safe planning and readiness artifact, not a benchmark result, score
claim, upload path, or leaderboard route.

## Source Boundary

This note uses only:

- public upstream facts from `rdi-berkeley/agents-last-exam` PR #8;
- LoopX compact readiness probes;
- existing compact benchmark ledger and case-analysis summaries;
- active-state routing policy.

It did not read raw task text, raw logs, raw trajectories, verifier output
tails, screenshots, hidden references, credentials, or leaderboard material.
No Docker image was pulled, no container was started, no model was invoked, and
no benchmark task was run.

## Policy Change

The previous Terminal-Bench-first budget cap is now superseded for routing.
Terminal-Bench, SkillsBench, and ALE should rotate as evidence sources until
the harness has enough runner, trace, ledger, and product-mode stop-policy
experience to justify specializing on one benchmark score.

ALE is newly eligible for bounded local readiness work because PR #8 adds a
non-GCP Local Docker provider for the Linux subset. It is not yet the default
scored-run lane: the first pull of `agentslastexam/ale-ubuntu22-docker:latest`
is a large local resource event, and DinD tasks are still deferred upstream.

## Main Matrix

Keep the main comparison table to these rows. Other combinations are ablations
or setup probes until promoted by a concrete failure or regression hypothesis.

| Row | Benchmark lane | Baseline arm | LoopX arm | Primary use |
| --- | --- | --- | --- | --- |
| 1 | SkillsBench product-mode | raw Codex autonomous max5 | LoopX state/todo/replan/CLI max5 | Main product-mode comparison once setup reaches agent rounds and official scoring. |
| 2 | SkillsBench blind-loop control | Codex ACP blind-loop max5 | LoopX blind-loop treatment max5 | Control for reward-blind continuation effects; useful for positive, neutral, and regression guards. |
| 3 | Terminal-Bench | raw/managed Codex CLI runner for one official task | LoopX-managed runner with durable lifecycle trace | Runner materialization, verifier attribution, timeout, and restart/ledger robustness. |
| 4 | ALE Local Docker | host Codex CLI local no-upload runner | LoopX product-mode local no-upload runner | Cross-benchmark adapter lifecycle and local Docker/CUA/source-lock readiness before score chasing. |

## Shared Metrics

Every scored pair should record the same compact fields:

- `best_score`: max official score reached across completed rounds;
- `final_score`: last completed round official score;
- `round_rewards`: offline scalar official score per completed round;
- `first_success_round`: first completed agent round reaching the pass
  threshold, or null;
- `declared_done_score`: score when an agent declares done, if applicable;
- `agent_rounds_started`;
- `case_attempt_budget_should_count`;
- `official_feedback_blinded`: true unless a reward-feedback ablation explicitly
  says otherwise;
- `reward_feedback_forwarded`: false for main-table rows;
- `decision`: uplift, no-uplift, regression, baseline-solved, setup-blocked,
  launcher/materialization-blocked, or attribution-required.

`best_score` is the comparison score for max-round experiments. `final_score`
and `declared_done_score` remain mandatory diagnostics because a treatment can
find a partial or early success and then regress, or can declare done at 0
before using LoopX state.

## Trace Contract

Each run must leave enough public-safe trace to explain good and bad cases
without opening raw trajectories:

- Codex CLI route label and compact session/run handle;
- LoopX CLI call count and command classes, such as `which goal`,
  state read, todo write, refresh, or replan;
- LoopX state reads/writes count;
- protected path and scope projection status per continuation;
- runner lifecycle stage: launch, process started, runner args accepted, job
  materialized, trial started, worker started, result written, verifier scored;
- compact blocker class when the run stops before scoring;
- private artifact roots represented only as basenames or compact refs.

## Current Lane Status

| Lane | Current status | Next useful bounded step |
| --- | --- | --- |
| SkillsBench product-mode | Local Docker readiness was repaired enough for `paratransit-routing` to reach official scoring, but LoopX product-mode stopped on agent-declared done at 0 before substantive state/replan use. | Fix or explicitly test product-mode stop/replan semantics before claiming route-level uplift. |
| SkillsBench blind-loop | Has positive, neutral, baseline-solved, and regression controls under max5 no-reward rules. | Use only when a prompt/round/scope policy change needs a guard. |
| Terminal-Bench | Valuable evidence exists for materialization, verifier attribution, timeout tiers, and baseline-solved cases. | Select one fresh or attribution-required case only when the lifecycle trace hypothesis is explicit. |
| ALE | PR #8 source is route-ready in a clean source lock at merge commit `3002622`; `uv` and `ale_run` are available; `docker.yaml`, `example_exp.yaml`, and `selected_tasks/linux_no_dind.txt` exist. The launch packet is blocked on `docker_image_missing` for `agentslastexam/ale-ubuntu22-docker:latest`. | Decide or schedule the large image acquisition boundary, then do a no-upload dry-run before any task-level run. |

## Local Disk Cleanup Update 2026-06-18

A later local cleanup removed the default Docker/Colima image, container,
volume, and build-cache inventory. Compact ledgers, case-analysis summaries,
and run-history records remain usable, but new local benchmark execution that
needs Docker images or runner-local Harbor tooling should be treated as not
launch-ready until explicitly rehydrated. The compact ALE local preflight now
stops on `docker_image_missing`; the existing ALE source checkout still imports
`ale_run` but is behind upstream and should not be treated as the fresh source
lock for a new non-demo run.

This changes routing, not historical interpretation. For Docker-heavy
ALE/Terminal-Bench/SkillsBench work, prefer the split-control provider route:
keep Codex CLI, LoopX state, credentials, and model invocation local;
use prod/remote only for Docker/CUA/provider capacity; and record only compact
readiness/run counters. Stop before syncing Codex auth, reading raw task bodies,
raw logs, trajectories, screenshots, hidden refs, uploads, leaderboard paths, or
public score claims.

## ALE Readiness Facts From This Batch

Compact probes on 2026-06-17:

- The existing local ALE checkout is intentionally left untouched because it is
  behind upstream and contains local host-Codex route experiments.
- A clean detached worktree was created at the public upstream merge commit
  `3002622` from PR #8 for source-lock probing.
- Source readiness is true when upstream tracking is not required for the
  detached source lock: expected repo matches, `ale_run` imports, no paths are
  recorded.
- Runner readiness sees `uv` and `ale_run`, permits public selected-task
  material, and stops only on `docker_image_missing`.
- The no-execution launch packet for `example_exp.yaml` plus
  `selected_tasks/linux_no_dind.txt` stops on the same Docker image blocker and
  records no raw command argv, local paths, task body, or artifact content.

## Next Action

Do not run ALE task execution or pull the large image from an automation turn
unless the local resource boundary is explicitly accepted or scheduled. While
ALE waits on image acquisition, continue Terminal-Bench and SkillsBench rotation
using existing compact cases and the trace contract above.

The next full benchmark execution should be selected by one of these concrete
hypotheses:

1. product-mode stop/replan semantics can improve or prevent a known
   SkillsBench product-mode miss;
2. Terminal-Bench lifecycle trace can convert an attribution-required row into
   a trusted case result or non-countable setup blocker;
3. ALE Local Docker can complete a no-upload dry-run after the image boundary
   is resolved, proving the new provider route without score claims.

## Validation

Use these validation surfaces when editing this protocol:

```bash
loopx check --scan-path docs/research/long-horizon-agent-benchmarks/benchmark-rotation-product-mode-protocol-20260617.md
python3 examples/agents-last-exam-local-docker-host-codex-route-smoke.py
python3 examples/agents-last-exam-local-runner-readiness-smoke.py
python3 examples/agents-last-exam-local-launch-packet-smoke.py
```
