# Benchmark Developer Workflow

Goal Harness treats benchmark execution as a developer workflow, not only as a
research activity. A benchmark runner should be something a contributor can
inspect, dry-run, diagnose, and improve without reading maintainer `.local`
state or raw benchmark trajectories.

This document is the stable product entry point for benchmark work. Research
packets and dated route notes still live under
`docs/research/long-horizon-agent-benchmarks/`, but reusable runner behavior
belongs in `goal_harness/`, `examples/`, and this guide.

## Product Shape

The benchmark workflow has four layers:

1. **Select** a benchmark family, task, and arm without exposing private task
   text or reward leakage.
2. **Launch** through an explicit route contract. The default route is now an
   exclusive cloud benchmark host where Codex CLI, the benchmark runner, Docker
   or compatible container runtime, task data, and compact reduction all run in
   one isolated environment. Split-control routes remain useful for constrained
   hosts or route research, but they are not the first choice when a dedicated
   cloud host is available.
3. **Observe** the run through compact handles: pid or job state, readiness
   re-check, materialization, result or blocker, and cleanup state.
4. **Ingest** only public-safe evidence into Goal Harness history, ledger, and
   case analysis.

The user-facing product promise is simple: a developer should be able to tell
what ran, why it was allowed, what blocked it, and what can be tried next,
without seeing credentials, raw logs, raw trajectories, or local machine paths.

## Golden Path

From a fresh checkout:

```bash
python3 -m py_compile goal_harness/*.py goal_harness/benchmark_core/*.py
python3 examples/benchmark-split-control-remote-executor-smoke.py
goal-harness benchmark --help
```

For a real benchmark slice, use this sequence:

1. Run a source and boundary preflight for the target benchmark.
2. Prepare or select the benchmark host route:
   - prefer the default cloud Codex route when the host is dedicated, has
     enough CPU/memory/disk, and can run Codex CLI plus containers directly;
   - use a split-control route only when host credentials, local policy, or
     runner constraints make a single cloud host unsuitable.
3. Produce a launch plan or runner batch only after a fresh readiness re-check.
4. Build benchmark-specific command-adapter facts when the route still needs a
   Goal Harness adapter, such as
   `goal-harness benchmark terminal-bench-command-adapter terminal-bench`.
   When Terminal-Bench uses a remote executor, first reduce the local-driver
   request plus private remote launch result through the launch adapter:
   `goal-harness benchmark terminal-bench-remote-launch-adapter terminal-bench --request-json <private-json> --launch-result-json <private-json>`.
   The launch adapter emits only field presence and compact blocker state; it
   never executes SSH, Docker, Codex, model calls, uploads, or submits. If a
   lower-level private runner already produced remote-executor handles, reduce
   them through a materializer such as
   `goal-harness benchmark terminal-bench-remote-materializer terminal-bench --handle-manifest-json <private-json>`.
   The materializer emits only handle field presence, never handle values. For
   Terminal-Bench, handle presence is still not enough: the payload must prove
   that a local Codex driver owns agent/model/auth and that the remote executor
   does not require agent or Codex runtime. Then build the execution seam from
   those facts. The seam should expose both a `local_driver_contract` and a
   `remote_sandbox_contract`; treat missing command adapters, missing
   launch-adapter results, missing local-driver materializers, missing sandbox
   contracts, remote-agent-runtime requirements, or compact reducers as
   blockers instead of launching a private script.
5. Run the smallest no-upload dry-run or mini-pair that can answer the current
   product question.
6. Ingest a compact result or precise blocker.
7. Update Goal Harness todo/state so the next developer sees the current route.

Do not start from a raw shell command hidden in a local note. If a benchmark
cannot be launched through a documented route, the next product task is to
build that route, not to keep a one-off script alive.

## Capture The Process While Running

Do not wait for a benchmark family to be fully solved before documenting how it
runs. Each real run should improve the developer workflow in the same batch as
the result or blocker:

1. Before launch, write down the intended route, boundary, command shape,
   expected compact artifacts, and stop conditions.
2. During launch, preserve only observable handles that another developer can
   use: pid or job basename, readiness state, poll command, cleanup state, and
   compact artifact refs.
3. After launch, update the workflow or adapter notes with what changed:
   product-path pass, precise blocker, cleanup rule, or stale assumption.
4. If the run required a private local script, turn the reusable part into a
   public command, fixture, or adapter contract before relying on it again.

The goal is a living runner guide. Repeated benchmark attempts should make the
next attempt easier to launch and debug, not only add more private evidence.

