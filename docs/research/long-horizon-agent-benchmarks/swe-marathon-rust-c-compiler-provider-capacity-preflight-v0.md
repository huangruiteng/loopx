# SWE-Marathon rust-c-compiler Provider Capacity Preflight v0

Date: 2026-06-12

Purpose: check whether the current local Docker/Colima provider can satisfy
the `rust-c-compiler` no-execution launch packet before any scored
SWE-Marathon run.

This is a provider/capacity preflight only. It did not execute `harbor run`,
build a task image, start a task container, invoke Codex, invoke a model/API,
read credentials, upload artifacts, use leaderboard paths, read task bodies,
read solution files, read test bodies, read raw trajectories, or capture
screenshots.

## Required Envelope

From `tasks/rust-c-compiler/task.toml` routing fields:

| Field | Required |
| --- | ---: |
| CPUs | 4 |
| Memory | 16384 MB |
| Storage | 20480 MB |
| GPUs | 0 |
| Internet | allowed |
| Agent timeout | 21600 seconds |
| Build timeout | 1200 seconds |
| Verifier timeout | 2400 seconds |

## Observed Local Provider

Observed commands:

```bash
docker context show
docker context ls
docker info --format 'ServerVersion={{.ServerVersion}} CPUs={{.NCPU}} MemTotal={{.MemTotal}} DockerRootDir={{.DockerRootDir}} OperatingSystem={{.OperatingSystem}}'
docker system df
colima list
colima status --profile loopx-bench --json
df -g .
```

Observed compact results:

| Check | Observed | Verdict |
| --- | --- | --- |
| Docker CLI | present | pass |
| Docker daemon | server `28.4.0` reachable | pass |
| Docker context | `colima-loopx-bench` | pass |
| Colima profile | `loopx-bench` running | pass |
| Runtime | Docker on Colima / macOS Virtualization.Framework | pass |
| CPU capacity | 4 CPUs | pass, exactly at requirement |
| Memory capacity | 8589934592 bytes / 8 GiB | fail, below 16 GiB requirement |
| Colima virtual disk | 32212254720 bytes / 30 GiB | pass by declared profile size |
| Host free space near workspace | 15 GiB available | fail/headroom risk for 20 GiB envelope |
| Docker images | 18.47 GB, 100% reclaimable, 0 active | possible cleanup candidate, not touched |
| Running containers | 0 | pass |

## Verdict

Do not run `rust-c-compiler` on the current local provider configuration.

The provider is reachable, but the active benchmark profile is configured with
only 8 GiB memory while the task declares 16 GiB. CPU is exactly sufficient.
The Colima virtual disk is nominally 30 GiB, but the host volume currently has
about 15 GiB free near the workspace, below the task's 20 GiB storage envelope.
There is a large inactive Docker image that appears reclaimable, but no cleanup
was performed because deleting local images is a side effect that should be
explicitly approved.

## Safe Next Options

Option A: keep SWE-Marathon as the active lane, but require an owner-approved
local runtime adjustment before any run:

- increase the `loopx-bench` Colima profile memory to at least 16 GiB,
  with a safer target of 20 to 24 GiB if the machine can spare it;
- ensure at least 25 to 30 GiB host free space before task image build/start;
- optionally approve Docker image cleanup only after confirming the inactive
  image is disposable;
- rerun this provider/capacity preflight before a baseline/treatment run.

Option B: treat this as a local-capacity blocker for SWE-Marathon and continue
with the next readiness scan lane:

- AgentIssue-Bench;
- PerfBench;
- SWE-Bench Pro public.

This avoids spending benchmark execution quota while preserving the
SWE-Marathon route for a later, better-provisioned machine.

## Stop Rules

Until the capacity blocker is cleared, stop before:

- `harbor run -p ...`;
- Docker task image build/start;
- Colima profile stop/restart/reconfiguration;
- Docker image deletion/prune;
- Codex/model invocation;
- credential reads;
- uploads, leaderboard, publish, or submit paths;
- task body, solution, test body, raw trajectory, screenshot, or hidden-ref
  reads.
