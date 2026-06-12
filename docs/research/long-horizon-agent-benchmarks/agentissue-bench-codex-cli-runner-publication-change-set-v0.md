# AgentIssue-Bench Codex CLI Runner Publication Change Set V0

Date: 2026-06-13

## Scope

This packet defines the publication boundary for the AgentIssue-Bench
`lagent_239` Codex CLI runner flow. It is a staging and review contract, not a
benchmark execution packet. It does not run Codex, Docker, model APIs, source
extraction, patch generation, patch evaluation, upload, submit, or public
ranking paths.

The publication change set is intentionally single-benchmark and single-tag:

```text
benchmark=agentissue-bench
selected_tag=lagent_239
selected_image=alfin06/agentissue-bench:lagent_239
real_run=false
submit_eligible=false
leaderboard_evidence=false
```

## Include In The Change Set

Stage these new public docs together:

```text
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-contract-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-flow-plan-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-dry-run-wrapper-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-synthetic-staging-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-execution-gate-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-first-run-handoff-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-workflow-check-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-run-gate-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md
docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-publication-change-set-v0.md
```

Stage these new public smokes together:

```text
examples/agentissue-bench-codex-cli-runner-contract-smoke.py
examples/agentissue-bench-codex-cli-runner-flow-smoke.py
examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py
examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py
examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py
examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py
examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py
examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py
examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py
examples/agentissue-bench-codex-cli-runner-publication-change-set-smoke.py
```

Stage only the AgentIssue hunks from these mixed tracked files:

```text
goal_harness/benchmark.py
goal_harness/cli.py
goal_harness/status.py
docs/research/long-horizon-agent-benchmarks/README.md
```

These files currently contain unrelated dirty hunks from other benchmark lanes,
so do not stage them with a whole-file `git add`. Use hunk-level staging or an
equivalent cached patch that selects only the AgentIssue runner-flow symbols,
CLI command, compact `read_boundary` preservation, README bullets, and
smoke/doc index entries. In a clean PR worktree based directly on `origin/main`,
these same hunks may appear as whole-file staged changes because no unrelated
local hunks are present.

## Mixed-File Hunk Boundaries

The source hunks that belong to this change set are identified by these public
symbols and command strings:

```text
AGENTISSUE_BENCHMARK_ID
AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION
AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION
AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION
AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION
AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION
AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION
build_agentissue_codex_cli_runner_wrapper
materialize_agentissue_codex_cli_runner_synthetic_staging
materialize_agentissue_codex_cli_runner_execution_gate
materialize_agentissue_codex_cli_runner_first_run_handoff
materialize_agentissue_codex_cli_runner_workflow_check
materialize_agentissue_codex_cli_runner_run_gate
agentissue-codex-runner-flow
--synthetic-staging-root
--execution-gate-root
--first-run-handoff-root
--workflow-check-root
--run-gate-root
read_boundary
```

The README hunks that belong to this change set are the ten
`agentissue-bench-codex-cli-runner-*` bullets. Earlier
`agentissue-bench-lagent239-*` research packets are useful historical evidence,
but they are not part of this runner-flow publication change set.

## Exclude From The Change Set

Do not stage unrelated benchmark exploration, remote-GPU route work, ALE
readiness work, SWE-Bench Pro packets, PerfBench packets, APEX packets,
TheAgentCompany packets, local runtime state, run history, credentials, raw
artifacts, private job roots, or generated temporary staging directories.

The publication change set must not include:

```text
.local/
.goal-harness/
~/.codex/
trajectory.json
screenshot.png
raw issue body
raw patch content
raw logs
credential values
API keys
uploads
submits
public ranking paths
```

## Validation Before Commit Or PR

Run the full runner-flow smoke chain:

```bash
python3 examples/agentissue-bench-codex-cli-runner-contract-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-flow-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py &&
python3 examples/agentissue-bench-codex-cli-runner-publication-change-set-smoke.py
```

Then compile and scan only the publication surfaces:

```bash
python3 -m py_compile \
  goal_harness/benchmark.py \
  goal_harness/cli.py \
  goal_harness/status.py \
  examples/agentissue-bench-codex-cli-runner-contract-smoke.py \
  examples/agentissue-bench-codex-cli-runner-flow-smoke.py \
  examples/agentissue-bench-codex-cli-runner-dry-run-wrapper-smoke.py \
  examples/agentissue-bench-codex-cli-runner-synthetic-staging-smoke.py \
  examples/agentissue-bench-codex-cli-runner-execution-gate-smoke.py \
  examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py \
  examples/agentissue-bench-codex-cli-runner-workflow-check-smoke.py \
  examples/agentissue-bench-codex-cli-runner-run-gate-smoke.py \
  examples/agentissue-bench-codex-cli-runner-pr-ready-packet-smoke.py \
  examples/agentissue-bench-codex-cli-runner-publication-change-set-smoke.py

goal-harness check \
  --scan-path goal_harness/benchmark.py \
  --scan-path goal_harness/cli.py \
  --scan-path goal_harness/status.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-contract-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-flow-plan-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-dry-run-wrapper-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-synthetic-staging-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-execution-gate-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-first-run-handoff-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-workflow-check-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-run-gate-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-pr-ready-packet-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-publication-change-set-v0.md
```

Commit or PR creation may proceed only after the hunk-level staged diff shows
no unrelated benchmark lanes and the public/private scan stays clean.
