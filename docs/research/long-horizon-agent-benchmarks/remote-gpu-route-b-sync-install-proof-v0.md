# Remote GPU Route B Sync And Isolated Install Proof v0

Date: 2026-06-12

Purpose: record the first controlled Route B real-sync and isolated Goal
Harness helper install on the shared remote GPU development host, while keeping
Codex auth, API keys, session state, shell history, benchmark tasks, and model
calls off the remote host.

This proof did not run Docker task pull/build/run, Codex, model APIs,
benchmark tasks, uploads, leaderboard paths, submit actions, raw trajectories,
screenshots, hidden refs, task bodies, solution files, test bodies, or other
users' workloads. It did not copy local `~/.codex`, API keys, access tokens,
`.env` files, shell histories, SSH private keys, local LoopX runtime,
or credentials.

## Pre-Sync Checks

Local checks passed before the real sync:

```text
local_diff_check_ok=true
local_loopx_check_ok=true
public_boundary_scan_clean=true
```

The dry-run envelope was rechecked before the real sync:

```text
route_b_rsync_dry_run_ok=true
rsync_number_of_files=328
rsync_total_transferred_bytes=5203755
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

This is a small increase from the prior `326` files / `5,193,320` bytes
dry-run proof. It was treated as non-material because this route plan and the
benchmark README were added after the earlier dry-run, and the manifest
forbidden-path scan remained clean.

## Real Sync Result

The real sync used the same redacted exclude set as the plan:

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

Compact result:

```text
route_b_manifest_scan_ok=true
forbidden_manifest_path_found=false
route_b_real_sync_ok=true
rsync_number_of_files=328
rsync_total_transferred_bytes=5203755
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

No file list, SSH target, host address, port, remote username, or credential
value was recorded.

## Remote Boundary Scan

Post-sync absence scan:

```text
forbidden_codex_found=false
forbidden_loopx_found=false
forbidden_local_found=false
forbidden_env_found=false
forbidden_env_glob_found=false
route_b_remote_boundary_scan_ok=true
```

## Isolated Install Result

LoopX was installed only under the private remote workspace with an
isolated empty Codex home route, skill install disabled, canary install
disabled, and shell-profile modification disabled.

Compact result:

```text
route_b_isolated_install_ok=true
remote_loopx_doctor_ok=true
remote_codex_auth_json_found=false
remote_codex_home_is_empty_route=true
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

One intermediate bare-environment `doctor` check failed because it did not use
the same isolated install environment: the helper was not on `PATH`, and the
doctor expected canary and skill installs that were intentionally disabled.
The follow-up doctor check using the intended isolated environment passed.

## Decision

Route B is now ready for the next no-score/no-upload runner plumbing preflight.
That preflight should exercise only local-driver-to-remote-command wiring and
compact artifact paths. It must still stop before Docker task pull/build/run,
Codex/model invocation, task body consumption, solution/test content, upload,
leaderboard, submit, credential transfer, or any action against other users'
workloads.
