# Remote GPU Route A/B Proof v0

Date: 2026-06-12

Purpose: compare the first two credential-isolated routes for using the shared
remote GPU development host as a benchmark provider while keeping Codex auth on
the local machine.

This proof did not copy `~/.codex`, API keys, Codex session state, shell
histories, `.env` files, local LoopX runtime, raw trajectories,
screenshots, hidden refs, task bodies, solution files, or test bodies to the
remote host. It did not run Codex, model APIs, benchmark tasks, Docker pull,
Docker build, Docker run, upload, leaderboard, publish, or submit actions.

## Route A: Local Driver Plus Remote Docker Provider

Route shape:

```text
local Codex / LoopX driver
  -> local Docker CLI
  -> Docker-over-SSH remote daemon
```

Result:

```text
route_a_target_present=true
route_a_docker_connect_ok=true
client_version=29.2.0
server_version=24.0.9
api_version=1.43
docker_info_ok=true
docker_cpu_count=180
docker_memory_gib=440
docker_driver=fuse-overlayfs
docker_pull_build_run_started=false
codex_home_synced=false
codex_model_invoked=false
benchmark_started=false
```

Important compatibility detail:

- The first Docker-over-SSH attempt failed because the local Docker client
  defaulted to API version `1.53`, while the remote daemon supports up to
  `1.43`.
- Pinning `DOCKER_API_VERSION=1.43` makes the provider wiring work.

Runner-level e2e status:

- Harbor `run` does not expose a no-run/dry-run route; using it would start
  trial/build behavior.
- Harbor `check` is a quality-evaluator command and is model-backed by
  default, so it is not a safe no-model benchmark-runner preflight for this
  heartbeat.
- Therefore Route A is provider-ready but not yet runner-proven. A real Route A
  e2e would require an explicit next step that allows the smallest task
  container preflight or a custom runner shim that stops before task execution.

## Route B: Local Driver Plus SSH Command Adapter

Route shape:

```text
local Codex / LoopX driver
  -> SSH command adapter
  -> private remote workspace
```

Command-adapter result:

```text
route_b_target_present=true
route_b_command_adapter_ok=true
route_b_workspace_exists=true
route_b_workspace_private=true
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

Redacted sync dry-run result:

```text
route_b_rsync_dry_run_ok=true
rsync_number_of_files=326
rsync_total_transferred_bytes=5193320
rsync_real_copy_started=false
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

The dry-run manifest excluded:

- `.git/`
- `.loopx/`
- `.local/`
- `.env`
- `.env.*`
- `.codex/`
- `__pycache__/`
- `*.pyc`
- `node_modules/`
- `.venv/`

No file list was recorded, and no actual copy was performed.

## Decision

Route A is attractive because a benchmark runner that already uses Docker may
work with only `DOCKER_HOST` plus `DOCKER_API_VERSION=1.43`. Its current gap is
the lack of a safe Harbor no-run runner preflight.

Route B is currently the more controllable path for a first end-to-end proof:
the command adapter works, the private workspace exists, and the sync manifest
has a small public-safe dry-run envelope. It still needs an explicit next step
before real sync, isolated remote install, or any benchmark task container.

## Next Safe Step

Prepare a one-time Route B real-sync and isolated-install plan from the dry-run
manifest, with the same excludes and a post-sync boundary scan. Stop before
Docker task pull/build/run, Codex/model invocation, task body consumption,
solution/test content, upload, leaderboard, submit, or credential transfer.
