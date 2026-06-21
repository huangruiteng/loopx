# AgentIssue-Bench Codex CLI Runner Execution Gate V0

Date: 2026-06-13

## Scope

This packet adds the next no-execute gate for the selected
AgentIssue-Bench tag:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id loopx-meta \
  --tag lagent_239 \
  --execution-gate-root <private-gate-root>
```

The command materializes the existing synthetic staging files plus
`execution-gate.public.json`. It still does not run Codex CLI, a model API,
Docker, source extraction, git baseline creation, patch generation, patch
evaluation, upload, submit, or public ranking paths. Passing `--execute`
appends only a compact no-run `benchmark_run_v0` readiness event.

`--execution-gate-root` and `--synthetic-staging-root` are mutually exclusive
so a worker cannot accidentally split one selected tag across two private job
roots.

## Gate Shape

The gate records only command shapes and relative-path placements.

Source extraction shape:

```text
docker image inspect alfin06/agentissue-bench:lagent_239
docker create --name <tmp-agentissue-lagent-239-container> alfin06/agentissue-bench:lagent_239
docker cp <tmp-agentissue-lagent-239-container>:/workspace/. <abs-private-job-root>/buggy-source
docker rm <tmp-agentissue-lagent-239-container>
```

Private git baseline shape:

```text
git -C <abs-private-job-root>/buggy-source init
git -C <abs-private-job-root>/buggy-source add .
git -C <abs-private-job-root>/buggy-source commit -m agentissue-bench-buggy-source-baseline
```

Host Codex patch-worker shape remains:

```text
codex exec --ephemeral --ignore-rules --sandbox workspace-write \
  --cd <abs-private-job-root>/buggy-source \
  --add-dir <abs-private-job-root> \
  --output-last-message <abs-private-job-root>/codex-last-message.txt \
  <abs-private-job-root>/context/prompt.md
```

Patch export placement remains:

```text
Patches/lagent_239/attempt.patch
```

## Compact Event

The compact event uses:

```text
mode=agentissue_codex_cli_runner_execution_gate
first_blocker=execution_gate_only_no_real_case
real_run=false
submit_eligible=false
leaderboard_evidence=false
```

Validation fields assert that the selected-container extraction commands,
private git baseline commands, host Codex command, and attempt-patch placement
are rendered, and that future execution still requires a run-specific opt-in.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py
python3 -m py_compile \
  loopx/benchmark.py \
  loopx/cli.py \
  examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-execution-gate-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
