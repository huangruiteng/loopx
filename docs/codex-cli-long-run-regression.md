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
- Run through the deterministic shim by default. Real Codex CLI invocation is
  an explicit low-frequency mode only after the fixture contract is stable.
- Record a JSONL run log with one row per worker step.
- Use the normal Goal Harness guard: `quota should-run` before work, validated
  artifact or state writeback before `quota spend-slot`.
- Do not depend on real session history, current chat context, browser state,
  user profile files, external services, or existing local automations.

## Worker Step Contract

Each worker step should do exactly one bounded transition. The acceptance frame
is the Goal Tick Output Protocol, recorded as
`goal_tick_output_protocol_v0` in each JSONL row:

1. `read_state`: Read the isolated global registry and active state, then run
   `quota should-run --goal-id <fixture-goal>`.
2. `propose_step`: Choose one public-safe fixture action, or record a
   no-spend stop when `should_run=false`.
3. `execute`: Perform the chosen fixture action only when `should_run=true`.
4. `validate`: Validate the action with a deterministic local check.
5. `critic`: Record the continue, terminal, or public-safe blocker judgment.
6. `writeback`: Write back a durable event or active-state update, then spend
   exactly one quota slot only after validation and writeback.

Spend exactly one quota slot only after validation and writeback.

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
| `goal_tick_output_protocol` | `goal_tick_output_protocol_v0` evidence for `read_state`, `propose_step`, `execute`, `validate`, `critic`, and `writeback`. |
| `writeback_event` | Classification or active-state mutation written. |
| `spend_event` | Quota spend event id/path, or null when no spend occurred. |

## Pass Criteria

- The run completes `3-5` worker steps without reading real session history.
- Every completed work step has a validation result, writeback event, and one
  quota spend event.
- Every completed work step has all six Goal Tick phases with evidence:
  `read_state`, `propose_step`, `execute`, `validate`, `critic`, and
  `writeback`.
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
shim action with a real Codex CLI worker later. The shim log also emits
`goal_tick_output_protocol` for every row, using the same six-phase evidence
shape expected from future real-worker runs.

## Real Codex CLI Worker Extension

The runner also supports an explicit, low-frequency real-worker mode:

```bash
python3 examples/codex-cli-long-run-regression-runner-smoke.py \
  --worker-mode real-codex \
  --codex-cli /path/to/codex
```

This mode invokes:

```bash
codex exec --skip-git-repo-check --ephemeral --ignore-user-config \
  --ignore-rules --sandbox workspace-write --ask-for-approval never \
  -C <isolated-fixture-project> <step-prompt>
```

The deterministic Goal Harness CLI shim remains the default public smoke so
ordinary contract checks stay fast and reproducible. The real-worker mode is
opt-in, starts from an empty isolated `HOME` and `CODEX_HOME`, and must not read
real session history or Codex App thread state.

The real-worker mode must reuse the same pass criteria as the shim: `3-5`
bounded worker steps, one JSONL row per step, deterministic validation, durable
writeback, Goal Tick Output Protocol evidence, and exactly one quota spend
after each validated work step. If the worker cannot complete the sequence, the
log should record the public-safe blocker instead of hiding the stop condition
in stdout.

The public contract smoke does not call a real external Codex worker. It uses a
temporary fake executable to verify the invocation shape, isolated environment,
JSONL log, Goal Tick phases, validation, writeback, and spend accounting:

```bash
python3 examples/codex-cli-long-run-real-worker-contract-smoke.py
```

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

## Capability Benchmark Extension

The runner's current fixture proves the control-plane contract but is too easy
to measure Codex task capability. Use
`docs/codex-cli-long-run-benchmark-design.md` for the next benchmark task:
`mini_control_plane_repair_v0`, a `3-5` step isolated control-plane repair with
matching with/without Goal Harness scenarios and `benchmark_result_v0` metrics.
