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
checks that `quota should-run` returns an external-evidence observation
obligation.

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
