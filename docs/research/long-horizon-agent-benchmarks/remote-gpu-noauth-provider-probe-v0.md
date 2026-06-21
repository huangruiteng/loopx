# Remote GPU No-Auth Provider Probe v0

Date: 2026-06-12

Purpose: record the first redacted provider-readiness result for the shared
remote GPU development host reachable through the local `to` route. This probe
is only a provider capability check. It did not sync files, install Goal
Harness remotely, start Docker containers, run a benchmark task, invoke Codex,
invoke model APIs, copy credentials, upload artifacts, inspect other users'
workloads, or print the concrete remote address or port.

## Method

Local setup used `zsh -f` and sourced only the user's local route file so the
probe could access the `to` route variables without loading the full interactive
shell prompt. The probe used direct SSH with:

- `BatchMode=yes`
- `ForwardAgent=no`
- `ClearAllForwardings=yes`
- `PermitLocalCommand=no`
- `RequestTTY=no`
- `StrictHostKeyChecking=yes`

The initial plan's `-o SendEnv=` option was invalid for the local OpenSSH
client and was removed before the successful probe. No environment variables,
credential values, hostnames, IPs, ports, process lists, shell histories, home
directories, or Docker workloads were printed.

## Result

```text
ssh_target_present=true
ssh_connect_ok=true
workspace_private=true
os_class=Linux
cpu_count=180
memory_gib=440
workspace_free_gib=153
docker_available=true
docker_server_version=24.0.9
docker_cpu_count=180
docker_memory_gib=440
nvidia_smi_available=true
gpu_count=2
gpu_memory_gib_total=191
python3_available=true
git_available=true
uv_available=false
rsync_available=true
credential_values_printed=false
codex_home_synced=false
benchmark_started=false
```

## Interpretation

The remote host is a viable high-capacity benchmark provider candidate:
Docker is reachable, the daemon sees 180 CPUs and 440 GiB memory, the workspace
has 153 GiB free, and NVIDIA GPUs are visible. This clears the shared provider
capacity blocker that stopped the local SWE-Marathon route.

This does not prove that a full benchmark can run yet. The open question is
which e2e architecture can satisfy the benchmark runner while keeping Codex
auth local:

1. Route A: local Codex/LoopX driver plus remote Docker provider.
2. Route B: local Codex/LoopX driver plus SSH command adapter and
   redacted sync.

Both should get a minimal no-upload e2e proof before choosing the first real
benchmark case.

## Next Proofs

- Route A proof: verify the local Docker client can talk to the remote daemon
  through the same SSH target without persisting credentials on the remote host,
  then run the smallest benchmark-runner preflight that exercises Docker
  provider wiring without invoking Codex/model execution or task submission.
- Route B proof: verify an SSH command adapter can run benchmark shell commands
  in the private remote workspace, then run a sync dry-run manifest and the
  smallest no-score/no-upload runner preflight.

Stop before a real scored task, task body consumption, solution/test content,
Docker pull/build/run for task images, Codex/model invocation, upload,
leaderboard, or credential transfer until one of these route proofs is clean.
