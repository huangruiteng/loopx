# Remote GPU Benchmark Route v0

Date: 2026-06-12

Purpose: evaluate a safer remote execution route for long-horizon benchmarks
after the local SWE-Marathon `rust-c-compiler` packet hit local
Docker/Colima memory and disk capacity blockers.

This note is a route-readiness and credential-isolation packet only. It does
not connect to the remote host, start benchmark tasks, run Docker images,
invoke Codex, invoke model APIs, copy credentials, upload artifacts, or read
private benchmark trajectories.

## Local Connector Observation

The local interactive zsh command `to` is a shell function loaded from
`~/.zshrc_local`. Its shape is SSH to a target carried by environment
variables:

```bash
ssh -p "$AI_PORT" root@"$AI_ADDR"
```

The concrete address and port are intentionally not recorded here. Non-
interactive shells did not load `to` by default, so automation should either
invoke an interactive shell intentionally or use a direct SSH command only
after confirming the environment variables are present.

## Why This Route Helps

The local `loopx-bench` Colima profile currently has 4 CPUs, 8 GiB
memory, and 30 GiB virtual disk; `rust-c-compiler` declares 4 CPUs, 16 GiB
memory, and 20 GiB storage. A remote GPU development host is likely to have
more CPU, memory, storage, Docker/NVIDIA runtime, and bandwidth for long
benchmark setup probes.

This route is useful only if it preserves two boundaries:

- the remote host is shared with other users, so it must not receive the
  operator's Codex auth/session material;
- benchmark artifacts must remain local/private and compact, with no upload,
  leaderboard, publish, or submit path unless explicitly approved later.

## Credential Isolation Policy

Never sync these paths or values to the remote host:

- `~/.codex/`
- Codex CLI auth or ChatGPT sign-in state
- OpenAI/OpenRouter/API keys
- `.env`, shell histories, private config files, and session logs
- SSH private keys
- LoopX runtime history under `~/.codex/loopx/`
- raw benchmark trajectories, screenshots, hidden refs, or task solution/test
  bodies

Remote benchmark work should use an isolated workspace with private
permissions:

```bash
umask 077
mkdir -p "$REMOTE_WORK"
chmod 700 "$REMOTE_WORK"
```

If a future scored benchmark requires Codex on the remote host, stop for an
explicit credential decision. Safer options to evaluate before that point:

1. keep Codex/model invocation on the local machine and use the remote host
   only for environment/provider readiness;
2. run only no-agent setup probes remotely;
3. use a dedicated non-shared Unix user or isolated container if remote Codex
   auth is ever required;
4. use a short-lived scoped auth mechanism only after the owner explicitly
   approves the risk.

## Sync Strategy

Prefer a clean public source sync over copying the live local runtime:

Option A: clone/pull the public repository on the remote host.

```bash
git clone https://github.com/huangruiteng/loopx "$REMOTE_WORK/loopx"
```

Option B: rsync the local checkout with an allowlist-style exclude set.

```bash
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.loopx/' \
  --exclude '.local/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'node_modules/' \
  --exclude '.venv/' \
  ./ "$REMOTE_WORK/loopx/"
```

Do not sync `~/.codex`, local LoopX global registry, local active goal
runtime, or local benchmark run artifacts.

On the remote host, install LoopX into the isolated workspace rather
than a shared home-level release:

```bash
cd "$REMOTE_WORK/loopx"
LOOPX_BIN_DIR="$REMOTE_WORK/bin" \
LOOPX_RELEASES_DIR="$REMOTE_WORK/releases" \
LOOPX_INSTALL_SKILL=0 \
LOOPX_INSTALL_CANARY=0 \
LOOPX_SHELL_PROFILE=/dev/null \
CODEX_HOME="$REMOTE_WORK/codex-empty" \
./scripts/install-local.sh
```

This publishes the CLI and docs/examples without installing Codex skills or
touching the operator's Codex home.

## First Remote Probe

The first remote probe should be read-only and no-auth. It should report only
compact readiness facts:

- OS/kernel class;
- CPU count;
- memory total;
- disk free in the isolated workspace parent;
- Docker availability and server version;
- whether NVIDIA GPUs are visible, with model and memory only;
- whether the current user/workspace permissions are private enough;
- whether Python 3.11+, git, uv, and rsync are available.

Avoid commands that print environment variables, shell history, credential
paths, home-directory listings, process command lines, or other users'
workloads.

## Benchmark Eligibility Gate

Do not run a real benchmark remotely until all are true:

- remote workspace is isolated and synced without credentials;
- LoopX CLI runs remotely from the isolated release path;
- Docker/provider capacity satisfies the selected benchmark envelope;
- no-upload/no-leaderboard command boundary is documented;
- Codex credential strategy is explicit and approved;
- result reduction writes only compact `benchmark_run_v0` /
  `benchmark_result_v0` style evidence;
- the selected task's body, solution, test body, raw trajectory, screenshot,
  and hidden refs remain unread unless the benchmark protocol explicitly
  allows them for the chosen role.

## Current Verdict

The remote GPU route is worth evaluating as a provider-readiness lane for any
Docker-heavy benchmark, not only the first local-capacity incident that
triggered this note. A later local cleanup made this more important: local
Docker images and build cache may disappear between benchmark slices, while
compact ledgers and run-history evidence remain intact. Terminal-Bench,
SkillsBench, and ALE should therefore all be eligible for the same split-control
route when their local blocker is Docker/provider capacity rather than task
semantics.

This route is still not blanket approval for scored benchmark execution. The
next bounded step remains a no-auth remote readiness probe or route-specific
sync dry-run that proves credentials are excluded before any remote install,
Docker pull/run, benchmark setup, Codex/model invocation, upload, or submit.
