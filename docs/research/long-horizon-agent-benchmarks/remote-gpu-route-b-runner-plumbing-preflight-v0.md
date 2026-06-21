# Remote GPU Route B Runner Plumbing Preflight v0

Date: 2026-06-12

Purpose: prove the smallest no-score/no-upload runner plumbing path for Route
B after the remote sync and isolated LoopX install. The route keeps the
local driver in control, invokes the remote helper through the SSH command
adapter, and uses only an isolated remote temporary registry/runtime surface.

This preflight did not run Docker task pull/build/run, Harbor, Terminal-Bench,
Codex workers, model APIs, benchmark tasks, uploads, leaderboard paths, submit
actions, raw trajectories, screenshots, hidden refs, task bodies, solution
files, test bodies, or other users' workloads. It did not copy or read Codex
auth, API keys, access tokens, `.env` files, shell histories, SSH private keys,
local LoopX runtime, or credentials.

## Temporary Remote Control Surface

The preflight used a temporary remote registry/runtime/artifact area under the
already-isolated Route B workspace. It did not use the remote user's real
Codex home, shell profile, skills directory, global binaries, or any copied
local runtime.

Compact setup result:

```text
route_b_preflight_bootstrap_ok=true
runner_preflight_artifact_dir_exists=true
runner_preflight_registry_exists=true
runner_preflight_runtime_dir_exists=true
remote_codex_auth_json_found=false
credential_values_printed=false
```

## CLI Contract Boundary

The first attempted shape combined the bridge contract and preflight guard in
one command. That failed fast as a CLI contract rule rather than starting any
runner:

```text
combined_cli_bridge_plus_preflight_ok=false
combined_error=--cli-bridge-contract cannot be combined with --preflight-guard
real_runner_invoked=false
real_codex_invoked=false
docker_task_started=false
task_material_read=false
upload_invoked=false
```

The route therefore uses two separate dry-run checks:

1. `--cli-bridge-contract`
2. `--preflight-guard`

## Bridge Contract Dry-Run

```text
bridge_exit=0
bridge_json=true
bridge_ok=true
bridge_dry_run=true
bridge_appended=false
bridge_classification=terminal_bench_codex_loopx_cli_bridge_contract_runner_fixture_v0
bridge_preflight_guard=false
bridge_cli_bridge_contract=true
bridge_cli_bridge_trace_observed=true
bridge_real_runner_invoked=false
bridge_real_codex_invoked=false
bridge_auth_values_read=false
bridge_submit_eligible=false
```

## Preflight Guard Dry-Run

```text
preflight_exit=0
preflight_json=true
preflight_ok=true
preflight_dry_run=true
preflight_appended=false
preflight_classification=terminal_bench_codex_loopx_preflight_guard_v0
preflight_preflight_guard=true
preflight_cli_bridge_contract=false
preflight_cli_bridge_trace_observed=false
preflight_real_runner_invoked=false
preflight_real_codex_invoked=false
preflight_auth_values_read=false
preflight_submit_eligible=false
docker_task_started=false
task_material_read=false
upload_invoked=false
```

## Decision

Route B is now runner-plumbing-ready for no-score/no-upload LoopX
benchmark preparation. The remote command adapter can invoke the isolated
LoopX helper, create a temporary registry/runtime, produce compact
Terminal-Bench bridge/preflight events, and preserve the no-run/no-auth
boundary.

This still does not authorize a real benchmark run. The next useful step is
to resume benchmark-candidate readiness scanning, starting with AgentIssue-Bench
unless the owner explicitly pivots back to Terminal-Bench/SWE-Marathon or
authorizes a specific real no-upload run. Any future real run still needs a
separate launch gate for benchmark terms, task-material boundary, model/Codex
budget, Docker task start, and upload/leaderboard exclusion.
