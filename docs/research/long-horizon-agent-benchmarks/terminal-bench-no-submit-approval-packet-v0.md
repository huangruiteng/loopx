# Terminal-Bench No-Submit Approval Packet V0

Checked at: 2026-06-08T02:44:00+08:00.

This packet is the smallest operator-approval shape for a future
Terminal-Bench or Harbor no-submit runner setup check. It is not approval by
itself. It does not run Terminal-Bench, Harbor, Docker, Codex, model APIs,
cloud sandboxes, paid compute, or leaderboard upload paths.

## Purpose

The packet answers one operator question:

If a future agent asks to verify Terminal-Bench or Harbor setup without
submitting or executing benchmark tasks, what exact surfaces may it touch, what
must remain forbidden, what artifacts should it leave, and how would those
artifacts later enter compact `benchmark_run_v0` and `benchmark_result_v0`
history rows?

The expected packet schema is `terminal_bench_no_submit_approval_packet_v0`.
The packet is a gate artifact, not a runner output. Current state must remain:

- `packet_id = terminal_bench_no_submit_setup_check_packet_v0`
- `benchmark_id = terminal-bench@2.0`
- `approval_state = requested`
- `execution_authorized = false`
- `submit_eligible = false`
- `real_run = false`

## Allowed Before Approval

Only local validation of this packet is allowed before an operator approves the
future setup check:

```bash
python3 examples/terminal-bench-no-submit-approval-packet-smoke.py
```

## Candidate Commands After Approval

If the operator approves this no-submit setup check, the candidate command set
is limited to these exact shapes:

```bash
git ls-remote https://github.com/laude-institute/harbor HEAD
git ls-remote https://github.com/harbor-framework/terminal-bench HEAD
harbor --help
tb --help
loopx history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>
loopx history append-benchmark-result --benchmark-result-json <benchmark-result-v0.json>
```

The `harbor --help` and `tb --help` checks are allowed only as CLI surface
inspection after approval. They must not be replaced by `harbor run`, `tb run`,
or any command that starts a benchmark task, sandbox, agent, evaluator, or
submission path.

The LoopX append commands are allowed only after a compact public-safe
JSON object exists. They must not ingest raw runner logs, private traces, host
absolute paths, raw session histories, credentials, or local artifact paths.

## Forbidden Surfaces

Stop before:

- executing `harbor run`, `tb run`, `codex exec`, or a custom agent wrapper;
- starting Docker, a container runtime, or any cloud sandbox;
- invoking Codex, a model API, paid compute, or an external evaluator;
- uploading, submitting, or preparing a leaderboard trace;
- modifying official tasks, prompts, tests, timeouts, resources, scoring, or
  runner code;
- copying credentials, host absolute paths, private runner logs, internal docs,
  raw Codex session JSONL, raw thread history, or private traces into public
  artifacts;
- claiming official pass/fail, reward, accuracy, leaderboard uplift, or paper
  evidence.

## Side-Effect Budget

| Surface | Before approval | After approval for this packet |
| --- | --- | --- |
| Local packet smoke | Allowed | Allowed |
| Public git metadata | Forbidden | Allowed for the two exact `git ls-remote` commands |
| CLI help text | Forbidden | Allowed for `harbor --help` and `tb --help` only |
| Docker or containers | Forbidden | Forbidden |
| Codex CLI or model APIs | Forbidden | Forbidden |
| Cloud or paid compute | Forbidden | Forbidden |
| Leaderboard upload | Forbidden | Forbidden |
| Official task mutation | Forbidden | Forbidden |

## Expected Public Artifacts

After an approved no-submit setup check, the agent may produce only compact
public-safe artifacts:

- `terminal_bench_no_submit_setup_check_v0.json`
- `benchmark_run_v0` shell for `bare_codex_cli_no_submit_setup`
- `benchmark_run_v0` shell for `passive_loopx_wrapper_no_submit_setup`
- optional `benchmark_result_v0` readiness shell with
  `official_task_score.kind = not_run`

The artifacts may contain public repository names, inspected public commits,
command-shape labels, no-submit mode names, and stop-condition checks. They must
not contain raw runner logs, local paths, credentials, private traces, task
outputs, official scores, or leaderboard eligibility claims.

## Ingestion Plan

The future no-submit setup check enters LoopX only as compact history:

1. A `benchmark_run_v0` row records each no-submit setup mode with
   `runner_mode = setup_check_no_submit`, `real_run = false`,
   `submit_eligible = false`, and `trace_publicness =
   public_no_submit_setup_check`.
2. A `benchmark_result_v0` row may be appended only if it remains
   readiness-only with `terminal_state = readiness_only` and
   `official_task_score.kind = not_run`.
3. The comparison or report lane may cite this packet only as approval-boundary
   evidence. It must not promote the row into official benchmark evidence.

## Stop Conditions

Stop and ask the operator again if:

- any command needs a runner execution, Docker, model call, cloud sandbox, paid
  compute, or external evaluator;
- any command would write outside compact public-safe LoopX history;
- any artifact would include a host absolute path, credential, private trace,
  raw log, or raw session history;
- the benchmark terms, Harbor protocol, Terminal-Bench protocol, or submission
  eligibility are ambiguous;
- an agent wants to claim official score, pass/fail, reward, accuracy,
  leaderboard uplift, or paper-ready evidence.

## Smoke

The deterministic smoke is:

```bash
python3 examples/terminal-bench-no-submit-approval-packet-smoke.py
```

It constructs a compact
`terminal_bench_no_submit_approval_packet_v0` payload and asserts that the
current packet does not authorize execution, submission, Docker, Codex/model
APIs, cloud or paid compute, private traces, raw logs, or leaderboard claims.
