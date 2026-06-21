# AgentIssue-Bench Codex CLI Runner First-Run Handoff V0

Date: 2026-06-13

## Scope

This packet turns the guarded `lagent_239` execution gate into a no-execute
first-run handoff surface:

```bash
loopx benchmark agentissue-codex-runner-flow \
  --goal-id loopx-meta \
  --tag lagent_239 \
  --first-run-handoff-root <private-gate-root>
```

The command materializes the synthetic staging files, `execution-gate.public.json`,
`first-run-handoff.public.json`, `first-run-handoff.md`, and
`benchmark_run.compact.json`. It still does not run Codex CLI, a model API,
Docker, source extraction, git baseline creation, patch generation, patch
evaluation, upload, submit, or public ranking paths. Passing `--execute`
appends only a compact no-run `benchmark_run_v0` handoff event.

`--first-run-handoff-root`, `--execution-gate-root`, and
`--synthetic-staging-root` are mutually exclusive so one selected tag has one
private packet root.

## Packet Shape

The handoff packet records the command shape:

```text
loopx benchmark agentissue-codex-runner-flow --goal-id <goal-id> --tag lagent_239 --execution-gate-root <private-gate-root> --delivery-batch-scale multi_surface --delivery-outcome outcome_progress --execute
```

It records a private artifact boundary:

```text
public: runner-flow-plan.public.json, execution-gate.public.json, first-run-handoff.public.json, first-run-handoff.md, benchmark_run.compact.json
private: context/, buggy-source/, Patches/lagent_239/
```

It records budget/auth safety:

```text
codex auth values read=false
codex home synced=false
model budget spent by packet=false
shared remote host receives codex auth=false
```

## Compact Event

The compact event uses:

```text
mode=agentissue_codex_cli_runner_first_run_handoff_packet
first_blocker=first_run_handoff_only_no_real_case
real_run=false
submit_eligible=false
leaderboard_evidence=false
```

Validation fields assert that the command shape, private artifact boundary,
expected compact outputs, budget/auth boundary, and safety checklist are
rendered, while all real execution flags remain false.

## Validation

```bash
python3 examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py
python3 -m py_compile \
  loopx/benchmark.py \
  loopx/cli.py \
  examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py
loopx check \
  --scan-path loopx/benchmark.py \
  --scan-path loopx/cli.py \
  --scan-path examples/agentissue-bench-codex-cli-runner-first-run-handoff-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/agentissue-bench-codex-cli-runner-first-run-handoff-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```
