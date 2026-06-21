# Remote GPU No-Auth Readiness Probe Plan v0

Date: 2026-06-12

Purpose: define the first safe probe for evaluating the shared remote GPU
development host as a benchmark provider, without copying Codex credentials or
starting benchmark work.

This is a plan only. It does not connect to the remote host, sync files, install
LoopX remotely, start Docker, run benchmark tasks, invoke Codex, invoke
model APIs, copy credentials, upload artifacts, use leaderboard paths, inspect
other users' workloads, or print the concrete remote address/port.

## Preconditions

- Local interactive zsh has a `to` function that SSHes to a target represented
  by `$AI_ADDR` and `$AI_PORT`.
- The remote host is shared, so credential isolation is mandatory.
- The first probe may collect only provider-readiness facts.
- A real benchmark run remains blocked until a later explicit execution and
  credential decision.

## SSH Invocation Mode

Preferred command shape for the first probe:

```bash
zsh -ic '
  [[ -n "$AI_ADDR" && -n "$AI_PORT" ]] || exit 71
  ssh -p "$AI_PORT" \
    -o ForwardAgent=no \
    -o PermitLocalCommand=no \
    root@"$AI_ADDR" \
    '"'"'REMOTE_WORK="${REMOTE_WORK:-/tmp/loopx-bench-${USER:-root}}"; umask 077; mkdir -p "$REMOTE_WORK"; chmod 700 "$REMOTE_WORK"; <probe-script>'"'"'
'
```

Rules:

- never echo `$AI_ADDR` or `$AI_PORT`;
- disable SSH agent forwarding;
- do not request environment forwarding; the local OpenSSH client treats
  `-o SendEnv=` as invalid, so omit `SendEnv` instead of passing an empty
  value;
- do not pass local Codex, OpenAI, or LoopX runtime variables;
- keep remote output to compact readiness JSON or key-value lines.

## Private Workspace Shape

Recommended remote workspace:

```bash
REMOTE_WORK="/tmp/loopx-bench-${USER:-root}"
```

Required checks:

```bash
umask 077
mkdir -p "$REMOTE_WORK"
chmod 700 "$REMOTE_WORK"
stat -c '%a %U %G %n' "$REMOTE_WORK"
```

The readiness result should record only whether permissions are private enough,
not raw usernames, group names, or full host paths in public artifacts.

## Redacted Readiness Commands

Remote commands should avoid environment dumps, process lists, shell history,
home-directory listings, and other users' workload inspection.

Allowed compact checks:

```bash
uname -srm
nproc
free -g
df -BG "$REMOTE_WORK"
command -v docker || true
docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}' 2>/dev/null || true
docker info --format 'CPUs={{.NCPU}} MemTotal={{.MemTotal}} DockerRootDir={{.DockerRootDir}}' 2>/dev/null || true
command -v nvidia-smi || true
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true
command -v python3 || true
python3 --version 2>/dev/null || true
command -v git || true
git --version 2>/dev/null || true
command -v uv || true
uv --version 2>/dev/null || true
command -v rsync || true
rsync --version 2>/dev/null | head -1 || true
```

Forbidden remote checks:

- `env`, `printenv`, shell history, `ps aux`, `docker ps` with full command
  lines, home-directory recursive listings, credential path listings, or other
  users' job/process inspection;
- any Docker pull/build/run;
- any benchmark checkout, task image, Harbor run, Codex invocation, model/API
  call, upload, leaderboard, publish, or submit action.

## Expected Compact Fields

The probe output should reduce to these fields:

```text
ssh_target_present=true|false
workspace_private=true|false
os_class=<kernel family only>
cpu_count=<integer>
memory_gib=<integer or unknown>
workspace_free_gib=<integer or unknown>
docker_available=true|false
docker_server_version=<version or unknown>
docker_cpu_count=<integer or unknown>
docker_memory_gib=<integer or unknown>
nvidia_smi_available=true|false
gpu_count=<integer or unknown>
gpu_memory_gib_total=<integer or unknown>
python3_available=true|false
git_available=true|false
uv_available=true|false
rsync_available=true|false
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

Do not store raw hostnames, IPs, ports, usernames, group names, environment
variables, process command lines, or full remote paths in public docs.

## Sync Dry-Run Plan

If and only if the no-auth probe is clean, the next step may be a local dry-run
of the sync manifest. It should not connect or copy yet:

```bash
rsync -azn --delete \
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

Before any real sync, add explicit excludes for any newly observed private or
generated paths. The sync must not include `~/.codex`, local LoopX
global runtime, benchmark run outputs, shell history, credentials, hidden refs,
or raw trajectories.

## Isolated LoopX Install Envelope

If sync is later approved and completed, install remotely with:

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

This keeps the remote LoopX release self-contained and prevents Codex
skill installation or Codex auth/session reuse.

## Stop Rules

Stop before:

- connecting if `$AI_ADDR` or `$AI_PORT` would be printed;
- SSH agent forwarding;
- syncing files;
- remote LoopX install;
- Docker pull/build/run;
- benchmark checkout or task execution;
- Codex/model/API invocation;
- copying `~/.codex`, API keys, SSH private keys, shell histories, `.env`
  files, local LoopX runtime, raw trajectories, screenshots, hidden
  refs, task bodies, solution files, or test bodies;
- inspecting other users' processes, jobs, home directories, or Docker
  workloads;
- upload, leaderboard, publish, or submit.

## Decision

The next executable action may be a single no-auth remote provider-readiness
probe that emits only compact readiness fields. It is still not a benchmark
run and does not authorize credential transfer.
