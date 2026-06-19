# Cloud Codex Benchmark Route 2026-06-19

Status: default route selected; benchmark execution still requires per-family
no-upload readiness and task/data gates.

## Decision

Use an exclusive cloud benchmark host as the default route for the next
Terminal-Bench, SkillsBench, and Agents' Last Exam runs.

The route is:

1. SSH to the dedicated benchmark host through the operator-approved access
   path.
2. Run Codex CLI on that host.
3. Keep benchmark source checkouts, containers, task data, runner dependencies,
   raw artifacts, and compact reducers on that host.
4. Write only compact public-safe evidence back to Goal Harness.

Goal Harness should not need to understand the SSH jump path, remote file
bridge, or command relay in the hot path. Once the host is reachable and Codex
is authenticated there by the operator, benchmark execution should look like a
normal single-host developer workflow.

## Why This Replaces The Default Split-Control Route

The earlier split-control route was the right safety choice for shared hosts:
Codex auth/model/state stayed local while the remote side handled Docker and
runner dependencies. That avoided credential movement, but it also introduced a
large amount of route plumbing:

- host-local ACP relays;
- remote command/file bridges;
- local-driver / remote-sandbox materializers;
- bridge probes that could prove transport without proving a real benchmark
  run.

With a dedicated benchmark host, that complexity is no longer the default
product path. The benchmark bottleneck should move back to runner setup, task
selection, no-upload execution, compact result reduction, and failure
attribution.

Split-control remains useful as a fallback or research route when credentials
cannot live on the execution host, but it should not consume the next benchmark
turn unless the cloud route is blocked by a concrete auth, policy, or host
gate. New split-control bridge work should not land on the main benchmark
route by default.

Near-term attention should therefore go to the cloud-host smoke batch. Existing
split-control code, docs, and smokes are technical assets: keep the durable
contracts and compact reducers, but move any further local-Codex /
remote-executor experiments to an explicitly labeled experimental branch or
separate research issue before adding more mainline code.

## Clean Benchmark Source Policy

Keep internal and external benchmark branches close to upstream:

- prefer upstream `main` or a pinned upstream commit for official runner code;
- keep internal changes on a tiny adapter branch or wrapper layer;
- avoid patching benchmark scoring, task definitions, prompts, or official
  runner behavior unless the change is upstreamable and separately reviewed;
- keep Goal Harness reducers, compact ledgers, route docs, and local evidence
  outside benchmark forks;
- do not commit raw logs, trajectories, hidden task files, credentials, local
  paths, or private host details.

If a fork is needed, it should preserve a small reusable patch set and stay
easy to rebase. Temporary local-Codex split-control hacks should be documented
as route research, not carried forward into benchmark forks or the default
Goal Harness benchmark path.

## Readiness Checklist

The cloud host should satisfy this compact checklist before a benchmark run:

- SSH alias works from the operator machine.
- Codex CLI is installed on the cloud host.
- The operator completes Codex auth on the cloud host; no auth files are copied
  from another machine.
- `git`, Python, `uv`, Node/npm when needed, and a Docker-compatible runtime
  are available.
- A reachable container registry or mirror is configured.
- The workspace has enough disk for task data, images, raw artifacts, and
  compact reducers.
- The first run is a no-upload dry-run or mini-pair.
- Output is reduced to compact `benchmark_run_v0` / `benchmark_result_v0`
  evidence before any claim.

## Current Per-Family Route

| Family | Next route | Remaining gate |
| --- | --- | --- |
| Terminal-Bench | Run Codex CLI and the runner directly on the cloud host. | Pick a bounded no-upload case and verify the Docker-compatible runtime is sufficient for the runner. |
| SkillsBench | Run BenchFlow and Codex CLI on the cloud host; compare base/test mini-pair through compact evidence. | Authenticate Codex on the host and run the first no-upload mini-pair. |
| Agents' Last Exam | Run upstream-close ALE local-Docker route on the cloud host. | Resolve task-data access and disk budget before formal task execution. |

## Claim Boundary

This note is a route decision, not benchmark score evidence. It may claim only
that the default route moved from split-control to dedicated cloud-host Codex
execution. It must not claim benchmark uplift, task success, leaderboard
standing, or Goal Harness effectiveness until compact run evidence exists.
