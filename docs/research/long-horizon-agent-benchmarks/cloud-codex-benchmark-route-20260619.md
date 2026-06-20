# Cloud ECS Benchmark Host Route 2026-06-19

Status: default route selected; remote Codex CLI auth and tiny execution smoke
are ready through a local-private network route. Benchmark execution still
requires per-family no-upload readiness and task/data gates.

## Decision

Use an exclusive cloud ECS benchmark host as the default route for the next
Terminal-Bench, SkillsBench, and Agents' Last Exam runs.

The route is:

1. SSH to the dedicated benchmark host through the operator-approved access
   path.
2. Run Codex CLI on that host.
3. Keep benchmark source checkouts, containers, task data, runner dependencies,
   raw artifacts, and compact reducers on that host.
4. Write only compact public-safe evidence back to Goal Harness.

The comparison baseline for product claims is real Codex Goal mode, not a
Codex CLI polling loop. If the cloud host can run `codex exec` but the benchmark
runner cannot prove a stable `/goal` invocation and persistent goal state, the
run remains a readiness or unverified slash-goal experiment. It should not be
paired with a Goal Harness treatment for uplift claims until that baseline
trigger is proven or an equivalent supported Codex Goal surface is documented.

Goal Harness should not need to understand the SSH jump path, remote file
bridge, or command relay in the hot path. Once the host is reachable and Codex
is authenticated there by the operator, benchmark execution should look like a
normal single-host developer workflow.

If the operator access path uses a jump host, GSSAPI, or another expensive SSH
handshake, establish one short-lived SSH ControlMaster/ControlPath connection
for the benchmark slice and reuse it for bounded probes, source staging, and
runner launch commands. Keep those commands mostly serial when authentication
is sensitive to concurrency, and close the master in cleanup. This reduces
connection flakiness without teaching Goal Harness private SSH topology.
Public evidence should record only that the SSH alias was reachable and the
slice used a short-lived multiplexed SSH session; private host names, keys,
jump-host details, control paths, and shell history stay out of commits.

For long-running benchmark jobs, pair the multiplexed SSH path with a persistent
remote `tmux` session. Launch the runner inside that session, detach, then
observe via compact artifacts or bounded `tmux capture-pane` reads. This keeps
benchmark execution alive across local Codex app restarts, laptop network
changes, or SSH master expiry. Treat the session name and working directory as
operator-private details; public notes may record only that the run used a
persistent remote session and compact no-upload evidence.

In practice, treat the SSH path as serial by default. Avoid parallel `ssh` or
`rsync` probes through the same jump-host path unless the connection has been
explicitly stress-tested; GSSAPI-backed paths can fail transiently under rapid
or concurrent handshakes even when the ticket is still valid. On failure,
prefer a short backoff plus a single retry before projecting a user gate.

When the cloud host cannot fetch a public benchmark source directly, stage the
source from the operator machine as a single archive rather than thousands of
small files through `rsync`. From macOS, build that archive with
`COPYFILE_DISABLE=1` and xattrs disabled so AppleDouble `._*` files and
extended attributes do not pollute the remote checkout or produce noisy remote
tar output:

```bash
COPYFILE_DISABLE=1 tar --no-xattrs -C /tmp -czf benchmark-source.tgz upstream-checkout
scp benchmark-source.tgz benchmark-host:/path/to/upstream-clean/
```

After extraction, verify `git status --short --branch` is clean before treating
the checkout as upstream-close. If a previous archive already produced `._*`
files, delete them on the remote checkout and re-run the clean-status check
before any runner preflight.

If the archive includes `.git` metadata and is extracted under a different user
or privilege boundary, Git may reject the checkout as a dubious repository.
Either prefer a source-only archive with an explicit upstream marker, or add a
bounded `safe.directory` entry for the staged checkout before running
`git status`. Keep that exception local to the benchmark host setup; do not
commit host-specific paths.

The same staging rule applies to runner dependencies pinned to public Git
repositories. If the host cannot fetch a Git dependency directly, stage the
dependency source as its own upstream-close checkout, then patch only a
temporary run-work copy to use a local `path` source. Keep the upstream-clean
benchmark checkout unmodified, record the dependency commit, and reduce the
result to a compact readiness or blocker. This avoids turning network fetch
failures into benchmark runner failures.

Assume the cloud host starts from a small tool surface. Use POSIX-ish `grep`,
`find`, `git`, `python`, and runner commands in remote bootstrap snippets unless
the bootstrap probe has already confirmed tools such as `rg`.

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

With a dedicated ECS benchmark host, that complexity is no longer the default
product path. The benchmark bottleneck should move back to cloud host
operations, runner setup, task selection, no-upload execution, compact result
reduction, and failure attribution.

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

The cloud ECS host should satisfy this compact checklist before a benchmark
run:

- SSH alias works from the operator machine.
- Codex CLI is installed on the cloud host.
- The operator completes Codex auth on the cloud host; no auth files are copied
  from another machine.
- If direct network egress to the model provider is unavailable, an
  operator-approved loopback-only proxy or tunnel is active for the run.
- A tiny `codex exec` smoke succeeds before any benchmark task starts.
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
| Terminal-Bench | Run Codex CLI and the runner directly on the cloud host; use the Codex app-server `thread/goal/set` path for real Goal-mode baseline automation once the host reproduces the local proof. | Pick a bounded no-upload case, verify Docker-compatible runtime and registry egress, then capture compact `thread/goal/get` evidence for the baseline arm before any paired claim. |
| SkillsBench | Run BenchFlow and Codex CLI on the cloud host; compare only after the app-server Goal baseline seam is wired into the runner or a manual `/goal` fallback is explicitly labeled. | Reproduce persistent Goal-state entry on the cloud host and keep slash-prefixed prompts classified as readiness/unverified experiments. |
| Agents' Last Exam | Run upstream-close ALE local-Docker route on the cloud host; use Codex Goal baseline only after task-data/image gates and the app-server Goal seam are ready. | Resolve task-data access, Docker/registry egress, disk budget, and cloud-host Goal-state evidence before formal paired claims. |

## Claim Boundary

This note is a route decision, not benchmark score evidence. It may claim only
that the default route moved from split-control to dedicated cloud-host Codex
execution. It must not claim benchmark uplift, task success, leaderboard
standing, or Goal Harness effectiveness until compact run evidence exists.