## Cloud Codex Route

Use the cloud Codex route as the default for Terminal-Bench, SkillsBench, ALE,
and other Docker-heavy benchmark families when a dedicated benchmark host is
available.

| Owner | Responsibility |
| --- | --- |
| Cloud benchmark host | Codex CLI, benchmark source checkout, runner dependencies, container runtime, task-data staging, no-upload run execution, compact result reduction, and private raw artifacts. |
| Goal Harness repo | Public-safe route contracts, reducer schemas, benchmark ledger ingestion, todo/state writeback, public docs, and focused smokes. |
| Operator | Codex login on the cloud host, benchmark data gates, upload/leaderboard decisions, and any private-material or credential approval. |

The route is intentionally simpler than split-control: SSH reaches the host,
then Codex CLI runs there like a normal developer would. Goal Harness should not
need to understand SSH internals, jump hosts, or remote file bridges in the hot
path. It should only record compact route readiness, result handles, blockers,
and no-upload boundaries.

Default cloud-host readiness:

- SSH access works through the operator's approved access path.
- Codex CLI is installed on the host; auth is completed by the operator on that
  host and is not copied from another machine.
- `git`, Python, `uv`, Node/npm when required, and Docker or a Docker-compatible
  runtime are available.
- Container image pulls use a documented reachable registry or mirror.
- The benchmark workspace is dedicated and private enough for raw artifacts.
- The first task is a no-upload dry-run or mini-pair that writes compact
  `benchmark_run_v0` / `benchmark_result_v0` evidence before any score claim.

Keep upstream benchmark sources clean:

- Use upstream `main` or a pinned upstream commit for official runner code.
- Keep any internal convenience changes on a tiny, rebased adapter branch.
- Prefer wrapper scripts, environment files, and reducer sidecars over editing
  upstream benchmark logic.
- Fork only when we need to preserve a small reusable patch set; keep the fork
  close enough that upstream pulls remain routine.
- Do not mix Goal Harness runner experiments, local bridge probes, raw logs, or
  credential setup into benchmark forks.

## Split-Control Route

The split-control route is now a fallback and research route, not the default
when a dedicated cloud host exists.

Use it when Codex auth cannot live on the execution host, when the host is
shared, or when the product question is specifically about a local Goal Harness
controller using a separate Docker substrate.

| Owner | Responsibility |
| --- | --- |
| Local agent | Codex CLI, auth, model invocation, planning, patch generation, Goal Harness state, quota, todo, and evidence filtering. |
| Remote executor | Docker runtime, runner dependencies, task-data or image staging, bounded command/file execution, and compact result reduction. |

The remote executor is not an agent-auth environment. Missing remote Codex,
Codex ACP, or model credentials is not a benchmark blocker. Real blockers are
things like missing split-control adapter, missing runner tooling, missing task
data or images, missing remote node runtime when a specific runner requires it,
or a failed cleanup/readiness check.

Historical split-control work is still useful: it records which boundaries
matter when credentials cannot move, and it produced adapter/reducer seams that
can be reused for compact evidence. Do not continue adding split-control bridge
layers when a cloud-host route can answer the benchmark question directly.

Treat split-control assets as a retained research branch, not a live default:

- keep durable contracts, reducers, and boundary smokes that still protect
  public behavior;
- do not add new bridge layers unless a cloud-host run is blocked by a concrete
  auth, policy, or host gate;
- move future local-Codex / remote-executor experiments to an explicitly named
  experimental branch or research issue;
- remove or defer mainline split-control code once the cloud-host route has
  equivalent compact evidence for the same benchmark family.

See
[`benchmark-split-control-remote-executor-v0.md`](research/long-horizon-agent-benchmarks/benchmark-split-control-remote-executor-v0.md)
for the current machine contract, and
[`benchmark-route-transition-retrospective-20260619.md`](research/long-horizon-agent-benchmarks/benchmark-route-transition-retrospective-20260619.md)
for the split-control retention, branch-hygiene, and retirement runbook.

## Current Benchmark Families

| Family | Product-path target | Current maturity |
| --- | --- | --- |
| Terminal-Bench | Cloud Codex CLI runs the task on a dedicated benchmark host; Goal Harness ingests compact no-upload evidence. | Prior split-control adapters remain useful reducers, but the next run should prefer direct cloud-host Codex plus container runtime. |
| SkillsBench | Cloud Codex CLI and BenchFlow run on the same dedicated host; Goal Harness records compact base/test mini-pair evidence. | Prior host-local ACP relay work is historical route-repair evidence. Do not add more bridge layers before trying the cloud-host path. |
| Agents' Last Exam | Cloud Codex CLI drives the local-Docker-capable ALE route on the dedicated host; Goal Harness ingests compact no-upload evidence. | Formal task runs still need task-data and public-claim gates, but Docker/Codex colocation should replace the earlier local-host split-control assumption. |

