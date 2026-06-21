# AgentIssue-Bench Codex CLI Runner Synthetic Staging V0

Date: 2026-06-13

## Scope

This packet extends the `lagent_239` AgentIssue-Bench Codex CLI runner flow
with an opt-in synthetic private job-root fixture:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id loopx-meta \
  --tag lagent_239 \
  --synthetic-staging-root <private-job-root>
```

The fixture creates only placeholders. It does not invoke Codex CLI, a model
API, Docker, official helpers, uploads, submit, public ranking paths, real
task material, patch generation, or patch evaluation. Passing `--execute`
still only appends a compact no-run `benchmark_run_v0` readiness event.

## Materialized Shape

The synthetic root contains:

```text
context/prompt.md
buggy-source/.gitkeep
Patches/lagent_239/.gitkeep
runner-flow-plan.public.json
benchmark_run.compact.json
```

`context/prompt.md` is a synthetic placeholder and names the expected patch
output slot:

```text
Patches/lagent_239/attempt.patch
```

`runner-flow-plan.public.json` records only relative paths, command
placeholders, stop rules, and no-execution boundary flags. It does not record
the private staging-root path.

`benchmark_run.compact.json` uses:

```text
mode=agentissue_codex_cli_runner_synthetic_staging_fixture
first_blocker=synthetic_staging_only_no_real_case
real_run=false
submit_eligible=false
leaderboard_evidence=false
```

## Why This Exists

The previous wrapper proved command rendering and compact append behavior. This
fixture proves the next layer that a real runner will need before any execution:

1. private job-root directory creation;
2. prompt-path rendering;
3. extracted-source workspace placeholder;
4. `Patches/lagent_239/attempt.patch` parent placement;
5. compact reducer file naming.

It intentionally stops before selected-container source extraction and before
host-local `codex exec`. The next step is a separate guarded opt-in gate for
real source extraction and host-Codex patch production.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py
python3 -m py_compile \
  loopx/benchmark.py \
  loopx/cli.py \
  examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-synthetic-staging-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
