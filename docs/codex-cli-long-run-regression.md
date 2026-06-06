# Codex CLI Long-Run Regression Spec

Goal Harness needs a low-frequency regression that proves a replaceable worker
can keep advancing a small goal for several turns from durable state alone. The
first version should be isolated, public-safe, and independent of any real
Codex App thread history.

## Scope

- Start from an empty isolated `HOME`, runtime root, global registry, project
  registry, and active state fixture.
- Use one small synthetic Goal Harness task that can complete in `3-5` worker
  steps.
- Run through Codex CLI or a narrow shim only after the fixture contract is
  stable. The spec smoke does not invoke Codex CLI yet.
- Record a JSONL run log with one row per worker step.
- Use the normal Goal Harness guard: `quota should-run` before work, validated
  artifact or state writeback before `quota spend-slot`.
- Do not depend on real session history, current chat context, browser state,
  user profile files, external services, or existing local automations.

## Worker Step Contract

Each worker step should do exactly one bounded transition:

1. Read the isolated global registry and active state.
2. Run `quota should-run --goal-id <fixture-goal>`.
3. If `should_run=false`, write a no-spend stop row and exit the sequence.
4. If `should_run=true`, perform one public-safe fixture action.
5. Validate the action with a deterministic local check.
6. Write back a durable event or active-state update.
7. Spend exactly one quota slot only after validation and writeback.

## Run Log JSONL Schema

Each row must contain:

| Field | Meaning |
| --- | --- |
| `step_index` | 1-based worker step number. |
| `started_at` / `finished_at` | ISO timestamps for timing. |
| `duration_ms` | Wall-clock duration for the step. |
| `goal_id` | Fixture goal id. |
| `status_before` / `status_after` | Projected status before and after the step. |
| `should_run_before` | Result of `quota should-run` before work. |
| `action_kind` | Fixture action performed, or `no_spend_stop`. |
| `artifact_path` | Relative path to the produced fixture artifact when any. |
| `validation` | Deterministic validation command and pass/fail result. |
| `writeback_event` | Classification or active-state mutation written. |
| `spend_event` | Quota spend event id/path, or null when no spend occurred. |

## Pass Criteria

- The run completes `3-5` worker steps without reading real session history.
- Every completed work step has a validation result, writeback event, and one
  quota spend event.
- No step spends when `should_run_before=false`.
- The final status is terminal for the fixture, or the run log records the exact
  public-safe blocker.
- The isolated runtime contains enough event history to reconstruct the current
  fixture state after deleting the worker process.

## First Runner Shim

The first executable regression is a narrow Goal Harness CLI shim:

```bash
python3 examples/codex-cli-long-run-regression-runner-smoke.py
```

It still does not invoke Codex CLI. Instead, it proves the fixture and log
contract by running exactly `3` isolated worker steps through the normal Goal
Harness CLI surfaces: `status`, `quota should-run`, `refresh-state`, and
`quota spend-slot`. Each step writes one public fixture artifact, validates it,
records one work event, records one spend event, and appends one JSONL row. This
keeps the regression deterministic while leaving a clear path for replacing the
shim action with a real Codex CLI worker later.

## Failure Criteria

- Any worker reads or requires real chat/session history.
- Any step spends before validation and writeback.
- Any step mutates files outside the isolated fixture root.
- Any log row contains private local paths, credentials, raw thread logs, or
  external-service identifiers.

## Later Optional Extension

After the empty-state regression is stable, add fixed session-history replay
fixtures. Replay fixtures should be compact synthetic transcripts, not copies of
real user sessions, and should verify that replayed context updates the same
durable state/event ledger as the empty-state path.
