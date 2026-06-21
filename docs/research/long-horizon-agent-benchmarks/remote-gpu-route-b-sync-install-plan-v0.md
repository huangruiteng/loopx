# Remote GPU Route B Sync And Isolated Install Plan v0

Date: 2026-06-12

Purpose: define the first controlled Route B execution step after the redacted
SSH command-adapter and rsync dry-run proof. Route B keeps Codex auth on the
local machine and uses the remote host only as a private execution workspace.

This is a plan only. It does not sync files, install LoopX remotely,
start Docker, run benchmark tasks, invoke Codex, invoke model APIs, copy
credentials, upload artifacts, use leaderboard paths, inspect other users'
workloads, print the concrete remote address or port, read raw trajectories,
or read task bodies, solution files, or test bodies.

## Preconditions

- Route B command adapter proof passed.
- Route B rsync dry-run passed with 326 files and 5,193,320 bytes in the
  would-transfer envelope.
- The remote host has `python3`, `git`, and `rsync`; `uv` is absent but not
  required for `scripts/install-local.sh`.
- Remote workspace permissions are private enough for a shared machine
  (`workspace_private=true` from the provider probe).
- The next execution step still must not run scored tasks, Docker task
  pull/build/run, Codex/model calls, uploads, leaderboard, or submit actions.

## Local Pre-Sync Validation

Before any real sync, rerun these local checks:

```bash
git diff --check -- \
  docs/research/long-horizon-agent-benchmarks/remote-gpu-route-b-sync-install-plan-v0.md \
  docs/research/long-horizon-agent-benchmarks/README.md

loopx check \
  --scan-path docs/research/long-horizon-agent-benchmarks/remote-gpu-route-b-sync-install-plan-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

Then rerun the dry-run manifest and record only compact counts, not file names:

```bash
rsync -azn --delete --stats \
  -e "ssh -p $AI_PORT -o BatchMode=yes -o ConnectTimeout=10 -o ForwardAgent=no -o ClearAllForwardings=yes -o PermitLocalCommand=no -o RequestTTY=no -o StrictHostKeyChecking=yes" \
  --exclude ".git/" \
  --exclude ".loopx/" \
  --exclude ".local/" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude ".codex/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude "node_modules/" \
  --exclude ".venv/" \
  ./ root@"$AI_ADDR":/tmp/loopx-bench-probe/loopx/
```

Do not print `$AI_ADDR`, `$AI_PORT`, file lists, local usernames, remote
usernames, or remote host paths in durable artifacts.

## One-Time Real Sync Envelope

If the dry-run still matches the expected small public-safe envelope, the first
real sync may use the same manifest without `-n`:

```bash
rsync -az --delete --stats \
  -e "ssh -p $AI_PORT -o BatchMode=yes -o ConnectTimeout=10 -o ForwardAgent=no -o ClearAllForwardings=yes -o PermitLocalCommand=no -o RequestTTY=no -o StrictHostKeyChecking=yes" \
  --exclude ".git/" \
  --exclude ".loopx/" \
  --exclude ".local/" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude ".codex/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude "node_modules/" \
  --exclude ".venv/" \
  ./ root@"$AI_ADDR":/tmp/loopx-bench-probe/loopx/
```

Allowed durable output from the real sync:

```text
route_b_real_sync_ok=true|false
rsync_number_of_files=<integer>
rsync_total_transferred_bytes=<integer>
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

Do not store file names, remote path details, or SSH target details.

## Post-Sync Boundary Scan

After the real sync, run a remote absence scan that reports only booleans:

```bash
REMOTE_WORK=/tmp/loopx-bench-probe
ROOT="$REMOTE_WORK/loopx"
for name in .codex .loopx .local .env; do
  if find "$ROOT" -maxdepth 4 -name "$name" -print -quit | grep -q .; then
    echo "forbidden_${name#.}_found=true"
  else
    echo "forbidden_${name#.}_found=false"
  fi
done
if find "$ROOT" -maxdepth 4 -name ".env.*" -print -quit | grep -q .; then
  echo "forbidden_env_glob_found=true"
else
  echo "forbidden_env_glob_found=false"
fi
```

The public-ready pass condition is every `forbidden_*_found=false`.

## Isolated Remote Install

If and only if the post-sync boundary scan is clean, install the LoopX
helper inside the private remote workspace:

```bash
cd /tmp/loopx-bench-probe/loopx
LOOPX_BIN_DIR=/tmp/loopx-bench-probe/bin \
LOOPX_RELEASES_DIR=/tmp/loopx-bench-probe/releases \
LOOPX_INSTALL_SKILL=0 \
LOOPX_INSTALL_CANARY=0 \
LOOPX_SHELL_PROFILE=/dev/null \
CODEX_HOME=/tmp/loopx-bench-probe/codex-empty \
./scripts/install-local.sh
```

The install command must not touch the remote user's real Codex home, shell
profile, skills directory, or global binaries. Its durable output should be
reduced to:

```text
route_b_isolated_install_ok=true|false
remote_loopx_doctor_ok=true|false
remote_codex_home_is_empty_route=true
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

## Stop Rules

Stop before:

- syncing if the dry-run envelope grows unexpectedly or includes private paths;
- writing outside `/tmp/loopx-bench-probe`;
- copying local `~/.codex`, API keys, access tokens, `.env` files, shell
  histories, SSH private keys, local LoopX runtime, raw trajectories,
  screenshots, hidden refs, task bodies, solution files, or test bodies;
- installing into a real remote `CODEX_HOME` or modifying the remote shell
  profile;
- Docker task pull/build/run;
- Codex/model/API invocation;
- benchmark task execution, upload, leaderboard, publish, or submit;
- inspecting other users' processes, jobs, home directories, or Docker
  workloads.

## Next Decision

If real sync, post-sync boundary scan, and isolated install all pass, Route B
can move to a no-upload/no-score runner preflight that exercises only wrapper
plumbing and still stops before task content, Docker task start, Codex/model
calls, uploads, or leaderboard actions.
