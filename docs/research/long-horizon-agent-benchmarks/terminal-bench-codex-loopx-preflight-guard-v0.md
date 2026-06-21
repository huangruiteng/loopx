# Terminal-Bench Codex LoopX Preflight Guard V0

Checked at: 2026-06-08T21:18:00+08:00.

This note records the no-upload preflight guard for the requested
`codex_loopx` treatment arm. Current V0 is still
`prompt_packet_only_no_cli_bridge`; the guard checks runner readiness and prompt
injection, not real LoopX interface use:

```bash
loopx benchmark run terminal-bench --mode codex-loopx --preflight-guard
```

The guard may probe public local CLI surfaces such as `uvx --version`,
`docker --version`, Docker server availability, and `codex --version`. It does
not run Harbor, Terminal-Bench tasks, Docker task containers, real Codex
workers, model APIs, uploads, shares, paid/cloud execution, or leaderboard
paths.

## Guard Checks

The compact `benchmark_run_v0` preflight event records:

```text
mode=codex_loopx_no_upload_preflight_guard
worker_mode=codex_loopx_cli
source_runner=loopx_terminal_bench_codex_loopx_no_upload_preflight_guard
loopx_inside_case=true
case_semantics_changed_by_harness=true
official_score_comparable_to_native_codex=false
model_plus_harness_pair=true
real_run=false
submit_eligible=false
```

The guard explicitly checks:

```text
runner_surface_checked=true
local_execution_surface_checked=true
codex_cli_surface_checked=true
auth_surface_names_only=true
auth_values_read=false
access_packet_prompt_injection_checked=true
trace_counter_extraction_contract_checked=true
loopx_mode_kwarg_checked=true
loopx_mode_kwarg=codex_loopx
real_interface_use_observed=false
uplift_claim_allowed=false
```

## Counter Semantics

Because this guard does not run a worker, its interaction counters remain
zero-observed:

```text
harness_skill_or_packet_injected=true
loopx_cli_calls.total=0
loopx_state_reads=0
loopx_state_writes=0
case_result_writeback=not_observed_prompt_only_no_cli_bridge
counter_trust_level=preflight_prompt_only_no_cli_bridge
```

This is deliberately different from the fake-worker fixture, where fixture
counter rows are nonzero. The preflight guard proves readiness for a private
no-upload prompt-only repeat and counter extraction; it does not prove bridge
availability or real interface use.

## First Blocker

The guard reports the first local blocker in the same style as the managed
preflight path:

```text
missing_uvx_runner_surface
uvx_runner_surface_unverified
missing_docker_cli_surface
missing_docker_server_surface
missing_codex_cli_surface
codex_auth_value_boundary_violation
no_upload_boundary_not_ready
ready_for_private_managed_no_upload_pilot_review
```

The name `ready_for_private_managed_no_upload_pilot_review` is inherited from
the existing local runner-surface checker. For `codex_loopx`, read it as
`ready_for_private_codex_loopx_no_upload_review`.

## Stop Conditions

Stop before:

- running the real Harbor task;
- starting a Terminal-Bench task container;
- invoking a real Codex worker or model API;
- reading credential values or auth file bodies;
- copying raw prompts, raw traces, local paths, logs, Docker output, sessions,
  or private task artifacts into public notes;
- treating this guard as official task score, real LoopX interface use,
  cost/token evidence, leaderboard readiness, or uplift.

## Smoke

```bash
python3 examples/terminal-bench-codex-loopx-preflight-guard-smoke.py
```

The smoke appends the guard event through a temporary LoopX registry,
reconstructs status, and checks public-safety boundaries.