This table is intentionally about runner maturity, not leaderboard score.
Score claims require separate public-safe result ingestion and review.

### SkillsBench Split-Control Preflight

This preflight is retained for historical split-control debugging and for
shared-host environments where Codex auth cannot live on the runner host. It is
not the default route when a dedicated cloud benchmark host is available.

SkillsBench currently uses BenchFlow's ACP stdio worker protocol for Codex-like
agents. For split-control runs, Codex auth, model invocation, and goal state
stay local. Before launching a split-control mini-pair, run:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --local-driver-worker-handshake-preflight \
  --local-codex-cli-participant-ready \
  --local-acp-relay-probe \
  --host-local-acp-transport-probe
```

The preflight is successful only when BenchFlow is importable, the default
Codex agent is registered as ACP, the local Codex CLI participant was already
materialized, the local ACP relay completes `initialize`, `session/new`,
`session/set_model`, and `session/prompt`, BenchFlow's own `ACPClient` can
drive that relay over host-local stdio, and a bounded remote command/file
bridge exists for the sandbox side. The default relay and transport probes are
dry-run: they do not invoke Codex, read task text, copy credentials, record raw
logs, or launch a benchmark task.

Do not treat a successful relay probe as mini-pair readiness. It only proves
the local ACP server shape. The host-local transport probe proves BenchFlow can
talk to that local server without `ContainerTransport`. A no-upload mini-pair
is product-path evidence only after the remote bridge is also materialized, so
the preflight may legitimately return `skillsbench_remote_command_file_bridge_missing`
after both local probes pass.

For the remote bridge, prefer a machine-verifiable probe over a manual
readiness flag:

```bash
python3 scripts/skillsbench_automation_loop.py \
  --local-driver-worker-handshake-preflight \
  --local-codex-cli-participant-ready \
  --local-acp-relay-probe \
  --host-local-acp-transport-probe \
  --remote-command-file-bridge-probe \
  --remote-command-file-bridge-probe-command '<private-remote-bridge-command>'
```

The bridge command reads a fixed JSON request from stdin and writes compact JSON
to stdout. It must prove four bounded operations: `exec`, `write_file`,
`read_file`, and `cleanup`. Its public result records only operation kinds,
statuses, and boundary flags; it must not return raw commands, stdout, stderr,
task text, paths, credentials, logs, trajectories, uploads, or submissions.
`scripts/skillsbench_remote_command_file_bridge.py --serve-probe` is only a
local fake bridge for smoke tests and adapter development. It is not evidence
that a real remote executor is ready.

## Evidence Contract

Benchmark evidence may include:

- benchmark id, task id or public-safe case id;
- arm or mode label;
- readiness gate result;
- process or job handle basename;
- compact result fields such as `score`, `best_score`, `final_score`,
  `first_success_round`, `duration_s`, and `blocker`;
- cleanup state;
- links to public docs or compact JSON/Markdown artifacts.

Benchmark evidence must not include:

- raw task text, hidden task files, verifier body output, or solution material;
- raw trajectories, transcripts, screenshots, stdout, stderr, or shell argv;
- credentials, tokens, local absolute paths, remote absolute paths, or private
  hostnames;
- uploads, submit paths, or leaderboard claims unless a specific public release
  gate has approved them.

## Developer Checklist

Before a PR that changes benchmark behavior:

- Name which layer changed: selection, launch, observe, ingest, scoring, or
  docs.
- Keep benchmark-specific runner details inside the adapter.
- Preserve the split-control boundary when a remote executor is involved.
- Add or update a focused smoke for the durable contract.
- Run `goal-harness check --scan-path <changed-public-path>` for public docs or
  examples.
- Do not commit `.local`, raw logs, private run directories, active state, or
  local runner configs.

## Roadmap

Near-term work should make the benchmark workflow feel like a small product:

- expose a single developer-facing command path for readiness and runner batch
  planning;
- add observable launch handles so long runs can be polled without chat memory;
- align Terminal-Bench, SkillsBench, and Agents' Last Exam on the same
  launch/observe/ingest lifecycle;
- document the no-upload dry-run path before chasing broad score matrices;
- make compact blockers first-class, so a failed launch still teaches the next
  developer exactly what to repair.
