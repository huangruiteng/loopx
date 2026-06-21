# Terminal-Bench No-Submit Boundary Probe V0

Checked at: 2026-06-07T23:25:00+08:00.

This note turns the Terminal-Bench official-pilot readiness shell into a
no-submit runner-boundary probe. It is still local-only: it does not run
Terminal-Bench, Harbor, Docker, Codex, model APIs, cloud sandboxes, paid
compute, or leaderboard upload paths.

## Purpose

The probe answers one question before any real benchmark work:

Can LoopX record the public runner identity, planned agent command
boundary, submit eligibility, expected output surface, and stop conditions for a
Terminal-Bench pilot without crossing the execution boundary?

The expected payload schema is `runner_boundary_probe_v0`. It feeds future
`benchmark_run_v0` and `benchmark_result_v0` events, but it is not itself task
evidence and must keep all official score fields as `not_run`.

## Allowed Now

- Record public runner candidates and inspected public commits.
- Record command templates with placeholders such as `<model>` and
  `<private-output-dir>`.
- Record the two comparison modes: `bare_codex_cli` and
  `passive_loopx_wrapper`.
- Record the expected passive output files for future `benchmark_run_v0`
  ingestion.
- Record that every command template is `execution_authorized = false`,
  `submit_eligible = false`, and `real_run = false`.

## Forbidden Now

Stop before:

- executing `harbor run`, `tb run`, `codex exec`, or any custom agent wrapper;
- starting Docker or any cloud sandbox;
- invoking a model API, paid compute, or external evaluator;
- using upload or leaderboard submission paths;
- changing official task files, prompts, tests, timeouts, resources, scoring, or
  runner code;
- copying credentials, host absolute paths, private runner logs, internal docs,
  raw Codex session JSONL, or raw thread history into public artifacts;
- claiming official pass/fail, reward, accuracy, or leaderboard uplift.

## Payload Contract

Every no-submit boundary probe should contain:

| Field | Rule |
| --- | --- |
| `schema_version` | `runner_boundary_probe_v0`. |
| `decision_id` | `terminal_bench_official_pilot_decision_packet_v0`. |
| `benchmark_id` | `terminal-bench@2.0`. |
| `probe_state` | `no_submit_boundary_only`. |
| `real_run` | `false`. |
| `submit_eligible` | `false`. |
| `trace_publicness` | `public_boundary_probe_only`. |
| `runner_sources` | Public runner name, role, repo URL, and inspected commit. |
| `mode_boundaries` | One entry each for `bare_codex_cli` and `passive_loopx_wrapper`. |
| `expected_future_events` | `benchmark_run_v0` per mode and one `benchmark_result_v0` comparison. |
| `stop_conditions` | All forbidden surfaces listed above. |

`passive_loopx_wrapper` means LoopX reads already-produced
official runner outputs after a validated run exists. It does not mean a custom
agent wrapper is authorized. The custom `--agent-import-path` path remains a
later local-only experiment gate.

## Smoke

The deterministic smoke is:

```bash
python3 examples/terminal-bench-no-submit-boundary-probe-smoke.py
```

It constructs a compact public-safe `runner_boundary_probe_v0` payload and
asserts that no command is authorized, no submit path is enabled, no real run is
claimed, and no private surface marker appears in the payload or this note.
