# Goal Harness Regression Suite

This directory is for low-frequency behavior regressions that check how Goal
Harness CLI contracts are consumed by worker/executor surfaces.

Fast deterministic examples stay under `examples/`. Files here may exercise
real local tools such as Codex CLI when explicitly requested, so they should be
run deliberately during release or major control-plane changes.

## Current Regressions

```bash
python3 regression/external-evidence-observation-real-codex.py
```

Runs the contract-only path. It creates an isolated Goal Harness fixture and
checks two projection contracts:

- explicit `waiting_on=external_evidence` goals return an
  external-evidence observation obligation;
- already-launched long-running work with an observable compact-result poll
  target is treated as read-only external evidence, even when the open todo
  still carries its original `advancement_task/run_eval` metadata.

```bash
python3 regression/quota-executable-backlog-projection.py
```

Runs a CLI-level quota projection regression over an isolated registry/runtime
fixture. It checks that when a P0 external monitor remains open but unchanged
and a P1 advancement todo is executable, `quota should-run` selects the P1
backlog item as `recommended_action`, interaction primary action, and protocol
packet action while keeping the monitor as context.

```bash
python3 regression/external-evidence-observation-real-codex.py --real-codex
```

Additionally invokes the host `codex exec` in `--ephemeral`, read-only mode
with an output schema. This consumes a real Codex run and verifies that the
worker interprets a missing external-evidence handle as a compact blocker
writeback, not a quiet no-op or benchmark execution.

The real path defaults to `--codex-model gpt-5.4-mini` so it does not depend on
the user's Codex CLI default model. Override with `--codex-model <model>` when a
release lane needs a specific model surface.

```bash
python3 regression/agentissue-lagent239-real-codex-runner.py
```

Runs the AgentIssue-Bench `lagent_239` runner contract-only path. It
materializes the private runner wrapper and checks the no-generator-execution,
selected-image, source-extraction, entrypoint eval, compact reducer, and
credential-boundary contracts without invoking Codex or Docker.

```bash
python3 regression/agentissue-lagent239-real-codex-runner.py \
  --real-codex \
  --prompt-path <private-agentissue-prompt.md>
```

Additionally invokes the host `codex exec` plus the selected
`alfin06/agentissue-bench:lagent_239` Docker image. It writes raw prompt,
stdout/stderr, and patch artifacts only under the temporary private regression
root, then prints a compact public-safe score and boundary summary.
